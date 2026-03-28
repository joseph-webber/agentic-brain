# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Redpanda-backed voice queue - voices NEVER overlap.

This module provides a durable, priority-aware voice queue implemented on top of
Redpanda/Kafka with an automatic Redis fallback. It guarantees that only ONE
voice message is spoken at a time, even when many producers enqueue messages
concurrently or from different processes.

Design goals:
* Buffer all voice requests via Redpanda (or Redis) for durability
* Process exactly one message at a time
* Priority ordering (CRITICAL > URGENT > HIGH > NORMAL > LOW)
* Never lose a message when backends are available
* Safe fallback chain: Redpanda → Redis → in-memory

The actual audio is delegated to :class:`agentic_brain.voice.resilient.ResilientVoice`
so we reuse the existing multi-layer fallback chain instead of calling ``say``
directly. This keeps all voice safety guarantees in one place.

Kafka client stack: ``aiokafka`` (lazy import)
----------------------------------------------
``aiokafka`` is chosen here because voice queue processing is async-first —
new messages are continuously awaited without blocking the audio thread.
The import is wrapped in a try/except so the module degrades gracefully to
Redis-only or in-memory when ``aiokafka`` is not installed.

See: docs/KAFKA_CLIENTS.md for the full client comparison.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional

try:  # Optional dependency – handled gracefully when missing
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore
except Exception:  # pragma: no cover - import fallback
    AIOKafkaProducer = None  # type: ignore[assignment]
    AIOKafkaConsumer = None  # type: ignore[assignment]

try:  # Redis is provided via optional ``redis`` extra
    import redis.asyncio as aioredis  # type: ignore
except Exception:  # pragma: no cover - import fallback
    aioredis = None  # type: ignore[assignment]

from agentic_brain.voice.resilient import ResilientVoice

logger = logging.getLogger(__name__)


class VoicePriority(IntEnum):
    """Voice priority levels - higher = more urgent.

    Levels are intentionally sparse so future priorities can be inserted.

    * LOW (1): Background info, low-importance updates
    * NORMAL (5): Default conversational speech
    * HIGH (8): Important notifications, agent completions
    * URGENT (10): Warnings, important updates that should play next
    * CRITICAL (15): Emergencies – always chosen before others
    """

    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10
    CRITICAL = 15


@dataclass
class VoiceMessage:
    """Single voice message stored in the durable queue."""

    text: str
    voice: str = "Karen"
    rate: int = 155
    priority: VoicePriority = VoicePriority.NORMAL
    timestamp: float = 0.0

    def to_json(self) -> str:
        return json.dumps(
            {
                "text": self.text,
                "voice": self.voice,
                "rate": self.rate,
                "priority": int(self.priority),
                "timestamp": self.timestamp,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> VoiceMessage:
        d = json.loads(data)
        return cls(
            text=d["text"],
            voice=d.get("voice", "Karen"),
            rate=int(d.get("rate", 155)),
            priority=VoicePriority(int(d.get("priority", VoicePriority.NORMAL))),
            timestamp=float(d.get("timestamp", 0.0)),
        )


class RedpandaVoiceQueue:
    """Voice queue using Redpanda (Kafka API) with Redis and memory fallbacks.

    Backends
    --------
    ``backend`` can be one of:

    * ``"auto"`` (default) – try Redpanda, then Redis, then in-memory
    * ``"redpanda"`` – force Redpanda (may fall back if unavailable)
    * ``"redis"`` – force Redis (may fall back to memory if unavailable)
    * ``"memory"`` – in-memory only, for tests and local/dev use
    """

    TOPIC = "agentic-brain-voice-queue"

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        *,
        backend: str = "auto",
        redis_url: Optional[str] = None,
        redis_client=None,
        speak_func=None,
    ) -> None:
        self._bootstrap = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self._redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://localhost:6379/0"
        )
        self._backend: str = backend  # desired backend; may be updated after connect()

        self._producer: Optional[AIOKafkaProducer] = None  # type: ignore[assignment]
        self._consumer: Optional[AIOKafkaConsumer] = None  # type: ignore[assignment]
        self._redis = redis_client
        self._redis_key = self.TOPIC

        self._processing: bool = False
        self._current_voice_task: Optional[asyncio.Task] = None
        self._memory_queue: List[VoiceMessage] = []
        self._speak_func = speak_func or ResilientVoice.speak

    # ------------------------------------------------------------------
    # Backend setup
    # ------------------------------------------------------------------
    async def _connect_redpanda(self) -> bool:
        """Try to connect to Redpanda. Returns True on success."""

        if AIOKafkaProducer is None or AIOKafkaConsumer is None:
            logger.debug("aiokafka not installed – skipping Redpanda backend")
            return False

        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap,
                value_serializer=lambda v: v.encode("utf-8"),
            )
            await self._producer.start()

            self._consumer = AIOKafkaConsumer(
                self.TOPIC,
                bootstrap_servers=self._bootstrap,
                value_deserializer=lambda v: v.decode("utf-8"),
                group_id="voice-processor",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
            )
            await self._consumer.start()
            logger.info(
                "Redpanda voice queue connected (bootstrap=%s)", self._bootstrap
            )
            self._backend = "redpanda"
            return True
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Redpanda connection failed: %s", exc)
            try:
                if self._producer:
                    await self._producer.stop()
            except Exception:
                pass
            try:
                if self._consumer:
                    await self._consumer.stop()
            except Exception:
                pass
            self._producer = None
            self._consumer = None
            return False

    async def _connect_redis(self) -> bool:
        """Try to connect to Redis. Returns True on success."""

        if aioredis is None:
            logger.debug("redis extra not installed – skipping Redis backend")
            return False

        try:
            self._redis = aioredis.from_url(self._redis_url)
            # Simple ping to verify connectivity
            await self._redis.ping()
            logger.info("Redis voice queue connected (url=%s)", self._redis_url)
            self._backend = "redis"
            return True
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Redis connection failed: %s", exc)
            self._redis = None
            return False

    async def connect(self) -> None:
        """Connect to the selected backend.

        The order when ``backend='auto'`` is:
        1. Redpanda
        2. Redis
        3. In-memory (always available)
        """

        target = self._backend or "auto"

        if target == "memory":
            self._backend = "memory"
            logger.info("Voice queue using in-memory backend (tests/dev)")
            return

        if target in {"auto", "redis"} and self._redis is not None:
            self._backend = "redis"
            return

        # Prefer Redpanda unless explicitly disabled
        if target in {"auto", "redpanda"}:
            if await self._connect_redpanda():
                return

        # Fallback to Redis if possible
        if target in {"auto", "redis", "redpanda"}:
            if await self._connect_redis():
                return

        # Final fallback: in-memory
        self._backend = "memory"
        logger.warning("Voice queue falling back to in-memory backend – no durability")

    # ------------------------------------------------------------------
    # Enqueue helpers
    # ------------------------------------------------------------------
    async def enqueue(self, message: VoiceMessage) -> None:
        """Add a voice message to the queue.

        Timestamps are assigned on enqueue so we can perform stable
        priority+time ordering later in :meth:`process_queue`.
        """

        message.timestamp = time.time()

        if self._backend == "memory":
            self._memory_queue.append(message)
            return

        if self._backend == "redis" and self._redis is not None:
            await self._redis.rpush(self._redis_key, message.to_json())
            return

        # Default: Redpanda (or best-effort if producer is None)
        if not self._producer:
            # If producer is missing for any reason, drop to memory to avoid crashes
            logger.warning("Producer not available – enqueueing to memory backend")
            self._backend = "memory"
            self._memory_queue.append(message)
            return

        await self._producer.send_and_wait(self.TOPIC, message.to_json())

    async def speak(
        self,
        text: str,
        voice: str = "Karen",
        rate: int = 155,
        priority: VoicePriority = VoicePriority.NORMAL,
    ) -> None:
        """Convenience method to enqueue speech."""

        await self.enqueue(
            VoiceMessage(text=text, voice=voice, rate=rate, priority=priority)
        )

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------
    @staticmethod
    def _sort_pending(pending: List[VoiceMessage]) -> None:
        """Sort pending messages by priority then timestamp (in place)."""

        pending.sort(key=lambda m: (-int(m.priority), m.timestamp))

    async def _pull_from_backends(self, pending: List[VoiceMessage]) -> None:
        """Pull new messages from the active backend into the pending list."""

        if self._backend == "memory":
            # Move any enqueued messages into the local pending buffer
            if self._memory_queue:
                pending.extend(self._memory_queue)
                self._memory_queue.clear()
            return

        if self._backend == "redis" and self._redis is not None:
            try:
                # Non-blocking fetch with short timeout (seconds)
                item = await self._redis.blpop(self._redis_key, timeout=0)
            except TypeError:
                # Some Redis clients require int timeout; 0 = immediate
                item = await self._redis.blpop(self._redis_key, timeout=0)  # type: ignore[arg-type]
            if item:
                _key, raw = item
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                pending.append(VoiceMessage.from_json(raw))
            return

        # Redpanda / Kafka backend
        if self._consumer is None:
            return

        messages = await self._consumer.getmany(timeout_ms=100)
        for _tp, msgs in messages.items():
            for msg in msgs:
                pending.append(VoiceMessage.from_json(msg.value))

    async def _play_message(self, message: VoiceMessage) -> None:
        """Play a single message via the resilient voice system."""

        # Delegate to resilient voice chain – this already ensures a single
        # active invocation within the process and handles all fallbacks.
        await self._speak_func(message.text, message.voice, message.rate)

    async def process_queue(self) -> None:
        """Process the voice queue – ONE message at a time.

        This method is intended to run as a long-lived background task
        (e.g. ``asyncio.create_task(queue.process_queue())``). It never
        raises out of the loop; any exception is logged and processing
        continues so Joseph is never left without voice.
        """

        self._processing = True
        pending: List[VoiceMessage] = []

        logger.info("Voice queue processor started (backend=%s)", self._backend)

        while self._processing:
            try:
                # Pull new messages from backend into local buffer
                await self._pull_from_backends(pending)

                if pending:
                    # Sort by priority (highest first), then timestamp
                    self._sort_pending(pending)

                    # Process highest-priority message
                    current = pending.pop(0)

                    # SPEAK - blocking (from queue point of view) until complete
                    await self._play_message(current)

                    # Small gap between voices to avoid perceived overlap
                    await asyncio.sleep(0.5)
                else:
                    # No work right now – short sleep to avoid busy loop
                    await asyncio.sleep(0.1)

            except (
                asyncio.CancelledError
            ):  # pragma: no cover - cooperative cancellation
                break
            except Exception as exc:  # pragma: no cover - safety net
                logger.error("Voice queue error: %s", exc)
                await asyncio.sleep(1.0)

        logger.info("Voice queue processor stopped (backend=%s)", self._backend)

    async def stop(self) -> None:
        """Stop processing and close backend connections."""

        self._processing = False

        # Give the loop a moment to exit if running in background
        await asyncio.sleep(0)

        if self._producer:
            try:
                await self._producer.stop()
            except Exception:  # pragma: no cover
                pass
            self._producer = None

        if self._consumer:
            try:
                await self._consumer.stop()
            except Exception:  # pragma: no cover
                pass
            self._consumer = None

        if self._redis is not None:
            try:
                await self._redis.close()
            except Exception:  # pragma: no cover
                pass
            self._redis = None

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------
    @property
    def backend(self) -> str:
        """Return the active backend name (redpanda/redis/memory)."""

        return self._backend

    async def queue_length(self) -> Optional[int]:
        """Best-effort queue length for the active backend.

        * For Redis: length of the Redis list
        * For memory: length of the local buffer
        * For Redpanda: returns ``None`` (not trivial to compute)
        """

        if self._backend == "memory":
            return len(self._memory_queue)
        if self._backend == "redis" and self._redis is not None:
            try:
                return int(await self._redis.llen(self._redis_key))
            except Exception:  # pragma: no cover - network dependent
                return None
        return None

    async def clear(self) -> int:
        """Clear pending messages for the active backend.

        Returns the estimated number of messages removed. For Redpanda the
        operation is a no-op (returning 0) because deleting data from Kafka
        safely requires admin tooling and is outside the scope of this helper.
        """

        if self._backend == "memory":
            count = len(self._memory_queue)
            self._memory_queue.clear()
            return count

        if self._backend == "redis" and self._redis is not None:
            try:
                count = int(await self._redis.llen(self._redis_key))
            except Exception:  # pragma: no cover - network dependent
                count = 0
            try:
                await self._redis.delete(self._redis_key)
            except Exception:  # pragma: no cover - network dependent
                pass
            return count

        # Redpanda backend: we do not try to mutate the topic here
        logger.info("Clear operation is a no-op for Redpanda backend")
        return 0

    async def status(self) -> dict:
        """Return a status dictionary for CLI/monitoring."""

        length = await self.queue_length()
        return {
            "backend": self._backend,
            "processing": self._processing,
            "bootstrap_servers": self._bootstrap,
            "redis_url": self._redis_url if self._backend == "redis" else None,
            "queue_length": length,
        }


# Global queue instance -------------------------------------------------
_voice_queue: Optional[RedpandaVoiceQueue] = None


async def get_voice_queue() -> RedpandaVoiceQueue:
    """Get or create the global voice queue instance."""

    global _voice_queue
    if _voice_queue is None:
        _voice_queue = RedpandaVoiceQueue()
        await _voice_queue.connect()
    return _voice_queue


# Convenience functions -------------------------------------------------
async def queue_speak(
    text: str,
    voice: str = "Karen",
    rate: int = 155,
    priority: VoicePriority = VoicePriority.NORMAL,
) -> None:
    """Queue a voice message – NEVER overlaps."""

    queue = await get_voice_queue()
    await queue.speak(text, voice, rate, priority)


async def queue_urgent(text: str, voice: str = "Karen") -> None:
    """Queue an urgent message – plays as soon as current message finishes."""

    await queue_speak(text, voice, priority=VoicePriority.URGENT)


async def queue_critical(text: str, voice: str = "Karen") -> None:
    """Queue a critical message – always chosen before other queued items."""

    await queue_speak(text, voice, priority=VoicePriority.CRITICAL)
