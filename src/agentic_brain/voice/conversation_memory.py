# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Conversation memory for voice continuity.

Tracks what each lady has said recently so the brain can:
- Avoid repeating the same thing twice
- Answer "what did you just say?" queries
- Maintain per-lady conversation history

Storage: Redis (with TTL) → in-memory fallback.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Redis key prefix for voice conversation memory
_REDIS_PREFIX = "brain.voice.memory"

# Default TTL: 1 hour
_DEFAULT_TTL_SECONDS = int(os.getenv("AGENTIC_BRAIN_VOICE_MEMORY_TTL", "3600"))

# Maximum utterances kept in-memory per lady (prevents unbounded growth)
_MAX_IN_MEMORY = int(os.getenv("AGENTIC_BRAIN_VOICE_MEMORY_MAX", "500"))


@dataclass(frozen=True)
class Utterance:
    """A single spoken utterance."""

    lady: str
    text: str
    timestamp: float = field(default_factory=time.time)
    voice: str = ""
    rate: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Utterance:
        return cls(
            lady=data.get("lady", ""),
            text=data.get("text", ""),
            timestamp=float(data.get("timestamp", 0.0)),
            voice=data.get("voice", ""),
            rate=int(data.get("rate", 0)),
        )

    def age_seconds(self) -> float:
        """Seconds since this utterance was recorded."""
        return time.time() - self.timestamp


class ConversationMemory:
    """Thread-safe conversation memory with Redis + in-memory fallback.

    All public methods are safe to call from any thread.

    Usage::

        mem = get_conversation_memory()
        mem.record("karen", "Good morning Joseph")
        recent = mem.get_recent("karen", count=5)
        last = mem.get_last()
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        redis_client: Any | None = None,
        use_redis: bool = True,
    ) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        # In-memory store: lady → list[Utterance]  (newest last)
        self._store: Dict[str, List[Utterance]] = {}
        # Global ordered list (newest last) for get_last() / search()
        self._global: List[Utterance] = []
        self._redis: Any | None = None
        self._redis_available = False

        if use_redis:
            self._init_redis(redis_client)

    # ── Redis bootstrap ──────────────────────────────────────────────

    def _init_redis(self, client: Any | None) -> None:
        """Try to connect to Redis; silently fall back to in-memory."""
        if client is not None:
            self._redis = client
            self._redis_available = True
            return
        try:
            from agentic_brain.core.redis_pool import get_redis_pool

            pool = get_redis_pool()
            health = pool.health_check()
            if health.get("ok"):
                self._redis = pool.client
                self._redis_available = True
                logger.debug("ConversationMemory: Redis connected")
            else:
                logger.debug(
                    "ConversationMemory: Redis unhealthy, using in-memory fallback"
                )
        except Exception:
            logger.debug(
                "ConversationMemory: Redis unavailable, using in-memory fallback",
                exc_info=True,
            )

    @property
    def redis_available(self) -> bool:
        return self._redis_available

    # ── Core API ─────────────────────────────────────────────────────

    def record(
        self,
        lady: str,
        text: str,
        timestamp: float | None = None,
        *,
        voice: str = "",
        rate: int = 0,
    ) -> Utterance:
        """Record an utterance.  Returns the stored ``Utterance``."""
        ts = timestamp if timestamp is not None else time.time()
        utt = Utterance(lady=lady, text=text, timestamp=ts, voice=voice, rate=rate)

        with self._lock:
            self._store.setdefault(lady, []).append(utt)
            self._global.append(utt)
            self._trim_in_memory(lady)

        if self._redis_available:
            self._redis_push(utt)

        return utt

    def get_recent(self, lady: str | None = None, count: int = 10) -> List[Utterance]:
        """Return the *count* most recent utterances.

        If *lady* is given, only that lady's utterances are returned.
        Results are ordered oldest → newest (natural conversation order).
        """
        if lady is not None:
            if self._redis_available:
                return self._redis_recent_by_lady(lady, count)
            with self._lock:
                return list(self._store.get(lady, [])[-count:])

        if self._redis_available:
            return self._redis_recent_global(count)
        with self._lock:
            return list(self._global[-count:])

    def get_last(self, lady: str | None = None) -> Optional[Utterance]:
        """Return the single most recent utterance (optionally per lady)."""
        results = self.get_recent(lady=lady, count=1)
        return results[0] if results else None

    def search(self, query: str, *, limit: int = 20) -> List[Utterance]:
        """Case-insensitive substring search across all utterances."""
        query_lower = query.lower()

        if self._redis_available:
            return self._redis_search(query_lower, limit)

        with self._lock:
            matches: List[Utterance] = []
            for utt in reversed(self._global):
                if query_lower in utt.text.lower():
                    matches.append(utt)
                    if len(matches) >= limit:
                        break
            matches.reverse()
            return matches

    def get_ladies(self) -> List[str]:
        """Return names of all ladies with recorded utterances."""
        if self._redis_available:
            return self._redis_ladies()
        with self._lock:
            return sorted(self._store.keys())

    def count(self, lady: str | None = None) -> int:
        """Total recorded utterances (optionally per lady)."""
        if lady is not None:
            if self._redis_available:
                return self._redis_count_lady(lady)
            with self._lock:
                return len(self._store.get(lady, []))
        if self._redis_available:
            return self._redis_count_global()
        with self._lock:
            return len(self._global)

    def clear(self, lady: str | None = None) -> int:
        """Remove utterances.  Returns count deleted."""
        if lady is not None:
            return self._clear_lady(lady)
        return self._clear_all()

    # ── In-memory helpers ────────────────────────────────────────────

    def _trim_in_memory(self, lady: str) -> None:
        """Evict oldest entries when the per-lady list exceeds the cap."""
        buf = self._store.get(lady, [])
        if len(buf) > _MAX_IN_MEMORY:
            excess = len(buf) - _MAX_IN_MEMORY
            self._store[lady] = buf[excess:]
        if len(self._global) > _MAX_IN_MEMORY * 2:
            excess = len(self._global) - _MAX_IN_MEMORY * 2
            self._global = self._global[excess:]

    def _clear_lady(self, lady: str) -> int:
        with self._lock:
            removed = len(self._store.pop(lady, []))
            self._global = [u for u in self._global if u.lady != lady]
        if self._redis_available:
            try:
                self._redis.delete(self._lady_key(lady))
                self._redis.srem(f"{_REDIS_PREFIX}:ladies", lady)
            except Exception:
                logger.debug("Redis clear for lady %s failed", lady, exc_info=True)
        return removed

    def _clear_all(self) -> int:
        with self._lock:
            total = len(self._global)
            self._store.clear()
            self._global.clear()
        if self._redis_available:
            try:
                ladies = self._redis_ladies()
                keys = [self._lady_key(l) for l in ladies]
                keys.append(f"{_REDIS_PREFIX}:global")
                keys.append(f"{_REDIS_PREFIX}:ladies")
                if keys:
                    self._redis.delete(*keys)
            except Exception:
                logger.debug("Redis clear all failed", exc_info=True)
        return total

    # ── Redis storage helpers ────────────────────────────────────────

    @staticmethod
    def _lady_key(lady: str) -> str:
        return f"{_REDIS_PREFIX}:lady:{lady}"

    def _redis_push(self, utt: Utterance) -> None:
        try:
            payload = json.dumps(utt.to_dict(), ensure_ascii=False)
            pipe = self._redis.pipeline()
            # Per-lady list
            lady_key = self._lady_key(utt.lady)
            pipe.rpush(lady_key, payload)
            pipe.expire(lady_key, self._ttl)
            # Global list
            global_key = f"{_REDIS_PREFIX}:global"
            pipe.rpush(global_key, payload)
            pipe.expire(global_key, self._ttl)
            # Track lady names
            pipe.sadd(f"{_REDIS_PREFIX}:ladies", utt.lady)
            pipe.execute()
        except Exception:
            logger.debug("Redis push failed, in-memory still has it", exc_info=True)
            self._redis_available = False

    def _redis_recent_by_lady(self, lady: str, count: int) -> List[Utterance]:
        try:
            raw: Sequence[str] = self._redis.lrange(self._lady_key(lady), -count, -1)
            return [Utterance.from_dict(json.loads(r)) for r in raw]
        except Exception:
            logger.debug("Redis read failed, falling back to in-memory", exc_info=True)
            with self._lock:
                return list(self._store.get(lady, [])[-count:])

    def _redis_recent_global(self, count: int) -> List[Utterance]:
        try:
            raw: Sequence[str] = self._redis.lrange(
                f"{_REDIS_PREFIX}:global", -count, -1
            )
            return [Utterance.from_dict(json.loads(r)) for r in raw]
        except Exception:
            logger.debug("Redis read failed, falling back to in-memory", exc_info=True)
            with self._lock:
                return list(self._global[-count:])

    def _redis_search(self, query_lower: str, limit: int) -> List[Utterance]:
        """Search Redis global list.  Falls back to in-memory on error."""
        try:
            raw: Sequence[str] = self._redis.lrange(f"{_REDIS_PREFIX}:global", 0, -1)
            matches: List[Utterance] = []
            for item in reversed(raw):
                utt = Utterance.from_dict(json.loads(item))
                if query_lower in utt.text.lower():
                    matches.append(utt)
                    if len(matches) >= limit:
                        break
            matches.reverse()
            return matches
        except Exception:
            logger.debug("Redis search failed, falling back", exc_info=True)
            return (
                self.search.__wrapped__(self, query_lower, limit=limit)
                if hasattr(self.search, "__wrapped__")
                else []
            )

    def _redis_ladies(self) -> List[str]:
        try:
            return sorted(self._redis.smembers(f"{_REDIS_PREFIX}:ladies"))
        except Exception:
            with self._lock:
                return sorted(self._store.keys())

    def _redis_count_lady(self, lady: str) -> int:
        try:
            return int(self._redis.llen(self._lady_key(lady)))
        except Exception:
            with self._lock:
                return len(self._store.get(lady, []))

    def _redis_count_global(self) -> int:
        try:
            return int(self._redis.llen(f"{_REDIS_PREFIX}:global"))
        except Exception:
            with self._lock:
                return len(self._global)

    def health(self) -> Dict[str, Any]:
        """Return a health summary."""
        with self._lock:
            in_mem_count = len(self._global)
            ladies = sorted(self._store.keys())
        return {
            "redis_available": self._redis_available,
            "ttl_seconds": self._ttl,
            "in_memory_count": in_mem_count,
            "ladies": ladies,
        }


# ── Singleton ────────────────────────────────────────────────────────

_instance: ConversationMemory | None = None
_instance_lock = threading.Lock()


def get_conversation_memory(**kwargs: Any) -> ConversationMemory:
    """Return (or create) the global ConversationMemory singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ConversationMemory(**kwargs)
    return _instance


def reset_conversation_memory() -> None:
    """Tear down the singleton (useful in tests)."""
    global _instance
    with _instance_lock:
        _instance = None
