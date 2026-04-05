# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from agentic_brain.rag.evaluation import EvalDataset, RAGEvaluator
from agentic_brain.rag.pipeline import RAGPipeline
from agentic_brain.rag.store import Document, InMemoryDocumentStore

pytestmark = [pytest.mark.integration, pytest.mark.rag]


def build_pipeline(llm_server, mock_embeddings, document_store=None):
    pipeline = RAGPipeline(
        embedding_provider=mock_embeddings,
        document_store=document_store or InMemoryDocumentStore(),
        llm_provider="ollama",
        llm_model="llama3.1:8b",
        llm_base_url=llm_server["base_url"],
        cache_ttl_hours=1,
    )
    pipeline._generation_calls = 0

    def _generate_ollama(prompt: str, context: str) -> str:
        pipeline._generation_calls += 1
        return f"Mock answer: {prompt}"

    def _stream_ollama(prompt: str, context: str):
        yield f"Mock answer: {prompt}"

    pipeline._generate_ollama = _generate_ollama  # type: ignore[assignment]
    pipeline._stream_ollama = _stream_ollama  # type: ignore[assignment]
    return pipeline


def test_add_document_updates_store_stats(llm_server, mock_embeddings):
    pipeline = build_pipeline(llm_server, mock_embeddings)
    stored = pipeline.add_document(
        "Neo4j powers graph retrieval.",
        metadata={"source": "graph"},
    )

    stats = pipeline.get_stats()

    assert stored.chunks
    assert stats["document_count"] == 1
    assert stats["total_chunks"] == len(stored.chunks)


@pytest.mark.parametrize(
    "query,expected_source",
    [
        ("graph retrieval", "graph"),
        ("repeat queries", "cache"),
    ],
)
def test_query_returns_answer_and_sources(
    llm_server, mock_embeddings, query, expected_source
):
    pipeline = build_pipeline(llm_server, mock_embeddings)
    pipeline.add_document("Neo4j powers graph retrieval.", metadata={"source": "graph"})
    pipeline.add_document(
        "Caching keeps repeat queries fast.", metadata={"source": "cache"}
    )

    result = pipeline.query(query)

    assert result.answer.startswith("Mock answer:")
    assert result.has_sources
    assert any(source.source == expected_source for source in result.sources)


def test_query_stream_returns_tokens(llm_server, mock_embeddings):
    pipeline = build_pipeline(llm_server, mock_embeddings)
    pipeline.add_document(
        "Streaming helps with long answers.", metadata={"source": "stream"}
    )

    tokens = list(pipeline.query_stream("long answers"))

    assert tokens
    assert "".join(tokens).startswith("Mock answer:")


def test_cached_query_avoids_second_llm_call(
    monkeypatch, llm_server, mock_embeddings, temp_cache_dir
):
    monkeypatch.setenv("RAG_CACHE_ENABLED", "true")
    monkeypatch.setattr("agentic_brain.rag.pipeline.CACHE_DIR", temp_cache_dir)

    pipeline = build_pipeline(llm_server, mock_embeddings)
    pipeline.cache_dir = temp_cache_dir
    pipeline.add_document(
        "Caching keeps repeat queries fast.", metadata={"source": "cache"}
    )

    first = pipeline.query("repeat queries")
    second = pipeline.query("repeat queries")

    assert first.answer == second.answer
    assert second.cached is True
    assert pipeline._generation_calls == 1


@pytest.mark.asyncio
async def test_ingest_directory_loads_real_files(tmp_path, llm_server, mock_embeddings):
    (tmp_path / "readme.txt").write_text("Neo4j powers retrieval.")
    (tmp_path / "guide.md").write_text("# Cache\nRepeat queries should be fast.")

    pipeline = build_pipeline(llm_server, mock_embeddings)
    result = await pipeline.ingest(str(tmp_path))

    assert result.success
    assert result.documents_processed == 2
    assert result.chunks_created >= 2


@pytest.mark.asyncio
async def test_ingest_documents_objects(llm_server, mock_embeddings):
    pipeline = build_pipeline(llm_server, mock_embeddings)
    docs = [
        Document(
            id="doc-1",
            content="Neo4j stores relationships.",
            metadata={"source": "graph"},
        ),
        Document(
            id="doc-2",
            content="Caches prevent repeated work.",
            metadata={"source": "cache"},
        ),
    ]

    result = await pipeline.ingest_documents(docs)

    assert result.success
    assert result.documents_processed == 2
    assert pipeline.get_stats()["document_count"] == 2


def test_evaluator_scores_relevant_sources(llm_server, mock_embeddings):
    pipeline = build_pipeline(llm_server, mock_embeddings)
    pipeline.add_document("Neo4j powers graph retrieval.", metadata={"source": "graph"})
    pipeline.add_document(
        "Caching keeps repeat queries fast.", metadata={"source": "cache"}
    )

    dataset = EvalDataset()
    dataset.add_query("graph retrieval", ["graph"])
    dataset.add_query("repeat queries", ["cache"])

    evaluator = RAGEvaluator()
    results = evaluator.evaluate(pipeline.retriever.retrieve, dataset)

    assert results.num_queries == 2
    assert results.precision_at_k(1) >= 0.5
    assert results.recall_at_k(1) >= 0.5


def test_query_without_relevant_context_returns_fallback(llm_server, mock_embeddings):
    pipeline = build_pipeline(llm_server, mock_embeddings)

    result = pipeline.query("unknown topic")

    assert result.answer == "I don't have enough information to answer that question."
    assert result.confidence == 0.0
    assert result.has_sources is False
