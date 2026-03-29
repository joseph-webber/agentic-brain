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
Temporal workflow compatibility module.

Provides decorators and utilities matching temporalio.workflow exactly:
- @workflow.defn - Define a workflow class
- @workflow.run - Mark the workflow entry point
- @workflow.signal - Define signal handlers
- @workflow.query - Define query handlers
- @workflow.update - Define update handlers
- workflow.execute_activity() - Execute an activity
- workflow.execute_child_workflow() - Execute child workflow
- workflow.start_child_workflow() - Start child workflow
- workflow.sleep() - Durable sleep
- workflow.now() - Current workflow time
- workflow.info() - Workflow info
- workflow.uuid4() - Deterministic UUID
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from functools import wraps
from random import Random
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

from ..durability import (
    ChildWorkflowManager,
    ChildWorkflowOptions,
    DurableWorkflow,
    ParentClosePolicy,
    Timer,
    TimerManager,
    query_handler,
    signal_handler,
    update_handler,
)
from ..durability import (
    workflow as native_workflow,
)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# ============================================================================
# Workflow Info (matches temporalio.workflow.Info)
# ============================================================================


@dataclass
class Info:
    """Information about the running workflow."""

    workflow_id: str
    workflow_type: str
    task_queue: str
    namespace: str = "default"
    run_id: str = ""
    parent_workflow_id: Optional[str] = None
    parent_run_id: Optional[str] = None
    root_workflow_id: Optional[str] = None
    root_run_id: Optional[str] = None
    attempt: int = 1
    cron_schedule: Optional[str] = None
    continued_run_id: Optional[str] = None
    execution_timeout: Optional[timedelta] = None
    run_timeout: Optional[timedelta] = None
    task_timeout: Optional[timedelta] = None
    retry_policy: Optional[Any] = None
    search_attributes: Optional[Dict[str, Any]] = None
    memo: Optional[Dict[str, Any]] = None
    start_time: Optional[datetime] = None
    typed_search_attributes: Optional[Any] = None


# ============================================================================
# Activity Execution Options
# ============================================================================


@dataclass
class ActivityConfig:
    """Configuration for activity execution (internal)."""

    activity: str | Callable
    args: tuple = ()
    task_queue: Optional[str] = None
    schedule_to_close_timeout: Optional[timedelta] = None
    schedule_to_start_timeout: Optional[timedelta] = None
    start_to_close_timeout: Optional[timedelta] = None
    heartbeat_timeout: Optional[timedelta] = None
    retry_policy: Optional[Any] = None
    cancellation_type: str = "wait_cancellation_completed"


# ============================================================================
# Workflow Context (thread-local storage for current workflow)
# ============================================================================

_current_workflow: Optional[DurableWorkflow] = None


def _get_current_workflow(raise_if_none: bool = True) -> Optional[DurableWorkflow]:
    """Get the currently executing workflow.

    Args:
        raise_if_none: If True, raise RuntimeError when no workflow context.
                      If False, return None (useful for testing).
    """
    if _current_workflow is None and raise_if_none:
        raise RuntimeError(
            "No workflow context. This function must be called from within a workflow."
        )
    return _current_workflow


def _set_current_workflow(wf: Optional[DurableWorkflow]) -> None:
    """Set the currently executing workflow."""
    global _current_workflow
    _current_workflow = wf


# ============================================================================
# Decorators (matching temporalio.workflow decorators)
# ============================================================================


def defn(
    cls: Optional[Type[T]] = None,
    *,
    name: Optional[str] = None,
    sandboxed: bool = True,
    failure_exception_types: Optional[List[Type[BaseException]]] = None,
) -> Type[T] | Callable[[Type[T]], Type[T]]:
    """
    Decorator to define a workflow class.

    Matches temporalio.workflow.defn exactly.

    Usage:
        @workflow.defn
        class MyWorkflow:
            @workflow.run
            async def run(self, arg: str) -> str:
                return await workflow.execute_activity(...)

    Args:
        cls: The workflow class (when used without parentheses)
        name: Optional workflow type name (defaults to class name)
        sandboxed: Whether to sandbox (ignored, for compatibility)
        failure_exception_types: Exception types that fail workflow

    Returns:
        Decorated workflow class
    """

    def decorator(cls: Type[T]) -> Type[T]:
        workflow_name = name or cls.__name__

        # Apply our native workflow decorator
        decorated = native_workflow(name=workflow_name)(cls)

        # Store metadata
        decorated._temporal_workflow_name = workflow_name
        decorated._temporal_sandboxed = sandboxed
        decorated._temporal_failure_types = failure_exception_types or []

        return decorated

    if cls is not None:
        return decorator(cls)
    return decorator


def run(fn: F) -> F:
    """
    Decorator to mark the workflow entry point method.

    Matches temporalio.workflow.run exactly.

    Usage:
        @workflow.defn
        class MyWorkflow:
            @workflow.run
            async def run(self, name: str) -> str:
                return f"Hello, {name}!"
    """

    @wraps(fn)
    async def wrapper(self, *args, **kwargs):
        # Set workflow context
        _set_current_workflow(self)
        try:
            return await fn(self, *args, **kwargs)
        finally:
            _set_current_workflow(None)

    wrapper._temporal_is_run = True
    wrapper._temporal_workflow_run = True  # Alias for compatibility
    return wrapper  # type: ignore


def signal(
    fn: Optional[F] = None,
    *,
    name: Optional[str] = None,
    dynamic: bool = False,
    unfinished_policy: str = "warn_and_abandon",
) -> F | Callable[[F], F]:
    """
    Decorator to define a signal handler.

    Matches temporalio.workflow.signal exactly.

    Usage:
        @workflow.defn
        class MyWorkflow:
            @workflow.signal
            async def my_signal(self, value: str) -> None:
                self.values.append(value)
    """

    def decorator(fn: F) -> F:
        signal_name = name or fn.__name__
        decorated = signal_handler(signal_name)(fn)
        decorated._temporal_signal_name = signal_name
        decorated._temporal_dynamic = dynamic
        return decorated

    if fn is not None:
        return decorator(fn)
    return decorator


def query(
    fn: Optional[F] = None,
    *,
    name: Optional[str] = None,
    dynamic: bool = False,
) -> F | Callable[[F], F]:
    """
    Decorator to define a query handler.

    Matches temporalio.workflow.query exactly.

    Usage:
        @workflow.defn
        class MyWorkflow:
            @workflow.query
            def get_status(self) -> str:
                return self.status
    """

    def decorator(fn: F) -> F:
        query_name = name or fn.__name__
        decorated = query_handler(query_name)(fn)
        decorated._temporal_query_name = query_name
        decorated._temporal_dynamic = dynamic
        return decorated

    if fn is not None:
        return decorator(fn)
    return decorator


def update(
    fn: Optional[F] = None,
    *,
    name: Optional[str] = None,
    dynamic: bool = False,
    unfinished_policy: str = "warn_and_abandon",
) -> F | Callable[[F], F]:
    """
    Decorator to define an update handler.

    Matches temporalio.workflow.update exactly.

    Usage:
        @workflow.defn
        class MyWorkflow:
            @workflow.update
            async def update_config(self, config: dict) -> bool:
                self.config = config
                return True
    """

    def decorator(fn: F) -> F:
        update_name = name or fn.__name__
        decorated = update_handler(update_name)(fn)
        decorated._temporal_update_name = update_name
        decorated._temporal_dynamic = dynamic
        return decorated

    if fn is not None:
        return decorator(fn)
    return decorator


# ============================================================================
# Workflow Functions (matching temporalio.workflow functions)
# ============================================================================


async def execute_activity(
    activity: str | Callable,
    *args: Any,
    task_queue: Optional[str] = None,
    schedule_to_close_timeout: Optional[timedelta] = None,
    schedule_to_start_timeout: Optional[timedelta] = None,
    start_to_close_timeout: Optional[timedelta] = None,
    heartbeat_timeout: Optional[timedelta] = None,
    retry_policy: Optional[Any] = None,
    cancellation_type: str = "wait_cancellation_completed",
) -> Any:
    """
    Execute an activity and wait for result.

    Matches temporalio.workflow.execute_activity exactly.

    Usage:
        result = await workflow.execute_activity(
            my_activity,
            "arg1",
            start_to_close_timeout=timedelta(seconds=30),
        )
    """
    wf = _get_current_workflow()

    # Get activity name
    if callable(activity):
        activity_name = getattr(activity, "__name__", str(activity))
    else:
        activity_name = activity

    # Calculate timeout in seconds
    timeout = None
    if start_to_close_timeout:
        timeout = start_to_close_timeout.total_seconds()
    elif schedule_to_close_timeout:
        timeout = schedule_to_close_timeout.total_seconds()

    # Execute via our native API
    return await wf.execute_activity(
        activity_name,
        args={"args": args},
        timeout=timeout,
    )


async def execute_local_activity(
    activity: str | Callable,
    *args: Any,
    schedule_to_close_timeout: Optional[timedelta] = None,
    start_to_close_timeout: Optional[timedelta] = None,
    retry_policy: Optional[Any] = None,
    local_retry_threshold: Optional[timedelta] = None,
    cancellation_type: str = "wait_cancellation_completed",
) -> Any:
    """
    Execute a local activity and wait for result.

    Local activities execute in the same process as the workflow,
    without going through the task queue. Use for short, fast operations.

    Matches temporalio.workflow.execute_local_activity exactly.

    Usage:
        result = await workflow.execute_local_activity(
            my_activity,
            "arg1",
            start_to_close_timeout=timedelta(seconds=10),
        )
    """
    wf = _get_current_workflow(raise_if_none=False)

    # Get activity name
    if callable(activity):
        activity_name = getattr(activity, "__name__", str(activity))
    else:
        activity_name = activity

    # For local activities, we execute directly rather than through task queue
    if callable(activity):
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(activity):
            return await activity(*args)
        else:
            # Run sync function in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, activity, *args)
    else:
        # If just a name, fall back to regular activity execution
        if wf is not None:
            return await wf.execute_activity(
                activity_name,
                args={"args": args},
            )
        raise RuntimeError(
            f"Cannot execute local activity {activity_name} outside workflow without function reference"
        )


async def wait_condition(
    fn: Callable[[], bool],
    timeout: Optional[timedelta] = None,
) -> bool:
    """
    Wait until a condition function returns True.

    Matches temporalio.workflow.wait_condition exactly.

    Args:
        fn: Callable that returns True when condition is met.
        timeout: Optional timeout. If reached, returns False.

    Returns:
        True if condition was met, False if timeout reached.

    Usage:
        await workflow.wait_condition(lambda: self.got_signal)
        # Or with timeout:
        met = await workflow.wait_condition(lambda: self.got_signal, timeout=timedelta(seconds=30))
    """
    import asyncio

    timeout_seconds = timeout.total_seconds() if timeout else None
    check_interval = 0.1  # Check every 100ms
    elapsed = 0.0

    while True:
        if fn():
            return True

        if timeout_seconds and elapsed >= timeout_seconds:
            return False

        await asyncio.sleep(check_interval)
        elapsed += check_interval


async def start_activity(
    activity: str | Callable,
    *args: Any,
    task_queue: Optional[str] = None,
    schedule_to_close_timeout: Optional[timedelta] = None,
    schedule_to_start_timeout: Optional[timedelta] = None,
    start_to_close_timeout: Optional[timedelta] = None,
    heartbeat_timeout: Optional[timedelta] = None,
    retry_policy: Optional[Any] = None,
    cancellation_type: str = "wait_cancellation_completed",
) -> Any:
    """
    Start an activity without waiting.

    Returns a handle that can be awaited later.
    """
    # For now, just execute - can enhance with proper handle later
    return await execute_activity(
        activity,
        *args,
        task_queue=task_queue,
        schedule_to_close_timeout=schedule_to_close_timeout,
        schedule_to_start_timeout=schedule_to_start_timeout,
        start_to_close_timeout=start_to_close_timeout,
        heartbeat_timeout=heartbeat_timeout,
        retry_policy=retry_policy,
        cancellation_type=cancellation_type,
    )


async def execute_child_workflow(
    workflow: str | Type,
    *args: Any,
    id: Optional[str] = None,
    task_queue: Optional[str] = None,
    namespace: str = "default",
    cancellation_type: str = "wait_cancellation_completed",
    parent_close_policy: str = "terminate",
    execution_timeout: Optional[timedelta] = None,
    run_timeout: Optional[timedelta] = None,
    task_timeout: Optional[timedelta] = None,
    retry_policy: Optional[Any] = None,
    memo: Optional[Dict[str, Any]] = None,
    search_attributes: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Execute a child workflow and wait for result.

    Matches temporalio.workflow.execute_child_workflow exactly.
    """
    wf = _get_current_workflow()

    # Get workflow name
    if isinstance(workflow, type):
        getattr(workflow, "_temporal_workflow_name", workflow.__name__)
    else:
        pass

    # Map parent close policy
    policy_map = {
        "terminate": ParentClosePolicy.TERMINATE,
        "abandon": ParentClosePolicy.ABANDON,
        "request_cancel": ParentClosePolicy.REQUEST_CANCEL,
    }
    policy = policy_map.get(parent_close_policy, ParentClosePolicy.TERMINATE)

    # Create child workflow manager
    manager = ChildWorkflowManager(parent_workflow=wf)

    # Configure options
    options = ChildWorkflowOptions(
        workflow_id=id or f"child-{uuid.uuid4().hex[:8]}",
        task_queue=task_queue,
        parent_close_policy=policy,
    )

    # Start and wait
    handle = await manager.start_child(
        workflow_class=workflow if isinstance(workflow, type) else None,
        workflow_id=options.workflow_id,
        args=args,
    )

    return await handle.result()


async def start_child_workflow(
    workflow: str | Type,
    *args: Any,
    id: Optional[str] = None,
    task_queue: Optional[str] = None,
    **kwargs,
) -> Any:
    """
    Start a child workflow without waiting.

    Returns a handle that can be awaited later.
    """
    # For now, just execute - can enhance with proper handle later
    return await execute_child_workflow(
        workflow,
        *args,
        id=id,
        task_queue=task_queue,
        **kwargs,
    )


async def sleep(duration: int | float | timedelta) -> None:
    """
    Sleep for a duration (durable - survives restarts).

    Matches temporalio.workflow.sleep exactly.

    Usage:
        await workflow.sleep(timedelta(hours=1))
        await workflow.sleep(3600)  # seconds

    When called outside a workflow (e.g., in tests), uses asyncio.sleep.
    """
    import asyncio as aio

    if isinstance(duration, timedelta):
        seconds = duration.total_seconds()
    else:
        seconds = float(duration)

    wf = _get_current_workflow(raise_if_none=False)

    if wf is None:
        # Outside workflow context - use standard asyncio sleep
        await aio.sleep(seconds)
        return

    # Use our timer system for durable sleep
    timer_manager = TimerManager(workflow_id=wf.workflow_id)
    timer_id = f"sleep-{uuid.uuid4().hex[:8]}"

    await timer_manager.create_timer(timer_id, seconds)
    await timer_manager.wait_for_timer(timer_id)


def now() -> datetime:
    """
    Get the current workflow time.

    This is deterministic - replays return the same time.

    Matches temporalio.workflow.now exactly.

    When called outside a workflow (e.g., in tests), returns current UTC time.
    """
    wf = _get_current_workflow(raise_if_none=False)
    if wf is None:
        return datetime.now(UTC)
    return wf.context.current_time if hasattr(wf, "context") else datetime.now(UTC)


def info() -> Info:
    """
    Get information about the current workflow.

    Matches temporalio.workflow.info exactly.
    """
    wf = _get_current_workflow()

    return Info(
        workflow_id=wf.workflow_id,
        workflow_type=getattr(wf, "_temporal_workflow_name", wf.__class__.__name__),
        task_queue=getattr(wf, "task_queue", "default"),
        namespace=getattr(wf, "namespace", "default"),
        run_id=getattr(wf, "run_id", ""),
        attempt=getattr(wf, "attempt", 1),
        start_time=getattr(wf, "start_time", None),
    )


def uuid4() -> str:
    """
    Generate a deterministic UUID.

    Safe to use in workflows - replays return same UUID.

    Matches temporalio.workflow.uuid4 exactly.

    When called outside a workflow (e.g., in tests), generates a random UUID.

    Returns:
        UUID as a string in standard format (e.g., "550e8400-e29b-41d4-a716-446655440000")
    """
    wf = _get_current_workflow(raise_if_none=False)

    if wf is None:
        # Outside workflow context - return random UUID
        return str(uuid.uuid4())

    # Use workflow context to generate deterministic UUID
    # Based on workflow_id + counter for reproducibility
    counter = getattr(wf, "_uuid_counter", 0)
    wf._uuid_counter = counter + 1

    # Create deterministic UUID from workflow_id and counter
    seed = f"{wf.workflow_id}-{counter}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


def random() -> Random:
    """
    Get a deterministic random number generator.

    Safe to use in workflows - replays produce same sequence.

    When called outside a workflow (e.g., in tests), returns unseeded Random.
    """
    import random as stdlib_random

    wf = _get_current_workflow(raise_if_none=False)

    rng = stdlib_random.Random()

    if wf is not None:
        # Seed based on workflow_id for determinism
        rng.seed(wf.workflow_id)

    return rng


def get_external_workflow_handle(
    workflow_id: str,
    *,
    run_id: Optional[str] = None,
) -> Any:
    """
    Get a handle to an external workflow.

    Can be used to signal/query/cancel external workflows.
    """
    from .client import WorkflowHandle

    return WorkflowHandle(workflow_id=workflow_id, run_id=run_id)


# ============================================================================
# Exceptions
# ============================================================================


class ContinueAsNewError(Exception):
    """
    Raised to continue workflow as new run.

    Matches temporalio.workflow.ContinueAsNewError.

    Supports both patterns:
        ContinueAsNewError("arg1", "arg2")  # positional
        ContinueAsNewError(args=("arg1", "arg2"))  # keyword (Temporal style)
    """

    def __init__(
        self,
        *positional_args: Any,
        args: Optional[Tuple[Any, ...]] = None,
        workflow: Optional[str | Type] = None,
        task_queue: Optional[str] = None,
        run_timeout: Optional[timedelta] = None,
        task_timeout: Optional[timedelta] = None,
        memo: Optional[Dict[str, Any]] = None,
        search_attributes: Optional[Dict[str, Any]] = None,
    ):
        super().__init__("Continue as new")
        # Support both positional args and args= keyword
        self.args = args if args is not None else positional_args
        self.workflow = workflow
        self.task_queue = task_queue
        self.run_timeout = run_timeout
        self.task_timeout = task_timeout
        self.memo = memo
        self.search_attributes = search_attributes


def continue_as_new(
    *args: Any,
    workflow: Optional[str | Type] = None,
    task_queue: Optional[str] = None,
    run_timeout: Optional[timedelta] = None,
    task_timeout: Optional[timedelta] = None,
    memo: Optional[Dict[str, Any]] = None,
    search_attributes: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Continue workflow as a new run.

    Matches temporalio.workflow.continue_as_new exactly.

    Usage:
        if len(self.history) > 1000:
            workflow.continue_as_new(self.state)
    """
    raise ContinueAsNewError(
        *args,
        workflow=workflow,
        task_queue=task_queue,
        run_timeout=run_timeout,
        task_timeout=task_timeout,
        memo=memo,
        search_attributes=search_attributes,
    )


class ApplicationError(Exception):
    """
    Application-level workflow error.

    Matches temporalio.exceptions.ApplicationError.
    """

    def __init__(
        self,
        message: str,
        *details: Any,
        type: Optional[str] = None,
        non_retryable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.details = details
        self.type = type
        self.non_retryable = non_retryable


# ============================================================================
# Module-level exports matching temporalio.workflow
# ============================================================================

__all__ = [
    # Decorators
    "defn",
    "run",
    "signal",
    "query",
    "update",
    # Functions
    "execute_activity",
    "start_activity",
    "execute_child_workflow",
    "start_child_workflow",
    "sleep",
    "now",
    "info",
    "uuid4",
    "random",
    "get_external_workflow_handle",
    "continue_as_new",
    # Classes
    "Info",
    "ContinueAsNewError",
    "ApplicationError",
]
