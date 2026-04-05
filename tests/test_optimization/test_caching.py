# SPDX-License-Identifier: Apache-2.0
"""Performance-oriented tests for caching helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from agentic_brain.optimization.caching import (
    CachedEmbeddingProvider,
    GraphQueryCache,
    LRUCache,
    QueryResultCache,
)


@dataclass
class FakeEmbeddingProvider:
    calls: int = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        return [float(len(text))]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[float(len(text))] for text in texts]


def test_lru_cache_get_and_set():
    cache = LRUCache(max_size=2)
    cache.set("a", 1)
    cache.set("b", 2)

    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_lru_cache_evicts_least_recently_used():
    cache = LRUCache(max_size=2)
    cache.set("a", 1)
    cache.set("b", 2)
    _ = cache.get("a")
    cache.set("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_lru_cache_invalidate_key():
    cache = LRUCache(max_size=2)
    cache.set("a", 1)

    assert cache.invalidate("a") is True
    assert cache.get("a") is None


def test_lru_cache_invalidate_prefix():
    cache = LRUCache(max_size=4)
    cache.set("query:1", 1)
    cache.set("query:2", 2)
    cache.set("other:3", 3)

    assert cache.invalidate_prefix("query:") == 2
    assert cache.get("query:1") is None
    assert cache.get("query:2") is None
    assert cache.get("other:3") == 3


def test_lru_cache_ttl_expires():
    cache = LRUCache(max_size=2, ttl_seconds=0.01)
    cache.set("a", 1)
    time.sleep(0.02)

    assert cache.get("a") is None


@pytest.mark.parametrize(
    "params_a, params_b",
    [
        ({"x": 1, "y": 2}, {"y": 2, "x": 1}),
        ({"limit": 5, "offset": 10}, {"offset": 10, "limit": 5}),
    ],
)
def test_query_cache_key_is_stable(params_a, params_b):
    cache = QueryResultCache()

    assert cache.key("MATCH (n) RETURN n", params_a) == cache.key(
        "MATCH (n) RETURN n", params_b
    )


def test_query_result_cache_round_trip():
    cache = QueryResultCache()
    payload = [{"id": 1}]
    cache.set("MATCH (n) RETURN n", payload, {"limit": 1})

    assert cache.get("MATCH (n) RETURN n", {"limit": 1}) == payload


def test_query_result_cache_invalidation():
    cache = QueryResultCache()
    cache.set("MATCH (n) RETURN n", [1], {"limit": 1})

    assert cache.invalidate("MATCH (n) RETURN n", {"limit": 1}) is True
    assert cache.get("MATCH (n) RETURN n", {"limit": 1}) is None


def test_graph_query_cache_uses_database_namespace():
    cache_a = GraphQueryCache(database="neo4j")
    cache_b = GraphQueryCache(database="analytics")

    assert cache_a.key("MATCH (n) RETURN n", {"limit": 1}) != cache_b.key(
        "MATCH (n) RETURN n", {"limit": 1}
    )


def test_graph_query_cache_round_trip():
    cache = GraphQueryCache(database="neo4j")
    payload = [{"name": "node"}]
    cache.set("MATCH (n) RETURN n", payload, {"limit": 2})

    assert cache.get("MATCH (n) RETURN n", {"limit": 2}) == payload


def test_cached_embedding_provider_hits_cache():
    provider = FakeEmbeddingProvider()
    cached = CachedEmbeddingProvider(provider)

    first = cached.embed("hello world")
    second = cached.embed("hello world")

    assert first == second
    assert provider.calls == 1


def test_cached_embedding_provider_batch_hits_cache():
    provider = FakeEmbeddingProvider()
    cached = CachedEmbeddingProvider(provider)

    first = cached.embed_batch(["a", "bb", "ccc"])
    second = cached.embed_batch(["a", "bb", "ccc"])

    assert first == second
    assert provider.calls == 1


def test_cached_embedding_provider_partial_batch_only_recomputes_misses():
    provider = FakeEmbeddingProvider()
    cached = CachedEmbeddingProvider(provider)

    cached.embed("persisted")
    provider.calls = 0
    cached.embed_batch(["persisted", "new"])

    assert provider.calls == 1


def test_cached_embedding_provider_invalidate_text():
    provider = FakeEmbeddingProvider()
    cached = CachedEmbeddingProvider(provider)

    cached.embed("invalidate me")
    assert cached.invalidate("invalidate me") is True
    cached.embed("invalidate me")

    assert provider.calls == 2


def test_cached_embedding_provider_clear():
    provider = FakeEmbeddingProvider()
    cached = CachedEmbeddingProvider(provider)

    cached.embed("a")
    cached.clear()

    assert cached.cache.stats()["size"] == 0
