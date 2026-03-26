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
Tests for the Brick Wall Rate Limiter.

Tests cover:
- Rate limit detection and status
- Exponential backoff on consecutive 429s
- Local LLM fallback activation
- Pattern learning (peak hours)
- Auto-save on rate limit
- Cooldown and recovery
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rate_limiter import (
    AgentLimiter,
    LimitStatus,
    ProviderLimits,
    RateLimiter,
    RequestRecord,
    get_limiter,
    rate_limited,
)


@pytest.fixture(autouse=True)
def reset_rate_limiter(tmp_path, monkeypatch):
    """Reset rate limiter state before each test."""
    import agentic_brain.rate_limiter as rl

    # Use a temp state file for tests
    temp_state_file = tmp_path / "state.json"
    monkeypatch.setattr(rl.RateLimiter, "STATE_FILE", temp_state_file)

    # Reset the singleton if it exists
    if hasattr(rl, "_limiter_instance"):
        rl._limiter_instance = None

    yield

    # Cleanup after test
    if hasattr(rl, "_limiter_instance"):
        rl._limiter_instance = None


class TestProviderLimits:
    """Test ProviderLimits configuration."""

    def test_github_copilot_defaults(self):
        """GitHub Copilot has conservative limits."""
        limits = ProviderLimits.github_copilot()
        assert limits.name == "github_copilot"
        assert limits.requests_per_minute == 10
        assert limits.requests_per_hour == 150
        assert limits.cooldown_seconds == 120

    def test_ollama_unlimited(self):
        """Ollama (local) has high limits."""
        limits = ProviderLimits.ollama()
        assert limits.name == "ollama"
        assert limits.requests_per_minute >= 1000

    def test_backoff_fields_initialized(self):
        """Backoff fields start at defaults."""
        limits = ProviderLimits.github_copilot()
        assert limits.consecutive_429s == 0
        assert limits.backoff_multiplier == 1.0


class TestRateLimiterStatus:
    """Test rate limit status detection."""

    def test_green_when_idle(self):
        """Status is GREEN when no requests made."""
        limiter = RateLimiter(auto_save=False)
        status = limiter.get_status("github_copilot")
        assert status == LimitStatus.GREEN

    def test_yellow_at_50_percent(self):
        """Status is YELLOW at 50% capacity."""
        limiter = RateLimiter(auto_save=False)
        # Simulate 5 requests (50% of 10 RPM)
        for _ in range(5):
            limiter.record_success("github_copilot")

        status = limiter.get_status("github_copilot")
        assert status == LimitStatus.YELLOW

    def test_orange_at_80_percent(self):
        """Status is ORANGE at 80% capacity."""
        limiter = RateLimiter(auto_save=False)
        # Simulate 8 requests (80% of 10 RPM)
        for _ in range(8):
            limiter.record_success("github_copilot")

        status = limiter.get_status("github_copilot")
        assert status == LimitStatus.ORANGE

    def test_red_at_95_percent(self):
        """Status is RED at 95% capacity."""
        limiter = RateLimiter(auto_save=False)
        # Simulate 10 requests (100% of 10 RPM)
        for _ in range(10):
            limiter.record_success("github_copilot")

        status = limiter.get_status("github_copilot")
        assert status == LimitStatus.RED

    def test_cooldown_status(self):
        """Status is COOLDOWN after 429."""
        limiter = RateLimiter(auto_save=False)
        limiter.record_rate_limit("github_copilot")

        status = limiter.get_status("github_copilot")
        assert status == LimitStatus.COOLDOWN

    def test_can_proceed_green_yellow(self):
        """can_proceed() returns True for GREEN and YELLOW."""
        limiter = RateLimiter(auto_save=False)
        assert limiter.can_proceed("github_copilot") is True

        # Add some requests to get to YELLOW
        for _ in range(5):
            limiter.record_success("github_copilot")
        assert limiter.can_proceed("github_copilot") is True

    def test_cannot_proceed_red_cooldown(self):
        """can_proceed() returns False for RED and COOLDOWN."""
        limiter = RateLimiter(auto_save=False)
        limiter.record_rate_limit("github_copilot")
        assert limiter.can_proceed("github_copilot") is False


class TestExponentialBackoff:
    """Test exponential backoff on consecutive 429s."""

    def test_first_429_normal_cooldown(self):
        """First 429 uses normal cooldown."""
        limiter = RateLimiter(auto_save=False)
        limiter.limits["github_copilot"].cooldown_seconds

        limiter.record_rate_limit("github_copilot")

        limits = limiter.limits["github_copilot"]
        assert limits.consecutive_429s == 1
        assert limits.backoff_multiplier == 1.0

    def test_second_429_doubles_cooldown(self):
        """Second consecutive 429 doubles cooldown."""
        limiter = RateLimiter(auto_save=False)

        limiter.record_rate_limit("github_copilot")
        # Simulate cooldown expired
        limiter.cooldown_until["github_copilot"] = 0
        limiter.record_rate_limit("github_copilot")

        limits = limiter.limits["github_copilot"]
        assert limits.consecutive_429s == 2
        assert limits.backoff_multiplier == 2.0

    def test_third_429_quadruples_cooldown(self):
        """Third consecutive 429 quadruples cooldown."""
        limiter = RateLimiter(auto_save=False)

        for _i in range(3):
            limiter.record_rate_limit("github_copilot")
            limiter.cooldown_until["github_copilot"] = 0

        limits = limiter.limits["github_copilot"]
        assert limits.consecutive_429s == 3
        assert limits.backoff_multiplier == 4.0

    def test_backoff_capped_at_16x(self):
        """Backoff multiplier capped at 16x."""
        limiter = RateLimiter(auto_save=False)

        for _i in range(10):
            limiter.record_rate_limit("github_copilot")
            limiter.cooldown_until["github_copilot"] = 0

        limits = limiter.limits["github_copilot"]
        assert limits.backoff_multiplier == 16.0


class TestLocalFallback:
    """Test automatic fallback to local LLM."""

    def test_fallback_activated_on_429(self):
        """Local fallback activates on 429."""
        limiter = RateLimiter(auto_save=False)

        limiter.record_rate_limit("github_copilot")

        assert limiter.local_fallback_active is True
        assert limiter.should_use_local("github_copilot") is True

    def test_get_best_provider_returns_ollama_when_limited(self):
        """get_best_provider returns ollama when cloud limited."""
        limiter = RateLimiter(auto_save=False)

        # Before rate limit
        assert limiter.get_best_provider("github_copilot") == "github_copilot"

        # After rate limit
        limiter.record_rate_limit("github_copilot")
        assert limiter.get_best_provider("github_copilot") == "ollama"

    def test_fallback_deactivates_after_cooldown(self):
        """Local fallback deactivates after cooldown expires."""
        limiter = RateLimiter(auto_save=False)

        limiter.record_rate_limit("github_copilot")
        assert limiter.should_use_local("github_copilot") is True

        # Simulate cooldown expired
        limiter.cooldown_until["github_copilot"] = time.time() - 1
        assert limiter.should_use_local("github_copilot") is False

    def test_consecutive_429s_reset_after_cooldown(self):
        """Consecutive 429 count resets after successful cooldown."""
        limiter = RateLimiter(auto_save=False)

        # Hit rate limit multiple times
        for _ in range(3):
            limiter.record_rate_limit("github_copilot")
            limiter.cooldown_until["github_copilot"] = 0

        limits = limiter.limits["github_copilot"]
        assert limits.consecutive_429s == 3

        # Let cooldown fully expire and check
        limiter.cooldown_until["github_copilot"] = time.time() - 1
        limiter.should_use_local("github_copilot")  # This triggers reset

        assert limits.consecutive_429s == 0
        assert limits.backoff_multiplier == 1.0


class TestPatternLearning:
    """Test learning from 429 patterns."""

    def test_learns_peak_hours(self):
        """Learns peak hours from repeated 429s."""
        limiter = RateLimiter(auto_save=False)

        # Simulate 3 429s at hour 14
        # Create a proper mock that returns an int for hour and float for timestamp
        mock_now = MagicMock()
        mock_now.hour = 14
        mock_now.timestamp.return_value = time.time()

        with patch("agentic_brain.rate_limiter.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.now.return_value.isoformat.return_value = "2024-01-01T14:00:00Z"
            for _ in range(3):
                limiter.record_rate_limit("github_copilot")
                limiter.cooldown_until["github_copilot"] = 0

        limits = limiter.limits["github_copilot"]
        assert 14 in limits.peak_hours

    def test_reduces_rpm_multiplier(self):
        """RPM multiplier reduces after 429s."""
        limiter = RateLimiter(auto_save=False)

        initial_mult = limiter.limits["github_copilot"].learned_rpm_multiplier
        limiter.record_rate_limit("github_copilot")

        final_mult = limiter.limits["github_copilot"].learned_rpm_multiplier
        assert final_mult < initial_mult

    def test_multiplier_floors_at_30_percent(self):
        """RPM multiplier doesn't go below 30%."""
        limiter = RateLimiter(auto_save=False)

        # Many 429s
        for _ in range(50):
            limiter.record_rate_limit("github_copilot")
            limiter.cooldown_until["github_copilot"] = 0

        mult = limiter.limits["github_copilot"].learned_rpm_multiplier
        assert mult >= 0.3


class TestAutoSave:
    """Test auto-save on rate limit."""

    def test_save_callback_called_on_429(self):
        """Save callback is called when rate limited."""
        save_called = []

        def save_callback():
            save_called.append(True)

        limiter = RateLimiter(auto_save=True, save_callback=save_callback)
        limiter.record_rate_limit("github_copilot")

        assert len(save_called) == 1

    def test_no_save_when_disabled(self):
        """No save when auto_save=False."""
        save_called = []

        def save_callback():
            save_called.append(True)

        limiter = RateLimiter(auto_save=False, save_callback=save_callback)
        limiter.record_rate_limit("github_copilot")

        assert len(save_called) == 0


class TestStatePersistence:
    """Test state persistence to disk."""

    def test_state_persists_across_instances(self):
        """State persists across limiter instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"

            with patch.object(RateLimiter, "STATE_FILE", state_file):
                # First instance - learn something
                limiter1 = RateLimiter(auto_save=False)
                limiter1.record_rate_limit("github_copilot")
                limiter1._save_state()

                mult1 = limiter1.limits["github_copilot"].learned_rpm_multiplier

                # Second instance - should load state
                limiter2 = RateLimiter(auto_save=False)
                mult2 = limiter2.limits["github_copilot"].learned_rpm_multiplier

                assert mult1 == mult2

    def test_reset_learning(self):
        """reset_learning clears learned patterns."""
        limiter = RateLimiter(auto_save=False)

        # Learn something
        limiter.record_rate_limit("github_copilot")
        assert limiter.limits["github_copilot"].learned_rpm_multiplier < 1.0

        # Reset
        limiter.reset_learning("github_copilot")
        assert limiter.limits["github_copilot"].learned_rpm_multiplier == 1.0
        assert limiter.limits["github_copilot"].peak_hours == []


class TestAgentLimiter:
    """Test agent-specific rate limiting."""

    def test_can_deploy_when_under_limit(self):
        """Can deploy when under agent limit."""
        agent_limiter = AgentLimiter()
        assert agent_limiter.can_deploy() is True

    def test_cannot_deploy_when_at_limit(self):
        """Cannot deploy when at agent limit."""
        agent_limiter = AgentLimiter()

        for i in range(AgentLimiter.MAX_CONCURRENT_AGENTS):
            agent_limiter.register_agent(f"agent-{i}")

        assert agent_limiter.can_deploy() is False

    def test_can_deploy_after_unregister(self):
        """Can deploy after agent completes."""
        agent_limiter = AgentLimiter()

        for i in range(AgentLimiter.MAX_CONCURRENT_AGENTS):
            agent_limiter.register_agent(f"agent-{i}")

        assert agent_limiter.can_deploy() is False

        agent_limiter.unregister_agent("agent-0")
        assert agent_limiter.can_deploy() is True

    def test_deployment_advice(self):
        """Get deployment advice."""
        agent_limiter = AgentLimiter()

        advice = agent_limiter.get_deployment_advice()
        assert "can_deploy" in advice
        assert "active_agents" in advice
        assert "recommendation" in advice


class TestRateLimitedDecorator:
    """Test @rate_limited decorator."""

    @pytest.mark.asyncio
    async def test_decorator_records_success(self):
        """Decorator records successful calls."""
        limiter = get_limiter()
        initial_count = limiter.total_requests.get("github_copilot", 0)

        @rate_limited("github_copilot")
        async def my_func():
            return "success"

        result = await my_func()
        assert result == "success"

        # Should have recorded the request
        final_count = limiter.total_requests.get("github_copilot", 0)
        assert final_count > initial_count

    @pytest.mark.asyncio
    async def test_decorator_records_429(self):
        """Decorator records 429 errors."""
        limiter = get_limiter()

        @rate_limited("github_copilot")
        async def failing_func():
            raise Exception("429 rate limit exceeded")

        with pytest.raises(Exception):
            await failing_func()

        # Should have recorded the 429
        assert limiter.total_429s.get("github_copilot", 0) > 0


class TestHealthReport:
    """Test health report generation."""

    def test_health_report_format(self):
        """Health report has expected format."""
        limiter = RateLimiter(auto_save=False)

        report = limiter.get_health_report()

        assert "Rate Limiter Health Report" in report
        assert "github_copilot" in report
        assert "Status:" in report

    def test_stats_include_all_fields(self):
        """Stats include all expected fields."""
        limiter = RateLimiter(auto_save=False)

        stats = limiter.get_stats("github_copilot")

        assert "github_copilot" in stats
        provider_stats = stats["github_copilot"]

        assert "status" in provider_stats
        assert "requests_last_minute" in provider_stats
        assert "total_requests" in provider_stats
        assert "total_429s" in provider_stats
        assert "learned_multiplier" in provider_stats
        assert "peak_hours" in provider_stats


class TestWaitForCapacity:
    """Test async waiting for capacity."""

    @pytest.mark.asyncio
    async def test_wait_returns_immediately_when_green(self):
        """Wait returns immediately when status is GREEN."""
        limiter = RateLimiter(auto_save=False)

        start = time.time()
        await limiter.wait_for_capacity("github_copilot")
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should be nearly instant

    @pytest.mark.asyncio
    async def test_get_wait_time_during_cooldown(self):
        """get_wait_time returns cooldown remaining."""
        limiter = RateLimiter(auto_save=False)

        # Enter cooldown for 10 seconds
        limiter.cooldown_until["github_copilot"] = time.time() + 10

        wait_time = limiter.get_wait_time("github_copilot")
        assert 9 <= wait_time <= 10


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unknown_provider_returns_green(self):
        """Unknown provider returns GREEN status."""
        limiter = RateLimiter(auto_save=False)
        status = limiter.get_status("unknown_provider")
        assert status == LimitStatus.GREEN

    def test_add_custom_provider(self):
        """Can add custom provider limits."""
        limiter = RateLimiter(auto_save=False)

        custom = ProviderLimits(
            name="custom_api",
            requests_per_minute=30,
            cooldown_seconds=30,
        )
        limiter.add_provider(custom)

        assert "custom_api" in limiter.limits
        assert limiter.limits["custom_api"].requests_per_minute == 30

    def test_reset_cooldown_manually(self):
        """Can manually reset cooldown."""
        limiter = RateLimiter(auto_save=False)

        limiter.record_rate_limit("github_copilot")
        assert limiter.get_status("github_copilot") == LimitStatus.COOLDOWN

        limiter.reset_cooldown("github_copilot")
        # Still might be RED due to recent requests, but not COOLDOWN
        assert limiter.get_status("github_copilot") != LimitStatus.COOLDOWN
