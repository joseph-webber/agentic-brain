"""
🔥 REDIS LLM COORDINATOR 🔥
Enables LUDICROUS SMASH MODE - fire all LLMs, fastest wins!
"""

import asyncio
import json
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from uuid import uuid4

try:
    import redis.asyncio as redis
except ImportError:
    redis = None


@dataclass
class SmashTask:
    """A task to smash across all LLMs"""

    task_id: str
    prompt: str
    mode: str = "ludicrous"
    created_at: float = 0
    timeout: float = 30.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class SmashResult:
    """Result from an LLM smash"""

    task_id: str
    provider: str
    response: str
    elapsed: float
    success: bool
    cost: float = 0.0
    tokens: int = 0


class RedisCoordinator:
    """Redis-based LLM coordination for MAXIMUM SMASH POWER!"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        self.pubsub = None

    async def connect(self):
        if redis is None:
            raise ImportError("pip install redis")
        self.client = redis.from_url(self.redis_url)
        self.pubsub = self.client.pubsub()
        await self.client.ping()
        return True

    async def disconnect(self):
        if self.pubsub:
            await self.pubsub.close()
        if self.client:
            await self.client.close()

    async def publish_result(self, result: SmashResult) -> bool:
        """First response wins!"""
        key = f"llm:response:{result.task_id}"
        won = await self.client.setnx(key, json.dumps(asdict(result)))
        if won:
            await self.client.expire(key, 300)
            await self.client.publish(f"llm:done:{result.task_id}", "done")
        return bool(won)

    async def check_rate_limit(self, provider: str, limit: int) -> bool:
        key = f"llm:rate:{provider}"
        count = await self.client.get(key)
        return int(count or 0) < limit

    async def increment_rate(self, provider: str, window: int = 60):
        key = f"llm:rate:{provider}"
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        await pipe.execute()

    async def add_heat(self, provider: str, amount: float = 1.0):
        await self.client.zincrby("llm:heat", amount, provider)

    async def get_coolest_providers(self, n: int = 3) -> List[str]:
        members = await self.client.zrange("llm:heat", 0, n - 1)
        return [m.decode() for m in members]

    async def get_stats(self) -> Dict[str, Any]:
        keys = await self.client.keys("llm:stats:*")
        stats = {}
        for key in keys:
            provider = key.decode().split(":")[-1]
            data = await self.client.hgetall(key)
            stats[provider] = {k.decode(): int(v) for k, v in data.items()}
        return stats
