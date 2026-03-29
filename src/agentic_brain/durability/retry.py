# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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
Sophisticated Retry Policies for durable activities.

This module provides production-grade retry policies with:
- Exponential backoff
- Configurable maximum attempts
- Non-retryable error classification
- Jitter for thundering herd prevention

Usage:
    from agentic_brain.durability.retry import RetryPolicy, with_retry

    policy = RetryPolicy(
        max_attempts=5,
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        non_retryable_errors=[ValueError, AuthenticationError],
    )

    @with_retry(policy)
    async def call_llm(prompt: str) -> str:
        return await llm.complete(prompt)
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import random
from dataclasses import dataclass, field
from datetime import timedelta
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class RetryPolicy:
    """
    Sophisticated retry policy for activities.

    Attributes:
        max_attempts: Maximum number of attempts (including first)
        initial_interval: Delay before first retry
        backoff_coefficient: Multiplier for each subsequent retry
        max_interval: Maximum delay between retries
        jitter_factor: Random jitter (0.0-1.0) to prevent thundering herd
        non_retryable_errors: Exception types that should not be retried
        retryable_errors: If set, ONLY these errors are retried
    """

    max_attempts: int = 3
    initial_interval: timedelta = timedelta(seconds=1)
    backoff_coefficient: float = 2.0
    max_interval: timedelta = timedelta(minutes=1)
    jitter_factor: float = 0.1
    non_retryable_errors: list[type[Exception]] = field(default_factory=list)
    retryable_errors: list[type[Exception]] | None = None

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for a retry attempt.

        Args:
            attempt: Attempt number (1-based, 1 = first retry)

        Returns:
            Delay in seconds
        """
        # Calculate base delay with exponential backoff
        base_delay = self.initial_interval.total_seconds()
        delay = base_delay * (self.backoff_coefficient ** (attempt - 1))

        # Apply max interval cap
        delay = min(delay, self.max_interval.total_seconds())

        # Apply jitter
        if self.jitter_factor > 0:
            jitter = delay * self.jitter_factor * random.random()
            delay = delay + jitter

        return delay

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Check if an error should be retried.

        Args:
            error: The exception that occurred
            attempt: Current attempt number

        Returns:
            True if should retry
        """
        # Check max attempts
        if attempt >= self.max_attempts:
            return False

        # Check non-retryable errors
        for error_type in self.non_retryable_errors:
            if isinstance(error, error_type):
                return False

        # Check retryable errors (if specified)
        if self.retryable_errors is not None:
            for error_type in self.retryable_errors:
                if isinstance(error, error_type):
                    return True
            return False  # Not in retryable list

        # Default: retry all errors
        return True


# =============================================================================
# Common Retry Policies
# =============================================================================

# Default policy for most activities
DEFAULT_POLICY = RetryPolicy(
    max_attempts=3,
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    max_interval=timedelta(minutes=1),
)

# Aggressive retry for transient failures
AGGRESSIVE_POLICY = RetryPolicy(
    max_attempts=10,
    initial_interval=timedelta(milliseconds=100),
    backoff_coefficient=1.5,
    max_interval=timedelta(seconds=30),
    jitter_factor=0.2,
)

# Conservative retry for expensive operations
CONSERVATIVE_POLICY = RetryPolicy(
    max_attempts=2,
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=3.0,
    max_interval=timedelta(minutes=5),
)

# LLM-specific policy (handles rate limits, timeouts)
LLM_RETRY_POLICY = RetryPolicy(
    max_attempts=5,
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    max_interval=timedelta(minutes=2),
    jitter_factor=0.15,
    # Don't retry auth errors or invalid requests
    non_retryable_errors=[
        ValueError,  # Invalid parameters
    ],
)

# Database retry policy
DB_RETRY_POLICY = RetryPolicy(
    max_attempts=5,
    initial_interval=timedelta(milliseconds=500),
    backoff_coefficient=2.0,
    max_interval=timedelta(seconds=30),
    jitter_factor=0.1,
)

# API call retry policy
API_RETRY_POLICY = RetryPolicy(
    max_attempts=4,
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.5,
    max_interval=timedelta(minutes=1),
    jitter_factor=0.2,
)


# =============================================================================
# Retry Decorator
# =============================================================================


def _sleep_safe(delay: float) -> None:
    """
    Sleep for the specified delay, checking if we're in an async context.

    If called from an async context, warns and uses a small busy-wait instead
    to avoid blocking the event loop catastrophically. This is a fallback for
    sync functions that might be called from async code.

    Args:
        delay: Delay in seconds
    """
    import time

    try:
        asyncio.get_running_loop()
        # We're in an async context - using time.sleep would block the loop!
        logger.warning(
            f"Sync function called from async context with sleep({delay:.2f}s). "
            "This blocks the event loop. Consider using the async version instead."
        )
        # Do a minimal sleep to avoid busy-waiting
        time.sleep(min(0.01, delay))
    except RuntimeError:
        # No running loop, sync context is fine
        time.sleep(delay)


def with_retry(
    policy: RetryPolicy | None = None,
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator that adds retry logic to a function.

    Args:
        policy: Retry policy to use (default: DEFAULT_POLICY)
        on_retry: Optional callback called before each retry

    Usage:
        @with_retry(LLM_RETRY_POLICY)
        async def call_openai(prompt: str) -> str:
            return await openai.complete(prompt)
    """
    policy = policy or DEFAULT_POLICY

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_error = None

            for attempt in range(1, policy.max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)

                except Exception as e:
                    last_error = e

                    if not policy.should_retry(e, attempt):
                        logger.debug(f"Error not retryable: {type(e).__name__}")
                        raise

                    if attempt < policy.max_attempts:
                        delay = policy.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt}/{policy.max_attempts} failed: {e}. "
                            f"Retrying in {delay:.2f}s"
                        )

                        if on_retry:
                            on_retry(e, attempt)

                        await asyncio.sleep(delay)

            raise last_error or RuntimeError("Retry failed")

        @wraps(fn)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_error = None

            for attempt in range(1, policy.max_attempts + 1):
                try:
                    return fn(*args, **kwargs)

                except Exception as e:
                    last_error = e

                    if not policy.should_retry(e, attempt):
                        raise

                    if attempt < policy.max_attempts:
                        delay = policy.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt}/{policy.max_attempts} failed: {e}. "
                            f"Retrying in {delay:.2f}s"
                        )

                        if on_retry:
                            on_retry(e, attempt)

                        _sleep_safe(delay)

            raise last_error or RuntimeError("Retry failed")

        if inspect.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# Retry Context Manager
# =============================================================================


class RetryContext:
    """
    Context manager for retry logic.

    Usage:
        async with RetryContext(policy) as ctx:
            while ctx.should_continue:
                try:
                    result = await do_something()
                    break
                except Exception as e:
                    await ctx.handle_error(e)
    """

    def __init__(self, policy: RetryPolicy | None = None):
        self.policy = policy or DEFAULT_POLICY
        self.attempt = 0
        self.last_error: Exception | None = None
        self._should_continue = True

    @property
    def should_continue(self) -> bool:
        """Check if should continue retrying"""
        return self._should_continue and self.attempt < self.policy.max_attempts

    async def handle_error(self, error: Exception) -> None:
        """
        Handle an error and prepare for retry.

        Raises:
            The error if it should not be retried
        """
        self.last_error = error
        self.attempt += 1

        if not self.policy.should_retry(error, self.attempt):
            self._should_continue = False
            raise error

        if self.attempt >= self.policy.max_attempts:
            self._should_continue = False
            raise error

        delay = self.policy.get_delay(self.attempt)
        logger.warning(
            f"Attempt {self.attempt}/{self.policy.max_attempts} failed: {error}. "
            f"Retrying in {delay:.2f}s"
        )
        await asyncio.sleep(delay)

    async def __aenter__(self) -> RetryContext:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# =============================================================================
# Retry Metrics
# =============================================================================


@dataclass
class RetryMetrics:
    """Metrics for retry operations"""

    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    retried_operations: int = 0
    total_retry_delay_seconds: float = 0.0
    errors_by_type: dict[str, int] = field(default_factory=dict)

    def record_attempt(self, success: bool, error: Exception | None = None) -> None:
        """Record an attempt"""
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1
            if error:
                error_type = type(error).__name__
                self.errors_by_type[error_type] = (
                    self.errors_by_type.get(error_type, 0) + 1
                )

    def record_retry(self, delay: float) -> None:
        """Record a retry"""
        self.retried_operations += 1
        self.total_retry_delay_seconds += delay

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_attempts == 0:
            return 0.0
        return self.successful_attempts / self.total_attempts

    @property
    def average_retry_delay(self) -> float:
        """Calculate average retry delay"""
        if self.retried_operations == 0:
            return 0.0
        return self.total_retry_delay_seconds / self.retried_operations


# Global metrics
_global_metrics = RetryMetrics()


def get_retry_metrics() -> RetryMetrics:
    """Get global retry metrics"""
    return _global_metrics


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Core
    "RetryPolicy",
    "with_retry",
    "RetryContext",
    "RetryMetrics",
    "get_retry_metrics",
    # Common policies
    "DEFAULT_POLICY",
    "AGGRESSIVE_POLICY",
    "CONSERVATIVE_POLICY",
    "LLM_RETRY_POLICY",
    "DB_RETRY_POLICY",
    "API_RETRY_POLICY",
]
