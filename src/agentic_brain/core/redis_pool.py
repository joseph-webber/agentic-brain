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
    """Configuration for Redis connection pool.

    Attributes:
        host: Redis server hostname (default: localhost).
        port: Redis server port (default: 6379).
        password: Optional authentication password.
        db: Database number to select (default: 0).
        url: Alternative connection string (overrides host/port/password).
        decode_responses: Auto-decode responses to strings (default: True).
    """

    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    url: Optional[str] = None
    decode_responses: bool = True

    @staticmethod
    def from_env() -> RedisConfig:
        """Create config from environment variables.

        Reads from:
            REDIS_URL: Optional connection string (overrides other vars)
            REDIS_HOST: Server hostname (default: localhost)
            REDIS_PORT: Server port (default: 6379)
            REDIS_PASSWORD: Optional password
            REDIS_DB: Database number (default: 0)

        Returns:
            RedisConfig instance with values from environment or defaults.
        """
        url = os.getenv("REDIS_URL")
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD")
        db = int(os.getenv("REDIS_DB", "0"))
        return RedisConfig(host=host, port=port, password=password, db=db, url=url)


class RedisPoolManager:
    """Lazy Redis client and connection pool wrapper.

    Defers importing redis and creating connections until first use.
    Thread-safe and compatible with both redis.Redis and pool patterns.

    Attributes:
        _config: RedisConfig with connection parameters.
        _pool: Optional ConnectionPool instance.
        _client: Optional Redis client instance.
    """

    def __init__(
        self,
        config: Optional[RedisConfig] = None,
        *,
        client: Any | None = None,
    ):
        """Initialize the Redis pool manager.

        Args:
            config: Optional RedisConfig. If None, creates from environment.
            client: Optional pre-created redis.Redis client (for testing).
        """
        self._config = config or RedisConfig.from_env()
        self._pool = None
        self._client = client

    def _import_redis(self):
        """Import redis module, raising helpful error if unavailable.

        Returns:
            redis module object.

        Raises:
            ImportError: If redis package is not installed.
        """
        try:
            import redis  # type: ignore

            return redis
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "redis package is required for Redis coordination (pip install redis)"
            ) from exc

    def _ensure_client(self) -> None:
        """Lazy-initialize Redis client and connection pool on first access."""
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
            if hasattr(redis, "ConnectionPool"):
                self._pool = redis.ConnectionPool(
                    host=self._config.host,
                    port=self._config.port,
                    password=self._config.password,
                    db=self._config.db,
                    decode_responses=self._config.decode_responses,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                )
            else:
                self._client = redis.Redis(
                    host=self._config.host,
                    port=self._config.port,
                    password=self._config.password,
                    db=self._config.db,
                    decode_responses=self._config.decode_responses,
                )
                self._pool = getattr(self._client, "connection_pool", None)
                return

        self._client = redis.Redis(connection_pool=self._pool)

    @property
    def client(self):
        """Get the underlying Redis client, creating it if needed.

        Returns:
            redis.Redis client instance.
        """
        self._ensure_client()
        return self._client

    def health_check(self) -> Dict[str, Any]:
        """Check Redis connectivity without raising exceptions.

        Returns:
            Dictionary with keys:
                ok (bool): True if Redis is reachable
                host, port, db (str): Connection parameters
                error (str): Error message if ok=False
        """
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
        """Publish a message to a Redis channel.

        Args:
            channel: Channel name or pattern.
            payload: Message data (dict or string).

        Returns:
            Number of subscribers that received the message.
        """
        msg = payload if isinstance(payload, str) else _json_dumps(payload)
        return int(self.client.publish(channel, msg))

    def pubsub(self, *, ignore_subscribe_messages: bool = True):
        """Create a pub/sub subscription handler.

        Args:
            ignore_subscribe_messages: If True, filter subscribe/unsubscribe confirmations.

        Returns:
            PubSub object with subscribe() and listen() methods.
        """
        return self.client.pubsub(ignore_subscribe_messages=ignore_subscribe_messages)


_default_pool: RedisPoolManager | None = None


def get_redis_pool() -> RedisPoolManager:
    """Get the default global Redis pool (lazy-initialized).

    Returns:
        RedisPoolManager configured from environment.
    """


class RedisCoordination:
    """High-level Redis primitives for agent coordination.

    Provides agent registry, task queues, result caching, and pub/sub
    for distributed agent systems.
    """

    def __init__(
        self,
        pool: Optional[RedisPoolManager] = None,
        *,
        client: Any | None = None,
    ):
        """Initialize coordination using a Redis pool.

        Args:
            pool: Optional RedisPoolManager. If None, uses default global pool.
            client: Optional pre-created redis client (for dependency injection).
        """
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
        """Register an agent with the system.

        Adds the agent to the registry and sets up a heartbeat key with TTL.

        Args:
            agent_id: Unique agent identifier.
            metadata: Optional metadata (role, capacity, status, etc).
            ttl_seconds: Heartbeat expiration time (default: 60).
        """
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
        """Refresh an agent's heartbeat to keep it active.

        Args:
            agent_id: Agent to heartbeat.
            ttl_seconds: Heartbeat expiration time (default: 60).
        """
        self.pool.client.setex(
            f"brain.agents.heartbeat:{agent_id}", ttl_seconds, str(time.time())
        )

    def list_active_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get all agents with active heartbeats.

        Returns:
            Dictionary mapping agent_id to agent metadata.
        """
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
        """Add a task to the queue.

        Also publishes a task_enqueued event to brain.events.task_enqueued.

        Args:
            task: Task dictionary (should include task_id).
            queue: Queue name (default: brain.tasks.queue).
        """
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
        """Retrieve and remove a task from the queue.

        Args:
            queue: Queue name (default: brain.tasks.queue).
            block_seconds: Blocking timeout (0 = non-blocking, >0 = wait max N seconds).

        Returns:
            Task dictionary or None if queue is empty.
        """
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
        """Store a result in the cache.

        Args:
            cache_key: Unique cache key.
            result: Result data to cache.
            ttl_seconds: Cache expiration time (default: 3600 = 1 hour).
        """
        self.pool.client.setex(
            f"brain.results.cache:{cache_key}", ttl_seconds, _json_dumps(result)
        )

    def get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached result.

        Args:
            cache_key: Cache key to look up.

        Returns:
            Cached result dictionary or None if key doesn't exist or expired.
        """
        data = self.pool.client.get(f"brain.results.cache:{cache_key}")
        return _json_loads(data) if data else None

    # ------------------------------------------------------------------
    # Event pub/sub
    # ------------------------------------------------------------------

    def publish_event(
        self, topic: str, payload: Dict[str, Any], *, persistent: bool = False
    ) -> None:
        """Publish an event to a topic (brain.* channels).

        Integrates with RedisRedpandaBridge for Redpanda event streaming.

        Args:
            topic: Event topic (brain.* prefix recommended).
            payload: Event data.
            persistent: If True, event intended for long-term storage.
        """
        event = {
            "topic": topic,
            "payload": payload,
            "timestamp": time.time(),
            "persistent": persistent,
        }
        # Publish on brain.* directly so RedisRedpandaBridge can bridge patterns.
        self.pool.publish(topic, event)

    def subscribe(self, topics: Iterable[str]):
        """Subscribe to one or more topics.

        Args:
            topics: Iterable of topic names or patterns.

        Returns:
            PubSub object. Call listen() to receive messages.
        """
        ps = self.pool.pubsub()
        ps.subscribe(*list(topics))
        return ps
