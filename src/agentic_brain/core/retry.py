# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Retry, timeout, and circuit-breaker helpers."""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import inspect
import random
import signal
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from .exceptions import AgenticBrainError, RateLimitError, ValidationError

T = TypeVar("T")


def is_retryable_exception(exc: BaseException) -> bool:
    """Return True when an exception is safe to retry."""
    if isinstance(exc, ValidationError):
        return False
    if isinstance(exc, (RateLimitError,)):
        return True
    if isinstance(exc, AgenticBrainError):
        return exc.retryable
    return isinstance(
        exc,
        (
            asyncio.TimeoutError,
            ConnectionError,
            TimeoutError,
            OSError,
        ),
    )


def retry_with_backoff(
    func: Callable[..., T] | None = None,
    *,
    attempts: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    max_delay: float = 30.0,
    jitter: float = 0.0,
    retry_if: Callable[[BaseException], bool] | None = None,
) -> Callable[..., T]:
    """Retry a callable with exponential backoff."""

    def decorator(callable_obj: Callable[..., T]) -> Callable[..., T]:
        predicate = retry_if or is_retryable_exception

        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return await callable_obj(*args, **kwargs)  # type: ignore[misc]
                except BaseException as exc:  # pragma: no cover - exercised in tests
                    last_exc = exc
                    if attempt >= attempts or not predicate(exc):
                        raise
                    sleep_for = min(max_delay, delay)
                    if jitter:
                        sleep_for *= random.uniform(1 - jitter, 1 + jitter)
                    await asyncio.sleep(max(0.0, sleep_for))
                    delay *= backoff_factor
            raise last_exc  # pragma: no cover

        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return callable_obj(*args, **kwargs)
                except BaseException as exc:
                    last_exc = exc
                    if attempt >= attempts or not predicate(exc):
                        raise
                    sleep_for = min(max_delay, delay)
                    if jitter:
                        sleep_for *= random.uniform(1 - jitter, 1 + jitter)
                    time.sleep(max(0.0, sleep_for))
                    delay *= backoff_factor
            raise last_exc  # pragma: no cover

        wrapper: Callable[..., T]
        if inspect.iscoroutinefunction(callable_obj):
            wrapper = functools.wraps(callable_obj)(async_wrapper)  # type: ignore[assignment]
        else:
            wrapper = functools.wraps(callable_obj)(sync_wrapper)  # type: ignore[assignment]
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def circuit_breaker(
    func: Callable[..., T] | None = None,
    *,
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0,
) -> Callable[..., T]:
    """Open a circuit after repeated failures and recover after a timeout."""

    def decorator(callable_obj: Callable[..., T]) -> Callable[..., T]:
        lock = threading.RLock()
        state = {
            "failures": 0,
            "opened_at": 0.0,
            "half_open": False,
        }

        def _before_call() -> None:
            with lock:
                if state["failures"] < failure_threshold:
                    return
                elapsed = time.monotonic() - state["opened_at"]
                if elapsed < recovery_timeout:
                    raise RuntimeError(
                        f"Circuit open for {callable_obj.__name__}; retry after "
                        f"{recovery_timeout - elapsed:.1f}s"
                    )
                state["half_open"] = True

        def _record_success() -> None:
            with lock:
                state["failures"] = 0
                state["opened_at"] = 0.0
                state["half_open"] = False

        def _record_failure(exc: BaseException) -> None:
            if not is_retryable_exception(exc):
                raise exc
            with lock:
                state["failures"] += 1
                state["opened_at"] = time.monotonic()
                state["half_open"] = False
                if state["failures"] >= failure_threshold:
                    raise RuntimeError(
                        f"Circuit opened for {callable_obj.__name__}"
                    ) from exc

        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            _before_call()
            try:
                result = await callable_obj(*args, **kwargs)  # type: ignore[misc]
            except BaseException as exc:
                _record_failure(exc)
                raise
            else:
                _record_success()
                return result

        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            _before_call()
            try:
                result = callable_obj(*args, **kwargs)
            except BaseException as exc:
                _record_failure(exc)
                raise
            else:
                _record_success()
                return result

        wrapper: Callable[..., T]
        if inspect.iscoroutinefunction(callable_obj):
            wrapper = functools.wraps(callable_obj)(async_wrapper)  # type: ignore[assignment]
        else:
            wrapper = functools.wraps(callable_obj)(sync_wrapper)  # type: ignore[assignment]
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def timeout(
    seconds: float,
    *,
    message: str | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Raise TimeoutError if a function takes too long."""

    def decorator(callable_obj: Callable[..., T]) -> Callable[..., T]:
        timeout_message = (
            message or f"{callable_obj.__name__} timed out after {seconds}s"
        )

        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            return await asyncio.wait_for(callable_obj(*args, **kwargs), timeout=seconds)  # type: ignore[misc]

        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            if (
                hasattr(signal, "SIGALRM")
                and threading.current_thread() is threading.main_thread()
            ):

                def _raise_timeout(*_: Any) -> None:
                    raise TimeoutError(timeout_message)

                previous_handler = signal.getsignal(signal.SIGALRM)
                signal.signal(signal.SIGALRM, _raise_timeout)
                signal.setitimer(signal.ITIMER_REAL, seconds)
                try:
                    return callable_obj(*args, **kwargs)
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, previous_handler)

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(callable_obj, *args, **kwargs)
            try:
                return future.result(timeout=seconds)
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        wrapper: Callable[..., T]
        if inspect.iscoroutinefunction(callable_obj):

            async def wrapped_async(*args: Any, **kwargs: Any) -> T:
                try:
                    return await async_wrapper(*args, **kwargs)
                except asyncio.TimeoutError as exc:
                    raise TimeoutError(timeout_message) from exc

            wrapper = functools.wraps(callable_obj)(wrapped_async)  # type: ignore[assignment]
        else:

            def wrapped_sync(*args: Any, **kwargs: Any) -> T:
                try:
                    return sync_wrapper(*args, **kwargs)
                except concurrent.futures.TimeoutError as exc:
                    raise TimeoutError(timeout_message) from exc

            wrapper = functools.wraps(callable_obj)(wrapped_sync)  # type: ignore[assignment]
        return wrapper

    return decorator


__all__ = [
    "retry_with_backoff",
    "circuit_breaker",
    "timeout",
    "is_retryable_exception",
]
