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
Workflow Memos for Agentic Brain

Memos are non-indexed workflow metadata. Unlike search attributes,
memos are not searchable but can store larger arbitrary data.

Features:
- Arbitrary metadata storage
- No size limit (within reason)
- JSON serializable values
- Workflow lifecycle bound
- Not indexed (use search_attributes for searchable data)

Use Cases:
- Debug information
- Batch job context
- User notes
- Configuration snapshots
- Audit trails

Usage:
    @workflow(
        name="batch-job",
        memo={
            "created_by": "batch_scheduler",
            "source": "nightly_import",
            "notes": "Processing Q4 data",
        }
    )
    class BatchWorkflow(DurableWorkflow):
        pass

    # Or set dynamically
    wf = BatchWorkflow()
    wf.set_memo("debug_info", {"step": 1, "items_processed": 0})

    # Read memo
    debug = wf.get_memo("debug_info")
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MemoEntry:
    """
    A single memo entry
    """

    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoEntry":
        return cls(
            key=data["key"],
            value=data["value"],
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
        )


class MemoStore:
    """
    Storage for workflow memos

    Each workflow has its own memo store.
    """

    def __init__(
        self, workflow_id: str, initial_memos: Optional[Dict[str, Any]] = None
    ):
        self.workflow_id = workflow_id
        self._entries: Dict[str, MemoEntry] = {}
        self._history: List[Dict[str, Any]] = []

        # Initialize with provided memos
        if initial_memos:
            for key, value in initial_memos.items():
                self._entries[key] = MemoEntry(key=key, value=value)

    def set(self, key: str, value: Any) -> MemoEntry:
        """
        Set a memo value

        Args:
            key: Memo key
            value: Memo value (must be JSON serializable)

        Returns:
            The created/updated MemoEntry
        """
        now = datetime.now(UTC)

        if key in self._entries:
            entry = self._entries[key]
            old_value = entry.value
            entry.value = value
            entry.updated_at = now

            # Record history
            self._history.append(
                {
                    "action": "update",
                    "key": key,
                    "old_value": old_value,
                    "new_value": value,
                    "timestamp": now.isoformat(),
                }
            )
        else:
            entry = MemoEntry(key=key, value=value, created_at=now, updated_at=now)
            self._entries[key] = entry

            # Record history
            self._history.append(
                {
                    "action": "create",
                    "key": key,
                    "value": value,
                    "timestamp": now.isoformat(),
                }
            )

        logger.debug(f"Set memo '{key}' for workflow {self.workflow_id}")
        return entry

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a memo value

        Args:
            key: Memo key
            default: Default value if key not found

        Returns:
            The memo value, or default
        """
        entry = self._entries.get(key)
        return entry.value if entry else default

    def delete(self, key: str) -> bool:
        """
        Delete a memo

        Args:
            key: Memo key

        Returns:
            True if deleted, False if not found
        """
        if key in self._entries:
            old_value = self._entries[key].value
            del self._entries[key]

            # Record history
            self._history.append(
                {
                    "action": "delete",
                    "key": key,
                    "old_value": old_value,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

            logger.debug(f"Deleted memo '{key}' from workflow {self.workflow_id}")
            return True
        return False

    def has(self, key: str) -> bool:
        """Check if memo exists"""
        return key in self._entries

    def keys(self) -> List[str]:
        """Get all memo keys"""
        return list(self._entries.keys())

    def values(self) -> List[Any]:
        """Get all memo values"""
        return [e.value for e in self._entries.values()]

    def items(self) -> Dict[str, Any]:
        """Get all memos as dict"""
        return {k: e.value for k, e in self._entries.items()}

    def entries(self) -> List[MemoEntry]:
        """Get all memo entries with metadata"""
        return list(self._entries.values())

    def clear(self) -> int:
        """
        Clear all memos

        Returns:
            Number of memos cleared
        """
        count = len(self._entries)

        # Record history
        self._history.append(
            {
                "action": "clear",
                "count": count,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        self._entries.clear()
        logger.debug(f"Cleared {count} memos from workflow {self.workflow_id}")
        return count

    def update(self, memos: Dict[str, Any]) -> int:
        """
        Update multiple memos at once

        Args:
            memos: Dict of key-value pairs

        Returns:
            Number of memos updated
        """
        for key, value in memos.items():
            self.set(key, value)
        return len(memos)

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get memo change history"""
        return self._history[-limit:]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize all memos"""
        return {
            "workflow_id": self.workflow_id,
            "memos": {k: e.to_dict() for k, e in self._entries.items()},
            "history_count": len(self._history),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoStore":
        """Deserialize memo store"""
        store = cls(workflow_id=data["workflow_id"])

        for key, entry_data in data.get("memos", {}).items():
            store._entries[key] = MemoEntry.from_dict(entry_data)

        return store


# Mixin for workflows to support memos
class MemoMixin:
    """
    Mixin to add memo support to workflows

    Usage:
        class MyWorkflow(DurableWorkflow, MemoMixin):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.init_memos(kwargs.get("memo"))
    """

    _memo_store: Optional[MemoStore] = None

    def init_memos(self, initial_memos: Optional[Dict[str, Any]] = None) -> None:
        """Initialize memo store"""
        workflow_id = getattr(self, "workflow_id", "unknown")
        self._memo_store = MemoStore(workflow_id, initial_memos)

    def set_memo(self, key: str, value: Any) -> None:
        """Set a memo value"""
        if self._memo_store is None:
            self.init_memos()
        assert self._memo_store is not None
        self._memo_store.set(key, value)

    def get_memo(self, key: str, default: Any = None) -> Any:
        """Get a memo value"""
        if self._memo_store is None:
            return default
        return self._memo_store.get(key, default)

    def delete_memo(self, key: str) -> bool:
        """Delete a memo"""
        if self._memo_store is None:
            return False
        return self._memo_store.delete(key)

    def list_memos(self) -> Dict[str, Any]:
        """List all memos"""
        if self._memo_store is None:
            return {}
        return self._memo_store.items()

    def update_memos(self, memos: Dict[str, Any]) -> int:
        """Update multiple memos"""
        if self._memo_store is None:
            self.init_memos()
        return self._memo_store.update(memos)


# Global memo registry for cross-workflow access
class MemoRegistry:
    """
    Central registry for workflow memos

    Allows external access to workflow memos.
    """

    def __init__(self):
        self._stores: Dict[str, MemoStore] = {}

    def register(self, workflow_id: str, store: MemoStore) -> None:
        """Register a workflow's memo store"""
        self._stores[workflow_id] = store

    def unregister(self, workflow_id: str) -> None:
        """Unregister a workflow's memo store"""
        self._stores.pop(workflow_id, None)

    def get_store(self, workflow_id: str) -> Optional[MemoStore]:
        """Get a workflow's memo store"""
        return self._stores.get(workflow_id)

    def get_memo(self, workflow_id: str, key: str, default: Any = None) -> Any:
        """Get a memo from any workflow"""
        store = self._stores.get(workflow_id)
        if store:
            return store.get(key, default)
        return default

    def set_memo(self, workflow_id: str, key: str, value: Any) -> bool:
        """Set a memo on any workflow"""
        store = self._stores.get(workflow_id)
        if store:
            store.set(key, value)
            return True
        return False

    def list_workflows(self) -> List[str]:
        """List all registered workflow IDs"""
        return list(self._stores.keys())


# Global registry
_registry: Optional[MemoRegistry] = None


def get_memo_registry() -> MemoRegistry:
    """Get the global memo registry"""
    global _registry
    if _registry is None:
        _registry = MemoRegistry()
    return _registry


# Decorator for workflows with memos
def with_memo(initial_memos: Optional[Dict[str, Any]] = None):
    """
    Decorator to add memo support to a workflow

    Usage:
        @with_memo({"source": "api", "version": "1.0"})
        @workflow(name="my-workflow")
        class MyWorkflow(DurableWorkflow):
            pass
    """

    def decorator(cls):
        original_init = cls.__init__

        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)

            # Initialize memo store
            workflow_id = getattr(self, "workflow_id", "unknown")

            # Merge decorator memos with runtime memos
            runtime_memos = kwargs.get("memo", {})
            all_memos = {**(initial_memos or {}), **runtime_memos}

            self._memo_store = MemoStore(workflow_id, all_memos)

            # Register with global registry
            get_memo_registry().register(workflow_id, self._memo_store)

        cls.__init__ = new_init

        # Add memo methods if not present
        if not hasattr(cls, "set_memo"):
            cls.set_memo = MemoMixin.set_memo
        if not hasattr(cls, "get_memo"):
            cls.get_memo = MemoMixin.get_memo
        if not hasattr(cls, "delete_memo"):
            cls.delete_memo = MemoMixin.delete_memo
        if not hasattr(cls, "list_memos"):
            cls.list_memos = MemoMixin.list_memos
        if not hasattr(cls, "update_memos"):
            cls.update_memos = MemoMixin.update_memos

        return cls

    return decorator


# Common memo keys for AI workflows
MEMO_KEYS = {
    "created_by": "Who/what created this workflow",
    "source": "Source system or trigger",
    "batch_id": "Batch identifier for grouped workflows",
    "request_id": "Original request ID",
    "user_notes": "User-provided notes",
    "debug_info": "Debug information",
    "config_snapshot": "Configuration at workflow start",
    "environment": "Environment (dev/staging/prod)",
    "version": "Workflow version or code version",
    "parent_workflow": "Parent workflow ID if child",
    "retry_context": "Context from previous retry attempts",
    "llm_context": "LLM conversation context",
    "rag_sources": "RAG document sources used",
}
