#!/usr/bin/env python3
"""Redpanda + Redis helpers for voice chat coordination."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Callable

from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic

REDPANDA_BOOTSTRAP_SERVERS = os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_URL = os.getenv("VOICE_REDIS_URL", "redis://:BrainRedis2026@localhost:6379/0")

VOICE_INPUT_TOPIC = "brain.voice.input"
VOICE_REASONING_TOPIC = "brain.voice.reasoning"
VOICE_RESPONSE_TOPIC = "brain.voice.response"
VOICE_COORDINATION_TOPIC = "brain.voice.coordination"
VOICE_TOPICS = (
    VOICE_INPUT_TOPIC,
    VOICE_REASONING_TOPIC,
    VOICE_RESPONSE_TOPIC,
    VOICE_COORDINATION_TOPIC,
)

PROGRESS_KEY = "voice:gpt_redpanda_progress"
READY_KEY = "voice:redpanda_ready"

producer = KafkaProducer(
    bootstrap_servers=REDPANDA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode(),
)


def _get_redis_client():
    import redis  # type: ignore[import]

    return redis.from_url(REDIS_URL, decode_responses=True)


def create_voice_consumer(
    topic: str,
    *,
    group_id: str | None = None,
    auto_offset_reset: str = "latest",
    consumer_timeout_ms: int = 1000,
) -> KafkaConsumer:
    return KafkaConsumer(
        topic,
        bootstrap_servers=REDPANDA_BOOTSTRAP_SERVERS,
        group_id=group_id or f"voice-event-bus-{uuid.uuid4().hex}",
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
        consumer_timeout_ms=consumer_timeout_ms,
        value_deserializer=lambda v: json.loads(v.decode()),
    )


def ensure_voice_topics() -> tuple[str, ...]:
    admin = KafkaAdminClient(bootstrap_servers=REDPANDA_BOOTSTRAP_SERVERS)
    try:
        topics = [
            NewTopic(name=topic, num_partitions=1, replication_factor=1)
            for topic in VOICE_TOPICS
        ]
        try:
            admin.create_topics(new_topics=topics, validate_only=False)
        except Exception as exc:  # pragma: no cover - broker state dependent
            text = f"{type(exc).__name__}: {exc}".lower()
            if "already exists" not in text and "already been created" not in text:
                raise
        return VOICE_TOPICS
    finally:
        admin.close()


def publish_voice_event(topic: str, data: dict[str, Any]) -> None:
    producer.send(topic, data)
    producer.flush()


def subscribe_voice_events(
    topic: str,
    callback: Callable[[dict[str, Any]], Any],
    *,
    group_id: str | None = None,
    auto_offset_reset: str = "latest",
    consumer_timeout_ms: int = 1000,
) -> int:
    consumer = create_voice_consumer(
        topic,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        consumer_timeout_ms=consumer_timeout_ms,
    )
    processed = 0
    try:
        for msg in consumer:
            callback(msg.value)
            processed += 1
    finally:
        consumer.close()
    return processed


def wait_for_voice_event(
    topic: str,
    *,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
    timeout: float = 30.0,
    group_id: str | None = None,
    auto_offset_reset: str = "latest",
) -> dict[str, Any] | None:
    consumer = create_voice_consumer(
        topic,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        consumer_timeout_ms=500,
    )
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            records = consumer.poll(timeout_ms=500, max_records=10)
            for batch in records.values():
                for msg in batch:
                    payload = msg.value
                    if predicate is None or predicate(payload):
                        return payload
        return None
    finally:
        consumer.close()


def set_voice_state(key: str, value: str) -> None:
    client = _get_redis_client()
    client.set(key, value)


def get_voice_state(key: str) -> str | None:
    client = _get_redis_client()
    return client.get(key)


def publish_progress(
    status: str, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = {
        "status": status,
        "timestamp": time.time(),
        **(extra or {}),
    }
    set_voice_state(PROGRESS_KEY, json.dumps(payload))
    publish_voice_event(VOICE_COORDINATION_TOPIC, payload)
    return payload


def mark_redpanda_ready(value: str = "true") -> None:
    set_voice_state(READY_KEY, value)
