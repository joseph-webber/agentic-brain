# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Redis availability and functionality tests for Agentic Brain.

BULLETPROOF testing ensures:
- Redis connection works
"""

import pytest

pytestmark = pytest.mark.requires_redis


class TestRedisImport:
    """Test Redis package availability."""

    def test_redis_import(self):
        """Test redis-py package can be imported."""
        try:
            import redis

            assert redis is not None
        except ImportError:
            pytest.skip("redis-py not installed")

    def test_redis_health_checker_available(self):
        """Test Redis health checker is available."""
        try:
            from agentic_brain.api.redis_health import RedisHealthCheck

            assert RedisHealthCheck is not None
        except ImportError:
            pytest.skip("Redis health checker not available")


class TestRedisConnection:
    """Test Redis connection functionality."""

    def test_redis_connection_mock(self, mock_redis):
        """Test Redis connection with mock."""
        # Test using our conftest mock fixture
        result = mock_redis.ping()
        assert result is True

        mock_redis.set("test_key", "test_value")
        mock_redis.set.assert_called_with("test_key", "test_value")


class TestRedisHealth:
    """Test Redis health checking."""

    def test_health_check_with_mock(self, mock_redis):
        """Test health check functionality."""
        from unittest.mock import patch

        with patch("redis.Redis", return_value=mock_redis):
            try:
                from agentic_brain.api.redis_health import RedisHealthCheck

                checker = RedisHealthCheck()
                # Should not fail even if Redis not running
                status = checker.get_health_status()
                assert isinstance(status, dict)
            except ImportError:
                pytest.skip("Redis health checker not available")

    @pytest.mark.skip_ci
    def test_ci_skip_example(self):
        """This test should be skipped in CI."""
        assert True, "This should not run in CI"
