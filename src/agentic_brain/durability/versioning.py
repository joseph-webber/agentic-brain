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
Workflow Versioning for Agentic Brain

Versioning allows safe updates to running workflows.
This provides durable versioning semantics.

Features:
- Version-aware workflow execution
- Migration between versions
- Backward compatibility checks
- Version history tracking
"""

import hashlib
import inspect
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class VersionCompatibility(Enum):
    """Compatibility level between versions"""

    IDENTICAL = "identical"
    BACKWARD_COMPATIBLE = "backward_compatible"
    FORWARD_COMPATIBLE = "forward_compatible"
    BREAKING = "breaking"
    UNKNOWN = "unknown"


@dataclass
class WorkflowVersion:
    """
    Represents a specific version of a workflow definition
    """

    workflow_type: str
    version: str

    # Version metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""

    # Schema info
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    # Code hash for change detection
    code_hash: Optional[str] = None

    # Deprecation
    deprecated: bool = False
    deprecated_at: Optional[datetime] = None
    deprecation_message: str = ""

    # Migration
    migrates_from: Optional[str] = None  # Previous version
    migration_handler: Optional[Callable] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_type": self.workflow_type,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "code_hash": self.code_hash,
            "deprecated": self.deprecated,
            "deprecated_at": (
                self.deprecated_at.isoformat() if self.deprecated_at else None
            ),
            "deprecation_message": self.deprecation_message,
            "migrates_from": self.migrates_from,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowVersion":
        return cls(
            workflow_type=data["workflow_type"],
            version=data["version"],
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.now(UTC)
            ),
            description=data.get("description", ""),
            input_schema=data.get("input_schema"),
            output_schema=data.get("output_schema"),
            code_hash=data.get("code_hash"),
            deprecated=data.get("deprecated", False),
            deprecated_at=(
                datetime.fromisoformat(data["deprecated_at"])
                if data.get("deprecated_at")
                else None
            ),
            deprecation_message=data.get("deprecation_message", ""),
            migrates_from=data.get("migrates_from"),
        )


@dataclass
class VersionChange:
    """
    Records a change between workflow versions
    """

    change_id: str
    from_version: str
    to_version: str
    change_type: str  # "added", "removed", "modified"
    element: str  # What changed
    description: str = ""
    breaking: bool = False


class WorkflowVersionManager:
    """
    Manages workflow versions and migrations

    Features:
    - Register workflow versions
    - Check compatibility
    - Migrate workflow state between versions
    - Track version usage
    """

    def __init__(self):
        # Versions by workflow type
        self._versions: Dict[str, Dict[str, WorkflowVersion]] = {}

        # Active version per workflow type
        self._active_versions: Dict[str, str] = {}

        # Workflow implementations by (type, version)
        self._implementations: Dict[Tuple[str, str], Type] = {}

        # Version usage counts
        self._usage_counts: Dict[Tuple[str, str], int] = {}

        # Migration history
        self._migrations: List[Dict[str, Any]] = []

    def register_version(
        self,
        workflow_type: str,
        version: str,
        implementation: Type,
        description: str = "",
        migrates_from: Optional[str] = None,
        migration_handler: Optional[Callable] = None,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> WorkflowVersion:
        """
        Register a new workflow version

        Args:
            workflow_type: Name of the workflow type
            version: Version string (e.g., "1.0", "2.0-beta")
            implementation: The workflow class
            description: Version description
            migrates_from: Previous version this migrates from
            migration_handler: Function to migrate state
            input_schema: JSON schema for inputs
            output_schema: JSON schema for outputs

        Returns:
            The registered WorkflowVersion
        """
        # Compute code hash
        source = inspect.getsource(implementation)
        code_hash = hashlib.sha256(source.encode()).hexdigest()[:16]

        wf_version = WorkflowVersion(
            workflow_type=workflow_type,
            version=version,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            code_hash=code_hash,
            migrates_from=migrates_from,
            migration_handler=migration_handler,
        )

        # Store version
        if workflow_type not in self._versions:
            self._versions[workflow_type] = {}
        self._versions[workflow_type][version] = wf_version

        # Store implementation
        self._implementations[(workflow_type, version)] = implementation

        # Set as active if first or explicitly requested
        if workflow_type not in self._active_versions:
            self._active_versions[workflow_type] = version

        logger.info(f"Registered workflow version: {workflow_type}@{version}")
        return wf_version

    def set_active_version(self, workflow_type: str, version: str) -> None:
        """Set the active (default) version for a workflow type"""
        if workflow_type not in self._versions:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        if version not in self._versions[workflow_type]:
            raise ValueError(f"Unknown version: {version}")

        old_version = self._active_versions.get(workflow_type)
        self._active_versions[workflow_type] = version
        logger.info(f"Active version for {workflow_type}: {old_version} -> {version}")

    def deprecate_version(
        self,
        workflow_type: str,
        version: str,
        message: str = "",
    ) -> None:
        """Mark a version as deprecated"""
        if workflow_type not in self._versions:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        if version not in self._versions[workflow_type]:
            raise ValueError(f"Unknown version: {version}")

        wf_version = self._versions[workflow_type][version]
        wf_version.deprecated = True
        wf_version.deprecated_at = datetime.now(UTC)
        wf_version.deprecation_message = message

        logger.warning(
            f"Deprecated workflow version: {workflow_type}@{version} - {message}"
        )

    def get_implementation(
        self,
        workflow_type: str,
        version: Optional[str] = None,
    ) -> Type:
        """Get workflow implementation for a type and version"""
        if version is None:
            version = self._active_versions.get(workflow_type)
            if version is None:
                raise ValueError(f"No versions registered for: {workflow_type}")

        impl = self._implementations.get((workflow_type, version))
        if impl is None:
            raise ValueError(f"No implementation for: {workflow_type}@{version}")

        # Track usage
        key = (workflow_type, version)
        self._usage_counts[key] = self._usage_counts.get(key, 0) + 1

        return impl

    def get_version(
        self,
        workflow_type: str,
        version: Optional[str] = None,
    ) -> WorkflowVersion:
        """Get version info"""
        if version is None:
            version = self._active_versions.get(workflow_type)

        if workflow_type not in self._versions:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        if version not in self._versions[workflow_type]:
            raise ValueError(f"Unknown version: {version}")

        return self._versions[workflow_type][version]

    def check_compatibility(
        self,
        workflow_type: str,
        from_version: str,
        to_version: str,
    ) -> VersionCompatibility:
        """
        Check compatibility between two versions

        Returns compatibility level
        """
        if from_version == to_version:
            return VersionCompatibility.IDENTICAL

        from_v = self.get_version(workflow_type, from_version)
        to_v = self.get_version(workflow_type, to_version)

        # Check if migration path exists
        if to_v.migrates_from == from_version:
            return VersionCompatibility.BACKWARD_COMPATIBLE

        # Check schema compatibility
        if from_v.input_schema and to_v.input_schema:
            if self._schemas_compatible(from_v.input_schema, to_v.input_schema):
                return VersionCompatibility.BACKWARD_COMPATIBLE

        # If code hash matches, identical behavior
        if from_v.code_hash == to_v.code_hash:
            return VersionCompatibility.IDENTICAL

        return VersionCompatibility.UNKNOWN

    def _schemas_compatible(
        self,
        from_schema: Dict[str, Any],
        to_schema: Dict[str, Any],
    ) -> bool:
        """Check if schemas are backward compatible"""
        # Simple check: new schema must have all fields from old
        from_props = from_schema.get("properties", {})
        to_props = to_schema.get("properties", {})

        return all(key in to_props for key in from_props)

    async def migrate_state(
        self,
        workflow_id: str,
        workflow_type: str,
        from_version: str,
        to_version: str,
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Migrate workflow state from one version to another

        Args:
            workflow_id: ID of the workflow
            workflow_type: Type of workflow
            from_version: Current version
            to_version: Target version
            current_state: Current workflow state

        Returns:
            Migrated state
        """
        if from_version == to_version:
            return current_state

        to_v = self.get_version(workflow_type, to_version)

        # Use migration handler if available
        if to_v.migration_handler:
            try:
                if inspect.iscoroutinefunction(to_v.migration_handler):
                    new_state = await to_v.migration_handler(
                        current_state, from_version
                    )
                else:
                    new_state = to_v.migration_handler(current_state, from_version)

                # Record migration
                self._migrations.append(
                    {
                        "workflow_id": workflow_id,
                        "workflow_type": workflow_type,
                        "from_version": from_version,
                        "to_version": to_version,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "success": True,
                    }
                )

                logger.info(
                    f"Migrated {workflow_id} from v{from_version} to v{to_version}"
                )
                return new_state

            except Exception as e:
                self._migrations.append(
                    {
                        "workflow_id": workflow_id,
                        "workflow_type": workflow_type,
                        "from_version": from_version,
                        "to_version": to_version,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "success": False,
                        "error": str(e),
                    }
                )
                raise RuntimeError(f"Migration failed: {e}")

        # No handler - try chain migration
        chain = self._find_migration_chain(workflow_type, from_version, to_version)
        if chain:
            state = current_state
            for intermediate in chain:
                state = await self.migrate_state(
                    workflow_id,
                    workflow_type,
                    intermediate[0],
                    intermediate[1],
                    state,
                )
            return state

        raise ValueError(f"No migration path from {from_version} to {to_version}")

    def _find_migration_chain(
        self,
        workflow_type: str,
        from_version: str,
        to_version: str,
    ) -> List[Tuple[str, str]]:
        """Find chain of migrations from one version to another"""
        if workflow_type not in self._versions:
            return []

        versions = self._versions[workflow_type]

        # BFS to find path
        visited = set()
        queue = [(from_version, [])]

        while queue:
            current, path = queue.pop(0)

            if current == to_version:
                return path

            if current in visited:
                continue
            visited.add(current)

            # Find versions that migrate from current
            for ver_str, ver in versions.items():
                if ver.migrates_from == current:
                    queue.append((ver_str, path + [(current, ver_str)]))

        return []

    def list_versions(
        self,
        workflow_type: str,
        include_deprecated: bool = False,
    ) -> List[WorkflowVersion]:
        """List all versions of a workflow type"""
        if workflow_type not in self._versions:
            return []

        versions = list(self._versions[workflow_type].values())

        if not include_deprecated:
            versions = [v for v in versions if not v.deprecated]

        return sorted(versions, key=lambda v: v.created_at)

    def get_active_version(self, workflow_type: str) -> Optional[str]:
        """Get the active version for a workflow type"""
        return self._active_versions.get(workflow_type)

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get version usage statistics"""
        return {
            "usage_counts": {
                f"{wt}@{ver}": count for (wt, ver), count in self._usage_counts.items()
            },
            "total_migrations": len(self._migrations),
            "recent_migrations": self._migrations[-10:],
        }


# Global version manager
_manager: Optional[WorkflowVersionManager] = None


def get_version_manager() -> WorkflowVersionManager:
    """Get the global version manager"""
    global _manager
    if _manager is None:
        _manager = WorkflowVersionManager()
    return _manager


# Decorator for versioned workflows
def workflow_version(
    version: str,
    description: str = "",
    migrates_from: Optional[str] = None,
):
    """
    Decorator to mark a workflow class with version info

    Usage:
        @workflow_version("2.0", migrates_from="1.0")
        class MyWorkflowV2(DurableWorkflow):
            ...
    """

    def decorator(cls: Type) -> Type:
        cls._workflow_version = version
        cls._workflow_description = description
        cls._migrates_from = migrates_from
        return cls

    return decorator


# Decorator for migration handler
def migration_handler(from_version: str, to_version: str):
    """
    Decorator to mark a function as a migration handler

    Usage:
        @migration_handler("1.0", "2.0")
        def migrate_v1_to_v2(state: dict, from_ver: str) -> dict:
            # Transform state
            return new_state
    """

    def decorator(func: Callable) -> Callable:
        func._migration_from = from_version
        func._migration_to = to_version
        return func

    return decorator


def version_gate(
    min_version: Optional[str] = None,
    max_version: Optional[str] = None,
    change_id: Optional[str] = None,
):
    """
    Version gate for gradual rollout

    Use this to conditionally execute code based on workflow version.
    Provides version branching for safe updates.

    Usage:
        if version_gate(min_version="2.0"):
            # New behavior
        else:
            # Old behavior

    Args:
        min_version: Minimum version to execute
        max_version: Maximum version to execute
        change_id: Unique ID for this change (for tracking)

    Returns:
        True if current version is within range
    """
    # This is a simplified implementation
    # In production, this would check the current workflow's version
    return True  # Placeholder


# Example migration function
def default_migration(state: Dict[str, Any], from_version: str) -> Dict[str, Any]:
    """
    Default migration that preserves all state

    Override this for custom migration logic.
    """
    return {
        **state,
        "_migrated_from": from_version,
        "_migrated_at": datetime.now(UTC).isoformat(),
    }
