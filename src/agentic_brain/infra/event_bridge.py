# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Event bridge between Redis and Redpanda.

Architecture:
- Redis: Fast, ephemeral pub/sub for real-time LLM chat
- Redpanda: Durable event log for persistent message storage

Critical messages (marked with metadata) are persisted from Redis to Redpanda.
On restart, state can be replayed from Redpanda to restore Redis state.

Kafka client stack: ``confluent_kafka``
---------------------------------------
This module uses ``confluent_kafka`` (C-extension, librdkafka-backed) because:
- It is synchronous by design — matches the synchronous bridge pattern
- Provides fine-grained producer/consumer control (flush, poll) needed here
- The Admin API (``AdminClient``, ``NewTopic``) is only available in confluent_kafka

Other modules in the codebase use different stacks for different reasons:
- ``durability/`` uses ``aiokafka`` for async task/event queues
- ``rag/loaders/event_stream.py`` uses ``kafka-python`` for simple sync RAG loading
- ``voice/redpanda_queue.py`` uses ``aiokafka`` for async voice queuing

See: docs/KAFKA_CLIENTS.md for the full comparison and migration notes.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Set

import redis.asyncio as aioredis
from confluent_kafka import Consumer, KafkaError, Producer
from confluent_kafka.admin import AdminClient, NewTopic

logger = logging.getLogger(__name__)


@dataclass
class BridgedEvent:
    """An event that crosses the Redis-Redpanda bridge."""

    id: str
    source: str  # "redis" or "redpanda"
    topic: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    persistent: bool = False  # Should be persisted to Redpanda?
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(
            {
                "id": self.id,
                "source": self.source,
                "topic": self.topic,
                "payload": self.payload,
                "timestamp": self.timestamp.isoformat(),
                "persistent": self.persistent,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> "BridgedEvent":
        """Deserialize from JSON."""
        obj = json.loads(data)
        return cls(
            id=obj["id"],
            source=obj["source"],
            topic=obj["topic"],
            payload=obj["payload"],
            timestamp=datetime.fromisoformat(obj["timestamp"]),
            persistent=obj.get("persistent", False),
            metadata=obj.get("metadata", {}),
        )


class EventBridge:
    """Base class for event bridges."""

    async def start(self):
        """Start the bridge."""
        raise NotImplementedError

    async def stop(self):
        """Stop the bridge."""
        raise NotImplementedError


class RedisRedpandaBridge(EventBridge):
    """
    Bridges Redis pub/sub to Redpanda topics.

    - Subscribes to Redis channels
    - Publishes to Redpanda topics
    - Persists critical messages from Redis to Redpanda
    - Can replay messages from Redpanda on startup

    Topic Mapping:
    - redis.brain.llm.* -> redpanda.brain.llm.*
    - redis.brain.events.* -> redpanda.brain.events.*
    - Any channel marked with persistent=true
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        redpanda_brokers: Optional[str] = None,
        redpanda_admin_port: int = 9644,
        bridge_channels: Optional[list] = None,
        persistent_channels: Optional[Set[str]] = None,
    ):
        """
        Initialize the Redis-Redpanda bridge.

        Args:
            redis_host: Redis host
            redis_port: Redis port
            redis_password: Redis password (optional)
            redpanda_brokers: Redpanda broker list
            redpanda_admin_port: Redpanda admin API port
            bridge_channels: List of channels to bridge (default: all)
            persistent_channels: Set of channels that should persist to Redpanda
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redpanda_brokers = redpanda_brokers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.redpanda_admin_port = redpanda_admin_port
        self.bridge_channels = bridge_channels or [
            "brain.llm.*",
            "brain.events.*",
            "brain.agents.*",
        ]
        self.persistent_channels = persistent_channels or {
            "brain.llm.requests",
            "brain.llm.responses",
            "brain.events.critical",
            "brain.agents.state",
        }

        self.redis_client = None
        self.redis_pubsub = None
        self.producer = None
        self.consumer = None
        self.admin_client = None

        self.is_running = False
        self.event_callbacks: Dict[str, list] = {}

    async def initialize(self):
        """Initialize connections."""
        # Redis connection
        if self.redis_password:
            redis_url = (
                f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
            )
        else:
            redis_url = f"redis://{self.redis_host}:{self.redis_port}/0"

        self.redis_client = await aioredis.from_url(redis_url)
        logger.info("Redis client initialized for bridge")

        # Redpanda producer
        self.producer = Producer(
            {
                "bootstrap.servers": self.redpanda_brokers,
                "client.id": "redis-redpanda-bridge",
            }
        )
        logger.info(f"Redpanda producer initialized: {self.redpanda_brokers}")

        # Redpanda consumer
        self.consumer = Consumer(
            {
                "bootstrap.servers": self.redpanda_brokers,
                "group.id": "redis-redpanda-bridge",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )
        logger.info(f"Redpanda consumer initialized: {self.redpanda_brokers}")

        # Redpanda admin client
        self.admin_client = AdminClient(
            {
                "bootstrap.servers": self.redpanda_brokers,
            }
        )
        logger.info("Redpanda admin client initialized")

        # Create topics if needed
        await self._create_topics()

    async def _create_topics(self):
        """Create Redpanda topics for bridged channels."""
        loop = asyncio.get_event_loop()

        topics_to_create = []
        for channel in self.bridge_channels:
            topic = f"redis_{channel}"
            topics_to_create.append(
                NewTopic(topic, num_partitions=1, replication_factor=1)
            )

        if topics_to_create:

            def create_topics():
                try:
                    result = self.admin_client.create_topics(
                        topics_to_create, validate_only=False
                    )
                    for topic, future in result.items():
                        try:
                            future.result()
                            logger.info(f"Created Redpanda topic: {topic}")
                        except Exception as e:
                            if "TOPIC_ALREADY_EXISTS" in str(e):
                                logger.debug(f"Topic already exists: {topic}")
                            else:
                                logger.warning(f"Failed to create topic {topic}: {e}")
                except Exception as e:
                    logger.warning(f"Error creating topics: {e}")

            await loop.run_in_executor(None, create_topics)

    async def start(self):
        """Start the bridge."""
        await self.initialize()
        self.is_running = True
        logger.info("Redis-Redpanda bridge started")

        # Start background tasks
        asyncio.create_task(self._redis_subscriber_loop())
        asyncio.create_task(self._redpanda_consumer_loop())

    async def stop(self):
        """Stop the bridge."""
        self.is_running = False
        logger.info("Redis-Redpanda bridge stopped")

        if self.redis_client:
            await self.redis_client.close()

        if self.producer:
            self.producer.flush()

        if self.consumer:
            self.consumer.close()

    async def _redis_subscriber_loop(self):
        """Subscribe to Redis channels and forward to Redpanda."""
        try:
            self.redis_pubsub = self.redis_client.pubsub()

            # Subscribe to channels
            await self.redis_pubsub.subscribe(*self.bridge_channels)
            logger.info(f"Subscribed to Redis channels: {self.bridge_channels}")

            while self.is_running:
                try:
                    # Get message from Redis
                    message = await self.redis_pubsub.get_message(
                        ignore_subscribe_messages=True
                    )
                    if message:
                        await self._handle_redis_message(message)
                    else:
                        await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error in Redis subscriber loop: {e}")
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Redis subscriber loop failed: {e}")

    async def _handle_redis_message(self, message: Dict[str, Any]):
        """Handle a message from Redis."""
        try:
            channel = message["channel"]
            data = message["data"]

            # Check if this is a critical message that should persist
            persistent = self._should_persist(channel)

            # Create event
            event = BridgedEvent(
                id=f"redis_{int(time.time()*1000)}",
                source="redis",
                topic=channel,
                payload=json.loads(data) if isinstance(data, (str, bytes)) else data,
                persistent=persistent,
            )

            # Forward to Redpanda if marked as persistent
            if persistent:
                await self._forward_to_redpanda(event)

            # Call event callbacks
            await self._call_callbacks(event)

            logger.debug(f"Processed Redis message from {channel}")

        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")

    async def _redpanda_consumer_loop(self):
        """Consume from Redpanda topics and optionally restore to Redis."""
        try:
            # Subscribe to all bridged topics
            topics = [f"redis_{channel}" for channel in self.bridge_channels]
            self.consumer.subscribe(topics)
            logger.info(f"Subscribed to Redpanda topics: {topics}")

            while self.is_running:
                try:
                    msg = self.consumer.poll(timeout=1.0)
                    if msg is None:
                        continue

                    if msg.error():
                        if msg.error().code() != KafkaError._PARTITION_EOF:
                            logger.error(f"Redpanda consumer error: {msg.error()}")
                    else:
                        await self._handle_redpanda_message(msg)

                except Exception as e:
                    logger.error(f"Error in Redpanda consumer loop: {e}")
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Redpanda consumer loop failed: {e}")

    async def _handle_redpanda_message(self, msg):
        """Handle a message from Redpanda."""
        try:
            event = BridgedEvent.from_json(msg.value().decode("utf-8"))

            # If this came from Redis originally, don't restore it
            if event.source == "redis":
                logger.debug(f"Skipping Redis-originated message: {event.id}")
                return

            # Call event callbacks
            await self._call_callbacks(event)

            logger.debug(f"Processed Redpanda message: {event.topic}")

        except Exception as e:
            logger.error(f"Error handling Redpanda message: {e}")

    async def _forward_to_redpanda(self, event: BridgedEvent):
        """Forward an event to Redpanda."""
        try:
            topic = f"redis_{event.topic}"
            loop = asyncio.get_event_loop()

            def send_message():
                self.producer.produce(
                    topic,
                    key=event.id.encode("utf-8"),
                    value=event.to_json().encode("utf-8"),
                    callback=self._on_produce_callback,
                )
                self.producer.flush()

            await loop.run_in_executor(None, send_message)
            logger.debug(f"Forwarded event to Redpanda: {topic}")

        except Exception as e:
            logger.error(f"Error forwarding to Redpanda: {e}")

    def _on_produce_callback(self, err, msg):
        """Callback for producer."""
        if err:
            logger.error(f"Redpanda produce failed: {err}")
        else:
            logger.debug(f"Message produced to {msg.topic()}")

    def _should_persist(self, channel: str) -> bool:
        """Determine if a channel should persist to Redpanda."""
        # Check exact matches
        if channel in self.persistent_channels:
            return True

        # Check pattern matches (e.g., "brain.llm.*")
        for pattern in self.persistent_channels:
            if "*" in pattern:
                prefix = pattern.replace("*", "")
                if channel.startswith(prefix):
                    return True

        return False

    def register_event_callback(
        self,
        topic: str,
        callback: Callable[[BridgedEvent], None],
    ):
        """
        Register a callback for events on a topic.

        Args:
            topic: Redis topic/channel
            callback: Async callback function that receives BridgedEvent
        """
        if topic not in self.event_callbacks:
            self.event_callbacks[topic] = []
        self.event_callbacks[topic].append(callback)

    async def _call_callbacks(self, event: BridgedEvent):
        """Call all registered callbacks for an event."""
        try:
            # Exact topic match
            callbacks = self.event_callbacks.get(event.topic, [])

            # Pattern match (e.g., "brain.llm.*")
            for pattern, pattern_callbacks in self.event_callbacks.items():
                if "*" in pattern:
                    prefix = pattern.replace("*", "")
                    if event.topic.startswith(prefix):
                        callbacks.extend(pattern_callbacks)

            # Call all callbacks
            for callback in callbacks:
                try:
                    result = callback(event)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Error in event callback: {e}")

        except Exception as e:
            logger.error(f"Error calling callbacks: {e}")

    async def replay_from_redpanda(self, topic: str, restore_to_redis: bool = True):
        """
        Replay messages from Redpanda.

        Args:
            topic: Redpanda topic to replay
            restore_to_redis: If True, restore messages to Redis
        """
        try:
            logger.info(f"Replaying messages from Redpanda topic: {topic}")

            consumer = Consumer(
                {
                    "bootstrap.servers": self.redpanda_brokers,
                    "group.id": f"replay-{int(time.time())}",
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": False,
                }
            )

            consumer.subscribe([topic])

            count = 0
            while True:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    break

                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        logger.error(f"Consumer error: {msg.error()}")
                    break

                try:
                    event = BridgedEvent.from_json(msg.value().decode("utf-8"))

                    if restore_to_redis:
                        # Restore to Redis
                        channel = event.topic
                        payload = json.dumps(event.payload).encode("utf-8")
                        await self.redis_client.publish(channel, payload)
                        logger.debug(f"Replayed message to Redis: {channel}")

                    await self._call_callbacks(event)
                    count += 1

                except Exception as e:
                    logger.error(f"Error replaying message: {e}")

            consumer.close()
            logger.info(f"Replay complete: {count} messages")

        except Exception as e:
            logger.error(f"Error replaying from Redpanda: {e}")
