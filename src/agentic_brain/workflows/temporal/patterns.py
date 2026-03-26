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

"""Durable execution patterns for Temporal workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Optional

# Optional dependency - graceful fallback if not installed
try:
    from temporalio import workflow
    from temporalio.common import RetryPolicy
    TEMPORALIO_AVAILABLE = True
except ImportError:
    TEMPORALIO_AVAILABLE = False
    # Create stub for workflow decorators
    class _WorkflowStub:
        @staticmethod
        def defn(cls):
            return cls
        @staticmethod
        def run(fn):
            return fn
        @staticmethod
        def signal(name=None):
            def decorator(fn):
                return fn
            return decorator
        @staticmethod
        def query(name=None):
            def decorator(fn):
                return fn
            return decorator
    workflow = _WorkflowStub()
    RetryPolicy = None  # type: ignore

from . import activities


@dataclass
class SagaStep:
    """A step in a saga transaction."""

    name: str
    action: Callable
    compensation: Callable
    params: dict[str, Any]


class SagaPattern:
    """Saga pattern for distributed transactions with compensations."""

    def __init__(self):
        """Initialize saga pattern."""
        self.steps: list[SagaStep] = []
        self.executed_steps: list[SagaStep] = []

    def add_step(
        self,
        name: str,
        action: Callable,
        compensation: Callable,
        params: dict[str, Any],
    ) -> SagaPattern:
        """Add a step to the saga.

        Args:
            name: Step name.
            action: Forward action to execute.
            compensation: Compensation action for rollback.
            params: Step parameters.

        Returns:
            Self for chaining.
        """
        self.steps.append(
            SagaStep(
                name=name,
                action=action,
                compensation=compensation,
                params=params,
            )
        )
        return self

    async def execute(self) -> dict[str, Any]:
        """Execute saga with automatic rollback on failure.

        Returns:
            Saga execution result.
        """
        try:
            results = []

            for step in self.steps:
                workflow.logger.info(f"Executing saga step: {step.name}")

                result = await workflow.execute_activity(
                    step.action,
                    args=[step.params],
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )

                results.append({"step": step.name, "result": result})
                self.executed_steps.append(step)

            return {"success": True, "results": results}

        except Exception as e:
            workflow.logger.error(f"Saga failed at step, rolling back: {e}")

            # Execute compensations in reverse order
            for step in reversed(self.executed_steps):
                try:
                    workflow.logger.info(f"Compensating saga step: {step.name}")
                    await workflow.execute_activity(
                        step.compensation,
                        args=[step.params],
                        start_to_close_timeout=timedelta(seconds=60),
                    )
                except Exception as comp_error:
                    workflow.logger.error(
                        f"Compensation failed for {step.name}: {comp_error}"
                    )

            return {
                "success": False,
                "error": str(e),
                "compensated_steps": len(self.executed_steps),
            }


@workflow.defn
class HumanInTheLoopWorkflow:
    """Workflow that requires human approval or input."""

    def __init__(self):
        """Initialize human-in-the-loop workflow."""
        self._approval_signal = workflow.SignalDefinition(name="approval")
        self._rejection_signal = workflow.SignalDefinition(name="rejection")
        self._approved: Optional[bool] = None
        self._feedback: Optional[str] = None

    @workflow.signal(name="approval")
    async def approval(self, feedback: str = "") -> None:
        """Signal approval from human.

        Args:
            feedback: Optional feedback from approver.
        """
        self._approved = True
        self._feedback = feedback

    @workflow.signal(name="rejection")
    async def rejection(self, reason: str = "") -> None:
        """Signal rejection from human.

        Args:
            reason: Rejection reason.
        """
        self._approved = False
        self._feedback = reason

    @workflow.run
    async def run(
        self,
        task: str,
        auto_approve_after: Optional[int] = None,
    ) -> dict[str, Any]:
        """Execute workflow with human approval.

        Args:
            task: Task requiring approval.
            auto_approve_after: Auto-approve after N seconds (optional).

        Returns:
            Workflow result with approval status.
        """
        workflow.logger.info(f"Starting task requiring approval: {task}")

        # Execute preliminary work
        preliminary = await workflow.execute_activity(
            activities.llm_query,
            args=[f"Prepare task: {task}", {}, "gpt-4"],
            start_to_close_timeout=timedelta(seconds=60),
        )

        # Send notification for approval
        await workflow.execute_activity(
            activities.send_notification,
            args=[
                "approval_required",
                {
                    "task": task,
                    "preliminary": preliminary,
                },
            ],
            start_to_close_timeout=timedelta(seconds=10),
        )

        workflow.logger.info("Waiting for human approval...")

        # Wait for approval signal
        if auto_approve_after:
            await workflow.wait_condition(
                lambda: self._approved is not None,
                timeout=timedelta(seconds=auto_approve_after),
            )
            # Auto-approve if timeout
            if self._approved is None:
                self._approved = True
                self._feedback = "Auto-approved after timeout"
        else:
            await workflow.wait_condition(lambda: self._approved is not None)

        if self._approved:
            workflow.logger.info(f"Task approved: {self._feedback}")

            # Execute main work
            result = await workflow.execute_activity(
                activities.llm_query,
                args=[f"Execute approved task: {task}", preliminary, "gpt-4"],
                start_to_close_timeout=timedelta(seconds=120),
            )

            return {
                "success": True,
                "approved": True,
                "result": result,
                "feedback": self._feedback,
            }
        else:
            workflow.logger.info(f"Task rejected: {self._feedback}")
            return {
                "success": False,
                "approved": False,
                "reason": self._feedback,
            }


@workflow.defn
class ScheduledWorkflow:
    """Workflow that executes on a schedule."""

    @workflow.run
    async def run(
        self,
        task: str,
        interval_seconds: int = 3600,
        max_iterations: int = 24,
    ) -> dict[str, Any]:
        """Execute task on schedule.

        Args:
            task: Task to execute.
            interval_seconds: Interval between executions.
            max_iterations: Maximum iterations.

        Returns:
            Aggregated results.
        """
        workflow.logger.info(
            f"Starting scheduled task: {task} "
            f"(interval={interval_seconds}s, max={max_iterations})"
        )

        results = []

        for i in range(max_iterations):
            workflow.logger.info(f"Scheduled execution {i+1}/{max_iterations}")

            result = await workflow.execute_activity(
                activities.llm_query,
                args=[f"Execute scheduled task: {task}", {"iteration": i}, "gpt-4"],
                start_to_close_timeout=timedelta(seconds=300),
            )

            results.append({"iteration": i, "result": result})

            # Sleep until next execution
            if i < max_iterations - 1:
                await workflow.sleep(interval_seconds)

        workflow.logger.info("Scheduled workflow completed")
        return {
            "success": True,
            "total_executions": len(results),
            "results": results,
        }


class ChildWorkflowManager:
    """Manager for child workflow execution."""

    @staticmethod
    async def execute_child(
        workflow_class: Any,
        workflow_id: str,
        args: list[Any],
        **kwargs: Any,
    ) -> Any:
        """Execute a child workflow.

        Args:
            workflow_class: Child workflow class.
            workflow_id: Child workflow ID.
            args: Workflow arguments.
            **kwargs: Additional options.

        Returns:
            Child workflow result.
        """
        workflow.logger.info(f"Starting child workflow: {workflow_id}")

        handle = await workflow.start_child_workflow(
            workflow_class,
            *args,
            id=workflow_id,
            **kwargs,
        )

        result = await handle.result()
        workflow.logger.info(f"Child workflow completed: {workflow_id}")
        return result

    @staticmethod
    async def execute_parallel_children(
        workflow_class: Any,
        tasks: list[dict[str, Any]],
    ) -> list[Any]:
        """Execute multiple child workflows in parallel.

        Args:
            workflow_class: Child workflow class.
            tasks: List of task definitions with id and args.

        Returns:
            List of child workflow results.
        """
        workflow.logger.info(f"Starting {len(tasks)} parallel child workflows")

        handles = []
        for task in tasks:
            handle = await workflow.start_child_workflow(
                workflow_class,
                *task.get("args", []),
                id=task["id"],
            )
            handles.append(handle)

        # Wait for all children to complete
        results = []
        for handle in handles:
            result = await handle.result()
            results.append(result)

        workflow.logger.info("All child workflows completed")
        return results
