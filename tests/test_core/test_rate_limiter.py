"""Tests for rate limit management."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from agentic_brain.core.rate_limiter import (
    RateLimitManager,
    RateLimitStrategy,
    ProviderQuota,
    ProviderState,
    RateLimitEvent,
    calculate_safe_agent_count,
    can_deploy_agents,
    get_deployment_recommendation,
)


class TestProviderQuota:
    """Test ProviderQuota dataclass."""
    
    def test_default_values(self):
        quota = ProviderQuota(name="test")
        assert quota.name == "test"
        assert quota.requests_per_minute == 60
        assert quota.requests_per_hour == 1000
        assert quota.concurrent_limit == 10
    
    def test_custom_values(self):
        quota = ProviderQuota(
            name="custom",
            requests_per_minute=30,
            concurrent_limit=5
        )
        assert quota.requests_per_minute == 30
        assert quota.concurrent_limit == 5


class TestProviderState:
    """Test ProviderState tracking."""
    
    def test_initial_state(self):
        state = ProviderState(name="test")
        assert state.requests_this_minute == 0
        assert state.active_requests == 0
        assert state.is_cooling_down is False
        assert state.success_rate == 1.0
    
    def test_cooldown_detection(self):
        state = ProviderState(name="test")
        assert state.is_cooling_down is False
        
        state.cooldown_until = datetime.now() + timedelta(seconds=30)
        assert state.is_cooling_down is True
        
        state.cooldown_until = datetime.now() - timedelta(seconds=1)
        assert state.is_cooling_down is False
    
    def test_success_rate_calculation(self):
        state = ProviderState(name="test")
        state.total_requests = 100
        state.total_rate_limits = 10
        assert state.success_rate == 0.9


class TestRateLimitManager:
    """Test RateLimitManager core functionality."""
    
    def test_initialization(self):
        manager = RateLimitManager()
        assert "claude" in manager.quotas
        assert "groq" in manager.quotas
        assert "ollama" in manager.quotas
    
    def test_can_request_initial(self):
        manager = RateLimitManager()
        assert manager.can_request("claude") is True
        assert manager.can_request("unknown_provider") is True
    
    def test_can_request_at_limit(self):
        manager = RateLimitManager()
        manager.states["claude"].requests_this_minute = 50
        assert manager.can_request("claude") is False
    
    def test_can_request_concurrent_limit(self):
        manager = RateLimitManager()
        manager.states["claude"].active_requests = 5
        assert manager.can_request("claude") is False
    
    def test_can_request_cooling_down(self):
        manager = RateLimitManager()
        manager.states["claude"].cooldown_until = datetime.now() + timedelta(seconds=30)
        assert manager.can_request("claude") is False
    
    def test_record_request(self):
        manager = RateLimitManager()
        manager.record_request("claude", tokens=1000)
        
        state = manager.states["claude"]
        assert state.requests_this_minute == 1
        assert state.tokens_this_minute == 1000
        assert state.active_requests == 1
        assert state.total_requests == 1
    
    def test_record_complete(self):
        manager = RateLimitManager()
        manager.record_request("claude")
        manager.record_complete("claude")
        
        state = manager.states["claude"]
        assert state.active_requests == 0
        assert state.consecutive_errors == 0
    
    def test_record_rate_limit(self):
        manager = RateLimitManager()
        manager.states["claude"].requests_this_minute = 10
        manager.record_rate_limit("claude", error_code=429)
        
        state = manager.states["claude"]
        assert state.consecutive_errors == 1
        assert state.total_rate_limits == 1
        assert state.cooldown_until is not None
        assert len(manager.events) == 1
    
    def test_get_available_provider(self):
        manager = RateLimitManager()
        
        # Should return highest priority available
        provider = manager.get_available_provider()
        assert provider in ["claude", "groq"]  # Priority 1 providers
    
    def test_get_available_provider_with_exclusion(self):
        manager = RateLimitManager()
        provider = manager.get_available_provider(exclude=["claude", "groq"])
        assert provider not in ["claude", "groq"]
    
    def test_get_available_provider_all_limited(self):
        manager = RateLimitManager()
        for name in manager.states:
            manager.states[name].cooldown_until = datetime.now() + timedelta(seconds=60)
        
        assert manager.get_available_provider() is None
    
    def test_get_wait_time(self):
        manager = RateLimitManager()
        assert manager.get_wait_time("claude") == 0.0
        
        manager.states["claude"].cooldown_until = datetime.now() + timedelta(seconds=30)
        wait = manager.get_wait_time("claude")
        assert 29 <= wait <= 31
    
    def test_get_status(self):
        manager = RateLimitManager()
        manager.record_request("claude")
        
        status = manager.get_status()
        assert "claude" in status
        assert status["claude"]["requests_this_minute"] == 1
        assert status["claude"]["can_request"] is True
    
    def test_reset_provider(self):
        manager = RateLimitManager()
        manager.record_request("claude")
        manager.record_rate_limit("claude")
        
        manager.reset_provider("claude")
        state = manager.states["claude"]
        assert state.requests_this_minute == 0
        assert state.consecutive_errors == 0


class TestLearning:
    """Test rate limit learning capabilities."""
    
    def test_learns_from_rate_limit(self):
        manager = RateLimitManager()
        original_limit = manager.quotas["claude"].requests_per_minute
        
        # Simulate hitting limit at 40 requests
        manager.states["claude"].requests_this_minute = 40
        manager.record_rate_limit("claude")
        
        # Should learn to use 80% of 40 = 32
        assert manager.quotas["claude"].requests_per_minute == 32
    
    def test_reduces_concurrent_after_repeated_limits(self):
        manager = RateLimitManager()
        original_concurrent = manager.quotas["claude"].concurrent_limit
        
        # Record multiple rate limits
        for _ in range(3):
            manager.record_rate_limit("claude")
        
        # Should reduce concurrent limit
        assert manager.quotas["claude"].concurrent_limit < original_concurrent


class TestBackoff:
    """Test exponential backoff calculation."""
    
    def test_backoff_increases_with_errors(self):
        manager = RateLimitManager()
        
        cooldowns = []
        for i in range(5):
            manager.states["claude"].consecutive_errors = i
            cooldown = manager._calculate_cooldown("claude")
            cooldowns.append(cooldown)
        
        # Each cooldown should be larger than previous (with some jitter tolerance)
        for i in range(1, len(cooldowns)):
            assert cooldowns[i] >= cooldowns[i-1] * 0.5  # Allow for jitter
    
    def test_backoff_capped_at_max(self):
        manager = RateLimitManager(max_backoff=60.0)
        manager.states["claude"].consecutive_errors = 100
        
        cooldown = manager._calculate_cooldown("claude")
        assert cooldown <= 75  # 60 + 25% jitter


class TestSafeAgentCalculation:
    """Test safe agent count calculation."""
    
    def test_calculate_safe_agent_count(self):
        count = calculate_safe_agent_count(
            provider="claude",
            task_duration_minutes=10,
            requests_per_agent=20
        )
        # With 50 req/min, 0.7 safety, 2 req/min per agent = 17
        # But capped by concurrent limit of 5
        assert count == 5
    
    def test_calculate_safe_count_ollama(self):
        count = calculate_safe_agent_count(
            provider="ollama",
            task_duration_minutes=10,
            requests_per_agent=20
        )
        # Ollama has 1000 req/min but concurrent limit 2
        assert count == 2
    
    def test_can_deploy_agents(self):
        assert can_deploy_agents(3, "claude") is True
        assert can_deploy_agents(100, "claude") is False
    
    def test_deployment_recommendation_safe(self):
        rec = get_deployment_recommendation(3, "claude")
        assert rec["safe"] is True
        assert rec["recommended_count"] == 3
    
    def test_deployment_recommendation_unsafe(self):
        rec = get_deployment_recommendation(20, "claude")
        assert rec["safe"] is False
        assert rec["recommended_count"] < 20
        assert "batch_strategy" in rec


class TestAsyncContext:
    """Test async request context."""
    
    @pytest.mark.asyncio
    async def test_request_context_success(self):
        manager = RateLimitManager()
        
        async with manager.request_context("claude"):
            assert manager.states["claude"].active_requests == 1
        
        assert manager.states["claude"].active_requests == 0
    
    @pytest.mark.asyncio
    async def test_request_context_tracks_tokens(self):
        manager = RateLimitManager()
        
        async with manager.request_context("claude", tokens=500):
            pass
        
        assert manager.states["claude"].tokens_this_minute == 500


class TestPersistence:
    """Test history persistence."""
    
    def test_save_and_load_history(self, tmp_path):
        history_file = tmp_path / "rate_limits.json"
        
        # Create manager and learn
        manager1 = RateLimitManager(history_file=history_file)
        manager1.quotas["claude"].requests_per_minute = 25
        manager1._save_history()
        
        # Create new manager, should load learned values
        manager2 = RateLimitManager(history_file=history_file)
        assert manager2.quotas["claude"].requests_per_minute == 25


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
