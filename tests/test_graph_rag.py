# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.rag.graph_rag import GraphRAG, GraphRAGConfig, SearchStrategy


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


class AsyncContextManager:
    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    session = AsyncMock()
    # Ensure session() returns an async context manager
    driver.session.return_value = AsyncContextManager(session)
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def graph_rag(mock_driver):
    with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase") as mock_db:
        mock_db.driver.return_value = mock_driver
        config = GraphRAGConfig()
        rag = GraphRAG(config)
        yield rag


@pytest.mark.asyncio
async def test_initialization(graph_rag):
    assert graph_rag.config.embedding_dim == 384
    assert graph_rag._driver is not None


@pytest.mark.asyncio
async def test_ingest_mock(graph_rag):
    # Setup mock session
    session = AsyncMock()
    graph_rag._driver.session.return_value = AsyncContextManager(session)

    documents = [
        {
            "entities": [{"id": "e1", "type": "Person"}, {"id": "e2", "type": "Place"}],
            "relationships": [{"source": "e1", "target": "e2", "type": "LIVES_IN"}],
        }
    ]

    with patch(
        "agentic_brain.rag.graph_rag.detect_communities_async",
        new=AsyncMock(return_value={1: ["Alpha"], 2: ["Beta"]}),
    ):
        stats = await graph_rag.ingest(documents)

    assert stats["entities"] == 2
    assert stats["relationships"] == 1
    assert stats["communities"] == 2
    # Check if cypher queries were run
    assert session.run.call_count >= 3


@pytest.mark.asyncio
async def test_vector_search_strategy(graph_rag):
    results = await graph_rag.search("test query", strategy=SearchStrategy.VECTOR)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "entity_id" in results[0]
    assert "score" in results[0]


@pytest.mark.asyncio
async def test_ingest_uses_real_entity_embeddings(mock_driver):
    session = AsyncMock()
    mock_driver.session.return_value = AsyncContextManager(session)

    with (
        patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase") as mock_db,
        patch(
            "agentic_brain.rag.graph_rag._get_mlx_embeddings",
            return_value=FakeGraphEmbedder,
        ),
    ):
        mock_db.driver.return_value = mock_driver
        rag = GraphRAG(GraphRAGConfig(embedding_dim=768))
        await rag.ingest(
            [
                {
                    "entities": [
                        {
                            "id": "e1",
                            "type": "Concept",
                            "description": "GraphRAG embedding search",
                        }
                    ],
                    "relationships": [],
                }
            ]
        )

    assert rag.config.embedding_dim == 384
    entity_call = session.run.await_args_list[0]
    embedding = entity_call.kwargs["embedding"]
    assert len(embedding) == 384
    assert embedding != [0.1] * 384


@pytest.mark.asyncio
async def test_hybrid_search_strategy(graph_rag):
    results = await graph_rag.search("test query", strategy=SearchStrategy.HYBRID)
    assert isinstance(results, list)
    assert len(results) > 0
    # Hybrid search should add context from graph expansion
    assert "context" in results[0]
    assert "graph_score" in results[0]


@pytest.mark.asyncio
async def test_community_search_strategy(graph_rag):
    with patch(
        "agentic_brain.rag.graph_rag.detect_communities_async",
        new=AsyncMock(return_value={1: ["Alpha", "Beta"]}),
    ):
        results = await graph_rag.search("Alpha", strategy=SearchStrategy.COMMUNITY)

    assert isinstance(results, list)
    assert results
    assert results[0]["strategy"] == "community"


@pytest.mark.asyncio
async def test_generate_answer(graph_rag):
    context = [
        {
            "entity_id": "e1",
            "content": "Entity 1 content",
            "context": [{"id": "e2", "relationship": "REL", "description": "Desc"}],
        }
    ]
    answer = await graph_rag.generate_answer("What is e1?", context)
    assert isinstance(answer, str)
    assert "e1" in answer or "Generated answer" in answer


@pytest.mark.asyncio
async def test_no_driver_ingest():
    # Test behavior when driver is not available
    with patch("agentic_brain.rag.graph_rag.AsyncGraphDatabase", None):
        rag = GraphRAG()
        assert rag._driver is None
        stats = await rag.ingest([{}])
        assert stats["entities"] == 0
