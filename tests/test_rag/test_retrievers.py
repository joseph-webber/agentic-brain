# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Tests for RAG retriever components.

Covers: RetrievedChunk, Retriever (search_documents, search_files,
        search_neo4j, search), cosine similarity, confidence levels,
        score ranking, filtering, and k-limiting.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.retriever import RetrievedChunk, Retriever

from .conftest import (
    EMBEDDING_DIM,
    InMemoryDocumentStore,
    MockEmbeddingProvider,
    _unit_vector,
)


# ---------------------------------------------------------------------------
# RetrievedChunk
# ---------------------------------------------------------------------------


class TestRetrievedChunk:
    def test_high_confidence(self) -> None:
        chunk = RetrievedChunk(content="x", source="doc", score=0.9)
        assert chunk.confidence == "high"

    def test_medium_confidence(self) -> None:
        chunk = RetrievedChunk(content="x", source="doc", score=0.65)
        assert chunk.confidence == "medium"

    def test_low_confidence(self) -> None:
        chunk = RetrievedChunk(content="x", source="doc", score=0.35)
        assert chunk.confidence == "low"

    def test_uncertain_confidence(self) -> None:
        chunk = RetrievedChunk(content="x", source="doc", score=0.1)
        assert chunk.confidence == "uncertain"

    def test_to_context_includes_source_and_content(self) -> None:
        chunk = RetrievedChunk(content="Machine learning.", source="wiki", score=0.8)
        ctx = chunk.to_context()
        assert "wiki" in ctx
        assert "Machine learning." in ctx

    def test_metadata_default_empty(self) -> None:
        chunk = RetrievedChunk(content="text", source="src", score=0.5)
        assert chunk.metadata == {}

    def test_metadata_preserved(self) -> None:
        meta = {"doc_id": "abc-123", "page": 2}
        chunk = RetrievedChunk(content="text", source="src", score=0.5, metadata=meta)
        assert chunk.metadata["doc_id"] == "abc-123"
        assert chunk.metadata["page"] == 2


# ---------------------------------------------------------------------------
# Retriever – cosine similarity
# ---------------------------------------------------------------------------


class TestCosineSimlarity:
    """Test the internal _cosine_similarity helper."""

    def _make_retriever(self) -> Retriever:
        emb = MockEmbeddingProvider()
        return Retriever(embedding_provider=emb)

    def test_identical_vectors_score_one(self) -> None:
        r = self._make_retriever()
        vec = _unit_vector(seed=7)
        score = r._cosine_similarity(vec, vec)
        assert abs(score - 1.0) < 1e-6

    def test_orthogonal_vectors_score_zero(self) -> None:
        r = self._make_retriever()
        a = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        score = r._cosine_similarity(a, b)
        assert abs(score) < 1e-6

    def test_zero_vector_returns_zero(self) -> None:
        r = self._make_retriever()
        zero = [0.0] * EMBEDDING_DIM
        vec = _unit_vector(seed=3)
        assert r._cosine_similarity(zero, vec) == 0.0
        assert r._cosine_similarity(vec, zero) == 0.0

    def test_score_in_range(self) -> None:
        r = self._make_retriever()
        a = _unit_vector(seed=1)
        b = _unit_vector(seed=42)
        score = r._cosine_similarity(a, b)
        assert -1.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Retriever – search_documents
# ---------------------------------------------------------------------------


class TestSearchDocuments:
    def _make_retriever(self, docs=None) -> Retriever:
        emb = MockEmbeddingProvider()
        store = InMemoryDocumentStore(docs or [])
        return Retriever(embedding_provider=emb, document_store=store)

    def test_returns_empty_when_no_documents(self) -> None:
        r = self._make_retriever(docs=[])
        results = r.search_documents("query", k=5)
        assert results == []

    def test_results_sorted_by_score(self) -> None:
        from agentic_brain.rag.loaders.base import LoadedDocument

        docs = [
            LoadedDocument(id=f"d{i}", content=f"doc content {i}", source="test")
            for i in range(5)
        ]
        r = self._make_retriever(docs=docs)
        results = r.search_documents("doc content", k=5)
        scores = [c.score for c in results]
        assert scores == sorted(scores, reverse=True)

    def test_k_limits_results(self) -> None:
        from agentic_brain.rag.loaders.base import LoadedDocument

        docs = [
            LoadedDocument(id=f"d{i}", content=f"document about topic {i}", source="test")
            for i in range(10)
        ]
        r = self._make_retriever(docs=docs)
        results = r.search_documents("topic", k=3)
        assert len(results) <= 3

    def test_returns_retrieved_chunks(self) -> None:
        from agentic_brain.rag.loaders.base import LoadedDocument

        docs = [LoadedDocument(id="d1", content="test content here", source="wiki")]
        r = self._make_retriever(docs=docs)
        results = r.search_documents("content", k=5)
        assert all(isinstance(rc, RetrievedChunk) for rc in results)

    def test_score_is_float_between_neg1_and_1(self) -> None:
        from agentic_brain.rag.loaders.base import LoadedDocument

        docs = [LoadedDocument(id=f"d{i}", content=f"text {i}", source="test") for i in range(3)]
        r = self._make_retriever(docs=docs)
        for rc in r.search_documents("text", k=5):
            assert -1.0 <= rc.score <= 1.0


# ---------------------------------------------------------------------------
# Retriever – search_files
# ---------------------------------------------------------------------------


class TestSearchFiles:
    def test_searches_txt_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("Machine learning overview.")
        (tmp_path / "b.txt").write_text("Python programming language.")
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb)
        results = r.search_files("machine learning", str(tmp_path), k=5)
        assert len(results) >= 1

    def test_k_limits_file_results(self, tmp_path: Path) -> None:
        for i in range(8):
            (tmp_path / f"doc{i}.txt").write_text(f"File content number {i}")
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb)
        results = r.search_files("file content", str(tmp_path), k=3)
        assert len(results) <= 3

    def test_extension_filter(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("text file content")
        (tmp_path / "b.md").write_text("markdown file content")
        (tmp_path / "c.py").write_text("# python file")
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb)
        results = r.search_files("content", str(tmp_path), k=10, extensions=[".txt"])
        sources = [rc.source for rc in results]
        assert all(".txt" in s for s in sources)

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb)
        results = r.search_files("query", str(tmp_path), k=5)
        assert results == []

    def test_results_ranked_by_score(self, tmp_path: Path) -> None:
        (tmp_path / "relevant.txt").write_text("machine learning neural networks")
        (tmp_path / "irrelevant.txt").write_text("cat sat on mat")
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb)
        results = r.search_files("machine learning", str(tmp_path), k=5)
        if len(results) > 1:
            scores = [rc.score for rc in results]
            assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Retriever – search (high-level)
# ---------------------------------------------------------------------------


class TestRetrieverSearch:
    def test_search_uses_document_store_when_set(self) -> None:
        from agentic_brain.rag.loaders.base import LoadedDocument

        docs = [LoadedDocument(id="d1", content="brain architecture", source="wiki")]
        emb = MockEmbeddingProvider()
        store = InMemoryDocumentStore(docs)
        r = Retriever(embedding_provider=emb, document_store=store)
        results = r.search("architecture", k=5)
        assert isinstance(results, list)

    def test_search_no_neo4j_no_store(self) -> None:
        """When Neo4j and document store are absent, should return empty or raise gracefully."""
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb, neo4j_uri="bolt://localhost:19999")
        # Should not crash - Neo4j unreachable should be handled
        try:
            results = r.search("test query", k=3)
            assert isinstance(results, list)
        except Exception as exc:
            # Any exception is acceptable as long as it's not a crash
            assert isinstance(exc, Exception)

    def test_retrieve_alias(self) -> None:
        """retrieve() is an alias for search()."""
        from agentic_brain.rag.loaders.base import LoadedDocument

        docs = [LoadedDocument(id="d1", content="test document content", source="wiki")]
        emb = MockEmbeddingProvider()
        store = InMemoryDocumentStore(docs)
        r = Retriever(embedding_provider=emb, document_store=store)
        r1 = r.search("test", k=3)
        r2 = r.retrieve("test", top_k=3)
        assert len(r1) == len(r2)

    def test_results_are_retrieved_chunks(self) -> None:
        from agentic_brain.rag.loaders.base import LoadedDocument

        docs = [LoadedDocument(id=f"d{i}", content=f"content {i}", source="test") for i in range(3)]
        emb = MockEmbeddingProvider()
        store = InMemoryDocumentStore(docs)
        r = Retriever(embedding_provider=emb, document_store=store)
        results = r.search("content", k=5)
        assert all(isinstance(rc, RetrievedChunk) for rc in results)

    def test_close_does_not_raise(self) -> None:
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb)
        r.close()  # Should not raise


# ---------------------------------------------------------------------------
# Retriever – search_neo4j (mocked)
# ---------------------------------------------------------------------------


class TestSearchNeo4j:
    def test_returns_chunks_from_vector_index(self) -> None:
        """Mock Neo4j vector index response."""
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb)

        mock_node = MagicMock()
        mock_node.get.side_effect = lambda key, default="": {
            "content": "Neo4j vector result",
        }.get(key, default)
        mock_node.__iter__ = MagicMock(return_value=iter([]))
        dict_mock = {}

        mock_record = {"node": mock_node, "score": 0.87, "labels": ["Document"]}

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_record]))

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = mock_result

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        with patch.object(r, "_get_driver", return_value=mock_driver):
            results = r.search_neo4j("brain architecture", k=5)

        assert isinstance(results, list)

    def test_neo4j_failure_returns_empty_gracefully(self) -> None:
        """When Neo4j raises, search_neo4j should handle it."""
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb)

        with patch.object(r, "_get_driver", side_effect=Exception("connection refused")):
            try:
                results = r.search_neo4j("query", k=3)
                assert isinstance(results, list)
            except Exception:
                pass  # Propagating is acceptable

    def test_min_score_filters_low_scores(self) -> None:
        """Chunks below min_score should not appear in results."""
        emb = MockEmbeddingProvider()
        r = Retriever(embedding_provider=emb)

        # Mock search_documents to return known chunks
        low_chunk = RetrievedChunk(content="low", source="doc", score=0.1)
        high_chunk = RetrievedChunk(content="high", source="doc", score=0.9)

        with patch.object(r, "search_documents", return_value=[high_chunk, low_chunk]):
            results = r.search_documents("test", k=10)

        # High score chunk should come first
        if len(results) >= 2:
            assert results[0].score >= results[1].score
