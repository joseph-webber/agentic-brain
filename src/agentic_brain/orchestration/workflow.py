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
Workflow class for defining complex multi-step agent workflows.

Features:
- Step-based workflow execution
- Branching logic (if/else, switch)
- Error handling and retries
- State machine for complex flows
- Conditional transitions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class WorkflowState(StrEnum):
    """Workflow execution states."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransitionType(StrEnum):
    """Types of transitions between steps."""

    ALWAYS = "always"  # Always transition
    ON_SUCCESS = "on_success"  # Only if previous step succeeded
    ON_FAILURE = "on_failure"  # Only if previous step failed
    CONDITIONAL = "conditional"  # Custom condition function


@dataclass
class Transition:
    """Transition from one step to another."""

    to_step: str
    type: TransitionType = TransitionType.ALWAYS
    condition: Callable[[dict[str, Any]], bool] | None = None

    def should_transition(self, context: dict[str, Any]) -> bool:
        """Check if transition should occur."""
        if self.type == TransitionType.ALWAYS:
            return True
        elif self.type == TransitionType.ON_SUCCESS:
            return context.get("_last_success", False)
        elif self.type == TransitionType.ON_FAILURE:
            return not context.get("_last_success", True)
        elif self.type == TransitionType.CONDITIONAL and self.condition:
            try:
                return self.condition(context)
            except Exception as e:
                logger.error(f"Error evaluating condition: {e}")
                return False
        return False


@dataclass
class WorkflowStep:
    """Single step in a workflow."""

    name: str
    execute: Callable[[dict[str, Any]], Any]  # Execution function
    transitions: list[Transition] = field(default_factory=list)
    retry_count: int = 0
    timeout: float | None = None
    skip_condition: Callable[[dict[str, Any]], bool] | None = None
    on_error: Callable[[Exception, dict[str, Any]], None] | None = None
    description: str = ""

    def should_skip(self, context: dict[str, Any]) -> bool:
        """Check if step should be skipped."""
        if self.skip_condition:
            try:
                return self.skip_condition(context)
            except Exception as e:
                logger.error(f"Error evaluating skip condition: {e}")
                return False
        return False

    def run(
        self,
        context: dict[str, Any],
        timeout: float | None = None,
    ) -> tuple[bool, Any, Exception | None]:
        """
        Execute the step.

        Args:
            context: Workflow context
            timeout: Optional timeout override

        Returns:
            Tuple of (success, result, error)
        """
        import time
        from concurrent.futures import (
            ThreadPoolExecutor,
        )
        from concurrent.futures import (
            TimeoutError as FuturesTimeoutError,
        )

        timeout = timeout or self.timeout
        attempts = 0
        last_error = None

        while attempts <= self.retry_count:
            try:
                # Execute with proper timeout enforcement using ThreadPoolExecutor
                if timeout:
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(self.execute, context)
                        try:
                            result = future.result(timeout=timeout)
                        except FuturesTimeoutError:
                            raise TimeoutError(
                                f"Step '{self.name}' exceeded timeout of {timeout}s"
                            )
                else:
                    result = self.execute(context)

                return (True, result, None)

            except Exception as e:
                last_error = e
                attempts += 1

                if self.on_error:
                    try:
                        self.on_error(e, context)
                    except Exception as handler_error:
                        logger.error(f"Error in on_error handler: {handler_error}")

                if attempts <= self.retry_count:
                    logger.warning(
                        f"Step '{self.name}' failed (attempt {attempts}/{self.retry_count}), retrying..."
                    )
                    time.sleep(0.5 * attempts)  # Exponential backoff

        return (False, None, last_error)


@dataclass
class WorkflowResult:
    """Result from workflow execution."""

    state: WorkflowState
    steps_executed: list[str] = field(default_factory=list)
    step_results: dict[str, Any] = field(default_factory=dict)
    step_errors: dict[str, Exception] = field(default_factory=dict)
    final_context: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None

    def success(self) -> bool:
        """Check if workflow succeeded."""
        return self.state == WorkflowState.COMPLETED

    def get_step_result(self, step_name: str) -> Any:
        """Get result from specific step."""
        return self.step_results.get(step_name)

    def get_step_error(self, step_name: str) -> Exception | None:
        """Get error from specific step."""
        return self.step_errors.get(step_name)


class Workflow:
    """
    Multi-step workflow with branching and state management.

    Example:
        >>> workflow = Workflow(start_step="fetch_data")
        >>> workflow.add_step(
        ...     WorkflowStep(
        ...         name="fetch_data",
        ...         execute=fetch_fn,
        ...         transitions=[Transition(to_step="process")]
        ...     )
        ... )
        >>> workflow.add_step(
        ...     WorkflowStep(
        ...         name="process",
        ...         execute=process_fn,
        ...         transitions=[Transition(to_step="save")]
        ...     )
        ... )
        >>> result = workflow.run()
    """

    def __init__(self, start_step: str) -> None:
        """
        Initialize workflow.

        Args:
            start_step: Name of first step to execute
        """
        self.start_step = start_step
        self.steps: dict[str, WorkflowStep] = {}
        self.state = WorkflowState.PENDING
        self.last_result: WorkflowResult | None = None

    def add_step(self, step: WorkflowStep) -> Workflow:
        """Add a step to the workflow (fluent API)."""
        self.steps[step.name] = step
        return self

    def add_steps(self, steps: list[WorkflowStep]) -> Workflow:
        """Add multiple steps (fluent API)."""
        for step in steps:
            self.add_step(step)
        return self

    def get_step(self, name: str) -> WorkflowStep | None:
        """Get step by name."""
        return self.steps.get(name)

    def run(
        self,
        context: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> WorkflowResult:
        """
        Execute the workflow.

        Args:
            context: Optional initial context
            timeout: Optional total timeout

        Returns:
            WorkflowResult with execution details
        """
        import time

        start_time = time.time()
        context = context or {}
        result = WorkflowResult(state=WorkflowState.RUNNING)

        # Validate start step exists
        if self.start_step not in self.steps:
            result.state = WorkflowState.FAILED
            result.error = f"Start step '{self.start_step}' not found"
            return result

        self.state = WorkflowState.RUNNING
        current_step_name = self.start_step
        visited_steps = set()

        try:
            while current_step_name:
                # Prevent infinite loops
                if current_step_name in visited_steps:
                    result.state = WorkflowState.FAILED
                    result.error = (
                        f"Infinite loop detected at step '{current_step_name}'"
                    )
                    break

                visited_steps.add(current_step_name)

                # Check timeout
                if timeout and (time.time() - start_time) > timeout:
                    result.state = WorkflowState.FAILED
                    result.error = "Workflow timeout exceeded"
                    break

                # Get step
                step = self.steps.get(current_step_name)
                if not step:
                    result.state = WorkflowState.FAILED
                    result.error = f"Step '{current_step_name}' not found"
                    break

                # Check if should skip
                if step.should_skip(context):
                    logger.info(f"Skipping step: {current_step_name}")
                    context["_last_success"] = True
                    current_step_name = self._find_next_step(step, context)
                    continue

                # Execute step
                logger.info(f"Executing step: {current_step_name}")
                success, step_result, error = step.run(context)

                result.steps_executed.append(current_step_name)
                result.step_results[current_step_name] = step_result

                if error:
                    result.step_errors[current_step_name] = error

                # Update context
                context[f"{current_step_name}_result"] = step_result
                context["_last_success"] = success
                context["_last_error"] = error

                if not success:
                    logger.error(f"Step failed: {current_step_name}, error: {error}")

                # Find next step
                current_step_name = self._find_next_step(step, context)

            # Determine final state
            if result.state == WorkflowState.RUNNING:
                if result.step_errors:
                    result.state = WorkflowState.FAILED
                else:
                    result.state = WorkflowState.COMPLETED

        except Exception as e:
            logger.error(f"Workflow error: {e}")
            result.state = WorkflowState.FAILED
            result.error = str(e)

        finally:
            result.duration_ms = (time.time() - start_time) * 1000
            result.final_context = dict(context)
            self.state = result.state
            self.last_result = result

        return result

    def _find_next_step(
        self,
        current_step: WorkflowStep,
        context: dict[str, Any],
    ) -> str | None:
        """Find the next step based on transitions."""
        if not current_step.transitions:
            return None

        for transition in current_step.transitions:
            if transition.should_transition(context):
                return transition.to_step

        return None

    def get_state(self) -> WorkflowState:
        """Get current workflow state."""
        return self.state

    def pause(self) -> None:
        """Pause workflow execution."""
        self.state = WorkflowState.PAUSED

    def cancel(self) -> None:
        """Cancel workflow execution."""
        self.state = WorkflowState.CANCELLED

    def reset(self) -> None:
        """Reset workflow to pending state."""
        self.state = WorkflowState.PENDING
        self.last_result = None


# Helper functions for common workflow patterns


def branch_if(
    condition: Callable[[dict[str, Any]], bool],
    true_step: str,
    false_step: str | None = None,
) -> list[Transition]:
    """Create if/else branching transitions."""
    transitions = [
        Transition(
            to_step=true_step,
            type=TransitionType.CONDITIONAL,
            condition=condition,
        )
    ]
    if false_step:
        transitions.append(
            Transition(
                to_step=false_step,
                type=TransitionType.CONDITIONAL,
                condition=lambda ctx: not condition(ctx),
            )
        )
    return transitions


def on_success(next_step: str) -> list[Transition]:
    """Transition only on success."""
    return [Transition(to_step=next_step, type=TransitionType.ON_SUCCESS)]


def on_failure(next_step: str) -> list[Transition]:
    """Transition only on failure."""
    return [Transition(to_step=next_step, type=TransitionType.ON_FAILURE)]


def always(next_step: str) -> list[Transition]:
    """Always transition to next step."""
    return [Transition(to_step=next_step, type=TransitionType.ALWAYS)]
