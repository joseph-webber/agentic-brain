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
Continue-As-New - Restart workflow with fresh history.

Enables long-running workflows to reset their event history
to prevent unbounded growth while maintaining workflow identity.

Features:
- Fresh history with carried state
- Same workflow ID, new run ID
- Automatic trigger on history size
- State serialization/deserialization
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from .event_store import EventStore, get_event_store
from .events import BaseEvent, EventType, WorkflowEvent


class ContinueAsNewError(Exception):
    """
    Raised to trigger continue-as-new behavior.

    When raised within a workflow, the workflow engine catches this
    and restarts the workflow with fresh history.
    """

    def __init__(
        self,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        workflow_type: Optional[str] = None,
        task_queue: Optional[str] = None,
        run_timeout: Optional[float] = None,
        memo: Optional[Dict[str, Any]] = None,
        search_attributes: Optional[Dict[str, Any]] = None,
    ):
        self.args = args
        self.kwargs = kwargs or {}
        self.workflow_type = workflow_type
        self.task_queue = task_queue
        self.run_timeout = run_timeout
        self.memo = memo
        self.search_attributes = search_attributes
        super().__init__("Continue as new requested")


@dataclass
class ContinueAsNewOptions:
    """Configuration for continue-as-new behavior."""

    workflow_type: Optional[str] = None  # Change workflow type
    task_queue: Optional[str] = None  # Change task queue
    run_timeout: Optional[float] = None  # New run timeout
    memo: Optional[Dict[str, Any]] = None  # Updated memo
    search_attributes: Optional[Dict[str, Any]] = None

    # Auto-continue settings
    auto_continue_threshold: int = 10000  # Events before auto-continue
    auto_continue_enabled: bool = True


@dataclass
class WorkflowRun:
    """Represents a single run of a workflow."""

    run_id: str
    workflow_id: str
    workflow_type: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = "running"
    event_count: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    continued_as_new: bool = False
    next_run_id: Optional[str] = None
    previous_run_id: Optional[str] = None


class ContinueAsNewManager:
    """
    Manages continue-as-new behavior for workflows.

    Features:
    - Track workflow runs with run IDs
    - Handle continue-as-new transitions
    - Preserve state across continuations
    - Auto-continue on history threshold
    """

    def __init__(
        self,
        event_store: Optional[EventStore] = None,
        options: Optional[ContinueAsNewOptions] = None,
    ):
        self.event_store = event_store or get_event_store()
        self.options = options or ContinueAsNewOptions()
        self.runs: Dict[str, WorkflowRun] = {}
        self.workflow_runs: Dict[str, list] = {}  # workflow_id -> [run_ids]

    def create_run(
        self,
        workflow_id: str,
        workflow_type: str,
        previous_run_id: Optional[str] = None,
    ) -> WorkflowRun:
        """Create a new workflow run."""
        run_id = f"run_{uuid.uuid4().hex[:12]}"

        run = WorkflowRun(
            run_id=run_id,
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            previous_run_id=previous_run_id,
        )

        self.runs[run_id] = run

        # Track runs per workflow
        if workflow_id not in self.workflow_runs:
            self.workflow_runs[workflow_id] = []
        self.workflow_runs[workflow_id].append(run_id)

        # Link previous run
        if previous_run_id and previous_run_id in self.runs:
            self.runs[previous_run_id].next_run_id = run_id

        return run

    def get_current_run(self, workflow_id: str) -> Optional[WorkflowRun]:
        """Get the current (latest) run for a workflow."""
        run_ids = self.workflow_runs.get(workflow_id, [])
        if not run_ids:
            return None
        return self.runs.get(run_ids[-1])

    def get_run_history(self, workflow_id: str) -> list:
        """Get all runs for a workflow in order."""
        run_ids = self.workflow_runs.get(workflow_id, [])
        return [self.runs[rid] for rid in run_ids if rid in self.runs]

    async def check_auto_continue(self, workflow_id: str, run_id: str) -> bool:
        """
        Check if workflow should auto-continue based on event count.

        Returns True if continue-as-new should be triggered.
        """
        if not self.options.auto_continue_enabled:
            return False

        run = self.runs.get(run_id)
        if not run:
            return False

        # Count events for this run
        events = await self.event_store.get_events(workflow_id)
        # Only count events from this run (after run start)
        run_events = [e for e in events if e.timestamp >= run.started_at]
        run.event_count = len(run_events)

        return run.event_count >= self.options.auto_continue_threshold

    async def execute_continue_as_new(
        self,
        workflow_id: str,
        current_run_id: str,
        workflow_func: Callable,
        continue_error: ContinueAsNewError,
    ) -> Any:
        """
        Execute continue-as-new transition.

        Args:
            workflow_id: The workflow ID (stays same)
            current_run_id: Current run being replaced
            workflow_func: Workflow function to execute
            continue_error: ContinueAsNewError with new args

        Returns:
            Result from new workflow run
        """
        # Mark current run as continued
        current_run = self.runs.get(current_run_id)
        if current_run:
            current_run.status = "continued_as_new"
            current_run.continued_as_new = True
            current_run.completed_at = datetime.now(timezone.utc)

        # Record continue event
        event = WorkflowEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.WORKFLOW_COMPLETED,
            timestamp=datetime.now(timezone.utc),
            data={
                "continued_as_new": True,
                "previous_run_id": current_run_id,
                "new_args": continue_error.args,
                "new_kwargs": continue_error.kwargs,
            },
        )
        await self.event_store.append(event)

        # Create new run
        workflow_type = continue_error.workflow_type or (
            current_run.workflow_type if current_run else "unknown"
        )

        new_run = self.create_run(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            previous_run_id=current_run_id,
        )

        # Record new run start
        start_event = WorkflowEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.WORKFLOW_STARTED,
            timestamp=datetime.now(timezone.utc),
            data={
                "run_id": new_run.run_id,
                "continued_from": current_run_id,
                "args": continue_error.args,
                "kwargs": continue_error.kwargs,
            },
        )
        await self.event_store.append(start_event)

        # Execute workflow with new args
        try:
            result = await workflow_func(*continue_error.args, **continue_error.kwargs)

            new_run.status = "completed"
            new_run.result = result
            new_run.completed_at = datetime.now(timezone.utc)

            return result

        except ContinueAsNewError as e:
            # Recursive continue-as-new
            return await self.execute_continue_as_new(
                workflow_id=workflow_id,
                current_run_id=new_run.run_id,
                workflow_func=workflow_func,
                continue_error=e,
            )
        except Exception as e:
            new_run.status = "failed"
            new_run.error = str(e)
            new_run.completed_at = datetime.now(timezone.utc)
            raise


def continue_as_new(
    *args,
    workflow_type: Optional[str] = None,
    task_queue: Optional[str] = None,
    memo: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> None:
    """
    Trigger continue-as-new from within a workflow.

    This raises ContinueAsNewError which is caught by the
    workflow executor to restart the workflow.

    Usage:
        @workflow
        async def my_workflow(items: list, processed: int = 0):
            for i, item in enumerate(items[processed:], processed):
                await process_item(item)

                # Continue as new every 100 items
                if (i + 1) % 100 == 0 and i + 1 < len(items):
                    continue_as_new(items, processed=i + 1)

            return {"processed": len(items)}
    """
    raise ContinueAsNewError(
        args=args,
        kwargs=kwargs,
        workflow_type=workflow_type,
        task_queue=task_queue,
        memo=memo,
    )


class ContinueAsNewWorkflowWrapper:
    """
    Wrapper that adds continue-as-new support to a workflow.

    Usage:
        @workflow(name="batch-processor")
        class BatchProcessor(DurableWorkflow):
            def __init__(self):
                super().__init__()
                self.continue_manager = ContinueAsNewManager()

            async def run(self, items: list, offset: int = 0):
                # Process batch
                for i in range(offset, min(offset + 100, len(items))):
                    await self.execute_activity("process", items[i])

                # Continue as new if more items
                if offset + 100 < len(items):
                    continue_as_new(items, offset=offset + 100)

                return {"total": len(items)}
    """

    def __init__(
        self,
        workflow_func: Callable,
        options: Optional[ContinueAsNewOptions] = None,
        event_store: Optional[EventStore] = None,
    ):
        self.workflow_func = workflow_func
        self.options = options or ContinueAsNewOptions()
        self.manager = ContinueAsNewManager(event_store=event_store, options=options)

    async def execute(self, workflow_id: str, *args, **kwargs) -> Any:
        """Execute workflow with continue-as-new support."""
        # Create initial run
        workflow_type = getattr(
            self.workflow_func, "_workflow_name", self.workflow_func.__name__
        )

        run = self.manager.create_run(
            workflow_id=workflow_id, workflow_type=workflow_type
        )

        try:
            result = await self.workflow_func(*args, **kwargs)
            run.status = "completed"
            run.result = result
            run.completed_at = datetime.now(timezone.utc)
            return result

        except ContinueAsNewError as e:
            return await self.manager.execute_continue_as_new(
                workflow_id=workflow_id,
                current_run_id=run.run_id,
                workflow_func=self.workflow_func,
                continue_error=e,
            )


def with_continue_as_new(
    options: Optional[ContinueAsNewOptions] = None,
    event_store: Optional[EventStore] = None,
):
    """
    Decorator to add continue-as-new support to a workflow.

    Usage:
        @with_continue_as_new(options=ContinueAsNewOptions(
            auto_continue_threshold=5000
        ))
        async def process_large_dataset(data: list):
            # Process items, continue_as_new() handled automatically
            ...
    """

    def decorator(func: Callable) -> ContinueAsNewWorkflowWrapper:
        return ContinueAsNewWorkflowWrapper(
            workflow_func=func, options=options, event_store=event_store
        )

    return decorator
