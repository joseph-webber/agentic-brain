# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Redis-backed voice queue and audio cache."""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Callable, Optional

from agentic_brain.core.redis_pool import RedisConfig, RedisPoolManager


def _json_compact(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _json_load(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)


@dataclass
class VoiceJob:
    text: str
    voice: str = "Karen (Premium)"
    rate: int = 155
    pitch: float = 1.0
    volume: float = 0.8
    emotion: str = "neutral"
    priority: str = "normal"
    timestamp: float = 0.0
    pause_after: Optional[float] = None
    job_id: str = ""
    sequence: int = 0

    def __post_init__(self) -> None:
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("Voice job text cannot be empty")
        if self.timestamp <= 0:
            self.timestamp = time.time()
        if not self.job_id:
            self.job_id = uuid.uuid4().hex
        self.priority = self.priority.lower()
        if self.priority not in {"normal", "high", "urgent"}:
            raise ValueError(f"Unsupported voice priority: {self.priority}")


class RedisVoiceQueue:
    """Crash-proof Redis queue for serialized speech."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = "BrainRedis2026",
        *,
        db: int = 0,
        pool: RedisPoolManager | None = None,
        client: Any | None = None,
    ) -> None:
        config = RedisConfig(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=True,
        )
        self._pool = pool or RedisPoolManager(config, client=client)
        self.QUEUE_KEY = "voice:queue"
        self.PRIORITY_KEY = "voice:queue:priority"
        self.STATE_KEY = "voice:state"

    @property
    def client(self):
        return self._pool.client

    def enqueue(self, job: VoiceJob) -> VoiceJob:
        payload = _json_compact(asdict(job))
        if job.priority == "normal":
            self.client.lpush(self.QUEUE_KEY, payload)
        else:
            self.client.lpush(self.PRIORITY_KEY, payload)
        self._refresh_depths()
        return job

    def dequeue(self) -> Optional[VoiceJob]:
        raw = self._dequeue_priority()
        if raw is None:
            raw = self._dequeue_fifo(self.QUEUE_KEY)
        self._refresh_depths()
        if raw is None:
            return None
        return VoiceJob(**_json_load(raw))

    def get_state(self) -> dict[str, Any]:
        state = self.client.hgetall(self.STATE_KEY)
        if not state:
            return {
                "is_speaking": False,
                "current_text": "",
                "current_voice": "",
                "current_lady": "",
                "queue_depth": self.depth,
                "priority_depth": int(self.client.llen(self.PRIORITY_KEY)),
                "normal_depth": int(self.client.llen(self.QUEUE_KEY)),
                "updated_at": 0.0,
            }

        normal_depth = int(state.get("normal_depth", 0) or 0)
        priority_depth = int(state.get("priority_depth", 0) or 0)
        return {
            "is_speaking": str(state.get("is_speaking", "")).lower()
            in {"1", "true", "yes"},
            "current_text": state.get("current_text", ""),
            "current_voice": state.get("current_voice", ""),
            "current_lady": state.get("current_lady", state.get("current_voice", "")),
            "queue_depth": int(
                state.get("queue_depth", normal_depth + priority_depth) or 0
            ),
            "priority_depth": priority_depth,
            "normal_depth": normal_depth,
            "updated_at": float(state.get("updated_at", 0.0) or 0.0),
        }

    def set_speaking(self, lady: str, text: str) -> None:
        self.client.hset(
            self.STATE_KEY,
            mapping={
                "is_speaking": "true",
                "current_text": text,
                "current_voice": lady,
                "current_lady": lady,
                "updated_at": str(time.time()),
            },
        )
        self._refresh_depths()

    def clear_speaking(self) -> None:
        self.client.hset(
            self.STATE_KEY,
            mapping={
                "is_speaking": "false",
                "current_text": "",
                "current_voice": "",
                "current_lady": "",
                "updated_at": str(time.time()),
            },
        )
        self._refresh_depths()

    @property
    def depth(self) -> int:
        return int(self.client.llen(self.QUEUE_KEY)) + int(
            self.client.llen(self.PRIORITY_KEY)
        )

    def clear(self) -> None:
        self.client.delete(self.QUEUE_KEY, self.PRIORITY_KEY, self.STATE_KEY)

    def _dequeue_priority(self) -> Optional[str]:
        items = self.client.lrange(self.PRIORITY_KEY, 0, -1)
        if not items:
            return None

        urgent_candidate = self._select_lowest_sequence(
            items,
            predicate=lambda payload: payload.get("priority") == "urgent",
        )
        if urgent_candidate is None:
            for raw in reversed(items):
                payload = _json_load(raw)
                if payload.get("priority") == "urgent":
                    urgent_candidate = raw
                    break

        if urgent_candidate is not None:
            self.client.lrem(self.PRIORITY_KEY, 1, urgent_candidate)
            return urgent_candidate

        return self._dequeue_fifo(self.PRIORITY_KEY)

    def _dequeue_fifo(self, key: str) -> Optional[str]:
        items = self.client.lrange(key, 0, -1)
        if not items:
            return None

        sequenced_candidate = self._select_lowest_sequence(items)
        if sequenced_candidate is not None:
            self.client.lrem(key, 1, sequenced_candidate)
            return sequenced_candidate

        return self.client.rpop(key)

    @staticmethod
    def _select_lowest_sequence(
        items: list[str],
        predicate: Optional[Callable[[dict[str, Any]], bool]] = None,
    ) -> Optional[str]:
        selected_raw: Optional[str] = None
        selected_sequence: Optional[int] = None

        for raw in items:
            payload = _json_load(raw)
            if predicate is not None and not predicate(payload):
                continue
            sequence = int(payload.get("sequence", 0) or 0)
            if sequence <= 0:
                continue
            if selected_sequence is None or sequence < selected_sequence:
                selected_raw = raw
                selected_sequence = sequence

        return selected_raw

    def _refresh_depths(self) -> None:
        normal_depth = int(self.client.llen(self.QUEUE_KEY))
        priority_depth = int(self.client.llen(self.PRIORITY_KEY))
        self.client.hset(
            self.STATE_KEY,
            mapping={
                "queue_depth": str(normal_depth + priority_depth),
                "priority_depth": str(priority_depth),
                "normal_depth": str(normal_depth),
                "updated_at": str(time.time()),
            },
        )


class VoiceAudioCache:
    """Redis audio blob cache with simple LRU eviction."""

    TTL = 86_400

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = "BrainRedis2026",
        *,
        db: int = 0,
        pool: RedisPoolManager | None = None,
        client: Any | None = None,
        ttl: int = 86_400,
        max_entries: int = 512,
    ) -> None:
        config = RedisConfig(
            host=host,
            port=port,
            password=password,
            db=db,
            decode_responses=True,
        )
        self._pool = pool or RedisPoolManager(config, client=client)
        self.CACHE_PREFIX = "voice:audio:"
        self.INDEX_KEY = "voice:audio:index"
        self.TTL = ttl
        self.max_entries = max_entries

    @property
    def client(self):
        return self._pool.client

    def get(self, text: str, voice: str) -> Optional[bytes]:
        key = self._key(text, voice)
        raw = self.client.get(key)
        if raw is None:
            return None

        payload = _json_load(raw)
        self.client.zadd(self.INDEX_KEY, {key: time.time()})
        self.client.expire(key, self.TTL)
        return base64.b64decode(payload["audio_base64"])

    def set(self, text: str, voice: str, audio: bytes) -> str:
        key = self._key(text, voice)
        payload = {
            "text": text,
            "voice": voice,
            "cached_at": time.time(),
            "audio_base64": base64.b64encode(audio).decode("ascii"),
            "size_bytes": len(audio),
        }
        self.client.setex(key, self.TTL, _json_compact(payload))
        self.client.zadd(self.INDEX_KEY, {key: time.time()})
        self._prune()
        return key

    def _prune(self) -> None:
        total = int(self.client.zcard(self.INDEX_KEY))
        if total <= self.max_entries:
            return
        overflow = total - self.max_entries
        for key in self.client.zrange(self.INDEX_KEY, 0, overflow - 1):
            self.client.delete(key)
            self.client.zrem(self.INDEX_KEY, key)

    def _key(self, text: str, voice: str) -> str:
        digest = hashlib.md5(f"{voice}:{text}".encode()).hexdigest()
        return f"{self.CACHE_PREFIX}{digest}"
