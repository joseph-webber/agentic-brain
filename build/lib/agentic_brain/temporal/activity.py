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
Temporal activity compatibility module.

Provides decorators and utilities matching temporalio.activity exactly:
- @activity.defn - Define an activity
- activity.heartbeat() - Send heartbeat
- activity.info() - Get activity info
- activity.is_cancelled() - Check if cancelled
- activity.wait_for_cancelled() - Wait for cancellation
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from ..durability import (
    HeartbeatContext,
    HeartbeatMonitor,
)
from ..durability import (
    activity as native_activity,
)

F = TypeVar("F", bound=Callable[..., Any])


# ============================================================================
# Activity Info (matches temporalio.activity.Info)
# ============================================================================


@dataclass
class Info:
    """Information about the running activity."""

    activity_id: str
    activity_type: str
    task_queue: str
    workflow_id: str
    workflow_type: str
    workflow_namespace: str = "default"
    workflow_run_id: str = ""
    attempt: int = 1
    task_token: bytes = b""  # Must have default for Temporal compatibility
    scheduled_time: Optional[datetime] = None
    current_attempt_scheduled_time: Optional[datetime] = None
    started_time: Optional[datetime] = None
    schedule_to_close_timeout: Optional[timedelta] = None
    start_to_close_timeout: Optional[timedelta] = None
    heartbeat_timeout: Optional[timedelta] = None
    heartbeat_details: Optional[Any] = None
    is_local: bool = False


# ============================================================================
# Activity Context (thread-local storage)
# ============================================================================


@dataclass
class _ActivityContext:
    """Internal activity context."""

    activity_id: str
    activity_type: str
    workflow_id: str
    task_queue: str = "default"
    attempt: int = 1
    heartbeat_details: Any = None
    cancelled: bool = False
    _cancel_event: Optional[asyncio.Event] = None


_current_activity: Optional[_ActivityContext] = None


def _get_current_activity() -> _ActivityContext:
    """Get the currently executing activity context."""
    if _current_activity is None:
        raise RuntimeError(
            "No activity context. This function must be called from within an activity."
        )
    return _current_activity


def _set_current_activity(ctx: Optional[_ActivityContext]) -> None:
    """Set the currently executing activity context."""
    global _current_activity
    _current_activity = ctx


# ============================================================================
# Decorators (matching temporalio.activity decorators)
# ============================================================================


def defn(
    fn: Optional[F] = None,
    *,
    name: Optional[str] = None,
    no_thread_cancel_exception: bool = False,
    executor: Optional[str] = None,
) -> F:
    """
    Decorator to define an activity.

    Matches temporalio.activity.defn exactly.

    Usage:
        @activity.defn
        async def my_activity(name: str) -> str:
            return f"Hello, {name}!"

        @activity.defn(name="custom-name")
        def sync_activity(data: bytes) -> int:
            return len(data)

    Args:
        fn: The activity function
        name: Optional activity name (defaults to function name)
        no_thread_cancel_exception: Don't raise on thread cancel
        executor: Executor type ("thread_pool", "process_pool", None for async)

    Returns:
        Decorated activity function
    """

    def decorator(fn: F) -> F:
        activity_name = name or fn.__name__

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            # Create activity context
            ctx = _ActivityContext(
                activity_id=f"act-{activity_name}-{id(args)}",
                activity_type=activity_name,
                workflow_id=kwargs.pop("_workflow_id", "unknown"),
                _cancel_event=asyncio.Event(),
            )
            _set_current_activity(ctx)

            try:
                if inspect.iscoroutinefunction(fn):
                    return await fn(*args, **kwargs)
                else:
                    # Run sync function in executor
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
            finally:
                _set_current_activity(None)

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            # For sync activities called directly
            ctx = _ActivityContext(
                activity_id=f"act-{activity_name}-{id(args)}",
                activity_type=activity_name,
                workflow_id=kwargs.pop("_workflow_id", "unknown"),
            )
            _set_current_activity(ctx)

            try:
                return fn(*args, **kwargs)
            finally:
                _set_current_activity(None)

        # Choose wrapper based on function type
        wrapper = async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper

        # Store metadata
        wrapper._temporal_activity_name = activity_name
        wrapper._temporal_executor = executor
        wrapper._temporal_no_thread_cancel = no_thread_cancel_exception

        # Also apply native decorator for our system
        return native_activity(name=activity_name)(wrapper)

    if fn is not None:
        return decorator(fn)
    return decorator


# ============================================================================
# Activity Functions (matching temporalio.activity functions)
# ============================================================================


def heartbeat(*details: Any) -> None:
    """
    Send a heartbeat from the activity.

    Matches temporalio.activity.heartbeat exactly.

    Usage:
        for i, item in enumerate(items):
            activity.heartbeat(i, len(items))
            process(item)

    Args:
        *details: Optional details to include with heartbeat
    """
    ctx = _get_current_activity()
    ctx.heartbeat_details = details

    # Use our heartbeat system
    monitor = HeartbeatMonitor()
    HeartbeatContext(
        activity_id=ctx.activity_id,
        workflow_id=ctx.workflow_id,
    )

    # Record heartbeat (non-blocking)
    try:
        monitor.record_heartbeat(
            activity_id=ctx.activity_id,
            details=details,
        )
    except Exception:
        # Heartbeat failures shouldn't crash the activity
        pass


async def heartbeat_async(*details: Any) -> None:
    """
    Async version of heartbeat.
    """
    heartbeat(*details)


def info() -> Info:
    """
    Get information about the current activity.

    Matches temporalio.activity.info exactly.
    """
    ctx = _get_current_activity()

    return Info(
        activity_id=ctx.activity_id,
        activity_type=ctx.activity_type,
        task_queue=ctx.task_queue,
        workflow_id=ctx.workflow_id,
        workflow_type="unknown",  # Would need workflow context
        attempt=ctx.attempt,
        heartbeat_details=ctx.heartbeat_details,
    )


def is_cancelled() -> bool:
    """
    Check if the activity has been cancelled.

    Matches temporalio.activity.is_cancelled exactly.

    Usage:
        for item in items:
            if activity.is_cancelled():
                raise asyncio.CancelledError()
            process(item)
    """
    ctx = _get_current_activity()
    return ctx.cancelled


async def wait_for_cancelled() -> None:
    """
    Wait until the activity is cancelled.

    Matches temporalio.activity.wait_for_cancelled exactly.

    Usage:
        try:
            await activity.wait_for_cancelled()
        except asyncio.CancelledError:
            # Cleanup
            pass
    """
    ctx = _get_current_activity()

    if ctx._cancel_event is None:
        ctx._cancel_event = asyncio.Event()

    await ctx._cancel_event.wait()


def raise_complete_async() -> None:
    """
    Indicate activity will complete asynchronously.

    Matches temporalio.activity.raise_complete_async exactly.

    Usage:
        @activity.defn
        async def send_email(to: str) -> None:
            token = activity.info().task_token
            send_email_with_callback(to, callback_token=token)
            activity.raise_complete_async()
    """
    from ..durability import AsyncCompletionError

    ctx = _get_current_activity()

    # This raises a special exception that signals async completion
    raise AsyncCompletionError(f"Activity {ctx.activity_id} completing asynchronously")


# ============================================================================
# Cancellation
# ============================================================================


def _cancel_activity(activity_id: str) -> None:
    """Cancel an activity (internal use)."""
    ctx = _get_current_activity()

    if ctx.activity_id == activity_id:
        ctx.cancelled = True
        if ctx._cancel_event:
            ctx._cancel_event.set()


# ============================================================================
# Activity Token (for async completion)
# ============================================================================


@dataclass
class TaskToken:
    """
    Task token for async activity completion.

    Matches the concept from temporalio.
    """

    token: bytes
    activity_id: str
    workflow_id: str

    def encode(self) -> bytes:
        """Encode token to bytes."""
        return self.token


def get_task_token() -> TaskToken:
    """
    Get the task token for async completion.

    Usage:
        token = activity.get_task_token()
        # Pass token to external system
        external_service.process(data, callback_token=token.encode())
    """
    ctx = _get_current_activity()

    # Generate token
    import hashlib
    import time

    token_data = f"{ctx.activity_id}:{ctx.workflow_id}:{time.time()}"
    token_bytes = hashlib.sha256(token_data.encode()).digest()

    return TaskToken(
        token=token_bytes,
        activity_id=ctx.activity_id,
        workflow_id=ctx.workflow_id,
    )


# ============================================================================
# Module-level exports matching temporalio.activity
# ============================================================================

__all__ = [
    # Decorators
    "defn",
    # Functions
    "heartbeat",
    "heartbeat_async",
    "info",
    "is_cancelled",
    "wait_for_cancelled",
    "raise_complete_async",
    "get_task_token",
    # Classes
    "Info",
    "TaskToken",
]
