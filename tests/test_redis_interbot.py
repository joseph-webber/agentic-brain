# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Test Redis inter-bot communication."""

import json
import time

import pytest
import redis

from agentic_brain.router.redis_cache import BotMessage, RedisInterBotComm


# Check if Redis is available
def is_redis_available():
    try:
        r = redis.Redis(host="localhost", port=6379)
        return r.ping()
    except redis.ConnectionError:
        return False


@pytest.mark.skipif(not is_redis_available(), reason="Redis not available")
class TestRedisInterBot:

    @pytest.fixture
    def comm(self):
        """Setup Redis comms."""
        c = RedisInterBotComm()
        # Clean up test keys
        c.client.delete("inbox:test_bot_2")
        c.client.delete("bots:registry")
        # Clean up cache keys
        keys = c.client.keys("llm:cache:*")
        if keys:
            c.client.delete(*keys)
        return c

    def test_send_receive(self, comm):
        """Test sending and receiving messages."""
        comm.send_to_bot("test_bot_1", "test_bot_2", "Hello there")

        # Verify message in inbox
        messages = comm.get_messages("test_bot_2")
        assert len(messages) == 1
        assert messages[0].from_bot == "test_bot_1"
        assert messages[0].content == "Hello there"
        assert messages[0].msg_type == "task"

    def test_broadcast(self, comm):
        """Test broadcasting messages."""
        # Subscribe to verify broadcast
        pubsub = comm.client.pubsub()
        pubsub.subscribe("bot:all")

        # Wait for subscription
        time.sleep(0.1)

        comm.broadcast("test_bot_1", "Announcement")

        # Check message
        time.sleep(0.1)
        msg = pubsub.get_message()
        # First message is subscription confirmation
        if msg and msg["type"] == "subscribe":
            msg = pubsub.get_message()

        assert msg is not None
        assert msg["type"] == "message"
        data = json.loads(msg["data"])
        assert data["from_bot"] == "test_bot_1"
        assert data["content"] == "Announcement"

    def test_caching(self, comm):
        """Test LLM response caching."""
        prompt = "What is the capital of France?"
        response = "Paris"
        model = "gpt-4"

        # Cache it
        comm.cache_response(prompt, response, model)

        # Retrieve it
        cached = comm.get_cached(prompt)
        assert cached is not None
        assert cached["response"] == response
        assert cached["model"] == model

        # Verify miss
        assert comm.get_cached("Unknown prompt") is None

    def test_bot_registry(self, comm):
        """Test bot registration and lookup."""
        comm.register_bot("coder_bot", ["python", "coding", "debugging"])
        comm.register_bot("writer_bot", ["writing", "editing"])

        # Find bot for task
        bot = comm.get_bot_for_task("python")
        assert bot == "coder_bot"

        bot = comm.get_bot_for_task("writing")
        assert bot == "writer_bot"

        bot = comm.get_bot_for_task("cooking")
        assert bot is None
