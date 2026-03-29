"""
Voice Event Streaming via Redpanda/Kafka.

Real-time voice events for the brain with safe, lazy Kafka integration.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Callable, Iterable, Optional, Sequence

try:  # Optional dependency: the rest of the voice stack must still work without it.
    from kafka import KafkaConsumer, KafkaProducer
except Exception:  # pragma: no cover - exercised when kafka-python is absent
    KafkaConsumer = None  # type: ignore[assignment]
    KafkaProducer = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Topics
VOICE_REQUEST = "brain.voice.request"
VOICE_STATUS = "brain.voice.status"
VOICE_INPUT = "brain.voice.input"
VOICE_CONTROL = "brain.voice.control"
LLM_STREAMING = "brain.llm.streaming"


def _normalize_bootstrap_servers(
    bootstrap_servers: str | Sequence[str] | None,
) -> list[str]:
    """Return bootstrap servers as a clean list."""

    if bootstrap_servers is None:
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    if isinstance(bootstrap_servers, str):
        return [
            server.strip() for server in bootstrap_servers.split(",") if server.strip()
        ]

    return [str(server).strip() for server in bootstrap_servers if str(server).strip()]


def _json_default(value: Any) -> Any:
    """JSON serializer for dataclasses and tuples."""

    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _serialize_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, default=_json_default).encode("utf-8")


def _deserialize_payload(payload: bytes | str | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return json.loads(payload)


@dataclass(slots=True)
class VoiceRequest:
    """Speech request published to the voice event bus."""

    text: str
    voice: str = "Karen"
    rate: int = 155
    priority: int = 50  # 0-100
    spatial_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    wait_for_voiceover: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("VoiceRequest.text must not be empty")
        if not 0 <= int(self.priority) <= 100:
            raise ValueError("VoiceRequest.priority must be between 0 and 100")
        if int(self.rate) <= 0:
            raise ValueError("VoiceRequest.rate must be greater than 0")
        if len(self.spatial_position) != 3:
            raise ValueError("VoiceRequest.spatial_position must contain x, y, z")

        self.priority = int(self.priority)
        self.rate = int(self.rate)
        self.spatial_position = tuple(float(v) for v in self.spatial_position)

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["spatial_position"] = list(self.spatial_position)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> VoiceRequest:
        return cls(
            text=payload["text"],
            voice=payload.get("voice", "Karen"),
            rate=int(payload.get("rate", 155)),
            priority=int(payload.get("priority", 50)),
            spatial_position=tuple(payload.get("spatial_position", (0.0, 0.0, 0.0))),
            request_id=payload.get("request_id", str(uuid.uuid4())),
            timestamp=float(payload.get("timestamp", time.time())),
            wait_for_voiceover=bool(payload.get("wait_for_voiceover", True)),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(slots=True)
class VoiceStatus:
    """Lifecycle update for a voice request."""

    event: str  # "started", "completed", "error"
    text: str
    voice: str
    queue_depth: int
    request_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event.strip():
            raise ValueError("VoiceStatus.event must not be empty")
        if int(self.queue_depth) < 0:
            raise ValueError("VoiceStatus.queue_depth must be zero or greater")
        self.queue_depth = int(self.queue_depth)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> VoiceStatus:
        return cls(
            event=payload["event"],
            text=payload.get("text", ""),
            voice=payload.get("voice", "Karen"),
            queue_depth=int(payload.get("queue_depth", 0)),
            request_id=payload.get("request_id"),
            error=payload.get("error"),
            timestamp=float(payload.get("timestamp", time.time())),
            metadata=dict(payload.get("metadata", {})),
        )


class VoiceEventProducer:
    """Kafka producer for voice and LLM streaming events.

    The underlying Kafka client is created lazily so importing this module does
    not block startup when Kafka/Redpanda is unavailable.
    """

    def __init__(
        self,
        bootstrap_servers: str | Sequence[str] | None = None,
        *,
        client_id: str = "agentic-brain-voice-events",
        producer: Any | None = None,
        producer_factory: Callable[..., Any] | None = None,
        enabled: bool = True,
        lazy: bool = True,
    ) -> None:
        self.bootstrap_servers = _normalize_bootstrap_servers(bootstrap_servers)
        self.client_id = client_id
        self._producer = producer
        self._producer_factory = producer_factory or KafkaProducer
        self._enabled = enabled
        self._lazy = lazy

        if self._producer is None and enabled and not lazy:
            self._ensure_producer()

    @property
    def enabled(self) -> bool:
        return bool(self._enabled and self._producer_factory is not None)

    def _ensure_producer(self) -> bool:
        if not self._enabled:
            return False
        if self._producer is not None:
            return True
        if self._producer_factory is None:
            logger.debug("Kafka producer unavailable - kafka-python not installed")
            return False

        try:
            self._producer = self._producer_factory(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                acks="all",
                retries=3,
                linger_ms=10,
                compression_type="gzip",
                value_serializer=_serialize_payload,
            )
            return True
        except Exception as exc:  # pragma: no cover - depends on broker availability
            logger.warning("VoiceEventProducer unavailable: %s", exc)
            self._producer = None
            return False

    def send(
        self,
        topic: str,
        payload: dict[str, Any],
        *,
        key: Optional[str] = None,
        headers: Optional[Iterable[tuple[str, bytes]]] = None,
    ) -> bool:
        """Send a JSON payload to Kafka."""

        if not self._ensure_producer():
            return False

        try:
            future = self._producer.send(  # type: ignore[union-attr]
                topic,
                value=payload,
                key=key.encode("utf-8") if key else None,
                headers=list(headers or []),
            )
            if hasattr(future, "get"):
                future.get(timeout=5)
            return True
        except Exception as exc:  # pragma: no cover - depends on broker availability
            logger.warning("Failed to publish voice event to %s: %s", topic, exc)
            return False

    def request_speech(self, request: VoiceRequest) -> bool:
        return self.send(VOICE_REQUEST, request.to_payload(), key=request.request_id)

    def publish_status(self, status: VoiceStatus) -> bool:
        return self.send(VOICE_STATUS, status.to_payload(), key=status.request_id)

    def publish_input(
        self,
        text: str,
        *,
        source: str = "user",
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        payload = {
            "text": text,
            "source": source,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        return self.send(VOICE_INPUT, payload)

    def publish_control(
        self,
        command: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        payload = {
            "command": command,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        return self.send(VOICE_CONTROL, payload)

    def publish_llm_stream(
        self,
        text: str,
        *,
        request_id: Optional[str] = None,
        voice: Optional[str] = None,
        done: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        payload = {
            "text": text,
            "request_id": request_id,
            "voice": voice,
            "done": done,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        return self.send(LLM_STREAMING, payload, key=request_id)

    def flush(self) -> None:
        if self._producer is not None and hasattr(self._producer, "flush"):
            self._producer.flush(timeout=5)

    def close(self) -> None:
        if self._producer is not None:
            try:
                if hasattr(self._producer, "flush"):
                    self._producer.flush(timeout=5)
                if hasattr(self._producer, "close"):
                    self._producer.close()
            except Exception:  # pragma: no cover - defensive
                logger.debug("VoiceEventProducer close failed", exc_info=True)
            finally:
                self._producer = None


class VoiceEventConsumer:
    """Kafka consumer for voice-related events."""

    def __init__(
        self,
        topics: Sequence[str],
        *,
        group_id: str = "voice-processor",
        bootstrap_servers: str | Sequence[str] | None = None,
        consumer: Any | None = None,
        consumer_factory: Callable[..., Any] | None = None,
        auto_offset_reset: str = "latest",
        enable_auto_commit: bool = True,
        consumer_timeout_ms: int = 1000,
    ) -> None:
        self.topics = list(topics)
        self.group_id = group_id
        self.bootstrap_servers = _normalize_bootstrap_servers(bootstrap_servers)
        self._consumer = consumer
        self._consumer_factory = consumer_factory or KafkaConsumer
        self._auto_offset_reset = auto_offset_reset
        self._enable_auto_commit = enable_auto_commit
        self._consumer_timeout_ms = consumer_timeout_ms

        if self._consumer is None and self._consumer_factory is not None:
            self._ensure_consumer()

    @property
    def enabled(self) -> bool:
        return self._consumer is not None

    def _ensure_consumer(self) -> bool:
        if self._consumer is not None:
            return True
        if self._consumer_factory is None:
            logger.debug("Kafka consumer unavailable - kafka-python not installed")
            return False

        try:
            self._consumer = self._consumer_factory(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self._auto_offset_reset,
                enable_auto_commit=self._enable_auto_commit,
                consumer_timeout_ms=self._consumer_timeout_ms,
                value_deserializer=_deserialize_payload,
            )
            return True
        except Exception as exc:  # pragma: no cover - depends on broker availability
            logger.warning("VoiceEventConsumer unavailable: %s", exc)
            self._consumer = None
            return False

    def process_requests(
        self,
        handler: Callable[[dict[str, Any]], Any],
        *,
        max_messages: Optional[int] = None,
    ) -> int:
        """Iterate through messages and pass each payload to ``handler``."""

        if not self._ensure_consumer():
            return 0

        processed = 0
        for message in self._consumer:  # type: ignore[union-attr]
            handler(message.value)
            processed += 1
            if max_messages is not None and processed >= max_messages:
                break

        return processed

    def poll(
        self, timeout_ms: int = 1000, max_records: int = 100
    ) -> list[dict[str, Any]]:
        """Poll a batch of messages from Kafka."""

        if not self._ensure_consumer():
            return []

        records = self._consumer.poll(  # type: ignore[union-attr]
            timeout_ms=timeout_ms,
            max_records=max_records,
        )
        payloads: list[dict[str, Any]] = []
        for batch in records.values():
            for message in batch:
                payloads.append(message.value)
        return payloads

    def close(self) -> None:
        if self._consumer is not None and hasattr(self._consumer, "close"):
            self._consumer.close()
            self._consumer = None


_voice_event_producer: Optional[VoiceEventProducer] = None


def _voice_events_enabled() -> bool:
    raw = os.getenv("AGENTIC_BRAIN_ENABLE_VOICE_EVENTS", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def get_voice_event_producer(
    bootstrap_servers: str | Sequence[str] | None = None,
) -> VoiceEventProducer:
    """Return a shared lazy producer for voice event publishing."""

    global _voice_event_producer
    normalized = _normalize_bootstrap_servers(bootstrap_servers)
    if (
        _voice_event_producer is None
        or _voice_event_producer.bootstrap_servers != normalized
    ):
        _voice_event_producer = VoiceEventProducer(
            bootstrap_servers=normalized,
            enabled=_voice_events_enabled(),
            lazy=True,
        )
    return _voice_event_producer
