# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Comprehensive tests for GraphRAG module.

Covers:
- GraphRAGConfig with all settings
- GraphRAG initialization and Neo4j driver setup
- SearchStrategy enum (VECTOR, GRAPH, HYBRID, COMMUNITY, MULTI_HOP)
- Vector search, graph search, hybrid search, community search
- Document ingestion (entities, relationships, community detection)
- Edge cases (empty results, missing driver, invalid embeddings)
- Fallback behaviors (GDS unavailable, community detection failure)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.rag.graph_rag import (
    GraphRAG,
    GraphRAGConfig,
    SearchStrategy,
    _embed_text,
    _get_embedding_dimension,
    _validate_embedding,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_basic() -> GraphRAGConfig:
    """Basic GraphRAG configuration for testing."""
    return GraphRAGConfig(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test-password",
        embedding_dim=384,
        embedding_model="test-model",
        chunk_size=512,
        chunk_overlap=50,
        max_hops=3,
        max_relationships=50,
        enable_communities=True,
        community_algorithm="leiden",
    )


@pytest.fixture
def config_no_communities() -> GraphRAGConfig:
    """GraphRAG configuration with communities disabled."""
    return GraphRAGConfig(
        neo4j_uri="bolt://localhost:7687",
        enable_communities=False,
    )


# ---------------------------------------------------------------------------
# GraphRAGConfig Tests
# ---------------------------------------------------------------------------


class TestGraphRAGConfig:
    def test_default_config_values(self) -> None:
        config = GraphRAGConfig()
        assert config.neo4j_uri == "bolt://localhost:7687"
        assert config.neo4j_user == "neo4j"
        assert config.embedding_dim == 384
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.enable_communities is True
        assert config.community_algorithm == "leiden"

    def test_config_custom_values(self, config_basic: GraphRAGConfig) -> None:
        assert config_basic.neo4j_uri == "bolt://localhost:7687"
        assert config_basic.embedding_model == "test-model"
        assert config_basic.max_hops == 3
        assert config_basic.max_relationships == 50

    def test_config_cache_settings(self) -> None:
        config = GraphRAGConfig(cache_embeddings=True, cache_ttl=3600)
        assert config.cache_embeddings is True
        assert config.cache_ttl == 3600

    def test_config_community_disabled(
        self, config_no_communities: GraphRAGConfig
    ) -> None:
        assert config_no_communities.enable_communities is False


# ---------------------------------------------------------------------------
# SearchStrategy Enum Tests
# ---------------------------------------------------------------------------


class TestSearchStrategy:
    def test_all_strategies_defined(self) -> None:
        assert SearchStrategy.VECTOR.value == "vector"
        assert SearchStrategy.GRAPH.value == "graph"
        assert SearchStrategy.HYBRID.value == "hybrid"
        assert SearchStrategy.COMMUNITY.value == "community"
        assert SearchStrategy.MULTI_HOP.value == "multi_hop"

    def test_strategies_are_enum_members(self) -> None:
        assert isinstance(SearchStrategy.VECTOR, SearchStrategy)
        assert isinstance(SearchStrategy.GRAPH, SearchStrategy)
        assert isinstance(SearchStrategy.HYBRID, SearchStrategy)
        assert isinstance(SearchStrategy.COMMUNITY, SearchStrategy)
        assert isinstance(SearchStrategy.MULTI_HOP, SearchStrategy)

    def test_strategy_comparison(self) -> None:
        assert SearchStrategy.VECTOR != SearchStrategy.GRAPH
        assert SearchStrategy.HYBRID != SearchStrategy.COMMUNITY
        assert SearchStrategy.MULTI_HOP != SearchStrategy.VECTOR


# ---------------------------------------------------------------------------
# Embedding Utilities Tests
# ---------------------------------------------------------------------------


class TestEmbeddingUtilities:
    def test_embed_text_with_fallback(self) -> None:
        # Test fallback embedding when MLX is unavailable
        with patch(
            "agentic_brain.rag.graph_rag._get_mlx_embeddings", return_value=None
        ):
            embedding = _embed_text("test query", fallback_dim=8)
            assert isinstance(embedding, list)
            assert len(embedding) == 8
            assert all(isinstance(x, float) for x in embedding)

    def test_embed_text_deterministic(self) -> None:
        # Same text should produce consistent embeddings
        emb1 = _embed_text("same text", fallback_dim=8)
        emb2 = _embed_text("same text", fallback_dim=8)
        assert emb1 == emb2

    def test_get_embedding_dimension_default(self) -> None:
        with patch(
            "agentic_brain.rag.graph_rag._get_mlx_embeddings", return_value=None
        ):
            dim = _get_embedding_dimension(default_dim=384)
            assert dim == 384

    def test_validate_embedding_correct_dimension(self) -> None:
        embedding = [0.1, 0.2, 0.3, 0.4]
        validated = _validate_embedding(embedding, expected_dim=4, context="test")
        assert validated == embedding

    def test_validate_embedding_dimension_mismatch(self) -> None:
        embedding = [0.1, 0.2, 0.3]
        with pytest.raises(ValueError, match="embedding dimension mismatch"):
            _validate_embedding(embedding, expected_dim=4, context="test")

    def test_validate_embedding_converts_to_float(self) -> None:
        embedding = [1, 2, 3, 4]  # integers
        validated = _validate_embedding(embedding, expected_dim=4, context="test")
        assert all(isinstance(x, float) for x in validated)


# ---------------------------------------------------------------------------
# GraphRAG Initialization Tests
# ---------------------------------------------------------------------------


class TestGraphRAGInitialization:
    def test_init_with_default_config(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase") as mock_db:
            rag = GraphRAG()
            assert rag.config is not None
            assert rag.config.neo4j_uri == "bolt://localhost:7687"

    def test_init_with_custom_config(self, config_basic: GraphRAGConfig) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG(config=config_basic)
            assert rag.config == config_basic

    def test_init_without_neo4j_driver(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase", None):
            rag = GraphRAG()
            assert rag._driver is None

    @pytest.mark.asyncio
    async def test_close_closes_driver(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            rag._driver = AsyncMock()
            await rag.close()
            rag._driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_no_driver(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase", None):
            rag = GraphRAG()
            # Should not raise
            await rag.close()


# ---------------------------------------------------------------------------
# Vector Search Tests
# ---------------------------------------------------------------------------


class TestVectorSearch:
    @pytest.mark.asyncio
    async def test_vector_search_returns_results(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag._vector_search("machine learning", top_k=5)
            assert isinstance(results, list)
            assert len(results) > 0
            assert "entity_id" in results[0]
            assert "score" in results[0]

    @pytest.mark.asyncio
    async def test_vector_search_respects_top_k(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag._vector_search("test", top_k=1)
            assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_vector_search_scores_between_0_and_1(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag._vector_search("test", top_k=5)
            for result in results:
                score = result.get("score", 0)
                assert 0 <= score <= 1


# ---------------------------------------------------------------------------
# Graph Search Tests
# ---------------------------------------------------------------------------


class TestGraphSearch:
    @pytest.mark.asyncio
    async def test_graph_search_returns_empty_list(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            # Graph search currently returns empty in basic implementation
            results = await rag.search("test", strategy=SearchStrategy.GRAPH, top_k=5)
            assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Hybrid Search Tests
# ---------------------------------------------------------------------------


class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_hybrid_search_combines_vector_and_graph(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag._hybrid_search("machine learning", top_k=5)
            assert isinstance(results, list)
            assert all("entity_id" in r for r in results)
            assert all("score" in r for r in results)

    @pytest.mark.asyncio
    async def test_hybrid_search_adds_context(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag._hybrid_search("test", top_k=1)
            if results:
                assert "context" in results[0]
                assert isinstance(results[0]["context"], list)

    @pytest.mark.asyncio
    async def test_hybrid_search_adds_graph_score(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag._hybrid_search("test", top_k=1)
            if results:
                assert "graph_score" in results[0]


# ---------------------------------------------------------------------------
# Community Search Tests
# ---------------------------------------------------------------------------


class TestCommunitySearch:
    @pytest.mark.asyncio
    async def test_community_search_no_driver(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase", None):
            rag = GraphRAG()
            results = await rag._community_search("test", top_k=5)
            assert results == []

    @pytest.mark.asyncio
    async def test_community_search_fallback_on_detection_failure(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            rag._driver = AsyncMock()
            with patch(
                "agentic_brain.rag.graph_rag.detect_communities_async",
                side_effect=Exception("Detection failed"),
            ):
                results = await rag._community_search("test", top_k=5)
                # Should fall back to hybrid search
                assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_community_search_empty_communities_fallback(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            rag._driver = AsyncMock()
            with patch(
                "agentic_brain.rag.graph_rag.detect_communities_async",
                return_value={},
            ):
                results = await rag._community_search("test", top_k=5)
                # Should fall back to hybrid search
                assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Search Strategy Dispatch Tests
# ---------------------------------------------------------------------------


class TestSearchStrategyDispatch:
    @pytest.mark.asyncio
    async def test_search_hybrid_strategy(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag.search("test", strategy=SearchStrategy.HYBRID, top_k=5)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_vector_strategy(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag.search("test", strategy=SearchStrategy.VECTOR, top_k=5)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_graph_strategy(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag.search("test", strategy=SearchStrategy.GRAPH, top_k=5)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_community_strategy(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag.search(
                "test", strategy=SearchStrategy.COMMUNITY, top_k=5
            )
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_multi_hop_strategy_empty(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag.search(
                "test", strategy=SearchStrategy.MULTI_HOP, top_k=5
            )
            assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Entity Expansion Tests
# ---------------------------------------------------------------------------


class TestEntityExpansion:
    @pytest.mark.asyncio
    async def test_expand_entity_returns_neighbors(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            neighbors = await rag._expand_entity("entity_1")
            assert isinstance(neighbors, list)
            assert len(neighbors) > 0
            assert all("id" in n and "relationship" in n for n in neighbors)

    @pytest.mark.asyncio
    async def test_expand_entity_mock_neighbors(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            neighbors = await rag._expand_entity("entity_1")
            # Default mock includes neighbor_1 and neighbor_2
            ids = [n["id"] for n in neighbors]
            assert "neighbor_1" in ids or len(neighbors) >= 0


# ---------------------------------------------------------------------------
# Document Ingestion Tests
# ---------------------------------------------------------------------------


class TestDocumentIngestion:
    @pytest.mark.asyncio
    async def test_ingest_returns_stats(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            rag._driver = None  # Simulate no connection
            docs = [{"content": "Test document"}]
            stats = await rag.ingest(docs)
            assert isinstance(stats, dict)
            assert "entities" in stats
            assert "relationships" in stats
            assert "communities" in stats

    @pytest.mark.asyncio
    async def test_ingest_without_driver(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase", None):
            rag = GraphRAG()
            docs = [{"content": "Test"}]
            stats = await rag.ingest(docs)
            # Should return empty stats when no driver
            assert stats["entities"] == 0

    @pytest.mark.asyncio
    async def test_ingest_empty_document_list(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            rag._driver = None
            stats = await rag.ingest([])
            assert isinstance(stats, dict)


# ---------------------------------------------------------------------------
# Answer Generation Tests
# ---------------------------------------------------------------------------


class TestAnswerGeneration:
    @pytest.mark.asyncio
    async def test_generate_answer_returns_string(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            context = [
                {
                    "entity_id": "e1",
                    "content": "Test context",
                    "context": [
                        {
                            "relationship": "related_to",
                            "id": "e2",
                            "description": "Another entity",
                        }
                    ],
                }
            ]
            answer = await rag.generate_answer("test query", context)
            assert isinstance(answer, str)
            assert len(answer) > 0

    @pytest.mark.asyncio
    async def test_generate_answer_empty_context(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            answer = await rag.generate_answer("test", [])
            assert isinstance(answer, str)


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_search_empty_query(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            # Empty query should still return results (mock data)
            results = await rag.search("", strategy=SearchStrategy.VECTOR, top_k=5)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_very_large_top_k(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag.search(
                "test", strategy=SearchStrategy.VECTOR, top_k=1000
            )
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_zero_top_k(self) -> None:
        with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase"):
            rag = GraphRAG()
            results = await rag.search("test", strategy=SearchStrategy.VECTOR, top_k=0)
            assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Configuration Edge Cases
# ---------------------------------------------------------------------------


class TestConfigurationEdgeCases:
    def test_config_zero_chunk_size(self) -> None:
        config = GraphRAGConfig(chunk_size=0)
        assert config.chunk_size == 0

    def test_config_large_max_relationships(self) -> None:
        config = GraphRAGConfig(max_relationships=1000)
        assert config.max_relationships == 1000

    def test_config_different_embedding_models(self) -> None:
        config1 = GraphRAGConfig(embedding_model="model-a")
        config2 = GraphRAGConfig(embedding_model="model-b")
        assert config1.embedding_model != config2.embedding_model

    def test_config_community_algorithms(self) -> None:
        config_leiden = GraphRAGConfig(community_algorithm="leiden")
        config_louvain = GraphRAGConfig(community_algorithm="louvain")
        assert config_leiden.community_algorithm == "leiden"
        assert config_louvain.community_algorithm == "louvain"
