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
Event types for durable workflow execution.

This module defines all event types used for event sourcing in the
durability system. Every state change in a workflow is recorded as
an immutable event, enabling full replay and crash recovery.

Event Categories:
- WorkflowEvents: Lifecycle events (started, completed, failed)
- ActivityEvents: Activity execution events
- SignalEvents: External input events
- TimerEvents: Timer/delay events
- CheckpointEvents: State snapshot events

Usage:
    from agentic_brain.durability.events import (
        WorkflowStarted,
        ActivityCompleted,
        SignalReceived,
    )

    event = WorkflowStarted(
        workflow_id="wf-123",
        workflow_type="ai-analysis",
        args={"query": "analyze data"}
    )
"""

from __future__ import annotations

import uuid
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """All event types in the system"""

    # Workflow lifecycle
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    WORKFLOW_TIMED_OUT = "workflow_timed_out"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"

    # Activity lifecycle
    ACTIVITY_SCHEDULED = "activity_scheduled"
    ACTIVITY_STARTED = "activity_started"
    ACTIVITY_COMPLETED = "activity_completed"
    ACTIVITY_FAILED = "activity_failed"
    ACTIVITY_RETRIED = "activity_retried"
    ACTIVITY_TIMED_OUT = "activity_timed_out"
    ACTIVITY_CANCELLED = "activity_cancelled"
    ACTIVITY_HEARTBEAT = "activity_heartbeat"

    # Signals and queries
    SIGNAL_RECEIVED = "signal_received"
    SIGNAL_PROCESSED = "signal_processed"
    QUERY_EXECUTED = "query_executed"

    # Timers
    TIMER_STARTED = "timer_started"
    TIMER_FIRED = "timer_fired"
    TIMER_CANCELLED = "timer_cancelled"

    # Checkpoints
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_LOADED = "checkpoint_loaded"

    # Child workflows
    CHILD_WORKFLOW_STARTED = "child_workflow_started"
    CHILD_WORKFLOW_COMPLETED = "child_workflow_completed"
    CHILD_WORKFLOW_FAILED = "child_workflow_failed"

    # LLM-specific ()
    LLM_REQUEST_STARTED = "llm_request_started"
    LLM_REQUEST_COMPLETED = "llm_request_completed"
    LLM_REQUEST_FAILED = "llm_request_failed"
    LLM_FALLBACK_TRIGGERED = "llm_fallback_triggered"

    # RAG-specific
    RAG_QUERY_STARTED = "rag_query_started"
    RAG_QUERY_COMPLETED = "rag_query_completed"
    RAG_DOCUMENTS_RETRIEVED = "rag_documents_retrieved"


@dataclass
class BaseEvent(ABC):
    """
    Base class for all workflow events.

    Every event has:
    - event_id: Unique identifier
    - workflow_id: ID of the workflow this event belongs to
    - sequence_number: Order of this event in the workflow
    - timestamp: When the event occurred
    - event_type: Type of the event
    """

    workflow_id: str
    event_type: EventType = EventType.WORKFLOW_STARTED
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sequence_number: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary for storage"""
        return {
            "event_id": self.event_id,
            "workflow_id": self.workflow_id,
            "event_type": self.event_type.value,
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "data": self._get_event_data(),
        }

    def _get_event_data(self) -> dict[str, Any]:
        """Override in subclasses to add event-specific data"""
        return {}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseEvent:
        """Deserialize events from the event store.

        The event store uses this method as the single entrypoint for
        deserialization. For unknown/extended event payloads, this will fall
        back to :class:`WorkflowEvent` so custom domain events can still be
        preserved.
        """

        return WorkflowEvent.from_dict(data)


@dataclass
class WorkflowEvent(BaseEvent):
    """Generic workflow event with custom data payload."""

    data: dict[str, Any] = field(default_factory=dict)

    def _get_event_data(self) -> dict[str, Any]:
        return self.data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseEvent:
        """Deserialize event from dictionary"""
        event_type = EventType(data["event_type"])
        event_class = EVENT_TYPE_MAP.get(event_type, WorkflowEvent)

        base_fields = {
            "event_id": data["event_id"],
            "workflow_id": data["workflow_id"],
            "event_type": event_type,
            "sequence_number": data["sequence_number"],
            "timestamp": datetime.fromisoformat(data["timestamp"]),
            "metadata": data.get("metadata", {}),
        }

        # Add event-specific data
        event_data = data.get("data", {})

        # If the payload doesn't match the expected event class (common for
        # custom/extended domain events), fall back to WorkflowEvent to preserve
        # the raw data.
        try:
            return event_class(**base_fields, **event_data)
        except TypeError:
            return WorkflowEvent(**base_fields, data=event_data)


# =============================================================================
# Workflow Events
# =============================================================================


@dataclass
class WorkflowStarted(BaseEvent):
    """Workflow execution began"""

    workflow_type: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    task_queue: str = "default"
    parent_workflow_id: str | None = None

    def __post_init__(self):
        self.event_type = EventType.WORKFLOW_STARTED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "workflow_type": self.workflow_type,
            "args": self.args,
            "task_queue": self.task_queue,
            "parent_workflow_id": self.parent_workflow_id,
        }


@dataclass
class WorkflowCompleted(BaseEvent):
    """Workflow completed successfully"""

    result: Any = None
    duration_ms: int = 0

    def __post_init__(self):
        self.event_type = EventType.WORKFLOW_COMPLETED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "result": self.result,
            "duration_ms": self.duration_ms,
        }


@dataclass
class WorkflowFailed(BaseEvent):
    """Workflow failed with error"""

    error: str = ""
    error_type: str = ""
    stack_trace: str | None = None
    retryable: bool = True

    def __post_init__(self):
        self.event_type = EventType.WORKFLOW_FAILED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "error": self.error,
            "error_type": self.error_type,
            "stack_trace": self.stack_trace,
            "retryable": self.retryable,
        }


@dataclass
class WorkflowCancelled(BaseEvent):
    """Workflow was cancelled"""

    reason: str = ""
    cancelled_by: str | None = None

    def __post_init__(self):
        self.event_type = EventType.WORKFLOW_CANCELLED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "cancelled_by": self.cancelled_by,
        }


@dataclass
class WorkflowTimedOut(BaseEvent):
    """Workflow exceeded time limit"""

    timeout_type: str = "execution"  # execution, run, task
    timeout_seconds: int = 0

    def __post_init__(self):
        self.event_type = EventType.WORKFLOW_TIMED_OUT

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "timeout_type": self.timeout_type,
            "timeout_seconds": self.timeout_seconds,
        }


# =============================================================================
# Activity Events
# =============================================================================


@dataclass
class ActivityScheduled(BaseEvent):
    """Activity was scheduled for execution"""

    activity_id: str = ""
    activity_type: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    task_queue: str = "default"

    def __post_init__(self):
        self.event_type = EventType.ACTIVITY_SCHEDULED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "activity_type": self.activity_type,
            "args": self.args,
            "task_queue": self.task_queue,
        }


@dataclass
class ActivityStarted(BaseEvent):
    """Activity execution began"""

    activity_id: str = ""
    worker_id: str = ""
    attempt: int = 1

    def __post_init__(self):
        self.event_type = EventType.ACTIVITY_STARTED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "worker_id": self.worker_id,
            "attempt": self.attempt,
        }


@dataclass
class ActivityCompleted(BaseEvent):
    """Activity completed successfully"""

    activity_id: str = ""
    result: Any = None
    duration_ms: int = 0

    def __post_init__(self):
        self.event_type = EventType.ACTIVITY_COMPLETED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "result": self.result,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ActivityFailed(BaseEvent):
    """Activity failed with error"""

    activity_id: str = ""
    error: str = ""
    error_type: str = ""
    attempt: int = 1
    will_retry: bool = False

    def __post_init__(self):
        self.event_type = EventType.ACTIVITY_FAILED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "error": self.error,
            "error_type": self.error_type,
            "attempt": self.attempt,
            "will_retry": self.will_retry,
        }


@dataclass
class ActivityHeartbeat(BaseEvent):
    """Activity sent heartbeat"""

    activity_id: str = ""
    progress: float = 0.0
    details: str = ""

    def __post_init__(self):
        self.event_type = EventType.ACTIVITY_HEARTBEAT

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "progress": self.progress,
            "details": self.details,
        }


# =============================================================================
# Signal Events
# =============================================================================


@dataclass
class SignalReceived(BaseEvent):
    """External signal received by workflow"""

    signal_name: str = ""
    signal_args: Any = None
    sender: str | None = None

    def __post_init__(self):
        self.event_type = EventType.SIGNAL_RECEIVED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "signal_name": self.signal_name,
            "signal_args": self.signal_args,
            "sender": self.sender,
        }


@dataclass
class SignalProcessed(BaseEvent):
    """Signal was processed by handler"""

    signal_name: str = ""
    result: Any = None

    def __post_init__(self):
        self.event_type = EventType.SIGNAL_PROCESSED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "signal_name": self.signal_name,
            "result": self.result,
        }


# =============================================================================
# Timer Events
# =============================================================================


@dataclass
class TimerStarted(BaseEvent):
    """Timer was started"""

    timer_id: str = ""
    duration_seconds: float = 0.0
    fire_at: datetime | None = None

    def __post_init__(self):
        self.event_type = EventType.TIMER_STARTED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "timer_id": self.timer_id,
            "duration_seconds": self.duration_seconds,
            "fire_at": self.fire_at.isoformat() if self.fire_at else None,
        }


@dataclass
class TimerFired(BaseEvent):
    """Timer fired (delay completed)"""

    timer_id: str = ""

    def __post_init__(self):
        self.event_type = EventType.TIMER_FIRED

    def _get_event_data(self) -> dict[str, Any]:
        return {"timer_id": self.timer_id}


# =============================================================================
# Checkpoint Events
# =============================================================================


@dataclass
class CheckpointCreated(BaseEvent):
    """Workflow state was checkpointed"""

    checkpoint_id: str = ""
    state_size_bytes: int = 0
    events_since_last: int = 0

    def __post_init__(self):
        self.event_type = EventType.CHECKPOINT_CREATED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "state_size_bytes": self.state_size_bytes,
            "events_since_last": self.events_since_last,
        }


@dataclass
class CheckpointLoaded(BaseEvent):
    """Workflow state was restored from checkpoint"""

    checkpoint_id: str = ""
    events_to_replay: int = 0

    def __post_init__(self):
        self.event_type = EventType.CHECKPOINT_LOADED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "events_to_replay": self.events_to_replay,
        }


# =============================================================================
# LLM Events ()
# =============================================================================


@dataclass
class LLMRequestStarted(BaseEvent):
    """LLM request began"""

    request_id: str = ""
    provider: str = ""
    model: str = ""
    prompt_tokens: int = 0

    def __post_init__(self):
        self.event_type = EventType.LLM_REQUEST_STARTED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
        }


@dataclass
class LLMRequestCompleted(BaseEvent):
    """LLM request completed"""

    request_id: str = ""
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    # Don't store full response - just metadata for replay
    response_hash: str = ""

    def __post_init__(self):
        self.event_type = EventType.LLM_REQUEST_COMPLETED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "duration_ms": self.duration_ms,
            "response_hash": self.response_hash,
        }


@dataclass
class LLMFallbackTriggered(BaseEvent):
    """LLM fallback was triggered"""

    request_id: str = ""
    from_provider: str = ""
    to_provider: str = ""
    reason: str = ""

    def __post_init__(self):
        self.event_type = EventType.LLM_FALLBACK_TRIGGERED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "from_provider": self.from_provider,
            "to_provider": self.to_provider,
            "reason": self.reason,
        }


# =============================================================================
# RAG Events
# =============================================================================


@dataclass
class RAGQueryStarted(BaseEvent):
    """RAG query began"""

    query_id: str = ""
    query_text: str = ""
    top_k: int = 10

    def __post_init__(self):
        self.event_type = EventType.RAG_QUERY_STARTED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "top_k": self.top_k,
        }


@dataclass
class RAGDocumentsRetrieved(BaseEvent):
    """RAG documents were retrieved"""

    query_id: str = ""
    document_count: int = 0
    document_ids: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.event_type = EventType.RAG_DOCUMENTS_RETRIEVED

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "document_count": self.document_count,
            "document_ids": self.document_ids,
        }


# =============================================================================
# Event Type Mapping
# =============================================================================

EVENT_TYPE_MAP: dict[EventType, type[BaseEvent]] = {
    EventType.WORKFLOW_STARTED: WorkflowStarted,
    EventType.WORKFLOW_COMPLETED: WorkflowCompleted,
    EventType.WORKFLOW_FAILED: WorkflowFailed,
    EventType.WORKFLOW_CANCELLED: WorkflowCancelled,
    EventType.WORKFLOW_TIMED_OUT: WorkflowTimedOut,
    EventType.ACTIVITY_SCHEDULED: ActivityScheduled,
    EventType.ACTIVITY_STARTED: ActivityStarted,
    EventType.ACTIVITY_COMPLETED: ActivityCompleted,
    EventType.ACTIVITY_FAILED: ActivityFailed,
    EventType.ACTIVITY_HEARTBEAT: ActivityHeartbeat,
    EventType.SIGNAL_RECEIVED: SignalReceived,
    EventType.SIGNAL_PROCESSED: SignalProcessed,
    EventType.TIMER_STARTED: TimerStarted,
    EventType.TIMER_FIRED: TimerFired,
    EventType.CHECKPOINT_CREATED: CheckpointCreated,
    EventType.CHECKPOINT_LOADED: CheckpointLoaded,
    EventType.LLM_REQUEST_STARTED: LLMRequestStarted,
    EventType.LLM_REQUEST_COMPLETED: LLMRequestCompleted,
    EventType.LLM_FALLBACK_TRIGGERED: LLMFallbackTriggered,
    EventType.RAG_QUERY_STARTED: RAGQueryStarted,
    EventType.RAG_DOCUMENTS_RETRIEVED: RAGDocumentsRetrieved,
}


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "EventType",
    # Base
    "BaseEvent",
    "WorkflowEvent",
    # Workflow events
    "WorkflowStarted",
    "WorkflowCompleted",
    "WorkflowFailed",
    "WorkflowCancelled",
    "WorkflowTimedOut",
    # Activity events
    "ActivityScheduled",
    "ActivityStarted",
    "ActivityCompleted",
    "ActivityFailed",
    "ActivityHeartbeat",
    # Signal events
    "SignalReceived",
    "SignalProcessed",
    # Timer events
    "TimerStarted",
    "TimerFired",
    # Checkpoint events
    "CheckpointCreated",
    "CheckpointLoaded",
    # LLM events
    "LLMRequestStarted",
    "LLMRequestCompleted",
    "LLMFallbackTriggered",
    # RAG events
    "RAGQueryStarted",
    "RAGDocumentsRetrieved",
    # Mapping
    "EVENT_TYPE_MAP",
]
