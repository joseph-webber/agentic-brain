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
Cancellation Scopes - Structured cancellation for workflows.

Enables hierarchical cancellation where cancelling a parent
scope cancels all children. Supports shielding operations
from cancellation.

Features:
- Hierarchical scopes
- Shield from cancellation
- Timeout scopes
- Cleanup handlers
- Detached scopes
"""

import asyncio
import inspect
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class CancellationState(Enum):
    """State of a cancellation scope."""

    ACTIVE = "active"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass
class CancellationScope:
    """
    A cancellation scope for structured cancellation.

    Child scopes are automatically cancelled when parent is cancelled.
    """

    scope_id: str
    parent_id: Optional[str] = None
    state: CancellationState = CancellationState.ACTIVE
    shielded: bool = False
    detached: bool = False
    timeout: Optional[timedelta] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    children: Set[str] = field(default_factory=set)
    cleanup_handlers: List[Callable] = field(default_factory=list)

    @property
    def is_cancelled(self) -> bool:
        """Check if scope is cancelled."""
        return self.state in (CancellationState.CANCELLING, CancellationState.CANCELLED)

    @property
    def is_active(self) -> bool:
        """Check if scope is still active."""
        return self.state == CancellationState.ACTIVE


class CancellationError(Exception):
    """Raised when a cancellation scope is cancelled."""

    def __init__(self, scope_id: str, reason: Optional[str] = None):
        self.scope_id = scope_id
        self.reason = reason
        super().__init__(f"Scope {scope_id} cancelled: {reason or 'no reason'}")


class CancellationScopeManager:
    """
    Manages cancellation scopes for a workflow.

    Features:
    - Create/cancel scopes
    - Hierarchical propagation
    - Shield operations
    - Cleanup handling
    """

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.scopes: Dict[str, CancellationScope] = {}
        self._current_scope_id: Optional[str] = None
        self._scope_tasks: Dict[str, asyncio.Task] = {}

    @property
    def current_scope(self) -> Optional[CancellationScope]:
        """Get the current active scope."""
        if self._current_scope_id:
            return self.scopes.get(self._current_scope_id)
        return None

    def create_scope(
        self,
        shielded: bool = False,
        detached: bool = False,
        timeout: Optional[timedelta] = None,
        parent_id: Optional[str] = None,
    ) -> CancellationScope:
        """
        Create a new cancellation scope.

        Args:
            shielded: If True, not cancelled when parent cancelled
            detached: If True, not linked to parent
            timeout: Auto-cancel after this duration
            parent_id: Explicit parent (uses current if not set)

        Returns:
            The new scope
        """
        scope_id = f"scope_{uuid.uuid4().hex[:8]}"

        # Determine parent
        if not detached:
            if parent_id is None:
                parent_id = self._current_scope_id

        scope = CancellationScope(
            scope_id=scope_id,
            parent_id=parent_id,
            shielded=shielded,
            detached=detached,
            timeout=timeout,
        )

        self.scopes[scope_id] = scope

        # Link to parent
        if parent_id and parent_id in self.scopes:
            self.scopes[parent_id].children.add(scope_id)

        return scope

    async def cancel_scope(self, scope_id: str, reason: Optional[str] = None) -> bool:
        """
        Cancel a scope and all its children.

        Args:
            scope_id: Scope to cancel
            reason: Cancellation reason

        Returns:
            True if cancelled, False if not found
        """
        scope = self.scopes.get(scope_id)
        if not scope:
            return False

        if scope.state != CancellationState.ACTIVE:
            return False

        scope.state = CancellationState.CANCELLING
        scope.cancelled_at = datetime.now(timezone.utc)
        scope.cancel_reason = reason

        # Cancel children (unless shielded)
        for child_id in scope.children:
            child = self.scopes.get(child_id)
            if child and not child.shielded:
                await self.cancel_scope(child_id, reason=f"Parent {scope_id} cancelled")

        # Run cleanup handlers
        for handler in reversed(scope.cleanup_handlers):
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception:
                pass  # Cleanup handlers should not raise

        # Cancel task if exists
        if scope_id in self._scope_tasks:
            self._scope_tasks[scope_id].cancel()

        scope.state = CancellationState.CANCELLED
        return True

    def add_cleanup_handler(self, scope_id: str, handler: Callable) -> None:
        """Add a cleanup handler to a scope."""
        scope = self.scopes.get(scope_id)
        if scope:
            scope.cleanup_handlers.append(handler)

    def check_cancelled(self, scope_id: Optional[str] = None) -> None:
        """
        Check if scope is cancelled and raise if so.

        Call this periodically in long-running operations.
        """
        scope_id = scope_id or self._current_scope_id
        if not scope_id:
            return

        scope = self.scopes.get(scope_id)
        if scope and scope.is_cancelled:
            raise CancellationError(scope_id, scope.cancel_reason)

    @asynccontextmanager
    async def scope(self, shielded: bool = False, timeout: Optional[timedelta] = None):
        """
        Context manager for a cancellation scope.

        Usage:
            async with manager.scope(timeout=timedelta(seconds=30)):
                await do_work()
        """
        scope = self.create_scope(shielded=shielded, timeout=timeout)
        previous_scope = self._current_scope_id
        self._current_scope_id = scope.scope_id

        timeout_task = None

        try:
            # Start timeout task
            if timeout:

                async def cancel_after_timeout():
                    await asyncio.sleep(timeout.total_seconds())
                    await self.cancel_scope(scope.scope_id, "Timeout")

                timeout_task = asyncio.create_task(cancel_after_timeout())

            yield scope

            scope.state = CancellationState.COMPLETED

        except CancellationError:
            raise
        except asyncio.CancelledError:
            scope.state = CancellationState.CANCELLED
            raise CancellationError(scope.scope_id, "Task cancelled")
        finally:
            if timeout_task:
                timeout_task.cancel()
                try:
                    await timeout_task
                except asyncio.CancelledError:
                    pass

            self._current_scope_id = previous_scope

    @asynccontextmanager
    async def shield(self):
        """
        Create a shielded scope that won't be cancelled by parent.

        Usage:
            async with manager.shield():
                await critical_cleanup()
        """
        async with self.scope(shielded=True) as scope:
            yield scope

    @asynccontextmanager
    async def timeout_scope(self, duration: timedelta):
        """
        Create a scope that auto-cancels after duration.

        Usage:
            async with manager.timeout_scope(timedelta(seconds=30)):
                await potentially_slow_operation()
        """
        async with self.scope(timeout=duration) as scope:
            yield scope


# Helper functions for workflow context
_scope_managers: Dict[str, CancellationScopeManager] = {}


def get_scope_manager(workflow_id: str) -> CancellationScopeManager:
    """Get or create scope manager for workflow."""
    if workflow_id not in _scope_managers:
        _scope_managers[workflow_id] = CancellationScopeManager(workflow_id)
    return _scope_managers[workflow_id]


@asynccontextmanager
async def cancellation_scope(
    workflow_id: str, shielded: bool = False, timeout: Optional[timedelta] = None
):
    """
    Create a cancellation scope for a workflow.

    Usage:
        async with cancellation_scope("my-workflow", timeout=timedelta(seconds=30)):
            await do_work()
    """
    manager = get_scope_manager(workflow_id)
    async with manager.scope(shielded=shielded, timeout=timeout) as scope:
        yield scope


@asynccontextmanager
async def shield(workflow_id: str):
    """
    Create a shielded scope that protects from parent cancellation.

    Usage:
        async with shield("my-workflow"):
            await critical_cleanup()
    """
    manager = get_scope_manager(workflow_id)
    async with manager.shield() as scope:
        yield scope


async def cancel_workflow(workflow_id: str, reason: Optional[str] = None) -> bool:
    """Cancel all scopes for a workflow."""
    manager = _scope_managers.get(workflow_id)
    if not manager:
        return False

    # Cancel root scope (will propagate)
    root_scope_id = None
    for scope in manager.scopes.values():
        if scope.parent_id is None:
            root_scope_id = scope.scope_id
            break

    if root_scope_id:
        return await manager.cancel_scope(root_scope_id, reason)

    return False


def is_cancelled(workflow_id: str) -> bool:
    """Check if workflow has been cancelled."""
    manager = _scope_managers.get(workflow_id)
    if not manager or not manager.current_scope:
        return False
    return manager.current_scope.is_cancelled


def check_cancelled(workflow_id: str) -> None:
    """Check if cancelled and raise CancellationError if so."""
    manager = _scope_managers.get(workflow_id)
    if manager:
        manager.check_cancelled()
