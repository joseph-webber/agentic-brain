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
Interceptors - Middleware for workflows and activities.

Interceptors allow injecting cross-cutting concerns like
logging, metrics, tracing, and authentication into workflow
and activity execution.

Features:
- Workflow interceptors
- Activity interceptors
- Chain of responsibility
- Built-in interceptors (logging, metrics, tracing)
- Custom interceptor support
"""

import asyncio
import functools
import inspect
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar


@dataclass
class InterceptorContext:
    """Context passed through interceptor chain."""

    workflow_id: str
    activity_name: Optional[str] = None
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.utcnow)

    # Tracing
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    parent_span_id: Optional[str] = None

    # Metrics
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Error tracking
    error: Optional[Exception] = None
    retries: int = 0


class WorkflowInterceptor(ABC):
    """
    Base class for workflow interceptors.

    Interceptors can modify workflow execution at various points.
    """

    @abstractmethod
    async def intercept_execute(
        self, context: InterceptorContext, next_fn: Callable
    ) -> Any:
        """
        Intercept workflow execution.

        Args:
            context: Execution context
            next_fn: Next interceptor or actual workflow

        Returns:
            Workflow result
        """
        pass

    async def on_start(self, context: InterceptorContext) -> None:
        """Called when workflow starts."""
        pass

    async def on_complete(self, context: InterceptorContext, result: Any) -> None:
        """Called when workflow completes successfully."""
        pass

    async def on_error(self, context: InterceptorContext, error: Exception) -> None:
        """Called when workflow fails."""
        pass


class ActivityInterceptor(ABC):
    """
    Base class for activity interceptors.

    Interceptors can modify activity execution at various points.
    """

    @abstractmethod
    async def intercept_execute(
        self, context: InterceptorContext, next_fn: Callable
    ) -> Any:
        """
        Intercept activity execution.

        Args:
            context: Execution context
            next_fn: Next interceptor or actual activity

        Returns:
            Activity result
        """
        pass

    async def on_start(self, context: InterceptorContext) -> None:
        """Called when activity starts."""
        pass

    async def on_complete(self, context: InterceptorContext, result: Any) -> None:
        """Called when activity completes successfully."""
        pass

    async def on_error(self, context: InterceptorContext, error: Exception) -> None:
        """Called when activity fails."""
        pass

    async def on_retry(self, context: InterceptorContext, error: Exception) -> None:
        """Called before activity retry."""
        pass


# Built-in interceptors


class LoggingInterceptor(WorkflowInterceptor, ActivityInterceptor):
    """
    Logs workflow and activity execution.

    Logs start, completion, and errors with timing information.
    """

    def __init__(self, logger: Optional[Callable] = None):
        self.logger = logger or print

    async def intercept_execute(
        self, context: InterceptorContext, next_fn: Callable
    ) -> Any:
        name = context.activity_name or "workflow"
        self.logger(f"[START] {name} (trace={context.trace_id[:8]})")

        start = time.time()
        try:
            result = await next_fn()
            elapsed = (time.time() - start) * 1000
            self.logger(f"[DONE] {name} ({elapsed:.2f}ms)")
            return result
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self.logger(f"[ERROR] {name} ({elapsed:.2f}ms): {e}")
            raise

    async def on_start(self, context: InterceptorContext) -> None:
        self.logger(f"Starting {context.workflow_id}")

    async def on_complete(self, context: InterceptorContext, result: Any) -> None:
        self.logger(f"Completed {context.workflow_id}")

    async def on_error(self, context: InterceptorContext, error: Exception) -> None:
        self.logger(f"Failed {context.workflow_id}: {error}")


class MetricsInterceptor(WorkflowInterceptor, ActivityInterceptor):
    """
    Collects execution metrics.

    Tracks timing, counts, and error rates.
    """

    def __init__(self):
        self.workflow_count = 0
        self.activity_count = 0
        self.error_count = 0
        self.total_duration_ms = 0.0
        self.durations: List[float] = []

    async def intercept_execute(
        self, context: InterceptorContext, next_fn: Callable
    ) -> Any:
        start = time.time()

        try:
            if context.activity_name:
                self.activity_count += 1
            else:
                self.workflow_count += 1

            result = await next_fn()

            elapsed = (time.time() - start) * 1000
            self.total_duration_ms += elapsed
            self.durations.append(elapsed)
            context.metrics["duration_ms"] = elapsed

            return result

        except Exception as e:
            self.error_count += 1
            context.metrics["error"] = str(e)
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get collected metrics."""
        if not self.durations:
            return {
                "workflows": self.workflow_count,
                "activities": self.activity_count,
                "errors": self.error_count,
            }

        sorted_durations = sorted(self.durations)
        p50_idx = len(sorted_durations) // 2
        p95_idx = int(len(sorted_durations) * 0.95)
        p99_idx = int(len(sorted_durations) * 0.99)

        return {
            "workflows": self.workflow_count,
            "activities": self.activity_count,
            "errors": self.error_count,
            "error_rate": self.error_count
            / max(self.workflow_count + self.activity_count, 1),
            "total_duration_ms": self.total_duration_ms,
            "avg_duration_ms": self.total_duration_ms / len(self.durations),
            "p50_ms": sorted_durations[p50_idx],
            "p95_ms": sorted_durations[min(p95_idx, len(sorted_durations) - 1)],
            "p99_ms": sorted_durations[min(p99_idx, len(sorted_durations) - 1)],
        }


class TracingInterceptor(WorkflowInterceptor, ActivityInterceptor):
    """
    Distributed tracing support.

    Creates spans for workflow and activity execution.
    """

    def __init__(self):
        self.spans: List[Dict[str, Any]] = []

    async def intercept_execute(
        self, context: InterceptorContext, next_fn: Callable
    ) -> Any:
        span = {
            "trace_id": context.trace_id,
            "span_id": context.span_id,
            "parent_span_id": context.parent_span_id,
            "name": context.activity_name or "workflow",
            "workflow_id": context.workflow_id,
            "start_time": datetime.now(UTC).isoformat(),
            "status": "running",
        }

        try:
            result = await next_fn()
            span["end_time"] = datetime.now(UTC).isoformat()
            span["status"] = "ok"
            return result
        except Exception as e:
            span["end_time"] = datetime.now(UTC).isoformat()
            span["status"] = "error"
            span["error"] = str(e)
            raise
        finally:
            self.spans.append(span)

    def get_spans(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recorded spans."""
        if trace_id:
            return [s for s in self.spans if s["trace_id"] == trace_id]
        return self.spans


class RetryInterceptor(ActivityInterceptor):
    """
    Handles activity retries with backoff.

    Wraps activity execution with retry logic.
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        backoff_multiplier: float = 2.0,
    ):
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier

    async def intercept_execute(
        self, context: InterceptorContext, next_fn: Callable
    ) -> Any:
        backoff = self.initial_backoff
        last_error = None

        for attempt in range(self.max_retries + 1):
            context.retries = attempt

            try:
                return await next_fn()
            except Exception as e:
                last_error = e

                if attempt < self.max_retries:
                    await self.on_retry(context, e)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * self.backoff_multiplier, self.max_backoff)

        raise last_error

    async def on_retry(self, context: InterceptorContext, error: Exception) -> None:
        # Could add logging/metrics here
        pass


class AuthenticationInterceptor(WorkflowInterceptor, ActivityInterceptor):
    """
    Validates authentication before execution.

    Checks for valid credentials in context metadata.
    """

    def __init__(self, validator: Optional[Callable] = None):
        self.validator = validator or self._default_validator

    def _default_validator(self, context: InterceptorContext) -> bool:
        return "auth_token" in context.metadata

    async def intercept_execute(
        self, context: InterceptorContext, next_fn: Callable
    ) -> Any:
        if not self.validator(context):
            raise PermissionError("Authentication required")

        return await next_fn()


class RateLimitInterceptor(WorkflowInterceptor, ActivityInterceptor):
    """
    Rate limits workflow/activity execution.

    Prevents excessive execution within a time window.
    """

    def __init__(self, max_per_second: int = 10, max_per_minute: int = 100):
        self.max_per_second = max_per_second
        self.max_per_minute = max_per_minute
        self._second_window: List[float] = []
        self._minute_window: List[float] = []

    async def intercept_execute(
        self, context: InterceptorContext, next_fn: Callable
    ) -> Any:
        now = time.time()

        # Clean old entries
        self._second_window = [t for t in self._second_window if now - t < 1]
        self._minute_window = [t for t in self._minute_window if now - t < 60]

        # Check limits
        if len(self._second_window) >= self.max_per_second:
            raise RuntimeError("Rate limit exceeded (per second)")

        if len(self._minute_window) >= self.max_per_minute:
            raise RuntimeError("Rate limit exceeded (per minute)")

        # Record execution
        self._second_window.append(now)
        self._minute_window.append(now)

        return await next_fn()


class InterceptorChain:
    """
    Chain of interceptors for execution.

    Interceptors are executed in order, wrapping the actual function.
    """

    def __init__(self):
        self.interceptors: List[WorkflowInterceptor] = []

    def add(self, interceptor: WorkflowInterceptor) -> "InterceptorChain":
        """Add interceptor to chain."""
        self.interceptors.append(interceptor)
        return self

    async def execute(
        self, context: InterceptorContext, func: Callable, *args, **kwargs
    ) -> Any:
        """Execute function through interceptor chain."""
        context.args = args
        context.kwargs = kwargs

        # Build chain from innermost to outermost
        async def run_func():
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        chain = run_func

        for interceptor in reversed(self.interceptors):
            current_interceptor = interceptor
            next_fn = chain

            async def make_intercepted(i=current_interceptor, n=next_fn):
                return await i.intercept_execute(context, n)

            chain = make_intercepted

        return await chain()


# Decorator for applying interceptors
def with_interceptors(*interceptors: WorkflowInterceptor):
    """
    Decorator to apply interceptors to a function.

    Usage:
        @with_interceptors(LoggingInterceptor(), MetricsInterceptor())
        async def my_workflow(data):
            ...
    """

    def decorator(func: Callable) -> Callable:
        chain = InterceptorChain()
        for interceptor in interceptors:
            chain.add(interceptor)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            context = InterceptorContext(workflow_id=str(uuid.uuid4()))
            return await chain.execute(context, func, *args, **kwargs)

        return wrapper

    return decorator


# Pre-configured interceptor chains
def default_interceptors() -> InterceptorChain:
    """Default interceptor chain with logging and metrics."""
    return InterceptorChain().add(LoggingInterceptor()).add(MetricsInterceptor())


def production_interceptors() -> InterceptorChain:
    """Production interceptor chain with full observability."""
    return (
        InterceptorChain()
        .add(LoggingInterceptor())
        .add(MetricsInterceptor())
        .add(TracingInterceptor())
        .add(RateLimitInterceptor())
    )
