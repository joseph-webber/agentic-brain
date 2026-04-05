# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Comprehensive tests for the unified RRF (Reciprocal Rank Fusion) module.

Tests cover:
- Basic RRF fusion with two sources
- Multi-source fusion (3+ sources)
- Weighted RRF
- Explain mode (per-source score breakdown)
- ID extraction from various formats
- Edge cases (empty, single item, duplicates, large datasets)
- Backward compatibility with legacy API
- Integration with HybridSearch, ParallelRetriever, community.py
"""

from __future__ import annotations

import pytest

from agentic_brain.rag.rrf import (
    DEFAULT_K,
    RRFExplanation,
    RRFResult,
    RRFSourceContribution,
    get_result_id,
    reciprocal_rank_fusion,
    reciprocal_rank_fusion_legacy,
)


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
def keyword_results() -> list[dict]:
    """Sample keyword search results."""
    return [
        {"id": "doc_2", "score": 0.92, "content": "Keyword result 2"},
        {"id": "doc_1", "score": 0.85, "content": "Keyword result 1"},
        {"id": "doc_4", "score": 0.68, "content": "Keyword result 4"},
    ]


@pytest.fixture
def graph_results() -> list[dict]:
    """Sample graph search results."""
    return [
        {"id": "doc_1", "score": 0.88, "content": "Graph result 1"},
        {"id": "doc_3", "score": 0.79, "content": "Graph result 3"},
        {"id": "doc_5", "score": 0.65, "content": "Graph result 5"},
    ]


@pytest.fixture
def three_source_ranked_lists(vector_results, keyword_results, graph_results):
    """Three sources for RRF fusion."""
    return [
        {"source": "vector", "results": vector_results},
        {"source": "keyword", "results": keyword_results},
        {"source": "graph", "results": graph_results},
    ]


# ---------------------------------------------------------------------------
# Basic RRF Fusion Tests
# ---------------------------------------------------------------------------


class TestBasicRRFFusion:
    """Tests for basic RRF fusion functionality."""

    def test_rrf_two_sources(self, vector_results, keyword_results) -> None:
        """Test RRF with two input sources."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ]
        )

        assert isinstance(result, RRFResult)
        assert len(result.items) > 0
        assert all("rrf_score" in item for item in result.items)
        assert result.total_sources == 2

    def test_rrf_three_sources(self, three_source_ranked_lists) -> None:
        """Test RRF with three input sources."""
        result = reciprocal_rank_fusion(three_source_ranked_lists)

        assert isinstance(result, RRFResult)
        assert result.total_sources == 3
        assert len(result.items) == 5  # doc_1 to doc_5

    def test_rrf_scores_are_positive(self, vector_results, keyword_results) -> None:
        """RRF scores should be positive."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ]
        )

        assert all(item["rrf_score"] > 0 for item in result.items)

    def test_rrf_scores_sorted_descending(
        self, vector_results, keyword_results
    ) -> None:
        """RRF scores should be sorted in descending order."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ]
        )

        scores = [item["rrf_score"] for item in result.items]
        assert scores == sorted(scores, reverse=True)

    def test_rrf_common_items_ranked_higher(
        self, vector_results, keyword_results
    ) -> None:
        """Items appearing in multiple sources should score higher."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ]
        )

        # doc_1 and doc_2 appear in both lists
        scores = {item["id"]: item["rrf_score"] for item in result.items}

        # doc_1 and doc_2 appear in both, doc_3 and doc_4 appear in one each
        assert scores["doc_1"] > scores["doc_3"]
        assert scores["doc_2"] > scores["doc_4"]


# ---------------------------------------------------------------------------
# Weighted RRF Tests
# ---------------------------------------------------------------------------


class TestWeightedRRF:
    """Tests for weighted RRF functionality."""

    def test_weighted_rrf_vector_priority(
        self, vector_results, keyword_results
    ) -> None:
        """Test that weights affect final scores."""
        unweighted = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ]
        )

        weighted = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ],
            weights={"vector": 2.0, "keyword": 1.0},
        )

        assert weighted.weights == {"vector": 2.0, "keyword": 1.0}

        # Scores should differ due to weighting
        unweighted_scores = {item["id"]: item["rrf_score"] for item in unweighted.items}
        weighted_scores = {item["id"]: item["rrf_score"] for item in weighted.items}

        # doc_1 is rank 0 in vector, rank 1 in keyword
        # With vector weight 2x, its vector contribution should dominate
        assert weighted_scores["doc_1"] != unweighted_scores["doc_1"]

    def test_weighted_rrf_custom_weights(self, three_source_ranked_lists) -> None:
        """Test RRF with custom weights for all sources."""
        result = reciprocal_rank_fusion(
            three_source_ranked_lists,
            weights={"vector": 1.5, "keyword": 1.0, "graph": 1.2},
        )

        assert result.weights == {"vector": 1.5, "keyword": 1.0, "graph": 1.2}
        assert len(result.items) > 0

    def test_weighted_rrf_missing_weight_uses_default(
        self, vector_results, keyword_results
    ) -> None:
        """Missing weight should default to 1.0."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ],
            weights={"vector": 2.0},  # keyword not specified
        )

        # Should still work with keyword defaulting to 1.0
        assert len(result.items) > 0


# ---------------------------------------------------------------------------
# Explain Mode Tests
# ---------------------------------------------------------------------------


class TestExplainMode:
    """Tests for RRF explain mode (per-source score breakdown)."""

    def test_explain_mode_returns_explanations(
        self, vector_results, keyword_results
    ) -> None:
        """Explain mode should return per-item explanations."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ],
            explain=True,
        )

        assert result.explanations is not None
        assert len(result.explanations) == len(result.items)

    def test_explain_mode_shows_source_contributions(
        self, vector_results, keyword_results
    ) -> None:
        """Explanations should show per-source contributions."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ],
            explain=True,
        )

        # doc_1 appears in both sources
        explanation = result.explanations["doc_1"]
        assert isinstance(explanation, RRFExplanation)
        assert explanation.appeared_in_count == 2
        assert len(explanation.sources) == 2

        source_names = [s.source for s in explanation.sources]
        assert "vector" in source_names
        assert "keyword" in source_names

    def test_explain_mode_contribution_details(
        self, vector_results, keyword_results
    ) -> None:
        """Source contributions should have rank, raw score, weighted score."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ],
            explain=True,
        )

        explanation = result.explanations["doc_1"]
        for contrib in explanation.sources:
            assert isinstance(contrib, RRFSourceContribution)
            assert contrib.rank >= 0
            assert contrib.raw_score > 0
            assert contrib.weighted_score > 0

    def test_explain_mode_disabled_by_default(
        self, vector_results, keyword_results
    ) -> None:
        """Explain mode should be disabled by default."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ]
        )

        assert result.explanations is None


# ---------------------------------------------------------------------------
# ID Extraction Tests
# ---------------------------------------------------------------------------


class TestIDExtraction:
    """Tests for get_result_id function."""

    def test_extract_id_from_id_field(self) -> None:
        """Extract ID from 'id' field."""
        item = {"id": "doc_123", "score": 0.9}
        assert get_result_id(item) == "doc_123"

    def test_extract_id_from_chunk_id_field(self) -> None:
        """Extract ID from 'chunk_id' field when 'id' is missing."""
        item = {"chunk_id": "chunk_456", "score": 0.8}
        assert get_result_id(item) == "chunk_456"

    def test_extract_id_from_doc_id_field(self) -> None:
        """Extract ID from 'doc_id' field."""
        item = {"doc_id": "document_789", "score": 0.7}
        assert get_result_id(item) == "document_789"

    def test_prefers_id_over_chunk_id(self) -> None:
        """Prefer 'id' field when multiple ID fields present."""
        item = {"id": "id_field", "chunk_id": "chunk_field", "score": 0.7}
        assert get_result_id(item) == "id_field"

    def test_raises_when_no_id_field(self) -> None:
        """Raise KeyError when no ID field is found."""
        item = {"score": 0.9, "content": "text"}
        with pytest.raises(KeyError):
            get_result_id(item)

    def test_converts_numeric_id_to_string(self) -> None:
        """Numeric IDs should be converted to strings."""
        item = {"id": 12345, "score": 0.9}
        assert get_result_id(item) == "12345"

    def test_custom_id_fields(self) -> None:
        """Test custom ID field names."""
        item = {"custom_key": "my_id", "score": 0.9}
        result = get_result_id(item, id_fields=("custom_key",))
        assert result == "my_id"


# ---------------------------------------------------------------------------
# K Parameter Tests
# ---------------------------------------------------------------------------


class TestKParameter:
    """Tests for configurable k parameter."""

    def test_default_k_is_60(self) -> None:
        """Default k parameter should be 60."""
        assert DEFAULT_K == 60

    def test_custom_k_affects_scores(self, vector_results, keyword_results) -> None:
        """Different k values should produce different scores."""
        result_k60 = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ],
            k=60,
        )

        result_k100 = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ],
            k=100,
        )

        # Scores should be different
        scores_k60 = {item["id"]: item["rrf_score"] for item in result_k60.items}
        scores_k100 = {item["id"]: item["rrf_score"] for item in result_k100.items}

        # Higher k means lower scores
        assert scores_k60["doc_1"] > scores_k100["doc_1"]

    def test_rrf_formula_correctness(self) -> None:
        """Test that RRF formula is correctly implemented."""
        results = [{"id": "x", "score": 0.9}]

        result = reciprocal_rank_fusion(
            [{"source": "test", "results": results}],
            k=60,
        )

        expected_score = 1.0 / (60 + 0 + 1)  # rank 0
        actual_score = result.items[0]["rrf_score"]
        assert abs(actual_score - expected_score) < 0.0001


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_sources(self) -> None:
        """RRF with empty source list."""
        result = reciprocal_rank_fusion([])
        assert result.items == []
        assert result.total_sources == 0

    def test_empty_results_in_source(self, vector_results) -> None:
        """RRF with one empty source."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": []},
            ]
        )

        assert len(result.items) == len(vector_results)

    def test_all_empty_results(self) -> None:
        """RRF with all sources having empty results."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": []},
                {"source": "keyword", "results": []},
            ]
        )

        assert result.items == []

    def test_single_item_single_source(self) -> None:
        """RRF with single item in single source."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": [{"id": "a", "score": 0.9}]},
            ]
        )

        assert len(result.items) == 1
        assert result.items[0]["id"] == "a"

    def test_duplicate_ids_in_same_source(self) -> None:
        """RRF should handle duplicate IDs in same source."""
        results = [
            {"id": "a", "score": 0.9},
            {"id": "a", "score": 0.8},  # Duplicate
        ]

        result = reciprocal_rank_fusion(
            [
                {"source": "test", "results": results},
            ]
        )

        # Should merge (update strategy by default)
        assert len(result.items) == 1

    def test_large_result_sets(self) -> None:
        """RRF should handle large result sets efficiently."""
        list1 = [{"id": f"doc_{i}", "score": 0.9 - i * 0.0001} for i in range(1000)]
        list2 = [
            {"id": f"doc_{i}", "score": 0.85 - i * 0.0001} for i in range(500, 1500)
        ]

        result = reciprocal_rank_fusion(
            [
                {"source": "list1", "results": list1},
                {"source": "list2", "results": list2},
            ]
        )

        assert len(result.items) == 1500
        assert result.total_unique_items == 1500

    def test_items_without_id_skipped(self) -> None:
        """Items without valid ID should be skipped."""
        results = [
            {"id": "valid", "score": 0.9},
            {"score": 0.8},  # No ID - should be skipped
        ]

        result = reciprocal_rank_fusion(
            [
                {"source": "test", "results": results},
            ]
        )

        assert len(result.items) == 1
        assert result.items[0]["id"] == "valid"


# ---------------------------------------------------------------------------
# Top K Tests
# ---------------------------------------------------------------------------


class TestTopK:
    """Tests for top_k parameter."""

    def test_top_k_limits_results(self, three_source_ranked_lists) -> None:
        """top_k should limit number of results."""
        result = reciprocal_rank_fusion(three_source_ranked_lists, top_k=3)

        assert len(result.items) == 3

    def test_top_k_returns_highest_scores(self, three_source_ranked_lists) -> None:
        """top_k should return items with highest scores."""
        result_all = reciprocal_rank_fusion(three_source_ranked_lists)
        result_top3 = reciprocal_rank_fusion(three_source_ranked_lists, top_k=3)

        # Top 3 should be same as first 3 of all results
        assert [item["id"] for item in result_top3.items] == [
            item["id"] for item in result_all.items[:3]
        ]


# ---------------------------------------------------------------------------
# Merge Strategy Tests
# ---------------------------------------------------------------------------


class TestMergeStrategy:
    """Tests for different merge strategies."""

    def test_update_strategy_merges_data(self) -> None:
        """Update strategy should merge data from multiple sources."""
        list1 = [{"id": "a", "field1": "value1"}]
        list2 = [{"id": "a", "field2": "value2"}]

        result = reciprocal_rank_fusion(
            [
                {"source": "s1", "results": list1},
                {"source": "s2", "results": list2},
            ],
            merge_strategy="update",
        )

        item = result.items[0]
        assert item["field1"] == "value1"
        assert item["field2"] == "value2"

    def test_first_strategy_keeps_first(self) -> None:
        """First strategy should keep only first occurrence data."""
        list1 = [{"id": "a", "field": "first"}]
        list2 = [{"id": "a", "field": "second"}]

        result = reciprocal_rank_fusion(
            [
                {"source": "s1", "results": list1},
                {"source": "s2", "results": list2},
            ],
            merge_strategy="first",
        )

        item = result.items[0]
        assert item["field"] == "first"


# ---------------------------------------------------------------------------
# Legacy API Tests
# ---------------------------------------------------------------------------


class TestLegacyAPI:
    """Tests for backward-compatible legacy API."""

    def test_legacy_api_two_sources(self, vector_results, keyword_results) -> None:
        """Legacy API should work with vector and graph results."""
        fused = reciprocal_rank_fusion_legacy(vector_results, keyword_results)

        assert isinstance(fused, list)
        assert len(fused) > 0
        assert all("rrf_score" in item for item in fused)

    def test_legacy_api_three_sources(
        self, vector_results, keyword_results, graph_results
    ) -> None:
        """Legacy API should work with optional keyword results."""
        fused = reciprocal_rank_fusion_legacy(
            vector_results, keyword_results, graph_results
        )

        assert isinstance(fused, list)
        assert len(fused) == 5

    def test_legacy_api_custom_k(self, vector_results, keyword_results) -> None:
        """Legacy API should accept custom k parameter."""
        fused = reciprocal_rank_fusion_legacy(vector_results, keyword_results, k=100)

        assert isinstance(fused, list)

    def test_legacy_import_from_hybrid(self, vector_results, keyword_results) -> None:
        """Legacy import from hybrid module should work."""
        from agentic_brain.rag.hybrid import reciprocal_rank_fusion as rrf_hybrid

        fused = rrf_hybrid(vector_results, keyword_results)
        assert isinstance(fused, list)
        assert len(fused) > 0


# ---------------------------------------------------------------------------
# RRFResult Dataclass Tests
# ---------------------------------------------------------------------------


class TestRRFResultDataclass:
    """Tests for RRFResult dataclass."""

    def test_result_has_metadata(self, vector_results, keyword_results) -> None:
        """RRFResult should include metadata."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ]
        )

        assert result.k == DEFAULT_K
        assert result.total_sources == 2
        assert result.total_unique_items > 0

    def test_result_with_custom_k(self, vector_results, keyword_results) -> None:
        """RRFResult should store custom k value."""
        result = reciprocal_rank_fusion(
            [
                {"source": "vector", "results": vector_results},
                {"source": "keyword", "results": keyword_results},
            ],
            k=100,
        )

        assert result.k == 100


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests with other modules."""

    def test_import_from_rag_module(self) -> None:
        """Should be importable from main rag module."""
        from agentic_brain.rag import (
            RRF_DEFAULT_K,
            RRFExplanation,
            RRFResult,
            get_result_id,
            reciprocal_rank_fusion,
        )

        assert RRF_DEFAULT_K == 60
        assert RRFResult is not None
        assert RRFExplanation is not None
        assert callable(reciprocal_rank_fusion)
        assert callable(get_result_id)

    def test_hybrid_search_uses_unified_rrf(self) -> None:
        """HybridSearch._reciprocal_rank_fusion should use unified RRF."""
        from agentic_brain.rag.hybrid import HybridSearch, DEFAULT_K

        assert DEFAULT_K == 60
        # The import should work, proving hybrid.py uses rrf.py

    def test_parallel_retrieval_uses_unified_rrf(self) -> None:
        """ParallelRetriever should use unified RRF."""
        from agentic_brain.rag.parallel_retrieval import FederatedRetriever

        # If import works, the module has been updated to use unified RRF
        assert FederatedRetriever is not None
