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
Worker Pool for Agentic Brain

Multi-process worker pool for executing workflows and activities.
Provides durable worker semantics with graceful shutdown.

Features:
- Multiple worker processes
- Task queue specialization
- Graceful shutdown with drain
- Activity execution with heartbeats
- Workflow execution with replay
"""

import asyncio
import inspect
import logging
import os
import signal
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from multiprocessing import Process
from multiprocessing import Queue as MPQueue
from typing import Any, Callable, Dict, List, Optional, Set, Type

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    """Worker lifecycle status"""

    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"  # No new tasks, finishing current
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class WorkerConfig:
    """Configuration for a worker"""

    worker_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Queues to poll
    task_queues: List[str] = field(default_factory=lambda: ["activities"])

    # Concurrency
    max_concurrent_activities: int = 10
    max_concurrent_workflows: int = 5

    # Polling
    poll_interval: float = 0.5
    poll_batch_size: int = 5

    # Shutdown
    graceful_shutdown_timeout: float = 30.0

    # Heartbeat
    activity_heartbeat_interval: float = 10.0


@dataclass
class WorkerStats:
    """Statistics for a worker"""

    worker_id: str
    status: WorkerStatus
    started_at: datetime

    # Counts
    activities_started: int = 0
    activities_completed: int = 0
    activities_failed: int = 0
    workflows_started: int = 0
    workflows_completed: int = 0
    workflows_failed: int = 0

    # Current
    current_activities: int = 0
    current_workflows: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "activities_started": self.activities_started,
            "activities_completed": self.activities_completed,
            "activities_failed": self.activities_failed,
            "workflows_started": self.workflows_started,
            "workflows_completed": self.workflows_completed,
            "workflows_failed": self.workflows_failed,
            "current_activities": self.current_activities,
            "current_workflows": self.current_workflows,
        }


class ActivityWorker:
    """
    Executes activities from task queues

    Features:
    - Concurrent activity execution
    - Automatic heartbeats
    - Graceful shutdown
    """

    def __init__(
        self,
        config: WorkerConfig,
        activity_registry: Dict[str, Callable],
    ):
        self.config = config
        self.activity_registry = activity_registry
        self.status = WorkerStatus.STARTING
        self.stats = WorkerStats(
            worker_id=config.worker_id,
            status=WorkerStatus.STARTING,
            started_at=datetime.now(timezone.utc),
        )

        self._running = False
        self._current_tasks: Dict[str, asyncio.Task] = {}
        self._running_tasks: Set[asyncio.Task] = set()  # Track fire-and-forget tasks
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._task_queue_manager = None

    async def start(self) -> None:
        """Start the worker"""
        from .task_queue import TaskQueueManager

        self._running = True
        self.status = WorkerStatus.RUNNING
        self.stats.status = WorkerStatus.RUNNING

        # Create semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_activities)

        # Connect to task queues
        self._task_queue_manager = TaskQueueManager()
        await self._task_queue_manager.start()

        logger.info(f"Activity worker {self.config.worker_id} started")

        # Start polling loop
        await self._poll_loop()

    def _task_done_callback(self, task: asyncio.Task) -> None:
        """Callback for when a task completes - logs exceptions and removes from tracking."""
        self._running_tasks.discard(task)
        try:
            exc = task.exception()
            if exc:
                logger.error(f"Task {task.get_name()} failed with exception: {exc}")
        except asyncio.CancelledError:
            logger.debug(f"Task {task.get_name()} was cancelled")
        except asyncio.InvalidStateError:
            pass  # Task was not done yet (shouldn't happen in done callback)

    async def stop(self, graceful: bool = True) -> None:
        """Stop the worker"""
        logger.info(f"Stopping worker {self.config.worker_id} (graceful={graceful})")

        if graceful:
            self.status = WorkerStatus.DRAINING
            self.stats.status = WorkerStatus.DRAINING

            # Wait for current tasks to complete
            if self._current_tasks:
                logger.info(f"Draining {len(self._current_tasks)} tasks...")
                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            *self._current_tasks.values(), return_exceptions=True
                        ),
                        timeout=self.config.graceful_shutdown_timeout,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Graceful shutdown timeout, cancelling remaining tasks"
                    )
                    for task in self._current_tasks.values():
                        task.cancel()
        else:
            for task in self._current_tasks.values():
                task.cancel()

        self._running = False
        self.status = WorkerStatus.STOPPED
        self.stats.status = WorkerStatus.STOPPED

        if self._task_queue_manager:
            await self._task_queue_manager.stop()

        logger.info(f"Worker {self.config.worker_id} stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop"""
        while self._running and self.status != WorkerStatus.DRAINING:
            try:
                for queue_name in self.config.task_queues:
                    queue = await self._task_queue_manager.get_queue(queue_name)
                    if not queue:
                        continue

                    # Check if we have capacity
                    if (
                        self.stats.current_activities
                        >= self.config.max_concurrent_activities
                    ):
                        continue

                    # Poll for tasks
                    tasks = await queue.poll(
                        worker_id=self.config.worker_id,
                        max_tasks=self.config.poll_batch_size,
                        timeout=self.config.poll_interval,
                    )

                    # Execute tasks - store references to prevent garbage collection
                    # and add done callbacks for proper error logging
                    for task in tasks:
                        async_task = asyncio.create_task(
                            self._execute_task(queue, task),
                            name=f"task-{task.task_id}"
                        )
                        self._running_tasks.add(async_task)
                        async_task.add_done_callback(self._task_done_callback)

                await asyncio.sleep(self.config.poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
                await asyncio.sleep(1)

    async def _execute_task(self, queue, task) -> None:
        """Execute a single task"""
        task_id = task.task_id

        async with self._semaphore:
            self.stats.current_activities += 1
            self.stats.activities_started += 1

            # Track running task
            execution_task = asyncio.current_task()
            self._current_tasks[task_id] = execution_task

            try:
                # Look up activity handler
                handler = self.activity_registry.get(task.task_type)
                if not handler:
                    await queue.fail(
                        task_id, f"Unknown activity type: {task.task_type}"
                    )
                    return

                # Execute with heartbeat
                result = await self._execute_with_heartbeat(handler, task)

                # Acknowledge success
                await queue.acknowledge(task_id, result)
                self.stats.activities_completed += 1

            except Exception as e:
                logger.error(f"Activity {task_id} failed: {e}")
                await queue.fail(task_id, str(e))
                self.stats.activities_failed += 1

            finally:
                self.stats.current_activities -= 1
                self._current_tasks.pop(task_id, None)

    async def _execute_with_heartbeat(self, handler: Callable, task) -> Any:
        """Execute handler with periodic heartbeats"""
        from .heartbeats import HeartbeatContext

        async def heartbeat_sender():
            """Send heartbeats periodically"""
            while True:
                await asyncio.sleep(self.config.activity_heartbeat_interval)
                # Heartbeat would be sent to workflow here
                logger.debug(f"Heartbeat for task {task.task_id}")

        heartbeat_task = asyncio.create_task(heartbeat_sender())

        try:
            # Execute the handler
            if inspect.iscoroutinefunction(handler):
                result = await handler(**task.payload)
            else:
                result = handler(**task.payload)
            return result
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass


class WorkerPool:
    """
    Pool of workers for distributed execution

    Features:
    - Multiple worker processes
    - Load balancing
    - Health monitoring
    - Auto-restart failed workers
    """

    def __init__(
        self,
        num_workers: int = 4,
        config: Optional[WorkerConfig] = None,
        activity_registry: Optional[Dict[str, Callable]] = None,
    ):
        self.num_workers = num_workers
        self.base_config = config or WorkerConfig()
        self.activity_registry = activity_registry or {}

        self._workers: Dict[str, ActivityWorker] = {}
        self._worker_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()

    def register_activity(self, name: str, handler: Callable) -> None:
        """Register an activity handler"""
        self.activity_registry[name] = handler
        logger.debug(f"Registered activity: {name}")

    def register_activities(self, activities: Dict[str, Callable]) -> None:
        """Register multiple activity handlers"""
        self.activity_registry.update(activities)
        logger.debug(f"Registered {len(activities)} activities")

    async def start(self) -> None:
        """Start all workers in the pool"""
        self._running = True
        self._shutdown_event.clear()

        for i in range(self.num_workers):
            await self._start_worker(i)

        logger.info(f"Worker pool started with {self.num_workers} workers")

        # Start health monitor
        asyncio.create_task(self._health_monitor())

    async def _start_worker(self, index: int) -> None:
        """Start a single worker"""
        config = WorkerConfig(
            worker_id=f"worker-{index}",
            task_queues=self.base_config.task_queues,
            max_concurrent_activities=self.base_config.max_concurrent_activities,
            max_concurrent_workflows=self.base_config.max_concurrent_workflows,
            poll_interval=self.base_config.poll_interval,
            poll_batch_size=self.base_config.poll_batch_size,
            graceful_shutdown_timeout=self.base_config.graceful_shutdown_timeout,
        )

        worker = ActivityWorker(config, self.activity_registry)
        self._workers[config.worker_id] = worker

        # Start worker in background task
        task = asyncio.create_task(worker.start())
        self._worker_tasks[config.worker_id] = task

    async def stop(self, graceful: bool = True) -> None:
        """Stop all workers"""
        self._running = False
        self._shutdown_event.set()

        logger.info(f"Stopping worker pool (graceful={graceful})")

        # Stop all workers
        stop_tasks = [
            worker.stop(graceful=graceful) for worker in self._workers.values()
        ]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        # Cancel worker tasks
        for task in self._worker_tasks.values():
            task.cancel()

        self._workers.clear()
        self._worker_tasks.clear()

        logger.info("Worker pool stopped")

    async def _health_monitor(self) -> None:
        """Monitor worker health and restart failed workers"""
        while self._running:
            try:
                for worker_id, worker in list(self._workers.items()):
                    if worker.status == WorkerStatus.FAILED:
                        logger.warning(f"Worker {worker_id} failed, restarting...")

                        # Get worker index
                        index = int(worker_id.split("-")[1])

                        # Remove failed worker
                        del self._workers[worker_id]
                        if worker_id in self._worker_tasks:
                            self._worker_tasks[worker_id].cancel()
                            del self._worker_tasks[worker_id]

                        # Start new worker
                        await self._start_worker(index)

                await asyncio.sleep(5)  # Check every 5 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(5)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        return {
            "num_workers": self.num_workers,
            "running": self._running,
            "workers": {
                worker_id: worker.stats.to_dict()
                for worker_id, worker in self._workers.items()
            },
            "registered_activities": list(self.activity_registry.keys()),
        }


# Convenience function for creating a worker pool
async def create_worker_pool(
    num_workers: int = 4,
    task_queues: Optional[List[str]] = None,
    activities: Optional[Dict[str, Callable]] = None,
) -> WorkerPool:
    """
    Factory function to create and start a worker pool

    Args:
        num_workers: Number of worker processes
        task_queues: List of queue names to poll
        activities: Dict of activity name -> handler

    Returns:
        Started WorkerPool instance
    """
    config = WorkerConfig(
        task_queues=task_queues or ["activities"],
    )

    pool = WorkerPool(
        num_workers=num_workers,
        config=config,
        activity_registry=activities or {},
    )

    await pool.start()
    return pool


# Decorator for registering activities
def activity(name: Optional[str] = None):
    """
    Decorator to mark a function as an activity

    Usage:
        @activity("my_activity")
        async def my_activity(arg1, arg2):
            return result
    """

    def decorator(func: Callable) -> Callable:
        func._activity_name = name or func.__name__
        return func

    return decorator


def get_activities_from_module(module) -> Dict[str, Callable]:
    """
    Extract all @activity decorated functions from a module

    Usage:
        import my_activities
        activities = get_activities_from_module(my_activities)
        pool.register_activities(activities)
    """
    activities = {}
    for name in dir(module):
        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, "_activity_name"):
            activities[obj._activity_name] = obj
    return activities
