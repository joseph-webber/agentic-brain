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

"""
Comprehensive tests for RAG pipeline - document retrieval and generation.

Tests for:
- RAGResult dataclass
- RAGPipeline initialization and configuration
- Query pipeline (retrieval + generation)
- Caching functionality
- Document management
- Streaming responses
- Error handling and edge cases
- Convenience functions
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.pipeline import (
    CACHE_DIR,
    RAGPipeline,
    RAGResult,
    ask,
)
from agentic_brain.rag.retriever import RetrievedChunk

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_embedding_provider():
    """Mock embedding provider that returns deterministic embeddings."""
    mock = MagicMock()
    # Return a 384-dim vector (common for sentence-transformers)
    mock.embed.return_value = [0.1] * 384
    return mock


@pytest.fixture
def mock_retriever():
    """Mock retriever that returns sample chunks."""
    mock = MagicMock()
    mock.search.return_value = [
        RetrievedChunk(
            content="The deployment process involves running the CI/CD pipeline.",
            source="Document",
            score=0.85,
            metadata={"title": "Deployment Guide"},
        ),
        RetrievedChunk(
            content="Make sure all tests pass before deploying.",
            source="Knowledge",
            score=0.72,
            metadata={"type": "best_practice"},
        ),
    ]
    mock.close.return_value = None
    return mock


@pytest.fixture
def mock_document_store():
    """Mock document store."""
    mock = MagicMock()
    mock.add.return_value = MagicMock(
        id="doc-123",
        content="Test document content",
        chunks=["Test", "document", "content"],
    )
    mock.list.return_value = []
    mock.search.return_value = []
    mock.stats.return_value = {"document_count": 5, "total_chunks": 25}
    return mock


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    """Sample retrieved chunks for testing."""
    return [
        RetrievedChunk(
            content="First relevant document about deployments.",
            source="Document",
            score=0.9,
            metadata={"title": "Deploy Guide"},
        ),
        RetrievedChunk(
            content="Second document about testing best practices.",
            source="Knowledge",
            score=0.75,
            metadata={"category": "testing"},
        ),
        RetrievedChunk(
            content="Third document with lower relevance.",
            source="Memory",
            score=0.4,
            metadata={},
        ),
    ]


@pytest.fixture
def rag_pipeline_with_mocks(mock_retriever, mock_embedding_provider):
    """RAG pipeline with mocked dependencies."""
    with patch("agentic_brain.rag.pipeline.Retriever") as MockRetriever:
        MockRetriever.return_value = mock_retriever
        pipeline = RAGPipeline(
            embedding_provider=mock_embedding_provider,
            llm_provider="ollama",
            llm_model="llama3.1:8b",
        )
        # Replace the retriever directly
        pipeline.retriever = mock_retriever
        yield pipeline
        pipeline.close()


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary cache directory."""
    cache_dir = tmp_path / "rag_cache"
    cache_dir.mkdir()
    return cache_dir


# =============================================================================
# RAGResult Tests
# =============================================================================


class TestRAGResult:
    """Tests for RAGResult dataclass."""

    def test_basic_creation(self, sample_chunks):
        """Test basic RAGResult creation."""
        result = RAGResult(
            query="How do I deploy?",
            answer="Run the deployment script.",
            sources=sample_chunks,
            confidence=0.85,
            model="ollama/llama3.1:8b",
        )

        assert result.query == "How do I deploy?"
        assert result.answer == "Run the deployment script."
        assert len(result.sources) == 3
        assert result.confidence == 0.85
        assert result.model == "ollama/llama3.1:8b"
        assert result.cached is False
        assert result.generation_time_ms == 0

    def test_has_sources_true(self, sample_chunks):
        """Test has_sources property when sources exist."""
        result = RAGResult(
            query="test",
            answer="answer",
            sources=sample_chunks,
            confidence=0.8,
            model="test",
        )
        assert result.has_sources is True

    def test_has_sources_false(self):
        """Test has_sources property when no sources."""
        result = RAGResult(
            query="test",
            answer="answer",
            sources=[],
            confidence=0.0,
            model="test",
        )
        assert result.has_sources is False

    @pytest.mark.parametrize(
        "confidence,expected_level",
        [
            (0.95, "high"),
            (0.8, "high"),
            (0.79, "medium"),
            (0.5, "medium"),
            (0.49, "low"),
            (0.3, "low"),
            (0.29, "uncertain"),
            (0.0, "uncertain"),
        ],
    )
    def test_confidence_level(self, confidence, expected_level):
        """Test confidence_level property with different values."""
        result = RAGResult(
            query="test",
            answer="answer",
            sources=[],
            confidence=confidence,
            model="test",
        )
        assert result.confidence_level == expected_level

    def test_to_dict(self, sample_chunks):
        """Test serialization to dictionary."""
        result = RAGResult(
            query="How to test?",
            answer="Write unit tests.",
            sources=sample_chunks,
            confidence=0.75,
            model="ollama/llama3.1:8b",
        )

        data = result.to_dict()

        assert data["query"] == "How to test?"
        assert data["answer"] == "Write unit tests."
        assert data["confidence"] == 0.75
        assert data["confidence_level"] == "medium"
        assert data["model"] == "ollama/llama3.1:8b"
        assert len(data["sources"]) == 3
        # Sources should be truncated to 200 chars
        assert all(len(s["content"]) <= 200 for s in data["sources"])

    def test_format_with_citations(self, sample_chunks):
        """Test formatting with source citations."""
        result = RAGResult(
            query="What is deployment?",
            answer="Deployment is the process of releasing software.",
            sources=sample_chunks,
            confidence=0.9,
            model="test",
        )

        formatted = result.format_with_citations()

        assert "Deployment is the process" in formatted
        assert "---" in formatted
        assert "Sources:" in formatted
        assert "[1]" in formatted
        assert "Document" in formatted
        # Only top 3 sources shown
        assert formatted.count("[") <= 4  # [1], [2], [3] max


# =============================================================================
# RAGPipeline Initialization Tests
# =============================================================================


class TestRAGPipelineInit:
    """Tests for RAGPipeline initialization."""

    def test_default_initialization(self, mock_embedding_provider):
        """Test pipeline with default configuration."""
        with patch("agentic_brain.rag.pipeline.Retriever") as MockRetriever:
            MockRetriever.return_value = MagicMock()
            pipeline = RAGPipeline(embedding_provider=mock_embedding_provider)

            assert pipeline.llm_provider == "ollama"
            assert pipeline.llm_model == "llama3.1:8b"
            assert pipeline.llm_base_url == "http://localhost:11434"
            assert pipeline.cache_ttl_hours == 4
            assert pipeline._document_store is None

            pipeline.close()

    def test_custom_configuration(self, mock_embedding_provider, mock_document_store):
        """Test pipeline with custom configuration."""
        with patch("agentic_brain.rag.pipeline.Retriever") as MockRetriever:
            MockRetriever.return_value = MagicMock()
            pipeline = RAGPipeline(
                neo4j_uri="bolt://custom:7687",
                neo4j_user="admin",
                neo4j_password="Brain2026",
                embedding_provider=mock_embedding_provider,
                llm_provider="openai",
                llm_model="gpt-4",
                llm_base_url="https://custom.api.com",
                cache_ttl_hours=12,
                document_store=mock_document_store,
            )

            assert pipeline.llm_provider == "openai"
            assert pipeline.llm_model == "gpt-4"
            assert pipeline.llm_base_url == "https://custom.api.com"
            assert pipeline.cache_ttl_hours == 12
            assert pipeline._document_store is mock_document_store

            pipeline.close()


# =============================================================================
# Caching Tests
# =============================================================================


class TestRAGPipelineCache:
    """Tests for RAG pipeline caching functionality."""

    def test_cache_key_generation(self, rag_pipeline_with_mocks):
        """Test cache key generation is deterministic."""
        key1 = rag_pipeline_with_mocks._cache_key("query1", ["Document", "Memory"])
        key2 = rag_pipeline_with_mocks._cache_key("query1", ["Document", "Memory"])
        key3 = rag_pipeline_with_mocks._cache_key("query2", ["Document", "Memory"])
        key4 = rag_pipeline_with_mocks._cache_key("query1", ["Document"])

        assert key1 == key2  # Same input = same key
        assert key1 != key3  # Different query = different key
        assert key1 != key4  # Different sources = different key

    def test_cache_key_source_order_independent(self, rag_pipeline_with_mocks):
        """Test that source order doesn't affect cache key."""
        key1 = rag_pipeline_with_mocks._cache_key("query", ["A", "B", "C"])
        key2 = rag_pipeline_with_mocks._cache_key("query", ["C", "A", "B"])

        assert key1 == key2  # Order shouldn't matter

    def test_set_and_get_cached(self, rag_pipeline_with_mocks, sample_chunks, tmp_path):
        """Test caching a result and retrieving it."""
        with patch("agentic_brain.rag.pipeline.CACHE_DIR", tmp_path):
            result = RAGResult(
                query="test query",
                answer="test answer",
                sources=sample_chunks,
                confidence=0.8,
                model="test/model",
            )

            cache_key = "test_cache_key"
            rag_pipeline_with_mocks._set_cached(cache_key, result)

            # Retrieve from cache
            cached = rag_pipeline_with_mocks._get_cached(cache_key)

            assert cached is not None
            assert cached.query == "test query"
            assert cached.answer == "test answer"
            assert cached.confidence == 0.8
            assert cached.model == "test/model"
            assert cached.cached is True
            # Sources are not cached
            assert len(cached.sources) == 0

    def test_cache_expired(self, rag_pipeline_with_mocks, tmp_path):
        """Test that expired cache entries are not returned."""
        with patch("agentic_brain.rag.pipeline.CACHE_DIR", tmp_path):
            # Set pipeline with 1 hour TTL
            rag_pipeline_with_mocks.cache_ttl_hours = 1

            # Create cache file with old timestamp
            cache_file = tmp_path / "old_cache.json"
            old_time = datetime.now() - timedelta(hours=2)
            cache_data = {
                "query": "old query",
                "answer": "old answer",
                "confidence": 0.5,
                "model": "old/model",
                "timestamp": old_time.isoformat(),
            }
            cache_file.write_text(json.dumps(cache_data))

            # Should return None for expired cache
            cached = rag_pipeline_with_mocks._get_cached("old_cache")
            assert cached is None

    def test_cache_corrupted(self, rag_pipeline_with_mocks, tmp_path):
        """Test graceful handling of corrupted cache files."""
        with patch("agentic_brain.rag.pipeline.CACHE_DIR", tmp_path):
            cache_file = tmp_path / "corrupted.json"
            cache_file.write_text("not valid json {{{")

            cached = rag_pipeline_with_mocks._get_cached("corrupted")
            assert cached is None  # Should handle gracefully

    def test_cache_missing_fields(self, rag_pipeline_with_mocks, tmp_path):
        """Test handling of cache files with missing fields."""
        with patch("agentic_brain.rag.pipeline.CACHE_DIR", tmp_path):
            cache_file = tmp_path / "incomplete.json"
            cache_data = {"query": "test"}  # Missing required fields
            cache_file.write_text(json.dumps(cache_data))

            cached = rag_pipeline_with_mocks._get_cached("incomplete")
            assert cached is None


# =============================================================================
# Context Building Tests
# =============================================================================


class TestContextBuilding:
    """Tests for context building from retrieved chunks."""

    def test_build_context_basic(self, rag_pipeline_with_mocks, sample_chunks):
        """Test basic context building."""
        context = rag_pipeline_with_mocks._build_context(sample_chunks)

        assert "First relevant document" in context
        assert "Second document" in context
        assert "[Source: Document]" in context
        assert "[Source: Knowledge]" in context

    def test_build_context_token_limit(self, rag_pipeline_with_mocks):
        """Test context building respects token limits."""
        # Create chunks that would exceed limits
        large_chunks = [
            RetrievedChunk(
                content="A" * 5000,  # Very large content
                source="Doc",
                score=0.9,
                metadata={},
            )
            for _ in range(10)
        ]

        context = rag_pipeline_with_mocks._build_context(large_chunks, max_tokens=1000)

        # Context should be limited (max_tokens * 4 chars)
        assert len(context) <= 5000  # Some buffer for source labels

    def test_build_context_empty_chunks(self, rag_pipeline_with_mocks):
        """Test context building with no chunks."""
        context = rag_pipeline_with_mocks._build_context([])
        assert context == ""


# =============================================================================
# LLM Generation Tests
# =============================================================================


class TestLLMGeneration:
    """Tests for LLM generation methods."""

    def test_generate_ollama_success(self, rag_pipeline_with_mocks):
        """Test successful Ollama generation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Generated answer"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            result = rag_pipeline_with_mocks._generate_ollama(
                "What is X?", "Context here"
            )

            assert result == "Generated answer"

    def test_generate_ollama_with_custom_url(self):
        """Test Ollama generation with custom base URL."""
        with patch("agentic_brain.rag.pipeline.Retriever"):
            pipeline = RAGPipeline(
                llm_provider="ollama",
                llm_base_url="http://custom:11434",
            )

            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "Custom answer"}
            mock_response.raise_for_status.return_value = None

            with patch("requests.post", return_value=mock_response) as mock_post:
                pipeline._generate_ollama("Query", "Context")

                # Verify correct URL was called
                call_args = mock_post.call_args
                assert "http://custom:11434/api/generate" in call_args[0][0]

            pipeline.close()

    def test_generate_openai_success(self, monkeypatch):
        """Test successful OpenAI generation."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        with patch("agentic_brain.rag.pipeline.Retriever"):
            pipeline = RAGPipeline(llm_provider="openai", llm_model="gpt-4")

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "OpenAI answer"}}]
            }
            mock_response.raise_for_status.return_value = None

            with patch("requests.post", return_value=mock_response):
                result = pipeline._generate_openai("What is X?", "Context")

                assert result == "OpenAI answer"

            pipeline.close()

    def test_generate_openai_missing_key(self):
        """Test OpenAI generation without API key."""
        with patch("agentic_brain.rag.pipeline.Retriever"):
            with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=True):
                pipeline = RAGPipeline(llm_provider="openai")

                with pytest.raises(ValueError, match="OPENAI_API_KEY required"):
                    pipeline._generate_openai("Query", "Context")

                pipeline.close()

    def test_generate_unknown_provider(self, rag_pipeline_with_mocks):
        """Test generation with unknown provider raises error."""
        rag_pipeline_with_mocks.llm_provider = "unknown"

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            rag_pipeline_with_mocks._generate("Query", "Context")


# =============================================================================
# Query Pipeline Tests
# =============================================================================


class TestQueryPipeline:
    """Tests for the main query pipeline."""

    def test_query_basic_flow(self, rag_pipeline_with_mocks, mock_retriever):
        """Test basic query flow."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "The deployment process is..."}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            result = rag_pipeline_with_mocks.query(
                "How do I deploy?",
                k=5,
                use_cache=False,
            )

            assert isinstance(result, RAGResult)
            assert result.query == "How do I deploy?"
            assert "deployment" in result.answer.lower()
            assert result.has_sources
            assert result.generation_time_ms > 0
            mock_retriever.search.assert_called()

    @patch.dict("os.environ", {"RAG_CACHE_ENABLED": "true"})
    def test_query_with_caching(self, rag_pipeline_with_mocks, tmp_path):
        """Test that query results are cached."""
        with patch("agentic_brain.rag.pipeline.CACHE_DIR", tmp_path):
            mock_response = MagicMock()
            mock_response.json.return_value = {"response": "Cached answer"}
            mock_response.raise_for_status.return_value = None

            with patch("requests.post", return_value=mock_response) as mock_post:
                # First query - should call LLM
                rag_pipeline_with_mocks.query("Test query", use_cache=True)
                first_call_count = mock_post.call_count

                # Second query - should use cache
                result2 = rag_pipeline_with_mocks.query("Test query", use_cache=True)

                assert mock_post.call_count == first_call_count  # No additional calls
                assert result2.cached is True

    def test_query_cache_disabled(self, rag_pipeline_with_mocks):
        """Test query with caching disabled."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Fresh answer"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response) as mock_post:
            # Two queries with cache disabled
            rag_pipeline_with_mocks.query("Same query", use_cache=False)
            rag_pipeline_with_mocks.query("Same query", use_cache=False)

            # Both should call LLM
            assert mock_post.call_count == 2

    def test_query_min_score_filtering(self, rag_pipeline_with_mocks, mock_retriever):
        """Test that chunks below min_score are filtered."""
        # Return mix of high and low score chunks
        mock_retriever.search.return_value = [
            RetrievedChunk(content="High score", source="Doc", score=0.9, metadata={}),
            RetrievedChunk(content="Low score", source="Doc", score=0.1, metadata={}),
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Answer"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            result = rag_pipeline_with_mocks.query(
                "Test", min_score=0.5, use_cache=False
            )

            # Only high score chunk should be in sources
            assert len(result.sources) == 1
            assert result.sources[0].score >= 0.5

    def test_query_no_relevant_context(self, rag_pipeline_with_mocks, mock_retriever):
        """Test query when no relevant context is found."""
        # Return chunks below min_score threshold
        mock_retriever.search.return_value = [
            RetrievedChunk(content="Irrelevant", source="Doc", score=0.1, metadata={}),
        ]

        result = rag_pipeline_with_mocks.query("Test", min_score=0.5, use_cache=False)

        assert "don't have enough information" in result.answer
        assert result.confidence == 0.0

    def test_query_custom_sources(self, rag_pipeline_with_mocks, mock_retriever):
        """Test query with custom sources."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Answer"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            rag_pipeline_with_mocks.query(
                "Test",
                sources=["JiraTicket", "Email"],
                use_cache=False,
            )

            # Verify sources were passed to retriever
            call_args = mock_retriever.search.call_args
            assert call_args.kwargs.get("sources") == ["JiraTicket", "Email"]

    def test_query_confidence_calculation(
        self, rag_pipeline_with_mocks, mock_retriever
    ):
        """Test confidence is calculated from source scores."""
        mock_retriever.search.return_value = [
            RetrievedChunk(content="Doc1", source="Doc", score=0.8, metadata={}),
            RetrievedChunk(content="Doc2", source="Doc", score=0.6, metadata={}),
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Answer"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            result = rag_pipeline_with_mocks.query("Test", use_cache=False)

            # Confidence should be average of source scores
            expected_confidence = (0.8 + 0.6) / 2
            assert abs(result.confidence - expected_confidence) < 0.01


# =============================================================================
# Document Management Tests
# =============================================================================


class TestDocumentManagement:
    """Tests for document management functionality."""

    def test_add_document_success(self, rag_pipeline_with_mocks, mock_document_store):
        """Test adding a document successfully."""
        rag_pipeline_with_mocks._document_store = mock_document_store

        rag_pipeline_with_mocks.add_document(
            content="New document content",
            metadata={"title": "Test Doc"},
            doc_id="custom-id",
        )

        mock_document_store.add.assert_called_once_with(
            "New document content",
            {"title": "Test Doc"},
            "custom-id",
        )

    def test_add_document_no_store(self, rag_pipeline_with_mocks):
        """Test adding document without configured store raises error."""
        rag_pipeline_with_mocks._document_store = None

        with pytest.raises(RuntimeError, match="No document store configured"):
            rag_pipeline_with_mocks.add_document("content")

    def test_list_documents_with_store(
        self, rag_pipeline_with_mocks, mock_document_store
    ):
        """Test listing documents with store configured."""
        rag_pipeline_with_mocks._document_store = mock_document_store
        mock_document_store.list.return_value = [
            MagicMock(id="doc1"),
            MagicMock(id="doc2"),
        ]

        docs = rag_pipeline_with_mocks.list_documents(limit=50)

        mock_document_store.list.assert_called_once_with(limit=50)
        assert len(docs) == 2

    def test_list_documents_no_store(self, rag_pipeline_with_mocks):
        """Test listing documents without store returns empty list."""
        rag_pipeline_with_mocks._document_store = None

        docs = rag_pipeline_with_mocks.list_documents()

        assert docs == []


# =============================================================================
# Statistics Tests
# =============================================================================


class TestPipelineStats:
    """Tests for pipeline statistics."""

    def test_get_stats_basic(self, rag_pipeline_with_mocks):
        """Test getting basic pipeline stats."""
        stats = rag_pipeline_with_mocks.get_stats()

        assert stats["llm_provider"] == "ollama"
        assert stats["llm_model"] == "llama3.1:8b"
        assert stats["cache_ttl_hours"] == 4
        assert stats["document_count"] == 0
        assert stats["total_chunks"] == 0

    def test_get_stats_with_document_store(
        self, rag_pipeline_with_mocks, mock_document_store
    ):
        """Test getting stats with document store configured."""
        rag_pipeline_with_mocks._document_store = mock_document_store

        stats = rag_pipeline_with_mocks.get_stats()

        assert stats["document_count"] == 5
        assert stats["total_chunks"] == 25


# =============================================================================
# Streaming Tests
# =============================================================================


class TestStreamingResponse:
    """Tests for streaming response functionality."""

    def test_query_stream_basic(self, rag_pipeline_with_mocks, mock_retriever):
        """Test basic streaming response."""
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            b'{"response": "Hello", "done": false}',
            b'{"response": " world", "done": false}',
            b'{"response": "!", "done": true}',
        ]
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            tokens = list(rag_pipeline_with_mocks.query_stream("Hello?"))

            assert len(tokens) == 3
            assert "".join(tokens) == "Hello world!"

    def test_query_stream_no_context(self, rag_pipeline_with_mocks, mock_retriever):
        """Test streaming when no context is available."""
        mock_retriever.search.return_value = []

        tokens = list(
            rag_pipeline_with_mocks.query_stream("Unknown query", min_score=0.9)
        )

        assert len(tokens) == 1
        assert "don't have enough information" in tokens[0]

    def test_query_stream_with_document_store(
        self, rag_pipeline_with_mocks, mock_document_store
    ):
        """Test streaming uses document store when available."""
        rag_pipeline_with_mocks._document_store = mock_document_store
        mock_doc = MagicMock()
        mock_doc.chunks = ["Chunk 1", "Chunk 2"]
        mock_document_store.search.return_value = [mock_doc]

        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            b'{"response": "Answer", "done": true}',
        ]
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            tokens = list(rag_pipeline_with_mocks.query_stream("Query"))

            assert "Answer" in tokens

    def test_query_stream_non_ollama_provider(
        self, mock_embedding_provider, mock_retriever
    ):
        """Test streaming with non-Ollama provider yields full response."""
        with patch("agentic_brain.rag.pipeline.Retriever") as MockRetriever:
            MockRetriever.return_value = mock_retriever
            pipeline = RAGPipeline(
                embedding_provider=mock_embedding_provider,
                llm_provider="openai",
                llm_model="gpt-4",
            )
            pipeline.retriever = mock_retriever

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Full response"}}]
            }
            mock_response.raise_for_status.return_value = None

            with patch("requests.post", return_value=mock_response):
                with patch.dict("os.environ", {"OPENAI_API_KEY": "test"}):
                    tokens = list(pipeline.query_stream("Query"))

            # Non-streaming provider yields full response at once
            assert len(tokens) == 1
            assert tokens[0] == "Full response"

            pipeline.close()


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestAskFunction:
    """Tests for the convenience ask() function."""

    def test_ask_basic(self, mock_retriever):
        """Test basic ask function usage."""
        pipeline = RAGPipeline(
            embedding_provider=MagicMock(),
            llm_provider="ollama",
            llm_model="llama3.1:8b",
        )
        pipeline.retriever = mock_retriever

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Quick answer"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            answer = ask("Simple question", pipeline=pipeline)

            assert answer == "Quick answer"

    def test_ask_reuses_pipeline(self, mock_retriever):
        """Test that ask reuses the same pipeline."""
        pipeline = RAGPipeline(
            embedding_provider=MagicMock(),
            llm_provider="ollama",
            llm_model="llama3.1:8b",
        )
        pipeline.retriever = mock_retriever

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Answer"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            ask("Question 1", pipeline=pipeline)
            ask("Question 2", pipeline=pipeline)

            assert mock_retriever.search.call_count >= 2

    def test_ask_with_custom_params(self, mock_retriever):
        """Test ask with custom k and sources."""
        pipeline = RAGPipeline(
            embedding_provider=MagicMock(),
            llm_provider="ollama",
            llm_model="llama3.1:8b",
        )
        pipeline.retriever = mock_retriever

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Answer"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            ask("Question", k=10, sources=["Custom"], pipeline=pipeline)

            call_args = mock_retriever.search.call_args
            assert call_args is not None
            assert call_args.kwargs.get("k") == 10
            assert call_args.kwargs.get("sources") == ["Custom"]


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_llm_request_timeout(self, rag_pipeline_with_mocks, mock_retriever):
        """Test handling of LLM request timeout."""
        import requests

        with patch("requests.post", side_effect=requests.Timeout("Request timed out")):
            with pytest.raises(requests.Timeout):
                rag_pipeline_with_mocks.query("Test", use_cache=False)

    def test_llm_request_connection_error(
        self, rag_pipeline_with_mocks, mock_retriever
    ):
        """Test handling of LLM connection error."""
        import requests

        with patch(
            "requests.post", side_effect=requests.ConnectionError("Connection failed")
        ):
            with pytest.raises(requests.ConnectionError):
                rag_pipeline_with_mocks.query("Test", use_cache=False)

    def test_llm_http_error(self, rag_pipeline_with_mocks, mock_retriever):
        """Test handling of HTTP error response."""
        import requests

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "500 Server Error"
        )

        with patch("requests.post", return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                rag_pipeline_with_mocks.query("Test", use_cache=False)

    def test_close_pipeline(self, rag_pipeline_with_mocks, mock_retriever):
        """Test pipeline close method."""
        rag_pipeline_with_mocks.close()

        mock_retriever.close.assert_called_once()


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests with mocked external services."""

    def test_full_query_flow(self, mock_embedding_provider):
        """Test complete query flow with all components mocked."""
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = [
            RetrievedChunk(
                content="Important deployment info here.",
                source="Document",
                score=0.88,
                metadata={"title": "Deploy Guide"},
            ),
        ]
        mock_retriever.close.return_value = None

        with patch("agentic_brain.rag.pipeline.Retriever") as MockRetriever:
            MockRetriever.return_value = mock_retriever

            pipeline = RAGPipeline(
                embedding_provider=mock_embedding_provider,
                llm_provider="ollama",
                llm_model="llama3.1:8b",
            )
            pipeline.retriever = mock_retriever

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "response": "To deploy, run the deployment script with proper configuration."
            }
            mock_response.raise_for_status.return_value = None

            with patch("requests.post", return_value=mock_response):
                result = pipeline.query(
                    "How do I deploy the application?",
                    k=5,
                    use_cache=False,
                )

            assert isinstance(result, RAGResult)
            assert result.query == "How do I deploy the application?"
            assert "deploy" in result.answer.lower()
            assert result.has_sources
            assert result.confidence > 0
            assert "ollama" in result.model
            assert result.generation_time_ms > 0

            pipeline.close()

    def test_multiple_queries_with_caching(self, mock_embedding_provider, tmp_path):
        """Test multiple queries demonstrating caching behavior."""
        mock_retriever = MagicMock()
        mock_retriever.search.return_value = [
            RetrievedChunk(content="Test", source="Doc", score=0.8, metadata={}),
        ]
        mock_retriever.close.return_value = None

        with patch.dict(os.environ, {"RAG_CACHE_ENABLED": "true"}):
            with patch("agentic_brain.rag.pipeline.CACHE_DIR", tmp_path):
                with patch("agentic_brain.rag.pipeline.Retriever") as MockRetriever:
                    MockRetriever.return_value = mock_retriever

                    pipeline = RAGPipeline(
                        embedding_provider=mock_embedding_provider,
                        cache_ttl_hours=1,
                    )
                    pipeline.retriever = mock_retriever

                    mock_response = MagicMock()
                    mock_response.json.return_value = {"response": "Cached answer"}
                    mock_response.raise_for_status.return_value = None

                    with patch(
                        "requests.post", return_value=mock_response
                    ) as mock_post:
                        # First query - hits LLM
                        result1 = pipeline.query("Cache test query", use_cache=True)
                        assert result1.cached is False
                        call_count_after_first = mock_post.call_count

                        # Second identical query - uses cache
                        result2 = pipeline.query("Cache test query", use_cache=True)
                        assert result2.cached is True
                        assert mock_post.call_count == call_count_after_first

                        # Different query - hits LLM again
                        result3 = pipeline.query("Different query", use_cache=True)
                        assert result3.cached is False
                        assert mock_post.call_count > call_count_after_first

                    pipeline.close()
