import asyncio
import time
import types
from datetime import datetime, timedelta

import pytest

from agentic_brain.core.rate_limiter import (
    ProviderQuota,
    ProviderState,
    RateLimitManager,
    RateLimitStrategy,
    calculate_safe_agent_count,
    can_deploy_agents,
    get_deployment_recommendation,
    get_rate_limit_manager,
)


def test_can_request_unknown_provider_returns_true():
    mgr = RateLimitManager()
    assert mgr.can_request("some_unknown_provider") is True


def test_record_and_complete_changes_active_requests():
    mgr = RateLimitManager()
    mgr.record_request("claude")
    state = mgr.states["claude"]
    assert state.active_requests >= 1
    mgr.record_complete("claude")
    assert state.active_requests >= 0


def test_record_rate_limit_sets_cooldown_and_event(tmp_path):
    history = tmp_path / "rate_limits.json"
    mgr = RateLimitManager(history_file=history)
    mgr.record_request("grok")
    mgr.record_rate_limit("grok", error_code=429, retry_after=1, context={"x": 1})
    state = mgr.states["grok"]
    assert state.last_rate_limit is not None
    assert state.cooldown_until is not None
    assert any(e.provider == "grok" for e in mgr.events)


def test_calculate_cooldown_jitter_and_bounds():
    mgr = RateLimitManager()
    # Force consecutive errors to increase backoff
    mgr.states["groq"].consecutive_errors = 3
    val = mgr._calculate_cooldown("groq")
    assert isinstance(val, int)
    assert val >= mgr.quotas["groq"].cooldown_seconds


def test_get_available_provider_respects_exclude():
    mgr = RateLimitManager()
    # exclude local fastest providers
    got = mgr.get_available_provider(exclude=["ollama", "groq"])
    assert got is None or got not in {"ollama", "groq"}


def test_get_wait_time_returns_zero_when_no_cooldown():
    mgr = RateLimitManager()
    assert mgr.get_wait_time("grok") == 0.0


def test_get_status_structure():
    mgr = RateLimitManager()
    status = mgr.get_status()
    assert isinstance(status, dict)
    for name, info in status.items():
        assert "can_request" in info
        assert "total_requests" in info


def test_reset_provider_resets_state():
    mgr = RateLimitManager()
    mgr.record_request("grok")
    mgr.reset_provider("grok")
    state = mgr.states["grok"]
    assert state.total_requests == 0


def test_calculate_safe_agent_count_respects_concurrent_limit():
    # Use a provider with small concurrent_limit
    safe = calculate_safe_agent_count(
        provider="claude", task_duration_minutes=1, requests_per_agent=1
    )
    assert isinstance(safe, int)
    assert safe >= 1


def test_get_deployment_recommendation_safe_and_unsafe():
    rec = get_deployment_recommendation(1, provider="claude")
    assert "safe" in rec
    rec2 = get_deployment_recommendation(10000, provider="claude")
    assert rec2["safe"] is False
