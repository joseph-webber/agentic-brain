from __future__ import annotations

import pytest

from agentic_brain.rag.embeddings import _fallback_embedding, detect_hardware, get_best_device
from agentic_brain.rag.retriever import Retriever
from agentic_brain.rag.store import InMemoryDocumentStore

pytestmark = [pytest.mark.integration, pytest.mark.embeddings]


def test_fallback_embedding_is_deterministic():
    first = _fallback_embedding("Neo4j and vector search", 32)
    second = _fallback_embedding("Neo4j and vector search", 32)

    assert first == second
    assert len(first) == 32


@pytest.mark.parametrize(
    "left,right",
    [
        ("alpha beta", "alpha gamma"),
        ("graph retrieval", "prompt caching"),
        ("OpenAI provider", "Anthropic provider"),
    ],
)
def test_fallback_embedding_distinguishes_text(left: str, right: str):
    left_vector = _fallback_embedding(left, 32)
    right_vector = _fallback_embedding(right, 32)

    assert left_vector != right_vector


def test_fallback_embedding_returns_zero_vector_for_blank_text():
    vector = _fallback_embedding("   ", 16)

    assert vector == [0.0] * 16


def test_mock_embeddings_batch_and_dimensions(mock_embeddings):
    vectors = mock_embeddings.embed_batch(["first", "second", "third"])

    assert len(vectors) == 3
    assert all(len(vector) == mock_embeddings.dimensions for vector in vectors)
    assert mock_embeddings.embed_call_count == 3


def test_inmemory_document_store_works_with_retriever(mock_embeddings):
    store = InMemoryDocumentStore()
    store.add("Neo4j powers graph retrieval.", {"source": "graph"})
    store.add("Caching keeps repeat queries fast.", {"source": "cache"})
    retriever = Retriever(document_store=store, embedding_provider=mock_embeddings)

    results = retriever.search_documents("graph retrieval", k=2)

    assert results
    assert results[0].source == "graph"
    assert results[0].score >= results[-1].score


def test_retriever_search_documents_prioritizes_relevant_content(mock_embeddings):
    store = InMemoryDocumentStore()
    store.add("OpenAI and Anthropic are provider examples.", {"source": "llm"})
    store.add("The documentation cache stores answers.", {"source": "cache"})
    retriever = Retriever(document_store=store, embedding_provider=mock_embeddings)

    results = retriever.retrieve("Anthropic provider", top_k=2)

    assert len(results) == 2
    assert results[0].source == "llm"
    assert results[0].score >= results[1].score


def test_detect_hardware_returns_best_device(monkeypatch):
    monkeypatch.setattr("agentic_brain.rag.embeddings.platform.system", lambda: "Linux")
    monkeypatch.setattr("agentic_brain.rag.embeddings.platform.machine", lambda: "x86_64")
    result = detect_hardware()

    assert "best_device" in result
    assert result["best_device"] in {"cpu", "mlx", "cuda", "mps"}


def test_get_best_device_caches_result(monkeypatch):
    import agentic_brain.rag.embeddings as embeddings_module

    monkeypatch.setattr(embeddings_module, "_HARDWARE_CACHE", None)
    monkeypatch.setattr(embeddings_module, "detect_hardware", lambda: {"best_device": "cpu"})

    assert get_best_device() == "cpu"
    assert get_best_device() == "cpu"

