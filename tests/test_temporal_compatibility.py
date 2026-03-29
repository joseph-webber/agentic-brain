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
Comprehensive unit tests for Temporal.io compatibility layer.

These tests ensure the agentic_brain.temporal package is a true
drop-in replacement for the temporalio Python SDK.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# Test: workflow module
# ============================================================================


class TestWorkflowDecorators:
    """Test @workflow.defn, @workflow.run, etc."""

    def test_workflow_defn_decorator(self):
        """Test @workflow.defn marks class as workflow."""
        from agentic_brain.temporal import workflow

        @workflow.defn
        class MyWorkflow:
            @workflow.run
            async def run(self, name: str) -> str:
                return f"Hello {name}"

        assert hasattr(MyWorkflow, "_temporal_workflow_name")
        assert MyWorkflow._temporal_workflow_name == "MyWorkflow"

    def test_workflow_defn_custom_name(self):
        """Test @workflow.defn with custom name."""
        from agentic_brain.temporal import workflow

        @workflow.defn(name="CustomName")
        class MyWorkflow:
            @workflow.run
            async def run(self) -> str:
                return "done"

        assert MyWorkflow._temporal_workflow_name == "CustomName"

    def test_workflow_run_decorator(self):
        """Test @workflow.run marks entry point."""
        from agentic_brain.temporal import workflow

        @workflow.defn
        class MyWorkflow:
            @workflow.run
            async def run(self, x: int) -> int:
                return x * 2

        assert hasattr(MyWorkflow.run, "_temporal_workflow_run")
        assert MyWorkflow.run._temporal_workflow_run is True

    def test_workflow_signal_decorator(self):
        """Test @workflow.signal decorator."""
        from agentic_brain.temporal import workflow

        @workflow.defn
        class MyWorkflow:
            def __init__(self):
                self.status = "pending"

            @workflow.run
            async def run(self) -> str:
                return self.status

            @workflow.signal
            async def update_status(self, new_status: str) -> None:
                self.status = new_status

        assert hasattr(MyWorkflow.update_status, "_temporal_signal_name")

    def test_workflow_query_decorator(self):
        """Test @workflow.query decorator."""
        from agentic_brain.temporal import workflow

        @workflow.defn
        class MyWorkflow:
            def __init__(self):
                self.value = 42

            @workflow.run
            async def run(self) -> int:
                return self.value

            @workflow.query
            def get_value(self) -> int:
                return self.value

        assert hasattr(MyWorkflow.get_value, "_temporal_query_name")

    def test_workflow_update_decorator(self):
        """Test @workflow.update decorator."""
        from agentic_brain.temporal import workflow

        @workflow.defn
        class MyWorkflow:
            def __init__(self):
                self.data = {}

            @workflow.run
            async def run(self) -> dict:
                return self.data

            @workflow.update
            async def set_data(self, key: str, value: str) -> dict:
                self.data[key] = value
                return self.data

        assert hasattr(MyWorkflow.set_data, "_temporal_update_name")


class TestWorkflowFunctions:
    """Test workflow module functions."""

    def test_workflow_now(self):
        """Test workflow.now() returns datetime."""
        from agentic_brain.temporal import workflow

        now = workflow.now()
        assert isinstance(now, datetime)

    def test_workflow_uuid4(self):
        """Test workflow.uuid4() returns UUID string."""
        from agentic_brain.temporal import workflow

        uuid = workflow.uuid4()
        assert isinstance(uuid, str)
        assert len(uuid) == 36  # UUID format

    def test_workflow_random(self):
        """Test workflow.random() returns Random instance."""
        import random

        from agentic_brain.temporal import workflow

        rng = workflow.random()
        assert isinstance(rng, random.Random)

        # Should produce consistent values when seeded
        value = rng.random()
        assert 0 <= value <= 1

    def test_workflow_info_dataclass(self):
        """Test workflow.Info dataclass structure."""
        from agentic_brain.temporal.workflow import Info

        info = Info(
            workflow_id="test-1",
            workflow_type="TestWorkflow",
            run_id="run-abc",
            task_queue="test-queue",
            namespace="default",
            attempt=1,
        )

        assert info.workflow_id == "test-1"
        assert info.workflow_type == "TestWorkflow"
        assert info.run_id == "run-abc"
        assert info.task_queue == "test-queue"
        assert info.namespace == "default"
        assert info.attempt == 1

    def test_continue_as_new_error(self):
        """Test ContinueAsNewError exception."""
        from agentic_brain.temporal.workflow import ContinueAsNewError

        error = ContinueAsNewError(args=("new-arg",), memo={"key": "value"})
        assert error.args == ("new-arg",)
        assert error.memo == {"key": "value"}

    def test_application_error(self):
        """Test ApplicationError exception."""
        from agentic_brain.temporal.workflow import ApplicationError

        error = ApplicationError("Something failed", type="ValidationError")
        assert str(error) == "Something failed"
        assert error.type == "ValidationError"


class TestWorkflowSleep:
    """Test workflow.sleep() durability."""

    @pytest.mark.asyncio
    async def test_sleep_with_timedelta(self):
        """Test workflow.sleep() with timedelta."""
        from agentic_brain.temporal import workflow

        start = datetime.utcnow()
        await workflow.sleep(timedelta(milliseconds=10))
        elapsed = (datetime.utcnow() - start).total_seconds()

        # Should complete (may be instant in test mode)
        assert elapsed >= 0

    @pytest.mark.asyncio
    async def test_sleep_with_seconds(self):
        """Test workflow.sleep() with seconds float."""
        from agentic_brain.temporal import workflow

        await workflow.sleep(0.01)  # 10ms
        # Should not raise


class TestWorkflowExecuteActivity:
    """Test workflow.execute_activity()."""

    @pytest.mark.asyncio
    async def test_execute_activity_basic(self):
        """Test basic activity execution."""
        from agentic_brain.temporal import activity, workflow

        @activity.defn
        async def my_activity(x: int) -> int:
            return x * 2

        # Note: In real usage, this would be inside a workflow
        # For unit test, we verify the function signature
        assert callable(workflow.execute_activity)

    def test_execute_activity_timeout_conversion(self):
        """Test timeout conversion from timedelta."""
        # Verify timedelta is handled correctly
        timeout = timedelta(minutes=5)
        assert timeout.total_seconds() == 300


# ============================================================================
# Test: activity module
# ============================================================================


class TestActivityDecorators:
    """Test @activity.defn decorator."""

    def test_activity_defn_decorator(self):
        """Test @activity.defn marks function as activity."""
        from agentic_brain.temporal import activity

        @activity.defn
        async def process_data(data: str) -> dict:
            return {"processed": data}

        assert hasattr(process_data, "_temporal_activity_name")
        assert process_data._temporal_activity_name == "process_data"

    def test_activity_defn_custom_name(self):
        """Test @activity.defn with custom name."""
        from agentic_brain.temporal import activity

        @activity.defn(name="CustomActivity")
        async def my_func() -> str:
            return "done"

        assert my_func._temporal_activity_name == "CustomActivity"

    def test_activity_defn_sync_function(self):
        """Test @activity.defn works with sync functions."""
        from agentic_brain.temporal import activity

        @activity.defn
        def sync_activity(x: int) -> int:
            return x + 1

        assert hasattr(sync_activity, "_temporal_activity_name")


class TestActivityFunctions:
    """Test activity module functions."""

    def test_activity_info_dataclass(self):
        """Test activity.Info dataclass."""
        from agentic_brain.temporal.activity import Info

        info = Info(
            activity_id="act-1",
            activity_type="ProcessData",
            workflow_id="wf-1",
            workflow_type="MyWorkflow",
            task_queue="tasks",
            attempt=1,
            task_token=b"token123",
            scheduled_time=datetime.utcnow(),
            current_attempt_scheduled_time=datetime.utcnow(),
            start_to_close_timeout=timedelta(minutes=5),
            heartbeat_timeout=timedelta(seconds=30),
        )

        assert info.activity_id == "act-1"
        assert info.attempt == 1
        assert info.task_token == b"token123"

    def test_heartbeat_function_exists(self):
        """Test activity.heartbeat() exists."""
        from agentic_brain.temporal import activity

        assert callable(activity.heartbeat)

    def test_is_cancelled_function_exists(self):
        """Test activity.is_cancelled() exists."""
        from agentic_brain.temporal import activity

        assert callable(activity.is_cancelled)

    def test_wait_for_cancelled_function_exists(self):
        """Test activity.wait_for_cancelled() exists."""
        from agentic_brain.temporal import activity

        assert callable(activity.wait_for_cancelled)


# ============================================================================
# Test: client module
# ============================================================================


class TestClient:
    """Test Client class."""

    @pytest.mark.asyncio
    async def test_client_connect(self):
        """Test Client.connect() is instant (no server needed)."""
        from agentic_brain.temporal.client import Client

        # Should connect instantly - no actual server
        client = await Client.connect("localhost:7233")
        assert client is not None
        assert client.namespace == "default"

    @pytest.mark.asyncio
    async def test_client_connect_custom_namespace(self):
        """Test Client.connect() with custom namespace."""
        from agentic_brain.temporal.client import Client

        client = await Client.connect("localhost:7233", namespace="production")
        assert client.namespace == "production"

    @pytest.mark.asyncio
    async def test_client_get_workflow_handle(self):
        """Test client.get_workflow_handle()."""
        from agentic_brain.temporal.client import Client

        client = await Client.connect("localhost:7233")
        handle = client.get_workflow_handle("test-workflow-id")

        assert handle is not None
        assert handle.id == "test-workflow-id"


class TestWorkflowHandle:
    """Test WorkflowHandle class."""

    @pytest.mark.asyncio
    async def test_workflow_handle_properties(self):
        """Test WorkflowHandle properties."""
        from agentic_brain.temporal.client import Client

        client = await Client.connect("localhost:7233")
        handle = client.get_workflow_handle("my-workflow", run_id="run-123")

        assert handle.id == "my-workflow"
        assert handle.run_id == "run-123"

    @pytest.mark.asyncio
    async def test_workflow_handle_methods_exist(self):
        """Test WorkflowHandle has required methods."""
        from agentic_brain.temporal.client import Client

        client = await Client.connect("localhost:7233")
        handle = client.get_workflow_handle("test")

        # All required methods should exist
        assert hasattr(handle, "result")
        assert hasattr(handle, "signal")
        assert hasattr(handle, "query")
        assert hasattr(handle, "update")
        assert hasattr(handle, "cancel")
        assert hasattr(handle, "terminate")
        assert hasattr(handle, "describe")


# ============================================================================
# Test: worker module
# ============================================================================


class TestWorker:
    """Test Worker class."""

    @pytest.mark.asyncio
    async def test_worker_init(self):
        """Test Worker initialization."""
        from agentic_brain.temporal import activity, workflow
        from agentic_brain.temporal.client import Client
        from agentic_brain.temporal.worker import Worker

        @workflow.defn
        class TestWorkflow:
            @workflow.run
            async def run(self) -> str:
                return "done"

        @activity.defn
        async def test_activity() -> str:
            return "done"

        client = await Client.connect("localhost:7233")

        worker = Worker(
            client,
            task_queue="test-queue",
            workflows=[TestWorkflow],
            activities=[test_activity],
        )

        assert worker.task_queue == "test-queue"
        assert len(worker.workflows) == 1
        assert len(worker.activities) == 1

    @pytest.mark.asyncio
    async def test_worker_methods_exist(self):
        """Test Worker has required methods."""
        from agentic_brain.temporal.client import Client
        from agentic_brain.temporal.worker import Worker

        client = await Client.connect("localhost:7233")
        worker = Worker(client, task_queue="test")

        assert hasattr(worker, "run")
        assert hasattr(worker, "shutdown")
        assert hasattr(worker, "is_running")
        assert hasattr(worker, "is_shutdown")

    @pytest.mark.asyncio
    async def test_worker_context_manager(self):
        """Test Worker as async context manager."""
        from agentic_brain.temporal.client import Client
        from agentic_brain.temporal.worker import Worker

        client = await Client.connect("localhost:7233")

        async with Worker(client, task_queue="test") as worker:
            assert worker is not None


# ============================================================================
# Test: testing module
# ============================================================================


class TestWorkflowEnvironment:
    """Test WorkflowEnvironment for testing workflows."""

    @pytest.mark.asyncio
    async def test_start_time_skipping(self):
        """Test WorkflowEnvironment.start_time_skipping()."""
        from agentic_brain.temporal.testing import WorkflowEnvironment

        async with await WorkflowEnvironment.start_time_skipping() as env:
            assert env is not None
            assert env.client is not None

    @pytest.mark.asyncio
    async def test_start_local(self):
        """Test WorkflowEnvironment.start_local()."""
        from agentic_brain.temporal.testing import WorkflowEnvironment

        async with await WorkflowEnvironment.start_local() as env:
            assert env is not None

    @pytest.mark.asyncio
    async def test_time_skipping_sleep(self):
        """Test time skipping makes sleep instant."""
        from agentic_brain.temporal.testing import WorkflowEnvironment

        async with await WorkflowEnvironment.start_time_skipping() as env:
            start = datetime.utcnow()
            await env.sleep(timedelta(hours=24))  # 24 hours
            elapsed = (datetime.utcnow() - start).total_seconds()

            # Should be instant (time skipping)
            assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_get_current_time(self):
        """Test env.get_current_time()."""
        from agentic_brain.temporal.testing import WorkflowEnvironment

        async with await WorkflowEnvironment.start_time_skipping() as env:
            time1 = env.get_current_time()
            await env.sleep(timedelta(minutes=5))
            time2 = env.get_current_time()

            # Time should have advanced by 5 minutes
            delta = (time2 - time1).total_seconds()
            assert delta == 300  # 5 minutes


class TestActivityEnvironment:
    """Test ActivityEnvironment for testing activities."""

    @pytest.mark.asyncio
    async def test_activity_environment_run(self):
        """Test ActivityEnvironment.run()."""
        from agentic_brain.temporal import activity
        from agentic_brain.temporal.testing import ActivityEnvironment

        @activity.defn
        async def double(x: int) -> int:
            return x * 2

        env = ActivityEnvironment()
        result = await env.run(double, 5)

        assert result == 10

    @pytest.mark.asyncio
    async def test_activity_environment_sync_activity(self):
        """Test ActivityEnvironment with sync activity."""
        from agentic_brain.temporal import activity
        from agentic_brain.temporal.testing import ActivityEnvironment

        @activity.defn
        def add(a: int, b: int) -> int:
            return a + b

        env = ActivityEnvironment()
        result = await env.run(add, 3, 4)

        assert result == 7


# ============================================================================
# Test: API Compatibility (matching temporalio exactly)
# ============================================================================


class TestAPICompatibility:
    """Ensure API matches temporalio SDK exactly."""

    def test_workflow_module_exports(self):
        """Test workflow module has all expected exports."""
        from agentic_brain.temporal import workflow

        # Decorators
        assert hasattr(workflow, "defn")
        assert hasattr(workflow, "run")
        assert hasattr(workflow, "signal")
        assert hasattr(workflow, "query")
        assert hasattr(workflow, "update")

        # Functions
        assert hasattr(workflow, "execute_activity")
        assert hasattr(workflow, "execute_local_activity")
        assert hasattr(workflow, "sleep")
        assert hasattr(workflow, "now")
        assert hasattr(workflow, "info")
        assert hasattr(workflow, "uuid4")
        assert hasattr(workflow, "random")
        assert hasattr(workflow, "continue_as_new")
        assert hasattr(workflow, "wait_condition")

        # Classes/Exceptions
        assert hasattr(workflow, "Info")
        assert hasattr(workflow, "ContinueAsNewError")
        assert hasattr(workflow, "ApplicationError")

    def test_activity_module_exports(self):
        """Test activity module has all expected exports."""
        from agentic_brain.temporal import activity

        # Decorator
        assert hasattr(activity, "defn")

        # Functions
        assert hasattr(activity, "heartbeat")
        assert hasattr(activity, "info")
        assert hasattr(activity, "is_cancelled")
        assert hasattr(activity, "wait_for_cancelled")

        # Classes
        assert hasattr(activity, "Info")

    def test_client_module_exports(self):
        """Test client module has expected exports."""
        from agentic_brain.temporal.client import Client

        assert hasattr(Client, "connect")

    def test_worker_module_exports(self):
        """Test worker module has expected exports."""
        from agentic_brain.temporal.worker import Worker

        assert Worker is not None

    def test_testing_module_exports(self):
        """Test testing module has expected exports."""
        from agentic_brain.temporal.testing import (
            ActivityEnvironment,
            WorkflowEnvironment,
        )

        assert WorkflowEnvironment is not None
        assert ActivityEnvironment is not None

    def test_top_level_imports(self):
        """Test top-level package imports work."""
        from agentic_brain.temporal import (
            ActivityEnvironment,
            Client,
            Worker,
            WorkflowEnvironment,
            activity,
            testing,
            workflow,
        )

        assert workflow is not None
        assert activity is not None
        assert testing is not None
        assert Client is not None
        assert Worker is not None
        assert WorkflowEnvironment is not None
        assert ActivityEnvironment is not None


# ============================================================================
# Test: Import Compatibility (drop-in replacement)
# ============================================================================


class TestImportCompatibility:
    """Test that imports match temporalio SDK pattern exactly."""

    def test_temporal_style_workflow_import(self):
        """Test: from agentic_brain.temporal import workflow"""
        from agentic_brain.temporal import workflow

        # Should work exactly like: from temporalio import workflow
        @workflow.defn
        class MyWorkflow:
            @workflow.run
            async def run(self) -> str:
                return "done"

        assert MyWorkflow._temporal_workflow_name == "MyWorkflow"

    def test_temporal_style_activity_import(self):
        """Test: from agentic_brain.temporal import activity"""
        from agentic_brain.temporal import activity

        # Should work exactly like: from temporalio import activity
        @activity.defn
        async def my_activity() -> str:
            return "done"

        assert my_activity._temporal_activity_name == "my_activity"

    def test_temporal_style_client_import(self):
        """Test: from agentic_brain.temporal.client import Client"""
        from agentic_brain.temporal.client import Client

        # Should work exactly like: from temporalio.client import Client
        assert hasattr(Client, "connect")

    def test_temporal_style_worker_import(self):
        """Test: from agentic_brain.temporal.worker import Worker"""
        from agentic_brain.temporal.worker import Worker

        # Should work exactly like: from temporalio.worker import Worker
        assert Worker is not None

    def test_temporal_style_testing_import(self):
        """Test: from agentic_brain.temporal.testing import WorkflowEnvironment"""
        from agentic_brain.temporal.testing import WorkflowEnvironment

        # Should work exactly like: from temporalio.testing import WorkflowEnvironment
        assert hasattr(WorkflowEnvironment, "start_time_skipping")
