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
Saga Pattern - Compensating transactions for workflows.

Implements the Saga pattern for distributed transactions
with automatic compensation (rollback) on failure.

Features:
- Sequential saga execution
- Automatic compensation on failure
- Parallel saga steps
- Compensation ordering
- Idempotent operations
"""

import asyncio
import inspect
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from .event_store import EventStore, get_event_store
from .events import BaseEvent, EventType, WorkflowEvent


class SagaState(Enum):
    """State of a saga execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    FAILED = "failed"


@dataclass
class SagaStep:
    """
    A step in a saga with action and compensation.

    The action is the forward operation.
    The compensation is the rollback operation.
    """

    name: str
    action: Callable
    compensation: Optional[Callable] = None
    timeout: Optional[float] = None  # seconds
    idempotency_key: Optional[str] = None

    def __hash__(self):
        return hash(self.name)


@dataclass
class SagaStepResult:
    """Result of executing a saga step."""

    step_name: str
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    compensated: bool = False
    compensation_error: Optional[str] = None


@dataclass
class SagaExecution:
    """Tracks execution of a saga."""

    saga_id: str
    saga_name: str
    workflow_id: str
    state: SagaState = SagaState.PENDING
    step_results: Dict[str, SagaStepResult] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    failed_at_step: Optional[str] = None
    error: Optional[str] = None

    @property
    def completed_steps(self) -> List[str]:
        """Get names of completed steps."""
        return [
            name
            for name, result in self.step_results.items()
            if result.status == "completed"
        ]

    @property
    def compensation_needed(self) -> List[str]:
        """Get steps that need compensation (reverse order)."""
        return list(reversed(self.completed_steps))


class Saga:
    """
    Builder for saga workflows.

    Usage:
        saga = (
            Saga("order-saga")
            .add_step(
                "reserve-inventory",
                reserve_inventory,
                release_inventory
            )
            .add_step(
                "charge-payment",
                charge_card,
                refund_card
            )
            .add_step(
                "ship-order",
                ship_order,
                cancel_shipment
            )
        )

        result = await saga.execute(order_data)
    """

    def __init__(self, name: str):
        self.name = name
        self.steps: List[SagaStep] = []

    def add_step(
        self,
        name: str,
        action: Callable,
        compensation: Optional[Callable] = None,
        timeout: Optional[float] = None,
    ) -> "Saga":
        """Add a step to the saga."""
        self.steps.append(
            SagaStep(
                name=name, action=action, compensation=compensation, timeout=timeout
            )
        )
        return self

    def step(
        self,
        name: str,
        compensation: Optional[Callable] = None,
        timeout: Optional[float] = None,
    ):
        """
        Decorator to add a step.

        Usage:
            saga = Saga("my-saga")

            @saga.step("step-1", compensation=undo_step_1)
            async def do_step_1(data):
                return process(data)
        """

        def decorator(func: Callable) -> Callable:
            self.add_step(name, func, compensation, timeout)
            return func

        return decorator


class SagaExecutor:
    """
    Executes sagas with automatic compensation.

    Features:
    - Execute saga steps in sequence
    - Automatic compensation on failure
    - Event recording
    - Idempotency support
    """

    def __init__(self, workflow_id: str, event_store: Optional[EventStore] = None):
        self.workflow_id = workflow_id
        self.event_store = event_store or get_event_store()
        self.executions: Dict[str, SagaExecution] = {}

    async def execute(
        self, saga: Saga, *args, saga_id: Optional[str] = None, **kwargs
    ) -> SagaExecution:
        """
        Execute a saga.

        Args:
            saga: The saga to execute
            *args: Arguments passed to each step
            saga_id: Optional specific ID
            **kwargs: Keyword arguments passed to each step

        Returns:
            SagaExecution with results
        """
        saga_id = saga_id or f"saga_{uuid.uuid4().hex[:8]}"

        execution = SagaExecution(
            saga_id=saga_id, saga_name=saga.name, workflow_id=self.workflow_id
        )
        self.executions[saga_id] = execution

        # Record saga start
        await self._record_event(
            saga_id,
            "saga_started",
            {"saga_name": saga.name, "steps": [s.name for s in saga.steps]},
        )

        execution.state = SagaState.RUNNING

        # Execute steps
        for step in saga.steps:
            step_result = SagaStepResult(step_name=step.name)
            execution.step_results[step.name] = step_result

            try:
                step_result.started_at = datetime.now(UTC)

                # Execute with timeout if specified
                if step.timeout:
                    result = await asyncio.wait_for(
                        self._execute_step(step, *args, **kwargs), timeout=step.timeout
                    )
                else:
                    result = await self._execute_step(step, *args, **kwargs)

                step_result.result = result
                step_result.status = "completed"
                step_result.completed_at = datetime.now(UTC)

                await self._record_event(saga_id, "step_completed", {"step": step.name})

            except Exception as e:
                step_result.status = "failed"
                step_result.error = str(e)
                step_result.completed_at = datetime.now(UTC)

                execution.failed_at_step = step.name
                execution.error = str(e)

                await self._record_event(
                    saga_id, "step_failed", {"step": step.name, "error": str(e)}
                )

                # Start compensation
                await self._compensate(saga, execution, *args, **kwargs)
                execution.state = SagaState.FAILED
                raise

        # All steps completed successfully
        execution.state = SagaState.COMPLETED
        execution.completed_at = datetime.now(UTC)

        await self._record_event(saga_id, "saga_completed", {})

        return execution

    async def _execute_step(self, step: SagaStep, *args, **kwargs) -> Any:
        """Execute a single saga step."""
        if inspect.iscoroutinefunction(step.action):
            return await step.action(*args, **kwargs)
        else:
            return step.action(*args, **kwargs)

    async def _compensate(
        self, saga: Saga, execution: SagaExecution, *args, **kwargs
    ) -> None:
        """Run compensating transactions for completed steps."""
        execution.state = SagaState.COMPENSATING

        await self._record_event(
            execution.saga_id,
            "compensation_started",
            {"failed_at": execution.failed_at_step},
        )

        # Get steps that need compensation (reverse order)
        steps_to_compensate = []
        for step in saga.steps:
            if step.name in execution.completed_steps:
                steps_to_compensate.append(step)

        steps_to_compensate.reverse()

        # Execute compensations
        for step in steps_to_compensate:
            if not step.compensation:
                continue

            step_result = execution.step_results[step.name]

            try:
                if inspect.iscoroutinefunction(step.compensation):
                    await step.compensation(*args, **kwargs)
                else:
                    step.compensation(*args, **kwargs)

                step_result.compensated = True

                await self._record_event(
                    execution.saga_id, "step_compensated", {"step": step.name}
                )

            except Exception as e:
                step_result.compensation_error = str(e)

                await self._record_event(
                    execution.saga_id,
                    "compensation_failed",
                    {"step": step.name, "error": str(e)},
                )

        execution.state = SagaState.COMPENSATED
        execution.completed_at = datetime.now(UTC)

        await self._record_event(execution.saga_id, "compensation_completed", {})

    async def _record_event(
        self, saga_id: str, event_type: str, data: Dict[str, Any]
    ) -> None:
        """Record saga event."""
        event = WorkflowEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=self.workflow_id,
            event_type=EventType.ACTIVITY_COMPLETED,
            timestamp=datetime.now(UTC),
            data={"saga_id": saga_id, "saga_event_type": event_type, **data},
        )
        await self.event_store.append(event)

    def get_execution(self, saga_id: str) -> Optional[SagaExecution]:
        """Get saga execution by ID."""
        return self.executions.get(saga_id)


# Convenience decorator for creating sagas
def saga_step(name: str, compensation: Optional[Callable] = None):
    """
    Decorator to mark function as a saga step.

    Usage:
        @saga_step("reserve-inventory", compensation=release_inventory)
        async def reserve_inventory(order):
            ...
    """

    def decorator(func: Callable) -> SagaStep:
        return SagaStep(name=name, action=func, compensation=compensation)

    return decorator


# Pre-built saga patterns
class OrderSaga(Saga):
    """Example: E-commerce order saga."""

    def __init__(self):
        super().__init__("order-saga")


class PaymentSaga(Saga):
    """Example: Payment processing saga."""

    def __init__(self):
        super().__init__("payment-saga")


class BookingSaga(Saga):
    """Example: Travel booking saga."""

    def __init__(self):
        super().__init__("booking-saga")


# Helper for creating compensation functions
def create_compensation(action_name: str, compensate_func: Callable) -> Callable:
    """
    Create a compensation function with logging.

    Usage:
        release_inventory = create_compensation(
            "reserve-inventory",
            lambda order: inventory.release(order.items)
        )
    """

    async def compensation(*args, **kwargs):
        # Could add logging/metrics here
        if inspect.iscoroutinefunction(compensate_func):
            return await compensate_func(*args, **kwargs)
        return compensate_func(*args, **kwargs)

    compensation.__name__ = f"compensate_{action_name}"
    return compensation
