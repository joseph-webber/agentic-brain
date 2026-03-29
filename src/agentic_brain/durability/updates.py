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
Workflow Updates for Agentic Brain

Updates provide synchronous mutations to workflow state with validation.
Unlike signals (fire-and-forget), updates wait for the handler to complete
and return a result.

Features:
- Synchronous state mutations with response
- Update validation before applying
- Update history tracking
- Atomic update semantics
- Timeout handling

Usage:
    @workflow(name="config-workflow")
    class ConfigWorkflow(DurableWorkflow):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.priority = 5

        @update_handler("set_priority")
        async def set_priority(self, new_priority: int) -> bool:
            if new_priority < 1 or new_priority > 10:
                raise ValueError("Priority must be 1-10")
            self.priority = new_priority
            return True

    # Client side - waits for result
    result = await workflow_handle.update("set_priority", 7)
"""

import asyncio
import inspect
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class UpdateStatus(Enum):
    """Status of update execution"""

    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class UpdateDefinition:
    """
    Definition of an update type

    Updates are synchronous mutations that return a result.
    """

    name: str
    description: str = ""
    arg_type: Optional[Type] = None
    return_type: Optional[Type] = None
    validator: Optional[Callable[[Any], bool]] = None
    timeout: float = 30.0  # Default 30 second timeout

    def validate_args(self, args: Any) -> bool:
        """Validate update arguments"""
        if self.validator:
            return self.validator(args)
        if self.arg_type is None:
            return True
        return isinstance(args, self.arg_type)


@dataclass
class UpdateRequest:
    """
    An update request to a workflow
    """

    update_id: str
    update_name: str
    workflow_id: str
    args: Any = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    requester_id: Optional[str] = None
    timeout: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "update_id": self.update_id,
            "update_name": self.update_name,
            "workflow_id": self.workflow_id,
            "args": self.args,
            "created_at": self.created_at.isoformat(),
            "requester_id": self.requester_id,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateRequest":
        return cls(
            update_id=data["update_id"],
            update_name=data["update_name"],
            workflow_id=data["workflow_id"],
            args=data.get("args"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now(UTC)
            ),
            requester_id=data.get("requester_id"),
            timeout=data.get("timeout", 30.0),
        )


@dataclass
class UpdateResult:
    """
    Result of an update execution
    """

    update_id: str
    update_name: str
    workflow_id: str
    status: UpdateStatus
    result: Any = None
    error: Optional[str] = None

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "update_id": self.update_id,
            "update_name": self.update_name,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    @property
    def success(self) -> bool:
        """Check if update completed successfully"""
        return self.status == UpdateStatus.COMPLETED

    @property
    def duration_ms(self) -> Optional[float]:
        """Get update duration in milliseconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None


class UpdateValidationError(Exception):
    """Raised when update validation fails"""

    def __init__(self, message: str, update_name: str):
        super().__init__(message)
        self.update_name = update_name


class UpdateTimeoutError(Exception):
    """Raised when update times out"""

    def __init__(self, update_id: str, timeout: float):
        super().__init__(f"Update {update_id} timed out after {timeout}s")
        self.update_id = update_id
        self.timeout = timeout


class UpdateHandler:
    """
    Handler for workflow updates

    Manages update reception, validation, and execution.
    """

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id

        # Registered update handlers
        self._handlers: Dict[str, Callable] = {}

        # Update definitions
        self._definitions: Dict[str, UpdateDefinition] = {}

        # Update history
        self._history: List[UpdateResult] = []

        # Pending updates (waiting for execution)
        self._pending: Dict[str, asyncio.Future] = {}

        # Lock for thread safety
        self._lock = asyncio.Lock()

    def define_update(
        self,
        name: str,
        description: str = "",
        arg_type: Optional[Type] = None,
        return_type: Optional[Type] = None,
        validator: Optional[Callable[[Any], bool]] = None,
        timeout: float = 30.0,
    ) -> UpdateDefinition:
        """Define a new update type"""
        definition = UpdateDefinition(
            name=name,
            description=description,
            arg_type=arg_type,
            return_type=return_type,
            validator=validator,
            timeout=timeout,
        )
        self._definitions[name] = definition
        return definition

    def register_handler(
        self,
        update_name: str,
        handler: Callable,
    ) -> None:
        """Register a handler for an update type"""
        self._handlers[update_name] = handler
        logger.debug(f"Registered update handler for '{update_name}'")

    async def execute(self, request: UpdateRequest) -> UpdateResult:
        """
        Execute an update and return the result

        This is synchronous from the caller's perspective -
        it waits for the handler to complete.
        """
        result = UpdateResult(
            update_id=request.update_id,
            update_name=request.update_name,
            workflow_id=request.workflow_id,
            status=UpdateStatus.PENDING,
            started_at=datetime.now(UTC),
        )

        async with self._lock:
            # Get handler
            handler = self._handlers.get(request.update_name)
            if not handler:
                result.status = UpdateStatus.FAILED
                result.error = (
                    f"No handler registered for update '{request.update_name}'"
                )
                result.completed_at = datetime.now(UTC)
                self._history.append(result)
                return result

            # Validate arguments
            result.status = UpdateStatus.VALIDATING
            definition = self._definitions.get(request.update_name)
            if definition and not definition.validate_args(request.args):
                result.status = UpdateStatus.REJECTED
                result.error = f"Invalid arguments for update '{request.update_name}'"
                result.completed_at = datetime.now(UTC)
                self._history.append(result)
                return result

            # Execute handler
            result.status = UpdateStatus.EXECUTING
            try:
                timeout = request.timeout
                if definition:
                    timeout = definition.timeout

                if inspect.iscoroutinefunction(handler):
                    update_result = await asyncio.wait_for(
                        handler(request.args),
                        timeout=timeout,
                    )
                else:
                    update_result = handler(request.args)

                result.status = UpdateStatus.COMPLETED
                result.result = update_result

            except TimeoutError:
                result.status = UpdateStatus.TIMEOUT
                result.error = f"Update timed out after {timeout}s"
                logger.warning(f"Update {request.update_id} timed out")

            except UpdateValidationError as e:
                result.status = UpdateStatus.REJECTED
                result.error = str(e)
                logger.warning(f"Update {request.update_id} rejected: {e}")

            except Exception as e:
                result.status = UpdateStatus.FAILED
                result.error = str(e)
                logger.error(f"Update {request.update_id} failed: {e}")

            result.completed_at = datetime.now(UTC)
            self._history.append(result)

            return result

    def get_history(
        self,
        update_name: Optional[str] = None,
        status: Optional[UpdateStatus] = None,
        limit: int = 100,
    ) -> List[UpdateResult]:
        """Get update history with optional filters"""
        history = self._history

        if update_name:
            history = [u for u in history if u.update_name == update_name]

        if status:
            history = [u for u in history if u.status == status]

        return history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get update statistics"""
        total = len(self._history)
        completed = len(
            [u for u in self._history if u.status == UpdateStatus.COMPLETED]
        )
        failed = len([u for u in self._history if u.status == UpdateStatus.FAILED])
        rejected = len([u for u in self._history if u.status == UpdateStatus.REJECTED])
        timed_out = len([u for u in self._history if u.status == UpdateStatus.TIMEOUT])

        durations = [u.duration_ms for u in self._history if u.duration_ms is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "rejected": rejected,
            "timed_out": timed_out,
            "success_rate": (completed / total * 100) if total > 0 else 0,
            "avg_duration_ms": avg_duration,
        }


class UpdateDispatcher:
    """
    Central dispatcher for workflow updates

    Routes updates to appropriate workflow update handlers.
    """

    def __init__(self):
        self._handlers: Dict[str, UpdateHandler] = {}

    def register_workflow(self, workflow_id: str) -> UpdateHandler:
        """Register a workflow for update handling"""
        if workflow_id not in self._handlers:
            handler = UpdateHandler(workflow_id)
            self._handlers[workflow_id] = handler
        return self._handlers[workflow_id]

    def unregister_workflow(self, workflow_id: str) -> None:
        """Unregister a workflow"""
        self._handlers.pop(workflow_id, None)

    async def send_update(
        self,
        workflow_id: str,
        update_name: str,
        args: Any = None,
        requester_id: Optional[str] = None,
        timeout: float = 30.0,
    ) -> UpdateResult:
        """
        Send an update to a workflow and wait for result

        Args:
            workflow_id: Target workflow ID
            update_name: Name of the update
            args: Update arguments
            requester_id: Optional requester identifier
            timeout: Timeout in seconds

        Returns:
            UpdateResult with the handler's response
        """
        request = UpdateRequest(
            update_id=str(uuid.uuid4()),
            update_name=update_name,
            workflow_id=workflow_id,
            args=args,
            requester_id=requester_id,
            timeout=timeout,
        )

        handler = self._handlers.get(workflow_id)
        if not handler:
            return UpdateResult(
                update_id=request.update_id,
                update_name=update_name,
                workflow_id=workflow_id,
                status=UpdateStatus.FAILED,
                error=f"Workflow {workflow_id} not registered",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )

        return await handler.execute(request)

    def get_handler(self, workflow_id: str) -> Optional[UpdateHandler]:
        """Get update handler for a workflow"""
        return self._handlers.get(workflow_id)


# Global update dispatcher
_dispatcher: Optional[UpdateDispatcher] = None


def get_update_dispatcher() -> UpdateDispatcher:
    """Get the global update dispatcher"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = UpdateDispatcher()
    return _dispatcher


async def update_workflow(
    workflow_id: str,
    update_name: str,
    args: Any = None,
    timeout: float = 30.0,
) -> UpdateResult:
    """
    Send an update to a workflow and wait for result

    Convenience function for sending updates.

    Args:
        workflow_id: Target workflow ID
        update_name: Name of the update
        args: Update arguments
        timeout: Timeout in seconds

    Returns:
        UpdateResult with the handler's response
    """
    dispatcher = get_update_dispatcher()
    return await dispatcher.send_update(
        workflow_id=workflow_id,
        update_name=update_name,
        args=args,
        timeout=timeout,
    )


# Decorator for update handlers
def update_handler(
    update_name: str,
    validator: Optional[Callable[[Any], bool]] = None,
    timeout: float = 30.0,
):
    """
    Decorator to mark a method as an update handler

    Usage:
        class MyWorkflow(DurableWorkflow):
            @update_handler("set_priority")
            async def set_priority(self, new_priority: int) -> bool:
                if new_priority < 1 or new_priority > 10:
                    raise ValueError("Priority must be 1-10")
                self.priority = new_priority
                return True
    """

    def decorator(func: Callable) -> Callable:
        func._update_name = update_name
        func._is_update_handler = True
        func._update_validator = validator
        func._update_timeout = timeout
        return func

    return decorator


def extract_update_handlers(obj: Any) -> Dict[str, Callable]:
    """
    Extract all update handlers from an object

    Returns dict of update_name -> handler method
    """
    handlers = {}
    for name in dir(obj):
        method = getattr(obj, name)
        if callable(method) and hasattr(method, "_is_update_handler"):
            handlers[method._update_name] = method
    return handlers


# Common update definitions for AI workflows
SET_CONFIG_UPDATE = UpdateDefinition(
    name="set_config",
    description="Update workflow configuration",
    arg_type=dict,
    return_type=bool,
)

SET_PRIORITY_UPDATE = UpdateDefinition(
    name="set_priority",
    description="Update workflow priority",
    arg_type=int,
    return_type=bool,
    validator=lambda p: isinstance(p, int) and 1 <= p <= 10,
)

SET_TIMEOUT_UPDATE = UpdateDefinition(
    name="set_timeout",
    description="Update workflow timeout",
    arg_type=float,
    return_type=bool,
    validator=lambda t: isinstance(t, (int, float)) and t > 0,
)

SET_RATE_LIMIT_UPDATE = UpdateDefinition(
    name="set_rate_limit",
    description="Update LLM rate limit settings",
    arg_type=dict,
    return_type=bool,
)

ADD_CONTEXT_UPDATE = UpdateDefinition(
    name="add_context",
    description="Add context to LLM workflow",
    arg_type=dict,
    return_type=bool,
)
