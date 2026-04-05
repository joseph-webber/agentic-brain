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

"""Redpanda-backed voice event streaming."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Optional

from agentic_brain.voice.events import (
    VoiceEvent,
    VoicePriorityLane,
    VoiceSpeechCompleted,
    VoiceSpeechFailed,
    VoiceSpeechRequested,
    VoiceSpeechStarted,
    deserialize_event,
    serialize_event,
)

try:  # Optional dependency - graceful fallback when kafka-python is absent
    from kafka import KafkaConsumer, KafkaProducer
    from kafka.admin import KafkaAdminClient, NewTopic
except Exception:  # pragma: no cover - exercised when kafka-python missing
    KafkaConsumer = None  # type: ignore[assignment]
    KafkaProducer = None  # type: ignore[assignment]
    KafkaAdminClient = None  # type: ignore[assignment]
    NewTopic = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

BRAIN_VOICE_REQUESTS = "brain.voice.requests"
BRAIN_VOICE_STATUS = "brain.voice.status"
BRAIN_VOICE_ERRORS = "brain.voice.errors"
VOICE_TOPICS = (
    BRAIN_VOICE_REQUESTS,
    BRAIN_VOICE_STATUS,
    BRAIN_VOICE_ERRORS,
)


def _normalize_bootstrap_servers(
    bootstrap_servers: str | Sequence[str] | None,
) -> list[str]:
    """Normalize Kafka bootstrap servers to a list of strings.
    
    Args:
        bootstrap_servers: Comma-separated string, sequence, or None.
        
    Returns:
        List of server addresses. Defaults to localhost:9092 if None.
    """
    if bootstrap_servers is None:
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    if isinstance(bootstrap_servers, str):
        return [
            server.strip() for server in bootstrap_servers.split(",") if server.strip()
        ]
    return [str(server).strip() for server in bootstrap_servers if str(server).strip()]


def _default_speaker(text: str, lady: str) -> bool:
    """Default speaker implementation using voice serializer.
    
    Args:
        text: Text to speak.
        lady: Voice/lady identifier.
        
    Returns:
        True if speech succeeded.
    """
    from agentic_brain.voice.serializer import speak_serialized

    return speak_serialized(text, voice=lady)


async def _resolve_result(result: Any) -> Any:
    """Resolve potentially awaitable result.
    
    Args:
        result: Value that may or may not be awaitable.
        
    Returns:
        Awaited result if awaitable, otherwise the value itself.
    """
    if inspect.isawaitable(result):
        return await result
    return result


class VoiceEventProducer:
    """Publish voice requests and lifecycle updates to Redpanda/Kafka."""

    def __init__(
        self,
        bootstrap_servers: str | Sequence[str] | None = None,
        *,
        producer: Any | None = None,
        producer_factory: Callable[..., Any] | None = None,
        admin_client: Any | None = None,
        admin_factory: Callable[..., Any] | None = None,
        enabled: bool = True,
        create_topics: bool = True,
    ) -> None:
        self.bootstrap_servers = _normalize_bootstrap_servers(bootstrap_servers)
        self._producer = producer
        self._producer_factory = producer_factory or KafkaProducer
        self._admin_client = admin_client
        self._admin_factory = admin_factory or KafkaAdminClient
        self._enabled = enabled
        self._create_topics = create_topics
        self._topics_ready = False

    @property
    def enabled(self) -> bool:
        """Check if producer is enabled and available.
        
        Returns:
            True if producer can be used.
        """
        return bool(self._enabled and self._producer_factory is not None)

    def _ensure_producer(self) -> bool:
        """Ensure Kafka producer is initialized.
        
        Returns:
            True if producer is ready, False otherwise.
        """
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
                acks="all",
                retries=3,
                value_serializer=lambda payload: serialize_event(payload).encode(
                    "utf-8"
                ),
            )
            return True
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Voice event producer unavailable: %s", exc)
            self._producer = None
            return False

    def ensure_topics(self) -> bool:
        """Ensure voice topics exist in Kafka.
        
        Creates topics if they don't exist. Gracefully handles
        already-exists errors.
        
        Returns:
            True if topics are ready.
        """
        if self._topics_ready or not self._create_topics:
            return True
        if self._admin_client is None and self._admin_factory is None:
            return False
        if self._admin_client is None:
            try:
                self._admin_client = self._admin_factory(
                    bootstrap_servers=self.bootstrap_servers
                )
            except Exception as exc:  # pragma: no cover - network dependent
                logger.debug("Voice topic admin unavailable: %s", exc)
                return False

        if NewTopic is None and not hasattr(self._admin_client, "create_topics"):
            return False

        topics: list[Any] = []
        if NewTopic is not None:
            topics = [
                NewTopic(name=topic, num_partitions=1, replication_factor=1)
                for topic in VOICE_TOPICS
            ]

        try:
            create_topics = self._admin_client.create_topics
            if topics:
                create_topics(new_topics=topics, validate_only=False)
            else:
                create_topics(list(VOICE_TOPICS))
            self._topics_ready = True
            return True
        except Exception as exc:  # pragma: no cover - broker dependent
            if "already exists" not in str(exc).lower():
                logger.debug("Voice topic creation skipped: %s", exc)
            self._topics_ready = True
            return True

    def send(self, topic: str, event: VoiceEvent) -> bool:
        """Send event to a specific Kafka topic.
        
        Args:
            topic: Kafka topic name.
            event: Voice event to send.
            
        Returns:
            True if send succeeded.
        """
        if not self._ensure_producer():
            return False

        self.ensure_topics()

        try:
            future = self._producer.send(topic, value=event)  # type: ignore[union-attr]
            if hasattr(future, "get"):
                future.get(timeout=5)
            return True
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Failed to publish voice event to %s: %s", topic, exc)
            return False

    def publish(self, event: VoiceEvent) -> bool:
        """Publish event to appropriate topic based on type.
        
        Routes events to correct topics:
        - Requests → brain.voice.requests
        - Status updates → brain.voice.status
        - Failures → brain.voice.errors (and status)
        
        Args:
            event: Voice event to publish.
            
        Returns:
            True if publish succeeded.
        """
        if isinstance(event, VoiceSpeechRequested):
            return self.send(BRAIN_VOICE_REQUESTS, event)
        if isinstance(event, (VoiceSpeechStarted, VoiceSpeechCompleted)):
            return self.send(BRAIN_VOICE_STATUS, event)
        if isinstance(event, VoiceSpeechFailed):
            status_ok = self.send(BRAIN_VOICE_STATUS, event)
            error_ok = self.send(BRAIN_VOICE_ERRORS, event)
            return status_ok or error_ok
        return False

    def publish_speech_request(
        self,
        text: str,
        lady: str = "Karen",
        *,
        priority: int | VoicePriorityLane = VoicePriorityLane.NORMAL,
        source: str = "agentic_brain.voice.stream",
    ) -> bool:
        """Publish a speech request event.
        
        Convenience method for publishing speech requests.
        
        Args:
            text: Text to speak.
            lady: Voice/lady identifier.
            priority: Priority lane for this request.
            source: Source identifier.
            
        Returns:
            True if publish succeeded.
        """
        return self.publish(
            VoiceSpeechRequested(
                text=text,
                lady=lady,
                priority=priority,
                source=source,
            )
        )

    def close(self) -> None:
        """Close the Kafka producer and release resources."""
        if self._producer is not None and hasattr(self._producer, "close"):
            try:
                self._producer.close()
            except Exception:  # pragma: no cover - defensive
                logger.debug("Failed to close voice event producer", exc_info=True)
        self._producer = None


class VoiceEventConsumer:
    """Consume speech requests, route them through the serializer, and publish status."""

    def __init__(
        self,
        bootstrap_servers: str | Sequence[str] | None = None,
        *,
        consumer: Any | None = None,
        consumer_factory: Callable[..., Any] | None = None,
        event_producer: VoiceEventProducer | None = None,
        speaker: Callable[[str, str], bool | Awaitable[bool]] | None = None,
        group_id: str = "agentic-brain-voice-stream",
        enabled: bool = True,
    ) -> None:
        self.bootstrap_servers = _normalize_bootstrap_servers(bootstrap_servers)
        self._consumer = consumer
        self._consumer_factory = consumer_factory or KafkaConsumer
        self._event_producer = event_producer or VoiceEventProducer(
            self.bootstrap_servers,
            enabled=enabled,
        )
        self._speaker = speaker or _default_speaker
        self._group_id = group_id
        self._enabled = enabled

    def _ensure_consumer(self) -> bool:
        """Ensure Kafka consumer is initialized.
        
        Returns:
            True if consumer is ready, False otherwise.
        """
        if not self._enabled:
            return False
        if self._consumer is not None:
            return True
        if self._consumer_factory is None:
            logger.debug("Kafka consumer unavailable - kafka-python not installed")
            return False

        try:
            self._consumer = self._consumer_factory(
                BRAIN_VOICE_REQUESTS,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self._group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                consumer_timeout_ms=1000,
                value_deserializer=lambda payload: json.loads(payload.decode("utf-8")),
            )
            return True
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Voice event consumer unavailable: %s", exc)
            self._consumer = None
            return False

    def poll(
        self, max_records: int = 100, timeout_ms: int = 1000
    ) -> list[VoiceSpeechRequested]:
        """Poll for speech request events from Kafka.
        
        Args:
            max_records: Maximum events to fetch.
            timeout_ms: Poll timeout in milliseconds.
            
        Returns:
            List of speech requests sorted by priority and timestamp.
        """
        if not self._ensure_consumer():
            return []

        payloads: list[dict[str, Any]] = []
        records = self._consumer.poll(  # type: ignore[union-attr]
            timeout_ms=timeout_ms,
            max_records=max_records,
        )

        for batch in records.values():
            for message in batch:
                value = getattr(message, "value", message)
                event = deserialize_event(value)
                if isinstance(event, VoiceSpeechRequested):
                    payloads.append(event)

        return self._sort_events(payloads)

    @staticmethod
    def _sort_events(
        events: list[VoiceSpeechRequested],
    ) -> list[VoiceSpeechRequested]:
        """Sort events by priority and timestamp.
        
        Args:
            events: List of speech request events.
            
        Returns:
            Sorted list with highest priority first.
        """
        return sorted(events, key=lambda event: (int(event.priority), event.timestamp))

    async def process_batch(
        self,
        *,
        max_records: int = 100,
        timeout_ms: int = 1000,
    ) -> list[VoiceSpeechRequested]:
        """Poll and process a batch of speech requests.
        
        Polls for events, executes them via the speaker,
        and publishes status updates.
        
        Args:
            max_records: Maximum events to process.
            timeout_ms: Poll timeout in milliseconds.
            
        Returns:
            List of processed speech requests.
        """
        events = self.poll(max_records=max_records, timeout_ms=timeout_ms)
        processed: list[VoiceSpeechRequested] = []

        for event in events:
            processed.append(event)
            self._event_producer.publish(VoiceSpeechStarted.from_request(event))
            try:
                result = await _resolve_result(self._speaker(event.text, event.lady))
                if not result:
                    raise RuntimeError("speech serializer returned False")
                self._event_producer.publish(VoiceSpeechCompleted.from_request(event))
            except Exception as exc:
                self._event_producer.publish(
                    VoiceSpeechFailed.from_request(event, error=str(exc))
                )

        return processed

    async def consume_forever(
        self,
        *,
        stop_event: asyncio.Event | None = None,
        poll_interval: float = 0.1,
        max_batches: int | None = None,
    ) -> int:
        """Continuously consume and process speech requests.
        
        Runs until stopped or max_batches is reached.
        
        Args:
            stop_event: Optional event to signal stop.
            poll_interval: Sleep duration when no events available.
            max_batches: Optional limit on batches to process.
            
        Returns:
            Number of batches processed.
        """
        batches = 0
        while stop_event is None or not stop_event.is_set():
            events = await self.process_batch()
            if events:
                batches += 1
            else:
                await asyncio.sleep(poll_interval)
            if max_batches is not None and batches >= max_batches:
                break
        return batches

    def close(self) -> None:
        """Close the Kafka consumer and release resources."""
        if self._consumer is not None and hasattr(self._consumer, "close"):
            try:
                self._consumer.close()
            except Exception:  # pragma: no cover - defensive
                logger.debug("Failed to close voice event consumer", exc_info=True)
        self._consumer = None


_shared_voice_event_producer: Optional[VoiceEventProducer] = None


def get_voice_event_producer(
    bootstrap_servers: str | Sequence[str] | None = None,
    *,
    enabled: bool | None = None,
) -> VoiceEventProducer:
    """Get or create shared voice event producer.
    
    Returns a singleton producer instance, creating it if necessary.
    
    Args:
        bootstrap_servers: Kafka bootstrap servers.
        enabled: Whether to enable the producer.
        
    Returns:
        Shared VoiceEventProducer instance.
    """
    global _shared_voice_event_producer
    normalized = _normalize_bootstrap_servers(bootstrap_servers)
    should_enable = (
        enabled
        if enabled is not None
        else os.getenv("AGENTIC_BRAIN_VOICE_USE_REDPANDA", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    if (
        _shared_voice_event_producer is None
        or _shared_voice_event_producer.bootstrap_servers != normalized
        or _shared_voice_event_producer.enabled != should_enable
    ):
        _shared_voice_event_producer = VoiceEventProducer(
            bootstrap_servers=normalized,
            enabled=should_enable,
        )
    return _shared_voice_event_producer


async def speak_async(
    text: str,
    lady: str = "Karen",
    *,
    priority: int | VoicePriorityLane = VoicePriorityLane.NORMAL,
    source: str = "agentic_brain.voice.stream",
    producer: VoiceEventProducer | None = None,
    fallback: Callable[[], bool | Awaitable[bool]] | None = None,
) -> bool:
    """Publish speech to Redpanda, or degrade to direct speech when unavailable.
    
    Attempts to publish to event stream first, falls back to
    direct speech if stream is unavailable.
    
    Args:
        text: Text to speak.
        lady: Voice/lady identifier.
        priority: Priority lane.
        source: Source identifier.
        producer: Optional producer instance.
        fallback: Optional fallback speech function.
        
    Returns:
        True if speech was published or executed.
    """
    event_producer = producer or get_voice_event_producer()
    published = event_producer.publish_speech_request(
        text,
        lady=lady,
        priority=priority,
        source=source,
    )
    if published:
        return True

    fallback = fallback or (lambda: _default_speaker(text, lady))
    return bool(await _resolve_result(fallback()))


__all__ = [
    "BRAIN_VOICE_REQUESTS",
    "BRAIN_VOICE_STATUS",
    "BRAIN_VOICE_ERRORS",
    "VOICE_TOPICS",
    "VoiceEventProducer",
    "VoiceEventConsumer",
    "get_voice_event_producer",
    "speak_async",
]
