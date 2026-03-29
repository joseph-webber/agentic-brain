# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Redis voice cache for fast speech coordination and audio reuse.

Provides six subsystems backed by a single Redis connection:

1. **Audio cache**    -- pre-rendered speech bytes   (String/base64, 24h TTL)
2. **Voice queue**    -- persistent priority FIFO     (Sorted Set + List)
3. **Voice state**    -- cross-process speaking flag  (Hash)
4. **Preferences**    -- per-user voice settings      (Hash)
5. **Phrase metrics** -- usage frequency + latency    (Sorted Set / List)
6. **LLM context**   -- conversation failover cache   (String, 30 min TTL)

Binary audio is stored as base64-wrapped JSON so it works safely with Redis
clients configured with ``decode_responses=True``.

Key namespaces::

    voice:audio:{hash}       -- cached audio payload
    voice:queue              -- speech queue (Sorted Set)
    voice:queue:seq          -- monotonic sequence counter
    voice:queue:priority     -- priority-lane list (drained first)
    voice:state              -- current speaker state
    voice:prefs:{user}       -- per-user preferences
    voice:metrics:phrases    -- phrase frequency (Sorted Set)
    voice:metrics:latency    -- latency log (List, capped 1 000)
    llm:context:{session}    -- LLM conversation cache
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

from agentic_brain.core.redis_pool import RedisConfig, RedisPoolManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _json_load(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)


@dataclass
class VoiceState:
    """Current voice pipeline status shared through Redis."""

    is_speaking: bool = False
    current_text: str = ""
    current_voice: str = "Karen"
    queue_depth: int = 0
    message_id: str = ""
    updated_at: float = 0.0


class Priority(IntEnum):
    """Compatibility priority values for queued speech."""

    LOW = 10
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


@dataclass
class VoicePreferences:
    """Per-user voice settings stored in Redis."""

    preferred_voice: str = "Karen (Premium)"
    preferred_rate: int = 160
    provider: str = "local"
    volume: float = 0.8
    spatial_pan: int = 0  # -100 (left) .. 100 (right)
    spatial_reverb: float = 0.0  # 0..1
    calm_mode: bool = False  # slower rate during Bali spa

    def to_hash(self) -> Dict[str, str]:
        return {k: str(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_hash(cls, d: Dict[str, str]) -> VoicePreferences:
        return cls(
            preferred_voice=d.get("preferred_voice", "Karen (Premium)"),
            preferred_rate=int(d.get("preferred_rate", 160)),
            provider=d.get("provider", "local"),
            volume=float(d.get("volume", 0.8)),
            spatial_pan=int(d.get("spatial_pan", 0)),
            spatial_reverb=float(d.get("spatial_reverb", 0.0)),
            calm_mode=str(d.get("calm_mode", "False")).lower() == "true",
        )


@dataclass
class VoiceQueueItem:
    """Typed representation of a queued speech item."""

    id: str
    text: str
    voice: str
    priority: int
    enqueued_at: float


class VoiceCache:
    """Redis-backed cache and coordination layer for the voice system.

    Reuses the project-wide :class:`RedisPoolManager` for connections.
    """

    AUDIO_TTL = 86_400
    LLM_CTX_TTL = 1_800
    LATENCY_CAP = 1_000

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = "BrainRedis2026",
        *,
        db: int = 0,
        pool: RedisPoolManager | None = None,
        client: Any | None = None,
        audio_ttl: int = 86_400,
        llm_ctx_ttl: int = 1_800,
    ) -> None:
        host = host or os.getenv("REDIS_HOST", "localhost")
        port = int(port or os.getenv("REDIS_PORT", "6379"))
        password = (
            password
            if password is not None
            else os.getenv("REDIS_PASSWORD", "BrainRedis2026")
        )
        db = int(db if db is not None else os.getenv("REDIS_DB", "0"))

        config = RedisConfig(host=host, port=port, password=password, db=db)
        self._pool = pool or RedisPoolManager(config, client=client)

        self.AUDIO_TTL = audio_ttl
        self.LLM_CTX_TTL = llm_ctx_ttl

        self.audio_prefix = "voice:audio:"
        self.state_key = "voice:state"
        self.queue_key = "voice:queue"
        self.queue_seq_key = "voice:queue:seq"
        self.queue_priority_key = "voice:queue:priority"
        self.prefs_prefix = "voice:prefs:"
        self.metrics_key = "voice:metrics:phrases"
        self.latency_key = "voice:metrics:latency"
        self.llm_ctx_prefix = "llm:context:"

    @property
    def client(self):
        return self._pool.client

    # ------------------------------------------------------------------
    # 1. Audio caching
    # ------------------------------------------------------------------
    def cache_audio(
        self,
        text: str,
        voice: str,
        audio_bytes: bytes,
        ttl: int | None = None,
        *,
        duration_ms: float = 0.0,
    ) -> str:
        """Store synthesized audio for fast replay. Returns the Redis key."""

        key = self._audio_key(text, voice)
        payload = {
            "text": text,
            "voice": voice,
            "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
            "cached_at": time.time(),
            "size_bytes": len(audio_bytes),
            "duration_ms": duration_ms,
            "hit_count": 0,
        }
        self.client.setex(
            key, ttl or self.AUDIO_TTL, json.dumps(payload, ensure_ascii=False)
        )
        self._track_phrase(text, voice)
        return key

    def get_cached_audio(self, text: str, voice: str) -> Optional[bytes]:
        """Return cached audio bytes if present, bumping hit count."""

        key = self._audio_key(text, voice)
        data = self.client.get(key)
        if data is None:
            return None

        if isinstance(data, (bytes, bytearray)):
            try:
                decoded = data.decode("utf-8")
            except UnicodeDecodeError:
                return bytes(data)
        else:
            decoded = str(data)

        try:
            payload = json.loads(decoded)
        except json.JSONDecodeError:
            return decoded.encode("utf-8")

        audio_base64 = payload.get("audio_base64")
        if not audio_base64:
            return None

        # Bump hit count + refresh TTL
        payload["hit_count"] = payload.get("hit_count", 0) + 1
        self.client.setex(key, self.AUDIO_TTL, json.dumps(payload, ensure_ascii=False))
        return base64.b64decode(audio_base64)

    def get_audio_meta(self, text: str, voice: str) -> Optional[Dict[str, Any]]:
        """Return metadata without the heavy audio blob."""
        key = self._audio_key(text, voice)
        raw = self.client.get(key)
        if raw is None:
            return None
        payload = _json_load(raw)
        if isinstance(payload, dict):
            payload.pop("audio_base64", None)
        return payload

    def audio_exists(self, text: str, voice: str) -> bool:
        return self.client.exists(self._audio_key(text, voice)) > 0

    def evict_audio(self, text: str, voice: str) -> bool:
        return self.client.delete(self._audio_key(text, voice)) > 0

    def _audio_key(self, text: str, voice: str) -> str:
        digest = hashlib.md5(f"{text}:{voice}".encode()).hexdigest()
        return f"{self.audio_prefix}{digest}"

    # ------------------------------------------------------------------
    # 2. Voice queue  (Sorted Set + priority List lane)
    # ------------------------------------------------------------------
    def enqueue_speech(
        self,
        text: str,
        voice: str,
        priority: int = 50,
        *,
        rate: int = 160,
        message_id: str = "",
    ) -> Dict[str, Any]:
        """Add a speech request to the shared Redis queue.

        Items with ``priority >= 80`` also enter the priority lane
        (drained before the sorted-set main queue).
        """

        item = VoiceQueueItem(
            id=message_id or uuid.uuid4().hex,
            text=text,
            voice=voice,
            priority=int(priority),
            enqueued_at=time.time(),
        )
        member = _json_compact(item.__dict__)

        if priority >= 80:
            self.client.lpush(self.queue_priority_key, member)
        else:
            self.client.zadd(self.queue_key, {member: self._queue_score(priority)})

        self._refresh_queue_depth()
        return item.__dict__.copy()

    def dequeue_speech(self) -> Optional[Dict[str, Any]]:
        """Pop the highest-priority queued speech item.

        Priority lane (List) is drained first, then the Sorted Set.
        """

        # Priority lane first
        raw = self.client.rpop(self.queue_priority_key)
        if raw is not None:
            self._refresh_queue_depth()
            return _json_load(raw)

        items = self.client.zpopmax(self.queue_key, 1)
        self._refresh_queue_depth()
        if not items:
            return None

        raw_item = items[0][0]
        if isinstance(raw_item, (bytes, bytearray)):
            raw_item = raw_item.decode("utf-8")
        return json.loads(raw_item)

    def get_queue_depth(self) -> int:
        """Return the total number of queued speech items."""

        main = int(self.client.zcard(self.queue_key))
        pri = int(self.client.llen(self.queue_priority_key))
        return main + pri

    def peek_queue(self, count: int = 5) -> List[Dict[str, Any]]:
        """Preview queued items without removing them."""
        items: List[Dict[str, Any]] = []
        for raw in self.client.lrange(self.queue_priority_key, -count, -1):
            items.append(_json_load(raw))
        remaining = count - len(items)
        if remaining > 0:
            for raw in self.client.zrevrange(self.queue_key, 0, remaining - 1):
                items.append(_json_load(raw))
        return items

    def clear_queue(self) -> int:
        """Remove all queued speech items and return the removed count."""

        count = self.get_queue_depth()
        self.client.delete(self.queue_key, self.queue_priority_key)
        self._refresh_queue_depth()
        return count

    def _queue_score(self, priority: int) -> float:
        """Build a score where priority wins and FIFO is preserved within priority."""

        sequence = int(self.client.incr(self.queue_seq_key))
        return float(int(priority) * 1_000_000_000_000 - sequence)

    # ------------------------------------------------------------------
    # 3. State management
    # ------------------------------------------------------------------
    def set_state(self, state: VoiceState) -> None:
        """Persist the current voice state in Redis."""

        updated_at = time.time() if state.updated_at is None else state.updated_at
        self.client.hset(
            self.state_key,
            mapping={
                "is_speaking": "true" if state.is_speaking else "false",
                "current_text": state.current_text,
                "current_voice": state.current_voice,
                "current_lady": state.current_voice,
                "queue_depth": str(state.queue_depth),
                "message_id": state.message_id,
                "updated_at": str(updated_at),
            },
        )

    def set_speaking(
        self,
        *,
        speaking: bool,
        text: str = "",
        voice: str = "",
        message_id: str = "",
    ) -> None:
        """Convenience wrapper to update speaking flag."""
        depth = self.get_queue_depth()
        self.set_state(
            VoiceState(
                is_speaking=speaking,
                current_text=text,
                current_voice=voice,
                queue_depth=depth,
                message_id=message_id,
                updated_at=time.time(),
            )
        )

    def get_state(self) -> VoiceState:
        """Load the latest shared voice state."""

        data = self.client.hgetall(self.state_key)
        if not data:
            return VoiceState()

        return VoiceState(
            is_speaking=str(data.get("is_speaking", "")).lower()
            in {"1", "true", "yes"},
            current_text=str(data.get("current_text", "")),
            current_voice=str(data.get("current_voice", "Karen")),
            queue_depth=int(data.get("queue_depth", 0) or 0),
            message_id=str(data.get("message_id", "")),
            updated_at=float(data.get("updated_at", 0) or 0),
        )

    def is_speaking(self) -> bool:
        """Quick check -- is any process currently speaking?"""
        val = self.client.hget(self.state_key, "is_speaking")
        return str(val).lower() in {"1", "true", "yes"}

    # ------------------------------------------------------------------
    # 4. Voice Preferences  (Hash per user)
    # ------------------------------------------------------------------

    def set_preferences(self, user: str, prefs: VoicePreferences) -> None:
        key = f"{self.prefs_prefix}{user}"
        self.client.hset(key, mapping=prefs.to_hash())

    def get_preferences(self, user: str) -> VoicePreferences:
        key = f"{self.prefs_prefix}{user}"
        data = self.client.hgetall(key)
        if not data:
            return VoicePreferences()
        return VoicePreferences.from_hash(data)

    def update_preference(self, user: str, field: str, value: str) -> None:
        self.client.hset(f"{self.prefs_prefix}{user}", field, value)

    # ------------------------------------------------------------------
    # 5. Metrics  (Sorted Set + latency List)
    # ------------------------------------------------------------------
    def get_top_phrases(self, limit: int = 10) -> List[Tuple[str, float]]:
        """Return the most frequently cached phrases."""

        return self.client.zrevrange(self.metrics_key, 0, limit - 1, withscores=True)

    def top_phrases_detailed(self, count: int = 20) -> List[Dict[str, Any]]:
        """Top phrases with voice split and cache status."""
        raw = self.client.zrevrange(self.metrics_key, 0, count - 1, withscores=True)
        results: List[Dict[str, Any]] = []
        for member, score in raw:
            parts = str(member).split("::", 1)
            voice = parts[0] if len(parts) == 2 else ""
            text = parts[-1]
            results.append(
                {
                    "voice": voice,
                    "text": text,
                    "count": int(score),
                    "cached": self.audio_exists(text, voice) if voice else False,
                }
            )
        return results

    def phrases_needing_cache(self, min_uses: int = 3) -> List[Dict[str, Any]]:
        """Phrases used >= *min_uses* times but not yet cached."""
        candidates = self.top_phrases_detailed(100)
        return [e for e in candidates if e["count"] >= min_uses and not e["cached"]]

    def record_latency(self, latency_ms: float, voice: str = "") -> None:
        """Append a latency measurement (capped list)."""
        entry = _json_compact(
            {
                "ms": round(latency_ms, 2),
                "voice": voice,
                "ts": time.time(),
            }
        )
        pipe = self.client.pipeline(transaction=False)
        pipe.lpush(self.latency_key, entry)
        pipe.ltrim(self.latency_key, 0, self.LATENCY_CAP - 1)
        pipe.execute()

    def latency_stats(self) -> Dict[str, Any]:
        """p50/p95/p99/avg from the last 1 000 measurements."""
        raw = self.client.lrange(self.latency_key, 0, -1)
        if not raw:
            return {"count": 0}
        values = sorted(float(_json_load(r)["ms"]) for r in raw)
        n = len(values)
        return {
            "count": n,
            "avg_ms": round(sum(values) / n, 2),
            "p50_ms": round(values[n // 2], 2),
            "p95_ms": round(values[int(n * 0.95)], 2),
            "p99_ms": round(values[int(n * 0.99)], 2),
            "min_ms": round(values[0], 2),
            "max_ms": round(values[-1], 2),
        }

    def _track_phrase(self, text: str, voice: str = "") -> None:
        phrase = " ".join(text.split())[:100]
        if not phrase:
            return
        self.client.zincrby(self.metrics_key, 1, phrase)
        if voice:
            self.client.zincrby(self.metrics_key, 1, f"{voice}::{phrase}")

    def _refresh_queue_depth(self) -> None:
        """Update only the queue depth while preserving the rest of the state."""

        state = self.get_state()
        state.queue_depth = self.get_queue_depth()
        self.set_state(state)

    # ------------------------------------------------------------------
    # 6. LLM Context Cache  (String with TTL)
    # ------------------------------------------------------------------

    def store_context(
        self,
        session_id: str,
        context: Dict[str, Any],
        *,
        ttl: int | None = None,
    ) -> None:
        """Cache LLM conversation context for fast failover."""
        key = f"{self.llm_ctx_prefix}{session_id}"
        self.client.setex(key, ttl or self.LLM_CTX_TTL, _json_compact(context))

    def get_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        raw = self.client.get(f"{self.llm_ctx_prefix}{session_id}")
        return _json_load(raw)

    def extend_context(self, session_id: str, role: str, content: str) -> None:
        """Append a message to an existing context, preserving TTL."""
        key = f"{self.llm_ctx_prefix}{session_id}"
        raw = self.client.get(key)
        ctx = _json_load(raw) if raw else {"messages": []}
        ctx.setdefault("messages", []).append(
            {
                "role": role,
                "content": content,
                "ts": time.time(),
            }
        )
        remaining = self.client.ttl(key)
        ttl = max(remaining if remaining > 0 else 0, self.LLM_CTX_TTL)
        self.client.setex(key, ttl, _json_compact(ctx))

    def delete_context(self, session_id: str) -> bool:
        return self.client.delete(f"{self.llm_ctx_prefix}{session_id}") > 0

    # ------------------------------------------------------------------
    # Health / diagnostics
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """Quick health snapshot for monitoring."""
        try:
            depth = self.get_queue_depth()
            state = self.get_state()
            phrase_count = self.client.zcard(self.metrics_key)
            latency_count = self.client.llen(self.latency_key)
            return {
                "ok": True,
                "queue_depth": depth,
                "speaking": state.is_speaking,
                "current_voice": state.current_voice,
                "unique_phrases_tracked": phrase_count,
                "latency_samples": latency_count,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def stats(self) -> Dict[str, Any]:
        """Extended statistics for dashboards."""
        h = self.health()
        if not h.get("ok"):
            return h
        h["top_5_phrases"] = self.top_phrases_detailed(5)
        h["latency"] = self.latency_stats()
        h["uncached_hot_phrases"] = len(self.phrases_needing_cache())
        return h


VoiceRedisCache = VoiceCache
_default_voice_cache: VoiceCache | None = None


def get_voice_cache() -> VoiceCache:
    """Return a process-global Redis voice cache instance."""

    global _default_voice_cache
    if _default_voice_cache is None:
        _default_voice_cache = VoiceCache()
    return _default_voice_cache
