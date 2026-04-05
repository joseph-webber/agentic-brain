#!/usr/bin/env python3
"""Redpanda topic setup and event helpers for Brain Chat voice integrations."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any, Callable

try:  # Lazy-safe optional import for environments without kafka-python.
    from kafka import KafkaConsumer, KafkaProducer
    from kafka.admin import KafkaAdminClient, NewTopic
except Exception:  # pragma: no cover - depends on optional dependency
    KafkaConsumer = None  # type: ignore[assignment]
    KafkaProducer = None  # type: ignore[assignment]
    KafkaAdminClient = None  # type: ignore[assignment]
    NewTopic = None  # type: ignore[assignment]

REDPANDA_BOOTSTRAP_SERVERS = os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "localhost:9092")

VOICE_INPUT_TOPIC = "brain.voice.input"
VOICE_RESPONSE_TOPIC = "brain.voice.response"
VOICE_STATUS_TOPIC = "brain.voice.status"
VOICE_TOPICS = (
    VOICE_INPUT_TOPIC,
    VOICE_RESPONSE_TOPIC,
    VOICE_STATUS_TOPIC,
)

VALID_PRIORITIES = {"low", "normal", "high", "critical"}
DEFAULT_VOICE = "Karen"
DEFAULT_SOURCE = "brainchat"

VoiceInputEvent: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "VoiceInputEvent",
    "type": "object",
    "required": ["timestamp", "session_id", "text", "confidence", "source"],
    "properties": {
        "timestamp": {"type": "string", "format": "date-time"},
        "session_id": {"type": "string", "minLength": 1},
        "text": {"type": "string", "minLength": 1},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "source": {"type": "string", "minLength": 1},
        "request_id": {"type": "string"},
    },
    "additionalProperties": True,
}

VoiceResponseEvent: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "VoiceResponseEvent",
    "type": "object",
    "required": ["timestamp", "session_id", "text", "voice", "priority"],
    "properties": {
        "timestamp": {"type": "string", "format": "date-time"},
        "session_id": {"type": "string", "minLength": 1},
        "text": {"type": "string", "minLength": 1},
        "voice": {"type": "string", "minLength": 1},
        "priority": {"type": "string", "enum": sorted(VALID_PRIORITIES)},
        "request_id": {"type": "string"},
        "source": {"type": "string"},
        "provider": {"type": "string"},
        "complexity": {"type": "string"},
        "latency_ms": {"type": "number"},
    },
    "additionalProperties": True,
}

VoiceStatusEvent: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "VoiceStatusEvent",
    "type": "object",
    "required": ["timestamp", "source", "status"],
    "properties": {
        "timestamp": {"type": "string", "format": "date-time"},
        "source": {"type": "string", "minLength": 1},
        "status": {"type": "string", "minLength": 1},
        "session_id": {"type": "string"},
        "error": {"type": "string"},
        "details": {"type": "object"},
        "topics": {"type": "array", "items": {"type": "string"}},
        "missing_topics": {"type": "array", "items": {"type": "string"}},
        "bootstrap_servers": {"type": "string"},
    },
    "additionalProperties": True,
}

_producer: Any | None = None
_topics_ensured = False


def _iso8601(value: Any | None = None) -> str:
    if value is None:
        dt = datetime.now(UTC)
    elif isinstance(value, datetime):
        dt = value.astimezone(UTC)
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=UTC)
    elif isinstance(value, str):
        return value
    else:
        raise TypeError(f"Unsupported timestamp value: {type(value).__name__}")

    return dt.isoformat().replace("+00:00", "Z")


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 1.0
    return max(0.0, min(1.0, confidence))


def _normalize_priority(value: Any) -> str:
    if isinstance(value, (int, float)):
        if value >= 90:
            return "critical"
        if value >= 70:
            return "high"
        if value <= 20:
            return "low"
        return "normal"

    text = str(value or "normal").strip().lower()
    return text if text in VALID_PRIORITIES else "normal"


def _require_text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    return text


def _producer_factory() -> Any:
    if KafkaProducer is None:
        raise RuntimeError("kafka-python is not installed")
    return KafkaProducer(
        bootstrap_servers=REDPANDA_BOOTSTRAP_SERVERS,
        acks="all",
        value_serializer=lambda payload: json.dumps(payload).encode("utf-8"),
    )


def _get_producer() -> Any:
    global _producer
    if _producer is None:
        _producer = _producer_factory()
    return _producer


def _get_admin_client() -> Any:
    if KafkaAdminClient is None:
        raise RuntimeError("kafka-python is not installed")
    return KafkaAdminClient(bootstrap_servers=REDPANDA_BOOTSTRAP_SERVERS)


def _create_consumer(
    topic: str,
    *,
    group_id: str | None = None,
    auto_offset_reset: str = "latest",
    consumer_timeout_ms: int = 1000,
) -> Any:
    if KafkaConsumer is None:
        raise RuntimeError("kafka-python is not installed")
    return KafkaConsumer(
        topic,
        bootstrap_servers=REDPANDA_BOOTSTRAP_SERVERS,
        group_id=group_id or f"brain-chat-{uuid.uuid4().hex}",
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
        consumer_timeout_ms=consumer_timeout_ms,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )


def ensure_voice_topics() -> tuple[str, ...]:
    """Create Brain Chat voice topics when they do not already exist."""

    global _topics_ensured
    if _topics_ensured:
        return VOICE_TOPICS

    admin = _get_admin_client()
    try:
        topics = [
            NewTopic(name=topic, num_partitions=1, replication_factor=1)
            for topic in VOICE_TOPICS
        ]
        try:
            admin.create_topics(new_topics=topics, validate_only=False)
        except Exception as exc:  # pragma: no cover - broker state dependent
            message = f"{type(exc).__name__}: {exc}".lower()
            if (
                "already exists" not in message
                and "already been created" not in message
            ):
                raise
        _topics_ensured = True
        return VOICE_TOPICS
    finally:
        admin.close()


def _publish(
    topic: str, payload: dict[str, Any], *, key: str | None = None
) -> dict[str, Any]:
    ensure_voice_topics()
    producer = _get_producer()
    producer.send(topic, value=payload, key=key.encode("utf-8") if key else None)
    producer.flush()
    return payload


def build_voice_input_event(
    text: str,
    session_id: str,
    *,
    confidence: float = 1.0,
    source: str = DEFAULT_SOURCE,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a normalized brain.voice.input payload."""

    return {
        "timestamp": _iso8601(),
        "session_id": _require_text("session_id", session_id),
        "text": _require_text("text", text),
        "confidence": _clamp_confidence(confidence),
        "source": _require_text("source", source),
        "request_id": request_id or str(uuid.uuid4()),
    }


def normalize_voice_response_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize response payloads from orchestrators into Brain Chat schema."""

    normalized = dict(payload)
    normalized["timestamp"] = _iso8601(
        normalized.get("timestamp", normalized.get("ts"))
    )
    normalized["session_id"] = _require_text(
        "session_id", normalized.get("session_id", "default")
    )
    normalized["text"] = _require_text("text", normalized.get("text"))
    normalized["voice"] = _require_text(
        "voice",
        normalized.get("voice") or normalized.get("voice_persona") or DEFAULT_VOICE,
    )
    normalized["priority"] = _normalize_priority(normalized.get("priority"))
    normalized.setdefault("source", normalized.get("provider") or DEFAULT_SOURCE)
    return normalized


def publish_voice_input(text: str, session_id: str) -> dict[str, Any]:
    """Publish a Brain Chat transcription event to brain.voice.input."""

    event = build_voice_input_event(text=text, session_id=session_id)
    return _publish(VOICE_INPUT_TOPIC, event, key=event["session_id"])


def publish_voice_status(
    status: str,
    *,
    session_id: str | None = None,
    error: str | None = None,
    details: dict[str, Any] | None = None,
    source: str = DEFAULT_SOURCE,
) -> dict[str, Any]:
    """Publish a connection or lifecycle update to brain.voice.status."""

    payload: dict[str, Any] = {
        "timestamp": _iso8601(),
        "status": _require_text("status", status),
        "source": _require_text("source", source),
    }
    if session_id:
        payload["session_id"] = session_id
    if error:
        payload["error"] = str(error)
    if details:
        payload["details"] = details
    return _publish(VOICE_STATUS_TOPIC, payload, key=session_id)


def subscribe_voice_responses(
    callback: Callable[[dict[str, Any]], Any],
    *,
    group_id: str | None = None,
    auto_offset_reset: str = "latest",
    consumer_timeout_ms: int = 1000,
) -> int:
    """Consume normalized brain.voice.response events and pass them to a callback."""

    ensure_voice_topics()
    consumer = _create_consumer(
        VOICE_RESPONSE_TOPIC,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        consumer_timeout_ms=consumer_timeout_ms,
    )
    processed = 0
    try:
        for message in consumer:
            callback(normalize_voice_response_event(message.value))
            processed += 1
    finally:
        consumer.close()
    return processed


def get_voice_status() -> dict[str, Any]:
    """Return broker/topic status and publish a matching brain.voice.status event."""

    try:
        ensure_voice_topics()
        admin = _get_admin_client()
        try:
            available_topics = sorted(admin.list_topics())
        finally:
            admin.close()

        missing_topics = [
            topic for topic in VOICE_TOPICS if topic not in available_topics
        ]
        status = "healthy" if not missing_topics else "degraded"
        details = {
            "bootstrap_servers": REDPANDA_BOOTSTRAP_SERVERS,
            "topics": list(VOICE_TOPICS),
            "available_topics": available_topics,
            "missing_topics": missing_topics,
        }
        return publish_voice_status(status, details=details)
    except Exception as exc:
        return {
            "timestamp": _iso8601(),
            "source": DEFAULT_SOURCE,
            "status": "error",
            "error": str(exc),
            "bootstrap_servers": REDPANDA_BOOTSTRAP_SERVERS,
            "topics": list(VOICE_TOPICS),
        }


__all__ = [
    "DEFAULT_SOURCE",
    "DEFAULT_VOICE",
    "REDPANDA_BOOTSTRAP_SERVERS",
    "VOICE_INPUT_TOPIC",
    "VOICE_RESPONSE_TOPIC",
    "VOICE_STATUS_TOPIC",
    "VOICE_TOPICS",
    "VoiceInputEvent",
    "VoiceResponseEvent",
    "VoiceStatusEvent",
    "build_voice_input_event",
    "ensure_voice_topics",
    "get_voice_status",
    "normalize_voice_response_event",
    "publish_voice_input",
    "publish_voice_status",
    "subscribe_voice_responses",
]
