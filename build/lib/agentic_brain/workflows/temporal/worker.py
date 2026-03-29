# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Temporal worker implementation."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any, Optional

# Optional dependency - graceful fallback if not installed
try:
    from temporalio.client import Client
    from temporalio.worker import Worker

    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False
    Client = None  # type: ignore
    Worker = None  # type: ignore

from . import activities, workflows
from .client import TemporalClient, TemporalConfig

logger = logging.getLogger(__name__)


class TemporalWorker:
    """Worker for executing Temporal workflows and activities."""

    def __init__(
        self,
        task_queue: str = "agentic-brain",
        config: Optional[TemporalConfig] = None,
        max_concurrent_activities: int = 100,
        max_concurrent_workflows: int = 100,
    ):
        """Initialize Temporal worker.

        Args:
            task_queue: Task queue to poll.
            config: Temporal configuration.
            max_concurrent_activities: Max concurrent activities.
            max_concurrent_workflows: Max concurrent workflows.
        """
        self.task_queue = task_queue
        self.client_wrapper = TemporalClient(config)
        self.max_concurrent_activities = max_concurrent_activities
        self.max_concurrent_workflows = max_concurrent_workflows
        self._worker: Optional[Worker] = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the worker."""
        if not TEMPORALIO_AVAILABLE:
            raise ImportError(
                "temporalio is not installed. Install with: pip install temporalio"
            )

        client = await self.client_wrapper.connect()

        logger.info(f"Starting worker on task queue: {self.task_queue}")

        # Register all workflows and activities
        self._worker = Worker(
            client,
            task_queue=self.task_queue,
            workflows=[
                workflows.RAGWorkflow,
                workflows.AgentWorkflow,
                workflows.CommerceWorkflow,
                workflows.LongRunningAnalysisWorkflow,
            ],
            activities=[
                activities.llm_query,
                activities.vector_search,
                activities.database_operation,
                activities.external_api_call,
                activities.process_file,
                activities.send_notification,
            ],
            max_concurrent_activities=self.max_concurrent_activities,
            max_concurrent_workflow_tasks=self.max_concurrent_workflows,
        )

        logger.info("Worker registered workflows and activities")

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.shutdown()),
            )

        # Run worker until shutdown
        logger.info("Worker started and polling for tasks")
        await self._worker.run()

    async def shutdown(self) -> None:
        """Gracefully shutdown the worker."""
        logger.info("Shutting down worker...")

        if self._worker:
            await self._worker.shutdown()
            logger.info("Worker shutdown complete")

        await self.client_wrapper.close()
        self._shutdown_event.set()

    async def health_check(self) -> dict[str, Any]:
        """Check worker health.

        Returns:
            Health status.
        """
        try:
            client = await self.client_wrapper.connect()
            # Simple health check: try to list workflows
            await client.list_workflows(page_size=1).__anext__()
            return {
                "status": "healthy",
                "task_queue": self.task_queue,
                "connected": True,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "task_queue": self.task_queue,
                "connected": False,
                "error": str(e),
            }


async def start_worker(
    task_queue: str = "agentic-brain",
    config: Optional[TemporalConfig] = None,
) -> None:
    """Start a Temporal worker.

    Args:
        task_queue: Task queue to poll.
        config: Temporal configuration.
    """
    worker = TemporalWorker(task_queue=task_queue, config=config)
    await worker.start()
