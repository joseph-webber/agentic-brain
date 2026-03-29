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
Temporal testing compatibility module.

Provides testing utilities matching temporalio.testing:
- WorkflowEnvironment - Test environment with time control
- ActivityEnvironment - Test environment for activities
- Time skipping and mocking
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
from unittest.mock import AsyncMock, MagicMock

from .client import Client, WorkflowHandle
from .worker import Worker

T = TypeVar("T")


# ============================================================================
# Workflow Environment (matches temporalio.testing.WorkflowEnvironment)
# ============================================================================


class WorkflowEnvironment:
    """
    Test environment for workflows.

    Provides:
    - Time skipping (no actual waiting)
    - Activity mocking
    - Deterministic execution

    Matches temporalio.testing.WorkflowEnvironment.

    Usage:
        async with await WorkflowEnvironment.start_time_skipping() as env:
            result = await env.client.execute_workflow(
                MyWorkflow.run,
                "arg",
                id="test-1",
                task_queue="test",
            )
            assert result == expected
    """

    def __init__(
        self,
        *,
        time_skipping: bool = False,
        start_time: Optional[datetime] = None,
    ):
        self._time_skipping = time_skipping
        self._current_time = start_time or datetime.now(UTC)
        self._client: Optional[Client] = None
        self._workers: List[Worker] = []
        self._activity_mocks: Dict[str, Callable] = {}

    @classmethod
    async def start_time_skipping(
        cls,
        *,
        start_time: Optional[datetime] = None,
    ) -> WorkflowEnvironment:
        """
        Start a time-skipping test environment.

        Time-skipping means workflow.sleep() completes instantly.

        Args:
            start_time: Optional starting time

        Returns:
            Test environment
        """
        env = cls(time_skipping=True, start_time=start_time)
        await env._initialize()
        return env

    @classmethod
    async def start_local(
        cls,
        *,
        start_time: Optional[datetime] = None,
    ) -> WorkflowEnvironment:
        """
        Start a local test environment.

        Like start_time_skipping but without automatic time advancement.

        Args:
            start_time: Optional starting time

        Returns:
            Test environment
        """
        env = cls(time_skipping=False, start_time=start_time)
        await env._initialize()
        return env

    async def _initialize(self) -> None:
        """Initialize the test environment."""
        self._client = await Client.connect(
            "test://localhost",
            namespace="test",
        )

    @property
    def client(self) -> Client:
        """Get the test client."""
        if self._client is None:
            raise RuntimeError("Environment not initialized")
        return self._client

    def get_current_time(self) -> datetime:
        """Get the current test time."""
        return self._current_time

    async def sleep(self, duration: timedelta) -> None:
        """
        Advance time by duration.

        In time-skipping mode, this is instant.
        """
        if self._time_skipping:
            self._current_time += duration
        else:
            await asyncio.sleep(duration.total_seconds())

    async def skip_time(self, duration: timedelta) -> None:
        """Skip time forward."""
        self._current_time += duration

    async def skip_to(self, target_time: datetime) -> None:
        """Skip to a specific time."""
        if target_time < self._current_time:
            raise ValueError("Cannot skip backwards in time")
        self._current_time = target_time

    def mock_activity(
        self,
        activity: Callable,
        return_value: Any = None,
        side_effect: Optional[Callable] = None,
    ) -> MagicMock:
        """
        Mock an activity.

        Args:
            activity: The activity to mock
            return_value: Value to return
            side_effect: Side effect function

        Returns:
            The mock object
        """
        name = getattr(activity, "_temporal_activity_name", activity.__name__)

        mock = AsyncMock(return_value=return_value, side_effect=side_effect)
        self._activity_mocks[name] = mock

        return mock

    async def start_worker(
        self,
        task_queue: str,
        workflows: List[Type] = None,
        activities: List[Callable] = None,
    ) -> Worker:
        """
        Start a worker in the test environment.

        Args:
            task_queue: Task queue name
            workflows: Workflow classes
            activities: Activity functions

        Returns:
            The worker
        """
        worker = Worker(
            self._client,
            task_queue,
            workflows=workflows or [],
            activities=activities or [],
        )
        self._workers.append(worker)

        # Start in background
        asyncio.create_task(worker.run())

        return worker

    async def shutdown(self) -> None:
        """Shutdown the test environment."""
        for worker in self._workers:
            await worker.shutdown()
        self._workers.clear()

    async def __aenter__(self) -> WorkflowEnvironment:
        return self

    async def __aexit__(self, *args) -> None:
        await self.shutdown()


# ============================================================================
# Activity Environment (matches temporalio.testing.ActivityEnvironment)
# ============================================================================


@dataclass
class ActivityInfo:
    """Activity info for testing."""

    activity_id: str = "test-activity"
    activity_type: str = "test"
    workflow_id: str = "test-workflow"
    workflow_type: str = "TestWorkflow"
    task_queue: str = "test"
    attempt: int = 1
    is_local: bool = False


class ActivityEnvironment:
    """
    Test environment for activities.

    Provides isolated activity execution for unit testing.

    Matches temporalio.testing.ActivityEnvironment.

    Usage:
        env = ActivityEnvironment()
        result = await env.run(my_activity, "arg1", "arg2")
        assert result == expected
    """

    def __init__(
        self,
        *,
        info: Optional[ActivityInfo] = None,
    ):
        self.info = info or ActivityInfo()
        self._heartbeats: List[Any] = []
        self._cancelled = False

    async def run(
        self,
        activity: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Run an activity in the test environment.

        Args:
            activity: The activity function
            *args: Activity arguments
            **kwargs: Activity keyword arguments

        Returns:
            Activity result
        """
        # Set up activity context
        from . import activity as activity_module

        ctx = activity_module._ActivityContext(
            activity_id=self.info.activity_id,
            activity_type=self.info.activity_type,
            workflow_id=self.info.workflow_id,
            task_queue=self.info.task_queue,
            attempt=self.info.attempt,
            cancelled=self._cancelled,
            _cancel_event=asyncio.Event(),
        )
        activity_module._set_current_activity(ctx)

        try:
            if inspect.iscoroutinefunction(activity):
                return await activity(*args, **kwargs)
            else:
                return activity(*args, **kwargs)
        finally:
            activity_module._set_current_activity(None)

    def cancel(self) -> None:
        """Mark activity as cancelled."""
        self._cancelled = True

    def get_heartbeats(self) -> List[Any]:
        """Get recorded heartbeats."""
        return self._heartbeats


# ============================================================================
# Test Utilities
# ============================================================================


async def assert_workflow_completes(
    client: Client,
    workflow: Type,
    *args: Any,
    id: str,
    task_queue: str,
    expected_result: Any = None,
    timeout: timedelta = timedelta(seconds=30),
) -> Any:
    """
    Assert that a workflow completes successfully.

    Args:
        client: Test client
        workflow: Workflow class
        *args: Workflow arguments
        id: Workflow ID
        task_queue: Task queue
        expected_result: Expected result (optional)
        timeout: Timeout

    Returns:
        Workflow result
    """
    result = await asyncio.wait_for(
        client.execute_workflow(
            workflow.run,
            *args,
            id=id,
            task_queue=task_queue,
        ),
        timeout=timeout.total_seconds(),
    )

    if expected_result is not None:
        assert result == expected_result, f"Expected {expected_result}, got {result}"

    return result


async def assert_workflow_fails(
    client: Client,
    workflow: Type,
    *args: Any,
    id: str,
    task_queue: str,
    expected_error: Optional[Type[Exception]] = None,
    timeout: timedelta = timedelta(seconds=30),
) -> Exception:
    """
    Assert that a workflow fails.

    Args:
        client: Test client
        workflow: Workflow class
        *args: Workflow arguments
        id: Workflow ID
        task_queue: Task queue
        expected_error: Expected exception type
        timeout: Timeout

    Returns:
        The exception
    """
    try:
        await asyncio.wait_for(
            client.execute_workflow(
                workflow.run,
                *args,
                id=id,
                task_queue=task_queue,
            ),
            timeout=timeout.total_seconds(),
        )
        raise AssertionError("Workflow should have failed")
    except Exception as e:
        if expected_error and not isinstance(e, expected_error):
            raise AssertionError(f"Expected {expected_error}, got {type(e)}")
        return e


# ============================================================================
# Module-level exports matching temporalio.testing
# ============================================================================

__all__ = [
    "WorkflowEnvironment",
    "ActivityEnvironment",
    "ActivityInfo",
    "assert_workflow_completes",
    "assert_workflow_fails",
]
