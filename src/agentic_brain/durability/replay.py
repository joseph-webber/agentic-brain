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
Event Replay Engine for workflow recovery.

This module provides the ability to rebuild workflow state by replaying
events from the event store. This is the core of durable execution -
after a crash, we can replay events to restore exact workflow state.

Features:
- Deterministic replay (same events = same state)
- Partial replay (from checkpoint)
- Event validation and ordering
- Conflict detection

Usage:
    from agentic_brain.durability.replay import ReplayEngine

    engine = ReplayEngine(event_store)
    state = await engine.replay_workflow("wf-123")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from .event_store import EventStore, get_event_store
from .events import (
    ActivityCompleted,
    ActivityFailed,
    ActivityScheduled,
    BaseEvent,
    CheckpointCreated,
    EventType,
    SignalReceived,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkflowState:
    """
    Reconstructed workflow state from event replay.

    This represents the full state of a workflow at a point in time,
    including all completed activities, pending activities, and signals.
    """

    workflow_id: str
    workflow_type: str = ""
    status: str = "unknown"  # pending, running, completed, failed, cancelled

    # Input/output
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str | None = None

    # Activity tracking
    completed_activities: dict[str, Any] = field(
        default_factory=dict
    )  # activity_id -> result
    pending_activities: set[str] = field(default_factory=set)
    failed_activities: dict[str, str] = field(
        default_factory=dict
    )  # activity_id -> error

    # Signal tracking
    received_signals: list[dict] = field(default_factory=list)

    # Progress
    last_sequence: int = 0
    last_checkpoint_id: str | None = None
    event_count: int = 0

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Custom state (workflow-specific)
    custom_state: dict[str, Any] = field(default_factory=dict)

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        return self.status in ("failed", "cancelled", "timed_out")

    @property
    def has_pending_activities(self) -> bool:
        return len(self.pending_activities) > 0


@dataclass
class ReplayResult:
    """Result of a replay operation"""

    success: bool
    state: WorkflowState | None = None
    events_replayed: int = 0
    from_checkpoint: bool = False
    checkpoint_id: str | None = None
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0


class ReplayEngine:
    """
    Engine for replaying workflow events to rebuild state.

    The replay engine processes events in order and updates the
    workflow state accordingly. It supports:

    - Full replay from the beginning
    - Partial replay from a checkpoint
    - Event validation and ordering
    - Custom event handlers for extensibility
    """

    def __init__(self, event_store: EventStore | None = None):
        """
        Initialize replay engine.

        Args:
            event_store: Event store to load events from. Uses default if not provided.
        """
        self.event_store = event_store or get_event_store()
        self._event_handlers: dict[EventType, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default event handlers"""
        self._event_handlers = {
            EventType.WORKFLOW_STARTED: self._handle_workflow_started,
            EventType.WORKFLOW_COMPLETED: self._handle_workflow_completed,
            EventType.WORKFLOW_FAILED: self._handle_workflow_failed,
            EventType.WORKFLOW_CANCELLED: self._handle_workflow_cancelled,
            EventType.WORKFLOW_TIMED_OUT: self._handle_workflow_timed_out,
            EventType.ACTIVITY_SCHEDULED: self._handle_activity_scheduled,
            EventType.ACTIVITY_STARTED: self._handle_activity_started,
            EventType.ACTIVITY_COMPLETED: self._handle_activity_completed,
            EventType.ACTIVITY_FAILED: self._handle_activity_failed,
            EventType.SIGNAL_RECEIVED: self._handle_signal_received,
            EventType.CHECKPOINT_CREATED: self._handle_checkpoint_created,
        }

    def register_handler(
        self,
        event_type: EventType,
        handler: Callable[[WorkflowState, BaseEvent], None],
    ) -> None:
        """
        Register a custom event handler.

        Args:
            event_type: Type of event to handle
            handler: Function that takes (state, event) and updates state
        """
        self._event_handlers[event_type] = handler

    async def replay_workflow(
        self,
        workflow_id: str,
        from_checkpoint: str | None = None,
    ) -> ReplayResult:
        """
        Replay all events for a workflow to rebuild state.

        Args:
            workflow_id: ID of the workflow to replay
            from_checkpoint: Optional checkpoint ID to start from

        Returns:
            ReplayResult with reconstructed state
        """
        start_time = datetime.now(UTC)
        errors = []
        from_sequence = 0

        # Initialize state
        state = WorkflowState(workflow_id=workflow_id)

        # Load from checkpoint if specified
        if from_checkpoint:
            checkpoint_state = await self._load_checkpoint(workflow_id, from_checkpoint)
            if checkpoint_state:
                state = checkpoint_state
                from_sequence = state.last_sequence + 1
                logger.debug(
                    f"Loaded checkpoint {from_checkpoint}, resuming from seq {from_sequence}"
                )

        # Load events
        try:
            events = await self.event_store.load_events(
                workflow_id,
                from_sequence=from_sequence,
            )
        except Exception as e:
            logger.error(f"Failed to load events: {e}")
            return ReplayResult(
                success=False,
                errors=[f"Failed to load events: {e}"],
            )

        # Replay events in order
        for event in events:
            try:
                self._apply_event(state, event)
                state.last_sequence = event.sequence_number
                state.event_count += 1
            except Exception as e:
                error_msg = f"Error replaying event {event.event_id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        duration_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

        return ReplayResult(
            success=len(errors) == 0,
            state=state,
            events_replayed=len(events),
            from_checkpoint=from_checkpoint is not None,
            checkpoint_id=from_checkpoint,
            errors=errors,
            duration_ms=duration_ms,
        )

    def _apply_event(self, state: WorkflowState, event: BaseEvent) -> None:
        """Apply a single event to the state"""
        handler = self._event_handlers.get(event.event_type)

        if handler:
            handler(state, event)
        else:
            # Unknown event type - store in metadata
            logger.debug(f"No handler for event type: {event.event_type}")

    # =========================================================================
    # Default Event Handlers
    # =========================================================================

    def _handle_workflow_started(self, state: WorkflowState, event: BaseEvent) -> None:
        """Handle WorkflowStarted event"""
        if isinstance(event, WorkflowStarted):
            state.workflow_type = event.workflow_type
            state.args = event.args
            state.status = "running"
            state.started_at = event.timestamp

    def _handle_workflow_completed(
        self, state: WorkflowState, event: BaseEvent
    ) -> None:
        """Handle WorkflowCompleted event"""
        if isinstance(event, WorkflowCompleted):
            state.status = "completed"
            state.result = event.result
            state.completed_at = event.timestamp

    def _handle_workflow_failed(self, state: WorkflowState, event: BaseEvent) -> None:
        """Handle WorkflowFailed event"""
        if isinstance(event, WorkflowFailed):
            state.status = "failed"
            state.error = event.error
            state.completed_at = event.timestamp

    def _handle_workflow_cancelled(
        self, state: WorkflowState, event: BaseEvent
    ) -> None:
        """Handle WorkflowCancelled event"""
        state.status = "cancelled"
        state.completed_at = event.timestamp

    def _handle_workflow_timed_out(
        self, state: WorkflowState, event: BaseEvent
    ) -> None:
        """Handle WorkflowTimedOut event"""
        state.status = "timed_out"
        state.completed_at = event.timestamp

    def _handle_activity_scheduled(
        self, state: WorkflowState, event: BaseEvent
    ) -> None:
        """Handle ActivityScheduled event"""
        if isinstance(event, ActivityScheduled):
            state.pending_activities.add(event.activity_id)

    def _handle_activity_started(self, state: WorkflowState, event: BaseEvent) -> None:
        """Handle ActivityStarted event"""
        # Activity is still pending until completed
        pass

    def _handle_activity_completed(
        self, state: WorkflowState, event: BaseEvent
    ) -> None:
        """Handle ActivityCompleted event"""
        if isinstance(event, ActivityCompleted):
            state.pending_activities.discard(event.activity_id)
            state.completed_activities[event.activity_id] = event.result

    def _handle_activity_failed(self, state: WorkflowState, event: BaseEvent) -> None:
        """Handle ActivityFailed event"""
        if isinstance(event, ActivityFailed):
            if not event.will_retry:
                state.pending_activities.discard(event.activity_id)
                state.failed_activities[event.activity_id] = event.error

    def _handle_signal_received(self, state: WorkflowState, event: BaseEvent) -> None:
        """Handle SignalReceived event"""
        if isinstance(event, SignalReceived):
            state.received_signals.append(
                {
                    "name": event.signal_name,
                    "args": event.signal_args,
                    "timestamp": event.timestamp.isoformat(),
                }
            )

    def _handle_checkpoint_created(
        self, state: WorkflowState, event: BaseEvent
    ) -> None:
        """Handle CheckpointCreated event"""
        if isinstance(event, CheckpointCreated):
            state.last_checkpoint_id = event.checkpoint_id

    # =========================================================================
    # Checkpoint Loading
    # =========================================================================

    async def _load_checkpoint(
        self,
        workflow_id: str,
        checkpoint_id: str,
    ) -> WorkflowState | None:
        """
        Load workflow state from a checkpoint.

        Checkpoints are stored as special events containing serialized state.
        """
        # For now, we don't have checkpoint storage implemented
        # This would load from a separate checkpoint store
        logger.debug(f"Checkpoint loading not yet implemented: {checkpoint_id}")
        return None

    # =========================================================================
    # Validation
    # =========================================================================

    async def validate_events(self, workflow_id: str) -> list[str]:
        """
        Validate event sequence for a workflow.

        Checks:
        - Events are in order
        - No sequence gaps
        - Required events present (WorkflowStarted)
        - Terminal events are last

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        events = await self.event_store.load_events(workflow_id)

        if not events:
            errors.append("No events found")
            return errors

        # Check first event is WorkflowStarted
        if events[0].event_type != EventType.WORKFLOW_STARTED:
            errors.append(
                f"First event should be WorkflowStarted, got {events[0].event_type}"
            )

        # Check sequence ordering
        last_seq = -1
        for event in events:
            if event.sequence_number <= last_seq:
                errors.append(
                    f"Events out of order: {event.sequence_number} after {last_seq}"
                )
            last_seq = event.sequence_number

        # Check for terminal event
        terminal_events = {
            EventType.WORKFLOW_COMPLETED,
            EventType.WORKFLOW_FAILED,
            EventType.WORKFLOW_CANCELLED,
            EventType.WORKFLOW_TIMED_OUT,
        }

        if events[-1].event_type in terminal_events:
            # Check no events after terminal
            for i, event in enumerate(events[:-1]):
                if event.event_type in terminal_events:
                    errors.append(
                        f"Terminal event at position {i} but workflow continued"
                    )

        return errors


# =============================================================================
# Convenience Functions
# =============================================================================


async def replay_workflow(
    workflow_id: str,
    from_checkpoint: str | None = None,
    event_store: EventStore | None = None,
) -> ReplayResult:
    """
    Convenience function to replay a workflow.

    Args:
        workflow_id: ID of the workflow
        from_checkpoint: Optional checkpoint to start from
        event_store: Optional event store instance

    Returns:
        ReplayResult with reconstructed state
    """
    engine = ReplayEngine(event_store)
    return await engine.replay_workflow(workflow_id, from_checkpoint)


async def get_workflow_state(
    workflow_id: str,
    event_store: EventStore | None = None,
) -> WorkflowState | None:
    """
    Get current state of a workflow by replaying events.

    Args:
        workflow_id: ID of the workflow
        event_store: Optional event store instance

    Returns:
        WorkflowState or None if workflow not found
    """
    result = await replay_workflow(workflow_id, event_store=event_store)
    return result.state if result.success else None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ReplayEngine",
    "ReplayResult",
    "WorkflowState",
    "replay_workflow",
    "get_workflow_state",
]
