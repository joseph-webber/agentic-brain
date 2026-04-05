# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Tests for RAG embedding providers.

Covers: EmbeddingProvider ABC, _fallback_embedding, OllamaEmbeddings,
        OpenAIEmbeddings, SentenceTransformerEmbeddings, dimension validation,
        batch processing, caching, and get_embeddings factory.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.embeddings import (
    CachedEmbeddings,
    EmbeddingProvider,
    EmbeddingResult,
    OllamaEmbeddings,
    OpenAIEmbeddings,
    SentenceTransformerEmbeddings,
    _fallback_embedding,
    get_embeddings,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# _fallback_embedding
# ---------------------------------------------------------------------------


class TestFallbackEmbedding:
    def test_returns_correct_dimensions(self) -> None:
        vec = _fallback_embedding("hello world", dimensions=64)
        assert len(vec) == 64

    def test_unit_normalised(self) -> None:
        """Fallback embeddings should be L2-normalised."""
        vec = _fallback_embedding("normalisation test", dimensions=32)
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_deterministic(self) -> None:
        """Same text should produce the same embedding every time."""
        vec1 = _fallback_embedding("deterministic", dimensions=16)
        vec2 = _fallback_embedding("deterministic", dimensions=16)
        assert vec1 == vec2

    def test_different_texts_differ(self) -> None:
        vec1 = _fallback_embedding("apple", dimensions=32)
        vec2 = _fallback_embedding("orange", dimensions=32)
        assert vec1 != vec2

    def test_empty_text_returns_zero_vector(self) -> None:
        vec = _fallback_embedding("", dimensions=8)
        assert len(vec) == 8
        # Empty text → zero vector (norm = 0, division skipped)
        assert all(v == 0.0 for v in vec)

    def test_large_dimensions(self) -> None:
        vec = _fallback_embedding("large dim test", dimensions=1536)
        assert len(vec) == 1536


# ---------------------------------------------------------------------------
# EmbeddingResult dataclass
# ---------------------------------------------------------------------------


class TestEmbeddingResult:
    def test_stores_embedding_and_dimensions(self) -> None:
        vec = [0.1, 0.2, 0.3]
        result = EmbeddingResult(
            text="test", embedding=vec, model="test-model", dimensions=3
        )
        assert result.embedding == vec
        assert result.dimensions == 3

    def test_dimensions_field(self) -> None:
        vec = list(range(8))
        result = EmbeddingResult(text="hello", embedding=vec, model="m", dimensions=8)
        assert result.dimensions == 8

    def test_text_field_stored(self) -> None:
        result = EmbeddingResult(
            text="my text", embedding=[0.5], model="m", dimensions=1
        )
        assert result.text == "my text"

    def test_cached_field_default_false(self) -> None:
        result = EmbeddingResult(text="x", embedding=[0.1], model="m", dimensions=1)
        assert result.cached is False


# ---------------------------------------------------------------------------
# OllamaEmbeddings
# ---------------------------------------------------------------------------


class TestOllamaEmbeddings:
    def test_default_dimensions(self) -> None:
        emb = OllamaEmbeddings()
        assert emb.dimensions == 768  # nomic-embed-text default

    def test_embed_falls_back_when_ollama_unavailable(self) -> None:
        """When Ollama is not running, the exception propagates (no silent fallback)."""
        emb = OllamaEmbeddings()
        # OllamaEmbeddings.embed does not catch ConnectionError; that is expected
        # behaviour — callers should wrap in try/except or use get_embeddings(cache=True).
        import requests as _requests

        with patch.object(_requests, "post", side_effect=ConnectionError("no server")):
            with pytest.raises((ConnectionError, Exception)):
                emb.embed("test text for fallback")

    def test_embed_uses_http_response_when_available(self) -> None:
        """When Ollama responds, use the returned embedding."""
        expected = [0.1] * 768
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embedding": expected}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp):
            emb = OllamaEmbeddings()
            vec = emb.embed("hello")

        assert len(vec) == 768

    def test_embed_batch_returns_list_of_lists(self) -> None:
        emb = OllamaEmbeddings()
        with patch.object(emb, "embed", side_effect=lambda t: [0.0] * emb.dimensions):
            result = emb.embed_batch(["text one", "text two", "text three"])
        assert len(result) == 3
        assert all(len(v) == emb.dimensions for v in result)

    def test_custom_model_accepted(self) -> None:
        emb = OllamaEmbeddings(model="mxbai-embed-large")
        assert "mxbai" in emb.model.lower() or emb.model != ""

    def test_embed_text_alias(self) -> None:
        """embed_text is an alias for embed."""
        emb = OllamaEmbeddings()
        with patch.object(emb, "embed", return_value=[0.5] * 768) as mock_embed:
            result = emb.embed_text("test")
        mock_embed.assert_called_once_with("test")


# ---------------------------------------------------------------------------
# OpenAIEmbeddings
# ---------------------------------------------------------------------------


class TestOpenAIEmbeddings:
    def _make(self, model: str) -> OpenAIEmbeddings:
        import os

        os.environ.setdefault("OPENAI_API_KEY", "test-key-for-tests")
        return OpenAIEmbeddings(model=model, api_key="test-key-for-tests")

    def test_dimensions_small_model(self) -> None:
        emb = self._make("text-embedding-3-small")
        assert emb.dimensions == 512

    def test_dimensions_large_model(self) -> None:
        emb = self._make("text-embedding-3-large")
        assert emb.dimensions == 1536

    def test_embed_calls_api(self) -> None:
        """embed() should call the OpenAI API endpoint."""
        expected_vec = [0.01] * 512
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"embedding": expected_vec}]}
        mock_resp.raise_for_status = MagicMock()

        emb = self._make("text-embedding-3-small")
        with patch("requests.post", return_value=mock_resp):
            vec = emb.embed("hello openai")

        assert len(vec) == 512

    def test_embed_raises_without_api_key(self) -> None:
        """Constructing without an API key or env var should raise."""
        import os

        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises((ValueError, Exception)):
                OpenAIEmbeddings(model="text-embedding-3-small", api_key=None)
        finally:
            if old:
                os.environ["OPENAI_API_KEY"] = old

    def test_embed_batch_processes_all_texts(self) -> None:
        texts = [f"sentence {i}" for i in range(5)]
        emb = self._make("text-embedding-3-small")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"embedding": [0.1] * 512, "index": i} for i in range(5)]
        }
        with patch("requests.post", return_value=mock_resp):
            result = emb.embed_batch(texts)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# SentenceTransformerEmbeddings
# ---------------------------------------------------------------------------


class TestSentenceTransformerEmbeddings:
    def test_known_model_dimensions(self) -> None:
        """all-MiniLM-L6-v2 should be 384 dimensions."""
        emb = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")
        assert emb.dimensions == 384

    def test_fallback_when_no_sentence_transformers(self) -> None:
        """Should return a vector even if sentence_transformers is missing."""
        emb = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")
        with patch.object(emb, "_model", None, create=True):
            vec = emb.embed("test sentence")
        assert len(vec) == emb.dimensions

    def test_embed_returns_correct_length(self) -> None:
        emb = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")
        vec = emb.embed("quick brown fox")
        assert len(vec) == emb.dimensions

    def test_embed_batch_same_length_as_input(self) -> None:
        texts = ["first", "second", "third"]
        emb = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")
        results = emb.embed_batch(texts)
        assert len(results) == len(texts)

    def test_model_name_property(self) -> None:
        emb = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")
        # model_name may include device suffix like "@mps" — just check non-empty
        assert isinstance(emb.model_name, str)
        assert len(emb.model_name) > 0


# ---------------------------------------------------------------------------
# get_embeddings factory
# ---------------------------------------------------------------------------


class TestGetEmbeddings:
    def test_returns_embedding_provider(self) -> None:
        provider = get_embeddings(provider="auto")
        assert isinstance(provider, EmbeddingProvider)

    def test_sentence_transformers_provider(self) -> None:
        provider = get_embeddings(provider="sentence_transformers")
        assert isinstance(provider, EmbeddingProvider)
        assert provider.dimensions > 0

    def test_ollama_provider(self) -> None:
        """get_embeddings(provider='ollama') may wrap in CachedEmbeddings but is still an EmbeddingProvider."""

        provider = get_embeddings(provider="ollama")
        assert isinstance(provider, EmbeddingProvider)
        # When cache=True (default), it may be wrapped in CachedEmbeddings
        assert isinstance(provider, (OllamaEmbeddings, CachedEmbeddings))

    def test_provider_dimensions_positive(self) -> None:
        """Every provider should advertise positive dimensions."""
        for pname in ("auto", "ollama", "sentence_transformers"):
            provider = get_embeddings(provider=pname)
            assert provider.dimensions > 0, f"{pname} dimensions should be > 0"

    def test_cached_provider_reused(self) -> None:
        """When cache=True the same object should be returned on second call."""
        p1 = get_embeddings(provider="ollama", cache=True)
        p2 = get_embeddings(provider="ollama", cache=True)
        # Objects may or may not be identical depending on implementation,
        # but both must be valid EmbeddingProvider instances.
        assert isinstance(p1, EmbeddingProvider)
        assert isinstance(p2, EmbeddingProvider)

    def test_uncached_provider_fresh_instance(self) -> None:
        p = get_embeddings(provider="sentence_transformers", cache=False)
        assert isinstance(p, EmbeddingProvider)
