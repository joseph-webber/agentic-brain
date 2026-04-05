# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Comprehensive tests for the embeddings module.

Tests cover:
- Base embedder interface validation
- Individual embedding implementations
- Batch processing
- Rate limiting
- Error handling
- Async operations
- Normalization and similarity calculations
"""

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from agentic_brain.embeddings.base import (
    BatchEmbeddingResult,
    Embedder,
    EmbeddingProvider,
    EmbeddingResult,
)
from agentic_brain.embeddings.cohere import CohereEmbedder
from agentic_brain.embeddings.jina import JinaEmbedder
from agentic_brain.embeddings.openai import OpenAIEmbedder
from agentic_brain.embeddings.sentence_transformers import (
    E5Embedder,
    SentenceTransformersEmbedder,
)
from agentic_brain.embeddings.voyage import VoyageEmbedder

# ============================================================================
# Base Embedder Tests
# ============================================================================


class TestEmbeddingResult:
    """Test EmbeddingResult dataclass."""

    def test_embedding_result_creation(self):
        """Test creating an embedding result."""
        embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = EmbeddingResult(
            text="test",
            embedding=embedding,
            dimension=3,
            provider="test",
            model="test-model",
            tokens_used=100,
            latency_ms=50.5,
        )

        assert result.text == "test"
        assert np.array_equal(result.embedding, embedding)
        assert result.dimension == 3
        assert result.tokens_used == 100
        assert result.latency_ms == 50.5

    def test_embedding_result_without_optional_fields(self):
        """Test creating embedding result without optional fields."""
        embedding = np.array([0.1, 0.2], dtype=np.float32)
        result = EmbeddingResult(
            text="test",
            embedding=embedding,
            dimension=2,
            provider="test",
            model="test",
        )

        assert result.tokens_used is None
        assert result.latency_ms is None


class TestBatchEmbeddingResult:
    """Test BatchEmbeddingResult dataclass."""

    def test_batch_result_creation(self):
        """Test creating batch result."""
        emb1 = EmbeddingResult(
            text="a",
            embedding=np.array([0.1, 0.2], dtype=np.float32),
            dimension=2,
            provider="test",
            model="test",
        )
        emb2 = EmbeddingResult(
            text="b",
            embedding=np.array([0.3, 0.4], dtype=np.float32),
            dimension=2,
            provider="test",
            model="test",
        )

        batch_result = BatchEmbeddingResult(
            results=[emb1, emb2],
            total_texts=2,
            successful=2,
            failed=0,
            total_tokens_used=200,
            total_latency_ms=100.0,
            errors=[],
        )

        assert len(batch_result.results) == 2
        assert batch_result.successful == 2
        assert batch_result.failed == 0
        assert batch_result.total_tokens_used == 200

    def test_batch_result_with_errors(self):
        """Test batch result with errors."""
        result = BatchEmbeddingResult(
            results=[],
            total_texts=2,
            successful=1,
            failed=1,
            total_tokens_used=100,
            total_latency_ms=50.0,
            errors=[{"text": "bad", "error": "invalid"}],
        )

        assert result.failed == 1
        assert len(result.errors) == 1


class TestEmbedderValidation:
    """Test validation methods in Embedder base class."""

    class MockEmbedder(Embedder):
        """Concrete implementation for testing."""

        @property
        def provider(self):
            return EmbeddingProvider.OPENAI

        @property
        def model(self):
            return "test-model"

        @property
        def dimension(self):
            return 768

        def embed_sync(self, text: str):
            return EmbeddingResult(
                text=text,
                embedding=np.random.randn(768).astype(np.float32),
                dimension=768,
                provider="test",
                model="test",
            )

        async def embed_async(self, text: str):
            return self.embed_sync(text)

        def embed_batch_sync(self, texts, batch_size=32, show_progress=False):
            pass

        async def embed_batch_async(
            self, texts, batch_size=32, show_progress=False, concurrent_requests=5
        ):
            pass

        async def close(self):
            pass

    def test_validate_text_success(self):
        """Test successful text validation."""
        embedder = self.MockEmbedder()
        embedder.validate_text("valid text")

    def test_validate_text_empty_string(self):
        """Test validation rejects empty string."""
        embedder = self.MockEmbedder()
        with pytest.raises(ValueError, match="cannot be empty"):
            embedder.validate_text("")

    def test_validate_text_whitespace_only(self):
        """Test validation rejects whitespace-only string."""
        embedder = self.MockEmbedder()
        with pytest.raises(ValueError, match="cannot be empty"):
            embedder.validate_text("   ")

    def test_validate_text_non_string(self):
        """Test validation rejects non-string input."""
        embedder = self.MockEmbedder()
        with pytest.raises(ValueError, match="must be string"):
            embedder.validate_text(123)

    def test_validate_text_none_input(self):
        """Test validation rejects None."""
        embedder = self.MockEmbedder()
        with pytest.raises(ValueError, match="must be string"):
            embedder.validate_text(None)

    def test_validate_texts_success(self):
        """Test successful batch text validation."""
        embedder = self.MockEmbedder()
        embedder.validate_texts(["text1", "text2", "text3"])

    def test_validate_texts_empty_list(self):
        """Test validation rejects empty list."""
        embedder = self.MockEmbedder()
        with pytest.raises(ValueError, match="cannot be empty"):
            embedder.validate_texts([])

    def test_validate_texts_invalid_item(self):
        """Test validation rejects invalid item in list."""
        embedder = self.MockEmbedder()
        with pytest.raises(ValueError, match="index 1 is invalid"):
            embedder.validate_texts(["text1", "", "text3"])

    def test_validate_texts_non_list(self):
        """Test validation rejects non-list input."""
        embedder = self.MockEmbedder()
        with pytest.raises(ValueError, match="must be list"):
            embedder.validate_texts("not a list")

    def test_normalize_embedding(self):
        """Test embedding normalization."""
        embedder = self.MockEmbedder()
        embedding = np.array([3.0, 4.0], dtype=np.float32)
        normalized = embedder.normalize_embedding(embedding)

        norm = np.linalg.norm(normalized)
        assert np.isclose(norm, 1.0)

    def test_normalize_zero_embedding(self):
        """Test normalizing zero vector returns zero."""
        embedder = self.MockEmbedder()
        embedding = np.array([0.0, 0.0], dtype=np.float32)
        normalized = embedder.normalize_embedding(embedding)

        assert np.allclose(normalized, embedding)

    def test_normalize_high_dimensional(self):
        """Test normalization with high-dimensional vectors."""
        embedder = self.MockEmbedder()
        embedding = np.random.randn(768).astype(np.float32)
        normalized = embedder.normalize_embedding(embedding)

        norm = np.linalg.norm(normalized)
        assert np.isclose(norm, 1.0, atol=1e-6)

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        embedder = self.MockEmbedder()
        emb1 = np.array([1.0, 0.0], dtype=np.float32)
        emb2 = np.array([1.0, 0.0], dtype=np.float32)

        similarity = embedder.cosine_similarity(emb1, emb2)
        assert np.isclose(similarity, 1.0)

    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity of orthogonal vectors."""
        embedder = self.MockEmbedder()
        emb1 = np.array([1.0, 0.0], dtype=np.float32)
        emb2 = np.array([0.0, 1.0], dtype=np.float32)

        similarity = embedder.cosine_similarity(emb1, emb2)
        assert np.isclose(similarity, 0.0, atol=1e-6)

    def test_cosine_similarity_opposite(self):
        """Test cosine similarity of opposite vectors."""
        embedder = self.MockEmbedder()
        emb1 = np.array([1.0, 0.0], dtype=np.float32)
        emb2 = np.array([-1.0, 0.0], dtype=np.float32)

        similarity = embedder.cosine_similarity(emb1, emb2)
        assert np.isclose(similarity, -1.0)

    def test_cosine_similarity_zero_vectors(self):
        """Test cosine similarity with zero vectors."""
        embedder = self.MockEmbedder()
        emb1 = np.array([0.0, 0.0], dtype=np.float32)
        emb2 = np.array([1.0, 0.0], dtype=np.float32)

        similarity = embedder.cosine_similarity(emb1, emb2)
        assert similarity == 0.0

    def test_embedder_repr(self):
        """Test embedder string representation."""
        embedder = self.MockEmbedder()
        repr_str = repr(embedder)
        assert "MockEmbedder" in repr_str
        assert "test-model" in repr_str
        assert "768" in repr_str

    def test_embedder_provider_property(self):
        """Test embedder provider property."""
        embedder = self.MockEmbedder()
        assert embedder.provider == EmbeddingProvider.OPENAI

    def test_embedder_model_property(self):
        """Test embedder model property."""
        embedder = self.MockEmbedder()
        assert embedder.model == "test-model"

    def test_embedder_dimension_property(self):
        """Test embedder dimension property."""
        embedder = self.MockEmbedder()
        assert embedder.dimension == 768


# ============================================================================
# OpenAI Embedder Tests
# ============================================================================


class TestOpenAIEmbedder:
    """Test OpenAI embedder implementation."""

    def test_init_without_api_key_fails(self):
        """Test initialization fails without API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIEmbedder()

    def test_init_with_api_key(self):
        """Test successful initialization with API key."""
        with patch("agentic_brain.embeddings.openai.OpenAI"):
            embedder = OpenAIEmbedder(api_key="test-key")
            assert embedder.api_key == "test-key"

    def test_init_from_env_var(self):
        """Test initialization from environment variable."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            with patch("agentic_brain.embeddings.openai.OpenAI"):
                embedder = OpenAIEmbedder()
                assert embedder.api_key == "env-key"

    def test_model_dimensions(self):
        """Test known model dimensions."""
        with patch("agentic_brain.embeddings.openai.OpenAI"):
            embedder_small = OpenAIEmbedder(
                api_key="test", model="text-embedding-3-small"
            )
            assert embedder_small.dimension == 1536

            embedder_large = OpenAIEmbedder(
                api_key="test", model="text-embedding-3-large"
            )
            assert embedder_large.dimension == 3072

            embedder_ada = OpenAIEmbedder(
                api_key="test", model="text-embedding-ada-002"
            )
            assert embedder_ada.dimension == 1536

    def test_unknown_model_fails(self):
        """Test initialization fails with unknown model."""
        with patch("agentic_brain.embeddings.openai.OpenAI"):
            with pytest.raises(ValueError, match="Unknown OpenAI model"):
                OpenAIEmbedder(api_key="test", model="unknown-model")

    def test_provider_property(self):
        """Test provider property returns correct value."""
        with patch("agentic_brain.embeddings.openai.OpenAI"):
            embedder = OpenAIEmbedder(api_key="test")
            assert embedder.provider == EmbeddingProvider.OPENAI

    def test_model_property(self):
        """Test model property returns correct value."""
        with patch("agentic_brain.embeddings.openai.OpenAI"):
            embedder = OpenAIEmbedder(api_key="test", model="text-embedding-3-large")
            assert embedder.model == "text-embedding-3-large"

    @patch("agentic_brain.embeddings.openai.OpenAI")
    def test_embed_sync_success(self, mock_openai_class):
        """Test successful synchronous embedding."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_response.usage.total_tokens = 10
        mock_client.embeddings.create.return_value = mock_response

        embedder = OpenAIEmbedder(api_key="test")
        result = embedder.embed_sync("test text")

        assert result.text == "test text"
        assert len(result.embedding) == 3
        assert result.tokens_used == 10
        assert result.dimension == 1536

    @patch("agentic_brain.embeddings.openai.OpenAI")
    def test_embed_sync_invalid_text(self, mock_openai_class):
        """Test embedding fails with invalid text."""
        mock_openai_class.return_value = MagicMock()
        embedder = OpenAIEmbedder(api_key="test")

        with pytest.raises(ValueError, match="cannot be empty"):
            embedder.embed_sync("")

    @patch("agentic_brain.embeddings.openai.OpenAI")
    def test_embed_sync_with_retries(self, mock_openai_class):
        """Test retry logic on API failure."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_response.usage.total_tokens = 10

        mock_client.embeddings.create.side_effect = [
            Exception("Rate limit"),
            Exception("Rate limit"),
            mock_response,
        ]

        embedder = OpenAIEmbedder(api_key="test", max_retries=3)
        result = embedder.embed_sync("test text")

        assert result.text == "test text"
        assert mock_client.embeddings.create.call_count == 3

    @patch("agentic_brain.embeddings.openai.OpenAI")
    def test_embed_sync_max_retries_exceeded(self, mock_openai_class):
        """Test failure after max retries exceeded."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.embeddings.create.side_effect = Exception("API Error")

        embedder = OpenAIEmbedder(api_key="test", max_retries=2)
        with pytest.raises(RuntimeError, match="Failed to embed text"):
            embedder.embed_sync("test text")

    @patch("agentic_brain.embeddings.openai.OpenAI")
    def test_rate_limiting(self, mock_openai_class):
        """Test rate limiting is applied."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data[0].embedding = [0.1]
        mock_response.usage.total_tokens = 1
        mock_client.embeddings.create.return_value = mock_response

        embedder = OpenAIEmbedder(api_key="test", rate_limit=100)
        assert embedder.min_request_interval > 0


# ============================================================================
# Cohere Embedder Tests
# ============================================================================


class TestCohereEmbedder:
    """Test Cohere embedder implementation."""

    def test_init_without_api_key_fails(self):
        """Test initialization fails without API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="COHERE_API_KEY"):
                CohereEmbedder()

    def test_init_with_api_key(self):
        """Test successful initialization."""
        with patch("agentic_brain.embeddings.cohere.cohere"):
            embedder = CohereEmbedder(api_key="test-key")
            assert embedder.api_key == "test-key"

    def test_model_dimensions(self):
        """Test known model dimensions."""
        with patch("agentic_brain.embeddings.cohere.cohere"):
            embedder_v3 = CohereEmbedder(api_key="test", model="embed-english-v3.0")
            assert embedder_v3.dimension == 1024

            embedder_light = CohereEmbedder(
                api_key="test", model="embed-english-light-v3.0"
            )
            assert embedder_light.dimension == 384

            embedder_multilingual = CohereEmbedder(
                api_key="test", model="embed-multilingual-v3.0"
            )
            assert embedder_multilingual.dimension == 1024

    def test_provider_property(self):
        """Test provider property."""
        with patch("agentic_brain.embeddings.cohere.cohere"):
            embedder = CohereEmbedder(api_key="test")
            assert embedder.provider == EmbeddingProvider.COHERE

    def test_input_type_parameter(self):
        """Test input_type parameter."""
        with patch("agentic_brain.embeddings.cohere.cohere"):
            embedder = CohereEmbedder(api_key="test", input_type="search_query")
            assert embedder.input_type == "search_query"

    def test_unknown_model_fails(self):
        """Test initialization fails with unknown model."""
        with patch("agentic_brain.embeddings.cohere.cohere"):
            with pytest.raises(ValueError, match="Unknown Cohere model"):
                CohereEmbedder(api_key="test", model="unknown")


# ============================================================================
# Sentence Transformers Tests
# ============================================================================


class TestSentenceTransformersEmbedder:
    """Test Sentence Transformers embedder."""

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_init_default_device_detection(self, mock_st):
        """Test automatic device detection."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
        assert embedder.device in ["cpu", "cuda", "mps"]

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_init_with_explicit_device(self, mock_st):
        """Test initialization with explicit device."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2", device="cpu")
        assert embedder.device == "cpu"

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_model_dimensions(self, mock_st):
        """Test known model dimensions."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-mpnet-base-v2")
        assert embedder.dimension == 768

        embedder_mini = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
        assert embedder_mini.dimension == 384

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_embed_sync(self, mock_st):
        """Test synchronous embedding."""
        mock_model = MagicMock()
        embedding = np.random.randn(384).astype(np.float32)
        mock_model.encode.return_value = embedding
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
        result = embedder.embed_sync("test text")

        assert result.text == "test text"
        assert len(result.embedding) == 384
        assert result.provider == "sentence_transformers"

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_embed_batch_sync(self, mock_st):
        """Test batch embedding."""
        mock_model = MagicMock()
        embeddings = np.random.randn(3, 384).astype(np.float32)
        mock_model.encode.return_value = embeddings
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
        texts = ["text1", "text2", "text3"]
        result = embedder.embed_batch_sync(texts)

        assert len(result.results) == 3
        assert result.successful == 3
        assert result.total_texts == 3
        assert result.failed == 0

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_normalize_embeddings_parameter(self, mock_st):
        """Test normalize_embeddings parameter."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(
            model="all-MiniLM-L6-v2", normalize_embeddings=False
        )
        assert embedder.normalize_embeddings is False

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_provider_property(self, mock_st):
        """Test provider property."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
        assert embedder.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS


# ============================================================================
# E5 Embedder Tests
# ============================================================================


class TestE5Embedder:
    """Test E5 embedder implementation."""

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_e5_embed_with_query_prefix(self, mock_st):
        """Test E5 embedding with query prefix."""
        mock_model = MagicMock()
        embedding = np.random.randn(384).astype(np.float32)
        mock_model.encode.return_value = embedding
        mock_st.return_value = mock_model

        embedder = E5Embedder(model="intfloat/e5-small")
        result = embedder.embed_sync("test query", task_type="query")

        assert result.text == "test query"
        mock_model.encode.assert_called_with(
            "query: test query",
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_e5_embed_with_passage_prefix(self, mock_st):
        """Test E5 embedding with passage prefix."""
        mock_model = MagicMock()
        embedding = np.random.randn(384).astype(np.float32)
        mock_model.encode.return_value = embedding
        mock_st.return_value = mock_model

        embedder = E5Embedder(model="intfloat/e5-small")
        result = embedder.embed_sync("test passage", task_type="passage")

        assert result.text == "test passage"
        mock_model.encode.assert_called_with(
            "passage: test passage",
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_e5_batch_with_prefixes(self, mock_st):
        """Test E5 batch embedding with task type."""
        mock_model = MagicMock()
        embeddings = np.random.randn(2, 384).astype(np.float32)
        mock_model.encode.return_value = embeddings
        mock_st.return_value = mock_model

        embedder = E5Embedder(model="intfloat/e5-small")
        result = embedder.embed_batch_sync(["query1", "query2"], task_type="query")

        assert len(result.results) == 2
        assert result.successful == 2

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_e5_model_dimensions(self, mock_st):
        """Test E5 model dimensions."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        embedder_small = E5Embedder(model="intfloat/e5-small")
        assert embedder_small.dimension == 384

        embedder_base = E5Embedder(model="intfloat/e5-base")
        assert embedder_base.dimension == 768

        embedder_large = E5Embedder(model="intfloat/e5-large")
        assert embedder_large.dimension == 1024


# ============================================================================
# Voyage Embedder Tests
# ============================================================================


class TestVoyageEmbedder:
    """Test Voyage AI embedder."""

    def test_init_without_api_key_fails(self):
        """Test initialization fails without API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="VOYAGE_API_KEY"):
                VoyageEmbedder()

    def test_init_with_api_key(self):
        """Test successful initialization."""
        with patch("agentic_brain.embeddings.voyage.voyageai"):
            embedder = VoyageEmbedder(api_key="test-key")
            assert embedder.api_key == "test-key"

    def test_model_dimensions(self):
        """Test known model dimensions."""
        with patch("agentic_brain.embeddings.voyage.voyageai"):
            embedder = VoyageEmbedder(api_key="test", model="voyage-2")
            assert embedder.dimension == 1024

            embedder_large = VoyageEmbedder(api_key="test", model="voyage-large-2")
            assert embedder_large.dimension == 1536

            embedder_law = VoyageEmbedder(api_key="test", model="voyage-law-2")
            assert embedder_law.dimension == 1024

    def test_provider_property(self):
        """Test provider property."""
        with patch("agentic_brain.embeddings.voyage.voyageai"):
            embedder = VoyageEmbedder(api_key="test")
            assert embedder.provider == EmbeddingProvider.VOYAGE

    def test_input_type_parameter(self):
        """Test input_type parameter."""
        with patch("agentic_brain.embeddings.voyage.voyageai"):
            embedder = VoyageEmbedder(api_key="test", input_type="query")
            assert embedder.input_type == "query"

    def test_unknown_model_fails(self):
        """Test initialization fails with unknown model."""
        with patch("agentic_brain.embeddings.voyage.voyageai"):
            with pytest.raises(ValueError, match="Unknown Voyage model"):
                VoyageEmbedder(api_key="test", model="unknown")


# ============================================================================
# Jina Embedder Tests
# ============================================================================


class TestJinaEmbedder:
    """Test Jina AI embedder."""

    def test_init_without_api_key_fails(self):
        """Test initialization fails without API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="JINA_API_KEY"):
                JinaEmbedder()

    def test_init_with_api_key(self):
        """Test successful initialization."""
        with patch("agentic_brain.embeddings.jina.JinaAI"):
            embedder = JinaEmbedder(api_key="test-key")
            assert embedder.api_key == "test-key"

    def test_model_dimensions(self):
        """Test known model dimensions."""
        with patch("agentic_brain.embeddings.jina.JinaAI"):
            embedder = JinaEmbedder(api_key="test", model="jina-embeddings-v2-base-en")
            assert embedder.dimension == 512

            embedder_small = JinaEmbedder(
                api_key="test", model="jina-embeddings-v2-small-en"
            )
            assert embedder_small.dimension == 384

    def test_provider_property(self):
        """Test provider property."""
        with patch("agentic_brain.embeddings.jina.JinaAI"):
            embedder = JinaEmbedder(api_key="test")
            assert embedder.provider == EmbeddingProvider.JINA

    def test_task_parameter(self):
        """Test task parameter."""
        with patch("agentic_brain.embeddings.jina.JinaAI"):
            embedder = JinaEmbedder(api_key="test", task="retrieval.query")
            assert embedder.task == "retrieval.query"

    def test_unknown_model_fails(self):
        """Test initialization fails with unknown model."""
        with patch("agentic_brain.embeddings.jina.JinaAI"):
            with pytest.raises(ValueError, match="Unknown Jina model"):
                JinaEmbedder(api_key="test", model="unknown")


# ============================================================================
# Integration and Edge Case Tests
# ============================================================================


class TestEmbeddingProviderEnum:
    """Test EmbeddingProvider enum."""

    def test_provider_values(self):
        """Test all provider values are accessible."""
        assert EmbeddingProvider.OPENAI.value == "openai"
        assert EmbeddingProvider.COHERE.value == "cohere"
        assert EmbeddingProvider.SENTENCE_TRANSFORMERS.value == "sentence_transformers"
        assert EmbeddingProvider.VOYAGE.value == "voyage"
        assert EmbeddingProvider.JINA.value == "jina"

    def test_provider_comparison(self):
        """Test provider comparison."""
        assert EmbeddingProvider.OPENAI == EmbeddingProvider.OPENAI
        assert EmbeddingProvider.OPENAI != EmbeddingProvider.COHERE

    def test_all_providers_accounted_for(self):
        """Test all providers have unique values."""
        providers = [p.value for p in EmbeddingProvider]
        assert len(providers) == len(set(providers))


class TestEmbeddingDimensionConsistency:
    """Test that dimensions are consistent across implementations."""

    @patch("agentic_brain.embeddings.openai.OpenAI")
    @patch("agentic_brain.embeddings.cohere.cohere")
    def test_model_dimension_consistency(self, mock_cohere, mock_openai):
        """Test dimension consistency across providers."""
        openai_small = OpenAIEmbedder(api_key="test", model="text-embedding-3-small")
        assert openai_small.dimension == 1536

        cohere_v3 = CohereEmbedder(api_key="test", model="embed-english-v3.0")
        assert cohere_v3.dimension == 1024

        with patch("agentic_brain.embeddings.voyage.voyageai"):
            voyage_2 = VoyageEmbedder(api_key="test", model="voyage-2")
            assert voyage_2.dimension == 1024


class TestErrorHandling:
    """Test error handling across implementations."""

    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    def test_batch_embedding_with_errors(self, mock_st):
        """Test batch embedding handles partial failures."""
        mock_model = MagicMock()
        mock_model.encode.side_effect = Exception("Model error")
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
        texts = ["text1", "text2", "text3"]
        result = embedder.embed_batch_sync(texts)

        assert result.total_texts == 3
        assert result.failed >= 0

    def test_api_key_environment_variable_priority(self):
        """Test that explicit API key takes priority over env var."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            with patch("agentic_brain.embeddings.openai.OpenAI"):
                embedder = OpenAIEmbedder(api_key="explicit-key")
                assert embedder.api_key == "explicit-key"


# ============================================================================
# Async Tests
# ============================================================================


class TestAsyncEmbedding:
    """Test asynchronous embedding operations."""

    @pytest.mark.asyncio
    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    async def test_sentence_transformers_embed_async(self, mock_st):
        """Test async embedding with SentenceTransformers."""
        mock_model = MagicMock()
        embedding = np.random.randn(384).astype(np.float32)
        mock_model.encode.return_value = embedding
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
        result = await embedder.embed_async("test text")

        assert result.text == "test text"
        assert len(result.embedding) == 384

    @pytest.mark.asyncio
    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    async def test_sentence_transformers_batch_async(self, mock_st):
        """Test async batch embedding."""
        mock_model = MagicMock()
        embeddings = np.random.randn(3, 384).astype(np.float32)
        mock_model.encode.return_value = embeddings
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
        texts = ["text1", "text2", "text3"]
        result = await embedder.embed_batch_async(texts)

        assert result.total_texts == 3
        assert len(result.results) == 3

    @pytest.mark.asyncio
    @patch("agentic_brain.embeddings.sentence_transformers.SentenceTransformer")
    async def test_close_async(self, mock_st):
        """Test closing async resources."""
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
        await embedder.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
