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
Event Store for durable workflow execution.

This module provides event storage and retrieval using Redpanda (Kafka-compatible).
Every workflow state change is recorded as an immutable event, enabling:
- Full replay on crash recovery
- Audit trail of all actions
- Time-travel debugging

Architecture:
- Each workflow gets a dedicated topic: workflow.{workflow_id}
- Events are JSON-serialized with optional compression
- Consumer groups enable multi-worker processing

Kafka client stack: ``aiokafka`` (lazy import)
----------------------------------------------
Imported inside methods so the module is usable without ``aiokafka`` installed
(falls back to an in-memory store). ``aiokafka`` is chosen here because event
sourcing requires coroutine-based producers/consumers that integrate naturally
with asyncio — blocking calls would stall the event loop.

See: docs/KAFKA_CLIENTS.md for the full client comparison.

Usage:
    from agentic_brain.durability.event_store import EventStore

    store = EventStore()
    await store.connect()

    # Publish event
    await store.publish(WorkflowStarted(
        workflow_id="wf-123",
        workflow_type="ai-analysis"
    ))

    # Load all events for a workflow
    events = await store.load_events("wf-123")
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator

from .events import EVENT_TYPE_MAP, BaseEvent, EventType

logger = logging.getLogger(__name__)


@dataclass
class EventStoreConfig:
    """Configuration for event store"""

    # Redpanda/Kafka connection
    bootstrap_servers: str = "localhost:9092"

    # Topic settings
    topic_prefix: str = "workflow"
    num_partitions: int = 3
    replication_factor: int = 1

    # Retention
    retention_ms: int = 7 * 24 * 60 * 60 * 1000  # 7 days
    retention_bytes: int = -1  # Unlimited

    # Compression
    compression: bool = True
    compression_type: str = "gzip"

    # Consumer settings
    consumer_group: str = "agentic-brain-workers"
    auto_offset_reset: str = "earliest"

    # Timeouts
    request_timeout_ms: int = 30000
    session_timeout_ms: int = 10000

    @classmethod
    def from_env(cls) -> EventStoreConfig:
        """Create config from environment variables"""
        return cls(
            bootstrap_servers=os.getenv("REDPANDA_SERVERS", "localhost:9092"),
            topic_prefix=os.getenv("EVENT_TOPIC_PREFIX", "workflow"),
            consumer_group=os.getenv("EVENT_CONSUMER_GROUP", "agentic-brain-workers"),
            compression=os.getenv("EVENT_COMPRESSION", "true").lower() == "true",
        )


@dataclass
class EventMetadata:
    """Metadata about stored events"""

    workflow_id: str
    topic: str
    event_count: int
    first_event_time: datetime | None
    last_event_time: datetime | None
    size_bytes: int


class EventStore:
    """
    Event store using Redpanda for durable event sourcing.

    Provides:
    - Event publishing to workflow-specific topics
    - Event loading with ordering guarantees
    - Event streaming for real-time processing
    - Checkpoint support for faster recovery
    """

    def __init__(self, config: EventStoreConfig | None = None):
        """
        Initialize event store.

        Args:
            config: Configuration options. Uses env vars if not provided.
        """
        self.config = config or EventStoreConfig.from_env()
        self._producer = None
        self._consumer = None
        self._admin = None
        self._connected = False
        self._sequence_numbers: dict[str, int] = {}

    @property
    def is_connected(self) -> bool:
        """Check if connected to Redpanda"""
        return self._connected

    def _topic_name(self, workflow_id: str) -> str:
        """Get topic name for a workflow"""
        return f"{self.config.topic_prefix}.{workflow_id}"

    async def connect(self) -> bool:
        """
        Connect to Redpanda/Kafka cluster.

        Returns:
            True if connection successful
        """
        try:
            # Try to import aiokafka
            try:
                from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
                from aiokafka.admin import AIOKafkaAdminClient
            except ImportError:
                logger.warning(
                    "aiokafka not installed. Using in-memory event store. "
                    "Install with: pip install aiokafka"
                )
                self._connected = False
                return False

            # Create producer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                request_timeout_ms=self.config.request_timeout_ms,
                compression_type=(
                    self.config.compression_type if self.config.compression else None
                ),
            )
            await self._producer.start()

            # Create admin client for topic management
            self._admin = AIOKafkaAdminClient(
                bootstrap_servers=self.config.bootstrap_servers,
            )
            await self._admin.start()

            self._connected = True
            logger.info(f"Connected to Redpanda at {self.config.bootstrap_servers}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Redpanda: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redpanda"""
        if self._producer:
            await self._producer.stop()
            self._producer = None

        if self._consumer:
            await self._consumer.stop()
            self._consumer = None

        if self._admin:
            await self._admin.close()
            self._admin = None

        self._connected = False
        logger.info("Disconnected from Redpanda")

    async def _ensure_topic(self, topic: str) -> None:
        """Ensure topic exists, create if not"""
        if not self._admin:
            return

        try:
            from aiokafka.admin import NewTopic

            new_topic = NewTopic(
                name=topic,
                num_partitions=self.config.num_partitions,
                replication_factor=self.config.replication_factor,
                topic_configs={
                    "retention.ms": str(self.config.retention_ms),
                },
            )
            await self._admin.create_topics([new_topic])
            logger.debug(f"Created topic: {topic}")
        except Exception as e:
            # Topic might already exist
            if (
                "TopicExistsException" not in str(e)
                and "already exists" not in str(e).lower()
            ):
                logger.warning(f"Failed to create topic {topic}: {e}")

    def _next_sequence(self, workflow_id: str) -> int:
        """Get next sequence number for workflow"""
        current = self._sequence_numbers.get(workflow_id, 0)
        self._sequence_numbers[workflow_id] = current + 1
        return current + 1

    def _serialize_event(self, event: BaseEvent) -> bytes:
        """Serialize event to bytes"""
        data = event.to_dict()
        json_str = json.dumps(data, default=str)

        if self.config.compression:
            return gzip.compress(json_str.encode("utf-8"))
        return json_str.encode("utf-8")

    def _deserialize_event(self, data: bytes) -> BaseEvent:
        """Deserialize event from bytes"""
        if self.config.compression:
            try:
                data = gzip.decompress(data)
            except gzip.BadGzipFile:
                pass  # Not compressed

        json_data = json.loads(data.decode("utf-8"))
        return BaseEvent.from_dict(json_data)

    async def publish(self, event: BaseEvent) -> bool:
        """
        Publish an event to the workflow's topic.

        Args:
            event: The event to publish

        Returns:
            True if published successfully
        """
        # Assign sequence number
        event.sequence_number = self._next_sequence(event.workflow_id)

        if not self._connected or not self._producer:
            # Fall back to in-memory storage
            logger.debug(f"In-memory event: {event.event_type.value}")
            return self._store_in_memory(event)

        topic = self._topic_name(event.workflow_id)

        try:
            await self._ensure_topic(topic)

            # Serialize and send
            data = self._serialize_event(event)
            await self._producer.send_and_wait(
                topic,
                value=data,
                key=event.event_id.encode("utf-8"),
            )

            logger.debug(
                f"Published event {event.event_type.value} "
                f"to {topic} (seq={event.sequence_number})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return False

    async def append(self, event: BaseEvent) -> bool:
        """Backward-compatible alias for publish."""
        return await self.publish(event)

    async def publish_batch(self, events: list[BaseEvent]) -> int:
        """
        Publish multiple events in a batch.

        Args:
            events: List of events to publish

        Returns:
            Number of events published successfully
        """
        if not events:
            return 0

        published = 0
        for event in events:
            if await self.publish(event):
                published += 1

        return published

    async def load_events(
        self,
        workflow_id: str,
        from_sequence: int = 0,
        to_sequence: int | None = None,
    ) -> list[BaseEvent]:
        """
        Load all events for a workflow.

        Args:
            workflow_id: ID of the workflow
            from_sequence: Start from this sequence number
            to_sequence: Stop at this sequence number (inclusive)

        Returns:
            List of events in order
        """
        if not self._connected:
            return self._load_from_memory(workflow_id, from_sequence, to_sequence)

        topic = self._topic_name(workflow_id)
        events = []

        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.config.bootstrap_servers,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                consumer_timeout_ms=5000,
            )
            await consumer.start()

            try:
                async for msg in consumer:
                    event = self._deserialize_event(msg.value)

                    # Filter by sequence
                    if event.sequence_number < from_sequence:
                        continue
                    if to_sequence and event.sequence_number > to_sequence:
                        break

                    events.append(event)
            finally:
                await consumer.stop()

            # Sort by sequence number
            events.sort(key=lambda e: e.sequence_number)

            logger.debug(f"Loaded {len(events)} events for workflow {workflow_id}")
            return events

        except Exception as e:
            logger.error(f"Failed to load events: {e}")
            return []

    async def stream_events(
        self,
        workflow_id: str,
        from_sequence: int = 0,
    ) -> AsyncIterator[BaseEvent]:
        """
        Stream events in real-time.

        Args:
            workflow_id: ID of the workflow
            from_sequence: Start from this sequence number

        Yields:
            Events as they arrive
        """
        if not self._connected:
            # Yield from memory
            for event in self._load_from_memory(workflow_id, from_sequence):
                yield event
            return

        topic = self._topic_name(workflow_id)

        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.config.bootstrap_servers,
                group_id=f"{self.config.consumer_group}-{workflow_id}",
                auto_offset_reset="earliest",
            )
            await consumer.start()

            try:
                async for msg in consumer:
                    event = self._deserialize_event(msg.value)

                    if event.sequence_number >= from_sequence:
                        yield event
            finally:
                await consumer.stop()

        except Exception as e:
            logger.error(f"Failed to stream events: {e}")

    async def get_latest_sequence(self, workflow_id: str) -> int:
        """Get the latest sequence number for a workflow"""
        return self._sequence_numbers.get(workflow_id, 0)

    async def get_metadata(self, workflow_id: str) -> EventMetadata | None:
        """Get metadata about events for a workflow"""
        events = await self.load_events(workflow_id)

        if not events:
            return None

        return EventMetadata(
            workflow_id=workflow_id,
            topic=self._topic_name(workflow_id),
            event_count=len(events),
            first_event_time=events[0].timestamp,
            last_event_time=events[-1].timestamp,
            size_bytes=sum(len(self._serialize_event(e)) for e in events),
        )

    async def delete_workflow_events(self, workflow_id: str) -> bool:
        """
        Delete all events for a workflow.

        WARNING: This is destructive and cannot be undone!
        """
        topic = self._topic_name(workflow_id)

        # Clear in-memory
        self._in_memory_events.pop(workflow_id, None)
        self._sequence_numbers.pop(workflow_id, None)

        if not self._connected or not self._admin:
            return True

        try:
            await self._admin.delete_topics([topic])
            logger.info(f"Deleted topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete topic: {e}")
            return False

    # =========================================================================
    # In-Memory Fallback (when Redpanda not available)
    # =========================================================================

    _in_memory_events: dict[str, list[BaseEvent]] = {}

    def _store_in_memory(self, event: BaseEvent) -> bool:
        """Store event in memory (fallback)"""
        if event.workflow_id not in self._in_memory_events:
            self._in_memory_events[event.workflow_id] = []
        self._in_memory_events[event.workflow_id].append(event)
        return True

    def _load_from_memory(
        self,
        workflow_id: str,
        from_sequence: int = 0,
        to_sequence: int | None = None,
    ) -> list[BaseEvent]:
        """Load events from memory (fallback)"""
        events = self._in_memory_events.get(workflow_id, [])

        filtered = [
            e
            for e in events
            if e.sequence_number >= from_sequence
            and (to_sequence is None or e.sequence_number <= to_sequence)
        ]

        return sorted(filtered, key=lambda e: e.sequence_number)


# =============================================================================
# Event Store Context Manager
# =============================================================================


class EventStoreContext:
    """
    Context manager for event store operations.

    Usage:
        async with EventStoreContext() as store:
            await store.publish(event)
    """

    def __init__(self, config: EventStoreConfig | None = None):
        self.store = EventStore(config)

    async def __aenter__(self) -> EventStore:
        await self.store.connect()
        return self.store

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.store.disconnect()


# =============================================================================
# Singleton Instance
# =============================================================================

_default_store: EventStore | None = None


def get_event_store() -> EventStore:
    """Get the default event store instance"""
    global _default_store
    if _default_store is None:
        _default_store = EventStore()
    return _default_store


async def init_event_store(config: EventStoreConfig | None = None) -> EventStore:
    """Initialize and connect the default event store"""
    global _default_store
    _default_store = EventStore(config)
    await _default_store.connect()
    return _default_store


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "EventStore",
    "EventStoreConfig",
    "EventStoreContext",
    "EventMetadata",
    "get_event_store",
    "init_event_store",
]
