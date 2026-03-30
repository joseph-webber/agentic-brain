# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain contributors

"""
Error recovery module for agentic-brain autonomous agents.

Provides retry logic with exponential backoff, jitter, and checkpoint-based recovery.
Supports both synchronous and asynchronous operations.

Example:
    >>> from agentic_brain.bots import RecoveryManager, RetryConfig, retry
    >>>
    >>> # Use the retry decorator
    >>> @retry(config=RetryConfig(max_attempts=5))
    >>> def fetch_data():
    ...     return requests.get("https://api.example.com/data")
    >>>
    >>> # Or use RecoveryManager for checkpoints
    >>> recovery = RecoveryManager("my_agent")
    >>> recovery.checkpoint("step_1", {"items": data})
    >>> previous = recovery.recover("step_1")
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import random
import re
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

try:
    import aiofiles

    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False
    aiofiles = None  # type: ignore

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])
AsyncF = TypeVar("AsyncF", bound=Callable[..., Awaitable[Any]])
_IDENTIFIER_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


def _sleep_safe(delay: float) -> None:
    """
    Sleep for the specified delay, checking if we're in an async context.

    If called from an async context, warns and uses a small busy-wait instead
    to avoid blocking the event loop catastrophically. This is a fallback for
    sync functions that might be called from async code.

    Args:
        delay: Delay in seconds
    """
    try:
        asyncio.get_running_loop()
        # We're in an async context - using time.sleep would block the loop!
        logger.warning(
            f"Sync function called from async context with sleep({delay:.2f}s). "
            "This blocks the event loop. Consider using the async version instead."
        )
        return
    except RuntimeError:
        # No running loop, sync context is fine
        time.sleep(delay)


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        max_delay: Maximum delay cap in seconds (default: 60.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        jitter: Whether to add randomness to delays to prevent thundering herd (default: True)

    Example:
        >>> config = RetryConfig(max_attempts=5, initial_delay=0.5)
        >>> @retry(config=config)
        >>> def unstable_function():
        ...     return api_call()
    """

    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay < 0:
            raise ValueError("initial_delay must be non-negative")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be >= initial_delay")
        if self.exponential_base < 1:
            raise ValueError("exponential_base must be >= 1")

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt number.

        Args:
            attempt: Zero-indexed attempt number

        Returns:
            Delay in seconds before next attempt
        """
        delay = self.initial_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            jitter_amount = delay * 0.1
            delay = delay + random.uniform(-jitter_amount, jitter_amount)

        return max(0, delay)


def retry(
    func: F | None = None,
    *,
    config: RetryConfig | None = None,
    on_exceptions: tuple[type[Exception], ...] = (Exception,),
    on_result: Callable[[Any], bool] | None = None,
) -> Callable[[F], F] | F:
    """
    Decorator for retrying functions with exponential backoff.

    Supports both sync and async functions automatically.

    Args:
        func: Function to decorate (when used without parentheses)
        config: RetryConfig instance. Defaults to RetryConfig()
        on_exceptions: Tuple of exception types to trigger retries (default: (Exception,))
        on_result: Optional callable that returns True if result should trigger retry

    Returns:
        Decorated function that retries on failures

    Raises:
        Last exception encountered if all retries are exhausted

    Example:
        >>> # Simple usage with defaults
        >>> @retry()
        >>> def fetch_data():
        ...     return requests.get("https://api.example.com/data")
        >>>
        >>> # With custom config
        >>> @retry(config=RetryConfig(max_attempts=5, initial_delay=0.5))
        >>> def unstable_operation():
        ...     return perform_operation()
        >>>
        >>> # Async function
        >>> @retry(on_exceptions=(ConnectionError,))
        >>> async def async_fetch():
        ...     return await client.get("/data")
    """
    if config is None:
        config = RetryConfig()

    def decorator(f: F) -> F:
        if inspect.iscoroutinefunction(f):

            @wraps(f)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exception: Exception | None = None
                last_result: Any = None

                for attempt in range(config.max_attempts):
                    try:
                        result = await f(*args, **kwargs)

                        if on_result is not None and on_result(result):
                            last_result = result
                            if attempt < config.max_attempts - 1:
                                delay = config.calculate_delay(attempt)
                                logger.info(
                                    f"Retry attempt {attempt + 1}/{config.max_attempts} "
                                    f"for {f.__name__} (result condition met). "
                                    f"Waiting {delay:.2f}s..."
                                )
                                await asyncio.sleep(delay)
                            continue

                        return result

                    except on_exceptions as e:
                        last_exception = e
                        if attempt < config.max_attempts - 1:
                            delay = config.calculate_delay(attempt)
                            logger.warning(
                                f"Retry attempt {attempt + 1}/{config.max_attempts} "
                                f"for {f.__name__}: {type(e).__name__}: {str(e)[:100]}. "
                                f"Waiting {delay:.2f}s..."
                            )
                            await asyncio.sleep(delay)
                        else:
                            logger.error(
                                f"All {config.max_attempts} retry attempts exhausted for {f.__name__}. "
                                f"Last exception: {type(e).__name__}: {str(e)}"
                            )

                if last_exception is not None:
                    raise last_exception
                if on_result is not None:
                    return last_result
                raise RuntimeError(
                    f"All {config.max_attempts} attempts exhausted for {f.__name__}"
                )

            return async_wrapper  # type: ignore
        else:

            @wraps(f)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exception: Exception | None = None
                last_result: Any = None

                for attempt in range(config.max_attempts):
                    try:
                        result = f(*args, **kwargs)

                        if on_result is not None and on_result(result):
                            last_result = result
                            if attempt < config.max_attempts - 1:
                                delay = config.calculate_delay(attempt)
                                logger.info(
                                    f"Retry attempt {attempt + 1}/{config.max_attempts} "
                                    f"for {f.__name__} (result condition met). "
                                    f"Waiting {delay:.2f}s..."
                                )
                                _sleep_safe(delay)
                            continue

                        return result

                    except on_exceptions as e:
                        last_exception = e
                        if attempt < config.max_attempts - 1:
                            delay = config.calculate_delay(attempt)
                            logger.warning(
                                f"Retry attempt {attempt + 1}/{config.max_attempts} "
                                f"for {f.__name__}: {type(e).__name__}: {str(e)[:100]}. "
                                f"Waiting {delay:.2f}s..."
                            )
                            _sleep_safe(delay)
                        else:
                            logger.error(
                                f"All {config.max_attempts} retry attempts exhausted for {f.__name__}. "
                                f"Last exception: {type(e).__name__}: {str(e)}"
                            )

                if last_exception is not None:
                    raise last_exception
                if on_result is not None:
                    return last_result
                raise RuntimeError(
                    f"All {config.max_attempts} attempts exhausted for {f.__name__}"
                )

            return sync_wrapper  # type: ignore

    if func is not None:
        return decorator(func)
    return decorator


class RecoveryManager:
    """
    Manages error recovery with checkpoints and automatic retries.

    Handles checkpoint-based recovery for autonomous operations, allowing
    agents to resume from known-good states after failures. Supports both
    synchronous and asynchronous checkpoint operations.

    Attributes:
        agent_id: Unique identifier for the agent instance
        checkpoint_dir: Directory where checkpoints are stored

    Example:
        >>> recovery = RecoveryManager("competitor_intel")
        >>>
        >>> # Run risky function with retries
        >>> try:
        ...     result = recovery.attempt(fetch_data, arg1, arg2)
        ... except Exception as e:
        ...     logger.error(f"Failed: {e}")
        >>>
        >>> # Save state for recovery
        >>> recovery.checkpoint("data_fetch", {"items": result})
        >>>
        >>> # Resume from checkpoint on next run
        >>> previous_data = recovery.recover("data_fetch")
        >>> if previous_data:
        ...     logger.info(f"Resuming with {len(previous_data['items'])} items")
    """

    def __init__(
        self,
        agent_id: str,
        logger: logging.Logger | None = None,
        checkpoint_root: str | Path | None = None,
    ) -> None:
        """
        Initialize RecoveryManager.

        Args:
            agent_id: Unique identifier for the agent instance
            logger: Optional logger instance (uses module logger if None)
            checkpoint_root: Optional root directory for checkpoints.
                Defaults to AGENTIC_BRAIN_CHECKPOINT_DIR or ~/.agentic-brain/checkpoints.
        """
        self.agent_id = agent_id
        self.bot_id = agent_id
        self.logger = logger or logging.getLogger(__name__)

        configured_root = checkpoint_root or os.getenv("AGENTIC_BRAIN_CHECKPOINT_DIR")
        if configured_root is None:
            base_dir = Path.home() / ".agentic-brain" / "checkpoints"
        else:
            base_dir = Path(configured_root).expanduser()

        safe_agent_id = _IDENTIFIER_PATTERN.sub("_", agent_id).strip("._") or "agent"
        self.checkpoint_dir = base_dir / safe_agent_id
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def attempt(
        self,
        func: Callable[..., Any],
        *args: Any,
        config: RetryConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a function with automatic retries.

        Args:
            func: Function to execute
            *args: Positional arguments to pass to func
            config: Optional RetryConfig. Uses default if None.
            **kwargs: Keyword arguments to pass to func

        Returns:
            Result from func

        Raises:
            Last exception if all retries are exhausted
        """
        if config is None:
            config = RetryConfig()

        last_exception: Exception | None = None

        for attempt in range(config.max_attempts):
            try:
                self.logger.debug(
                    f"Attempting {func.__name__} (attempt {attempt + 1}/{config.max_attempts})"
                )
                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                if attempt < config.max_attempts - 1:
                    delay = config.calculate_delay(attempt)
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: "
                        f"{type(e).__name__}: {str(e)[:100]}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    _sleep_safe(delay)
                else:
                    self.logger.error(
                        f"All {config.max_attempts} attempts failed for {func.__name__}. "
                        f"Last error: {type(e).__name__}: {str(e)}"
                    )

        if last_exception is not None:
            raise last_exception
        return None

    async def attempt_async(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        config: RetryConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Execute an async function with automatic retries.

        Args:
            func: Async function to execute
            *args: Positional arguments to pass to func
            config: Optional RetryConfig. Uses default if None.
            **kwargs: Keyword arguments to pass to func

        Returns:
            Result from func

        Raises:
            Last exception if all retries are exhausted
        """
        if config is None:
            config = RetryConfig()

        last_exception: Exception | None = None

        for attempt in range(config.max_attempts):
            try:
                self.logger.debug(
                    f"Attempting {func.__name__} (attempt {attempt + 1}/{config.max_attempts})"
                )
                return await func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                if attempt < config.max_attempts - 1:
                    delay = config.calculate_delay(attempt)
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: "
                        f"{type(e).__name__}: {str(e)[:100]}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"All {config.max_attempts} attempts failed for {func.__name__}. "
                        f"Last error: {type(e).__name__}: {str(e)}"
                    )

        if last_exception is not None:
            raise last_exception
        return None

    def checkpoint(self, name: str, data: dict[str, Any]) -> None:
        """
        Save a checkpoint for recovery.

        Args:
            name: Checkpoint name (used as filename)
            data: Data to save in checkpoint
        """
        checkpoint_path = self.checkpoint_dir / f"{name}.json"

        checkpoint_data = {
            "name": name,
            "timestamp": time.time(),
            "data": data,
        }

        try:
            temp_path = checkpoint_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(checkpoint_data, f, indent=2, default=str)
            temp_path.replace(checkpoint_path)

            self.logger.debug(f"Checkpoint '{name}' saved to {checkpoint_path}")
        except OSError as e:
            self.logger.error(f"Failed to save checkpoint '{name}': {e}")
            raise

    async def checkpoint_async(self, name: str, data: dict[str, Any]) -> None:
        """
        Save a checkpoint asynchronously for recovery.

        Args:
            name: Checkpoint name (used as filename)
            data: Data to save in checkpoint

        Note:
            Falls back to sync method if aiofiles not installed.
        """
        if not AIOFILES_AVAILABLE:
            self.checkpoint(name, data)
            return

        checkpoint_path = self.checkpoint_dir / f"{name}.json"

        checkpoint_data = {
            "name": name,
            "timestamp": time.time(),
            "data": data,
        }

        try:
            temp_path = checkpoint_path.with_suffix(".tmp")
            async with aiofiles.open(temp_path, "w") as f:
                await f.write(json.dumps(checkpoint_data, indent=2, default=str))
            temp_path.replace(checkpoint_path)

            self.logger.debug(f"Checkpoint '{name}' saved to {checkpoint_path}")
        except OSError as e:
            self.logger.error(f"Failed to save checkpoint '{name}': {e}")
            raise

    def recover(self, name: str) -> dict[str, Any] | None:
        """
        Load a checkpoint for recovery.

        Args:
            name: Checkpoint name to recover

        Returns:
            Checkpoint data if found, None otherwise
        """
        checkpoint_path = self.checkpoint_dir / f"{name}.json"

        if not checkpoint_path.exists():
            self.logger.debug(f"No checkpoint found for '{name}'")
            return None

        try:
            with open(checkpoint_path) as f:
                checkpoint_data = json.load(f)

            self.logger.info(
                f"Recovered checkpoint '{name}' "
                f"(saved {time.time() - checkpoint_data['timestamp']:.1f}s ago)"
            )
            return checkpoint_data.get("data")
        except (OSError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load checkpoint '{name}': {e}")
            return None

    async def recover_async(self, name: str) -> dict[str, Any] | None:
        """
        Load a checkpoint asynchronously for recovery.

        Args:
            name: Checkpoint name to recover

        Returns:
            Checkpoint data if found, None otherwise

        Note:
            Falls back to sync method if aiofiles not installed.
        """
        if not AIOFILES_AVAILABLE:
            return self.recover(name)

        checkpoint_path = self.checkpoint_dir / f"{name}.json"

        if not checkpoint_path.exists():
            self.logger.debug(f"No checkpoint found for '{name}'")
            return None

        try:
            async with aiofiles.open(checkpoint_path, "r") as f:
                content = await f.read()
            checkpoint_data = json.loads(content)

            self.logger.info(
                f"Recovered checkpoint '{name}' "
                f"(saved {time.time() - checkpoint_data['timestamp']:.1f}s ago)"
            )
            return checkpoint_data.get("data")
        except (OSError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load checkpoint '{name}': {e}")
            return None

    def clear_checkpoints(self) -> None:
        """
        Delete all checkpoints for this agent.

        Useful for cleanup or forcing a fresh start.
        """
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                checkpoint_file.unlink()
            self.logger.info(f"Cleared all checkpoints from {self.checkpoint_dir}")
        except OSError as e:
            self.logger.error(f"Failed to clear checkpoints: {e}")
            raise

    def list_checkpoints(self) -> dict[str, float]:
        """
        List all available checkpoints with their timestamps.

        Returns:
            Dict mapping checkpoint names to timestamps
        """
        checkpoints: dict[str, float] = {}
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                try:
                    with open(checkpoint_file) as f:
                        data = json.load(f)
                    checkpoints[checkpoint_file.stem] = data.get("timestamp", 0)
                except (OSError, json.JSONDecodeError):
                    pass
        except OSError as e:
            self.logger.error(f"Failed to list checkpoints: {e}")

        return checkpoints


__all__ = [
    "RetryConfig",
    "retry",
    "RecoveryManager",
]
