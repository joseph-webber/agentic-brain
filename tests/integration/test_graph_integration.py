# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from agentic_brain.rag.graph import EnhancedGraphRAG, GraphRAGConfig, RetrievalStrategy
from agentic_brain.rag.graph_traversal import TraversalStrategy
from agentic_brain.rag.graphrag.knowledge_extractor import KnowledgeExtractor
from agentic_brain.rag.pipeline import RAGPipeline

pytestmark = [pytest.mark.integration, pytest.mark.graph]


def make_graph_rag(fake_graph_driver, monkeypatch):
    from agentic_brain.rag import community_detection as community_detection_module

    monkeypatch.setattr(
        community_detection_module, "resolve_entities", lambda session: 0
    )
    rag = EnhancedGraphRAG(GraphRAGConfig(use_pool=True))
    rag._get_session = fake_graph_driver.session
    return rag


@pytest.mark.asyncio
async def test_index_document_persists_document_entities_and_chunks(
    fake_graph_driver, graph_store, monkeypatch
):
    rag = make_graph_rag(fake_graph_driver, monkeypatch)

    doc_id = await rag.index_document(
        "Neo4j powers graph retrieval for OpenAI teams.",
        metadata={"source": "graph"},
    )

    assert doc_id
    assert graph_store.documents[doc_id]["metadata"]["source"] == "graph"
    assert graph_store.chunks
    assert graph_store.entities


@pytest.mark.asyncio
async def test_index_document_generates_stable_document_id(
    fake_graph_driver, monkeypatch
):
    rag = make_graph_rag(fake_graph_driver, monkeypatch)

    first = await rag.index_document("Ada Lovelace inspired modern computing.")
    second = await rag.index_document("Ada Lovelace inspired modern computing.")

    assert first == second


@pytest.mark.asyncio
async def test_index_document_accepts_precomputed_embedding(
    fake_graph_driver, graph_store, monkeypatch
):
    rag = make_graph_rag(fake_graph_driver, monkeypatch)
    embedding = [0.1] * rag.config.embedding_dimension

    doc_id = await rag.index_document(
        "Precomputed embeddings are supported.", embedding=embedding
    )

    assert doc_id in graph_store.documents
    assert all(
        len(chunk["embedding"]) == rag.config.embedding_dimension
        for chunk in graph_store.chunks.values()
    )


@pytest.mark.asyncio
async def test_vector_retrieve_returns_ranked_results(fake_graph_driver, monkeypatch):
    rag = make_graph_rag(fake_graph_driver, monkeypatch)
    await rag.index_document("Neo4j powers graph retrieval for OpenAI teams.")
    await rag.index_document("Caching keeps repeat queries fast.")

    results = await rag.retrieve("graph retrieval", strategy="vector", top_k=2)

    assert results
    assert results[0]["strategy"] == "vector"
    assert results[0]["score"] >= results[-1]["score"]


@pytest.mark.asyncio
async def test_graph_retrieve_finds_related_chunk(fake_graph_driver, monkeypatch):
    rag = make_graph_rag(fake_graph_driver, monkeypatch)
    await rag.index_document("Neo4j powers graph retrieval for OpenAI teams.")
    await rag.index_document("Caching keeps repeat queries fast.")

    results = await rag.retrieve("Neo4j graph", strategy="graph", top_k=3)

    assert results
    assert all(result["strategy"] == "graph" for result in results)
    assert any("Neo4j" in result["entities"] for result in results)


@pytest.mark.asyncio
async def test_hybrid_retrieve_combines_signals(fake_graph_driver, monkeypatch):
    rag = make_graph_rag(fake_graph_driver, monkeypatch)
    await rag.index_document("Neo4j powers graph retrieval for OpenAI teams.")
    await rag.index_document("Graph retrieval helps repeat queries.")

    results = await rag.retrieve("graph retrieval", strategy="hybrid", top_k=3)

    assert results
    assert all(result["strategy"] == "hybrid" for result in results)


def test_knowledge_extractor_builds_graph_payload():
    extractor = KnowledgeExtractor()
    result = extractor.extract_graph_only(
        "Ada Lovelace worked with Charles Babbage in London."
    )

    assert result.entity_count >= 2
    assert result.pipeline_used is False


def test_graph_query_hints_infer_labels_and_strategy():
    pipeline = RAGPipeline(document_store=None)

    labels, relationships, strategy = pipeline._infer_graph_hints(
        "Show the path from team owner to service dependency"
    )

    assert "Team" in labels
    assert "Service" in labels
    assert "DEPENDS_ON" in relationships
    assert strategy == TraversalStrategy.DEPTH_FIRST


@pytest.mark.asyncio
async def test_unknown_graph_query_returns_no_results(fake_graph_driver, monkeypatch):
    rag = make_graph_rag(fake_graph_driver, monkeypatch)
    await rag.index_document("Neo4j powers graph retrieval for OpenAI teams.")

    results = await rag.retrieve(
        "completely unrelated topic", strategy="graph", top_k=5
    )

    assert results == []
