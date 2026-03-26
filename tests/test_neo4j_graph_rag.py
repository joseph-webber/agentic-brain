# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for Enhanced Graph RAG."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from agentic_brain.rag.graph import (
    EnhancedGraphRAG,
    GraphRAGConfig,
    RetrievalStrategy,
)


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
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([])
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        graph_rag._initialized = True
        results = await graph_rag._hybrid_retrieve("test query", top_k=5)

        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_retrieve_strategies(graph_rag, mock_session):
    """Test different retrieval strategies."""
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([])
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        graph_rag._initialized = True

        # Test each strategy
        for strategy in ["vector", "graph", "hybrid"]:
            results = await graph_rag.retrieve("test query", strategy=strategy)
            assert isinstance(results, list)


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
