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
Workflow Namespaces for Agentic Brain

Namespaces provide multi-tenant isolation for workflows.
Each namespace is a logical container with its own:
- Workflow definitions
- Event store partition
- Task queues
- Access controls

Features:
- Logical isolation between tenants
- Namespace-specific configuration
- Resource quotas
- Access control
- Cross-namespace visibility (optional)

Use Cases:
- SaaS multi-tenancy
- Environment separation (dev/staging/prod)
- Team isolation
- Customer workspaces

Usage:
    # Create a namespace
    ns = Namespace("tenant-a", description="Customer A")

    # Register workflows in namespace
    ns.register_workflow(MyWorkflow)

    # Start workflow in namespace
    wf = await ns.start_workflow(
        "MyWorkflow",
        args={"query": "analyze this"}
    )

    # Query workflows in namespace
    workflows = ns.list_workflows(status="running")
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class NamespaceState(Enum):
    """State of a namespace"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


@dataclass
class NamespaceConfig:
    """Configuration for a namespace"""

    # Basic
    name: str
    description: str = ""

    # State
    state: NamespaceState = NamespaceState.ACTIVE

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    owner: Optional[str] = None

    # Resource Quotas
    max_workflows: int = 10000
    max_pending_activities: int = 100000
    max_history_size_mb: int = 1000
    retention_days: int = 30

    # Feature Flags
    enable_schedules: bool = True
    enable_search: bool = True
    enable_archival: bool = False

    # Access Control
    allowed_users: List[str] = field(default_factory=list)
    allowed_roles: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "owner": self.owner,
            "max_workflows": self.max_workflows,
            "max_pending_activities": self.max_pending_activities,
            "max_history_size_mb": self.max_history_size_mb,
            "retention_days": self.retention_days,
            "enable_schedules": self.enable_schedules,
            "enable_search": self.enable_search,
            "enable_archival": self.enable_archival,
            "allowed_users": self.allowed_users,
            "allowed_roles": self.allowed_roles,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NamespaceConfig":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            state=NamespaceState(data.get("state", "active")),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now(UTC)
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else datetime.now(UTC)
            ),
            owner=data.get("owner"),
            max_workflows=data.get("max_workflows", 10000),
            max_pending_activities=data.get("max_pending_activities", 100000),
            max_history_size_mb=data.get("max_history_size_mb", 1000),
            retention_days=data.get("retention_days", 30),
            enable_schedules=data.get("enable_schedules", True),
            enable_search=data.get("enable_search", True),
            enable_archival=data.get("enable_archival", False),
            allowed_users=data.get("allowed_users", []),
            allowed_roles=data.get("allowed_roles", []),
        )


@dataclass
class NamespaceStats:
    """Statistics for a namespace"""

    workflow_count: int = 0
    running_workflows: int = 0
    pending_activities: int = 0
    history_size_mb: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_count": self.workflow_count,
            "running_workflows": self.running_workflows,
            "pending_activities": self.pending_activities,
            "history_size_mb": self.history_size_mb,
        }


class NamespaceError(Exception):
    """Base error for namespace operations"""

    pass


class NamespaceNotFoundError(NamespaceError):
    """Namespace does not exist"""

    def __init__(self, name: str):
        super().__init__(f"Namespace not found: {name}")
        self.name = name


class NamespaceSuspendedError(NamespaceError):
    """Namespace is suspended"""

    def __init__(self, name: str):
        super().__init__(f"Namespace is suspended: {name}")
        self.name = name


class NamespaceQuotaExceededError(NamespaceError):
    """Namespace quota exceeded"""

    def __init__(self, name: str, resource: str):
        super().__init__(f"Quota exceeded for {resource} in namespace {name}")
        self.name = name
        self.resource = resource


class Namespace:
    """
    A logical container for workflows

    Provides isolation and configuration for a set of workflows.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        config: Optional[NamespaceConfig] = None,
    ):
        self.name = name
        self.config = config or NamespaceConfig(name=name, description=description)

        # Registered workflow types
        self._workflow_types: Dict[str, Type] = {}

        # Active workflow instances
        self._workflows: Dict[str, Any] = {}

        # Statistics
        self._stats = NamespaceStats()

        # Lock
        self._lock = asyncio.Lock()

    @property
    def is_active(self) -> bool:
        """Check if namespace is active"""
        return self.config.state == NamespaceState.ACTIVE

    def _check_active(self) -> None:
        """Raise if namespace is not active"""
        if not self.is_active:
            raise NamespaceSuspendedError(self.name)

    def register_workflow(
        self,
        workflow_class: Type,
        name: Optional[str] = None,
    ) -> None:
        """
        Register a workflow type in this namespace

        Args:
            workflow_class: The workflow class to register
            name: Optional name override
        """
        workflow_name = name or getattr(
            workflow_class, "_workflow_name", workflow_class.__name__
        )
        self._workflow_types[workflow_name] = workflow_class
        logger.debug(
            f"Registered workflow '{workflow_name}' in namespace '{self.name}'"
        )

    def get_workflow_type(self, name: str) -> Optional[Type]:
        """Get a registered workflow type by name"""
        return self._workflow_types.get(name)

    def list_workflow_types(self) -> List[str]:
        """List all registered workflow type names"""
        return list(self._workflow_types.keys())

    async def start_workflow(
        self,
        workflow_type: str,
        workflow_id: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Start a new workflow in this namespace

        Args:
            workflow_type: Name of registered workflow type
            workflow_id: Optional workflow ID (auto-generated if not provided)
            args: Arguments to pass to workflow

        Returns:
            The started workflow instance
        """
        self._check_active()

        # Check quota
        if len(self._workflows) >= self.config.max_workflows:
            raise NamespaceQuotaExceededError(self.name, "max_workflows")

        # Get workflow class
        workflow_class = self._workflow_types.get(workflow_type)
        if not workflow_class:
            raise ValueError(f"Workflow type '{workflow_type}' not registered")

        async with self._lock:
            # Create workflow instance
            import uuid

            wf_id = workflow_id or str(uuid.uuid4())

            workflow = workflow_class(
                workflow_id=wf_id,
                namespace=self.name,
            )

            # Store in namespace
            self._workflows[wf_id] = workflow
            self._stats.workflow_count += 1
            self._stats.running_workflows += 1

            # Start workflow
            await workflow.start(args=args or {})

            logger.info(
                f"Started workflow {wf_id} ({workflow_type}) "
                f"in namespace {self.name}"
            )

            return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Any]:
        """Get a workflow by ID"""
        return self._workflows.get(workflow_id)

    def list_workflows(
        self,
        status: Optional[str] = None,
        workflow_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Any]:
        """
        List workflows in this namespace

        Args:
            status: Filter by status (running, completed, failed)
            workflow_type: Filter by workflow type
            limit: Maximum workflows to return

        Returns:
            List of matching workflows
        """
        workflows = list(self._workflows.values())

        if status:
            workflows = [w for w in workflows if getattr(w, "status", None) == status]

        if workflow_type:
            workflows = [
                w
                for w in workflows
                if getattr(w, "_workflow_name", w.__class__.__name__) == workflow_type
            ]

        return workflows[:limit]

    def get_stats(self) -> NamespaceStats:
        """Get namespace statistics"""
        return self._stats

    async def suspend(self) -> None:
        """Suspend the namespace (no new workflows)"""
        self.config.state = NamespaceState.SUSPENDED
        self.config.updated_at = datetime.now(UTC)
        logger.warning(f"Namespace '{self.name}' suspended")

    async def resume(self) -> None:
        """Resume a suspended namespace"""
        self.config.state = NamespaceState.ACTIVE
        self.config.updated_at = datetime.now(UTC)
        logger.info(f"Namespace '{self.name}' resumed")

    async def delete(self) -> None:
        """
        Mark namespace as deleted

        Does not actually delete workflows - use cleanup for that
        """
        self.config.state = NamespaceState.DELETED
        self.config.updated_at = datetime.now(UTC)
        logger.warning(f"Namespace '{self.name}' marked for deletion")

    async def cleanup(self, force: bool = False) -> int:
        """
        Clean up completed workflows in namespace

        Args:
            force: If True, also clean running workflows

        Returns:
            Number of workflows cleaned up
        """
        async with self._lock:
            to_remove = []

            for wf_id, workflow in self._workflows.items():
                status = getattr(workflow, "status", None)
                if (
                    status in ("completed", "failed", "cancelled")
                    or force
                    and status == "running"
                ):
                    to_remove.append(wf_id)

            for wf_id in to_remove:
                del self._workflows[wf_id]

            self._stats.workflow_count = len(self._workflows)

            logger.info(
                f"Cleaned up {len(to_remove)} workflows in namespace '{self.name}'"
            )
            return len(to_remove)


class NamespaceRegistry:
    """
    Central registry for all namespaces

    Manages namespace lifecycle and provides cross-namespace operations.
    """

    def __init__(self):
        self._namespaces: Dict[str, Namespace] = {}
        self._lock = asyncio.Lock()

        # Create default namespace
        self._default_namespace = Namespace(
            "default",
            description="Default namespace",
        )
        self._namespaces["default"] = self._default_namespace

    @property
    def default(self) -> Namespace:
        """Get the default namespace"""
        return self._default_namespace

    async def create(
        self,
        name: str,
        description: str = "",
        config: Optional[NamespaceConfig] = None,
    ) -> Namespace:
        """
        Create a new namespace

        Args:
            name: Unique namespace name
            description: Optional description
            config: Optional configuration

        Returns:
            The created Namespace
        """
        async with self._lock:
            if name in self._namespaces:
                raise ValueError(f"Namespace '{name}' already exists")

            namespace = Namespace(
                name=name,
                description=description,
                config=config,
            )

            self._namespaces[name] = namespace
            logger.info(f"Created namespace '{name}'")

            return namespace

    def get(self, name: str) -> Namespace:
        """
        Get a namespace by name

        Args:
            name: Namespace name

        Returns:
            The Namespace

        Raises:
            NamespaceNotFoundError: If namespace doesn't exist
        """
        namespace = self._namespaces.get(name)
        if not namespace:
            raise NamespaceNotFoundError(name)
        return namespace

    def exists(self, name: str) -> bool:
        """Check if namespace exists"""
        return name in self._namespaces

    def list(
        self,
        state: Optional[NamespaceState] = None,
    ) -> List[Namespace]:
        """
        List all namespaces

        Args:
            state: Optional state filter

        Returns:
            List of namespaces
        """
        namespaces = list(self._namespaces.values())

        if state:
            namespaces = [ns for ns in namespaces if ns.config.state == state]

        return namespaces

    async def delete(self, name: str, force: bool = False) -> None:
        """
        Delete a namespace

        Args:
            name: Namespace name
            force: If True, delete even if workflows exist
        """
        if name == "default":
            raise ValueError("Cannot delete default namespace")

        async with self._lock:
            namespace = self.get(name)

            if not force and namespace.list_workflows():
                raise ValueError(
                    f"Namespace '{name}' has active workflows. "
                    "Use force=True to delete anyway."
                )

            await namespace.delete()
            del self._namespaces[name]

            logger.info(f"Deleted namespace '{name}'")

    def get_stats(self) -> Dict[str, NamespaceStats]:
        """Get statistics for all namespaces"""
        return {name: ns.get_stats() for name, ns in self._namespaces.items()}


# Global registry instance
_registry: Optional[NamespaceRegistry] = None


def get_namespace_registry() -> NamespaceRegistry:
    """Get the global namespace registry"""
    global _registry
    if _registry is None:
        _registry = NamespaceRegistry()
    return _registry


def get_namespace(name: str = "default") -> Namespace:
    """
    Get a namespace by name

    Convenience function for getting namespaces.
    """
    return get_namespace_registry().get(name)


async def create_namespace(
    name: str,
    description: str = "",
    **config_kwargs,
) -> Namespace:
    """
    Create a new namespace

    Convenience function for creating namespaces.
    """
    config = NamespaceConfig(name=name, description=description, **config_kwargs)
    return await get_namespace_registry().create(name, description, config)


# Decorator to bind workflow to namespace
def namespace_workflow(namespace_name: str):
    """
    Decorator to register a workflow in a specific namespace

    Usage:
        @namespace_workflow("tenant-a")
        @workflow(name="analysis")
        class AnalysisWorkflow(DurableWorkflow):
            pass
    """

    def decorator(cls: Type) -> Type:
        cls._namespace = namespace_name

        # Auto-register on import (deferred to avoid circular imports)
        def register_later():
            try:
                ns = get_namespace(namespace_name)
                ns.register_workflow(cls)
            except NamespaceNotFoundError:
                logger.warning(
                    f"Namespace '{namespace_name}' not found during registration. "
                    f"Create it before using workflow {cls.__name__}."
                )

        # Register asynchronously
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon(register_later)
            else:
                register_later()
        except RuntimeError:
            register_later()

        return cls

    return decorator
