# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Joseph Webber
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

"""CI tests for swarm coordination."""

from __future__ import annotations

import json
import os
import time

import pytest
import redis

pytestmark = pytest.mark.requires_redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture
def redis_client():
    r = redis.from_url(REDIS_URL)
    yield r
    keys = r.keys("test:*")
    if keys:
        r.delete(*keys)


def test_agent_registration(redis_client):
    """Test agent can register."""
    redis_client.set("test:agent1:ready", "true")
    assert redis_client.get("test:agent1:ready") == b"true"


def test_task_queue(redis_client):
    """Test task distribution."""
    redis_client.lpush("test:tasks", json.dumps({"task": "search"}))
    task = redis_client.rpop("test:tasks")
    assert task is not None
    assert json.loads(task)["task"] == "search"


def test_pubsub(redis_client):
    """Test coordination channel."""
    pubsub = redis_client.pubsub()
    pubsub.subscribe("test:coordination")
    time.sleep(0.05)
    redis_client.publish("test:coordination", "hello")

    received = None
    for _ in range(20):
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if message is not None:
            received = message
            break
        time.sleep(0.05)

    pubsub.close()
    assert received is not None
    assert received["data"] == b"hello"


def test_result_aggregation(redis_client):
    """Test collecting results."""
    for i in range(3):
        redis_client.lpush("test:results", json.dumps({"id": i}))
    assert redis_client.llen("test:results") == 3
