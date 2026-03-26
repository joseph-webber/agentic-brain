# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""Tests for graph-aware RAG pipeline helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.graph_traversal import GraphContext, GraphNode
from agentic_brain.rag.pipeline import (
    GraphQueryResult,
    GraphSearchResult,
    RAGPipeline,
)


@pytest.fixture
def graph_context() -> GraphContext:
    """Sample graph context for testing."""
    root = GraphNode(
        labels=["Project"],
        properties={"id": "proj-1", "name": "Project Alpha"},
        score=0.9,
    )
    related = GraphNode(
        labels=["Person"],
        properties={"id": "user-1", "name": "Sam"},
        score=0.7,
        depth=1,
        path=["WORKS_ON"],
    )
    return GraphContext(
        query="Project Alpha",
        root_nodes=[root],
        related_nodes=[related],
        relationships=[{"from": "proj-1", "to": "user-1", "type": "WORKS_ON"}],
        total_nodes=2,
        max_depth=1,
    )


def _make_pipeline() -> RAGPipeline:
    pipeline = RAGPipeline(embedding_provider=MagicMock())
    pipeline.retriever = MagicMock()
    pipeline.retriever._get_driver.return_value = MagicMock()
    pipeline.retriever.embeddings = MagicMock()
    return pipeline


def test_graph_search_result_fields(graph_context: GraphContext) -> None:
    """GraphSearchResult stores nodes, edges, and relevance scores."""
    nodes = graph_context.root_nodes + graph_context.related_nodes
    result = GraphSearchResult(
        query="Project Alpha",
        nodes=nodes,
        edges=graph_context.relationships,
        relevance_scores={"proj-1": 0.9, "user-1": 0.7},
    )

    assert result.nodes == nodes
    assert result.edges == graph_context.relationships
    assert result.relevance_scores["proj-1"] == 0.9
    assert result.has_results is True


@pytest.mark.asyncio
async def test_graph_search_returns_graph_results(
    graph_context: GraphContext,
) -> None:
    """graph_search returns nodes and edges from traversal."""
    pipeline = _make_pipeline()

    with patch("agentic_brain.rag.pipeline.GraphTraversalRetriever") as mock_retriever:
        graph_retriever = mock_retriever.return_value
        graph_retriever.retrieve.return_value = graph_context

        result = await pipeline.graph_search("Project Alpha", max_depth=2)

    assert isinstance(result, GraphSearchResult)
    assert len(result.nodes) == 2
    assert result.edges == graph_context.relationships
    assert result.relevance_scores["proj-1"] == 0.9


@pytest.mark.asyncio
async def test_graph_query_generates_answer(graph_context: GraphContext) -> None:
    """graph_query synthesizes an answer from graph context."""
    pipeline = _make_pipeline()

    with patch("agentic_brain.rag.pipeline.GraphTraversalRetriever") as mock_retriever:
        graph_retriever = mock_retriever.return_value
        graph_retriever.retrieve.return_value = graph_context

        with patch.object(
            pipeline, "_generate", return_value="Sam works on Project Alpha"
        ):
            result = await pipeline.graph_query("Who works on Project Alpha?")

    assert isinstance(result, GraphQueryResult)
    assert result.answer == "Sam works on Project Alpha"
    assert result.graph_context == graph_context
    assert len(result.sources) == 2


@pytest.mark.asyncio
async def test_graph_query_handles_empty_context() -> None:
    """graph_query returns a fallback answer when no nodes are found."""
    pipeline = _make_pipeline()
    empty_context = GraphContext(
        query="Unknown",
        root_nodes=[],
        related_nodes=[],
        relationships=[],
        total_nodes=0,
        max_depth=0,
    )

    with patch("agentic_brain.rag.pipeline.GraphTraversalRetriever") as mock_retriever:
        graph_retriever = mock_retriever.return_value
        graph_retriever.retrieve.return_value = empty_context

        result = await pipeline.graph_query("Unknown entity?")

    assert "couldn't find relevant graph context" in result.answer.lower()
    assert result.sources == []
