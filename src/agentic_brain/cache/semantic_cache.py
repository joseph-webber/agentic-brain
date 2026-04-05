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

"""
Semantic Prompt Cache implementation.

Provides intelligent caching of LLM responses with:
- Semantic key normalization
- Multiple storage backends
- TTL expiration and LRU eviction
- Comprehensive metrics
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
import sqlite3
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot = sum(a * b for a, b in zip(v1, v2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class CacheConfig:
    """Configuration for semantic cache."""

    # Core settings
    enabled: bool = True
    ttl_seconds: int = 3600  # 1 hour default
    max_entries: int = 10000  # LRU eviction threshold

    # Semantic matching
    normalize_whitespace: bool = True
    normalize_case: bool = False  # Case often matters in prompts
    normalize_punctuation: bool = False

    # Backend selection
    backend: str = "memory"  # memory, sqlite, redis

    # SQLite settings
    sqlite_path: Optional[str] = None

    # Redis settings
    redis_url: Optional[str] = None
    redis_prefix: str = "agentic_brain:cache:"

    # Performance
    async_writes: bool = True  # Don't block on cache writes
    compression: bool = False  # Compress large responses
    compression_threshold: int = 1024  # Bytes

    def __post_init__(self):
        if self.sqlite_path is None:
            self.sqlite_path = ".cache/semantic_cache.db"


# =============================================================================
# Cache Entry & Key
# =============================================================================


@dataclass
class CacheEntry:
    """A cached LLM response."""

    key: str
    response: str
    model: str
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
    last_accessed: Optional[datetime] = None

    # Metadata for debugging/analytics
    original_prompt_hash: str = ""
    system_hash: str = ""
    tokens_saved: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return datetime.now(UTC) > self.expires_at

    def touch(self) -> None:
        """Update access time and hit count."""
        self.last_accessed = datetime.now(UTC)
        self.hit_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "response": self.response,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "hit_count": self.hit_count,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "original_prompt_hash": self.original_prompt_hash,
            "system_hash": self.system_hash,
            "tokens_saved": self.tokens_saved,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CacheEntry:
        """Deserialize from dictionary."""
        return cls(
            key=data["key"],
            response=data["response"],
            model=data["model"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            hit_count=data.get("hit_count", 0),
            last_accessed=(
                datetime.fromisoformat(data["last_accessed"])
                if data.get("last_accessed")
                else None
            ),
            original_prompt_hash=data.get("original_prompt_hash", ""),
            system_hash=data.get("system_hash", ""),
            tokens_saved=data.get("tokens_saved", 0),
        )


@dataclass
class SemanticCacheKey:
    """
    Generates semantic cache keys from prompts.

    Keys are based on normalized content + model + temperature,
    allowing cache hits even with minor prompt variations.
    """

    # Normalization patterns
    WHITESPACE_PATTERN = re.compile(r"\s+")
    PUNCTUATION_PATTERN = re.compile(r"[^\w\s]")

    @classmethod
    def create(
        cls,
        prompt: str,
        system: Optional[str] = None,
        model: str = "default",
        temperature: float = 0.7,
        config: Optional[CacheConfig] = None,
    ) -> str:
        """
        Create a semantic cache key from prompt components.

        Args:
            prompt: User prompt/message
            system: System prompt (optional)
            model: Model identifier
            temperature: Sampling temperature
            config: Normalization configuration

        Returns:
            SHA256 hash as hex string
        """
        config = config or CacheConfig()

        # Normalize prompt
        normalized_prompt = cls._normalize(prompt, config)
        normalized_system = cls._normalize(system or "", config)

        # Build key components
        components = {
            "prompt": normalized_prompt,
            "system": normalized_system,
            "model": model,
            "temperature": round(
                temperature, 2
            ),  # Round to avoid float precision issues
        }

        # Create deterministic JSON string
        key_string = json.dumps(components, sort_keys=True, ensure_ascii=True)

        # Hash it
        return hashlib.sha256(key_string.encode()).hexdigest()

    @classmethod
    def _normalize(cls, text: str, config: CacheConfig) -> str:
        """Normalize text based on configuration."""
        if not text:
            return ""

        normalized = text

        # Whitespace normalization (most common)
        if config.normalize_whitespace:
            normalized = cls.WHITESPACE_PATTERN.sub(" ", normalized).strip()

        # Case normalization (use with caution - case often matters)
        if config.normalize_case:
            normalized = normalized.lower()

        # Punctuation normalization (aggressive - rarely needed)
        if config.normalize_punctuation:
            normalized = cls.PUNCTUATION_PATTERN.sub("", normalized)

        return normalized

    @classmethod
    def create_prompt_hash(cls, prompt: str) -> str:
        """Create a hash of just the prompt for tracking."""
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]


# =============================================================================
# Cache Statistics
# =============================================================================


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    expirations: int = 0
    errors: int = 0

    # Size tracking
    current_entries: int = 0
    max_entries: int = 0

    # Timing
    total_hit_time_ms: float = 0
    total_miss_time_ms: float = 0

    # Cost savings estimate (rough)
    estimated_tokens_saved: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def avg_hit_time_ms(self) -> float:
        """Average time for cache hits."""
        return self.total_hit_time_ms / self.hits if self.hits > 0 else 0.0

    @property
    def avg_miss_time_ms(self) -> float:
        """Average time for cache misses."""
        return self.total_miss_time_ms / self.misses if self.misses > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate * 100, 2),
            "sets": self.sets,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "errors": self.errors,
            "current_entries": self.current_entries,
            "max_entries": self.max_entries,
            "avg_hit_time_ms": round(self.avg_hit_time_ms, 2),
            "avg_miss_time_ms": round(self.avg_miss_time_ms, 2),
            "estimated_tokens_saved": self.estimated_tokens_saved,
        }


# =============================================================================
# Cache Backend Interface
# =============================================================================


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Retrieve entry by key."""
        pass

    @abstractmethod
    async def set(self, entry: CacheEntry) -> bool:
        """Store entry."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete entry by key."""
        pass

    @abstractmethod
    async def clear(self) -> int:
        """Clear all entries. Returns count deleted."""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get current number of entries."""
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        pass


# =============================================================================
# Memory Backend (Default)
# =============================================================================


class MemoryBackend(CacheBackend):
    """
    In-memory cache backend with LRU eviction.

    Thread-safe using a lock. Suitable for single-process deployments.
    For multi-process, use Redis backend.
    """

    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry and move to end (LRU)."""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()

            return entry

    async def set(self, entry: CacheEntry) -> bool:
        """Store entry with LRU eviction if needed."""
        with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_entries:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Evicted oldest cache entry: {oldest_key[:16]}...")

            self._cache[entry.key] = entry
            self._cache.move_to_end(entry.key)

            return True

    async def delete(self, key: str) -> bool:
        """Delete entry by key."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> int:
        """Clear all entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    async def size(self) -> int:
        """Get current entry count."""
        with self._lock:
            return len(self._cache)

    async def cleanup_expired(self) -> int:
        """Remove expired entries."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def get_all_entries(self) -> List[CacheEntry]:
        """Get all entries (for debugging/export)."""
        with self._lock:
            return list(self._cache.values())


# =============================================================================
# Main Semantic Cache Class
# =============================================================================


class SemanticCache:
    """
    High-level semantic prompt cache.

    Provides intelligent caching of LLM responses with automatic
    key generation, TTL management, and statistics tracking.

    Example:
        cache = SemanticCache(CacheConfig(ttl_seconds=3600))

        # Generate key from prompt
        key = cache.create_key("What is Python?", model="gpt-4")

        # Check cache
        if response := await cache.get(key):
            print(f"Cache hit! {response}")
        else:
            # Make API call
            response = await llm.chat("What is Python?")
            await cache.set(key, response, model="gpt-4")
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.stats = CacheStats(max_entries=self.config.max_entries)

        # Initialize backend
        self._backend = self._create_backend()

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(
            f"SemanticCache initialized: backend={self.config.backend}, "
            f"ttl={self.config.ttl_seconds}s, max={self.config.max_entries}"
        )

    def _create_backend(self) -> CacheBackend:
        """Create the appropriate backend based on config."""
        if self.config.backend == "memory":
            return MemoryBackend(max_entries=self.config.max_entries)
        elif self.config.backend == "sqlite":
            # Import lazily to avoid dependency if not used
            from .sqlite_backend import SQLiteBackend

            return SQLiteBackend(
                path=self.config.sqlite_path,
                max_entries=self.config.max_entries,
            )
        elif self.config.backend == "redis":
            from .redis_backend import RedisBackend

            return RedisBackend(
                url=self.config.redis_url,
                prefix=self.config.redis_prefix,
                max_entries=self.config.max_entries,
            )
        else:
            logger.warning(f"Unknown backend '{self.config.backend}', using memory")
            return MemoryBackend(max_entries=self.config.max_entries)

    def create_key(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: str = "default",
        temperature: float = 0.7,
    ) -> str:
        """
        Create a semantic cache key.

        Args:
            prompt: User message/prompt
            system: System prompt (optional)
            model: Model identifier
            temperature: Sampling temperature

        Returns:
            Cache key (SHA256 hex)
        """
        return SemanticCacheKey.create(
            prompt=prompt,
            system=system,
            model=model,
            temperature=temperature,
            config=self.config,
        )

    async def get(self, key: str) -> Optional[str]:
        """
        Get cached response by key.

        Args:
            key: Cache key from create_key()

        Returns:
            Cached response string or None
        """
        if not self.config.enabled:
            return None

        start = time.perf_counter()

        try:
            entry = await self._backend.get(key)

            elapsed_ms = (time.perf_counter() - start) * 1000

            if entry:
                self.stats.hits += 1
                self.stats.total_hit_time_ms += elapsed_ms
                self.stats.estimated_tokens_saved += entry.tokens_saved

                logger.debug(f"Cache HIT: {key[:16]}... ({elapsed_ms:.2f}ms)")
                return entry.response
            else:
                self.stats.misses += 1
                self.stats.total_miss_time_ms += elapsed_ms

                logger.debug(f"Cache MISS: {key[:16]}... ({elapsed_ms:.2f}ms)")
                return None

        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Cache get error: {e}")
            return None

    async def set(
        self,
        key: str,
        response: str,
        model: str = "default",
        tokens_saved: int = 0,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Store response in cache.

        Args:
            key: Cache key from create_key()
            response: LLM response to cache
            model: Model identifier
            tokens_saved: Estimated tokens saved by caching
            ttl_seconds: Override default TTL

        Returns:
            True if stored successfully
        """
        if not self.config.enabled:
            return False

        try:
            ttl = ttl_seconds or self.config.ttl_seconds
            now = datetime.now(UTC)

            entry = CacheEntry(
                key=key,
                response=response,
                model=model,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl),
                tokens_saved=tokens_saved,
            )

            # Async write if configured
            if self.config.async_writes:
                asyncio.create_task(self._async_set(entry))
                return True
            else:
                return await self._backend.set(entry)

        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Cache set error: {e}")
            return False

    async def _async_set(self, entry: CacheEntry) -> None:
        """Async cache write (fire and forget)."""
        try:
            old_size = await self._backend.size()
            await self._backend.set(entry)
            new_size = await self._backend.size()

            self.stats.sets += 1
            self.stats.current_entries = new_size

            if new_size <= old_size and old_size >= self.config.max_entries:
                self.stats.evictions += 1

        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Async cache set error: {e}")

    async def delete(self, key: str) -> bool:
        """Delete entry by key."""
        try:
            result = await self._backend.delete(key)
            if result:
                self.stats.current_entries = await self._backend.size()
            return result
        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Cache delete error: {e}")
            return False

    async def clear(self) -> int:
        """Clear all cache entries."""
        try:
            count = await self._backend.clear()
            self.stats.current_entries = 0
            logger.info(f"Cache cleared: {count} entries removed")
            return count
        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Cache clear error: {e}")
            return 0

    async def cleanup(self) -> int:
        """Remove expired entries."""
        try:
            count = await self._backend.cleanup_expired()
            self.stats.expirations += count
            self.stats.current_entries = await self._backend.size()

            if count > 0:
                logger.debug(f"Cache cleanup: {count} expired entries removed")

            return count
        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Cache cleanup error: {e}")
            return 0

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self.stats

    def reset_stats(self) -> None:
        """Reset statistics (keeps entries)."""
        self.stats = CacheStats(max_entries=self.config.max_entries)

    async def start_cleanup_task(self, interval_seconds: int = 300) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is not None:
            return

        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_seconds)
                await self.cleanup()

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Cache cleanup task started (interval={interval_seconds}s)")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Cache cleanup task stopped")

    async def __aenter__(self) -> SemanticCache:
        """Async context manager entry."""
        await self.start_cleanup_task()
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.stop_cleanup_task()


# =============================================================================
# Vector Semantic Cache (Embedding-based)
# =============================================================================


@dataclass
class VectorCacheConfig:
    """Configuration for vector-based semantic cache."""

    enabled: bool = True
    ttl_seconds: int = 3600
    max_entries: int = 10000
    backend: str = "memory"  # memory, sqlite
    sqlite_path: Optional[str] = None
    similarity_threshold: float = 0.85
    async_writes: bool = True

    def __post_init__(self) -> None:
        if self.sqlite_path is None:
            self.sqlite_path = ".cache/vector_cache.db"


@dataclass
class VectorCacheEntry:
    """A cached response with embedding."""

    query: str
    response: str
    embedding: List[float]
    model: str
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
    last_accessed: Optional[datetime] = None
    tokens_saved: int = 0

    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    def touch(self) -> None:
        self.last_accessed = datetime.now(UTC)
        self.hit_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "response": self.response,
            "embedding": self.embedding,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "hit_count": self.hit_count,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "tokens_saved": self.tokens_saved,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VectorCacheEntry:
        return cls(
            query=data["query"],
            response=data["response"],
            embedding=data["embedding"],
            model=data["model"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            hit_count=data.get("hit_count", 0),
            last_accessed=(
                datetime.fromisoformat(data["last_accessed"])
                if data.get("last_accessed")
                else None
            ),
            tokens_saved=data.get("tokens_saved", 0),
        )


class VectorMemoryBackend:
    """In-memory vector backend with simple LRU eviction."""

    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._entries: List[VectorCacheEntry] = []

    async def add(self, entry: VectorCacheEntry) -> bool:
        self._entries.append(entry)
        while len(self._entries) > self.max_entries:
            self._entries.pop(0)
        return True

    async def find_similar(
        self, embedding: List[float], threshold: float
    ) -> Optional[Tuple[VectorCacheEntry, float]]:
        best_index = None
        best_similarity = 0.0

        for idx, entry in enumerate(self._entries):
            if entry.is_expired():
                continue
            similarity = _cosine_similarity(embedding, entry.embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_index = idx

        if best_index is None or best_similarity < threshold:
            return None

        entry = self._entries[best_index]
        entry.touch()
        # LRU: move to end
        self._entries.append(self._entries.pop(best_index))
        return entry, best_similarity

    async def size(self) -> int:
        return len(self._entries)

    async def clear(self) -> int:
        count = len(self._entries)
        self._entries.clear()
        return count

    async def cleanup_expired(self) -> int:
        before = len(self._entries)
        self._entries = [e for e in self._entries if not e.is_expired()]
        return before - len(self._entries)


class VectorSQLiteBackend:
    """SQLite-backed vector cache."""

    def __init__(self, path: str, max_entries: int = 10000):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vector_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                embedding TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                tokens_saved INTEGER DEFAULT 0
            )
            """
        )
        self._conn.commit()

    async def add(self, entry: VectorCacheEntry) -> bool:
        self._conn.execute(
            """
            INSERT INTO vector_cache
                (query, response, embedding, model, created_at, expires_at,
                 hit_count, last_accessed, tokens_saved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.query,
                entry.response,
                json.dumps(entry.embedding),
                entry.model,
                entry.created_at.isoformat(),
                entry.expires_at.isoformat(),
                entry.hit_count,
                entry.last_accessed.isoformat() if entry.last_accessed else None,
                entry.tokens_saved,
            ),
        )
        self._conn.commit()
        await self._evict_if_needed()
        return True

    async def _evict_if_needed(self) -> None:
        cur = self._conn.execute("SELECT COUNT(*) FROM vector_cache")
        count = cur.fetchone()[0]
        if count <= self.max_entries:
            return
        to_remove = count - self.max_entries
        self._conn.execute(
            """
            DELETE FROM vector_cache
            WHERE id IN (
                SELECT id FROM vector_cache
                ORDER BY created_at ASC
                LIMIT ?
            )
            """,
            (to_remove,),
        )
        self._conn.commit()

    async def find_similar(
        self, embedding: List[float], threshold: float
    ) -> Optional[Tuple[VectorCacheEntry, float]]:
        rows = self._conn.execute("SELECT * FROM vector_cache").fetchall()
        best_row = None
        best_similarity = 0.0
        now = datetime.now(UTC)

        for row in rows:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at <= now:
                continue
            entry_embedding = json.loads(row["embedding"])
            similarity = _cosine_similarity(embedding, entry_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_row = row

        if best_row is None or best_similarity < threshold:
            return None

        entry = VectorCacheEntry(
            query=best_row["query"],
            response=best_row["response"],
            embedding=json.loads(best_row["embedding"]),
            model=best_row["model"],
            created_at=datetime.fromisoformat(best_row["created_at"]),
            expires_at=datetime.fromisoformat(best_row["expires_at"]),
            hit_count=best_row["hit_count"],
            last_accessed=(
                datetime.fromisoformat(best_row["last_accessed"])
                if best_row["last_accessed"]
                else None
            ),
            tokens_saved=best_row["tokens_saved"],
        )
        entry.touch()
        self._conn.execute(
            "UPDATE vector_cache SET hit_count = ?, last_accessed = ? WHERE id = ?",
            (
                entry.hit_count,
                entry.last_accessed.isoformat() if entry.last_accessed else None,
                best_row["id"],
            ),
        )
        self._conn.commit()
        return entry, best_similarity

    async def size(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM vector_cache")
        return cur.fetchone()[0]

    async def clear(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM vector_cache")
        count = cur.fetchone()[0]
        self._conn.execute("DELETE FROM vector_cache")
        self._conn.commit()
        return count

    async def cleanup_expired(self) -> int:
        now = datetime.now(UTC).isoformat()
        cur = self._conn.execute(
            "DELETE FROM vector_cache WHERE expires_at < ?", (now,)
        )
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()


class VectorSemanticCache:
    """Embedding-based semantic cache."""

    def __init__(self, config: Optional[VectorCacheConfig] = None):
        self.config = config or VectorCacheConfig()
        self.stats = CacheStats(max_entries=self.config.max_entries)
        self._backend = self._create_backend()
        try:
            from agentic_brain.memory.unified import SimpleHashEmbedding

            self._embedder = SimpleHashEmbedding()
        except Exception:
            self._embedder = None

    def _create_backend(self):
        if self.config.backend == "sqlite":
            return VectorSQLiteBackend(
                path=self.config.sqlite_path,
                max_entries=self.config.max_entries,
            )
        return VectorMemoryBackend(max_entries=self.config.max_entries)

    async def get(self, query: str) -> Optional[str]:
        if not self.config.enabled:
            return None

        if self._embedder is None:
            return None

        embedding = self._embedder.embed(query)
        result = await self._backend.find_similar(
            embedding, self.config.similarity_threshold
        )
        if result is None:
            self.stats.misses += 1
            return None

        entry, _similarity = result
        self.stats.hits += 1
        self.stats.estimated_tokens_saved += entry.tokens_saved
        return entry.response

    async def set(
        self, query: str, response: str, model: str = "default", tokens_saved: int = 0
    ) -> bool:
        if not self.config.enabled:
            return False

        if self._embedder is None:
            return False

        now = datetime.now(UTC)
        embedding = self._embedder.embed(query)
        entry = VectorCacheEntry(
            query=query,
            response=response,
            embedding=embedding,
            model=model,
            created_at=now,
            expires_at=now + timedelta(seconds=self.config.ttl_seconds),
            tokens_saved=tokens_saved,
        )

        if self.config.async_writes:
            asyncio.create_task(self._async_add(entry))
            return True
        return await self._add_entry(entry)

    async def _add_entry(self, entry: VectorCacheEntry) -> bool:
        old_size = await self._backend.size()
        await self._backend.add(entry)
        new_size = await self._backend.size()
        self.stats.sets += 1
        self.stats.current_entries = new_size
        if new_size <= old_size and old_size >= self.config.max_entries:
            self.stats.evictions += 1
        return True

    async def _async_add(self, entry: VectorCacheEntry) -> None:
        try:
            await self._add_entry(entry)
        except Exception:
            self.stats.errors += 1

    def set_similarity_threshold(self, threshold: float) -> None:
        self.config.similarity_threshold = threshold

    async def clear(self) -> int:
        count = await self._backend.clear()
        self.stats.current_entries = 0
        return count

    def get_stats(self) -> CacheStats:
        return self.stats

    async def __aenter__(self) -> VectorSemanticCache:
        return self

    async def __aexit__(self, *args) -> None:
        return None
