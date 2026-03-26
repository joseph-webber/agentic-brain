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
Child Workflows - Spawn workflows from within workflows.

Enables hierarchical workflow composition where parent workflows
can spawn, monitor, and wait for child workflows.

Features:
- Spawn child workflows with inheritance options
- Parent-child lifecycle management
- Cancellation propagation
- Result collection
- Parallel child execution
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar

from .event_store import EventStore, get_event_store
from .events import BaseEvent, EventType, WorkflowEvent


class ChildWorkflowPolicy(Enum):
    """Policy for handling child workflow failures."""

    FAIL_PARENT = "fail_parent"  # Parent fails if child fails
    ABANDON = "abandon"  # Parent continues, child orphaned
    WAIT_CANCELLATION = "wait_cancellation"  # Wait for child to cancel


class ParentClosePolicy(Enum):
    """What happens to children when parent closes."""

    TERMINATE = "terminate"  # Kill all children
    ABANDON = "abandon"  # Children become root workflows
    REQUEST_CANCEL = "request_cancel"  # Send cancel signal


@dataclass
class ChildWorkflowOptions:
    """Configuration for child workflow execution."""

    workflow_id: Optional[str] = None  # Auto-generated if not provided
    task_queue: Optional[str] = None  # Inherit from parent if not set
    execution_timeout: Optional[float] = None  # Total execution time limit
    run_timeout: Optional[float] = None  # Single run time limit
    retry_policy: Optional[Dict[str, Any]] = None
    parent_close_policy: ParentClosePolicy = ParentClosePolicy.TERMINATE
    cancellation_type: str = "wait_cancellation_completed"
    search_attributes: Optional[Dict[str, Any]] = None
    memo: Optional[Dict[str, Any]] = None


@dataclass
class ChildWorkflowHandle:
    """Handle to a running child workflow."""

    workflow_id: str
    workflow_type: str
    parent_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "running"
    result: Optional[Any] = None
    error: Optional[str] = None
    _future: Optional[asyncio.Future] = field(default=None, repr=False)

    async def result_async(self, timeout: Optional[float] = None) -> Any:
        """Wait for child workflow result."""
        if self._future is None:
            raise RuntimeError("Child workflow not properly started")

        try:
            return await asyncio.wait_for(self._future, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Child workflow {self.workflow_id} timed out")

    async def signal(self, signal_name: str, data: Any = None) -> None:
        """Send signal to child workflow."""
        # Signal dispatch handled by parent's signal system
        pass

    async def cancel(self) -> None:
        """Request cancellation of child workflow."""
        if self._future and not self._future.done():
            self._future.cancel()
            self.status = "cancelled"


@dataclass
class ChildWorkflowExecution:
    """Tracks a child workflow execution within parent context."""

    handle: ChildWorkflowHandle
    options: ChildWorkflowOptions
    workflow_func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)


class ChildWorkflowManager:
    """
    Manages child workflow lifecycle within a parent workflow.

    Features:
    - Spawn child workflows
    - Track parent-child relationships
    - Handle cancellation propagation
    - Collect results from children
    """

    def __init__(
        self, parent_workflow_id: str, event_store: Optional[EventStore] = None
    ):
        self.parent_workflow_id = parent_workflow_id
        self.event_store = event_store or get_event_store()
        self.children: Dict[str, ChildWorkflowExecution] = {}
        self._registry: Dict[str, Callable] = {}

    def register_workflow(self, name: str, func: Callable) -> None:
        """Register a workflow type that can be spawned as child."""
        self._registry[name] = func

    async def start_child_workflow(
        self,
        workflow_type: str,
        *args,
        options: Optional[ChildWorkflowOptions] = None,
        **kwargs,
    ) -> ChildWorkflowHandle:
        """
        Start a child workflow.

        Args:
            workflow_type: Name of registered workflow
            *args: Positional arguments for workflow
            options: Child workflow configuration
            **kwargs: Keyword arguments for workflow

        Returns:
            Handle to the running child workflow
        """
        if workflow_type not in self._registry:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

        options = options or ChildWorkflowOptions()
        workflow_id = (
            options.workflow_id
            or f"{self.parent_workflow_id}_child_{uuid.uuid4().hex[:8]}"
        )

        # Create handle
        handle = ChildWorkflowHandle(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            parent_id=self.parent_workflow_id,
        )

        # Create future for result
        loop = asyncio.get_event_loop()
        handle._future = loop.create_future()

        # Record event
        event = WorkflowEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=self.parent_workflow_id,
            event_type=EventType.ACTIVITY_STARTED,
            timestamp=datetime.now(timezone.utc),
            data={
                "child_workflow_id": workflow_id,
                "child_workflow_type": workflow_type,
                "args": args,
                "kwargs": kwargs,
                "options": {
                    "parent_close_policy": options.parent_close_policy.value,
                    "execution_timeout": options.execution_timeout,
                },
            },
        )
        await self.event_store.append(event)

        # Store execution
        workflow_func = self._registry[workflow_type]
        execution = ChildWorkflowExecution(
            handle=handle,
            options=options,
            workflow_func=workflow_func,
            args=args,
            kwargs=kwargs,
        )
        self.children[workflow_id] = execution

        # Start child workflow task
        asyncio.create_task(self._run_child(execution))

        return handle

    async def _run_child(self, execution: ChildWorkflowExecution) -> None:
        """Execute child workflow and set result."""
        handle = execution.handle
        try:
            # Apply timeout if specified
            timeout = execution.options.execution_timeout

            if timeout:
                result = await asyncio.wait_for(
                    execution.workflow_func(*execution.args, **execution.kwargs),
                    timeout=timeout,
                )
            else:
                result = await execution.workflow_func(
                    *execution.args, **execution.kwargs
                )

            handle.result = result
            handle.status = "completed"

            if handle._future and not handle._future.done():
                handle._future.set_result(result)

            # Record completion event
            event = WorkflowEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=self.parent_workflow_id,
                event_type=EventType.ACTIVITY_COMPLETED,
                timestamp=datetime.now(timezone.utc),
                data={"child_workflow_id": handle.workflow_id, "result": result},
            )
            await self.event_store.append(event)

        except asyncio.CancelledError:
            handle.status = "cancelled"
            if handle._future and not handle._future.done():
                handle._future.cancel()
        except Exception as e:
            handle.error = str(e)
            handle.status = "failed"

            if handle._future and not handle._future.done():
                handle._future.set_exception(e)

            # Record failure event
            event = WorkflowEvent(
                event_id=str(uuid.uuid4()),
                workflow_id=self.parent_workflow_id,
                event_type=EventType.ACTIVITY_FAILED,
                timestamp=datetime.now(timezone.utc),
                data={"child_workflow_id": handle.workflow_id, "error": str(e)},
            )
            await self.event_store.append(event)

    async def wait_all(
        self,
        handles: Optional[List[ChildWorkflowHandle]] = None,
        timeout: Optional[float] = None,
    ) -> List[Any]:
        """
        Wait for multiple child workflows to complete.

        Args:
            handles: Specific handles to wait for (all if None)
            timeout: Maximum time to wait

        Returns:
            List of results in same order as handles
        """
        if handles is None:
            handles = [e.handle for e in self.children.values()]

        if not handles:
            return []

        futures = [h._future for h in handles if h._future is not None]

        try:
            done, pending = await asyncio.wait(
                futures, timeout=timeout, return_when=asyncio.ALL_COMPLETED
            )

            results = []
            for handle in handles:
                if handle._future in done:
                    results.append(handle.result)
                else:
                    results.append(None)

            return results

        except asyncio.TimeoutError:
            raise TimeoutError("Timed out waiting for child workflows")

    async def cancel_all(self) -> None:
        """Cancel all running child workflows."""
        for execution in self.children.values():
            if execution.handle.status == "running":
                await execution.handle.cancel()

    def get_child(self, workflow_id: str) -> Optional[ChildWorkflowHandle]:
        """Get handle to specific child workflow."""
        execution = self.children.get(workflow_id)
        return execution.handle if execution else None

    def list_children(self) -> List[ChildWorkflowHandle]:
        """List all child workflow handles."""
        return [e.handle for e in self.children.values()]

    def get_running_children(self) -> List[ChildWorkflowHandle]:
        """Get only running child workflows."""
        return [
            e.handle for e in self.children.values() if e.handle.status == "running"
        ]


def child_workflow(name: Optional[str] = None, task_queue: Optional[str] = None):
    """
    Decorator to mark a function as a child workflow.

    Usage:
        @child_workflow(name="process-item")
        async def process_item(item_id: str) -> dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        workflow_name = name or func.__name__

        # Store metadata
        func._workflow_name = workflow_name
        func._task_queue = task_queue
        func._is_child_workflow = True

        return func

    return decorator


# Convenience functions for use in workflow context
async def execute_child_workflow(
    workflow_type: str,
    *args,
    parent_workflow_id: str,
    event_store: Optional[EventStore] = None,
    options: Optional[ChildWorkflowOptions] = None,
    **kwargs,
) -> Any:
    """
    Execute a child workflow and wait for result.

    Convenience function for one-shot child workflow execution.
    """
    manager = ChildWorkflowManager(
        parent_workflow_id=parent_workflow_id, event_store=event_store
    )

    handle = await manager.start_child_workflow(
        workflow_type, *args, options=options, **kwargs
    )

    return await handle.result_async()


async def start_child_workflow_async(
    workflow_type: str,
    *args,
    parent_workflow_id: str,
    event_store: Optional[EventStore] = None,
    options: Optional[ChildWorkflowOptions] = None,
    **kwargs,
) -> ChildWorkflowHandle:
    """
    Start a child workflow without waiting.

    Returns handle for later result collection.
    """
    manager = ChildWorkflowManager(
        parent_workflow_id=parent_workflow_id, event_store=event_store
    )

    return await manager.start_child_workflow(
        workflow_type, *args, options=options, **kwargs
    )
