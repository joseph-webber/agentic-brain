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

from __future__ import annotations

"""Redis cache for smart LLM router - enables inter-bot communication."""

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..core.redis_pool import RedisConfig, RedisPoolManager

try:
    import redis
except ImportError:  # pragma: no cover - fallback for environments without redis
    import types

    redis = types.ModuleType("redis")

    class _MissingRedis:
        def __init__(self, *args, **kwargs):
            raise ImportError("redis package is required for RedisRouterCache")

    def _missing_from_url(*args, **kwargs):
        raise ImportError("redis package is required for RedisRouterCache")

    redis.Redis = _MissingRedis
    redis.from_url = _missing_from_url
    sys.modules.setdefault("redis", redis)


@dataclass
class BotMessage:
    """Message between LLM bots."""

    from_bot: str
    to_bot: str
    content: str
    timestamp: float
    msg_type: str = "task"  # task, response, status


class RedisInterBotComm:
    """Redis-based inter-bot communication for LLM coordination.

    Uses lazy pool initialization to avoid establishing network connections until first use.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        password: str | None = None,
        *,
        pool: RedisPoolManager | None = None,
        client: Any | None = None,
    ):
        """Initialize Redis inter-bot communication with password support.
        
        Uses environment variables for configuration in Docker:
        - REDIS_HOST: Redis hostname (default: localhost)
        - REDIS_PORT: Redis port (default: 6379)
        - REDIS_PASSWORD: Redis password (optional)
        """
        # Use environment variables if not explicitly provided
        host = host or os.getenv("REDIS_HOST", "localhost")
        port = port or int(os.getenv("REDIS_PORT", "6379"))
        password = password or os.getenv("REDIS_PASSWORD")
        config = RedisConfig(host=host, port=port, password=password, db=0)
        self._pool = pool or RedisPoolManager(config, client=client)
        self._pubsub = None

    @property
    def client(self):
        return self._pool.client

    @property
    def pubsub(self):
        if self._pubsub is None:
            self._pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        return self._pubsub

    def send_to_bot(
        self, from_bot: str, to_bot: str, message: str, msg_type: str = "task"
    ):
        """Send message to another LLM bot."""
        msg = BotMessage(from_bot, to_bot, message, time.time(), msg_type)
        channel = f"bot:{to_bot}"
        self.client.publish(channel, json.dumps(msg.__dict__))
        # Also store in list for retrieval
        self.client.lpush(f"inbox:{to_bot}", json.dumps(msg.__dict__))
        self.client.ltrim(f"inbox:{to_bot}", 0, 99)  # Keep last 100

    def get_messages(self, bot_id: str, limit: int = 10) -> List[BotMessage]:
        """Get messages for a bot."""
        messages = self.client.lrange(f"inbox:{bot_id}", 0, limit - 1)
        return [BotMessage(**json.loads(m)) for m in messages]

    def broadcast(self, from_bot: str, message: str):
        """Broadcast to all bots."""
        self.client.publish(
            "bot:all",
            json.dumps(
                {"from_bot": from_bot, "content": message, "timestamp": time.time()}
            ),
        )

    def cache_response(self, prompt: str, response: str, model: str, ttl: int = 3600):
        """Cache LLM response for reuse."""
        key = f"llm:cache:{hashlib.sha256(prompt.encode()).hexdigest()[:16]}"
        self.client.setex(
            key,
            ttl,
            json.dumps(
                {"response": response, "model": model, "cached_at": time.time()}
            ),
        )

    def get_cached(self, prompt: str) -> Optional[Dict]:
        """Get cached response."""
        key = f"llm:cache:{hashlib.sha256(prompt.encode()).hexdigest()[:16]}"
        data = self.client.get(key)
        return json.loads(data) if data else None

    def register_bot(self, bot_id: str, capabilities: List[str]):
        """Register a bot with its capabilities."""
        self.client.hset(
            "bots:registry",
            bot_id,
            json.dumps(
                {
                    "capabilities": capabilities,
                    "registered_at": time.time(),
                    "status": "active",
                }
            ),
        )

    def get_bot_for_task(self, task_type: str) -> Optional[str]:
        """Find best bot for a task type."""
        bots = self.client.hgetall("bots:registry")
        for bot_id, info in bots.items():
            data = json.loads(info)
            if task_type in data.get("capabilities", []):
                return bot_id
        return None


class RedisRouterCache:
    """Redis-backed cache for LLM router with inter-bot messaging.

    Also publishes coordination events on brain.llm.* channels so the optional
    Redis→Redpanda bridge can persist critical traffic.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        *,
        pool: RedisPoolManager | None = None,
        client: Any | None = None,
    ):
        host = host or os.getenv("REDIS_HOST", "localhost")
        port = port or int(os.getenv("REDIS_PORT", "6379"))
        password = password or os.getenv("REDIS_PASSWORD")
        config = RedisConfig(host=host, port=port, password=password, db=db)
        self._pool = pool or RedisPoolManager(config, client=client)
        self._pubsub = None

    @property
    def client(self):
        return self._pool.client

    @property
    def pubsub(self):
        if self._pubsub is None:
            self._pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        return self._pubsub

    def cache_response(self, prompt: str, response: str, model: str, ttl: int = 3600):
        """Cache LLM response for reuse."""
        key = f"llm:response:{hashlib.md5(prompt.encode()).hexdigest()}"
        self.client.setex(key, ttl, json.dumps({"response": response, "model": model}))

    def get_cached(self, prompt: str) -> Optional[dict]:
        """Get cached response if exists."""
        key = f"llm:response:{hashlib.md5(prompt.encode()).hexdigest()}"
        data = self.client.get(key)
        return json.loads(data) if data else None

    def publish_task(self, channel: str, task: dict):
        """Publish task to other LLMs.

        Publishes on both the legacy llm:* channel names and the newer brain.llm.*
        naming so the Redis→Redpanda bridge can optionally persist events.
        """
        payload = json.dumps(task)
        self.client.publish(f"llm:{channel}", payload)
        self.client.publish(f"brain.llm.{channel}", payload)

    def subscribe(self, channel: str):
        """Subscribe to LLM channel for tasks."""
        self.pubsub.subscribe(f"llm:{channel}", f"brain.llm.{channel}")

    def get_message(self) -> Optional[dict]:
        """Get next message from subscribed channels."""
        msg = self.pubsub.get_message()
        if not msg or msg.get("type") != "message":
            return None

        data = msg.get("data")
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        return json.loads(data)

    def set_bot_status(self, bot_id: str, status: dict):
        """Set bot status for coordination."""
        encoded = json.dumps(status)
        self.client.hset("llm:bots", bot_id, encoded)
        # Also mirror into the brain.* namespace for event/bridge consumers.
        self.client.hset("brain.agents.state", bot_id, encoded)

    def get_all_bots(self) -> dict:
        """Get all bot statuses."""
        bots = self.client.hgetall("llm:bots")
        if not bots:
            bots = self.client.hgetall("brain.agents.state")
        return {k: json.loads(v) for k, v in bots.items()}
