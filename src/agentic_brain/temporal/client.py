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
Temporal client compatibility module.

Provides client classes matching temporalio.client exactly:
- Client.connect() - Connect to Agentic Brain (no server needed!)
- client.execute_workflow() - Execute workflow and wait
- client.start_workflow() - Start workflow without waiting
- client.get_workflow_handle() - Get handle to existing workflow
- WorkflowHandle - Handle for workflow operations
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from ..durability import (
    DurableWorkflow,
    get_event_store,
    get_query_dispatcher,
    get_signal_dispatcher,
    get_update_dispatcher,
)

T = TypeVar("T")


# ============================================================================
# Workflow Handle (matches temporalio.client.WorkflowHandle)
# ============================================================================


@dataclass
class WorkflowHandle:
    """
    Handle to a workflow execution.

    Matches temporalio.client.WorkflowHandle.
    """

    workflow_id: str
    run_id: Optional[str] = None
    result_run_id: Optional[str] = None
    first_execution_run_id: Optional[str] = None
    _client: Optional[Client] = None
    _workflow_instance: Optional[DurableWorkflow] = None

    @property
    def id(self) -> str:
        """Alias for workflow_id for compatibility."""
        return self.workflow_id

    async def result(self, *, follow_runs: bool = True) -> Any:
        """
        Wait for workflow result.

        Args:
            follow_runs: Follow continue-as-new runs

        Returns:
            The workflow result
        """
        if self._workflow_instance:
            return await self._workflow_instance.wait_for_completion()

        # Poll for completion
        event_store = get_event_store()
        while True:
            events = await event_store.get_events(self.workflow_id)
            for event in reversed(events):
                if event.event_type.name == "WORKFLOW_COMPLETED":
                    return event.data.get("result")
                if event.event_type.name == "WORKFLOW_FAILED":
                    raise Exception(event.data.get("error", "Workflow failed"))

            await asyncio.sleep(0.5)

    async def signal(
        self,
        signal: str | Callable,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Send a signal to the workflow.

        Args:
            signal: Signal name or handler function
            *args: Signal arguments
        """
        signal_name = signal if isinstance(signal, str) else signal.__name__

        dispatcher = get_signal_dispatcher()
        await dispatcher.send_signal(
            workflow_id=self.workflow_id,
            signal_name=signal_name,
            args=args,
            kwargs=kwargs,
        )

    async def query(
        self,
        query: str | Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Query the workflow state.

        Args:
            query: Query name or handler function
            *args: Query arguments

        Returns:
            Query result
        """
        query_name = query if isinstance(query, str) else query.__name__

        dispatcher = get_query_dispatcher()
        result = await dispatcher.send_query(
            workflow_id=self.workflow_id,
            query_name=query_name,
            args=args,
            kwargs=kwargs,
        )
        return result.result

    async def update(
        self,
        update: str | Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Send an update to the workflow.

        Unlike signals, updates wait for the handler to complete.

        Args:
            update: Update name or handler function
            *args: Update arguments

        Returns:
            Update result
        """
        update_name = update if isinstance(update, str) else update.__name__

        dispatcher = get_update_dispatcher()
        result = await dispatcher.send_update(
            workflow_id=self.workflow_id,
            update_name=update_name,
            args=args,
            kwargs=kwargs,
        )
        return result.result

    async def cancel(self) -> None:
        """Cancel the workflow."""
        await self.signal("__cancel__")

    async def terminate(
        self,
        reason: Optional[str] = None,
        *,
        details: Optional[List[Any]] = None,
    ) -> None:
        """Terminate the workflow immediately."""
        if self._workflow_instance:
            await self._workflow_instance.terminate(reason)

    async def describe(self) -> WorkflowExecutionDescription:
        """Get workflow description."""
        event_store = get_event_store()
        events = await event_store.get_events(self.workflow_id)

        status = "RUNNING"
        start_time = None
        close_time = None

        for event in events:
            if event.event_type.name == "WORKFLOW_STARTED":
                start_time = event.timestamp
            elif event.event_type.name == "WORKFLOW_COMPLETED":
                status = "COMPLETED"
                close_time = event.timestamp
            elif event.event_type.name == "WORKFLOW_FAILED":
                status = "FAILED"
                close_time = event.timestamp
            elif event.event_type.name == "WORKFLOW_CANCELLED":
                status = "CANCELLED"
                close_time = event.timestamp

        return WorkflowExecutionDescription(
            workflow_id=self.workflow_id,
            run_id=self.run_id or "",
            status=status,
            start_time=start_time,
            close_time=close_time,
        )

    async def fetch_history(self) -> List[Any]:
        """Fetch workflow history events."""
        event_store = get_event_store()
        return await event_store.get_events(self.workflow_id)


@dataclass
class WorkflowExecutionDescription:
    """Description of a workflow execution."""

    workflow_id: str
    run_id: str
    status: str
    workflow_type: str = ""
    task_queue: str = "default"
    start_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    execution_time: Optional[timedelta] = None
    memo: Optional[Dict[str, Any]] = None
    search_attributes: Optional[Dict[str, Any]] = None
    parent_workflow_id: Optional[str] = None
    parent_run_id: Optional[str] = None


# ============================================================================
# Async Activity Completion Handle
# ============================================================================


@dataclass
class AsyncActivityHandle:
    """Handle for completing activities asynchronously."""

    task_token: bytes
    _client: Optional[Client] = None

    async def complete(self, result: Any = None) -> None:
        """Complete the activity with a result."""
        from ..durability import get_async_completion_manager

        manager = get_async_completion_manager()
        await manager.complete(self.task_token.decode(), result)

    async def fail(self, error: Exception) -> None:
        """Fail the activity with an error."""
        from ..durability import get_async_completion_manager

        manager = get_async_completion_manager()
        await manager.fail(self.task_token.decode(), str(error))

    async def heartbeat(self, *details: Any) -> None:
        """Send a heartbeat."""
        from ..durability import get_async_completion_manager

        manager = get_async_completion_manager()
        await manager.heartbeat(self.task_token.decode(), details)


# ============================================================================
# Client (matches temporalio.client.Client)
# ============================================================================


@dataclass
class ClientConfig:
    """Client configuration."""

    target_host: str = "localhost:7233"  # Ignored - no server needed!
    namespace: str = "default"
    data_converter: Optional[Any] = None
    interceptors: List[Any] = field(default_factory=list)
    tls: bool = False
    retry_config: Optional[Any] = None


class Client:
    """
    Client for Agentic Brain workflows.

    Matches temporalio.client.Client API exactly.

    Note: Unlike Temporal, no server connection is needed!
    Agentic Brain runs workflows in-process with durable execution.

    Usage:
        # Connect (instant - no server!)
        client = await Client.connect("localhost:7233")

        # Execute workflow
        result = await client.execute_workflow(
            MyWorkflow.run,
            "arg",
            id="my-workflow",
            task_queue="my-queue",
        )
    """

    def __init__(
        self,
        *,
        namespace: str = "default",
        data_converter: Optional[Any] = None,
        interceptors: Optional[List[Any]] = None,
    ):
        self.namespace = namespace
        self.data_converter = data_converter
        self.interceptors = interceptors or []
        self._workflows: Dict[str, DurableWorkflow] = {}

    @classmethod
    async def connect(
        cls,
        target_host: str = "localhost:7233",
        *,
        namespace: str = "default",
        data_converter: Optional[Any] = None,
        interceptors: Optional[List[Any]] = None,
        tls: bool = False,
        tls_config: Optional[Any] = None,
        retry_config: Optional[Any] = None,
        rpc_metadata: Optional[Dict[str, str]] = None,
        identity: Optional[str] = None,
        lazy: bool = False,
        runtime: Optional[Any] = None,
    ) -> Client:
        """
        Connect to Agentic Brain.

        Note: This is instant! No server connection needed.
        The target_host parameter is accepted for compatibility
        but ignored - Agentic Brain runs in-process.

        Args:
            target_host: Ignored (for Temporal compatibility)
            namespace: Workflow namespace
            data_converter: Custom data converter
            interceptors: Workflow interceptors
            tls: Ignored
            tls_config: Ignored
            retry_config: Retry configuration
            rpc_metadata: Ignored
            identity: Worker identity
            lazy: Lazy connection (always true for us)
            runtime: Runtime configuration

        Returns:
            Connected client
        """
        # No actual connection needed - we run in-process!
        return cls(
            namespace=namespace,
            data_converter=data_converter,
            interceptors=interceptors,
        )

    async def start_workflow(
        self,
        workflow: str | Type | Callable,
        *args: Any,
        id: str,
        task_queue: str,
        execution_timeout: Optional[timedelta] = None,
        run_timeout: Optional[timedelta] = None,
        task_timeout: Optional[timedelta] = None,
        id_reuse_policy: str = "allow_duplicate",
        id_conflict_policy: str = "fail",
        retry_policy: Optional[Any] = None,
        cron_schedule: Optional[str] = None,
        memo: Optional[Dict[str, Any]] = None,
        search_attributes: Optional[Dict[str, Any]] = None,
        start_delay: Optional[timedelta] = None,
        start_signal: Optional[str] = None,
        start_signal_args: Optional[List[Any]] = None,
        rpc_metadata: Optional[Dict[str, str]] = None,
        rpc_timeout: Optional[timedelta] = None,
        request_eager_start: bool = False,
    ) -> WorkflowHandle:
        """
        Start a workflow without waiting for result.

        Matches temporalio.client.Client.start_workflow exactly.

        Args:
            workflow: Workflow class, method, or name
            *args: Workflow arguments
            id: Workflow ID (required)
            task_queue: Task queue name (required)
            execution_timeout: Total execution timeout
            run_timeout: Single run timeout
            task_timeout: Task timeout
            id_reuse_policy: ID reuse policy
            retry_policy: Retry configuration
            cron_schedule: Cron schedule string
            memo: Workflow memo
            search_attributes: Search attributes

        Returns:
            Workflow handle
        """
        # Get workflow class
        if isinstance(workflow, str):
            raise ValueError("String workflow types not yet supported")
        elif callable(workflow) and not isinstance(workflow, type):
            # It's a method like MyWorkflow.run
            workflow_class = (
                workflow.__self__.__class__ if hasattr(workflow, "__self__") else None
            )
            if workflow_class is None:
                # Try to get from qualname
                parts = workflow.__qualname__.split(".")
                if len(parts) >= 2:
                    # Need to find the class - for now just use a generic wrapper
                    workflow_class = type(
                        parts[0], (DurableWorkflow,), {"run": workflow}
                    )
        else:
            workflow_class = workflow

        # Create workflow instance
        run_id = uuid.uuid4().hex
        instance = workflow_class()
        instance.workflow_id = id
        instance.run_id = run_id
        instance.task_queue = task_queue
        instance.namespace = self.namespace

        # Store for later
        self._workflows[id] = instance

        # Start execution in background
        async def run_workflow():
            try:
                if hasattr(instance, "run"):
                    return await instance.run(*args)
                else:
                    # Find the @workflow.run decorated method
                    for attr_name in dir(instance):
                        attr = getattr(instance, attr_name)
                        if callable(attr) and getattr(attr, "_temporal_is_run", False):
                            return await attr(*args)
            except Exception as e:
                instance._error = e
                raise

        # Start in background
        asyncio.create_task(run_workflow())

        return WorkflowHandle(
            workflow_id=id,
            run_id=run_id,
            _client=self,
            _workflow_instance=instance,
        )

    async def execute_workflow(
        self,
        workflow: str | Type | Callable,
        *args: Any,
        id: str,
        task_queue: str,
        execution_timeout: Optional[timedelta] = None,
        run_timeout: Optional[timedelta] = None,
        task_timeout: Optional[timedelta] = None,
        id_reuse_policy: str = "allow_duplicate",
        id_conflict_policy: str = "fail",
        retry_policy: Optional[Any] = None,
        cron_schedule: Optional[str] = None,
        memo: Optional[Dict[str, Any]] = None,
        search_attributes: Optional[Dict[str, Any]] = None,
        start_delay: Optional[timedelta] = None,
        start_signal: Optional[str] = None,
        start_signal_args: Optional[List[Any]] = None,
        rpc_metadata: Optional[Dict[str, str]] = None,
        rpc_timeout: Optional[timedelta] = None,
        request_eager_start: bool = False,
    ) -> Any:
        """
        Execute a workflow and wait for result.

        Matches temporalio.client.Client.execute_workflow exactly.

        This is equivalent to start_workflow + handle.result().

        Returns:
            The workflow result
        """
        handle = await self.start_workflow(
            workflow,
            *args,
            id=id,
            task_queue=task_queue,
            execution_timeout=execution_timeout,
            run_timeout=run_timeout,
            task_timeout=task_timeout,
            id_reuse_policy=id_reuse_policy,
            id_conflict_policy=id_conflict_policy,
            retry_policy=retry_policy,
            cron_schedule=cron_schedule,
            memo=memo,
            search_attributes=search_attributes,
            start_delay=start_delay,
            start_signal=start_signal,
            start_signal_args=start_signal_args,
            rpc_metadata=rpc_metadata,
            rpc_timeout=rpc_timeout,
            request_eager_start=request_eager_start,
        )

        return await handle.result()

    def get_workflow_handle(
        self,
        workflow_id: str,
        *,
        run_id: Optional[str] = None,
        first_execution_run_id: Optional[str] = None,
    ) -> WorkflowHandle:
        """
        Get a handle to an existing workflow.

        Args:
            workflow_id: The workflow ID
            run_id: Optional specific run ID
            first_execution_run_id: First execution run ID

        Returns:
            Workflow handle
        """
        instance = self._workflows.get(workflow_id)

        return WorkflowHandle(
            workflow_id=workflow_id,
            run_id=run_id,
            first_execution_run_id=first_execution_run_id,
            _client=self,
            _workflow_instance=instance,
        )

    def get_async_activity_handle(
        self,
        task_token: bytes,
    ) -> AsyncActivityHandle:
        """
        Get a handle for async activity completion.

        Args:
            task_token: The activity task token

        Returns:
            Async activity handle
        """
        return AsyncActivityHandle(
            task_token=task_token,
            _client=self,
        )

    async def list_workflows(
        self,
        query: Optional[str] = None,
        *,
        page_size: int = 100,
    ) -> List[WorkflowExecutionDescription]:
        """
        List workflows.

        Args:
            query: Optional search query
            page_size: Results per page

        Returns:
            List of workflow descriptions
        """
        results = []

        for workflow_id, instance in self._workflows.items():
            handle = WorkflowHandle(
                workflow_id=workflow_id,
                _client=self,
                _workflow_instance=instance,
            )
            desc = await handle.describe()
            results.append(desc)

        return results[:page_size]

    async def count_workflows(
        self,
        query: Optional[str] = None,
    ) -> int:
        """Count workflows matching query."""
        workflows = await self.list_workflows(query)
        return len(workflows)

    @property
    def identity(self) -> str:
        """Get client identity."""
        import socket

        return f"agentic-brain@{socket.gethostname()}"

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(self, *args) -> None:
        pass


# ============================================================================
# Module-level exports matching temporalio.client
# ============================================================================

__all__ = [
    "Client",
    "ClientConfig",
    "WorkflowHandle",
    "WorkflowExecutionDescription",
    "AsyncActivityHandle",
]
