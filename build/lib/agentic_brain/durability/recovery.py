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
Recovery Manager for crash recovery and workflow resumption.

This module handles automatic discovery and recovery of incomplete
workflows after a crash or restart. It scans for workflows that
were running when the process stopped and resumes them.

Features:
- Automatic recovery on startup
- Incomplete workflow detection
- Event replay and resumption
- Duplicate execution prevention (idempotency)

Usage:
    from agentic_brain.durability.recovery import RecoveryManager

    manager = RecoveryManager()
    await manager.recover_all()
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .checkpoints import CheckpointManager, get_checkpoint_manager
from .event_store import EventStore, get_event_store
from .events import EventType, WorkflowStarted
from .replay import ReplayEngine, ReplayResult, WorkflowState

logger = logging.getLogger(__name__)


@dataclass
class RecoveryConfig:
    """Configuration for recovery manager"""

    # Recovery behavior
    auto_recover_on_startup: bool = True
    max_concurrent_recoveries: int = 5
    recovery_timeout_seconds: float = 300.0

    # Workflow discovery
    scan_interval_seconds: float = 60.0
    stale_workflow_hours: float = 24.0  # Consider workflows stale after this

    # Idempotency
    idempotency_key_ttl_hours: float = 24.0

    @classmethod
    def from_env(cls) -> RecoveryConfig:
        """Create config from environment variables"""
        return cls(
            auto_recover_on_startup=os.getenv("RECOVERY_AUTO", "true").lower()
            == "true",
            max_concurrent_recoveries=int(os.getenv("RECOVERY_CONCURRENCY", "5")),
        )


@dataclass
class RecoveryResult:
    """Result of a recovery operation"""

    workflow_id: str
    success: bool
    recovered_from_checkpoint: bool = False
    checkpoint_id: str | None = None
    events_replayed: int = 0
    resumed: bool = False
    error: str | None = None
    duration_ms: int = 0


@dataclass
class IncompleteWorkflow:
    """Information about an incomplete workflow"""

    workflow_id: str
    workflow_type: str
    status: str
    last_event_time: datetime | None
    event_count: int
    has_checkpoint: bool
    latest_checkpoint_id: str | None = None


class RecoveryManager:
    """
    Manages crash recovery and workflow resumption.

    On startup:
    1. Scans for incomplete workflows (started but not completed/failed)
    2. Replays events to restore state
    3. Optionally resumes execution

    Also provides idempotency checking to prevent duplicate executions.
    """

    def __init__(
        self,
        config: RecoveryConfig | None = None,
        event_store: EventStore | None = None,
        checkpoint_manager: CheckpointManager | None = None,
    ):
        """
        Initialize recovery manager.

        Args:
            config: Configuration options
            event_store: Event store for loading events
            checkpoint_manager: Checkpoint manager for faster recovery
        """
        self.config = config or RecoveryConfig.from_env()
        self.event_store = event_store or get_event_store()
        self.checkpoint_manager = checkpoint_manager or get_checkpoint_manager()
        self.replay_engine = ReplayEngine(self.event_store)

        # Track workflows being recovered
        self._recovering: set[str] = set()

        # Idempotency keys (activity_id -> timestamp)
        self._idempotency_keys: dict[str, datetime] = {}

        # Workflow resume callbacks
        self._resume_callbacks: dict[str, Callable] = {}

    async def scan_incomplete_workflows(self) -> list[IncompleteWorkflow]:
        """
        Scan for workflows that were running but not completed.

        Returns:
            List of incomplete workflows
        """
        incomplete = []

        # This requires iterating over workflow topics
        # In a real implementation, we'd have a registry or index
        # For now, we scan the checkpoint directory

        checkpoint_path = Path(self.checkpoint_manager.config.storage_path)
        if not checkpoint_path.exists():
            return incomplete

        for workflow_dir in checkpoint_path.iterdir():
            if not workflow_dir.is_dir():
                continue

            workflow_id = workflow_dir.name

            try:
                # Replay to get current state
                result = await self.replay_engine.replay_workflow(workflow_id)

                if not result.success or not result.state:
                    continue

                state = result.state

                # Check if incomplete (running, not terminal)
                if state.status in ("running", "pending"):
                    # Get checkpoint info
                    checkpoints = await self.checkpoint_manager.list_checkpoints(
                        workflow_id
                    )

                    incomplete.append(
                        IncompleteWorkflow(
                            workflow_id=workflow_id,
                            workflow_type=state.workflow_type,
                            status=state.status,
                            last_event_time=state.completed_at or state.started_at,
                            event_count=state.event_count,
                            has_checkpoint=len(checkpoints) > 0,
                            latest_checkpoint_id=(
                                checkpoints[0].checkpoint_id if checkpoints else None
                            ),
                        )
                    )

            except Exception as e:
                logger.warning(f"Failed to scan workflow {workflow_id}: {e}")

        logger.info(f"Found {len(incomplete)} incomplete workflows")
        return incomplete

    async def recover_workflow(
        self,
        workflow_id: str,
        resume: bool = True,
    ) -> RecoveryResult:
        """
        Recover a single workflow.

        Args:
            workflow_id: ID of the workflow to recover
            resume: Whether to resume execution after recovery

        Returns:
            RecoveryResult with details
        """
        start_time = datetime.now(timezone.utc)

        if workflow_id in self._recovering:
            return RecoveryResult(
                workflow_id=workflow_id,
                success=False,
                error="Recovery already in progress",
            )

        self._recovering.add(workflow_id)

        try:
            # Try to load from checkpoint first
            checkpoint_id = None
            state = None
            events_replayed = 0

            checkpoints = await self.checkpoint_manager.list_checkpoints(workflow_id)
            if checkpoints:
                checkpoint_id = checkpoints[0].checkpoint_id
                state = await self.checkpoint_manager.load_checkpoint(
                    workflow_id, checkpoint_id
                )
                logger.info(
                    f"Loaded checkpoint {checkpoint_id} for workflow {workflow_id}"
                )

            # Replay events (from checkpoint or beginning)
            start_sequence = state.last_sequence + 1 if state else 0
            logger.debug(f"Starting replay from sequence {start_sequence}")

            result = await self.replay_engine.replay_workflow(
                workflow_id,
                from_checkpoint=checkpoint_id,
            )

            if not result.success:
                return RecoveryResult(
                    workflow_id=workflow_id,
                    success=False,
                    error="; ".join(result.errors),
                )

            events_replayed = result.events_replayed
            state = result.state

            # Resume if requested and workflow is resumable
            resumed = False
            if resume and state and state.status == "running":
                callback = self._resume_callbacks.get(state.workflow_type)
                if callback:
                    try:
                        await callback(workflow_id, state)
                        resumed = True
                    except Exception as e:
                        logger.error(f"Failed to resume workflow: {e}")

            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            return RecoveryResult(
                workflow_id=workflow_id,
                success=True,
                recovered_from_checkpoint=checkpoint_id is not None,
                checkpoint_id=checkpoint_id,
                events_replayed=events_replayed,
                resumed=resumed,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error(f"Recovery failed for {workflow_id}: {e}")
            return RecoveryResult(
                workflow_id=workflow_id,
                success=False,
                error=str(e),
            )
        finally:
            self._recovering.discard(workflow_id)

    async def recover_all(self, resume: bool = True) -> list[RecoveryResult]:
        """
        Recover all incomplete workflows.

        Args:
            resume: Whether to resume execution after recovery

        Returns:
            List of recovery results
        """
        incomplete = await self.scan_incomplete_workflows()

        if not incomplete:
            logger.info("No incomplete workflows to recover")
            return []

        logger.info(f"Recovering {len(incomplete)} workflows...")

        # Recover with concurrency limit
        semaphore = asyncio.Semaphore(self.config.max_concurrent_recoveries)

        async def recover_with_limit(wf: IncompleteWorkflow) -> RecoveryResult:
            async with semaphore:
                return await self.recover_workflow(wf.workflow_id, resume)

        tasks = [recover_with_limit(wf) for wf in incomplete]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to RecoveryResult
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    RecoveryResult(
                        workflow_id=incomplete[i].workflow_id,
                        success=False,
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)

        # Log summary
        successful = sum(1 for r in final_results if r.success)
        logger.info(f"Recovery complete: {successful}/{len(final_results)} successful")

        return final_results

    def register_resume_callback(
        self,
        workflow_type: str,
        callback: Callable[[str, WorkflowState], Any],
    ) -> None:
        """
        Register a callback for resuming a workflow type.

        Args:
            workflow_type: Type of workflow
            callback: Async function(workflow_id, state) to resume
        """
        self._resume_callbacks[workflow_type] = callback

    # =========================================================================
    # Idempotency
    # =========================================================================

    def check_idempotency(self, key: str) -> bool:
        """
        Check if an operation has already been executed.

        Args:
            key: Idempotency key (e.g., activity_id)

        Returns:
            True if already executed (should skip)
        """
        if key not in self._idempotency_keys:
            return False

        # Check if expired
        timestamp = self._idempotency_keys[key]
        ttl = timedelta(hours=self.config.idempotency_key_ttl_hours)

        if datetime.now(timezone.utc) - timestamp > ttl:
            del self._idempotency_keys[key]
            return False

        return True

    def record_idempotency(self, key: str) -> None:
        """
        Record that an operation was executed.

        Args:
            key: Idempotency key
        """
        self._idempotency_keys[key] = datetime.now(timezone.utc)

    def clear_idempotency(self, key: str) -> None:
        """Clear an idempotency key"""
        self._idempotency_keys.pop(key, None)

    async def cleanup_expired_keys(self) -> int:
        """
        Remove expired idempotency keys.

        Returns:
            Number of keys removed
        """
        ttl = timedelta(hours=self.config.idempotency_key_ttl_hours)
        now = datetime.now(timezone.utc)

        expired = [key for key, ts in self._idempotency_keys.items() if now - ts > ttl]

        for key in expired:
            del self._idempotency_keys[key]

        return len(expired)


# =============================================================================
# Startup Recovery
# =============================================================================


async def recover_on_startup(resume: bool = True) -> list[RecoveryResult]:
    """
    Convenience function to run recovery on application startup.

    Args:
        resume: Whether to resume workflows

    Returns:
        List of recovery results
    """
    manager = RecoveryManager()
    return await manager.recover_all(resume)


# =============================================================================
# Singleton
# =============================================================================

_default_manager: RecoveryManager | None = None


def get_recovery_manager() -> RecoveryManager:
    """Get the default recovery manager"""
    global _default_manager
    if _default_manager is None:
        _default_manager = RecoveryManager()
    return _default_manager


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "RecoveryManager",
    "RecoveryConfig",
    "RecoveryResult",
    "IncompleteWorkflow",
    "recover_on_startup",
    "get_recovery_manager",
]
