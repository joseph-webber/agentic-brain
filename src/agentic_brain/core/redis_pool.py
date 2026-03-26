# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Redis connection pooling + coordination helpers.

This module is intentionally *lazy*:
- Redis is imported only when needed.
- Connections/pools are created on first use.

UnifiedBrain uses this for cross-agent coordination:
- Agent registry + heartbeats
- Task queue
- Result cache
- Event pub/sub on brain.* channels (bridgeable to Redpanda)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _json_loads(data: str) -> Any:
    return json.loads(data)


@dataclass(frozen=True)
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    url: Optional[str] = None
    decode_responses: bool = True

    @staticmethod
    def from_env() -> RedisConfig:
        url = os.getenv("REDIS_URL")
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD")
        db = int(os.getenv("REDIS_DB", "0"))
        return RedisConfig(host=host, port=port, password=password, db=db, url=url)


class RedisPoolManager:
    """Lazy Redis client + ConnectionPool wrapper."""

    def __init__(
        self,
        config: Optional[RedisConfig] = None,
        *,
        client: Any | None = None,
    ):
        self._config = config or RedisConfig.from_env()
        self._pool = None
        self._client = client

    def _import_redis(self):
        try:
            import redis  # type: ignore

            return redis
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "redis package is required for Redis coordination (pip install redis)"
            ) from exc

    def _ensure_client(self) -> None:
        if self._client is not None:
            return

        redis = self._import_redis()

        if self._config.url:
            # from_url internally creates a pool; keep a reference for health.
            self._client = redis.from_url(
                self._config.url, decode_responses=self._config.decode_responses
            )
            self._pool = getattr(self._client, "connection_pool", None)
            return

        if self._pool is None:
            self._pool = redis.ConnectionPool(
                host=self._config.host,
                port=self._config.port,
                password=self._config.password,
                db=self._config.db,
                decode_responses=self._config.decode_responses,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )

        self._client = redis.Redis(connection_pool=self._pool)

    @property
    def client(self):
        self._ensure_client()
        return self._client

    def health_check(self) -> Dict[str, Any]:
        """Return a small health payload; never raises."""
        try:
            ok = bool(self.client.ping())
            conn_kwargs = getattr(self._pool, "connection_kwargs", {}) or {}
            host = conn_kwargs.get("host", self._config.host)
            port = conn_kwargs.get("port", self._config.port)
            return {"ok": ok, "host": host, "port": port, "db": self._config.db}
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "host": self._config.host,
                "port": self._config.port,
                "db": self._config.db,
            }

    def publish(self, channel: str, payload: Any) -> int:
        msg = payload if isinstance(payload, str) else _json_dumps(payload)
        return int(self.client.publish(channel, msg))

    def pubsub(self, *, ignore_subscribe_messages: bool = True):
        return self.client.pubsub(ignore_subscribe_messages=ignore_subscribe_messages)


_default_pool: RedisPoolManager | None = None


def get_redis_pool() -> RedisPoolManager:
    global _default_pool
    if _default_pool is None:
        _default_pool = RedisPoolManager()
    return _default_pool


class RedisCoordination:
    """High-level Redis primitives for agent coordination."""

    def __init__(
        self,
        pool: Optional[RedisPoolManager] = None,
        *,
        client: Any | None = None,
    ):
        base_pool = pool or get_redis_pool()
        self.pool = (
            RedisPoolManager(base_pool._config, client=client)
            if client is not None
            else base_pool
        )

    # ------------------------------------------------------------------
    # Agent registry + heartbeats
    # ------------------------------------------------------------------

    def register_agent(
        self,
        agent_id: str,
        metadata: Dict[str, Any] | None = None,
        *,
        ttl_seconds: int = 60,
    ) -> None:
        metadata = metadata or {}
        record = {
            **metadata,
            "agent_id": agent_id,
            "registered_at": time.time(),
        }
        self.pool.client.hset("brain.agents.registry", agent_id, _json_dumps(record))
        self.pool.client.sadd("brain.agents.active", agent_id)
        self.heartbeat_agent(agent_id, ttl_seconds=ttl_seconds)

    def heartbeat_agent(self, agent_id: str, *, ttl_seconds: int = 60) -> None:
        self.pool.client.setex(
            f"brain.agents.heartbeat:{agent_id}", ttl_seconds, str(time.time())
        )

    def list_active_agents(self) -> Dict[str, Dict[str, Any]]:
        agents = self.pool.client.smembers("brain.agents.active")
        out: Dict[str, Dict[str, Any]] = {}
        for agent_id in agents:
            hb = self.pool.client.get(f"brain.agents.heartbeat:{agent_id}")
            if hb is None:
                continue
            raw = self.pool.client.hget("brain.agents.registry", agent_id)
            if raw:
                try:
                    out[str(agent_id)] = _json_loads(raw)
                except Exception:
                    out[str(agent_id)] = {"agent_id": str(agent_id)}
            else:
                out[str(agent_id)] = {"agent_id": str(agent_id)}
        return out

    # ------------------------------------------------------------------
    # Task queue
    # ------------------------------------------------------------------

    def enqueue_task(
        self, task: Dict[str, Any], *, queue: str = "brain.tasks.queue"
    ) -> None:
        self.pool.client.lpush(queue, _json_dumps(task))
        self.publish_event(
            "brain.events.task_enqueued",
            {"queue": queue, "task_id": task.get("task_id"), "task": task},
        )

    def dequeue_task(
        self,
        *,
        queue: str = "brain.tasks.queue",
        block_seconds: int = 0,
    ) -> Optional[Dict[str, Any]]:
        if block_seconds:
            item = self.pool.client.brpop(queue, timeout=block_seconds)
            if not item:
                return None
            _q, data = item
        else:
            data = self.pool.client.rpop(queue)
            if data is None:
                return None
        return _json_loads(data)

    # ------------------------------------------------------------------
    # Result cache
    # ------------------------------------------------------------------

    def cache_result(
        self, cache_key: str, result: Dict[str, Any], *, ttl_seconds: int = 3600
    ) -> None:
        self.pool.client.setex(
            f"brain.results.cache:{cache_key}", ttl_seconds, _json_dumps(result)
        )

    def get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        data = self.pool.client.get(f"brain.results.cache:{cache_key}")
        return _json_loads(data) if data else None

    # ------------------------------------------------------------------
    # Event pub/sub
    # ------------------------------------------------------------------

    def publish_event(
        self, topic: str, payload: Dict[str, Any], *, persistent: bool = False
    ) -> None:
        event = {
            "topic": topic,
            "payload": payload,
            "timestamp": time.time(),
            "persistent": persistent,
        }
        # Publish on brain.* directly so RedisRedpandaBridge can bridge patterns.
        self.pool.publish(topic, event)

    def subscribe(self, topics: Iterable[str]):
        ps = self.pool.pubsub()
        ps.subscribe(*list(topics))
        return ps
