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

"""
Tests for RAG Smart Rate Limiter

Tests cover:
- Per-loader rate limits (GitHub, Confluence, Slack, etc.)
- Concurrent request limiting
- Exponential backoff with jitter
- IP-based rate limiting
- Document size and batch limits
- Redis-backed distributed rate limiting
- @rate_limited decorator
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.rate_limiter import (
    IPRateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    SmartRateLimiter,
    get_rate_limiter,
    rate_limited,
)


@pytest.fixture
def limiter():
    """Create a fresh rate limiter for each test"""
    return SmartRateLimiter()


@pytest.fixture
def ip_limiter():
    """Create a fresh IP rate limiter"""
    return IPRateLimiter(requests_per_minute=10)


class TestSmartRateLimiter:
    """Test SmartRateLimiter functionality"""

    @pytest.mark.asyncio
    async def test_basic_rate_limit(self, limiter):
        """Test basic rate limiting works"""
        # GitHub has 30 req/min limit
        assert await limiter.acquire("github")
        limiter.release("github")

    @pytest.mark.asyncio
    async def test_concurrent_limit(self, limiter):
        """Test concurrent request limiting"""
        # GitHub has max 5 concurrent
        slots = []
        for i in range(5):
            acquired = await limiter.acquire("github")
            assert acquired, f"Should acquire slot {i}"
            slots.append(i)

        # 6th should fail
        assert not await limiter.acquire("github")

        # Release one and try again
        limiter.release("github")
        assert await limiter.acquire("github")

    @pytest.mark.asyncio
    async def test_per_minute_limit(self, limiter):
        """Test per-minute rate limit enforcement"""
        # Notion has VERY strict 3 req/min
        for i in range(3):
            assert await limiter.acquire("notion"), f"Request {i+1} should succeed"
            limiter.release("notion")

        # 4th should fail
        assert not await limiter.acquire("notion")

    @pytest.mark.asyncio
    async def test_backoff_trigger(self, limiter):
        """Test exponential backoff gets triggered"""
        limiter.record_failure("github", trigger_backoff=True)

        # Should be in backoff
        assert not await limiter.acquire("github")

        # Record success should clear failures count
        limiter.record_success("github")
        state = limiter._get_state("github")
        assert state.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, limiter):
        """Test exponential backoff increases with failures"""
        limiter._get_config("github")

        # Multiple failures
        for _i in range(3):
            limiter.record_failure("github", trigger_backoff=True)
            # Clear backoff for next iteration
            state = limiter._get_state("github")
            state.backoff_until = None

        state = limiter._get_state("github")
        # Should have 3 failures recorded
        assert state.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_wait_for_slot_success(self, limiter):
        """Test wait_for_slot successfully waits"""
        # Acquire one slot
        await limiter.acquire("notion")

        # Try to wait for another (should work after release)
        async def release_after_delay():
            await asyncio.sleep(0.5)
            limiter.release("notion")

        asyncio.create_task(release_after_delay())

        # Should succeed after waiting
        result = await limiter.wait_for_slot("notion", timeout=2)
        assert result

    @pytest.mark.asyncio
    async def test_wait_for_slot_timeout(self, limiter):
        """Test wait_for_slot times out properly"""
        # Fill all notion slots (max 1 concurrent)
        await limiter.acquire("notion")

        # Should timeout
        result = await limiter.wait_for_slot("notion", timeout=0.5)
        assert not result

    @pytest.mark.asyncio
    async def test_document_size_limit(self, limiter):
        """Test document size limiting"""
        # Within limit
        assert await limiter.check_document_limits("github", 50, 1)

        # Exceeds limit
        assert not await limiter.check_document_limits("github", 200, 1)

    @pytest.mark.asyncio
    async def test_batch_size_limit(self, limiter):
        """Test batch size limiting"""
        # Within limit
        assert await limiter.check_document_limits("github", 10, 30)

        # Exceeds limit
        assert not await limiter.check_document_limits("github", 10, 100)

    @pytest.mark.asyncio
    async def test_ip_based_limiting(self, limiter):
        """Test IP-based rate limiting"""
        ip = "192.168.1.1"

        # Different IPs should have separate limits
        assert await limiter.acquire("github", ip_address=ip)
        assert await limiter.acquire("github", ip_address="192.168.1.2")

        limiter.release("github", ip_address=ip)
        limiter.release("github", ip_address="192.168.1.2")

    def test_get_stats(self, limiter):
        """Test rate limit stats"""
        stats = limiter.get_stats("github")

        assert "loader" in stats
        assert stats["loader"] == "github"
        assert "requests_last_minute" in stats
        assert "limit_per_minute" in stats
        assert stats["limit_per_minute"] == 30  # GitHub limit

    @pytest.mark.asyncio
    async def test_different_loaders(self, limiter):
        """Test different loaders have different limits"""
        github_config = limiter._get_config("github")
        notion_config = limiter._get_config("notion")

        assert github_config.requests_per_minute == 30
        assert notion_config.requests_per_minute == 3

        # GitHub should allow more requests
        for _i in range(5):
            assert await limiter.acquire("github")
            limiter.release("github")


class TestRateLimitedDecorator:
    """Test the @rate_limited decorator"""

    @pytest.mark.asyncio
    async def test_decorator_on_async_function(self):
        """Test decorator works on async functions"""
        call_count = 0

        @rate_limited("notion", timeout=1)
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

        # First 3 calls should work (Notion limit)
        for _i in range(3):
            result = await test_func()
            assert result == "success"

        assert call_count == 3

        # 4th should raise RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            await test_func()

    @pytest.mark.asyncio
    async def test_decorator_records_success(self):
        """Test decorator records successful calls"""

        @rate_limited("github", timeout=1)
        async def test_func():
            return "success"

        await test_func()

        limiter = get_rate_limiter()
        state = limiter._get_state("github")
        assert state.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_decorator_records_failure(self):
        """Test decorator records failures"""

        @rate_limited("github", timeout=1)
        async def test_func():
            raise Exception("Rate limit exceeded")

        limiter = get_rate_limiter()

        with pytest.raises(Exception):
            await test_func()

        state = limiter._get_state("github")
        assert state.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_decorator_triggers_backoff_on_rate_limit_error(self):
        """Test decorator triggers backoff on rate limit errors"""

        @rate_limited("github", timeout=1)
        async def test_func():
            raise Exception("429 Too Many Requests")

        limiter = get_rate_limiter()

        with pytest.raises(Exception):
            await test_func()

        state = limiter._get_state("github")
        # Should have triggered backoff
        assert state.backoff_until is not None


class TestIPRateLimiter:
    """Test IP-based rate limiting"""

    def test_allows_requests_within_limit(self, ip_limiter):
        """Test IP is allowed up to limit"""
        ip = "192.168.1.1"

        for i in range(10):
            assert ip_limiter.is_allowed(ip), f"Request {i+1} should be allowed"

        # 11th should be blocked
        assert not ip_limiter.is_allowed(ip)

    def test_different_ips_separate_limits(self, ip_limiter):
        """Test different IPs have separate limits"""
        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"

        # Fill limit for IP1
        for _i in range(10):
            ip_limiter.is_allowed(ip1)

        # IP1 should be blocked
        assert not ip_limiter.is_allowed(ip1)

        # IP2 should still work
        assert ip_limiter.is_allowed(ip2)

    def test_get_remaining(self, ip_limiter):
        """Test getting remaining requests"""
        ip = "192.168.1.1"

        # Initially all available
        assert ip_limiter.get_remaining(ip) == 10

        # Use 5
        for _i in range(5):
            ip_limiter.is_allowed(ip)

        # Should have 5 remaining
        assert ip_limiter.get_remaining(ip) == 5

    def test_requests_expire(self, ip_limiter):
        """Test old requests are cleaned up"""
        ip = "192.168.1.1"

        # Make requests
        for _i in range(5):
            ip_limiter.is_allowed(ip)

        # Manually expire timestamps
        state = ip_limiter._ip_states[ip]
        expired_time = time.time() - 120  # 2 minutes ago
        state.request_timestamps = [expired_time] * 5

        # Should allow new requests
        assert ip_limiter.is_allowed(ip)


class TestRedisRateLimiting:
    """Test Redis-backed rate limiting"""

    @pytest.mark.asyncio
    async def test_redis_fallback_on_import_error(self):
        """Test falls back to memory if Redis not installed"""
        # Patch at import time would require reloading the module
        # Instead, just verify fallback works when Redis unavailable
        limiter = SmartRateLimiter(use_redis=False)
        assert not limiter._use_redis
        # Should still work
        assert await limiter.acquire("github")


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_unknown_loader_uses_default(self, limiter):
        """Test unknown loaders use default config"""
        assert await limiter.acquire("unknown_service")

        config = limiter._get_config("unknown_service")
        default = limiter._get_config("default")

        assert config.requests_per_minute == default.requests_per_minute

    @pytest.mark.asyncio
    async def test_negative_concurrent_count_protected(self, limiter):
        """Test concurrent count can't go negative"""
        # Try to release without acquiring
        limiter.release("github")

        state = limiter._get_state("github")
        assert state.concurrent_count == 0  # Should be max(0, -1)

    @pytest.mark.asyncio
    async def test_multiple_failures_cap_backoff(self, limiter):
        """Test backoff caps at max_backoff_seconds"""
        config = limiter._get_config("github")

        # Trigger many failures
        for _i in range(20):
            limiter.record_failure("github", trigger_backoff=True)

        state = limiter._get_state("github")
        backoff_duration = state.backoff_until - time.time()

        # Should not exceed max
        assert backoff_duration <= config.max_backoff_seconds * 1.5  # Allow for jitter

    @pytest.mark.asyncio
    async def test_concurrent_access_thread_safe(self, limiter):
        """Test concurrent access is thread-safe"""
        results = []

        async def try_acquire():
            result = await limiter.acquire("github")
            results.append(result)
            if result:
                limiter.release("github")

        # Run 20 concurrent acquisitions
        await asyncio.gather(*[try_acquire() for _ in range(20)])

        # All should have gotten a result (True or False)
        assert len(results) == 20


class TestLoaderSpecificLimits:
    """Test specific loader configurations"""

    @pytest.mark.asyncio
    async def test_notion_strict_limits(self, limiter):
        """Test Notion's very strict 3 req/min limit"""
        config = limiter._get_config("notion")

        assert config.requests_per_minute == 3
        assert config.max_concurrent == 1
        assert config.cooldown_seconds == 120

    @pytest.mark.asyncio
    async def test_github_moderate_limits(self, limiter):
        """Test GitHub's 30 req/min limit"""
        config = limiter._get_config("github")

        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 5000
        assert config.max_concurrent == 5

    @pytest.mark.asyncio
    async def test_confluence_permissive_limits(self, limiter):
        """Test Confluence's higher limits"""
        config = limiter._get_config("confluence")

        assert config.requests_per_minute == 100
        assert config.burst_limit == 20


class TestIntegration:
    """Integration tests combining multiple features"""

    @pytest.mark.asyncio
    async def test_realistic_usage_pattern(self):
        """Test realistic usage pattern with mixed success/failure"""
        # Use a fresh global limiter
        import agentic_brain.rag.rate_limiter as rl

        old_limiter = rl._rate_limiter
        rl._rate_limiter = SmartRateLimiter()

        try:

            @rate_limited("github", timeout=1, limiter=rl._rate_limiter)
            async def fetch_repo():
                # Simulate API call
                await asyncio.sleep(0.01)
                return {"data": "repo_info"}

            # Make several successful requests
            for _i in range(5):
                result = await fetch_repo()
                assert result["data"] == "repo_info"

            # Check stats
            stats = rl._rate_limiter.get_stats("github")
            assert stats["requests_last_minute"] >= 5
        finally:
            # Restore original limiter
            rl._rate_limiter = old_limiter

    @pytest.mark.asyncio
    async def test_multiple_loaders_independently(self):
        """Test multiple loaders work independently"""
        # Reset the global limiter
        import agentic_brain.rag.rate_limiter as rl

        rl._rate_limiter = SmartRateLimiter()
        limiter = rl._rate_limiter

        # Fill Notion limit (3 req/min) and release to free up concurrent slots
        for _i in range(3):
            assert await limiter.acquire("notion")
            limiter.release("notion")  # Release immediately to free concurrent slot

        # 4th acquisition should be blocked (rate limit reached)
        assert not await limiter.acquire("notion")

        # But GitHub should still work (different loader, different limit)
        assert await limiter.acquire("github")
        limiter.release("github")

    @pytest.mark.asyncio
    async def test_recovery_from_backoff(self, limiter):
        """Test system recovers from backoff"""
        # Trigger backoff
        limiter.record_failure("github", trigger_backoff=True)

        # Should be blocked
        assert not await limiter.acquire("github")

        # Manually clear backoff (simulating time passing)
        state = limiter._get_state("github")
        state.backoff_until = None
        state.consecutive_failures = 0

        # Should work again
        assert await limiter.acquire("github")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
