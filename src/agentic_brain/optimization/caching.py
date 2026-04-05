"""Caching helpers for embeddings and Neo4j queries."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Iterable


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _stable_params(params: dict[str, Any] | None) -> str:
    return json.dumps(params or {}, sort_keys=True, separators=(",", ":"), default=str)


def _cache_key(prefix: str, *parts: str) -> str:
    payload = "\u241f".join(parts)
    return f"{prefix}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl_seconds: float | None = None
    hits: int = 0

    def expired(self, now: float | None = None) -> bool:
        if self.ttl_seconds is None:
            return False
        now = now or time.time()
        return now - self.created_at > self.ttl_seconds


class LRUCache:
    """Thread-safe LRU cache with optional TTL."""

    def __init__(self, max_size: int = 1024, ttl_seconds: float | None = None) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expired():
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            entry.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
            self._items[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl_seconds=self.ttl_seconds if ttl_seconds is None else ttl_seconds,
            )
            while len(self._items) > self.max_size:
                self._items.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        with self._lock:
            return self._items.pop(key, None) is not None

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [key for key in self._items if key.startswith(prefix)]
            for key in keys:
                self._items.pop(key, None)
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._items),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "keys": list(self._items.keys()),
            }


class CachedEmbeddingProvider:
    """Wrap an embedding provider with an LRU cache."""

    def __init__(
        self,
        provider: Any,
        *,
        cache: LRUCache | None = None,
        model_name: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self.provider = provider
        self.cache = cache or LRUCache(max_size=2048, ttl_seconds=3600)
        self.model_name = (
            model_name
            or getattr(provider, "model_name", None)
            or getattr(provider, "model", provider.__class__.__name__)
        )
        self.dimensions = dimensions or int(getattr(provider, "dimensions", 0) or 0)

    def _key(self, text: str) -> str:
        return _cache_key(
            f"embedding:{self.model_name}:{self.dimensions}",
            self.model_name,
            str(self.dimensions),
            _normalize_text(text),
        )

    def embed(self, text: str) -> list[float]:
        key = self._key(text)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        embedding = self.provider.embed(text)
        self.cache.set(key, embedding)
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float] | None] = [None] * len(texts)
        missing: list[tuple[int, str]] = []

        for index, text in enumerate(texts):
            key = self._key(text)
            cached = self.cache.get(key)
            if cached is None:
                missing.append((index, text))
            else:
                results[index] = cached

        if missing:
            batch_texts = [text for _, text in missing]
            if hasattr(self.provider, "embed_batch"):
                embeddings = self.provider.embed_batch(batch_texts)
            else:
                embeddings = [self.provider.embed(text) for text in batch_texts]

            for (index, text), embedding in zip(missing, embeddings, strict=False):
                self.cache.set(self._key(text), embedding)
                results[index] = embedding

        return [embedding or [] for embedding in results]

    def invalidate(self, text: str) -> bool:
        return self.cache.invalidate(self._key(text))

    def invalidate_many(self, texts: Iterable[str]) -> int:
        removed = 0
        for text in texts:
            if self.invalidate(text):
                removed += 1
        return removed

    def clear(self) -> None:
        self.cache.clear()


class QueryResultCache:
    """Cache for arbitrary query responses."""

    def __init__(
        self,
        *,
        cache: LRUCache | None = None,
        namespace: str = "query",
    ) -> None:
        self.cache = cache or LRUCache(max_size=2048, ttl_seconds=300)
        self.namespace = namespace

    def key(self, query: str, params: dict[str, Any] | None = None) -> str:
        return _cache_key(
            self.namespace, _normalize_text(query), _stable_params(params)
        )

    def get(self, query: str, params: dict[str, Any] | None = None) -> Any | None:
        return self.cache.get(self.key(query, params))

    def set(
        self,
        query: str,
        value: Any,
        params: dict[str, Any] | None = None,
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        self.cache.set(self.key(query, params), value, ttl_seconds=ttl_seconds)

    def invalidate(self, query: str, params: dict[str, Any] | None = None) -> bool:
        return self.cache.invalidate(self.key(query, params))

    def invalidate_prefix(self, prefix: str) -> int:
        return self.cache.invalidate_prefix(prefix)

    def clear(self) -> None:
        self.cache.clear()


class GraphQueryCache(QueryResultCache):
    """Cache for Neo4j graph queries."""

    def __init__(
        self,
        *,
        cache: LRUCache | None = None,
        database: str = "neo4j",
    ) -> None:
        super().__init__(cache=cache, namespace=f"graph:{database}")
        self.database = database

    def key(self, query: str, params: dict[str, Any] | None = None) -> str:
        return _cache_key(
            self.namespace,
            self.database,
            _normalize_text(query),
            _stable_params(params),
        )
