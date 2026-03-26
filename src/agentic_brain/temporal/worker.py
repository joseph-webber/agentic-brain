# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""
Temporal worker compatibility module.

Provides Worker class matching temporalio.worker exactly:
- Worker(client, task_queue, workflows, activities)
- worker.run() - Start processing
- worker.shutdown() - Graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, Union

from ..durability import (
    ActivityWorker,
    TaskQueue,
    TaskQueueManager,
    WorkerPool,
)
from .client import Client

logger = logging.getLogger(__name__)


# ============================================================================
# Worker Configuration
# ============================================================================


@dataclass
class WorkerConfig:
    """Worker configuration options."""

    max_concurrent_activities: int = 100
    max_concurrent_workflow_tasks: int = 100
    max_concurrent_local_activities: int = 100
    max_cached_workflows: int = 1000
    no_remote_activities: bool = False
    sticky_queue_schedule_to_start_timeout: timedelta = timedelta(seconds=10)
    max_heartbeat_throttle_interval: timedelta = timedelta(seconds=60)
    default_heartbeat_throttle_interval: timedelta = timedelta(seconds=30)
    max_activities_per_second: Optional[float] = None
    max_task_queue_activities_per_second: Optional[float] = None
    graceful_shutdown_timeout: timedelta = timedelta(seconds=10)
    shared_state_manager: Optional[Any] = None
    debug_mode: bool = False
    disable_eager_activity_execution: bool = False
    on_fatal_error: Optional[Callable[[Exception], None]] = None
    use_worker_versioning: bool = False
    build_id: Optional[str] = None
    identity: Optional[str] = None


# ============================================================================
# Worker (matches temporalio.worker.Worker)
# ============================================================================


class Worker:
    """
    Worker that processes workflows and activities.

    Matches temporalio.worker.Worker API exactly.

    Unlike Temporal, workers run in-process with no server needed!

    Usage:
        async def main():
            client = await Client.connect("localhost:7233")

            worker = Worker(
                client,
                task_queue="my-queue",
                workflows=[MyWorkflow],
                activities=[my_activity],
            )

            await worker.run()
    """

    def __init__(
        self,
        client: Client,
        task_queue: str,
        *,
        workflows: Sequence[Type] = (),
        activities: Sequence[Callable] = (),
        activity_executor: Optional[Any] = None,
        workflow_task_executor: Optional[Any] = None,
        workflow_runner: Optional[Any] = None,
        unsandboxed_workflow_runner: Optional[Any] = None,
        interceptors: Sequence[Any] = (),
        build_id: Optional[str] = None,
        identity: Optional[str] = None,
        max_cached_workflows: int = 1000,
        max_concurrent_workflow_tasks: int = 100,
        max_concurrent_activities: int = 100,
        max_concurrent_local_activities: int = 100,
        max_concurrent_workflow_task_polls: int = 5,
        nonsticky_to_sticky_poll_ratio: float = 0.2,
        max_concurrent_activity_task_polls: int = 5,
        no_remote_activities: bool = False,
        sticky_queue_schedule_to_start_timeout: timedelta = timedelta(seconds=10),
        max_heartbeat_throttle_interval: timedelta = timedelta(seconds=60),
        default_heartbeat_throttle_interval: timedelta = timedelta(seconds=30),
        max_activities_per_second: Optional[float] = None,
        max_task_queue_activities_per_second: Optional[float] = None,
        graceful_shutdown_timeout: timedelta = timedelta(seconds=0),
        shared_state_manager: Optional[Any] = None,
        debug_mode: bool = False,
        disable_eager_activity_execution: bool = False,
        on_fatal_error: Optional[Callable[[Exception], None]] = None,
        use_worker_versioning: bool = False,
    ):
        """
        Create a worker.

        Args:
            client: The connected client
            task_queue: Name of the task queue to poll
            workflows: Workflow classes to register
            activities: Activity functions to register
            max_concurrent_activities: Max concurrent activity tasks
            max_concurrent_workflow_tasks: Max concurrent workflow tasks
            graceful_shutdown_timeout: Shutdown timeout
            debug_mode: Enable debug logging
        """
        self.client = client
        self.task_queue = task_queue
        self.workflows = list(workflows)
        self.activities = list(activities)
        self.max_concurrent_activities = max_concurrent_activities
        self.max_concurrent_workflow_tasks = max_concurrent_workflow_tasks
        self.graceful_shutdown_timeout = graceful_shutdown_timeout
        self.debug_mode = debug_mode
        self.on_fatal_error = on_fatal_error
        self.build_id = build_id
        self.identity = identity

        # Internal state
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._worker_pool: Optional[WorkerPool] = None
        self._task_queue_manager: Optional[TaskQueueManager] = None

        # Register workflows and activities
        self._workflow_registry: Dict[str, Type] = {}
        self._activity_registry: Dict[str, Callable] = {}

        for wf in workflows:
            name = getattr(wf, "_temporal_workflow_name", wf.__name__)
            self._workflow_registry[name] = wf

        for act in activities:
            name = getattr(act, "_temporal_activity_name", act.__name__)
            self._activity_registry[name] = act

    async def run(self) -> None:
        """
        Run the worker until shutdown.

        This method blocks until shutdown() is called.

        Usage:
            # Run forever
            await worker.run()

            # Or run with cancellation
            try:
                await worker.run()
            except asyncio.CancelledError:
                pass
        """
        if self._running:
            raise RuntimeError("Worker is already running")

        self._running = True
        self._shutdown_event.clear()

        logger.info(
            f"Worker starting on task queue '{self.task_queue}' "
            f"with {len(self.workflows)} workflows and {len(self.activities)} activities"
        )

        # Create task queue manager
        self._task_queue_manager = TaskQueueManager()
        task_queue = TaskQueue(name=self.task_queue)
        self._task_queue_manager.register_queue(task_queue)

        # Create worker pool for activities
        config = WorkerConfig(
            max_workers=self.max_concurrent_activities,
            task_queue=self.task_queue,
        )
        self._worker_pool = WorkerPool(config)

        # Register activities with pool
        for name, activity in self._activity_registry.items():
            self._worker_pool.register_activity(name, activity)

        try:
            # Start worker pool
            await self._worker_pool.start()

            # Wait for shutdown
            await self._shutdown_event.wait()

        except asyncio.CancelledError:
            logger.info("Worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Worker error: {e}")
            if self.on_fatal_error:
                self.on_fatal_error(e)
            raise
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self._worker_pool:
            await self._worker_pool.shutdown(
                timeout=self.graceful_shutdown_timeout.total_seconds()
            )
        self._running = False
        logger.info("Worker stopped")

    async def shutdown(self) -> None:
        """
        Initiate graceful shutdown.

        Waits for in-progress tasks to complete.
        """
        logger.info("Worker shutdown requested")
        self._shutdown_event.set()

    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running

    def is_shutdown(self) -> bool:
        """Check if worker is shut down."""
        return not self._running

    async def __aenter__(self) -> Worker:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        if self._running:
            await self.shutdown()


# ============================================================================
# Convenience Functions
# ============================================================================


async def run_worker(
    client: Client,
    task_queue: str,
    workflows: Sequence[Type] = (),
    activities: Sequence[Callable] = (),
    **kwargs,
) -> None:
    """
    Convenience function to create and run a worker.

    Usage:
        await run_worker(
            client,
            "my-queue",
            workflows=[MyWorkflow],
            activities=[my_activity],
        )
    """
    worker = Worker(
        client,
        task_queue,
        workflows=workflows,
        activities=activities,
        **kwargs,
    )
    await worker.run()


# ============================================================================
# Module-level exports matching temporalio.worker
# ============================================================================

__all__ = [
    "Worker",
    "WorkerConfig",
    "run_worker",
]
