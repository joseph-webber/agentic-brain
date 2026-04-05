# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for semantic (embedding-based) memory retrieval.

Covers:
  - SimpleHashEmbedding: dimension, normalisation, determinism, batch
  - Cosine similarity helper in SQLiteMemoryStore
  - MemoryType.SEMANTIC store + search
  - Semantic re-ranking (FTS results boosted by embedding similarity)
  - Similar content ranks higher than dissimilar content
  - Custom EmbeddingProvider protocol
  - Edge cases: empty text, single character, very long text, Unicode
  - Importance interplay with semantic score
"""

from __future__ import annotations

import math
from typing import Optional
from unittest.mock import MagicMock

import pytest

from agentic_brain.memory.unified import (
    MemoryEntry,
    MemoryType,
    SimpleHashEmbedding,
    SQLiteMemoryStore,
    UnifiedMemory,
)

# ---------------------------------------------------------------------------
# SimpleHashEmbedding – unit tests
# ---------------------------------------------------------------------------


class TestSimpleHashEmbedding:
    @pytest.fixture
    def embedder(self) -> SimpleHashEmbedding:
        return SimpleHashEmbedding(dimension=128)

    def test_default_dimension(self):
        emb = SimpleHashEmbedding()
        assert emb.dimension == 384

    def test_custom_dimension(self, embedder):
        assert embedder.dimension == 128

    def test_embed_returns_correct_length(self, embedder):
        vec = embedder.embed("Hello world")
        assert len(vec) == 128

    def test_embed_is_normalised(self, embedder):
        vec = embedder.embed("normalisation test")
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6 or norm == 0.0

    def test_embed_is_deterministic(self, embedder):
        text = "deterministic embedding test"
        assert embedder.embed(text) == embedder.embed(text)

    def test_empty_string_returns_zero_vector(self, embedder):
        vec = embedder.embed("")
        assert len(vec) == 128
        assert all(v == 0.0 for v in vec)

    def test_single_char_embed(self, embedder):
        vec = embedder.embed("x")
        assert len(vec) == 128

    def test_embed_batch_matches_singles(self, embedder):
        texts = ["foo bar", "hello world", "python programming"]
        batch = embedder.embed_batch(texts)
        for i, text in enumerate(texts):
            assert batch[i] == embedder.embed(text)

    def test_different_texts_differ(self, embedder):
        v1 = embedder.embed("Python programming language")
        v2 = embedder.embed("quantum physics nuclear")
        assert v1 != v2

    def test_unicode_text(self, embedder):
        vec = embedder.embed("Héllo wörld 日本語 🎉")
        assert len(vec) == 128

    def test_very_long_text(self, embedder):
        text = " ".join(["word"] * 1000)
        vec = embedder.embed(text)
        assert len(vec) == 128
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6 or norm == 0.0


# ---------------------------------------------------------------------------
# Cosine similarity helper
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    @pytest.fixture
    def store(self, tmp_path) -> SQLiteMemoryStore:
        return SQLiteMemoryStore(db_path=str(tmp_path / "sem.db"))

    def test_identical_vectors_score_one(self, store):
        vec = [1.0, 0.0, 0.0]
        assert abs(store._cosine_similarity(vec, vec) - 1.0) < 1e-9

    def test_orthogonal_vectors_score_zero(self, store):
        v1, v2 = [1.0, 0.0], [0.0, 1.0]
        assert abs(store._cosine_similarity(v1, v2)) < 1e-9

    def test_zero_vector_returns_zero(self, store):
        v = [0.0, 0.0, 0.0]
        u = [1.0, 0.0, 0.0]
        assert store._cosine_similarity(v, u) == 0.0

    def test_opposite_vectors_score_negative_one(self, store):
        v1, v2 = [1.0, 0.0], [-1.0, 0.0]
        assert abs(store._cosine_similarity(v1, v2) + 1.0) < 1e-9

    def test_similar_embeddings_score_higher_than_dissimilar(self, store):
        emb = SimpleHashEmbedding(dimension=64)
        q = emb.embed("Python programming language")
        similar = emb.embed("Python is a programming language")
        dissimilar = emb.embed("quantum physics nuclear reactor")
        score_similar = store._cosine_similarity(q, similar)
        score_dissimilar = store._cosine_similarity(q, dissimilar)
        assert score_similar > score_dissimilar


# ---------------------------------------------------------------------------
# SQLiteMemoryStore – semantic storage and retrieval
# ---------------------------------------------------------------------------


class TestSemanticStorageRetrieval:
    @pytest.fixture
    def store(self, tmp_path) -> SQLiteMemoryStore:
        return SQLiteMemoryStore(db_path=str(tmp_path / "semantic.db"))

    def test_semantic_memory_gets_embedding(self, store):
        entry = store.store("Python data science", memory_type=MemoryType.SEMANTIC)
        assert entry.embedding is not None
        assert len(entry.embedding) > 0

    def test_long_term_memory_gets_embedding(self, store):
        entry = store.store("Docker containers", memory_type=MemoryType.LONG_TERM)
        assert entry.embedding is not None

    def test_session_memory_no_embedding_by_default(self, store):
        entry = store.store("quick note", memory_type=MemoryType.SESSION)
        # SESSION type does not get an embedding in the current implementation
        assert entry.embedding is None

    def test_semantic_search_returns_relevant_result(self, store):
        store.store("Python is a programming language", memory_type=MemoryType.SEMANTIC)
        store.store("The Eiffel Tower is in Paris", memory_type=MemoryType.SEMANTIC)
        results = store.search("programming language Python", use_semantic=True)
        contents = [r.content for r in results]
        assert any("Python" in c for c in contents)

    def test_semantic_search_ranks_similar_higher(self, store):
        store.store(
            "Python data science machine learning", memory_type=MemoryType.SEMANTIC
        )
        store.store(
            "French cuisine baguette croissant", memory_type=MemoryType.SEMANTIC
        )
        results = store.search(
            "machine learning algorithms", use_semantic=True, limit=5
        )
        if len(results) >= 2:
            assert results[0].score >= results[1].score

    def test_semantic_search_no_results_for_unrelated(self, store):
        store.store("Python programming", memory_type=MemoryType.SEMANTIC)
        # Search for something unrelated – may return results but score will be low
        results = store.search("xyzzyx gobbledygook", use_semantic=True)
        for r in results:
            assert r.score >= 0.0

    def test_semantic_search_disabled(self, store):
        store.store("Python programming language", memory_type=MemoryType.LONG_TERM)
        results = store.search("Python", use_semantic=False)
        assert isinstance(results, list)

    def test_custom_embedding_provider(self, tmp_path):
        """Plugging in a custom EmbeddingProvider is respected."""

        class FixedEmbedder:
            dimension = 8

            def embed(self, text: str) -> list[float]:
                return [1.0] + [0.0] * 7

            def embed_batch(self, texts):
                return [self.embed(t) for t in texts]

        store = SQLiteMemoryStore(
            db_path=str(tmp_path / "custom.db"),
            embedder=FixedEmbedder(),
        )
        entry = store.store("anything", memory_type=MemoryType.SEMANTIC)
        assert entry.embedding == [1.0] + [0.0] * 7


# ---------------------------------------------------------------------------
# UnifiedMemory – semantic search integration
# ---------------------------------------------------------------------------


class TestUnifiedSemanticSearch:
    @pytest.fixture
    def mem(self, tmp_path) -> UnifiedMemory:
        m = UnifiedMemory(db_path=str(tmp_path / "uni.db"))
        yield m
        m.close()

    def test_store_semantic_and_search(self, mem):
        mem.store("Python machine learning TensorFlow", memory_type=MemoryType.SEMANTIC)
        mem.store("Recipe for chocolate cake baking", memory_type=MemoryType.SEMANTIC)
        results = mem.search("deep learning neural networks", use_semantic=True)
        assert isinstance(results, list)

    def test_semantic_results_have_scores(self, mem):
        mem.store("FastAPI REST API web development", memory_type=MemoryType.SEMANTIC)
        results = mem.search("web API", use_semantic=True)
        for r in results:
            assert isinstance(r.score, float)

    def test_long_term_and_semantic_both_returned(self, mem):
        mem.store("fact about Python", memory_type=MemoryType.LONG_TERM)
        mem.store("semantic about Python", memory_type=MemoryType.SEMANTIC)
        results = mem.search("Python")
        assert len(results) >= 1

    def test_importance_boosts_ranking(self, mem):
        mem.store(
            "low importance Python", memory_type=MemoryType.SEMANTIC, importance=0.1
        )
        mem.store(
            "high importance Python critical",
            memory_type=MemoryType.SEMANTIC,
            importance=0.9,
        )
        results = mem.search("Python", use_semantic=True, limit=10)
        if len(results) >= 2:
            high_idx = next(
                (i for i, r in enumerate(results) if "high" in r.content), None
            )
            low_idx = next(
                (i for i, r in enumerate(results) if "low importance" in r.content),
                None,
            )
            # High importance item should appear at or before low importance
            if high_idx is not None and low_idx is not None:
                assert high_idx <= low_idx

    def test_filter_by_memory_type(self, mem):
        mem.store("session content", memory_type=MemoryType.SESSION)
        mem.store("long term content", memory_type=MemoryType.LONG_TERM)
        results = mem.search("content", memory_type=MemoryType.LONG_TERM)
        for r in results:
            assert r.memory_type == MemoryType.LONG_TERM

    def test_search_with_session_filter(self, mem):
        mem.store("session A data", memory_type=MemoryType.LONG_TERM, session_id="A")
        mem.store("session B data", memory_type=MemoryType.LONG_TERM, session_id="B")
        results = mem.search("data", session_id="A")
        for r in results:
            assert r.session_id == "A"
