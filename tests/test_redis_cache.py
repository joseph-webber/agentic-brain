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

"""Tests for Redis LLM cache - inter-bot communication."""

import os
import sys
import types
from unittest.mock import MagicMock

import pytest

# Skip all if Redis not available
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") and not os.environ.get("REDIS_URL"),
    reason="Redis not available in CI",
)


class TestRedisRouterCache:
    """Test Redis cache for LLM router."""

    @pytest.fixture
    def mock_redis(self, monkeypatch):
        """Mock Redis client for testing without real Redis."""
        fake_redis = types.ModuleType("redis")
        client = MagicMock()
        fake_redis.Redis = MagicMock(return_value=client)
        fake_redis.from_url = MagicMock(return_value=client)
        monkeypatch.setitem(sys.modules, "redis", fake_redis)
        import agentic_brain.router.redis_cache as redis_cache

        monkeypatch.setattr(redis_cache, "redis", fake_redis, raising=False)
        yield fake_redis, client

    def test_cache_response(self, mock_redis):
        """Test caching LLM response."""
        from agentic_brain.router.redis_cache import RedisRouterCache

        fake_redis, client = mock_redis
        cache = RedisRouterCache()
        cache.cache_response("Hello", "Hi there!", "gpt-4", ttl=60)
        client.setex.assert_called_once()

    def test_get_cached_hit(self, mock_redis):
        """Test cache hit."""
        from agentic_brain.router.redis_cache import RedisRouterCache

        _fake_redis, client = mock_redis
        client.get.return_value = '{"response": "cached", "model": "gpt-4"}'
        cache = RedisRouterCache()
        result = cache.get_cached("Hello")
        assert result is not None
        assert result["response"] == "cached"

    def test_get_cached_miss(self, mock_redis):
        """Test cache miss."""
        from agentic_brain.router.redis_cache import RedisRouterCache

        _fake_redis, client = mock_redis
        client.get.return_value = None
        cache = RedisRouterCache()
        result = cache.get_cached("Unknown")
        assert result is None


class TestInterBotCommunication:
    """Test inter-bot messaging."""

    @pytest.fixture
    def mock_redis(self, monkeypatch):
        fake_redis = types.ModuleType("redis")
        client = MagicMock()
        client.pubsub.return_value = MagicMock()
        fake_redis.Redis = MagicMock(return_value=client)
        fake_redis.from_url = MagicMock(return_value=client)
        monkeypatch.setitem(sys.modules, "redis", fake_redis)
        import agentic_brain.router.redis_cache as redis_cache

        monkeypatch.setattr(redis_cache, "redis", fake_redis, raising=False)
        yield fake_redis, client

    def test_publish_task(self, mock_redis):
        """Test publishing task to other bots."""
        from agentic_brain.router.redis_cache import RedisRouterCache

        _fake_redis, client = mock_redis
        cache = RedisRouterCache()
        cache.publish_task("code-review", {"task": "review PR"})
        client.publish.assert_called()

    def test_bot_status(self, mock_redis):
        """Test bot status management."""
        from agentic_brain.router.redis_cache import RedisRouterCache

        _fake_redis, client = mock_redis
        cache = RedisRouterCache()
        cache.set_bot_status("bot-1", {"status": "active"})
        client.hset.assert_called()
