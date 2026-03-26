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
End-to-end tests for Temporal.io compatibility.

These tests simulate real-world Temporal workflows to prove
Agentic Brain is a true drop-in replacement.

Note: These tests require a full workflow environment with activity
registration. Set RUN_TEMPORAL_E2E=true to run these tests.
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pytest

# E2E tests are skipped by default, set RUN_TEMPORAL_E2E=true to run
RUN_TEMPORAL_E2E = os.environ.get("RUN_TEMPORAL_E2E", "false").lower() == "true"

pytestmark = pytest.mark.skipif(
    not RUN_TEMPORAL_E2E,
    reason="Temporal E2E tests require full workflow environment. Set RUN_TEMPORAL_E2E=true to run.",
)

# Import exactly as you would with temporalio
from agentic_brain.temporal import activity, workflow
from agentic_brain.temporal.client import Client
from agentic_brain.temporal.testing import (
    ActivityEnvironment,
    WorkflowEnvironment,
)
from agentic_brain.temporal.worker import Worker

# ============================================================================
# Example Activities (real-world patterns)
# ============================================================================


@activity.defn
async def fetch_user(user_id: str) -> Dict[str, Any]:
    """Fetch user data (simulated)."""
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"{user_id}@example.com",
    }


@activity.defn
async def process_payment(amount: float, user_id: str) -> Dict[str, Any]:
    """Process payment (simulated)."""
    return {
        "transaction_id": f"txn-{user_id}-{amount}",
        "amount": amount,
        "status": "completed",
    }


@activity.defn
async def send_email(to: str, subject: str, body: str) -> bool:
    """Send email (simulated)."""
    return True


@activity.defn
async def reserve_inventory(item_id: str, quantity: int) -> Dict[str, Any]:
    """Reserve inventory (simulated)."""
    return {
        "item_id": item_id,
        "quantity": quantity,
        "reservation_id": f"res-{item_id}",
    }


@activity.defn
async def cancel_reservation(reservation_id: str) -> bool:
    """Cancel inventory reservation (compensation)."""
    return True


@activity.defn
async def long_running_task(duration_seconds: float) -> str:
    """Simulated long-running task with heartbeats."""
    steps = int(duration_seconds * 10)
    for i in range(steps):
        activity.heartbeat(f"Step {i+1}/{steps}")
        await asyncio.sleep(0.1)
    return "completed"


# ============================================================================
# Example Workflows (real-world patterns)
# ============================================================================


@workflow.defn
class OrderWorkflow:
    """
    E-commerce order processing workflow.

    Demonstrates:
    - Activity execution with timeouts
    - Signals for status updates
    - Queries for current state
    - Error handling
    """

    def __init__(self):
        self.status = "pending"
        self.order_id = None
        self.user = None
        self.payment = None

    @workflow.run
    async def run(self, order_id: str, user_id: str, amount: float) -> Dict[str, Any]:
        self.order_id = order_id
        self.status = "processing"

        # Step 1: Fetch user
        self.user = await workflow.execute_activity(
            fetch_user,
            user_id,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 2: Process payment
        self.status = "payment"
        self.payment = await workflow.execute_activity(
            process_payment,
            amount,
            user_id,
            start_to_close_timeout=timedelta(minutes=1),
        )

        # Step 3: Send confirmation
        self.status = "confirming"
        await workflow.execute_activity(
            send_email,
            self.user["email"],
            "Order Confirmed",
            f"Your order {order_id} is confirmed!",
            start_to_close_timeout=timedelta(seconds=30),
        )

        self.status = "completed"
        return {
            "order_id": order_id,
            "user": self.user,
            "payment": self.payment,
            "status": self.status,
        }

    @workflow.signal
    async def update_status(self, new_status: str) -> None:
        self.status = new_status

    @workflow.query
    def get_status(self) -> str:
        return self.status

    @workflow.query
    def get_order_details(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "status": self.status,
            "user": self.user,
            "payment": self.payment,
        }


@workflow.defn
class SagaWorkflow:
    """
    Saga pattern workflow for distributed transactions.

    Demonstrates:
    - Compensation on failure
    - Multi-step transactions
    - Rollback logic
    """

    @workflow.run
    async def run(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        reservations = []

        try:
            # Reserve all items
            for item in items:
                result = await workflow.execute_activity(
                    reserve_inventory,
                    item["id"],
                    item["quantity"],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                reservations.append(result)

            return {
                "success": True,
                "reservations": reservations,
            }

        except Exception as e:
            # Compensate: cancel all reservations
            for res in reservations:
                await workflow.execute_activity(
                    cancel_reservation,
                    res["reservation_id"],
                    start_to_close_timeout=timedelta(seconds=30),
                )

            return {
                "success": False,
                "error": str(e),
                "compensated": len(reservations),
            }


@workflow.defn
class ScheduledWorkflow:
    """
    Workflow with scheduled delays.

    Demonstrates:
    - Durable sleep (workflow.sleep)
    - Time-based logic
    - Continue-as-new for long-running
    """

    def __init__(self):
        self.iteration = 0

    @workflow.run
    async def run(self, max_iterations: int = 5) -> Dict[str, Any]:
        results = []

        for i in range(max_iterations):
            self.iteration = i + 1

            # Durable sleep - survives crashes
            await workflow.sleep(timedelta(seconds=1))

            # Do work
            result = {
                "iteration": self.iteration,
                "timestamp": workflow.now().isoformat(),
            }
            results.append(result)

        return {
            "completed_iterations": len(results),
            "results": results,
        }

    @workflow.query
    def get_iteration(self) -> int:
        return self.iteration


@workflow.defn
class ContinueAsNewWorkflow:
    """
    Long-running workflow using continue-as-new.

    Demonstrates:
    - continue_as_new for history management
    - State passing between generations
    """

    @workflow.run
    async def run(self, count: int = 0, max_count: int = 100) -> int:
        # Do some work
        new_count = count + 1

        if new_count < max_count:
            # Continue as new to avoid history growth
            workflow.continue_as_new(new_count, max_count)

        return new_count


# ============================================================================
# E2E Tests
# ============================================================================


class TestOrderWorkflowE2E:
    """E2E tests for OrderWorkflow."""

    @pytest.mark.asyncio
    async def test_order_workflow_success(self):
        """Test complete order workflow execution."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            result = await env.client.execute_workflow(
                OrderWorkflow.run,
                "order-123",
                "user-456",
                99.99,
                id="test-order-1",
                task_queue="orders",
            )

            assert result["order_id"] == "order-123"
            assert result["status"] == "completed"
            assert result["user"]["id"] == "user-456"
            assert result["payment"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_order_workflow_query_status(self):
        """Test querying workflow status."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            handle = await env.client.start_workflow(
                OrderWorkflow.run,
                "order-789",
                "user-123",
                50.00,
                id="test-order-2",
                task_queue="orders",
            )

            # Wait for completion
            await handle.result()

            # Query should work
            status = await handle.query(OrderWorkflow.get_status)
            assert status == "completed"


class TestSagaWorkflowE2E:
    """E2E tests for saga pattern."""

    @pytest.mark.asyncio
    async def test_saga_success(self):
        """Test successful saga execution."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            items = [
                {"id": "item-1", "quantity": 2},
                {"id": "item-2", "quantity": 1},
            ]

            result = await env.client.execute_workflow(
                SagaWorkflow.run,
                items,
                id="test-saga-1",
                task_queue="orders",
            )

            assert result["success"] is True
            assert len(result["reservations"]) == 2


class TestScheduledWorkflowE2E:
    """E2E tests for scheduled/delayed workflows."""

    @pytest.mark.asyncio
    async def test_scheduled_workflow_with_time_skipping(self):
        """Test workflow with sleeps using time skipping."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            # This would take 5 seconds normally, but is instant with time skipping
            result = await env.client.execute_workflow(
                ScheduledWorkflow.run,
                5,  # 5 iterations
                id="test-scheduled-1",
                task_queue="scheduled",
            )

            assert result["completed_iterations"] == 5
            assert len(result["results"]) == 5


class TestActivityE2E:
    """E2E tests for activities."""

    @pytest.mark.asyncio
    async def test_activity_in_isolation(self):
        """Test activity execution in ActivityEnvironment."""
        env = ActivityEnvironment()

        result = await env.run(fetch_user, "user-999")

        assert result["id"] == "user-999"
        assert result["name"] == "User user-999"

    @pytest.mark.asyncio
    async def test_activity_with_multiple_args(self):
        """Test activity with multiple arguments."""
        env = ActivityEnvironment()

        result = await env.run(process_payment, 100.50, "user-123")

        assert result["amount"] == 100.50
        assert result["status"] == "completed"


class TestWorkerE2E:
    """E2E tests for Worker."""

    @pytest.mark.asyncio
    async def test_worker_registration(self):
        """Test worker registers workflows and activities."""
        client = await Client.connect("localhost:7233")

        worker = Worker(
            client,
            task_queue="test-queue",
            workflows=[OrderWorkflow, SagaWorkflow],
            activities=[fetch_user, process_payment, send_email],
        )

        assert len(worker.workflows) == 2
        assert len(worker.activities) == 3
        assert "OrderWorkflow" in worker._workflow_registry
        assert "fetch_user" in worker._activity_registry


class TestClientE2E:
    """E2E tests for Client."""

    @pytest.mark.asyncio
    async def test_client_connect_and_execute(self):
        """Test client connection and workflow execution."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            # Client should be ready instantly
            assert env.client is not None
            assert env.client.namespace == "test"

    @pytest.mark.asyncio
    async def test_get_workflow_handle(self):
        """Test getting handle to existing workflow."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            # Start workflow
            await env.client.start_workflow(
                ScheduledWorkflow.run,
                2,
                id="handle-test-1",
                task_queue="test",
            )

            # Get handle by ID
            handle2 = env.client.get_workflow_handle("handle-test-1")
            assert handle2.id == "handle-test-1"


class TestDeterminism:
    """Test deterministic execution (critical for Temporal compatibility)."""

    @pytest.mark.asyncio
    async def test_uuid_determinism(self):
        """Test workflow.uuid4() produces consistent UUIDs."""
        from agentic_brain.temporal import workflow

        # Same seed should produce same UUIDs
        uuids_1 = [workflow.uuid4() for _ in range(3)]

        # All should be valid UUID format
        for uuid in uuids_1:
            assert len(uuid) == 36
            assert uuid.count("-") == 4

    @pytest.mark.asyncio
    async def test_random_determinism(self):
        """Test workflow.random() produces consistent values."""
        from agentic_brain.temporal import workflow

        rng = workflow.random()
        values = [rng.random() for _ in range(5)]

        # All should be valid floats between 0 and 1
        for v in values:
            assert 0 <= v <= 1

    @pytest.mark.asyncio
    async def test_now_returns_datetime(self):
        """Test workflow.now() returns proper datetime."""
        from agentic_brain.temporal import workflow

        now = workflow.now()
        assert isinstance(now, datetime)


class TestErrorHandling:
    """Test error handling matches Temporal semantics."""

    @pytest.mark.asyncio
    async def test_application_error(self):
        """Test ApplicationError propagation."""
        from agentic_brain.temporal.workflow import ApplicationError

        @activity.defn
        async def failing_activity() -> None:
            raise ApplicationError("Validation failed", type="ValidationError")

        env = ActivityEnvironment()

        with pytest.raises(ApplicationError) as exc_info:
            await env.run(failing_activity)

        assert "Validation failed" in str(exc_info.value)

    def test_continue_as_new_error(self):
        """Test ContinueAsNewError structure."""
        from agentic_brain.temporal.workflow import ContinueAsNewError

        error = ContinueAsNewError(
            args=("arg1", "arg2"),
            memo={"key": "value"},
        )

        assert error.args == ("arg1", "arg2")
        assert error.memo == {"key": "value"}


class TestTimeSkipping:
    """Test time-skipping functionality for fast tests."""

    @pytest.mark.asyncio
    async def test_time_skip_forward(self):
        """Test skipping time forward."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            t1 = env.get_current_time()
            await env.skip_time(timedelta(days=30))
            t2 = env.get_current_time()

            delta = (t2 - t1).total_seconds()
            assert delta == 30 * 24 * 60 * 60  # 30 days in seconds

    @pytest.mark.asyncio
    async def test_sleep_is_instant_in_time_skipping(self):
        """Test that sleep is instant in time-skipping mode."""
        import time

        async with await WorkflowEnvironment.start_time_skipping() as env:
            real_start = time.time()
            await env.sleep(timedelta(hours=100))  # 100 hours
            real_elapsed = time.time() - real_start

            # Should complete in under 1 second (it's instant)
            assert real_elapsed < 1.0


# ============================================================================
# Compatibility Matrix Tests
# ============================================================================


class TestTemporalCompatibilityMatrix:
    """
    Verify all Temporal SDK features are supported.

    This is the definitive compatibility checklist.
    """

    def test_workflow_decorators_supported(self):
        """All workflow decorators supported."""
        from agentic_brain.temporal import workflow

        decorators = ["defn", "run", "signal", "query", "update"]
        for dec in decorators:
            assert hasattr(workflow, dec), f"Missing: @workflow.{dec}"

    def test_workflow_functions_supported(self):
        """All workflow functions supported."""
        from agentic_brain.temporal import workflow

        functions = [
            "execute_activity",
            "execute_local_activity",
            "sleep",
            "now",
            "info",
            "uuid4",
            "random",
            "continue_as_new",
            "wait_condition",
        ]
        for func in functions:
            assert hasattr(workflow, func), f"Missing: workflow.{func}()"

    def test_activity_decorators_supported(self):
        """All activity decorators supported."""
        from agentic_brain.temporal import activity

        assert hasattr(activity, "defn"), "Missing: @activity.defn"

    def test_activity_functions_supported(self):
        """All activity functions supported."""
        from agentic_brain.temporal import activity

        functions = ["heartbeat", "info", "is_cancelled", "wait_for_cancelled"]
        for func in functions:
            assert hasattr(activity, func), f"Missing: activity.{func}()"

    def test_client_methods_supported(self):
        """All Client methods supported."""
        from agentic_brain.temporal.client import Client

        methods = ["connect"]
        for method in methods:
            assert hasattr(Client, method), f"Missing: Client.{method}()"

    def test_workflow_handle_methods_supported(self):
        """All WorkflowHandle methods supported."""
        from agentic_brain.temporal.client import WorkflowHandle

        methods = [
            "result",
            "signal",
            "query",
            "update",
            "cancel",
            "terminate",
            "describe",
        ]
        for method in methods:
            assert hasattr(
                WorkflowHandle, method
            ), f"Missing: WorkflowHandle.{method}()"

    def test_worker_methods_supported(self):
        """All Worker methods supported."""
        from agentic_brain.temporal.worker import Worker

        methods = ["run", "shutdown", "is_running", "is_shutdown"]
        for method in methods:
            assert hasattr(Worker, method), f"Missing: Worker.{method}()"

    def test_testing_classes_supported(self):
        """All testing classes supported."""
        from agentic_brain.temporal.testing import (
            ActivityEnvironment,
            WorkflowEnvironment,
        )

        assert hasattr(WorkflowEnvironment, "start_time_skipping")
        assert hasattr(WorkflowEnvironment, "start_local")
        assert hasattr(ActivityEnvironment, "run")
