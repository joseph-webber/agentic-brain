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
Checkpoint System for faster workflow recovery.

Instead of replaying all events from the beginning, checkpoints allow
workflows to restore from a recent snapshot, then replay only the
events since that checkpoint.

Features:
- Automatic periodic checkpoints
- Manual checkpoint creation
- Checkpoint storage with compression
- Fast recovery from checkpoint + events

Usage:
    from agentic_brain.durability.checkpoints import CheckpointManager

    manager = CheckpointManager()

    # Create checkpoint
    checkpoint_id = await manager.create_checkpoint(
        workflow_id="wf-123",
        state=workflow_state
    )

    # Load checkpoint
    state = await manager.load_checkpoint("wf-123", checkpoint_id)
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from .replay import WorkflowState

logger = logging.getLogger(__name__)


@dataclass
class CheckpointConfig:
    """Configuration for checkpoint manager"""

    # Storage
    storage_path: str = "/tmp/agentic-brain/checkpoints"
    use_compression: bool = True

    # Automatic checkpointing
    auto_checkpoint: bool = True
    checkpoint_interval_events: int = 100  # Checkpoint every N events
    checkpoint_interval_seconds: float = 300  # Checkpoint every N seconds

    # Retention
    max_checkpoints_per_workflow: int = 5
    checkpoint_ttl_hours: int = 24 * 7  # 7 days

    @classmethod
    def from_env(cls) -> CheckpointConfig:
        """Create config from environment variables"""
        return cls(
            storage_path=os.getenv("CHECKPOINT_PATH", "/tmp/agentic-brain/checkpoints"),
            use_compression=os.getenv("CHECKPOINT_COMPRESSION", "true").lower()
            == "true",
            auto_checkpoint=os.getenv("CHECKPOINT_AUTO", "true").lower() == "true",
        )


@dataclass
class CheckpointInfo:
    """Metadata about a checkpoint"""

    checkpoint_id: str
    workflow_id: str
    created_at: datetime
    sequence_number: int
    size_bytes: int
    compressed: bool
    event_count: int


class CheckpointManager:
    """
    Manages workflow checkpoints for faster recovery.

    Checkpoints are snapshots of workflow state that allow skipping
    event replay from the beginning. Instead, we:
    1. Load the most recent checkpoint
    2. Replay only events since that checkpoint

    This dramatically speeds up recovery for long-running workflows.
    """

    def __init__(self, config: CheckpointConfig | None = None):
        """
        Initialize checkpoint manager.

        Args:
            config: Configuration options
        """
        self.config = config or CheckpointConfig.from_env()
        self._storage_path = Path(self.config.storage_path)
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Ensure storage directory exists"""
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def _workflow_path(self, workflow_id: str) -> Path:
        """Get storage path for a workflow's checkpoints"""
        path = self._storage_path / workflow_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _checkpoint_path(self, workflow_id: str, checkpoint_id: str) -> Path:
        """Get path for a specific checkpoint"""
        ext = ".json.gz" if self.config.use_compression else ".json"
        return self._workflow_path(workflow_id) / f"{checkpoint_id}{ext}"

    async def create_checkpoint(
        self,
        workflow_id: str,
        state: WorkflowState,
        checkpoint_id: str | None = None,
    ) -> str:
        """
        Create a checkpoint of workflow state.

        Args:
            workflow_id: ID of the workflow
            state: Current workflow state
            checkpoint_id: Optional ID (auto-generated if not provided)

        Returns:
            Checkpoint ID
        """
        checkpoint_id = checkpoint_id or f"ckpt-{uuid.uuid4().hex[:12]}"

        # Serialize state
        state_dict = {
            "workflow_id": state.workflow_id,
            "workflow_type": state.workflow_type,
            "status": state.status,
            "args": state.args,
            "result": state.result,
            "error": state.error,
            "completed_activities": state.completed_activities,
            "pending_activities": list(state.pending_activities),
            "failed_activities": state.failed_activities,
            "received_signals": state.received_signals,
            "last_sequence": state.last_sequence,
            "last_checkpoint_id": state.last_checkpoint_id,
            "event_count": state.event_count,
            "started_at": state.started_at.isoformat() if state.started_at else None,
            "completed_at": (
                state.completed_at.isoformat() if state.completed_at else None
            ),
            "custom_state": state.custom_state,
        }

        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "workflow_id": workflow_id,
            "created_at": datetime.now(UTC).isoformat(),
            "sequence_number": state.last_sequence,
            "state": state_dict,
        }

        # Save to file
        checkpoint_path = self._checkpoint_path(workflow_id, checkpoint_id)
        json_str = json.dumps(checkpoint_data, default=str)

        if self.config.use_compression:
            data = gzip.compress(json_str.encode("utf-8"))
        else:
            data = json_str.encode("utf-8")

        checkpoint_path.write_bytes(data)

        logger.info(
            f"Created checkpoint {checkpoint_id} for workflow {workflow_id} "
            f"(seq={state.last_sequence}, size={len(data)} bytes)"
        )

        # Cleanup old checkpoints
        await self._cleanup_old_checkpoints(workflow_id)

        return checkpoint_id

    async def load_checkpoint(
        self,
        workflow_id: str,
        checkpoint_id: str | None = None,
    ) -> WorkflowState | None:
        """
        Load workflow state from a checkpoint.

        Args:
            workflow_id: ID of the workflow
            checkpoint_id: Specific checkpoint to load (latest if not provided)

        Returns:
            WorkflowState or None if not found
        """
        if checkpoint_id:
            checkpoint_path = self._checkpoint_path(workflow_id, checkpoint_id)
        else:
            # Get latest checkpoint
            checkpoint_path = await self._get_latest_checkpoint_path(workflow_id)
            if not checkpoint_path:
                return None

        if not checkpoint_path.exists():
            logger.warning(f"Checkpoint not found: {checkpoint_path}")
            return None

        # Load and decompress
        data = checkpoint_path.read_bytes()

        if self.config.use_compression or checkpoint_path.suffix == ".gz":
            try:
                data = gzip.decompress(data)
            except gzip.BadGzipFile:
                pass  # Not compressed

        checkpoint_data = json.loads(data.decode("utf-8"))
        state_dict = checkpoint_data["state"]

        # Reconstruct WorkflowState
        state = WorkflowState(
            workflow_id=state_dict["workflow_id"],
            workflow_type=state_dict.get("workflow_type", ""),
            status=state_dict.get("status", "unknown"),
            args=state_dict.get("args", {}),
            result=state_dict.get("result"),
            error=state_dict.get("error"),
            completed_activities=state_dict.get("completed_activities", {}),
            pending_activities=set(state_dict.get("pending_activities", [])),
            failed_activities=state_dict.get("failed_activities", {}),
            received_signals=state_dict.get("received_signals", []),
            last_sequence=state_dict.get("last_sequence", 0),
            last_checkpoint_id=checkpoint_data["checkpoint_id"],
            event_count=state_dict.get("event_count", 0),
            custom_state=state_dict.get("custom_state", {}),
        )

        # Parse timestamps
        if state_dict.get("started_at"):
            state.started_at = datetime.fromisoformat(state_dict["started_at"])
        if state_dict.get("completed_at"):
            state.completed_at = datetime.fromisoformat(state_dict["completed_at"])

        logger.debug(
            f"Loaded checkpoint {checkpoint_data['checkpoint_id']} "
            f"for workflow {workflow_id}"
        )

        return state

    async def list_checkpoints(self, workflow_id: str) -> list[CheckpointInfo]:
        """List all checkpoints for a workflow"""
        workflow_path = self._workflow_path(workflow_id)
        checkpoints = []

        for file_path in workflow_path.glob("ckpt-*"):
            try:
                # Load metadata
                data = file_path.read_bytes()
                compressed = file_path.suffix == ".gz"

                if compressed:
                    data = gzip.decompress(data)

                checkpoint_data = json.loads(data.decode("utf-8"))

                checkpoints.append(
                    CheckpointInfo(
                        checkpoint_id=checkpoint_data["checkpoint_id"],
                        workflow_id=workflow_id,
                        created_at=datetime.fromisoformat(
                            checkpoint_data["created_at"]
                        ),
                        sequence_number=checkpoint_data["sequence_number"],
                        size_bytes=file_path.stat().st_size,
                        compressed=compressed,
                        event_count=checkpoint_data["state"].get("event_count", 0),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to read checkpoint {file_path}: {e}")

        # Sort by sequence number (newest first)
        checkpoints.sort(key=lambda c: c.sequence_number, reverse=True)

        return checkpoints

    async def _get_latest_checkpoint_path(self, workflow_id: str) -> Path | None:
        """Get path to the latest checkpoint"""
        checkpoints = await self.list_checkpoints(workflow_id)
        if not checkpoints:
            return None

        latest = checkpoints[0]  # Already sorted newest first
        return self._checkpoint_path(workflow_id, latest.checkpoint_id)

    async def _cleanup_old_checkpoints(self, workflow_id: str) -> int:
        """
        Remove old checkpoints beyond retention limit.

        Returns:
            Number of checkpoints removed
        """
        checkpoints = await self.list_checkpoints(workflow_id)

        if len(checkpoints) <= self.config.max_checkpoints_per_workflow:
            return 0

        # Remove oldest checkpoints
        to_remove = checkpoints[self.config.max_checkpoints_per_workflow :]
        removed = 0

        for checkpoint in to_remove:
            try:
                path = self._checkpoint_path(workflow_id, checkpoint.checkpoint_id)
                path.unlink(missing_ok=True)
                removed += 1
                logger.debug(f"Removed old checkpoint: {checkpoint.checkpoint_id}")
            except Exception as e:
                logger.warning(f"Failed to remove checkpoint: {e}")

        return removed

    async def delete_checkpoint(
        self,
        workflow_id: str,
        checkpoint_id: str,
    ) -> bool:
        """Delete a specific checkpoint"""
        try:
            path = self._checkpoint_path(workflow_id, checkpoint_id)
            path.unlink(missing_ok=True)
            logger.info(f"Deleted checkpoint {checkpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")
            return False

    async def delete_all_checkpoints(self, workflow_id: str) -> int:
        """Delete all checkpoints for a workflow"""
        checkpoints = await self.list_checkpoints(workflow_id)
        deleted = 0

        for checkpoint in checkpoints:
            if await self.delete_checkpoint(workflow_id, checkpoint.checkpoint_id):
                deleted += 1

        return deleted


# =============================================================================
# Auto-Checkpointing
# =============================================================================


class AutoCheckpointer:
    """
    Automatic checkpoint creation based on events or time.

    Usage:
        checkpointer = AutoCheckpointer(workflow, manager)
        await checkpointer.start()

        # In workflow, after each event:
        await checkpointer.on_event(event)
    """

    def __init__(
        self,
        workflow_id: str,
        manager: CheckpointManager,
        get_state: callable,
    ):
        """
        Initialize auto-checkpointer.

        Args:
            workflow_id: ID of the workflow
            manager: Checkpoint manager
            get_state: Callable that returns current WorkflowState
        """
        self.workflow_id = workflow_id
        self.manager = manager
        self.get_state = get_state

        self._events_since_checkpoint = 0
        self._last_checkpoint_time = datetime.now(UTC)
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start automatic checkpointing"""
        self._running = True
        self._task = asyncio.create_task(self._time_based_checkpoint_loop())

    async def stop(self) -> None:
        """Stop automatic checkpointing"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def on_event(self, event: Any) -> None:
        """
        Called after each event is processed.

        Creates checkpoint if event threshold reached.
        """
        self._events_since_checkpoint += 1

        if (
            self._events_since_checkpoint
            >= self.manager.config.checkpoint_interval_events
        ):
            await self._create_checkpoint()

    async def _time_based_checkpoint_loop(self) -> None:
        """Background task for time-based checkpoints"""
        interval = self.manager.config.checkpoint_interval_seconds

        while self._running:
            await asyncio.sleep(interval)

            if self._events_since_checkpoint > 0:
                await self._create_checkpoint()

    async def _create_checkpoint(self) -> None:
        """Create a checkpoint"""
        try:
            state = self.get_state()
            if state:
                await self.manager.create_checkpoint(self.workflow_id, state)
                self._events_since_checkpoint = 0
                self._last_checkpoint_time = datetime.now(UTC)
        except Exception as e:
            logger.error(f"Auto-checkpoint failed: {e}")


# =============================================================================
# Singleton
# =============================================================================

_default_manager: CheckpointManager | None = None


def get_checkpoint_manager() -> CheckpointManager:
    """Get the default checkpoint manager"""
    global _default_manager
    if _default_manager is None:
        _default_manager = CheckpointManager()
    return _default_manager


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CheckpointManager",
    "CheckpointConfig",
    "CheckpointInfo",
    "AutoCheckpointer",
    "get_checkpoint_manager",
]
