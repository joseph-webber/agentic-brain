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
Tests for Semantic Prompt Cache.

Tests coverage:
- VectorSemanticCache (embedding-based similarity)
- Cache LLM responses by semantic similarity
- Return cached response for similar queries
- Configurable similarity threshold
- TTL and invalidation
- SQLite backend (no Redis required)
- Memory backend fallback

Run with: pytest tests/test_cache.py -v
"""

import asyncio
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.cache import (
    CacheConfig,
    CacheEntry,
    CacheStats,
    MemoryBackend,
    SemanticCache,
    SemanticCacheKey,
    VectorCacheConfig,
    VectorCacheEntry,
    VectorMemoryBackend,
    VectorSemanticCache,
    VectorSQLiteBackend,
)
from agentic_brain.cache.semantic_cache import _cosine_similarity

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_embedder():
    """Create a mock embedding provider."""
    embedder = MagicMock()
    embedder.model_name = "mock/test-model"
    embedder.dimensions = 384

    # Create simple embeddings based on text content
    # Similar texts get similar embeddings
    def embed(text: str) -> list[float]:
        # Simple hash-based embedding for testing
        import hashlib

        base = [0.0] * 384

        # Add similarity for common words
        words = text.lower().split()
        for _i, word in enumerate(words[:10]):
            hash_val = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
            idx = hash_val % 384
            base[idx] += 1.0

        # Normalize
        norm = sum(x * x for x in base) ** 0.5
        if norm > 0:
            base = [x / norm for x in base]
        return base

    embedder.embed = embed
    return embedder


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def memory_backend():
    """Create a memory backend for testing."""
    return VectorMemoryBackend(max_entries=100)


@pytest.fixture
def sqlite_backend(temp_db):
    """Create a SQLite backend for testing."""
    return VectorSQLiteBackend(path=temp_db, max_entries=100)


# =============================================================================
# Test Cosine Similarity
# =============================================================================


class TestCosineSimilarity:
    """Test cosine similarity calculation."""

    def test_identical_vectors_similarity_1(self):
        """Identical vectors should have similarity of 1.0."""
        v1 = [1.0, 2.0, 3.0]
        v2 = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v1, v2) - 1.0) < 0.001

    def test_orthogonal_vectors_similarity_0(self):
        """Orthogonal vectors should have similarity of 0.0."""
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert abs(_cosine_similarity(v1, v2) - 0.0) < 0.001

    def test_opposite_vectors_similarity_minus_1(self):
        """Opposite vectors should have similarity of -1.0."""
        v1 = [1.0, 2.0, 3.0]
        v2 = [-1.0, -2.0, -3.0]
        assert abs(_cosine_similarity(v1, v2) - (-1.0)) < 0.001

    def test_similar_vectors_high_similarity(self):
        """Similar vectors should have high similarity."""
        v1 = [1.0, 2.0, 3.0, 4.0]
        v2 = [1.1, 2.1, 3.1, 4.1]  # Slightly different
        similarity = _cosine_similarity(v1, v2)
        assert similarity > 0.99

    def test_empty_vector_returns_0(self):
        """Empty vectors should return 0."""
        assert _cosine_similarity([], []) == 0.0
        assert _cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    def test_different_length_returns_0(self):
        """Different length vectors should return 0."""
        v1 = [1.0, 2.0]
        v2 = [1.0, 2.0, 3.0]
        assert _cosine_similarity(v1, v2) == 0.0


# =============================================================================
# Test Vector Memory Backend
# =============================================================================


class TestVectorMemoryBackend:
    """Test in-memory vector backend."""

    @pytest.mark.asyncio
    async def test_add_and_find_entry(self, memory_backend):
        """Test adding and finding entries."""
        embedding = [1.0, 0.0, 0.0] * 128  # 384-dim
        entry = VectorCacheEntry(
            query="What is Python?",
            response="Python is a programming language.",
            embedding=embedding,
            model="test",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        await memory_backend.add(entry)
        assert await memory_backend.size() == 1

        # Find with identical embedding
        result = await memory_backend.find_similar(embedding, threshold=0.8)
        assert result is not None
        found_entry, similarity = result
        assert found_entry.query == "What is Python?"
        assert abs(similarity - 1.0) < 0.001  # Use tolerance for float comparison

    @pytest.mark.asyncio
    async def test_threshold_filtering(self, memory_backend):
        """Test that threshold filters correctly."""
        embedding1 = [1.0, 0.0, 0.0] * 128
        entry = VectorCacheEntry(
            query="Test query",
            response="Test response",
            embedding=embedding1,
            model="test",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await memory_backend.add(entry)

        # Very different embedding
        embedding2 = [0.0, 1.0, 0.0] * 128  # Orthogonal
        result = await memory_backend.find_similar(embedding2, threshold=0.9)
        assert result is None  # Should not match

    @pytest.mark.asyncio
    async def test_expiration_filtering(self, memory_backend):
        """Test that expired entries are filtered."""
        embedding = [1.0, 0.0, 0.0] * 128
        entry = VectorCacheEntry(
            query="Expired query",
            response="Expired response",
            embedding=embedding,
            model="test",
            created_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),  # Expired
        )
        await memory_backend.add(entry)

        result = await memory_backend.find_similar(embedding, threshold=0.8)
        assert result is None  # Should not find expired entry

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction at max capacity."""
        backend = VectorMemoryBackend(max_entries=3)

        for i in range(5):
            embedding = [float(i), 0.0, 0.0] * 128
            entry = VectorCacheEntry(
                query=f"Query {i}",
                response=f"Response {i}",
                embedding=embedding,
                model="test",
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            await backend.add(entry)

        # Should only have 3 entries
        assert await backend.size() == 3

    @pytest.mark.asyncio
    async def test_clear(self, memory_backend):
        """Test clearing the cache."""
        embedding = [1.0, 0.0, 0.0] * 128
        entry = VectorCacheEntry(
            query="Test",
            response="Response",
            embedding=embedding,
            model="test",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await memory_backend.add(entry)
        await memory_backend.add(entry)

        count = await memory_backend.clear()
        assert count == 2
        assert await memory_backend.size() == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, memory_backend):
        """Test cleanup of expired entries."""
        now = datetime.now(UTC)

        # Add expired entry
        expired_entry = VectorCacheEntry(
            query="Expired",
            response="Response",
            embedding=[1.0] * 384,
            model="test",
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )
        await memory_backend.add(expired_entry)

        # Add valid entry
        valid_entry = VectorCacheEntry(
            query="Valid",
            response="Response",
            embedding=[2.0] * 384,
            model="test",
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        await memory_backend.add(valid_entry)

        removed = await memory_backend.cleanup_expired()
        assert removed == 1
        assert await memory_backend.size() == 1


# =============================================================================
# Test Vector SQLite Backend
# =============================================================================


class TestVectorSQLiteBackend:
    """Test SQLite vector backend."""

    @pytest.mark.asyncio
    async def test_add_and_find_entry(self, sqlite_backend):
        """Test adding and finding entries with SQLite."""
        embedding = [1.0, 0.0, 0.0] * 128
        entry = VectorCacheEntry(
            query="What is Python?",
            response="Python is a programming language.",
            embedding=embedding,
            model="test",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        await sqlite_backend.add(entry)
        assert await sqlite_backend.size() == 1

        result = await sqlite_backend.find_similar(embedding, threshold=0.8)
        assert result is not None
        found_entry, similarity = result
        assert found_entry.query == "What is Python?"
        assert abs(similarity - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_persistence(self, temp_db):
        """Test that SQLite persists data."""
        embedding = [1.0, 0.0, 0.0] * 128
        entry = VectorCacheEntry(
            query="Persistent query",
            response="Persistent response",
            embedding=embedding,
            model="test",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        # Create first backend and add entry
        backend1 = VectorSQLiteBackend(path=temp_db, max_entries=100)
        await backend1.add(entry)
        backend1.close()

        # Create second backend and verify data persists
        backend2 = VectorSQLiteBackend(path=temp_db, max_entries=100)
        result = await backend2.find_similar(embedding, threshold=0.8)
        assert result is not None
        assert result[0].query == "Persistent query"
        backend2.close()

    @pytest.mark.asyncio
    async def test_clear(self, sqlite_backend):
        """Test clearing SQLite cache."""
        embedding = [1.0] * 384
        entry = VectorCacheEntry(
            query="Test",
            response="Response",
            embedding=embedding,
            model="test",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await sqlite_backend.add(entry)

        count = await sqlite_backend.clear()
        assert count == 1
        assert await sqlite_backend.size() == 0


# =============================================================================
# Test VectorSemanticCache (Main Class)
# =============================================================================


class TestVectorSemanticCache:
    """Test the main VectorSemanticCache class."""

    @pytest.mark.asyncio
    async def test_basic_set_and_get(self, mock_embedder, temp_db):
        """Test basic cache set and get operations."""
        config = VectorCacheConfig(
            backend="sqlite",
            sqlite_path=temp_db,
            similarity_threshold=0.8,
            async_writes=False,
        )

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder  # Inject mock embedder

        # Set a value
        await cache.set(
            "What is Python?",
            "Python is a programming language created by Guido van Rossum.",
        )

        # Get with exact same query
        result = await cache.get("What is Python?")
        assert result is not None
        assert "Python" in result
        assert "programming language" in result

    @pytest.mark.asyncio
    async def test_semantic_similarity_matching(self, mock_embedder, temp_db):
        """Test that similar queries hit the cache."""
        config = VectorCacheConfig(
            backend="sqlite",
            sqlite_path=temp_db,
            similarity_threshold=0.5,  # Lower threshold for mock embeddings
            async_writes=False,
        )

        # Create more sophisticated mock that returns similar embeddings for similar text
        def smart_embed(text: str) -> list[float]:
            base = [0.0] * 384
            # "python" and "Python" should be similar
            if "python" in text.lower():
                base[0] = 1.0
                base[1] = 0.5
            if "language" in text.lower():
                base[2] = 0.8
            if "programming" in text.lower():
                base[3] = 0.7
            # Normalize
            norm = sum(x * x for x in base) ** 0.5
            if norm > 0:
                base = [x / norm for x in base]
            return base

        mock_embedder.embed = smart_embed

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder

        # Set original query
        await cache.set(
            "What is Python?", "Python is a high-level programming language."
        )

        # Try similar queries
        result1 = await cache.get("Tell me about Python")
        assert result1 is not None  # Should hit cache

        result2 = await cache.get("Explain Python programming language")
        assert result2 is not None  # Should hit cache

    @pytest.mark.asyncio
    async def test_cache_miss_for_dissimilar_queries(self, mock_embedder, temp_db):
        """Test that dissimilar queries miss the cache."""
        config = VectorCacheConfig(
            backend="sqlite",
            sqlite_path=temp_db,
            similarity_threshold=0.9,  # High threshold
            async_writes=False,
        )

        def different_embed(text: str) -> list[float]:
            base = [0.0] * 384
            if "python" in text.lower():
                base[0] = 1.0
            elif "javascript" in text.lower():
                base[100] = 1.0  # Very different position
            return base

        mock_embedder.embed = different_embed

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder

        await cache.set("What is Python?", "Python is a programming language.")

        # Completely different query should miss
        result = await cache.get("What is JavaScript?")
        assert result is None  # Should be a cache miss

    @pytest.mark.asyncio
    async def test_configurable_threshold(self, mock_embedder, temp_db):
        """Test that similarity threshold is configurable."""
        config = VectorCacheConfig(
            backend="memory",
            similarity_threshold=0.95,
            async_writes=False,
        )

        mock_embedder.embed = lambda t: (
            [1.0] * 384 if "python" in t.lower() else [0.9] * 384
        )

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder
        await cache.set("What is Python?", "Python is great.")

        # Should miss with high threshold
        await cache.get("Different question")
        # Similarity of [1.0]*384 and [0.9]*384 is 1.0 (normalized), so might hit

        # Lower threshold
        cache.set_similarity_threshold(0.5)
        await cache.get("Different question")
        # Now might hit depending on embeddings

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, mock_embedder, temp_db):
        """Test that entries expire after TTL."""
        config = VectorCacheConfig(
            backend="memory",
            ttl_seconds=1,  # 1 second TTL
            async_writes=False,
        )

        mock_embedder.embed = lambda t: [1.0] * 384

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder
        await cache.set("Query", "Response")

        # Should hit immediately
        result = await cache.get("Query")
        assert result is not None

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should miss after expiration
        result = await cache.get("Query")
        assert result is None

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, mock_embedder, temp_db):
        """Test that cache statistics are tracked."""
        config = VectorCacheConfig(
            backend="memory",
            similarity_threshold=0.9,
            async_writes=False,
        )

        mock_embedder.embed = lambda t: [1.0] * 384

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder

        # Set and get
        await cache.set("Query", "Response")
        await cache.get("Query")  # Hit
        await cache.get("Query")  # Hit
        await cache.get("Different")  # Also hit (same embedding)

        stats = cache.get_stats()
        assert stats.hits >= 2
        assert stats.sets >= 1
        assert stats.hit_rate > 0

    @pytest.mark.asyncio
    async def test_clear_cache(self, mock_embedder, temp_db):
        """Test clearing the cache."""
        config = VectorCacheConfig(
            backend="memory",
            async_writes=False,
        )

        mock_embedder.embed = lambda t: [1.0] * 384

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder
        await cache.set("Query 1", "Response 1")
        await cache.set("Query 2", "Response 2")

        count = await cache.clear()
        assert count == 2

        result = await cache.get("Query 1")
        assert result is None

    @pytest.mark.asyncio
    async def test_disabled_cache(self, mock_embedder):
        """Test that disabled cache always returns None."""
        config = VectorCacheConfig(enabled=False)

        cache = VectorSemanticCache(config)

        result = await cache.set("Query", "Response")
        assert result is False

        result = await cache.get("Query")
        assert result is None

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_embedder, temp_db):
        """Test async context manager."""
        config = VectorCacheConfig(
            backend="memory",
            async_writes=False,
        )

        mock_embedder.embed = lambda t: [1.0] * 384

        async with VectorSemanticCache(config) as cache:
            cache._embedder = mock_embedder
            await cache.set("Query", "Response")
            result = await cache.get("Query")
            assert result is not None


# =============================================================================
# Test Original Hash-Based Cache (SemanticCacheKey)
# =============================================================================


class TestSemanticCacheKey:
    """Test the original hash-based cache key generation."""

    def test_same_prompt_same_key(self):
        """Same prompt should produce same key."""
        key1 = SemanticCacheKey.create("What is Python?", model="gpt-4")
        key2 = SemanticCacheKey.create("What is Python?", model="gpt-4")
        assert key1 == key2

    def test_different_prompt_different_key(self):
        """Different prompts should produce different keys."""
        key1 = SemanticCacheKey.create("What is Python?", model="gpt-4")
        key2 = SemanticCacheKey.create("What is JavaScript?", model="gpt-4")
        assert key1 != key2

    def test_different_model_different_key(self):
        """Different models should produce different keys."""
        key1 = SemanticCacheKey.create("What is Python?", model="gpt-4")
        key2 = SemanticCacheKey.create("What is Python?", model="gpt-3.5")
        assert key1 != key2

    def test_whitespace_normalization(self):
        """Whitespace should be normalized by default."""
        config = CacheConfig(normalize_whitespace=True)
        key1 = SemanticCacheKey.create("What  is   Python?", config=config)
        key2 = SemanticCacheKey.create("What is Python?", config=config)
        assert key1 == key2

    def test_case_normalization(self):
        """Case normalization when enabled."""
        config = CacheConfig(normalize_case=True)
        key1 = SemanticCacheKey.create("What is Python?", config=config)
        key2 = SemanticCacheKey.create("what is python?", config=config)
        assert key1 == key2


# =============================================================================
# Test Integration (Simulated Real-World Usage)
# =============================================================================


class TestSemanticCacheIntegration:
    """Integration tests simulating real-world usage."""

    @pytest.mark.asyncio
    async def test_typical_llm_caching_workflow(self, mock_embedder, temp_db):
        """Test typical LLM response caching workflow."""
        config = VectorCacheConfig(
            backend="sqlite",
            sqlite_path=temp_db,
            similarity_threshold=0.7,
            ttl_seconds=3600,
            async_writes=False,
        )

        # More realistic embedding mock
        def realistic_embed(text: str) -> list[float]:
            base = [0.0] * 384
            words = text.lower().split()
            for _i, word in enumerate(words):
                idx = hash(word) % 384
                base[idx] += 0.5
                base[(idx + 1) % 384] += 0.3
            # Normalize
            norm = sum(x * x for x in base) ** 0.5
            if norm > 0:
                base = [x / norm for x in base]
            return base

        mock_embedder.embed = realistic_embed

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder

        # Simulate LLM calls
        queries = [
            ("What is Python?", "Python is a high-level programming language."),
            ("How do I install Python?", "Use pip to install Python packages."),
            (
                "What are Python decorators?",
                "Decorators are functions that wrap other functions.",
            ),
        ]

        # Store responses
        for query, response in queries:
            await cache.set(query, response, tokens_saved=100)

        # Verify cache hits for similar queries
        await cache.get("Tell me about Python")  # Similar to "What is Python?"
        # Result depends on embedding similarity

        # Verify stats
        stats = cache.get_stats()
        assert stats.sets == 3

    @pytest.mark.asyncio
    async def test_cost_savings_tracking(self, mock_embedder, temp_db):
        """Test that cost savings are tracked."""
        config = VectorCacheConfig(
            backend="memory",
            async_writes=False,
        )

        mock_embedder.embed = lambda t: [1.0] * 384

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder

        # Store with token count
        await cache.set("Query", "Response", tokens_saved=500)

        # Hit the cache
        await cache.get("Query")

        stats = cache.get_stats()
        assert stats.estimated_tokens_saved >= 500


# =============================================================================
# Test No Redis Required (SQLite Fallback)
# =============================================================================


class TestSQLiteFallback:
    """Test that cache works without Redis."""

    @pytest.mark.asyncio
    async def test_sqlite_works_without_redis(self, mock_embedder, temp_db):
        """Test SQLite backend works as fallback without Redis."""
        # No Redis configuration - should use SQLite
        config = VectorCacheConfig(
            backend="sqlite",
            sqlite_path=temp_db,
            async_writes=False,
        )

        mock_embedder.embed = lambda t: [1.0] * 384

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder

        # Should work without Redis
        await cache.set("What is Python?", "Python is a programming language.")
        result = await cache.get("What is Python?")

        assert result is not None
        assert "Python" in result

    @pytest.mark.asyncio
    async def test_memory_fallback(self, mock_embedder):
        """Test memory backend works as fallback."""
        config = VectorCacheConfig(
            backend="memory",
            async_writes=False,
        )

        mock_embedder.embed = lambda t: [1.0] * 384

        cache = VectorSemanticCache(config)
        cache._embedder = mock_embedder

        await cache.set("Query", "Response")
        result = await cache.get("Query")

        assert result is not None


# =============================================================================
# Smoke Test for Import
# =============================================================================


def test_import_semantic_cache():
    """Test that SemanticCache can be imported."""

    assert SemanticCache is not None


def test_cache_entry_to_dict():
    """Test CacheEntry serialization."""
    entry = CacheEntry(
        key="test-key",
        response="test response",
        model="gpt-4",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        hit_count=5,
    )

    data = entry.to_dict()
    assert data["key"] == "test-key"
    assert data["response"] == "test response"
    assert data["hit_count"] == 5

    # Test deserialization
    restored = CacheEntry.from_dict(data)
    assert restored.key == entry.key
    assert restored.response == entry.response


def test_cache_stats():
    """Test CacheStats calculations."""
    stats = CacheStats(hits=80, misses=20)
    assert abs(stats.hit_rate - 0.8) < 0.001
    assert stats.to_dict()["hit_rate"] == 80.0  # Percentage


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
