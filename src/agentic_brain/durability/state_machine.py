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
Durable Workflow State Machine.

This module provides the core DurableWorkflow class that enables workflows
to survive crashes and restarts. All state changes are recorded as events,
allowing full recovery through event replay.

Key Concepts:
- Event Sourcing: Every state change is an immutable event
- Deterministic Execution: Same inputs = same outputs
- Activity as Side Effect: External calls (LLM, DB, API) are activities
- Automatic Recovery: On restart, replay events to restore state

Usage:
    from agentic_brain.durability import DurableWorkflow, activity

    class MyWorkflow(DurableWorkflow):
        async def run(self, query: str) -> str:
            # This LLM call is automatically durable
            response = await self.execute_activity(
                "llm_call",
                args={"prompt": query}
            )
            return response
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import random
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, ParamSpec, TypeVar

from .event_store import EventStore, get_event_store
from .events import (
    ActivityCompleted,
    ActivityFailed,
    ActivityScheduled,
    ActivityStarted,
    CheckpointCreated,
    SignalProcessed,
    SignalReceived,
    TimerFired,
    TimerStarted,
    WorkflowCancelled,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
)
from .replay import ReplayEngine, WorkflowState

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class RetryPolicy:
    """Retry policy for activities"""

    max_attempts: int = 3
    initial_interval: timedelta = timedelta(seconds=1)
    backoff_coefficient: float = 2.0
    max_interval: timedelta = timedelta(minutes=1)
    jitter_factor: float = 0.1
    non_retryable_errors: list[type[Exception]] = field(default_factory=list)
    retryable_errors: list[type[Exception]] | None = None

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a retry attempt"""
        delay = self.initial_interval.total_seconds() * (
            self.backoff_coefficient ** (attempt - 1)
        )
        max_delay = self.max_interval.total_seconds()
        delay = min(delay, max_delay)

        if self.jitter_factor > 0:
            delay += delay * self.jitter_factor * random.random()

        return delay

    def get_retry_delay(self, attempt: int) -> float:
        """Backward-compatible alias for get_delay"""
        return self.get_delay(attempt)

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if an error should be retried"""
        if attempt >= self.max_attempts:
            return False

        for error_type in self.non_retryable_errors:
            if isinstance(error, error_type):
                return False

        if self.retryable_errors is not None:
            return any(
                isinstance(error, error_type) for error_type in self.retryable_errors
            )

        return True


@dataclass
class ActivityOptions:
    """Options for activity execution"""

    activity_id: str | None = None
    task_queue: str = "default"
    start_to_close_timeout: timedelta = timedelta(seconds=30)
    schedule_to_close_timeout: timedelta | None = None
    heartbeat_timeout: timedelta | None = None
    retry_policy: RetryPolicy | None = None


@dataclass
class WorkflowContext:
    """Context available to running workflows"""

    workflow_id: str
    workflow_type: str
    run_id: str
    task_queue: str
    started_at: datetime

    # Parent workflow info (for child workflows)
    parent_workflow_id: str | None = None
    parent_run_id: str | None = None

    # Execution info
    attempt: int = 1
    continued_from_run_id: str | None = None


class DurableWorkflow(ABC):
    """
    Base class for durable workflows.

    A durable workflow is a long-running process that:
    1. Records all state changes as events
    2. Can be stopped and resumed at any point
    3. Survives crashes through event replay
    4. Handles activities (side effects) with retries

    To create a workflow:
    1. Subclass DurableWorkflow
    2. Implement the `run` method
    3. Use `execute_activity` for side effects
    4. Use `wait_for_signal` for external input

    Example:
        class AnalysisWorkflow(DurableWorkflow):
            async def run(self, data: dict) -> dict:
                # Execute LLM call as durable activity
                analysis = await self.execute_activity(
                    "analyze",
                    args={"data": data},
                    timeout=60
                )
                return {"result": analysis}
    """

    # Workflow metadata (set by decorator or registration)
    _workflow_name: str = ""
    _workflow_version: str = "1.0"

    def __init__(
        self,
        workflow_id: str | None = None,
        event_store: EventStore | None = None,
    ):
        """
        Initialize workflow.

        Args:
            workflow_id: Unique ID for this workflow execution
            event_store: Event store for persistence
        """
        self.workflow_id = workflow_id or str(uuid.uuid4())
        self.event_store = event_store or get_event_store()

        # Runtime state
        self._context: WorkflowContext | None = None
        self._state: WorkflowState | None = None
        self._running = False
        self._cancelled = False

        # Activity registry
        self._activities: dict[str, Callable] = {}

        # Signal handlers
        self._signal_handlers: dict[str, Callable] = {}
        self._pending_signals: list[tuple[str, Any]] = []

        # Query handlers
        self._query_handlers: dict[str, Callable] = {}

        # Replay mode
        self._replaying = False
        self._replay_results: dict[str, Any] = {}

    @property
    def context(self) -> WorkflowContext:
        """Get workflow context"""
        if not self._context:
            raise RuntimeError("Workflow not started")
        return self._context

    @property
    def is_replaying(self) -> bool:
        """Check if currently replaying (not live execution)"""
        return self._replaying

    @abstractmethod
    async def run(self, **args: Any) -> Any:
        """
        Main workflow logic. Override in subclass.

        This method should contain the workflow's business logic.
        Use execute_activity() for side effects.

        Returns:
            Workflow result
        """
        pass

    async def start(
        self,
        args: dict[str, Any] | None = None,
        task_queue: str = "default",
        timeout: float | None = None,
    ) -> Any:
        """
        Start workflow execution.

        Args:
            args: Arguments to pass to run()
            task_queue: Task queue for activities
            timeout: Maximum execution time in seconds

        Returns:
            Workflow result
        """
        args = args or {}
        start_time = datetime.now(UTC)

        # Create context
        self._context = WorkflowContext(
            workflow_id=self.workflow_id,
            workflow_type=self._workflow_name or self.__class__.__name__,
            run_id=str(uuid.uuid4()),
            task_queue=task_queue,
            started_at=start_time,
        )

        # Publish start event
        await self.event_store.publish(
            WorkflowStarted(
                workflow_id=self.workflow_id,
                workflow_type=self._context.workflow_type,
                args=args,
                task_queue=task_queue,
            )
        )

        self._running = True

        try:
            # Execute with optional timeout
            if timeout:
                result = await asyncio.wait_for(self.run(**args), timeout=timeout)
            else:
                result = await self.run(**args)

            # Publish completion event
            duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            await self.event_store.publish(
                WorkflowCompleted(
                    workflow_id=self.workflow_id,
                    result=result,
                    duration_ms=duration_ms,
                )
            )

            self._running = False
            return result

        except asyncio.CancelledError:
            await self.event_store.publish(
                WorkflowCancelled(
                    workflow_id=self.workflow_id,
                    reason="Cancelled",
                )
            )
            self._running = False
            raise

        except TimeoutError:
            from .events import WorkflowTimedOut

            await self.event_store.publish(
                WorkflowTimedOut(
                    workflow_id=self.workflow_id,
                    timeout_type="execution",
                    timeout_seconds=int(timeout) if timeout else 0,
                )
            )
            self._running = False
            raise

        except Exception as e:
            await self.event_store.publish(
                WorkflowFailed(
                    workflow_id=self.workflow_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
            )
            self._running = False
            raise

    async def resume(self) -> Any:
        """
        Resume workflow from saved state.

        Replays events to restore state, then continues execution.
        """
        # Replay events to restore state
        engine = ReplayEngine(self.event_store)
        result = await engine.replay_workflow(self.workflow_id)

        if not result.success or not result.state:
            raise RuntimeError(f"Failed to replay workflow: {result.errors}")

        self._state = result.state

        if result.state.is_completed:
            return result.state.result

        if result.state.is_failed:
            raise RuntimeError(f"Workflow failed: {result.state.error}")

        # Store completed activity results for replay
        self._replaying = True
        self._replay_results = result.state.completed_activities.copy()

        # Create context from state
        self._context = WorkflowContext(
            workflow_id=self.workflow_id,
            workflow_type=result.state.workflow_type,
            run_id=str(uuid.uuid4()),
            task_queue="default",
            started_at=result.state.started_at or datetime.now(UTC),
        )

        # Continue execution
        self._running = True
        self._replaying = False

        try:
            result = await self.run(**result.state.args)

            await self.event_store.publish(
                WorkflowCompleted(
                    workflow_id=self.workflow_id,
                    result=result,
                )
            )

            return result

        except Exception as e:
            await self.event_store.publish(
                WorkflowFailed(
                    workflow_id=self.workflow_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
            )
            raise
        finally:
            self._running = False

    async def execute_activity(
        self,
        name: str,
        args: dict[str, Any] | None = None,
        timeout: float = 30.0,
        retry: int = 3,
        activity_id: str | None = None,
    ) -> Any:
        """
        Execute an activity (side effect) durably.

        Activities are recorded as events, so on replay we can skip
        re-execution and use the cached result.

        Args:
            name: Activity name (registered or callable)
            args: Arguments to pass to activity
            timeout: Timeout in seconds
            retry: Number of retry attempts
            activity_id: Unique ID for this activity invocation

        Returns:
            Activity result
        """
        args = args or {}
        activity_id = activity_id or f"{name}-{uuid.uuid4().hex[:8]}"

        # Check if already completed (replay mode)
        if activity_id in self._replay_results:
            logger.debug(f"Using cached result for activity {activity_id}")
            return self._replay_results[activity_id]

        # Get activity function
        activity_fn = self._activities.get(name)
        if not activity_fn:
            raise ValueError(f"Activity not registered: {name}")

        # Record scheduled event
        await self.event_store.publish(
            ActivityScheduled(
                workflow_id=self.workflow_id,
                activity_id=activity_id,
                activity_type=name,
                args=args,
            )
        )

        # Execute with retries
        last_error = None
        for attempt in range(1, retry + 1):
            # Record start event
            await self.event_store.publish(
                ActivityStarted(
                    workflow_id=self.workflow_id,
                    activity_id=activity_id,
                    attempt=attempt,
                )
            )

            try:
                # Execute activity
                start_time = datetime.now(UTC)

                if inspect.iscoroutinefunction(activity_fn):
                    result = await asyncio.wait_for(
                        activity_fn(**args), timeout=timeout
                    )
                else:
                    result = activity_fn(**args)

                duration_ms = int(
                    (datetime.now(UTC) - start_time).total_seconds() * 1000
                )

                # Record completion event
                await self.event_store.publish(
                    ActivityCompleted(
                        workflow_id=self.workflow_id,
                        activity_id=activity_id,
                        result=result,
                        duration_ms=duration_ms,
                    )
                )

                # Cache for potential replay
                self._replay_results[activity_id] = result

                return result

            except Exception as e:
                last_error = e
                will_retry = attempt < retry

                await self.event_store.publish(
                    ActivityFailed(
                        workflow_id=self.workflow_id,
                        activity_id=activity_id,
                        error=str(e),
                        error_type=type(e).__name__,
                        attempt=attempt,
                        will_retry=will_retry,
                    )
                )

                if will_retry:
                    delay = RetryPolicy().get_delay(attempt)
                    logger.warning(f"Activity {name} failed, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)

        raise last_error or RuntimeError(
            f"Activity {name} failed after {retry} attempts"
        )

    def register_activity(self, name: str, fn: Callable) -> None:
        """Register an activity function"""
        self._activities[name] = fn

    async def sleep(self, duration: float) -> None:
        """
        Sleep for a duration (durable).

        The sleep is recorded as a timer event, so on replay
        we can skip the actual sleep.
        """
        timer_id = f"timer-{uuid.uuid4().hex[:8]}"

        await self.event_store.publish(
            TimerStarted(
                workflow_id=self.workflow_id,
                timer_id=timer_id,
                duration_seconds=duration,
                fire_at=datetime.now(UTC) + timedelta(seconds=duration),
            )
        )

        if not self._replaying:
            await asyncio.sleep(duration)

        await self.event_store.publish(
            TimerFired(
                workflow_id=self.workflow_id,
                timer_id=timer_id,
            )
        )

    async def wait_for_signal(
        self,
        signal_name: str,
        timeout: float | None = None,
    ) -> Any:
        """
        Wait for an external signal.

        Args:
            signal_name: Name of the signal to wait for
            timeout: Maximum time to wait

        Returns:
            Signal arguments
        """
        # Check pending signals
        for i, (name, args) in enumerate(self._pending_signals):
            if name == signal_name:
                self._pending_signals.pop(i)
                return args

        # Wait for signal
        start = datetime.now(UTC)
        while True:
            # Check again
            for i, (name, args) in enumerate(self._pending_signals):
                if name == signal_name:
                    self._pending_signals.pop(i)
                    return args

            if timeout:
                elapsed = (datetime.now(UTC) - start).total_seconds()
                if elapsed >= timeout:
                    raise TimeoutError(f"Signal {signal_name} timed out")

            await asyncio.sleep(0.1)

    async def receive_signal(self, signal_name: str, args: Any = None) -> None:
        """
        Receive an external signal (called by orchestrator).

        Args:
            signal_name: Name of the signal
            args: Signal arguments
        """
        await self.event_store.publish(
            SignalReceived(
                workflow_id=self.workflow_id,
                signal_name=signal_name,
                signal_args=args,
            )
        )

        self._pending_signals.append((signal_name, args))

        # Call handler if registered
        handler = self._signal_handlers.get(signal_name)
        if handler:
            await handler(args)

            await self.event_store.publish(
                SignalProcessed(
                    workflow_id=self.workflow_id,
                    signal_name=signal_name,
                )
            )

    def register_signal_handler(self, name: str, handler: Callable) -> None:
        """Register a signal handler"""
        self._signal_handlers[name] = handler

    def register_query_handler(self, name: str, handler: Callable) -> None:
        """Register a query handler"""
        self._query_handlers[name] = handler

    async def query(self, query_name: str, args: Any = None) -> Any:
        """
        Execute a query (read-only state inspection).

        Queries don't record events - they're for inspecting state.
        """
        handler = self._query_handlers.get(query_name)
        if not handler:
            raise ValueError(f"Query not registered: {query_name}")

        return handler(args)

    async def checkpoint(self) -> str:
        """
        Create a checkpoint of current state.

        Returns:
            Checkpoint ID
        """
        checkpoint_id = f"ckpt-{uuid.uuid4().hex[:8]}"

        # Get current sequence number
        last_seq = await self.event_store.get_latest_sequence(self.workflow_id)

        await self.event_store.publish(
            CheckpointCreated(
                workflow_id=self.workflow_id,
                checkpoint_id=checkpoint_id,
                events_since_last=last_seq,
            )
        )

        return checkpoint_id

    async def cancel(self, reason: str = "Cancelled by user") -> None:
        """Cancel workflow execution"""
        self._cancelled = True

        await self.event_store.publish(
            WorkflowCancelled(
                workflow_id=self.workflow_id,
                reason=reason,
            )
        )

    async def wait_for_completion(self, timeout: float | None = None) -> Any:
        """
        Wait for workflow to complete and return result.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Workflow result

        Raises:
            asyncio.TimeoutError: If timeout expires
            Exception: If workflow fails
        """
        # If workflow is not running, check if it's already completed
        if not self._running:
            # Check if we have a cached result from event store
            events = await self.event_store.get_events(self.workflow_id)
            for event in reversed(events):
                if event.event_type.name == "WORKFLOW_COMPLETED":
                    return event.data.get("result")
                if event.event_type.name == "WORKFLOW_FAILED":
                    error = event.data.get("error", "Workflow failed")
                    raise Exception(error)
                if event.event_type.name == "WORKFLOW_CANCELLED":
                    reason = event.data.get("reason", "Workflow cancelled")
                    raise asyncio.CancelledError(reason)

        # If workflow is running, wait for completion by polling events
        start_time = asyncio.get_event_loop().time()
        while True:
            events = await self.event_store.get_events(self.workflow_id)
            for event in reversed(events):
                if event.event_type.name == "WORKFLOW_COMPLETED":
                    return event.data.get("result")
                if event.event_type.name == "WORKFLOW_FAILED":
                    error = event.data.get("error", "Workflow failed")
                    raise Exception(error)
                if event.event_type.name == "WORKFLOW_CANCELLED":
                    reason = event.data.get("reason", "Workflow cancelled")
                    raise asyncio.CancelledError(reason)

            # Check timeout
            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                raise TimeoutError(
                    f"Workflow did not complete within {timeout} seconds"
                )

            # If workflow is no longer running but we haven't found completion event, it might have failed
            if not self._running:
                break

            # Wait a bit before polling again
            await asyncio.sleep(0.1)


# =============================================================================
# Decorators
# =============================================================================


def workflow(
    name: str | None = None,
    version: str = "1.0",
) -> Callable[[type], type]:
    """
    Decorator for workflow class definitions.

    Usage:
        @workflow(name="my-workflow")
        class MyWorkflow(DurableWorkflow):
            async def run(self, data: dict) -> str:
                return "done"
    """

    def decorator(cls: type) -> type:
        cls._workflow_name = name or cls.__name__
        cls._workflow_version = version
        return cls

    return decorator


def activity(
    name: str | None = None,
    timeout: float = 30.0,
    retry: int = 3,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator for activity definitions.

    Usage:
        @activity(name="call_llm", timeout=60, retry=3)
        async def call_llm(prompt: str) -> str:
            return await llm.complete(prompt)
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        fn._activity_name = name or fn.__name__
        fn._activity_timeout = timeout
        fn._activity_retry = retry
        return fn

    return decorator


def signal(name: str | None = None) -> Callable[[Callable], Callable]:
    """Decorator for signal handlers"""

    def decorator(fn: Callable) -> Callable:
        fn._signal_name = name or fn.__name__
        return fn

    return decorator


def query(name: str | None = None) -> Callable[[Callable], Callable]:
    """Decorator for query handlers"""

    def decorator(fn: Callable) -> Callable:
        fn._query_name = name or fn.__name__
        return fn

    return decorator


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "DurableWorkflow",
    "WorkflowContext",
    "RetryPolicy",
    "ActivityOptions",
    "workflow",
    "activity",
    "signal",
    "query",
]
