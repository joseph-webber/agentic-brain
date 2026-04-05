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
Local Activities - Same-process activities without task queue.

Local activities run in the same process as the workflow,
avoiding serialization overhead for simple operations.
Useful for fast, deterministic operations.

Features:
- In-process execution
- No serialization overhead
- Short timeout enforcement
- Automatic fallback to regular activity
"""

import asyncio
import functools
import inspect
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from .event_store import EventStore, get_event_store
from .events import BaseEvent, EventType


@dataclass
class LocalActivityOptions:
    """Configuration for local activity execution."""

    # Maximum execution time (local activities should be fast)
    start_to_close_timeout: timedelta = field(
        default_factory=lambda: timedelta(seconds=10)
    )

    # Number of retry attempts
    retry_attempts: int = 3

    # Backoff between retries
    retry_backoff: timedelta = field(
        default_factory=lambda: timedelta(milliseconds=100)
    )

    # Maximum retry backoff
    max_backoff: timedelta = field(default_factory=lambda: timedelta(seconds=1))

    # Schedule to close (total including retries)
    schedule_to_close_timeout: Optional[timedelta] = None

    # Fallback to regular activity if local fails
    fallback_to_regular: bool = False

    def __post_init__(self):
        # Local activities should be short
        if self.start_to_close_timeout > timedelta(minutes=1):
            raise ValueError(
                "Local activities should complete within 1 minute. "
                "Use regular activities for longer operations."
            )


@dataclass
class LocalActivityExecution:
    """Record of a local activity execution."""

    activity_id: str
    activity_name: str
    workflow_id: str
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    attempts: int = 0
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


class LocalActivityRegistry:
    """Registry of local activities."""

    def __init__(self):
        self._activities: Dict[str, Callable] = {}
        self._options: Dict[str, LocalActivityOptions] = {}

    def register(
        self, name: str, func: Callable, options: Optional[LocalActivityOptions] = None
    ) -> None:
        """Register a local activity."""
        self._activities[name] = func
        self._options[name] = options or LocalActivityOptions()

    def get(self, name: str) -> Optional[Callable]:
        """Get a registered activity."""
        return self._activities.get(name)

    def get_options(self, name: str) -> LocalActivityOptions:
        """Get options for activity."""
        return self._options.get(name, LocalActivityOptions())

    def list_activities(self) -> List[str]:
        """List all registered activities."""
        return list(self._activities.keys())


# Global registry
_registry = LocalActivityRegistry()


def local_activity(
    name: Optional[str] = None,
    start_to_close_timeout: Optional[timedelta] = None,
    retry_attempts: int = 3,
    fallback_to_regular: bool = False,
):
    """
    Decorator to mark a function as a local activity.

    Local activities run in-process without task queue overhead.
    Best for fast, simple operations.

    Usage:
        @local_activity(name="validate-input")
        def validate_input(data: dict) -> bool:
            return "email" in data and "@" in data["email"]
    """

    def decorator(func: Callable) -> Callable:
        activity_name = name or func.__name__

        options = LocalActivityOptions(
            start_to_close_timeout=start_to_close_timeout or timedelta(seconds=10),
            retry_attempts=retry_attempts,
            fallback_to_regular=fallback_to_regular,
        )

        _registry.register(activity_name, func, options)

        # Store metadata
        func._local_activity_name = activity_name
        func._local_activity_options = options

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await execute_local_activity(activity_name, *args, **kwargs)

        return wrapper

    return decorator


class LocalActivityExecutor:
    """
    Executes local activities with timeout and retry handling.

    Features:
    - Execute in same process
    - Enforce timeouts
    - Retry on failure
    - Record execution history
    """

    def __init__(self, workflow_id: str, event_store: Optional[EventStore] = None):
        self.workflow_id = workflow_id
        self.event_store = event_store or get_event_store()
        self.executions: Dict[str, LocalActivityExecution] = {}

    async def execute(
        self,
        activity_name: str,
        *args,
        options: Optional[LocalActivityOptions] = None,
        **kwargs,
    ) -> Any:
        """
        Execute a local activity.

        Args:
            activity_name: Name of registered activity
            *args: Positional arguments
            options: Override default options
            **kwargs: Keyword arguments

        Returns:
            Activity result
        """
        func = _registry.get(activity_name)
        if not func:
            raise ValueError(f"Unknown local activity: {activity_name}")

        options = options or _registry.get_options(activity_name)

        activity_id = f"local_{uuid.uuid4().hex[:8]}"

        execution = LocalActivityExecution(
            activity_id=activity_id,
            activity_name=activity_name,
            workflow_id=self.workflow_id,
            args=args,
            kwargs=kwargs,
        )

        self.executions[activity_id] = execution

        # Record start event
        start_event = BaseEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=self.workflow_id,
            event_type=EventType.ACTIVITY_STARTED,
            timestamp=datetime.now(UTC),
            data={
                "activity_id": activity_id,
                "activity_name": activity_name,
                "local": True,
                "args": str(args),
                "kwargs": str(kwargs),
            },
        )
        await self.event_store.append(start_event)

        last_error = None
        backoff = options.retry_backoff

        for attempt in range(options.retry_attempts + 1):
            execution.attempts = attempt + 1

            try:
                # Execute with timeout
                timeout = options.start_to_close_timeout.total_seconds()

                start_time = datetime.now(UTC)

                if inspect.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs), timeout=timeout
                    )
                else:
                    # Run sync function in executor
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            None, functools.partial(func, *args, **kwargs)
                        ),
                        timeout=timeout,
                    )

                end_time = datetime.now(UTC)

                execution.completed_at = end_time
                execution.status = "completed"
                execution.result = result
                execution.duration_ms = (end_time - start_time).total_seconds() * 1000

                # Record completion
                complete_event = BaseEvent(
                    event_id=str(uuid.uuid4()),
                    workflow_id=self.workflow_id,
                    event_type=EventType.ACTIVITY_COMPLETED,
                    timestamp=datetime.now(UTC),
                    data={
                        "activity_id": activity_id,
                        "attempts": execution.attempts,
                        "duration_ms": execution.duration_ms,
                    },
                )
                await self.event_store.append(complete_event)

                return result

            except TimeoutError:
                last_error = TimeoutError(
                    f"Local activity {activity_name} timed out " f"after {timeout}s"
                )
            except Exception as e:
                last_error = e

            # Retry with backoff
            if attempt < options.retry_attempts:
                await asyncio.sleep(backoff.total_seconds())
                backoff = min(backoff * 2, options.max_backoff)

        # All retries exhausted
        execution.status = "failed"
        execution.error = str(last_error)
        execution.completed_at = datetime.now(UTC)

        # Record failure
        fail_event = BaseEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=self.workflow_id,
            event_type=EventType.ACTIVITY_FAILED,
            timestamp=datetime.now(UTC),
            data={
                "activity_id": activity_id,
                "attempts": execution.attempts,
                "error": str(last_error),
            },
        )
        await self.event_store.append(fail_event)

        raise last_error

    def get_execution(self, activity_id: str) -> Optional[LocalActivityExecution]:
        """Get execution by ID."""
        return self.executions.get(activity_id)

    def list_executions(self) -> List[LocalActivityExecution]:
        """List all executions."""
        return list(self.executions.values())


async def execute_local_activity(
    activity_name: str,
    *args,
    workflow_id: str = "default",
    event_store: Optional[EventStore] = None,
    options: Optional[LocalActivityOptions] = None,
    **kwargs,
) -> Any:
    """
    Execute a local activity.

    Convenience function for one-shot execution.

    Usage:
        result = await execute_local_activity(
            "validate-input",
            {"email": "user@example.com"},
            workflow_id="my-workflow"
        )
    """
    executor = LocalActivityExecutor(workflow_id=workflow_id, event_store=event_store)

    return await executor.execute(activity_name, *args, options=options, **kwargs)


# Pre-built local activities for common operations
@local_activity(name="validate_email")
def validate_email(email: str) -> bool:
    """Validate email format."""
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


@local_activity(name="parse_json")
def parse_json(text: str) -> dict:
    """Parse JSON string."""
    import json

    return json.loads(text)


@local_activity(name="format_date")
def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    """Format datetime to string."""
    return dt.strftime(fmt)


@local_activity(name="hash_data")
def hash_data(data: str, algorithm: str = "sha256") -> str:
    """Hash data with specified algorithm."""
    import hashlib

    h = hashlib.new(algorithm)
    h.update(data.encode())
    return h.hexdigest()


@local_activity(name="uuid_generate")
def uuid_generate() -> str:
    """Generate a UUID."""
    return str(uuid.uuid4())
