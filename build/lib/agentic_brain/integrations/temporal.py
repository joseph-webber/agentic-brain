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
Temporal.io Integration for Agentic-Brain

This module provides integration with Temporal.io's durable execution platform,
enabling fault-tolerant AI agent workflows.

Features:
- TemporalOrchestrator: Connect to Temporal server
- Workflow decorators for AI agents
- Activity wrappers for LLM operations
- Durable execution patterns

Usage:
    from agentic_brain.integrations import TemporalOrchestrator

    orchestrator = TemporalOrchestrator("localhost:7233")
    await orchestrator.connect()

    result = await orchestrator.run_workflow(
        "ai-analysis",
        args={"query": "Analyze this data"},
        timeout=300
    )
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

# Type variables for decorators
P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


class WorkflowStatus(str, Enum):
    """Status of a workflow execution"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    PAUSED = "paused"


@dataclass
class RetryPolicy:
    """Retry policy for activities and workflows"""

    max_attempts: int = 3
    initial_interval: float = 1.0
    backoff_coefficient: float = 2.0
    max_interval: float = 60.0
    non_retryable_errors: list[type[Exception]] = field(default_factory=list)


@dataclass
class WorkflowOptions:
    """Options for workflow execution"""

    workflow_id: str | None = None
    task_queue: str = "default"
    execution_timeout: timedelta = timedelta(hours=1)
    run_timeout: timedelta | None = None
    task_timeout: timedelta = timedelta(seconds=10)
    retry_policy: RetryPolicy | None = None
    memo: dict[str, Any] | None = None
    search_attributes: dict[str, Any] | None = None


@dataclass
class ActivityOptions:
    """Options for activity execution"""

    start_to_close_timeout: timedelta = timedelta(seconds=30)
    schedule_to_close_timeout: timedelta | None = None
    heartbeat_timeout: timedelta | None = None
    retry_policy: RetryPolicy | None = None


@dataclass
class WorkflowExecution:
    """Result of a workflow execution"""

    workflow_id: str
    run_id: str
    status: WorkflowStatus
    result: Any | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self.status in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING)

    @property
    def is_completed(self) -> bool:
        return self.status == WorkflowStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status in (WorkflowStatus.FAILED, WorkflowStatus.TIMED_OUT)


class TemporalOrchestrator:
    """
    Integration with Temporal.io for durable workflow execution.

    Provides connection to Temporal server and methods to:
    - Start and manage workflows
    - Execute activities with durability
    - Handle signals and queries
    - Integrate AI agents with fault-tolerant execution

    Example:
        orchestrator = TemporalOrchestrator("localhost:7233")
        await orchestrator.connect()

        # Run an AI analysis workflow
        result = await orchestrator.run_workflow(
            "ai-analysis",
            workflow_id="analysis-001",
            args={"query": "Analyze sales data"}
        )
    """

    def __init__(
        self,
        host: str = "localhost:7233",
        namespace: str = "default",
        task_queue: str = "agentic-brain",
        api_key: str | None = None,
    ):
        """
        Initialize Temporal orchestrator.

        Args:
            host: Temporal server address (host:port)
            namespace: Temporal namespace to use
            task_queue: Default task queue for workflows
            api_key: Optional API key for Temporal Cloud
        """
        self.host = host
        self.namespace = namespace
        self.task_queue = task_queue
        self.api_key = api_key
        self._client = None
        self._connected = False
        self._workflows: dict[str, type] = {}
        self._activities: dict[str, Callable] = {}

    @property
    def is_connected(self) -> bool:
        """Check if connected to Temporal server"""
        return self._connected

    async def connect(self) -> bool:
        """
        Connect to Temporal server.

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If unable to connect
        """
        try:
            # Check if temporalio is installed
            try:
                import temporalio
                from temporalio.client import Client

                self._client = await Client.connect(
                    self.host,
                    namespace=self.namespace,
                )
                self._connected = True
                logger.info(f"Connected to Temporal at {self.host}")
                return True

            except ImportError:
                logger.warning(
                    "temporalio package not installed. "
                    "Install with: pip install temporalio"
                )
                # Fall back to local orchestration
                self._connected = False
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Temporal: {e}")
            self._connected = False
            raise ConnectionError(f"Cannot connect to Temporal at {self.host}: {e}")

    async def disconnect(self) -> None:
        """Disconnect from Temporal server"""
        if self._client:
            # Temporal client doesn't need explicit close
            self._client = None
        self._connected = False
        logger.info("Disconnected from Temporal")

    def register_workflow(self, workflow_class: type) -> None:
        """
        Register a workflow class for execution.

        Args:
            workflow_class: Class decorated with @workflow
        """
        name = getattr(workflow_class, "_workflow_name", workflow_class.__name__)
        self._workflows[name] = workflow_class
        logger.debug(f"Registered workflow: {name}")

    def register_activity(self, activity_fn: Callable) -> None:
        """
        Register an activity function.

        Args:
            activity_fn: Function decorated with @activity
        """
        name = getattr(activity_fn, "_activity_name", activity_fn.__name__)
        self._activities[name] = activity_fn
        logger.debug(f"Registered activity: {name}")

    async def run_workflow(
        self,
        workflow_name: str,
        args: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        task_queue: str | None = None,
        timeout: float = 3600,
        **options: Any,
    ) -> WorkflowExecution:
        """
        Start and wait for a workflow to complete.

        Args:
            workflow_name: Name of registered workflow
            args: Arguments to pass to workflow
            workflow_id: Unique ID for workflow (auto-generated if not provided)
            task_queue: Task queue to use (defaults to orchestrator's queue)
            timeout: Maximum time to wait for completion
            **options: Additional workflow options

        Returns:
            WorkflowExecution with results
        """
        import uuid

        workflow_id = workflow_id or f"{workflow_name}-{uuid.uuid4().hex[:8]}"
        task_queue = task_queue or self.task_queue
        started_at = datetime.now(timezone.utc)

        try:
            if self._connected and self._client:
                # Use Temporal for durable execution
                from temporalio.client import Client

                workflow_class = self._workflows.get(workflow_name)
                if not workflow_class:
                    raise ValueError(f"Workflow not registered: {workflow_name}")

                handle = await self._client.start_workflow(
                    workflow_class,
                    args or {},
                    id=workflow_id,
                    task_queue=task_queue,
                    execution_timeout=timedelta(seconds=timeout),
                )

                result = await handle.result()

                return WorkflowExecution(
                    workflow_id=workflow_id,
                    run_id=handle.result_run_id or "",
                    status=WorkflowStatus.COMPLETED,
                    result=result,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )
            else:
                # Local fallback - execute workflow directly
                return await self._run_local_workflow(
                    workflow_name, args, workflow_id, timeout, started_at
                )

        except asyncio.TimeoutError:
            return WorkflowExecution(
                workflow_id=workflow_id,
                run_id="",
                status=WorkflowStatus.TIMED_OUT,
                error=f"Workflow timed out after {timeout}s",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {e}")
            return WorkflowExecution(
                workflow_id=workflow_id,
                run_id="",
                status=WorkflowStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

    async def _run_local_workflow(
        self,
        workflow_name: str,
        args: dict[str, Any] | None,
        workflow_id: str,
        timeout: float,
        started_at: datetime,
    ) -> WorkflowExecution:
        """Run workflow locally without Temporal"""
        workflow_class = self._workflows.get(workflow_name)
        if not workflow_class:
            raise ValueError(f"Workflow not registered: {workflow_name}")

        # Find the run method
        run_method = None
        for name in dir(workflow_class):
            method = getattr(workflow_class, name)
            if hasattr(method, "_workflow_run"):
                run_method = method
                break

        if not run_method:
            raise ValueError(f"Workflow {workflow_name} has no @run method")

        # Execute
        instance = workflow_class()
        result = await asyncio.wait_for(
            run_method(instance, **(args or {})), timeout=timeout
        )

        return WorkflowExecution(
            workflow_id=workflow_id,
            run_id="local",
            status=WorkflowStatus.COMPLETED,
            result=result,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

    async def start_workflow(
        self,
        workflow_name: str,
        args: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        task_queue: str | None = None,
        **options: Any,
    ) -> str:
        """
        Start a workflow without waiting for completion.

        Returns:
            Workflow ID for tracking
        """
        import uuid

        workflow_id = workflow_id or f"{workflow_name}-{uuid.uuid4().hex[:8]}"

        if self._connected and self._client:
            workflow_class = self._workflows.get(workflow_name)
            if not workflow_class:
                raise ValueError(f"Workflow not registered: {workflow_name}")

            await self._client.start_workflow(
                workflow_class,
                args or {},
                id=workflow_id,
                task_queue=task_queue or self.task_queue,
            )
        else:
            # Start in background task
            asyncio.create_task(
                self._run_local_workflow(
                    workflow_name, args, workflow_id, 3600, datetime.now(timezone.utc)
                )
            )

        return workflow_id

    async def get_workflow_status(self, workflow_id: str) -> WorkflowExecution | None:
        """Get status of a running or completed workflow"""
        if not self._connected or not self._client:
            return None

        try:
            handle = self._client.get_workflow_handle(workflow_id)
            description = await handle.describe()

            status_map = {
                "RUNNING": WorkflowStatus.RUNNING,
                "COMPLETED": WorkflowStatus.COMPLETED,
                "FAILED": WorkflowStatus.FAILED,
                "CANCELED": WorkflowStatus.CANCELLED,
                "TERMINATED": WorkflowStatus.CANCELLED,
                "TIMED_OUT": WorkflowStatus.TIMED_OUT,
            }

            return WorkflowExecution(
                workflow_id=workflow_id,
                run_id=description.run_id,
                status=status_map.get(str(description.status), WorkflowStatus.RUNNING),
                started_at=description.start_time,
            )
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            return None

    async def signal_workflow(
        self,
        workflow_id: str,
        signal_name: str,
        args: Any = None,
    ) -> bool:
        """
        Send a signal to a running workflow.

        Args:
            workflow_id: ID of the workflow
            signal_name: Name of the signal handler
            args: Arguments to pass to signal handler

        Returns:
            True if signal was sent successfully
        """
        if not self._connected or not self._client:
            logger.warning("Not connected to Temporal, signal not sent")
            return False

        try:
            handle = self._client.get_workflow_handle(workflow_id)
            await handle.signal(signal_name, args)
            logger.debug(f"Sent signal {signal_name} to workflow {workflow_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to signal workflow: {e}")
            return False

    async def query_workflow(
        self,
        workflow_id: str,
        query_name: str,
        args: Any = None,
    ) -> Any:
        """
        Query a running workflow's state.

        Args:
            workflow_id: ID of the workflow
            query_name: Name of the query handler
            args: Arguments to pass to query handler

        Returns:
            Query result
        """
        if not self._connected or not self._client:
            raise RuntimeError("Not connected to Temporal")

        handle = self._client.get_workflow_handle(workflow_id)
        return await handle.query(query_name, args)

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow"""
        if not self._connected or not self._client:
            return False

        try:
            handle = self._client.get_workflow_handle(workflow_id)
            await handle.cancel()
            logger.info(f"Cancelled workflow {workflow_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel workflow: {e}")
            return False


# =============================================================================
# Decorators for workflow and activity definitions
# =============================================================================


def workflow(
    name: str | None = None,
    timeout: float = 3600,
    versioned: bool = False,
) -> Callable[[type[T]], type[T]]:
    """
    Decorator for workflow class definitions.

    Usage:
        @workflow(name="my-workflow", timeout=1800)
        class MyWorkflow:
            @run
            async def run(self, data: dict) -> str:
                return "done"
    """

    def decorator(cls: type[T]) -> type[T]:
        cls._workflow_name = name or cls.__name__
        cls._workflow_timeout = timeout
        cls._workflow_versioned = versioned
        return cls

    return decorator


def run(fn: Callable[P, R]) -> Callable[P, R]:
    """
    Decorator for the main workflow run method.

    Must be used on exactly one async method in the workflow class.
    """
    if not inspect.iscoroutinefunction(fn):
        raise TypeError("@run method must be async")

    fn._workflow_run = True
    return fn


def signal(name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator for workflow signal handlers.

    Signals allow external input to running workflows.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        fn._signal_name = name or fn.__name__
        return fn

    return decorator


def query(name: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator for workflow query handlers.

    Queries allow reading workflow state without affecting it.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        fn._query_name = name or fn.__name__
        return fn

    return decorator


def activity(
    name: str | None = None,
    retry: int = 3,
    timeout: float = 30.0,
    heartbeat_interval: float | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator for activity definitions.

    Activities are side-effect operations (API calls, DB writes, LLM calls).

    Usage:
        @activity(name="call-llm", retry=3, timeout=60)
        async def call_llm(prompt: str) -> str:
            return await llm.complete(prompt)
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_error = None

            for attempt in range(retry):
                try:
                    if inspect.iscoroutinefunction(fn):
                        return await asyncio.wait_for(
                            fn(*args, **kwargs), timeout=timeout
                        )
                    else:
                        return fn(*args, **kwargs)

                except asyncio.TimeoutError:
                    last_error = TimeoutError(
                        f"Activity {name or fn.__name__} timed out after {timeout}s"
                    )
                    logger.warning(f"Activity timeout, attempt {attempt + 1}/{retry}")

                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Activity failed, attempt {attempt + 1}/{retry}: {e}"
                    )

                # Exponential backoff
                if attempt < retry - 1:
                    await asyncio.sleep(2**attempt)

            raise last_error or RuntimeError("Activity failed")

        wrapper._activity_name = name or fn.__name__
        wrapper._retry_count = retry
        wrapper._timeout = timeout
        wrapper._heartbeat_interval = heartbeat_interval
        return wrapper

    return decorator


# =============================================================================
# AI Agent Workflow Helpers
# =============================================================================


@dataclass
class AgentWorkflowContext:
    """Context for AI agent workflows"""

    workflow_id: str
    agent_id: str
    memory: dict[str, Any] = field(default_factory=dict)
    messages: list[dict] = field(default_factory=list)
    current_step: str = "init"


class AIAgentWorkflowMixin:
    """
    Mixin for AI agent workflows with common patterns.

    Provides:
    - LLM activity execution
    - Memory persistence
    - Multi-turn conversation support
    - Tool/function calling
    """

    async def execute_llm_activity(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Execute an LLM call as a durable activity"""
        # This would be implemented as a Temporal activity
        # For now, provides the pattern
        raise NotImplementedError("Override this method or register an LLM activity")

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> Any:
        """Execute a tool/function as a durable activity"""
        raise NotImplementedError("Override this method or register tool activities")

    async def save_memory(self, key: str, value: Any) -> None:
        """Persist workflow memory (survives restarts)"""
        # This would use Temporal's workflow state
        pass

    async def load_memory(self, key: str) -> Any | None:
        """Load persisted workflow memory"""
        pass


# =============================================================================
# Example Workflows
# =============================================================================


@workflow(name="ai-analysis", timeout=1800)
class AIAnalysisWorkflow(AIAgentWorkflowMixin):
    """
    Example: Durable AI analysis workflow.

    This workflow:
    1. Receives analysis request
    2. Calls LLM for analysis (durable, retried)
    3. Handles signals for feedback
    4. Supports queries for progress
    """

    def __init__(self):
        self.progress = "starting"
        self.result = None
        self.feedback: list[str] = []

    @run
    async def run(self, query: str, context: dict | None = None) -> dict:
        """Main workflow logic"""
        self.progress = "analyzing"

        # This would call an LLM activity
        # analysis = await self.execute_llm_activity(
        #     prompt=query,
        #     system_prompt="You are a data analyst..."
        # )

        # Simulate analysis
        await asyncio.sleep(1)
        analysis = f"Analysis complete for: {query}"

        self.progress = "complete"
        self.result = {
            "query": query,
            "analysis": analysis,
            "feedback_received": self.feedback,
        }

        return self.result

    @signal()
    async def add_feedback(self, feedback: str) -> None:
        """Signal handler for receiving feedback during analysis"""
        self.feedback.append(feedback)

    @query()
    def get_progress(self) -> str:
        """Query handler for checking progress"""
        return self.progress


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Main orchestrator
    "TemporalOrchestrator",
    # Data classes
    "WorkflowStatus",
    "WorkflowExecution",
    "WorkflowOptions",
    "ActivityOptions",
    "RetryPolicy",
    "AgentWorkflowContext",
    # Decorators
    "workflow",
    "run",
    "signal",
    "query",
    "activity",
    # Mixins and helpers
    "AIAgentWorkflowMixin",
    "AIAnalysisWorkflow",
]
