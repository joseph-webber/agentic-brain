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
Redis-based swarm coordination for multi-agent development.

Coordinates multiple agents through Redis primitives:
- Agent registration and heartbeating
- Pub/sub event bus for coordination messages
- Distributed task lists
- Result aggregation

Key patterns (swarm_id is an opaque string, e.g. "pr-review-42"):
    swarm:{swarm_id}:agents      HASH  agent_id -> metadata JSON
    swarm:{swarm_id}:agents:set  SET   active agent IDs
    swarm:{swarm_id}:tasks       LIST  pending tasks (LPUSH / BRPOP)
    swarm:{swarm_id}:results     LIST  completed results
    swarm:{swarm_id}:status      HASH  overall swarm health
    swarm:{swarm_id}:hb:{id}     STRING  heartbeat (TTL key)
    swarm:channel:{swarm_id}     pub/sub coordination channel

Usage::

    coord = SwarmCoordinator.from_url("redis://:BrainRedis2026@localhost:6379/0")
    coord.start_swarm("pr-review-42", total_tasks=10)
    coord.register_agent("pr-review-42", "agent-1", capabilities=["python", "git"])

    # Publish a coordination event
    coord.publish("pr-review-42", {"type": "start", "agent": "agent-1"})

    # Enqueue tasks
    coord.push_task("pr-review-42", {"file": "main.py", "action": "review"})

    # Workers pull + store results
    task = coord.pull_task("pr-review-42", timeout=5)
    coord.push_result("pr-review-42", {**task, "result": "ok"})

    # Get swarm status
    status = coord.swarm_status("pr-review-42")
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

REDIS_URL_DEFAULT = "redis://:BrainRedis2026@localhost:6379/0"
_AGENT_TTL = 60  # heartbeat TTL in seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _loads(raw: str | bytes) -> Any:
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Key builders
# ---------------------------------------------------------------------------


def _key_agents_hash(swarm_id: str) -> str:
    return f"swarm:{swarm_id}:agents"


def _key_agents_set(swarm_id: str) -> str:
    return f"swarm:{swarm_id}:agents:set"


def _key_tasks(swarm_id: str) -> str:
    return f"swarm:{swarm_id}:tasks"


def _key_results(swarm_id: str) -> str:
    return f"swarm:{swarm_id}:results"


def _key_status(swarm_id: str) -> str:
    return f"swarm:{swarm_id}:status"


def _key_hb(swarm_id: str, agent_id: str) -> str:
    return f"swarm:{swarm_id}:hb:{agent_id}"


def _key_channel(swarm_id: str) -> str:
    return f"swarm:channel:{swarm_id}"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class SwarmStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CoordinationEvent:
    """An event published on the swarm channel."""

    event_type: str
    swarm_id: str
    agent_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "swarm_id": self.swarm_id,
            "agent_id": self.agent_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CoordinationEvent:
        return cls(
            event_id=d.get("event_id", ""),
            event_type=d["event_type"],
            swarm_id=d["swarm_id"],
            agent_id=d.get("agent_id"),
            payload=d.get("payload", {}),
            timestamp=d.get("timestamp", time.time()),
        )


# ---------------------------------------------------------------------------
# Main coordinator
# ---------------------------------------------------------------------------


class SwarmCoordinator:
    """
    Redis-backed coordinator for multi-agent swarms.

    One coordinator instance can manage many swarms simultaneously.
    Each swarm is identified by an opaque ``swarm_id`` string.
    """

    def __init__(self, redis_client: Any, *, url: str | None = None) -> None:
        self._r = redis_client
        self._url = url
        self._shutdown = threading.Event()
        self._subscriber_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_url(cls, url: str = REDIS_URL_DEFAULT) -> SwarmCoordinator:
        """Create a coordinator from a Redis URL.  Connection is lazy."""
        try:
            import redis  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "redis package required: pip install 'agentic-brain[redis]'"
            ) from exc
        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=5)
        return cls(client, url=url)

    @classmethod
    def from_pool(cls, pool_manager: Any) -> SwarmCoordinator:
        """Create a coordinator from an existing RedisPoolManager."""
        return cls(pool_manager.client)

    # ------------------------------------------------------------------
    # Swarm lifecycle
    # ------------------------------------------------------------------

    def start_swarm(
        self,
        swarm_id: str,
        *,
        total_tasks: int = 0,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        """Initialise swarm metadata in Redis."""
        status: Dict[str, Any] = {
            "status": SwarmStatus.RUNNING,
            "started_at": time.time(),
            "total_tasks": total_tasks,
            "completed_tasks": 0,
            "failed_tasks": 0,
            **(metadata or {}),
        }
        self._r.hset(
            _key_status(swarm_id), mapping={k: str(v) for k, v in status.items()}
        )
        self.publish(
            swarm_id,
            CoordinationEvent(
                event_type="swarm_started",
                swarm_id=swarm_id,
                payload={"total_tasks": total_tasks},
            ),
        )
        logger.info("Swarm %s started (total_tasks=%d)", swarm_id, total_tasks)

    def finish_swarm(
        self, swarm_id: str, *, status: SwarmStatus = SwarmStatus.COMPLETED
    ) -> None:
        """Mark swarm as finished and emit final event."""
        self._r.hset(
            _key_status(swarm_id),
            mapping={
                "status": str(status),
                "finished_at": str(time.time()),
            },
        )
        self.publish(
            swarm_id,
            CoordinationEvent(
                event_type="swarm_finished",
                swarm_id=swarm_id,
                payload={"status": str(status)},
            ),
        )
        logger.info("Swarm %s finished with status=%s", swarm_id, status)

    def swarm_status(self, swarm_id: str) -> Dict[str, Any]:
        """Return the current status hash for the swarm."""
        raw = self._r.hgetall(_key_status(swarm_id))
        agents = self._r.smembers(_key_agents_set(swarm_id)) or set()
        task_depth = self._r.llen(_key_tasks(swarm_id))
        result_depth = self._r.llen(_key_results(swarm_id))
        return {
            **raw,
            "swarm_id": swarm_id,
            "active_agents": len(agents),
            "pending_tasks": task_depth,
            "collected_results": result_depth,
        }

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agent(
        self,
        swarm_id: str,
        agent_id: str,
        *,
        capabilities: List[str] | None = None,
        metadata: Dict[str, Any] | None = None,
        ttl: int = _AGENT_TTL,
    ) -> None:
        """Register an agent with optional capabilities and set a heartbeat TTL."""
        record: Dict[str, Any] = {
            "agent_id": agent_id,
            "swarm_id": swarm_id,
            "capabilities": capabilities or [],
            "registered_at": time.time(),
            "status": "ready",
            **(metadata or {}),
        }
        self._r.hset(_key_agents_hash(swarm_id), agent_id, _dumps(record))
        self._r.sadd(_key_agents_set(swarm_id), agent_id)
        self._heartbeat(swarm_id, agent_id, ttl=ttl)
        self.publish(
            swarm_id,
            CoordinationEvent(
                event_type="agent_registered",
                swarm_id=swarm_id,
                agent_id=agent_id,
                payload={"capabilities": capabilities or []},
            ),
        )
        logger.debug("Agent %s registered in swarm %s", agent_id, swarm_id)

    def deregister_agent(self, swarm_id: str, agent_id: str) -> None:
        """Remove an agent from the swarm registry."""
        self._r.hdel(_key_agents_hash(swarm_id), agent_id)
        self._r.srem(_key_agents_set(swarm_id), agent_id)
        self._r.delete(_key_hb(swarm_id, agent_id))
        self.publish(
            swarm_id,
            CoordinationEvent(
                event_type="agent_deregistered",
                swarm_id=swarm_id,
                agent_id=agent_id,
            ),
        )

    def heartbeat(self, swarm_id: str, agent_id: str, *, ttl: int = _AGENT_TTL) -> None:
        """Renew the agent heartbeat TTL key."""
        self._heartbeat(swarm_id, agent_id, ttl=ttl)

    def _heartbeat(self, swarm_id: str, agent_id: str, *, ttl: int) -> None:
        self._r.setex(_key_hb(swarm_id, agent_id), ttl, str(time.time()))

    def agent_status(self, swarm_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """Return agent metadata if heartbeat is alive, else None."""
        hb = self._r.get(_key_hb(swarm_id, agent_id))
        if hb is None:
            return None
        raw = self._r.hget(_key_agents_hash(swarm_id), agent_id)
        return _loads(raw) if raw else {"agent_id": agent_id}

    def active_agents(self, swarm_id: str) -> Dict[str, Dict[str, Any]]:
        """Return metadata for all agents with a live heartbeat."""
        ids = self._r.smembers(_key_agents_set(swarm_id)) or set()
        out: Dict[str, Dict[str, Any]] = {}
        for aid in ids:
            info = self.agent_status(swarm_id, str(aid))
            if info is not None:
                out[str(aid)] = info
        return out

    # ------------------------------------------------------------------
    # Task distribution
    # ------------------------------------------------------------------

    def push_task(
        self,
        swarm_id: str,
        task: Dict[str, Any],
        *,
        task_id: str | None = None,
        priority: int = 0,
    ) -> str:
        """Push a task onto the swarm's task list.  Returns the task_id."""
        tid = task_id or str(uuid.uuid4())
        task = {
            **task,
            "task_id": tid,
            "priority": priority,
            "enqueued_at": time.time(),
        }
        self._r.lpush(_key_tasks(swarm_id), _dumps(task))
        self.publish(
            swarm_id,
            CoordinationEvent(
                event_type="task_enqueued",
                swarm_id=swarm_id,
                payload={"task_id": tid},
            ),
        )
        return tid

    def pull_task(
        self,
        swarm_id: str,
        *,
        timeout: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Pull the next task from the queue (blocking if timeout > 0)."""
        if timeout > 0:
            item = self._r.brpop(_key_tasks(swarm_id), timeout=timeout)
            if not item:
                return None
            _, raw = item
        else:
            raw = self._r.rpop(_key_tasks(swarm_id))
            if raw is None:
                return None
        return _loads(raw)

    def task_queue_depth(self, swarm_id: str) -> int:
        """Return number of pending tasks."""
        return int(self._r.llen(_key_tasks(swarm_id)))

    # ------------------------------------------------------------------
    # Result collection
    # ------------------------------------------------------------------

    def push_result(self, swarm_id: str, result: Dict[str, Any]) -> None:
        """Store a completed task result."""
        result = {**result, "stored_at": time.time()}
        self._r.lpush(_key_results(swarm_id), _dumps(result))
        self._r.hset(
            _key_status(swarm_id),
            "completed_tasks",
            int(self._r.hget(_key_status(swarm_id), "completed_tasks") or 0) + 1,
        )
        self.publish(
            swarm_id,
            CoordinationEvent(
                event_type="result_stored",
                swarm_id=swarm_id,
                payload={"task_id": result.get("task_id")},
            ),
        )

    def get_results(self, swarm_id: str, *, limit: int = 0) -> List[Dict[str, Any]]:
        """Drain (pop) up to *limit* results (0 = all) from the results list."""
        raw_list = self._r.lrange(_key_results(swarm_id), 0, limit - 1 if limit else -1)
        return [_loads(r) for r in raw_list]

    def results_count(self, swarm_id: str) -> int:
        return int(self._r.llen(_key_results(swarm_id)))

    # ------------------------------------------------------------------
    # Pub/sub
    # ------------------------------------------------------------------

    def publish(self, swarm_id: str, event: CoordinationEvent | Dict[str, Any]) -> int:
        """Publish a coordination event to the swarm channel."""
        payload = event.to_dict() if isinstance(event, CoordinationEvent) else event
        return int(self._r.publish(_key_channel(swarm_id), _dumps(payload)))

    def subscribe(self, swarm_id: str) -> Any:
        """Return a Redis PubSub handle subscribed to the swarm channel."""
        ps = self._r.pubsub(ignore_subscribe_messages=True)
        ps.subscribe(_key_channel(swarm_id))
        return ps

    def listen(
        self,
        swarm_id: str,
        callback: Callable[[CoordinationEvent], None],
        *,
        timeout: float = 0.1,
    ) -> None:
        """
        Block and deliver events from the swarm channel to *callback*.

        Runs until ``shutdown()`` is called.
        """
        ps = self.subscribe(swarm_id)
        try:
            while not self._shutdown.is_set():
                msg = ps.get_message(timeout=timeout)
                if msg and msg.get("type") == "message":
                    try:
                        event = CoordinationEvent.from_dict(_loads(msg["data"]))
                        callback(event)
                    except Exception:
                        logger.exception("Error in swarm event callback")
        finally:
            try:
                ps.unsubscribe()
                ps.close()
            except Exception:
                pass

    def listen_in_thread(
        self,
        swarm_id: str,
        callback: Callable[[CoordinationEvent], None],
    ) -> threading.Thread:
        """Start listening in a daemon thread.  Call ``shutdown()`` to stop."""
        t = threading.Thread(
            target=self.listen,
            args=(swarm_id, callback),
            daemon=True,
            name=f"swarm-listener-{swarm_id}",
        )
        t.start()
        self._subscriber_thread = t
        return t

    # ------------------------------------------------------------------
    # Graceful shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Signal background threads to stop."""
        self._shutdown.set()
        if self._subscriber_thread and self._subscriber_thread.is_alive():
            self._subscriber_thread.join(timeout=3)

    def __enter__(self) -> SwarmCoordinator:
        return self

    def __exit__(self, *_: Any) -> None:
        self.shutdown()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Return True if Redis is reachable."""
        try:
            return bool(self._r.ping())
        except Exception:
            return False
