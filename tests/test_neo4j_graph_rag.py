# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for Enhanced Graph RAG."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agentic_brain.rag.graph import (
    EnhancedGraphRAG,
    GraphRAGConfig,
    RetrievalStrategy,
)
from agentic_brain.rag.hybrid import reciprocal_rank_fusion


class FakeGraphEmbedder:
    @staticmethod
    def is_available():
        return True

    @staticmethod
    def provider_name():
        return "sentence_transformers/all-MiniLM-L6-v2@mps"

    @staticmethod
    def dimensions():
        return 384

    @staticmethod
    def embed(text: str):
        return [float(len(text))] * 384

    @staticmethod
    def embed_batch(texts: list[str]):
        return [[float(index + 1)] * 384 for index, _ in enumerate(texts)]


@pytest.fixture
def config():
    """Create test configuration."""
    return GraphRAGConfig(
        use_pool=True,
        embedding_dimension=384,
        top_k=5,
    )


@pytest.fixture
def graph_rag(config):
    """Create Enhanced Graph RAG instance."""
    return EnhancedGraphRAG(config)


@pytest.fixture
def mock_session():
    """Create mock Neo4j session."""
    session = MagicMock()
    session.run = MagicMock(return_value=MagicMock())
    session.close = MagicMock()
    return session


@pytest.mark.asyncio
async def test_initialize(graph_rag, mock_session):
    """Test initialization creates schema."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        await graph_rag.initialize()

        assert graph_rag._initialized is True
        # Verify schema creation calls
        assert mock_session.run.call_count >= 3  # Constraints + indexes


@pytest.mark.asyncio
async def test_index_document(graph_rag, mock_session):
    """Test indexing a document."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        doc_id = await graph_rag.index_document(
            content="Python is a programming language",
            doc_id="doc1",
            metadata={"source": "test"},
        )

        assert doc_id == "doc1"
        # Verify document creation
        assert mock_session.run.call_count >= 1


@pytest.mark.asyncio
async def test_index_document_uses_real_chunk_embeddings(mock_session):
    """Chunk embeddings should come from the real embedder, not mock [0.1] values."""
    with (
        patch("agentic_brain.rag.graph._get_mlx_embeddings", return_value=FakeGraphEmbedder),
        patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session,
    ):
        mock_get_session.return_value.__enter__.return_value = mock_session
        rag = EnhancedGraphRAG(GraphRAGConfig())

        await rag.index_document(
            content="Python powers GraphRAG on Apple Silicon. Neo4j stores vectors.",
            doc_id="doc-real-embeddings",
        )

    chunk_calls = [call for call in mock_session.run.call_args_list if "chunks" in call.kwargs]
    assert chunk_calls
    chunk_params = chunk_calls[-1].kwargs["chunks"]
    assert chunk_params
    first_embedding = chunk_params[0]["embedding"]
    assert len(first_embedding) == 384
    assert first_embedding != [0.1] * 384
    assert first_embedding == [1.0] * 384


def test_init_aligns_vector_dimension_with_embedder():
    """Graph config should match the active embedder dimension."""
    with patch(
        "agentic_brain.rag.graph._get_mlx_embeddings", return_value=FakeGraphEmbedder
    ):
        rag = EnhancedGraphRAG(GraphRAGConfig(embedding_dimension=768))

    assert rag.config.embedding_dimension == 384


@pytest.mark.asyncio
async def test_extract_entities(graph_rag):
    """Test entity extraction."""
    text = "Python and JavaScript are popular Programming languages"

    entities = graph_rag._extract_entities(text)

    assert len(entities) > 0
    # Should extract capitalized words
    entity_names = [e["name"] for e in entities]
    assert "Python" in entity_names
    assert "JavaScript" in entity_names


@pytest.mark.asyncio
async def test_chunk_content(graph_rag):
    """Test content chunking."""
    content = "This is a test. " * 100  # Long content

    chunks = graph_rag._chunk_content(content, chunk_size=50)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 60  # Some flexibility for sentence boundaries


@pytest.mark.asyncio
async def test_vector_retrieve(graph_rag, mock_session):
    """Test vector similarity search."""
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([])
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        graph_rag._initialized = True
        results = await graph_rag._vector_retrieve("test query", top_k=5)

        # Should return mock results if DB empty
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_graph_retrieve(graph_rag, mock_session):
    """Test graph-based retrieval."""
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([])
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        graph_rag._initialized = True
        results = await graph_rag._graph_retrieve("test query", top_k=5)

        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_hybrid_retrieve(graph_rag, mock_session):
    """Test hybrid vector+graph retrieval."""
    graph_rag._initialized = True
    graph_rag._vector_retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "chunk-a",
                "content": "Vector-only result",
                "position": 0,
                "doc_id": "doc-a",
                "metadata": {"source": "vector"},
                "score": 0.99,
                "strategy": "vector",
            },
            {
                "chunk_id": "chunk-b",
                "content": "Shared result",
                "position": 1,
                "doc_id": "doc-b",
                "metadata": {"source": "vector"},
                "score": 0.5,
                "strategy": "vector",
            },
        ]
    )
    graph_rag._graph_retrieve = AsyncMock(
        return_value=[
            {
                "chunk_id": "chunk-b",
                "content": "Shared result",
                "position": 1,
                "doc_id": "doc-b",
                "metadata": {"source": "graph"},
                "score": 0.2,
                "entities": ["Shared"],
                "strategy": "graph",
            }
        ]
    )

    results = await graph_rag._hybrid_retrieve("test query", top_k=5)

    assert isinstance(results, list)
    assert [result["chunk_id"] for result in results[:2]] == ["chunk-b", "chunk-a"]
    assert results[0]["vector_score"] == 0.5
    assert results[0]["graph_score"] == 0.2
    assert results[0]["score"] == results[0]["rrf_score"]
    assert results[0]["fusion_method"] == "rrf"


def test_reciprocal_rank_fusion_prefers_consensus_hits():
    """RRF should reward items that rank well across multiple sources."""
    fused = reciprocal_rank_fusion(
        vector_results=[
            {"id": "chunk-a", "content": "Vector-only"},
            {"id": "chunk-b", "content": "Shared"},
        ],
        graph_results=[
            {"id": "chunk-b", "content": "Shared", "entities": ["Shared"]},
            {"id": "chunk-c", "content": "Graph-only"},
        ],
    )

    assert [item["id"] for item in fused[:3]] == ["chunk-b", "chunk-a", "chunk-c"]
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]
    assert fused[0]["entities"] == ["Shared"]


@pytest.mark.asyncio
async def test_retrieve_strategies(graph_rag, mock_session):
    """Test different retrieval strategies."""
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([])
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        graph_rag._initialized = True

        graph_rag._community_retrieve = AsyncMock(return_value=[])

        # Test each strategy
        for strategy in ["vector", "graph", "hybrid", "community"]:
            results = await graph_rag.retrieve("test query", strategy=strategy)
            assert isinstance(results, list)


@pytest.mark.asyncio
async def test_community_retrieve(graph_rag, mock_session):
    """Test community-based retrieval."""
    with patch("agentic_brain.rag.graph.detect_communities") as mock_detect:
        mock_detect.return_value = {1: ["Python", "Java"]}
        with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session

            graph_rag._initialized = True
            graph_rag._run_query = Mock(
                return_value=[
                    {
                        "chunk_id": "chunk-1",
                        "content": "Python content",
                        "position": 0,
                        "doc_id": "doc-1",
                        "metadata": {"source": "community"},
                        "community_score": 2,
                        "entities": ["Python", "Java"],
                    }
                ]
            )

            results = await graph_rag._community_retrieve("Python", top_k=5)

    assert results
    assert results[0]["strategy"] == "community"
    assert results[0]["community_ids"] == [1]


@pytest.mark.asyncio
async def test_build_relationships(graph_rag, mock_session):
    """Test building entity relationships."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        await graph_rag.build_relationships(
            source_entity="Python",
            target_entity="Programming",
            relationship_type="IS_A",
            weight=0.9,
        )

        # Verify relationship creation
        assert mock_session.run.call_count >= 1


@pytest.mark.asyncio
async def test_get_entity_context(graph_rag, mock_session):
    """Test getting entity context."""
    mock_record = {
        "name": "Python",
        "type": "TECHNOLOGY",
        "mentions": 10,
        "neighbors": [],
        "relationships": [],
        "documents": [],
    }
    mock_result = MagicMock()
    mock_result.single.return_value = mock_record
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        context = await graph_rag.get_entity_context("Python", max_hops=2)

        assert context["entity"]["name"] == "Python"
        assert context["entity"]["type"] == "TECHNOLOGY"


@pytest.mark.asyncio
async def test_fallback_text_search(graph_rag, mock_session):
    """Test fallback text search when vector index unavailable."""
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([])
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        graph_rag._initialized = True
        results = await graph_rag._fallback_text_search("test", top_k=5)

        assert isinstance(results, list)


def test_config_defaults():
    """Test default configuration values."""
    config = GraphRAGConfig()

    assert config.use_pool is True
    assert config.embedding_dimension == 384
    assert config.top_k == 10
    assert config.max_hop_depth == 3
    assert config.similarity_threshold == 0.7
