# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Redpanda Voice Event Stream Consumer.

Listens to ``brain.voice.*`` topics on the Redpanda event bus and feeds
incoming speech requests into the voice serializer.  This enables any
brain component (JHipster portal, Python bots, MCP servers) to request
voice output by publishing an event — the consumer handles serialization.

The consumer is **optional** — if Redpanda/Kafka is not available the
brain falls back to direct ``speak_safe()`` calls.

Usage::

    from agentic_brain.voice.stream_consumer import VoiceStreamConsumer

    consumer = VoiceStreamConsumer()
    await consumer.start()      # begins consuming in background
    consumer.status()            # health / metrics
    await consumer.stop()        # graceful shutdown
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_TOPIC = "brain.voice.request"
_GROUP_ID = "voice-stream-consumer"


@dataclass
class StreamMetrics:
    """Tracks consumer performance."""

    messages_received: int = 0
    messages_spoken: int = 0
    messages_failed: int = 0
    last_message_at: float = 0.0
    started_at: float = 0.0


class VoiceStreamConsumer:
    """Consumes voice requests from Redpanda and routes to the serializer.

    Falls back gracefully if ``aiokafka`` or Redpanda is unavailable.
    """

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        topic: str = _TOPIC,
        group_id: str = _GROUP_ID,
        speak_fn: Optional[Callable[..., bool]] = None,
    ) -> None:
        self._bootstrap = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self._topic = topic
        self._group_id = group_id
        self._speak_fn = speak_fn

        self._consumer = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._available = False
        self._metrics = StreamMetrics()

    # ── Lifecycle ────────────────────────────────────────────────────

    async def start(self) -> bool:
        """Start consuming events. Returns True if successfully connected."""
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError:
            logger.info("aiokafka not installed — voice stream consumer disabled")
            return False

        try:
            self._consumer = AIOKafkaConsumer(
                self._topic,
                bootstrap_servers=self._bootstrap,
                group_id=self._group_id,
                value_deserializer=lambda v: v.decode("utf-8"),
                auto_offset_reset="latest",
                enable_auto_commit=True,
            )
            await self._consumer.start()
            self._running = True
            self._available = True
            self._metrics.started_at = time.time()
            self._task = asyncio.create_task(self._consume_loop())
            logger.info("Voice stream consumer started (topic=%s)", self._topic)
            return True
        except Exception as exc:
            logger.warning("Voice stream consumer failed to start: %s", exc)
            self._available = False
            return False

    async def stop(self) -> None:
        """Stop the consumer gracefully."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:
                pass
            self._consumer = None
        self._available = False
        logger.info("Voice stream consumer stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_available(self) -> bool:
        return self._available

    # ── Status ───────────────────────────────────────────────────────

    def status(self) -> Dict:
        """Return health / metrics dict."""
        elapsed = time.time() - self._metrics.started_at if self._metrics.started_at else 0
        return {
            "running": self._running,
            "available": self._available,
            "topic": self._topic,
            "bootstrap": self._bootstrap,
            "messages_received": self._metrics.messages_received,
            "messages_spoken": self._metrics.messages_spoken,
            "messages_failed": self._metrics.messages_failed,
            "uptime_s": round(elapsed, 1),
        }

    # ── Internal ─────────────────────────────────────────────────────

    async def _consume_loop(self) -> None:
        """Main consumer loop — processes one message at a time."""
        while self._running:
            try:
                if self._consumer is None:
                    break
                messages = await self._consumer.getmany(timeout_ms=500)
                for _tp, msgs in messages.items():
                    for msg in msgs:
                        await self._handle_message(msg.value)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Voice stream consumer error")
                await asyncio.sleep(1.0)

    async def _handle_message(self, raw: str) -> None:
        """Parse and speak a single message."""
        self._metrics.messages_received += 1
        self._metrics.last_message_at = time.time()

        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            text = data.get("text", "")
            voice = data.get("voice", "Karen")
            rate = int(data.get("rate", 155))

            if not text:
                logger.debug("Ignoring empty voice stream message")
                return

            speak = self._speak_fn or self._default_speak
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: speak(text, voice=voice, rate=rate)
            )

            if result:
                self._metrics.messages_spoken += 1
            else:
                self._metrics.messages_failed += 1

        except Exception:
            self._metrics.messages_failed += 1
            logger.exception("Failed to handle voice stream message")

    @staticmethod
    def _default_speak(text: str, voice: str = "Karen", rate: int = 155) -> bool:
        from agentic_brain.voice.serializer import get_voice_serializer

        return get_voice_serializer().speak(text, voice=voice, rate=rate)
