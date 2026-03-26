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
Smart Rate Limiting for RAG Loaders

Protects against:
- API rate limits from external services (GitHub, Confluence, etc.)
- DoS attacks on the loader endpoints
- Resource exhaustion from large document processing
- Concurrent request floods
- Malicious batch operations

Features:
- Per-loader rate limits matching external API constraints
- Adaptive exponential backoff
- Concurrent request limiting
- IP-based rate limiting for API endpoints
- Redis-backed distributed rate limiting
- Document size and batch limits
- Automatic retry with jitter
"""

import asyncio
import inspect
import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded"""

    pass


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting a loader or endpoint"""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    cooldown_seconds: int = 60
    max_concurrent: int = 5
    max_document_size_mb: int = 100
    max_documents_per_batch: int = 50
    backoff_multiplier: float = 2.0
    max_backoff_seconds: int = 300


@dataclass
class RateLimitState:
    """Current state of rate limiting for a key"""

    request_timestamps: List[float] = field(default_factory=list)
    concurrent_count: int = 0
    backoff_until: Optional[float] = None
    consecutive_failures: int = 0


class SmartRateLimiter:
    """Intelligent rate limiting with adaptive backoff"""

    # Per-loader rate limits (external API limits)
    LOADER_LIMITS = {
        "github": RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=5000,
            burst_limit=10,
            max_concurrent=5,
        ),
        "confluence": RateLimitConfig(
            requests_per_minute=100, burst_limit=20, max_concurrent=10
        ),
        "slack": RateLimitConfig(
            requests_per_minute=50, max_concurrent=3, burst_limit=5
        ),
        "salesforce": RateLimitConfig(requests_per_minute=100, max_concurrent=5),
        "notion": RateLimitConfig(
            requests_per_minute=3,  # Notion is VERY strict!
            burst_limit=3,
            max_concurrent=1,
            cooldown_seconds=120,
        ),
        "jira": RateLimitConfig(requests_per_minute=100, burst_limit=15),
        "zendesk": RateLimitConfig(requests_per_minute=200, burst_limit=30),
        "google_drive": RateLimitConfig(
            requests_per_minute=100, burst_limit=20, max_document_size_mb=50
        ),
        "sharepoint": RateLimitConfig(requests_per_minute=60, max_concurrent=5),
        "default": RateLimitConfig(),
    }

    def __init__(self, use_redis: bool = False, redis_url: Optional[str] = None):
        """Initialize rate limiter.

        Args:
            use_redis: Use Redis for distributed rate limiting
            redis_url: Redis connection URL (if use_redis=True)
        """
        self._states: Dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._use_redis = use_redis
        self._redis = None

        if use_redis:
            self._init_redis(redis_url)

    def _init_redis(self, redis_url: Optional[str]):
        """Initialize Redis connection for distributed rate limiting"""
        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(
                redis_url or "redis://localhost:6379",
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("✓ Redis-backed rate limiting enabled")
        except ImportError:
            logger.warning(
                "redis package not installed. "
                "Falling back to in-memory rate limiting. "
                "Install with: pip install redis"
            )
            self._use_redis = False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._use_redis = False

    def _get_config(self, loader_name: str) -> RateLimitConfig:
        """Get rate limit config for a loader"""
        return self.LOADER_LIMITS.get(loader_name, self.LOADER_LIMITS["default"])

    def _get_state(self, key: str) -> RateLimitState:
        """Get rate limit state for a key"""
        return self._states[key]

    def _clean_old_timestamps(self, state: RateLimitState, window_seconds: int = 60):
        """Remove timestamps outside the rate limit window"""
        now = time.time()
        cutoff = now - window_seconds
        state.request_timestamps = [
            ts for ts in state.request_timestamps if ts > cutoff
        ]

    async def _check_redis_limit(self, key: str, config: RateLimitConfig) -> bool:
        """Check rate limit using Redis (distributed)"""
        if not self._redis:
            return await self._check_memory_limit(key, config)

        try:
            now = time.time()
            pipe = self._redis.pipeline()

            # Use Redis sorted set with timestamps as scores
            minute_key = f"rate_limit:{key}:minute"
            hour_key = f"rate_limit:{key}:hour"

            # Remove old timestamps
            pipe.zremrangebyscore(minute_key, 0, now - 60)
            pipe.zremrangebyscore(hour_key, 0, now - 3600)

            # Count current requests
            pipe.zcard(minute_key)
            pipe.zcard(hour_key)

            # Add current request
            pipe.zadd(minute_key, {str(now): now})
            pipe.zadd(hour_key, {str(now): now})

            # Set expiry
            pipe.expire(minute_key, 120)
            pipe.expire(hour_key, 7200)

            results = await pipe.execute()
            minute_count = results[2]
            hour_count = results[3]

            # Check limits
            if minute_count >= config.requests_per_minute:
                logger.warning(f"Rate limit exceeded for {key}: {minute_count}/min")
                return False

            if hour_count >= config.requests_per_hour:
                logger.warning(
                    f"Hourly rate limit exceeded for {key}: {hour_count}/hour"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fall back to memory
            return await self._check_memory_limit(key, config)

    async def _check_memory_limit(self, key: str, config: RateLimitConfig) -> bool:
        """Check rate limit using in-memory state"""
        state = self._get_state(key)

        # Clean old timestamps
        self._clean_old_timestamps(state, window_seconds=60)

        # Check per-minute limit
        if len(state.request_timestamps) >= config.requests_per_minute:
            return False

        # Check hourly limit (keep hour of timestamps)
        hour_timestamps = [
            ts for ts in state.request_timestamps if time.time() - ts < 3600
        ]
        return not len(hour_timestamps) >= config.requests_per_hour

    async def acquire(self, loader_name: str, ip_address: Optional[str] = None) -> bool:
        """Acquire rate limit slot, returns False if limited.

        Args:
            loader_name: Name of the loader (github, confluence, etc.)
            ip_address: Optional IP address for IP-based limiting

        Returns:
            True if slot acquired, False if rate limited
        """
        config = self._get_config(loader_name)
        key = f"{loader_name}:{ip_address}" if ip_address else loader_name

        async with self._locks[key]:
            state = self._get_state(key)

            # Check backoff
            if state.backoff_until and time.time() < state.backoff_until:
                return False

            # Clear backoff if expired
            if state.backoff_until:
                state.backoff_until = None
                state.consecutive_failures = 0

            # Check concurrent limit
            if state.concurrent_count >= config.max_concurrent:
                return False

            # Check rate limit
            if self._use_redis:
                can_proceed = await self._check_redis_limit(key, config)
            else:
                can_proceed = await self._check_memory_limit(key, config)

            if not can_proceed:
                return False

            # Acquire slot
            state.request_timestamps.append(time.time())
            state.concurrent_count += 1
            return True

    def release(self, loader_name: str, ip_address: Optional[str] = None):
        """Release rate limit slot.

        Args:
            loader_name: Name of the loader
            ip_address: Optional IP address
        """
        key = f"{loader_name}:{ip_address}" if ip_address else loader_name
        state = self._get_state(key)
        state.concurrent_count = max(0, state.concurrent_count - 1)

    def record_success(self, loader_name: str, ip_address: Optional[str] = None):
        """Record successful request (resets backoff).

        Args:
            loader_name: Name of the loader
            ip_address: Optional IP address
        """
        key = f"{loader_name}:{ip_address}" if ip_address else loader_name
        state = self._get_state(key)
        state.consecutive_failures = 0

    def record_failure(
        self,
        loader_name: str,
        ip_address: Optional[str] = None,
        trigger_backoff: bool = True,
    ):
        """Record failed request and optionally trigger backoff.

        Args:
            loader_name: Name of the loader
            ip_address: Optional IP address
            trigger_backoff: Whether to trigger exponential backoff
        """
        key = f"{loader_name}:{ip_address}" if ip_address else loader_name
        config = self._get_config(loader_name)
        state = self._get_state(key)

        state.consecutive_failures += 1

        if trigger_backoff:
            # Exponential backoff with jitter
            backoff_seconds = min(
                config.cooldown_seconds
                * (config.backoff_multiplier**state.consecutive_failures),
                config.max_backoff_seconds,
            )
            # Add jitter (±20%)
            jitter = random.uniform(0.8, 1.2)
            backoff_seconds *= jitter

            state.backoff_until = time.time() + backoff_seconds
            logger.warning(
                f"Backoff triggered for {key}: "
                f"{backoff_seconds:.1f}s (failure #{state.consecutive_failures})"
            )

    async def wait_for_slot(
        self, loader_name: str, ip_address: Optional[str] = None, timeout: float = 300
    ) -> bool:
        """Wait for a rate limit slot with timeout.

        Args:
            loader_name: Name of the loader
            ip_address: Optional IP address
            timeout: Maximum seconds to wait

        Returns:
            True if slot acquired, False if timed out
        """
        start = time.time()
        attempt = 0

        while time.time() - start < timeout:
            if await self.acquire(loader_name, ip_address):
                return True

            # Exponential backoff with jitter
            wait_time = min(2**attempt, 30) * random.uniform(0.8, 1.2)
            await asyncio.sleep(wait_time)
            attempt += 1

        return False

    async def check_document_limits(
        self, loader_name: str, document_size_mb: float, batch_size: int = 1
    ) -> bool:
        """Check if document size and batch size are within limits.

        Args:
            loader_name: Name of the loader
            document_size_mb: Size of document in MB
            batch_size: Number of documents in batch

        Returns:
            True if within limits, False otherwise
        """
        config = self._get_config(loader_name)

        if document_size_mb > config.max_document_size_mb:
            logger.warning(
                f"Document size {document_size_mb:.1f}MB exceeds "
                f"limit of {config.max_document_size_mb}MB for {loader_name}"
            )
            return False

        if batch_size > config.max_documents_per_batch:
            logger.warning(
                f"Batch size {batch_size} exceeds "
                f"limit of {config.max_documents_per_batch} for {loader_name}"
            )
            return False

        return True

    def get_stats(self, loader_name: str) -> Dict[str, Any]:
        """Get current rate limit stats for a loader.

        Args:
            loader_name: Name of the loader

        Returns:
            Dictionary with stats
        """
        state = self._get_state(loader_name)
        config = self._get_config(loader_name)

        now = time.time()
        minute_requests = len([ts for ts in state.request_timestamps if now - ts < 60])

        return {
            "loader": loader_name,
            "requests_last_minute": minute_requests,
            "limit_per_minute": config.requests_per_minute,
            "concurrent": state.concurrent_count,
            "max_concurrent": config.max_concurrent,
            "consecutive_failures": state.consecutive_failures,
            "backoff_active": state.backoff_until and now < state.backoff_until,
            "backoff_remaining": (
                max(0, state.backoff_until - now) if state.backoff_until else 0
            ),
        }


# Global instance
_rate_limiter = SmartRateLimiter()


def rate_limited(loader_name: str, timeout: float = 60):
    """Decorator to apply rate limiting to loader methods.

    Args:
        loader_name: Name of the loader (github, confluence, etc.)
        timeout: Maximum seconds to wait for a slot

    Example:
        @rate_limited("github", timeout=30)
        async def fetch_repo_data(repo_url: str):
            # This will be rate limited
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract IP if available from kwargs
            ip_address = kwargs.get("ip_address")

            if not await _rate_limiter.wait_for_slot(loader_name, ip_address, timeout):
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {loader_name} " f"(waited {timeout}s)"
                )

            try:
                result = await func(*args, **kwargs)
                _rate_limiter.record_success(loader_name, ip_address)
                return result
            except Exception as e:
                # Only trigger backoff for rate limit errors
                trigger_backoff = (
                    "rate limit" in str(e).lower()
                    or "429" in str(e)
                    or "too many requests" in str(e).lower()
                )
                _rate_limiter.record_failure(loader_name, ip_address, trigger_backoff)
                raise
            finally:
                _rate_limiter.release(loader_name, ip_address)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, run in event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(async_wrapper(*args, **kwargs))

        # Return appropriate wrapper using inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def get_rate_limiter() -> SmartRateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


# IP-based rate limiting for API endpoints
class IPRateLimiter:
    """IP-based rate limiting for API endpoints"""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._ip_states: Dict[str, RateLimitState] = defaultdict(RateLimitState)

    def is_allowed(self, ip_address: str) -> bool:
        """Check if IP is allowed to make a request.

        Args:
            ip_address: IP address to check

        Returns:
            True if allowed, False if rate limited
        """
        state = self._ip_states[ip_address]
        now = time.time()

        # Clean old timestamps
        state.request_timestamps = [
            ts for ts in state.request_timestamps if now - ts < 60
        ]

        # Check limit
        if len(state.request_timestamps) >= self.requests_per_minute:
            return False

        # Record request
        state.request_timestamps.append(now)
        return True

    def get_remaining(self, ip_address: str) -> int:
        """Get remaining requests for an IP.

        Args:
            ip_address: IP address

        Returns:
            Number of requests remaining in current minute
        """
        state = self._ip_states[ip_address]
        now = time.time()

        # Count recent requests
        recent = len([ts for ts in state.request_timestamps if now - ts < 60])

        return max(0, self.requests_per_minute - recent)


# Export public API
__all__ = [
    "SmartRateLimiter",
    "RateLimitConfig",
    "RateLimitExceeded",
    "IPRateLimiter",
    "rate_limited",
    "get_rate_limiter",
]
