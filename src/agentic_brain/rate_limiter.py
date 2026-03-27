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
🧱 Brick Wall Rate Limiter - Like a studio limiter for API calls.

Inspired by audio production limiters (Pro Tools, Logic Pro), this module
prevents API rate limit "clipping" by:
1. Monitoring request rates in real-time
2. Learning from 429 errors and adapting
3. Auto-saving state before hitting limits
4. Queuing requests during cooldown
5. Tracking time-of-day patterns

Usage:
    >>> from agentic_brain.rate_limiter import RateLimiter, rate_limited
    >>> limiter = RateLimiter()
    >>>
    >>> # Check before making request
    >>> if limiter.can_proceed("github"):
    ...     response = await make_request()
    ...     limiter.record_success("github")
    >>> else:
    ...     print("Cooling down, try later")
    >>>
    >>> # Or use decorator
    >>> @rate_limited("openai")
    >>> async def call_openai():
    ...     ...
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# Type for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


class LimitStatus(Enum):
    """Current rate limit status - like a VU meter."""

    GREEN = "green"  # < 50% of limit - all good
    YELLOW = "yellow"  # 50-80% of limit - slow down
    ORANGE = "orange"  # 80-95% of limit - queue requests
    RED = "red"  # > 95% or active cooldown - stop
    COOLDOWN = "cooldown"  # Hit 429, waiting for reset


@dataclass
class ProviderLimits:
    """Rate limits for a specific provider."""

    name: str
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    cooldown_seconds: int = 60

    # Learned adjustments (updated from 429s)
    learned_rpm_multiplier: float = 1.0  # Reduce if hitting limits
    peak_hours: list[int] = field(default_factory=list)  # Hours with more 429s

    # Exponential backoff state
    consecutive_429s: int = 0  # Count of consecutive 429s
    backoff_multiplier: float = 1.0  # Exponential backoff (doubles each 429)

    @classmethod
    def github_copilot(cls) -> ProviderLimits:
        """GitHub Copilot limits (Pro+ plan: 1500/month premium)."""
        return cls(
            name="github_copilot",
            requests_per_minute=10,  # Conservative for agents
            requests_per_hour=150,  # GitHub's hourly limit
            requests_per_day=500,  # Daily budget (~50/day for month)
            cooldown_seconds=120,  # 2 min cooldown on 429
        )

    @classmethod
    def openai(cls) -> ProviderLimits:
        """OpenAI API limits."""
        return cls(
            name="openai",
            requests_per_minute=60,
            requests_per_hour=3500,
            requests_per_day=10000,
            cooldown_seconds=60,
        )

    @classmethod
    def anthropic(cls) -> ProviderLimits:
        """Anthropic Claude limits."""
        return cls(
            name="anthropic",
            requests_per_minute=60,
            requests_per_hour=1000,
            requests_per_day=10000,
            cooldown_seconds=60,
        )

    @classmethod
    def ollama(cls) -> ProviderLimits:
        """Ollama (local) - unlimited but track for patterns."""
        return cls(
            name="ollama",
            requests_per_minute=1000,  # Essentially unlimited
            requests_per_hour=100000,
            requests_per_day=1000000,
            cooldown_seconds=5,
        )


@dataclass
class RequestRecord:
    """Record of a single request."""

    timestamp: float
    provider: str
    success: bool
    status_code: int = 200
    response_time_ms: float = 0
    hour_of_day: int = 0  # For pattern learning


class RateLimiter:
    """
    🧱 Brick Wall Rate Limiter

    Like a studio limiter that prevents audio clipping, this prevents
    API rate limit errors by monitoring and throttling requests.

    Features:
    - Real-time request rate monitoring
    - Automatic cooldown on 429 errors
    - Time-of-day pattern learning
    - Auto-save state on rate limit
    - Request queuing during cooldown
    - Provider-specific limits

    Example:
        >>> limiter = RateLimiter()
        >>>
        >>> # Check status (like looking at VU meter)
        >>> status = limiter.get_status("github_copilot")
        >>> print(f"Status: {status.name}")  # GREEN, YELLOW, ORANGE, RED
        >>>
        >>> # Safe request pattern
        >>> if limiter.can_proceed("github_copilot"):
        ...     try:
        ...         response = await make_api_call()
        ...         limiter.record_success("github_copilot")
        ...     except RateLimitError:
        ...         limiter.record_rate_limit("github_copilot")
        >>> else:
        ...     # Queue or wait
        ...     await limiter.wait_for_capacity("github_copilot")
    """

    # State file for persistence
    STATE_FILE = Path.home() / ".brain-rate-limiter" / "state.json"

    def __init__(
        self,
        auto_save: bool = True,
        save_callback: Callable[[], None] | None = None,
    ):
        """
        Initialize rate limiter.

        Args:
            auto_save: Auto-save brain state when rate limited
            save_callback: Function to call for saving state (e.g., continuity save)
        """
        self.auto_save = auto_save
        self.save_callback = save_callback

        # Provider limits
        self.limits: dict[str, ProviderLimits] = {
            "github_copilot": ProviderLimits.github_copilot(),
            "openai": ProviderLimits.openai(),
            "anthropic": ProviderLimits.anthropic(),
            "ollama": ProviderLimits.ollama(),
        }

        # Request history per provider (last hour)
        self.history: dict[str, deque[RequestRecord]] = {
            name: deque(maxlen=10000) for name in self.limits
        }

        # Cooldown state
        self.cooldown_until: dict[str, float] = {}

        # Pattern learning
        self.hourly_429_counts: dict[str, dict[int, int]] = {
            name: dict.fromkeys(range(24), 0) for name in self.limits
        }

        # Stats
        self.total_requests: dict[str, int] = dict.fromkeys(self.limits, 0)
        self.total_429s: dict[str, int] = dict.fromkeys(self.limits, 0)

        # Load persisted state
        if self.auto_save:
            self._load_state()

        logger.info("🧱 Brick Wall Rate Limiter initialized")

    def _load_state(self) -> None:
        """Load persisted state from disk."""
        if not self.STATE_FILE.exists():
            return

        try:
            with open(self.STATE_FILE) as f:
                state = json.load(f)

            # Restore learned patterns
            for name, limits in self.limits.items():
                if name in state.get("learned_multipliers", {}):
                    limits.learned_rpm_multiplier = state["learned_multipliers"][name]
                if name in state.get("peak_hours", {}):
                    limits.peak_hours = state["peak_hours"][name]

            # Restore 429 patterns
            if "hourly_429_counts" in state:
                self.hourly_429_counts = state["hourly_429_counts"]

            # Restore stats
            if "total_requests" in state:
                self.total_requests = state["total_requests"]
            if "total_429s" in state:
                self.total_429s = state["total_429s"]

            logger.info("📊 Loaded rate limiter state from disk")

        except Exception as e:
            logger.warning(f"Could not load rate limiter state: {e}")

    def _save_state(self) -> None:
        """Persist state to disk."""
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "timestamp": datetime.now(UTC).isoformat(),
            "learned_multipliers": {
                name: limits.learned_rpm_multiplier
                for name, limits in self.limits.items()
            },
            "peak_hours": {
                name: limits.peak_hours for name, limits in self.limits.items()
            },
            "hourly_429_counts": self.hourly_429_counts,
            "total_requests": self.total_requests,
            "total_429s": self.total_429s,
        }

        with open(self.STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

        logger.debug("💾 Saved rate limiter state")

    def add_provider(self, limits: ProviderLimits) -> None:
        """Add or update a provider's limits."""
        self.limits[limits.name] = limits
        if limits.name not in self.history:
            self.history[limits.name] = deque(maxlen=10000)
            self.cooldown_until[limits.name] = 0
            self.hourly_429_counts[limits.name] = dict.fromkeys(range(24), 0)
            self.total_requests[limits.name] = 0
            self.total_429s[limits.name] = 0

    def get_status(self, provider: str) -> LimitStatus:
        """
        Get current rate limit status for provider.

        Like checking a VU meter:
        - GREEN: All good, plenty of headroom
        - YELLOW: Approaching limits, slow down
        - ORANGE: Near limits, queue requests
        - RED: At limit, stop
        - COOLDOWN: Hit 429, waiting for reset

        Args:
            provider: Provider name

        Returns:
            Current status
        """
        if provider not in self.limits:
            return LimitStatus.GREEN

        # Check if in cooldown
        if provider in self.cooldown_until:
            if time.time() < self.cooldown_until[provider]:
                return LimitStatus.COOLDOWN

        # Calculate current rate
        limits = self.limits[provider]
        now = time.time()

        # Count requests in last minute
        minute_ago = now - 60
        recent_requests = sum(
            1 for r in self.history[provider] if r.timestamp > minute_ago
        )

        # Apply learned multiplier
        effective_rpm = limits.requests_per_minute * limits.learned_rpm_multiplier

        # Check if in peak hour (more conservative)
        current_hour = datetime.now().hour
        if current_hour in limits.peak_hours:
            effective_rpm *= 0.7  # 30% reduction during peak

        # Calculate usage percentage
        usage_pct = recent_requests / effective_rpm if effective_rpm > 0 else 1.0

        if usage_pct >= 0.95:
            return LimitStatus.RED
        elif usage_pct >= 0.80:
            return LimitStatus.ORANGE
        elif usage_pct >= 0.50:
            return LimitStatus.YELLOW
        else:
            return LimitStatus.GREEN

    def can_proceed(self, provider: str) -> bool:
        """
        Check if we can make a request to this provider.

        Args:
            provider: Provider name

        Returns:
            True if safe to proceed
        """
        status = self.get_status(provider)
        return status in (LimitStatus.GREEN, LimitStatus.YELLOW)

    def get_wait_time(self, provider: str) -> float:
        """
        Get seconds to wait before next request.

        Args:
            provider: Provider name

        Returns:
            Seconds to wait (0 if can proceed immediately)
        """
        status = self.get_status(provider)

        if status == LimitStatus.COOLDOWN:
            remaining = self.cooldown_until.get(provider, 0) - time.time()
            return max(0, remaining)
        elif status == LimitStatus.RED:
            return 30.0  # Wait 30 seconds
        elif status == LimitStatus.ORANGE:
            return 5.0  # Wait 5 seconds
        else:
            return 0.0

    async def wait_for_capacity(self, provider: str) -> None:
        """
        Wait until we have capacity for this provider.

        Args:
            provider: Provider name
        """
        wait_time = self.get_wait_time(provider)
        if wait_time > 0:
            logger.info(f"⏳ Rate limiter: waiting {wait_time:.1f}s for {provider}")
            await asyncio.sleep(wait_time)

    def record_success(self, provider: str, response_time_ms: float = 0) -> None:
        """
        Record a successful request.

        Args:
            provider: Provider name
            response_time_ms: Response time in milliseconds
        """
        if provider not in self.history:
            return

        now = time.time()
        record = RequestRecord(
            timestamp=now,
            provider=provider,
            success=True,
            status_code=200,
            response_time_ms=response_time_ms,
            hour_of_day=datetime.now().hour,
        )

        self.history[provider].append(record)
        self.total_requests[provider] = self.total_requests.get(provider, 0) + 1

        # Clean old history
        self._cleanup_history(provider)

    def record_rate_limit(self, provider: str) -> None:
        """
        Record a 429 rate limit error.

        This triggers:
        1. Cooldown period
        2. Pattern learning
        3. Auto-save if enabled

        Args:
            provider: Provider name
        """
        if provider not in self.limits:
            return

        now = time.time()
        current_hour = datetime.now().hour
        limits = self.limits[provider]

        # Record the 429
        record = RequestRecord(
            timestamp=now,
            provider=provider,
            success=False,
            status_code=429,
            hour_of_day=current_hour,
        )
        self.history[provider].append(record)
        self.total_requests[provider] = self.total_requests.get(provider, 0) + 1
        self.total_429s[provider] = self.total_429s.get(provider, 0) + 1

        # Increment consecutive 429s and apply exponential backoff
        limits.consecutive_429s += 1
        limits.backoff_multiplier = min(16.0, 2 ** (limits.consecutive_429s - 1))

        # Calculate cooldown with exponential backoff
        cooldown = limits.cooldown_seconds * limits.backoff_multiplier
        self.cooldown_until[provider] = now + cooldown

        logger.warning(
            f"🛑 Rate limited on {provider}! "
            f"Consecutive 429s: {limits.consecutive_429s}, "
            f"Backoff: {limits.backoff_multiplier}x, "
            f"Cooling down for {cooldown:.0f}s"
        )

        # Learn from this
        self._learn_from_429(provider, current_hour)

        # Trigger fallback to local LLM
        self._activate_local_fallback(provider)

        # Auto-save state
        if self.auto_save:
            self._trigger_save()
            # Persist learned patterns
            self._save_state()

    def _learn_from_429(self, provider: str, hour: int) -> None:
        """
        Learn from a 429 error.

        Updates:
        - learned_rpm_multiplier (reduce if hitting limits)
        - peak_hours (track problematic hours)
        """
        limits = self.limits[provider]

        # Track hourly patterns
        self.hourly_429_counts[provider][hour] = (
            self.hourly_429_counts[provider].get(hour, 0) + 1
        )

        # If this hour has 3+ 429s, mark as peak hour
        if self.hourly_429_counts[provider][hour] >= 3:
            if hour not in limits.peak_hours:
                limits.peak_hours.append(hour)
                logger.info(f"📊 Learned: Hour {hour} is peak time for {provider}")

        # Reduce multiplier (more conservative)
        limits.learned_rpm_multiplier = max(
            0.3,  # Never go below 30% of stated limit
            limits.learned_rpm_multiplier * 0.85,  # Reduce by 15%
        )
        logger.info(
            f"📊 Adjusted {provider} rate multiplier to "
            f"{limits.learned_rpm_multiplier:.2f}"
        )

    def _activate_local_fallback(self, provider: str) -> None:
        """
        Activate fallback to local LLM when cloud is rate limited.

        This ensures work continues even when cloud APIs are unavailable.
        """
        self.local_fallback_active = True
        self.fallback_reason = f"Rate limited on {provider}"
        self.fallback_activated_at = time.time()

        logger.info(
            f"🔄 Activated local LLM fallback due to {provider} rate limit. "
            f"Requests will route to Ollama until cooldown expires."
        )

    def should_use_local(self, preferred_provider: str = "github_copilot") -> bool:
        """
        Check if we should use local LLM instead of cloud.

        Returns True if:
        - Cloud provider is in cooldown
        - Local fallback is active
        - Cloud provider status is RED or ORANGE

        Args:
            preferred_provider: The cloud provider we'd normally use

        Returns:
            True if should use local LLM
        """
        # Check if fallback is active
        if getattr(self, "local_fallback_active", False):
            # Check if cooldown has expired
            cooldown_end = self.cooldown_until.get(preferred_provider, 0)
            if time.time() > cooldown_end:
                self.local_fallback_active = False
                limits = self.limits.get(preferred_provider)
                if limits:
                    # Reset consecutive 429s on successful cooldown
                    limits.consecutive_429s = 0
                    limits.backoff_multiplier = 1.0
                logger.info("✅ Cooldown expired, deactivating local fallback")
                return False
            return True

        # Check provider status
        status = self.get_status(preferred_provider)
        return status in (LimitStatus.COOLDOWN, LimitStatus.RED)

    def get_best_provider(self, preferred: str = "github_copilot") -> str:
        """
        Get the best available provider right now.

        Automatically falls back to Ollama if cloud is rate limited.

        Args:
            preferred: Preferred cloud provider

        Returns:
            Provider name to use ("ollama" if falling back)
        """
        if self.should_use_local(preferred):
            return "ollama"
        return preferred

    def _trigger_save(self) -> None:
        """Trigger auto-save of brain state."""
        logger.info("💾 Rate limit triggered auto-save")

        if self.save_callback:
            try:
                self.save_callback()
            except Exception as e:
                logger.error(f"Auto-save callback failed: {e}")

        # Also save our own state
        self._save_state()

    def _cleanup_history(self, provider: str) -> None:
        """Remove history older than 1 hour."""
        if provider not in self.history:
            return

        hour_ago = time.time() - 3600
        while self.history[provider] and self.history[provider][0].timestamp < hour_ago:
            self.history[provider].popleft()

    def get_stats(self, provider: str | None = None) -> dict[str, Any]:
        """
        Get rate limiter statistics.

        Args:
            provider: Specific provider or None for all

        Returns:
            Statistics dict
        """
        if provider:
            providers = [provider] if provider in self.limits else []
        else:
            providers = list(self.limits.keys())

        stats = {}
        for p in providers:
            limits = self.limits[p]
            status = self.get_status(p)

            # Count recent requests
            now = time.time()
            minute_ago = now - 60
            hour_ago = now - 3600

            rpm = sum(1 for r in self.history[p] if r.timestamp > minute_ago)
            rph = sum(1 for r in self.history[p] if r.timestamp > hour_ago)

            stats[p] = {
                "status": status.value,
                "requests_last_minute": rpm,
                "requests_last_hour": rph,
                "limit_rpm": int(
                    limits.requests_per_minute * limits.learned_rpm_multiplier
                ),
                "total_requests": self.total_requests.get(p, 0),
                "total_429s": self.total_429s.get(p, 0),
                "in_cooldown": time.time() < self.cooldown_until.get(p, 0),
                "cooldown_remaining": max(
                    0, self.cooldown_until.get(p, 0) - time.time()
                ),
                "learned_multiplier": limits.learned_rpm_multiplier,
                "peak_hours": limits.peak_hours,
            }

        return stats

    def get_health_report(self) -> str:
        """
        Get a human-readable health report.

        Returns:
            Formatted health report
        """
        lines = ["🧱 Rate Limiter Health Report", "=" * 40]

        for provider in self.limits:
            status = self.get_status(provider)
            stats = self.get_stats(provider)[provider]

            # Status emoji
            status_emoji = {
                LimitStatus.GREEN: "🟢",
                LimitStatus.YELLOW: "🟡",
                LimitStatus.ORANGE: "🟠",
                LimitStatus.RED: "🔴",
                LimitStatus.COOLDOWN: "⏸️",
            }.get(status, "❓")

            lines.append(f"\n{status_emoji} {provider}")
            lines.append(f"   Status: {status.value}")
            lines.append(
                f"   RPM: {stats['requests_last_minute']}/{stats['limit_rpm']}"
            )
            lines.append(
                f"   Total: {stats['total_requests']} ({stats['total_429s']} 429s)"
            )

            if stats["in_cooldown"]:
                lines.append(
                    f"   ⏳ Cooldown: {stats['cooldown_remaining']:.0f}s remaining"
                )

            if stats["peak_hours"]:
                lines.append(f"   📊 Peak hours: {stats['peak_hours']}")

        return "\n".join(lines)

    def reset_cooldown(self, provider: str) -> None:
        """Manually reset cooldown for a provider."""
        if provider in self.cooldown_until:
            self.cooldown_until[provider] = 0
            logger.info(f"✅ Reset cooldown for {provider}")

    def reset_learning(self, provider: str | None = None) -> None:
        """Reset learned patterns (e.g., after plan change)."""
        providers = [provider] if provider else list(self.limits.keys())

        for p in providers:
            if p in self.limits:
                self.limits[p].learned_rpm_multiplier = 1.0
                self.limits[p].peak_hours = []
                self.hourly_429_counts[p] = dict.fromkeys(range(24), 0)

        self._save_state()
        logger.info(f"🔄 Reset learning for {providers}")


# Global instance
_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter


def rate_limited(provider: str):
    """
    Decorator for rate-limited functions.

    Usage:
        >>> @rate_limited("github_copilot")
        >>> async def call_copilot():
        ...     ...
    """

    def decorator(func: F) -> F:
        async def wrapper(*args, **kwargs):
            limiter = get_limiter()

            # Wait if needed
            await limiter.wait_for_capacity(provider)

            start = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed_ms = (time.time() - start) * 1000
                limiter.record_success(provider, elapsed_ms)
                return result
            except Exception as e:
                # Check if it's a rate limit error
                if "429" in str(e) or "rate limit" in str(e).lower():
                    limiter.record_rate_limit(provider)
                raise

        return wrapper  # type: ignore

    return decorator


class AgentLimiter:
    """
    🤖 Agent-specific rate limiter.

    Tracks how many agents are running and prevents deploying
    too many at once (which causes rate limiting).
    """

    MAX_CONCURRENT_AGENTS = 3  # Safe default

    def __init__(self):
        self.active_agents: dict[str, float] = {}  # agent_id -> start_time
        self.limiter = get_limiter()

    def can_deploy(self) -> bool:
        """Check if we can deploy another agent."""
        # Clean up old agents (> 30 min)
        now = time.time()
        self.active_agents = {
            aid: start
            for aid, start in self.active_agents.items()
            if now - start < 1800
        }

        # Check count
        if len(self.active_agents) >= self.MAX_CONCURRENT_AGENTS:
            return False

        # Check rate limiter
        return self.limiter.can_proceed("github_copilot")

    def register_agent(self, agent_id: str) -> None:
        """Register a deployed agent."""
        self.active_agents[agent_id] = time.time()

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister a completed agent."""
        self.active_agents.pop(agent_id, None)

    def get_deployment_advice(self) -> dict[str, Any]:
        """Get advice on agent deployment."""
        can_deploy = self.can_deploy()
        status = self.limiter.get_status("github_copilot")

        return {
            "can_deploy": can_deploy,
            "active_agents": len(self.active_agents),
            "max_agents": self.MAX_CONCURRENT_AGENTS,
            "rate_status": status.value,
            "recommendation": self._get_recommendation(status),
        }

    def _get_recommendation(self, status: LimitStatus) -> str:
        """Get human-readable recommendation."""
        if status == LimitStatus.COOLDOWN:
            return "⏸️ In cooldown - wait before deploying agents"
        elif status == LimitStatus.RED:
            return "🔴 At rate limit - do not deploy agents"
        elif status == LimitStatus.ORANGE:
            return "🟠 Near limit - deploy max 1 agent"
        elif status == LimitStatus.YELLOW:
            return "🟡 Approaching limit - deploy max 2 agents"
        else:
            return "🟢 Good to go - safe to deploy agents"
