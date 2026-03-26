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
Distributed Task Queue for Agentic Brain

Uses Redpanda consumer groups to distribute tasks across multiple workers.
This provides durable task queue semantics for AI workflows.

Features:
- Multiple task queues with priority support
- Consumer groups for work distribution
- At-least-once delivery guarantees
- Dead letter queues for failed tasks
- Task visibility timeout (requeue if not acknowledged)
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(Enum):
    """Task lifecycle status"""

    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTERED = "dead_lettered"


@dataclass
class Task:
    """A unit of work to be executed by a worker"""

    task_id: str
    queue_name: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING

    # Timing (timezone-aware for proper comparisons)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Execution tracking
    worker_id: Optional[str] = None
    attempt: int = 0
    max_attempts: int = 3
    visibility_timeout: float = 300.0  # 5 minutes

    # Results
    result: Optional[Any] = None
    error: Optional[str] = None

    # Metadata
    workflow_id: Optional[str] = None
    activity_id: Optional[str] = None
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize task to dictionary"""
        return {
            "task_id": self.task_id,
            "queue_name": self.queue_name,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "worker_id": self.worker_id,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "visibility_timeout": self.visibility_timeout,
            "result": self.result,
            "error": self.error,
            "workflow_id": self.workflow_id,
            "activity_id": self.activity_id,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Deserialize task from dictionary"""
        return cls(
            task_id=data["task_id"],
            queue_name=data["queue_name"],
            task_type=data["task_type"],
            payload=data["payload"],
            priority=TaskPriority(data.get("priority", 1)),
            status=TaskStatus(data.get("status", "pending")),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now(timezone.utc)
            ),
            claimed_at=(
                datetime.fromisoformat(data["claimed_at"])
                if data.get("claimed_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            worker_id=data.get("worker_id"),
            attempt=data.get("attempt", 0),
            max_attempts=data.get("max_attempts", 3),
            visibility_timeout=data.get("visibility_timeout", 300.0),
            result=data.get("result"),
            error=data.get("error"),
            workflow_id=data.get("workflow_id"),
            activity_id=data.get("activity_id"),
            correlation_id=data.get("correlation_id"),
        )


class TaskQueue:
    """
    Distributed task queue using Redpanda/Kafka

    Provides:
    - Enqueue tasks with priority
    - Poll for tasks (consumer group distribution)
    - Acknowledge/fail tasks
    - Dead letter queue for permanently failed tasks
    - Visibility timeout for hung tasks
    """

    def __init__(
        self,
        queue_name: str,
        bootstrap_servers: str = "localhost:9092",
        consumer_group: Optional[str] = None,
        visibility_timeout: float = 300.0,
    ):
        self.queue_name = queue_name
        self.bootstrap_servers = bootstrap_servers
        self.consumer_group = consumer_group or f"workers-{queue_name}"
        self.visibility_timeout = visibility_timeout

        # Topic names
        self.topic_name = f"taskqueue.{queue_name}"
        self.dlq_topic = f"taskqueue.{queue_name}.dlq"

        # Kafka/Redpanda clients (lazy init)
        self._producer = None
        self._consumer = None
        self._connected = False

        # In-memory fallback when Redpanda unavailable
        self._pending_tasks: Dict[TaskPriority, List[Task]] = defaultdict(list)
        self._claimed_tasks: Dict[str, Task] = {}
        self._dlq: List[Task] = []
        self._use_memory = False

        # Statistics
        self._stats = {
            "enqueued": 0,
            "claimed": 0,
            "completed": 0,
            "failed": 0,
            "dead_lettered": 0,
            "requeued": 0,
        }

    async def connect(self) -> bool:
        """Connect to Redpanda/Kafka"""
        try:
            from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

            # Create producer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()

            # Create consumer with consumer group
            self._consumer = AIOKafkaConsumer(
                self.topic_name,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                auto_offset_reset="earliest",
                enable_auto_commit=False,  # Manual commit for at-least-once
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            await self._consumer.start()

            self._connected = True
            logger.info(f"Task queue '{self.queue_name}' connected to Redpanda")
            return True

        except ImportError:
            logger.warning("aiokafka not installed, using in-memory task queue")
            self._use_memory = True
            return True
        except Exception as e:
            logger.warning(f"Redpanda connection failed: {e}, using in-memory fallback")
            self._use_memory = True
            return True

    async def disconnect(self) -> None:
        """Disconnect from Redpanda/Kafka"""
        if self._producer:
            await self._producer.stop()
        if self._consumer:
            await self._consumer.stop()
        self._connected = False

    async def enqueue(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        workflow_id: Optional[str] = None,
        activity_id: Optional[str] = None,
        max_attempts: int = 3,
        visibility_timeout: Optional[float] = None,
    ) -> Task:
        """Add a task to the queue"""
        task = Task(
            task_id=str(uuid.uuid4()),
            queue_name=self.queue_name,
            task_type=task_type,
            payload=payload,
            priority=priority,
            workflow_id=workflow_id,
            activity_id=activity_id,
            max_attempts=max_attempts,
            visibility_timeout=visibility_timeout or self.visibility_timeout,
        )

        if self._use_memory:
            # In-memory: add to priority queue
            self._pending_tasks[priority].append(task)
        else:
            # Redpanda: publish to topic
            await self._producer.send_and_wait(
                self.topic_name,
                task.to_dict(),
                key=task.task_id.encode(),
            )

        self._stats["enqueued"] += 1
        logger.debug(f"Enqueued task {task.task_id} to {self.queue_name}")
        return task

    async def poll(
        self,
        worker_id: str,
        max_tasks: int = 1,
        timeout: float = 1.0,
    ) -> List[Task]:
        """Poll for available tasks"""
        tasks = []

        if self._use_memory:
            # In-memory: check priority queues
            for priority in [
                TaskPriority.CRITICAL,
                TaskPriority.HIGH,
                TaskPriority.NORMAL,
                TaskPriority.LOW,
            ]:
                while self._pending_tasks[priority] and len(tasks) < max_tasks:
                    task = self._pending_tasks[priority].pop(0)
                    task.status = TaskStatus.CLAIMED
                    task.claimed_at = datetime.now(timezone.utc)
                    task.worker_id = worker_id
                    self._claimed_tasks[task.task_id] = task
                    tasks.append(task)
        else:
            # Redpanda: consume from topic
            try:
                records = await asyncio.wait_for(
                    self._consumer.getmany(
                        timeout_ms=int(timeout * 1000), max_records=max_tasks
                    ),
                    timeout=timeout + 1,
                )

                for _tp, messages in records.items():
                    for msg in messages:
                        task = Task.from_dict(msg.value)
                        task.status = TaskStatus.CLAIMED
                        task.claimed_at = datetime.now(timezone.utc)
                        task.worker_id = worker_id
                        self._claimed_tasks[task.task_id] = task
                        tasks.append(task)

            except asyncio.TimeoutError:
                pass

        if tasks:
            self._stats["claimed"] += len(tasks)
            logger.debug(
                f"Worker {worker_id} claimed {len(tasks)} tasks from {self.queue_name}"
            )

        return tasks

    async def acknowledge(self, task_id: str, result: Any = None) -> bool:
        """Mark task as successfully completed"""
        task = self._claimed_tasks.get(task_id)
        if not task:
            logger.warning(f"Cannot acknowledge unknown task {task_id}")
            return False

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        task.result = result

        del self._claimed_tasks[task_id]

        if not self._use_memory and self._consumer:
            await self._consumer.commit()

        self._stats["completed"] += 1
        logger.debug(f"Task {task_id} completed successfully")
        return True

    async def fail(
        self,
        task_id: str,
        error: str,
        retry: bool = True,
    ) -> bool:
        """Mark task as failed, optionally retry"""
        task = self._claimed_tasks.get(task_id)
        if not task:
            logger.warning(f"Cannot fail unknown task {task_id}")
            return False

        task.attempt += 1
        task.error = error

        del self._claimed_tasks[task_id]

        if retry and task.attempt < task.max_attempts:
            # Requeue for retry
            task.status = TaskStatus.RETRYING
            task.worker_id = None
            task.claimed_at = None

            if self._use_memory:
                self._pending_tasks[task.priority].append(task)
            else:
                await self._producer.send_and_wait(
                    self.topic_name,
                    task.to_dict(),
                    key=task.task_id.encode(),
                )

            self._stats["requeued"] += 1
            logger.info(
                f"Task {task_id} failed (attempt {task.attempt}/{task.max_attempts}), requeued"
            )
        else:
            # Move to dead letter queue
            task.status = TaskStatus.DEAD_LETTERED

            if self._use_memory:
                self._dlq.append(task)
            else:
                await self._producer.send_and_wait(
                    self.dlq_topic,
                    task.to_dict(),
                    key=task.task_id.encode(),
                )

            self._stats["dead_lettered"] += 1
            logger.warning(
                f"Task {task_id} moved to dead letter queue after {task.attempt} attempts"
            )

        self._stats["failed"] += 1
        return True

    async def check_visibility_timeouts(self) -> int:
        """Check for tasks past visibility timeout and requeue them"""
        now = datetime.now(timezone.utc)
        requeued = 0

        for task_id, task in list(self._claimed_tasks.items()):
            if task.claimed_at:
                elapsed = (now - task.claimed_at).total_seconds()
                if elapsed > task.visibility_timeout:
                    # Task timed out, requeue
                    logger.warning(f"Task {task_id} visibility timeout, requeuing")
                    await self.fail(task_id, "Visibility timeout exceeded", retry=True)
                    requeued += 1

        return requeued

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        pending = sum(len(q) for q in self._pending_tasks.values())
        return {
            "queue_name": self.queue_name,
            "connected": self._connected,
            "using_memory": self._use_memory,
            "pending": pending,
            "claimed": len(self._claimed_tasks),
            "dlq_size": len(self._dlq),
            **self._stats,
        }


class TaskQueueManager:
    """
    Manages multiple task queues

    Provides:
    - Create/get queues by name
    - Global statistics
    - Visibility timeout checker
    """

    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.bootstrap_servers = bootstrap_servers
        self._queues: Dict[str, TaskQueue] = {}
        self._running = False
        self._timeout_checker: Optional[asyncio.Task] = None

    async def get_queue(
        self,
        queue_name: str,
        consumer_group: Optional[str] = None,
        create: bool = True,
    ) -> Optional[TaskQueue]:
        """Get or create a task queue"""
        if queue_name in self._queues:
            return self._queues[queue_name]

        if not create:
            return None

        queue = TaskQueue(
            queue_name=queue_name,
            bootstrap_servers=self.bootstrap_servers,
            consumer_group=consumer_group,
        )
        await queue.connect()
        self._queues[queue_name] = queue
        return queue

    async def start(self) -> None:
        """Start the queue manager"""
        self._running = True
        self._timeout_checker = asyncio.create_task(self._check_timeouts_loop())
        logger.info("Task queue manager started")

    async def stop(self) -> None:
        """Stop the queue manager"""
        self._running = False

        if self._timeout_checker:
            self._timeout_checker.cancel()
            try:
                await self._timeout_checker
            except asyncio.CancelledError:
                pass

        for queue in self._queues.values():
            await queue.disconnect()

        self._queues.clear()
        logger.info("Task queue manager stopped")

    async def _check_timeouts_loop(self) -> None:
        """Background loop to check visibility timeouts"""
        while self._running:
            try:
                for queue in self._queues.values():
                    await queue.check_visibility_timeouts()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Timeout checker error: {e}")
                await asyncio.sleep(10)

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all queues"""
        return {
            "queues": {name: q.get_stats() for name, q in self._queues.items()},
            "total_queues": len(self._queues),
            "running": self._running,
        }


# Pre-configured queue names for common use cases
WORKFLOW_QUEUE = "workflows"  # Main workflow execution
ACTIVITY_QUEUE = "activities"  # Activity execution
LLM_QUEUE = "llm"  # LLM requests (rate limited)
RAG_QUEUE = "rag"  # RAG queries
NOTIFICATION_QUEUE = "notifications"  # Async notifications


async def create_task_queue_manager(
    bootstrap_servers: str = "localhost:9092",
) -> TaskQueueManager:
    """Factory function to create and start a task queue manager"""
    manager = TaskQueueManager(bootstrap_servers=bootstrap_servers)
    await manager.start()

    # Pre-create common queues
    for queue_name in [
        WORKFLOW_QUEUE,
        ACTIVITY_QUEUE,
        LLM_QUEUE,
        RAG_QUEUE,
        NOTIFICATION_QUEUE,
    ]:
        await manager.get_queue(queue_name)

    return manager
