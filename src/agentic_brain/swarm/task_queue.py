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

"""
Distributed task queue for swarm agents.

Tasks flow through three Redis structures:

    swarm:{swarm_id}:tasks              LIST  pending tasks (LPUSH / BRPOP)
    swarm:{swarm_id}:tasks:inflight     HASH  task_id -> task JSON (being worked on)
    swarm:{swarm_id}:tasks:failed       LIST  tasks that exhausted retries

Workers call ``claim()`` which atomically moves a task from the pending list
into the inflight hash.  On completion they call ``complete()`` or ``fail()``.

Visibility timeout: a background sweep in ``requeue_stalled()`` re-enqueues
tasks whose inflight TTL has elapsed, enabling automatic recovery from
crashed workers.

Example::

    queue = TaskQueue(coordinator, swarm_id="pr-review-42")

    # Producer
    tids = queue.enqueue_many([
        {"action": "review", "file": "main.py"},
        {"action": "review", "file": "utils.py"},
    ])

    # Worker loop
    while True:
        task = queue.claim(timeout=5)
        if task is None:
            break
        try:
            result = do_work(task)
            queue.complete(task["task_id"], result=result)
        except Exception as exc:
            queue.fail(task["task_id"], error=str(exc))
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Dict, List, Optional

from .redis_coordinator import (
    SwarmCoordinator,
    _dumps,
    _loads,
    _key_tasks,
    _key_results,
)

logger = logging.getLogger(__name__)

_DEFAULT_VISIBILITY_TIMEOUT = 120  # seconds before inflight task is re-queued
_DEFAULT_MAX_RETRIES = 3


def _key_inflight(swarm_id: str) -> str:
    return f"swarm:{swarm_id}:tasks:inflight"


def _key_inflight_ts(swarm_id: str) -> str:
    return f"swarm:{swarm_id}:tasks:inflight:ts"


def _key_failed(swarm_id: str) -> str:
    return f"swarm:{swarm_id}:tasks:failed"


def _key_retry_count(swarm_id: str, task_id: str) -> str:
    return f"swarm:{swarm_id}:tasks:retry:{task_id}"


class TaskState(StrEnum):
    PENDING = "pending"
    INFLIGHT = "inflight"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    task_id: str
    state: TaskState
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    agent_id: Optional[str] = None


class TaskQueue:
    """
    Reliable distributed task queue backed by Redis.

    Provides at-least-once delivery with configurable retries and
    visibility timeout for automatic stall recovery.
    """

    def __init__(
        self,
        coordinator: SwarmCoordinator,
        swarm_id: str,
        *,
        visibility_timeout: int = _DEFAULT_VISIBILITY_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ) -> None:
        self._c = coordinator
        self._r = coordinator._r
        self.swarm_id = swarm_id
        self.visibility_timeout = visibility_timeout
        self.max_retries = max_retries

    # ------------------------------------------------------------------
    # Enqueueing
    # ------------------------------------------------------------------

    def enqueue(
        self,
        task: Dict[str, Any],
        *,
        task_id: str | None = None,
        priority: int = 0,
    ) -> str:
        """Push a single task. Returns the task_id."""
        return self._c.push_task(
            self.swarm_id,
            task,
            task_id=task_id,
            priority=priority,
        )

    def enqueue_many(
        self,
        tasks: List[Dict[str, Any]],
        *,
        priority: int = 0,
    ) -> List[str]:
        """Push multiple tasks atomically (pipeline).  Returns list of task_ids."""
        ids: List[str] = []
        with self._r.pipeline() as pipe:
            for task in tasks:
                tid = str(uuid.uuid4())
                enriched = {
                    **task,
                    "task_id": tid,
                    "priority": priority,
                    "enqueued_at": time.time(),
                }
                pipe.lpush(_key_tasks(self.swarm_id), _dumps(enriched))
                ids.append(tid)
            pipe.execute()
        return ids

    # ------------------------------------------------------------------
    # Claiming & completing
    # ------------------------------------------------------------------

    def claim(
        self,
        *,
        agent_id: str | None = None,
        timeout: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        Claim the next task from the queue.

        Moves the task from the pending list into the inflight hash so that
        stalled tasks can be automatically re-queued after *visibility_timeout*.
        """
        if timeout > 0:
            item = self._r.brpop(_key_tasks(self.swarm_id), timeout=timeout)
            if not item:
                return None
            _, raw = item
        else:
            raw = self._r.rpop(_key_tasks(self.swarm_id))
            if raw is None:
                return None

        task = _loads(raw)
        tid = task["task_id"]
        task["claimed_at"] = time.time()
        task["agent_id"] = agent_id
        task["state"] = TaskState.INFLIGHT

        # Track inflight: hash (task body) + sorted set (for TTL scanning)
        self._r.hset(_key_inflight(self.swarm_id), tid, _dumps(task))
        self._r.zadd(_key_inflight_ts(self.swarm_id), {tid: time.time()})

        logger.debug("Task %s claimed by agent=%s in swarm %s", tid, agent_id, self.swarm_id)
        return task

    def complete(
        self,
        task_id: str,
        *,
        result: Any = None,
        agent_id: str | None = None,
    ) -> TaskResult:
        """Mark a task as completed and store the result."""
        raw = self._r.hget(_key_inflight(self.swarm_id), task_id)
        task = _loads(raw) if raw else {"task_id": task_id}

        task_result: Dict[str, Any] = {
            **task,
            "state": TaskState.COMPLETED,
            "result": result,
            "finished_at": time.time(),
            "agent_id": agent_id or task.get("agent_id"),
        }
        self._r.lpush(_key_results(self.swarm_id), _dumps(task_result))
        self._cleanup_inflight(task_id)

        logger.debug("Task %s completed in swarm %s", task_id, self.swarm_id)
        return TaskResult(
            task_id=task_id,
            state=TaskState.COMPLETED,
            result=result,
            finished_at=task_result["finished_at"],
            agent_id=task_result.get("agent_id"),
        )

    def fail(
        self,
        task_id: str,
        *,
        error: str = "unknown error",
        agent_id: str | None = None,
    ) -> TaskResult:
        """
        Mark a task as failed.

        If retry budget remains, the task is re-enqueued.
        Otherwise it moves to the dead-letter failed list.
        """
        raw = self._r.hget(_key_inflight(self.swarm_id), task_id)
        task = _loads(raw) if raw else {"task_id": task_id}

        retries = int(self._r.incr(_key_retry_count(self.swarm_id, task_id)))
        self._cleanup_inflight(task_id)

        if retries <= self.max_retries:
            task["retry_count"] = retries
            task["last_error"] = error
            task["enqueued_at"] = time.time()
            self._r.lpush(_key_tasks(self.swarm_id), _dumps(task))
            logger.warning(
                "Task %s failed (retry %d/%d): %s", task_id, retries, self.max_retries, error
            )
            return TaskResult(
                task_id=task_id, state=TaskState.PENDING, error=error
            )

        # Dead-letter
        dl: Dict[str, Any] = {
            **task,
            "state": TaskState.FAILED,
            "error": error,
            "failed_at": time.time(),
            "retry_count": retries,
            "agent_id": agent_id or task.get("agent_id"),
        }
        self._r.lpush(_key_failed(self.swarm_id), _dumps(dl))
        logger.error(
            "Task %s permanently failed after %d retries: %s", task_id, retries, error
        )
        return TaskResult(
            task_id=task_id, state=TaskState.FAILED, error=error, agent_id=dl.get("agent_id")
        )

    # ------------------------------------------------------------------
    # Stall recovery
    # ------------------------------------------------------------------

    def requeue_stalled(self) -> List[str]:
        """
        Re-enqueue inflight tasks whose visibility timeout has elapsed.

        Call periodically from a supervisor or health-check loop.
        Returns list of re-queued task_ids.
        """
        cutoff = time.time() - self.visibility_timeout
        stalled_ids = self._r.zrangebyscore(_key_inflight_ts(self.swarm_id), 0, cutoff)
        requeued: List[str] = []
        for tid in stalled_ids:
            raw = self._r.hget(_key_inflight(self.swarm_id), tid)
            if not raw:
                self._r.zrem(_key_inflight_ts(self.swarm_id), tid)
                continue
            task = _loads(raw)
            task["stall_requeued_at"] = time.time()
            self._r.lpush(_key_tasks(self.swarm_id), _dumps(task))
            self._cleanup_inflight(str(tid))
            requeued.append(str(tid))
            logger.warning("Re-queued stalled task %s in swarm %s", tid, self.swarm_id)
        return requeued

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, int]:
        """Return queue depth counters."""
        return {
            "pending": int(self._r.llen(_key_tasks(self.swarm_id))),
            "inflight": int(self._r.hlen(_key_inflight(self.swarm_id))),
            "completed": int(self._r.llen(_key_results(self.swarm_id))),
            "failed": int(self._r.llen(_key_failed(self.swarm_id))),
        }

    def failed_tasks(self, *, limit: int = 0) -> List[Dict[str, Any]]:
        """Return dead-lettered tasks (all or up to *limit*)."""
        raw_list = self._r.lrange(_key_failed(self.swarm_id), 0, limit - 1 if limit else -1)
        return [_loads(r) for r in raw_list]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _cleanup_inflight(self, task_id: str) -> None:
        self._r.hdel(_key_inflight(self.swarm_id), task_id)
        self._r.zrem(_key_inflight_ts(self.swarm_id), task_id)
