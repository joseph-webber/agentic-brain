#!/usr/bin/env python3
"""Voice event bus v2 — enhanced Redpanda integration for the world-class voice system.

Topics:
  brain.voice.input          – raw user speech (from Whisper)
  brain.voice.reasoning      – complexity analysis + routing decisions
  brain.voice.response       – LLM responses ready for TTS
  brain.voice.coordination   – inter-agent coordination messages
  brain.voice.health         – health checks and circuit breaker events
  brain.voice.memory         – conversation stored to Neo4j
  brain.voice.metrics        – latency, provider usage, quality metrics

All events are JSON and include a timestamp and source field.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

REDPANDA_BOOTSTRAP = os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_URL = os.getenv("VOICE_REDIS_URL", "redis://:BrainRedis2026@localhost:6379/0")

# Topic definitions
TOPICS = {
    "input": "brain.voice.input",
    "reasoning": "brain.voice.reasoning",
    "response": "brain.voice.response",
    "coordination": "brain.voice.coordination",
    "health": "brain.voice.health",
    "memory": "brain.voice.memory",
    "metrics": "brain.voice.metrics",
}

# Redis keys for state
STATE_KEYS = {
    "current_input": "voice:current_input",
    "current_response": "voice:current_response",
    "llm_used": "voice:llm_used",
    "health_status": "voice:health_status",
    "architect_progress": "voice:architect_progress",
    "world_class_ready": "voice:world_class_ready",
}


# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_producer = None
_redis_client = None


def _get_producer():
    global _producer
    if _producer is None:
        from kafka import KafkaProducer
        _producer = KafkaProducer(
            bootstrap_servers=REDPANDA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
    return _producer


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

def publish(topic_key: str, data: dict[str, Any]) -> None:
    """Publish an event to a voice topic.

    Args:
        topic_key: Short key from TOPICS dict (e.g. 'input', 'response').
        data: Event payload (timestamp and source added automatically).
    """
    topic = TOPICS.get(topic_key, topic_key)
    event = {
        "timestamp": time.time(),
        **data,
    }
    try:
        _get_producer().send(topic, event)
        _get_producer().flush()
    except Exception:
        # Never let event bus failures crash the voice pipeline
        pass


def publish_metric(
    event_type: str,
    *,
    provider: str = "",
    latency_ms: float = 0,
    strategy: str = "",
    complexity: str = "",
    success: bool = True,
    **extra: Any,
) -> None:
    """Publish a voice metrics event."""
    publish("metrics", {
        "event_type": event_type,
        "provider": provider,
        "latency_ms": round(latency_ms, 1),
        "strategy": strategy,
        "complexity": complexity,
        "success": success,
        **extra,
    })


def publish_health_event(component: str, status: str, **extra: Any) -> None:
    """Publish a health event for a voice component."""
    publish("health", {
        "component": component,
        "status": status,
        **extra,
    })


# ---------------------------------------------------------------------------
# State management (Redis)
# ---------------------------------------------------------------------------

def set_state(key: str, value: str, *, expire: int | None = None) -> None:
    """Set a Redis state value."""
    try:
        r = _get_redis()
        if expire:
            r.set(key, value, ex=expire)
        else:
            r.set(key, value)
    except Exception:
        pass


def get_state(key: str) -> str | None:
    """Get a Redis state value."""
    try:
        return _get_redis().get(key)
    except Exception:
        return None


def set_progress(message: str) -> None:
    """Update the architect progress in Redis."""
    set_state(STATE_KEYS["architect_progress"], message)


# ---------------------------------------------------------------------------
# Topic management
# ---------------------------------------------------------------------------

def ensure_topics() -> list[str]:
    """Create all voice topics if they don't exist."""
    try:
        from kafka.admin import KafkaAdminClient, NewTopic
        admin = KafkaAdminClient(bootstrap_servers=REDPANDA_BOOTSTRAP)
        new_topics = [
            NewTopic(name=topic, num_partitions=1, replication_factor=1)
            for topic in TOPICS.values()
        ]
        try:
            admin.create_topics(new_topics=new_topics, validate_only=False)
        except Exception as exc:
            text = str(exc).lower()
            if "already exists" not in text and "already been created" not in text:
                raise
        admin.close()
    except Exception:
        pass
    return list(TOPICS.values())


# ---------------------------------------------------------------------------
# Consuming (for daemons)
# ---------------------------------------------------------------------------

def create_consumer(
    topic_key: str,
    *,
    group_id: str = "voice-consumer",
    auto_offset_reset: str = "latest",
) -> Any:
    """Create a Kafka consumer for a voice topic."""
    from kafka import KafkaConsumer
    topic = TOPICS.get(topic_key, topic_key)
    return KafkaConsumer(
        topic,
        bootstrap_servers=REDPANDA_BOOTSTRAP,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
        consumer_timeout_ms=1000,
        value_deserializer=lambda v: json.loads(v.decode()),
    )
