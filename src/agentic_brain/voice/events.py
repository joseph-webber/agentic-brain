"""Voice event models for Redpanda-backed speech streaming."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, ClassVar


class VoicePriorityLane(IntEnum):
    """Priority lanes consumed in ascending order."""

    URGENT = 0
    NORMAL = 1
    BACKGROUND = 2

    @classmethod
    def coerce(cls, value: int | VoicePriorityLane | None) -> VoicePriorityLane:
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.NORMAL
        return cls(int(value))


@dataclass(slots=True)
class VoiceEvent:
    """Base voice event shared by request and lifecycle updates."""

    text: str
    lady: str = "Karen"
    priority: VoicePriorityLane = VoicePriorityLane.NORMAL
    timestamp: float = field(default_factory=time.time)
    source: str = "agentic_brain.voice"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    event_type: ClassVar[str] = "voice.base"

    def __post_init__(self) -> None:
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("Voice event text must not be empty")
        self.priority = VoicePriorityLane.coerce(self.priority)
        self.timestamp = float(self.timestamp)
        self.source = self.source.strip() or "agentic_brain.voice"
        self.lady = self.lady.strip() or "Karen"
        self.request_id = self.request_id.strip() or str(uuid.uuid4())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["priority"] = int(self.priority)
        payload["event_type"] = self.event_type
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclass(slots=True)
class VoiceSpeechRequested(VoiceEvent):
    event_type: ClassVar[str] = "voice.speech.requested"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VoiceSpeechRequested:
        return cls(
            text=payload["text"],
            lady=payload.get("lady", "Karen"),
            priority=payload.get("priority", VoicePriorityLane.NORMAL),
            timestamp=payload.get("timestamp", time.time()),
            source=payload.get("source", "agentic_brain.voice"),
            request_id=payload.get("request_id", str(uuid.uuid4())),
        )


@dataclass(slots=True)
class VoiceSpeechStarted(VoiceEvent):
    event_type: ClassVar[str] = "voice.speech.started"

    @classmethod
    def from_request(cls, request: VoiceSpeechRequested) -> VoiceSpeechStarted:
        return cls(
            text=request.text,
            lady=request.lady,
            priority=request.priority,
            timestamp=time.time(),
            source=request.source,
            request_id=request.request_id,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VoiceSpeechStarted:
        return cls(
            text=payload["text"],
            lady=payload.get("lady", "Karen"),
            priority=payload.get("priority", VoicePriorityLane.NORMAL),
            timestamp=payload.get("timestamp", time.time()),
            source=payload.get("source", "agentic_brain.voice"),
            request_id=payload.get("request_id", str(uuid.uuid4())),
        )


@dataclass(slots=True)
class VoiceSpeechCompleted(VoiceEvent):
    event_type: ClassVar[str] = "voice.speech.completed"

    @classmethod
    def from_request(cls, request: VoiceSpeechRequested) -> VoiceSpeechCompleted:
        return cls(
            text=request.text,
            lady=request.lady,
            priority=request.priority,
            timestamp=time.time(),
            source=request.source,
            request_id=request.request_id,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VoiceSpeechCompleted:
        return cls(
            text=payload["text"],
            lady=payload.get("lady", "Karen"),
            priority=payload.get("priority", VoicePriorityLane.NORMAL),
            timestamp=payload.get("timestamp", time.time()),
            source=payload.get("source", "agentic_brain.voice"),
            request_id=payload.get("request_id", str(uuid.uuid4())),
        )


@dataclass(slots=True)
class VoiceSpeechFailed(VoiceEvent):
    error: str = "speech failed"

    event_type: ClassVar[str] = "voice.speech.failed"

    def __post_init__(self) -> None:
        super().__post_init__()
        self.error = self.error.strip() or "speech failed"

    @classmethod
    def from_request(
        cls, request: VoiceSpeechRequested, *, error: str
    ) -> VoiceSpeechFailed:
        return cls(
            text=request.text,
            lady=request.lady,
            priority=request.priority,
            timestamp=time.time(),
            source=request.source,
            request_id=request.request_id,
            error=error,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VoiceSpeechFailed:
        return cls(
            text=payload["text"],
            lady=payload.get("lady", "Karen"),
            priority=payload.get("priority", VoicePriorityLane.NORMAL),
            timestamp=payload.get("timestamp", time.time()),
            source=payload.get("source", "agentic_brain.voice"),
            request_id=payload.get("request_id", str(uuid.uuid4())),
            error=payload.get("error", "speech failed"),
        )


_EVENT_TYPES = {
    VoiceSpeechRequested.event_type: VoiceSpeechRequested,
    VoiceSpeechStarted.event_type: VoiceSpeechStarted,
    VoiceSpeechCompleted.event_type: VoiceSpeechCompleted,
    VoiceSpeechFailed.event_type: VoiceSpeechFailed,
}


def serialize_event(event: VoiceEvent) -> str:
    """Serialize a voice event to JSON."""

    return event.to_json()


def deserialize_event(payload: str | bytes | dict[str, Any]) -> VoiceEvent:
    """Deserialize JSON or a dict into the correct voice event type."""

    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        payload = json.loads(payload)

    event_type = payload.get("event_type", VoiceSpeechRequested.event_type)
    event_cls = _EVENT_TYPES.get(event_type)
    if event_cls is None:
        raise ValueError(f"Unknown voice event type: {event_type}")
    return event_cls.from_dict(payload)


__all__ = [
    "VoicePriorityLane",
    "VoiceEvent",
    "VoiceSpeechRequested",
    "VoiceSpeechStarted",
    "VoiceSpeechCompleted",
    "VoiceSpeechFailed",
    "serialize_event",
    "deserialize_event",
]
