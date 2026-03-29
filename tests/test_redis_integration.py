# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Redis-backed coordination tests.

These tests use fakeredis so they run without a real Redis server.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import pytest

fakeredis = pytest.importorskip("fakeredis")

from agentic_brain.core.redis_pool import (
    RedisConfig,
    RedisCoordination,
    RedisPoolManager,
)
from agentic_brain.router.redis_cache import RedisRouterCache
from agentic_brain.unified_brain import UnifiedBrain


def _wait_for_pubsub_message(pubsub, *, attempts: int = 50, sleep_s: float = 0.001):
    for _ in range(attempts):
        msg = pubsub.get_message()
        if msg and msg.get("type") == "message":
            return msg
        time.sleep(sleep_s)
    return None


def test_redis_pool_lazy_initialization():
    mgr = RedisPoolManager(RedisConfig(host="localhost", port=6379))
    assert mgr._client is None
    assert mgr._pool is None

    _ = mgr.client
    assert mgr._client is not None


def test_coordination_registry_queue_cache_and_events():
    client = fakeredis.FakeRedis(decode_responses=True)
    coord = RedisCoordination(client=client)

    coord.register_agent("agent-1", {"role": "worker"}, ttl_seconds=60)
    agents = coord.list_active_agents()
    assert "agent-1" in agents
    assert agents["agent-1"]["role"] == "worker"

    task = {"task_id": "t-1", "content": "do work"}
    coord.enqueue_task(task)
    got = coord.dequeue_task()
    assert got is not None
    assert got["task_id"] == "t-1"

    coord.cache_result("k1", {"ok": True}, ttl_seconds=60)
    assert coord.get_cached_result("k1") == {"ok": True}

    ps = coord.subscribe(["brain.events.test"])
    coord.publish_event("brain.events.test", {"hello": "world"})
    msg = _wait_for_pubsub_message(ps)
    assert msg is not None
    payload = json.loads(msg["data"])
    assert payload["topic"] == "brain.events.test"
    assert payload["payload"]["hello"] == "world"


def test_unified_brain_uses_redis_for_registry_queue_and_events():
    client = fakeredis.FakeRedis(decode_responses=True)

    redis_cache = RedisRouterCache(client=client)
    coord = RedisCoordination(client=client)

    brain = UnifiedBrain(
        router=MagicMock(),
        redis_cache=redis_cache,
        coordination=coord,
        enable_redis_coordination=True,
        enable_inter_bot_comms=False,
    )

    bots = client.hgetall("llm:bots")
    assert bots, "UnifiedBrain should register bots into Redis"

    agents = coord.list_active_agents()
    assert agents, "UnifiedBrain should register agents into RedisCoordination"

    ps = client.pubsub(ignore_subscribe_messages=True)
    ps.subscribe("brain.llm.all")

    res = brain.broadcast_task("test broadcast", wait_for_consensus=True)
    assert res["status"] == "broadcast"

    # Task should be enqueued for workers.
    queued = coord.dequeue_task(queue="brain.tasks.queue")
    assert queued is not None
    assert queued["task_id"] == res["task_id"]

    # Event should be published onto brain.llm.* namespace.
    msg = _wait_for_pubsub_message(ps)
    assert msg is not None
    task_payload = json.loads(msg["data"])
    assert task_payload["task_id"] == res["task_id"]
