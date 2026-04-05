import asyncio
import pytest

from agentic_brain.rag.graph import (
    _validate_embedding,
    _get_embedding_dimension,
    EnhancedGraphRAG,
    GraphRAGConfig,
)


def test_validate_embedding_ok():
    emb = [0.0] * 384
    out = _validate_embedding(emb, 384, context="test")
    assert isinstance(out, list)


def test_validate_embedding_mismatch_raises():
    emb = [0.0] * 10
    with pytest.raises(ValueError):
        _validate_embedding(emb, 384, context="test")


def test_chunk_content_single_chunk():
    s = "short content"
    chunks = EnhancedGraphRAG()._chunk_content(s, chunk_size=100)
    assert chunks == ["short content"]


def test_chunk_content_sentence_boundary():
    s = "This is a sentence. This is another sentence. End."
    chunks = EnhancedGraphRAG()._chunk_content(s, chunk_size=10)
    assert len(chunks) >= 2


def test_get_embedding_dimension_default():
    # May return real embedder dimensions in some environments; ensure an int is returned
    dim = _get_embedding_dimension(123)
    assert isinstance(dim, int) and dim > 0


@pytest.mark.asyncio
async def test_hybrid_retrieve_merges_vector_and_graph(monkeypatch):
    rag = EnhancedGraphRAG(config=GraphRAGConfig())

    async def fake_vector(q, top_k, query_embedding=None):
        return [{"chunk_id": "c1", "score": 0.9, "content": "v1"}]

    async def fake_graph(q, top_k, filters=None):
        return [{"chunk_id": "c1", "score": 0.8, "content": "g1"}]

    def fake_rrf(v, g):
        return [{"id": "c1", "rrf_score": 0.85}]

    monkeypatch.setattr(rag, "_vector_retrieve", fake_vector)
    monkeypatch.setattr(rag, "_graph_retrieve", fake_graph)
    import agentic_brain.rag.hybrid as hybrid

    monkeypatch.setattr(hybrid, "reciprocal_rank_fusion", fake_rrf)

    out = await rag._hybrid_retrieve("q", top_k=1)
    assert isinstance(out, list)
    assert out and out[0]["strategy"] == "hybrid"


@pytest.mark.asyncio
async def test_hybrid_retrieve_handles_missing_merged(monkeypatch):
    rag = EnhancedGraphRAG(config=GraphRAGConfig())

    async def fake_vector(q, top_k, query_embedding=None):
        return [{"chunk_id": "c2", "score": 0.9, "content": "v1"}]

    async def fake_graph(q, top_k, filters=None):
        return []

    def fake_rrf(v, g):
        return [{"id": "c2", "rrf_score": 0.9}]

    monkeypatch.setattr(rag, "_vector_retrieve", fake_vector)
    monkeypatch.setattr(rag, "_graph_retrieve", fake_graph)
    import agentic_brain.rag.hybrid as hybrid

    monkeypatch.setattr(hybrid, "reciprocal_rank_fusion", fake_rrf)

    out = await rag._hybrid_retrieve("q", top_k=1)
    assert out and out[0]["strategy"] == "hybrid"
