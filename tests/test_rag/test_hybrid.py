# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Comprehensive tests for hybrid search module.

Covers:
- Reciprocal Rank Fusion (RRF) combining multiple ranked lists
- HybridSearchResult dataclass
- Vector + keyword + graph result merging
- Ranking normalization
- Edge cases (empty results, duplicate items, single vs multiple sources)
"""

from __future__ import annotations

import pytest

from agentic_brain.rag.hybrid import HybridSearchResult, reciprocal_rank_fusion
from agentic_brain.rag.retriever import RetrievedChunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vector_results() -> list[dict]:
    """Sample vector search results."""
    return [
        {"id": "doc_1", "score": 0.95, "content": "Vector result 1"},
        {"id": "doc_2", "score": 0.87, "content": "Vector result 2"},
        {"id": "doc_3", "score": 0.75, "content": "Vector result 3"},
    ]


@pytest.fixture
def graph_results() -> list[dict]:
    """Sample graph search results."""
    return [
        {"id": "doc_2", "score": 0.92, "content": "Graph result 2"},
        {"id": "doc_1", "score": 0.85, "content": "Graph result 1"},
        {"id": "doc_4", "score": 0.68, "content": "Graph result 4"},
    ]


@pytest.fixture
def keyword_results() -> list[dict]:
    """Sample keyword search results."""
    return [
        {"id": "doc_1", "score": 0.88, "content": "Keyword result 1"},
        {"id": "doc_3", "score": 0.79, "content": "Keyword result 3"},
    ]


@pytest.fixture
def retrieved_chunks() -> list[RetrievedChunk]:
    """Sample retrieved chunks for HybridSearchResult."""
    return [
        RetrievedChunk(content="Chunk 1", source="doc1", score=0.9),
        RetrievedChunk(content="Chunk 2", source="doc2", score=0.8),
        RetrievedChunk(content="Chunk 3", source="doc3", score=0.7),
    ]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion Tests
# ---------------------------------------------------------------------------


class TestReciprocalRankFusion:
    def test_rrf_two_ranked_lists(self, vector_results: list, graph_results: list) -> None:
        """Test RRF with two input ranked lists."""
        fused = reciprocal_rank_fusion(vector_results, graph_results)

        assert isinstance(fused, list)
        assert len(fused) > 0
        assert all("rrf_score" in item for item in fused)

    def test_rrf_three_ranked_lists(
        self,
        vector_results: list,
        graph_results: list,
        keyword_results: list,
    ) -> None:
        """Test RRF with three input ranked lists."""
        fused = reciprocal_rank_fusion(
            vector_results, graph_results, keyword_results
        )
        assert isinstance(fused, list)
        assert len(fused) > 0

    def test_rrf_scores_are_positive(self, vector_results: list, graph_results: list) -> None:
        """RRF scores should be positive."""
        fused = reciprocal_rank_fusion(vector_results, graph_results)
        assert all(item["rrf_score"] > 0 for item in fused)

    def test_rrf_scores_decrease_monotonically(
        self, vector_results: list, graph_results: list
    ) -> None:
        """RRF scores should be sorted in descending order."""
        fused = reciprocal_rank_fusion(vector_results, graph_results)
        scores = [item["rrf_score"] for item in fused]
        assert scores == sorted(scores, reverse=True)

    def test_rrf_common_items_ranked_higher(
        self, vector_results: list, graph_results: list
    ) -> None:
        """Items appearing in multiple ranked lists should score higher."""
        # doc_1 and doc_2 appear in both lists
        fused = reciprocal_rank_fusion(vector_results, graph_results)

        # Find doc_1 and doc_2 in fused results
        doc_1_item = next(item for item in fused if item["id"] == "doc_1")
        doc_3_item = next(item for item in fused if item["id"] == "doc_3")

        # doc_1 appears in both lists, doc_3 only in vector
        assert doc_1_item["rrf_score"] > doc_3_item["rrf_score"]

    def test_rrf_merges_item_data(self, vector_results: list, graph_results: list) -> None:
        """RRF should merge data from multiple sources."""
        fused = reciprocal_rank_fusion(vector_results, graph_results)
        # Items should have merged content from both searches
        for item in fused:
            assert "id" in item
            assert "rrf_score" in item

    def test_rrf_custom_k_parameter(self, vector_results: list, graph_results: list) -> None:
        """Test RRF with custom k parameter."""
        fused_k60 = reciprocal_rank_fusion(
            vector_results, graph_results, k=60
        )
        fused_k100 = reciprocal_rank_fusion(
            vector_results, graph_results, k=100
        )

        # Different k values should produce different scores
        assert isinstance(fused_k60, list)
        assert isinstance(fused_k100, list)

    def test_rrf_empty_vector_results(self, graph_results: list) -> None:
        """RRF should handle empty vector results."""
        fused = reciprocal_rank_fusion([], graph_results)
        assert isinstance(fused, list)
        assert len(fused) == len(graph_results)

    def test_rrf_empty_graph_results(self, vector_results: list) -> None:
        """RRF should handle empty graph results."""
        fused = reciprocal_rank_fusion(vector_results, [])
        assert isinstance(fused, list)
        assert len(fused) == len(vector_results)

    def test_rrf_both_empty(self) -> None:
        """RRF with both empty lists should return empty."""
        fused = reciprocal_rank_fusion([], [])
        assert fused == []

    def test_rrf_single_item_in_each_list(self) -> None:
        """RRF with single item in each list."""
        list1 = [{"id": "a", "score": 0.9}]
        list2 = [{"id": "b", "score": 0.8}]
        fused = reciprocal_rank_fusion(list1, list2)
        assert len(fused) == 2

    def test_rrf_same_items_in_both_lists(self) -> None:
        """RRF with identical items in both lists."""
        list1 = [
            {"id": "x", "score": 0.9},
            {"id": "y", "score": 0.8},
        ]
        list2 = [
            {"id": "x", "score": 0.85},
            {"id": "y", "score": 0.75},
        ]
        fused = reciprocal_rank_fusion(list1, list2)
        assert len(fused) == 2
        # Both items appear twice, so should have higher RRF scores
        assert all(item["rrf_score"] > 0.01 for item in fused)


# ---------------------------------------------------------------------------
# Result ID Extraction Tests
# ---------------------------------------------------------------------------


class TestResultIDExtraction:
    def test_get_result_id_from_id_field(self) -> None:
        """Extract ID from 'id' field."""
        from agentic_brain.rag.hybrid import _get_result_id

        item = {"id": "doc_123", "score": 0.9}
        assert _get_result_id(item) == "doc_123"

    def test_get_result_id_from_chunk_id_field(self) -> None:
        """Extract ID from 'chunk_id' field when 'id' is missing."""
        from agentic_brain.rag.hybrid import _get_result_id

        item = {"chunk_id": "chunk_456", "score": 0.8}
        assert _get_result_id(item) == "chunk_456"

    def test_get_result_id_prefers_id_over_chunk_id(self) -> None:
        """Prefer 'id' field when both are present."""
        from agentic_brain.rag.hybrid import _get_result_id

        item = {"id": "id_field", "chunk_id": "chunk_field", "score": 0.7}
        assert _get_result_id(item) == "id_field"

    def test_get_result_id_raises_when_missing(self) -> None:
        """Raise KeyError when neither id nor chunk_id present."""
        from agentic_brain.rag.hybrid import _get_result_id

        item = {"score": 0.9}
        with pytest.raises(KeyError):
            _get_result_id(item)


# ---------------------------------------------------------------------------
# HybridSearchResult Tests
# ---------------------------------------------------------------------------


class TestHybridSearchResult:
    def test_hybrid_result_creation(
        self, vector_results: list, keyword_results: list, retrieved_chunks: list
    ) -> None:
        """Create HybridSearchResult."""
        vector_chunks = [
            RetrievedChunk(content=r["content"], source="vector", score=0.9)
            for r in vector_results
        ]
        keyword_chunks = [
            RetrievedChunk(content=r["content"], source="keyword", score=0.8)
            for r in keyword_results
        ]

        result = HybridSearchResult(
            query="test query",
            vector_results=vector_chunks,
            keyword_results=keyword_chunks,
            fused_results=retrieved_chunks,
        )

        assert result.query == "test query"
        assert len(result.vector_results) == 3
        assert len(result.keyword_results) == 2
        assert len(result.fused_results) == 3

    def test_hybrid_result_default_fused(
        self, vector_results: list, keyword_results: list
    ) -> None:
        """HybridSearchResult should handle empty fused results."""
        vector_chunks = [
            RetrievedChunk(content=r["content"], source="vector", score=0.9)
            for r in vector_results
        ]
        keyword_chunks = [
            RetrievedChunk(content=r["content"], source="keyword", score=0.8)
            for r in keyword_results
        ]

        result = HybridSearchResult(
            query="test",
            vector_results=vector_chunks,
            keyword_results=keyword_chunks,
            fused_results=[],
        )

        assert result.fused_results == []


# ---------------------------------------------------------------------------
# RRF Weight and Rank Tests
# ---------------------------------------------------------------------------


class TestRRFRanking:
    def test_rrf_rank_position_matters(self) -> None:
        """Earlier rank positions should contribute more to RRF score."""
        list1 = [
            {"id": "a", "score": 0.9},
            {"id": "b", "score": 0.8},
            {"id": "c", "score": 0.7},
        ]
        list2 = []

        fused = reciprocal_rank_fusion(list1, list2, k=60)

        # Extract RRF scores
        scores = {item["id"]: item["rrf_score"] for item in fused}
        # First rank (a) should have highest RRF score
        assert scores["a"] > scores["b"]
        assert scores["b"] > scores["c"]

    def test_rrf_rank_decay_formula(self) -> None:
        """Test that RRF score follows 1/(k+rank+1) formula."""
        list1 = [{"id": "x", "score": 0.9}]
        list2 = []

        fused = reciprocal_rank_fusion(list1, list2, k=60)

        expected_score = 1.0 / (60 + 0 + 1)  # rank 0 (first item)
        actual_score = fused[0]["rrf_score"]
        assert abs(actual_score - expected_score) < 0.0001


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestHybridSearchEdgeCases:
    def test_rrf_with_duplicate_ids_in_same_list(self) -> None:
        """RRF should handle duplicate IDs (take latest/merge)."""
        list1 = [
            {"id": "a", "score": 0.9},
            {"id": "a", "score": 0.8},  # Duplicate
        ]
        list2 = []

        fused = reciprocal_rank_fusion(list1, list2)
        # Should handle gracefully
        assert isinstance(fused, list)

    def test_rrf_with_string_vs_numeric_ids(self) -> None:
        """RRF should handle mixed ID types."""
        list1 = [
            {"id": "string_id", "score": 0.9},
            {"id": 123, "score": 0.8},
        ]
        list2 = [{"id": "string_id", "score": 0.85}]

        fused = reciprocal_rank_fusion(list1, list2)
        # Should convert to strings for consistency
        assert len(fused) == 2

    def test_rrf_large_result_sets(self) -> None:
        """RRF should handle large result sets."""
        list1 = [{"id": f"doc_{i}", "score": 0.9 - i * 0.001} for i in range(1000)]
        list2 = [{"id": f"doc_{i}", "score": 0.85 - i * 0.001} for i in range(500, 1500)]

        fused = reciprocal_rank_fusion(list1, list2)
        assert isinstance(fused, list)
        assert len(fused) == 1500

    def test_rrf_with_none_scores(self) -> None:
        """RRF should handle missing scores."""
        list1 = [{"id": "a", "score": 0.9}, {"id": "b"}]
        list2 = []

        # Should not crash even with missing scores
        fused = reciprocal_rank_fusion(list1, list2)
        assert isinstance(fused, list)

    def test_rrf_preserves_all_metadata(self) -> None:
        """RRF should preserve metadata from all sources."""
        list1 = [
            {"id": "a", "score": 0.9, "source": "vector", "metadata": {"type": "entity"}},
        ]
        list2 = [
            {"id": "a", "score": 0.8, "content": "text", "metadata": {"page": 1}},
        ]

        fused = reciprocal_rank_fusion(list1, list2)
        item_a = fused[0]

        assert "source" in item_a
        assert "content" in item_a
        # Metadata should be merged
        assert "metadata" in item_a or "page" in item_a or "type" in item_a
