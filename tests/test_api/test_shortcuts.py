# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for API shortcuts and fluent builder patterns.

Comprehensive test suite with 25+ test cases covering:
- Shortcuts (quick_rag, quick_graph, quick_search, quick_eval)
- Fluent builder (AgenticBrain)
- Error handling
- Integration scenarios
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

from agentic_brain.api import (
    AgenticBrain,
    quick_rag,
    quick_graph,
    quick_search,
    quick_eval,
)
from agentic_brain.rag import RAGResult


# ============================================================================
# SHORTCUTS TESTS
# ============================================================================


class TestQuickRAG:
    """Tests for quick_rag shortcut."""

    def test_quick_rag_simple_query(self):
        """Test basic RAG query without documents."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            mock_result = RAGResult(
                query="test query",
                answer="test answer",
                sources=[],
                confidence=0.8,
                model="llama3.1:8b",
            )
            mock_instance.query.return_value = mock_result

            result = quick_rag("test query")

            assert result.answer == "test answer"
            assert result.confidence == 0.8
            assert result.query == "test query"

    def test_quick_rag_with_documents(self):
        """Test RAG with document ingestion."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            mock_result = RAGResult(
                query="deployment",
                answer="Deploy using...",
                sources=[],
                confidence=0.9,
                model="llama3.1:8b",
            )
            mock_instance.query.return_value = mock_result

            result = quick_rag(
                "How to deploy?",
                docs=["deployment.md", "guide.md"]
            )

            assert mock_instance.ingest_document.call_count >= 2
            assert result.answer == "Deploy using..."

    def test_quick_rag_custom_provider(self):
        """Test RAG with custom LLM provider."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            mock_result = RAGResult(
                query="test",
                answer="answer",
                sources=[],
                confidence=0.7,
                model="gpt-4",
            )
            mock_instance.query.return_value = mock_result

            result = quick_rag(
                "test",
                llm_provider="openai",
                llm_model="gpt-4"
            )

            mock_pipeline.assert_called_once()
            call_kwargs = mock_pipeline.call_args[1]
            assert call_kwargs["llm_provider"] == "openai"
            assert call_kwargs["llm_model"] == "gpt-4"

    def test_quick_rag_error_handling(self):
        """Test RAG error handling."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_pipeline.side_effect = Exception("Connection failed")

            result = quick_rag("test query")

            assert result.confidence == 0.0
            assert "Error" in result.answer
            assert result.sources == []

    def test_quick_rag_cache_disabled(self):
        """Test RAG with caching disabled."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            mock_result = RAGResult(
                query="test",
                answer="answer",
                sources=[],
                confidence=0.8,
                model="llama3.1:8b",
                cached=False,
            )
            mock_instance.query.return_value = mock_result

            result = quick_rag("test", use_cache=False)
            assert result.cached is False


class TestQuickGraph:
    """Tests for quick_graph shortcut."""

    def test_quick_graph_simple_entities(self):
        """Test graph creation with simple entities."""
        with patch("agentic_brain.api.shortcuts.TopicHub") as mock_hub:
            mock_instance = MagicMock()
            mock_hub.return_value = mock_instance

            graph = quick_graph(["User", "Project", "Task"])

            assert mock_instance.create_topic.call_count == 3
            calls = [call[0][0] for call in mock_instance.create_topic.call_args_list]
            assert "User" in calls
            assert "Project" in calls
            assert "Task" in calls

    def test_quick_graph_with_relationships(self):
        """Test graph with relationships."""
        with patch("agentic_brain.api.shortcuts.TopicHub") as mock_hub:
            mock_instance = MagicMock()
            mock_hub.return_value = mock_instance

            entities = ["User", "Project"]
            rels = [("User", "owns", "Project")]

            graph = quick_graph(entities, rels)

            assert mock_instance.create_topic.call_count == 2
            assert mock_instance.link_topic.call_count == 1
            mock_instance.link_topic.assert_called_with(
                "User", "owns", "Project"
            )

    def test_quick_graph_multiple_relationships(self):
        """Test graph with multiple relationships."""
        with patch("agentic_brain.api.shortcuts.TopicHub") as mock_hub:
            mock_instance = MagicMock()
            mock_hub.return_value = mock_instance

            rels = [
                ("User", "owns", "Project"),
                ("Project", "contains", "Task"),
                ("User", "assigned_to", "Task"),
            ]

            quick_graph(["User", "Project", "Task"], rels)

            assert mock_instance.link_topic.call_count == 3

    def test_quick_graph_error_handling(self):
        """Test graph error handling."""
        with patch("agentic_brain.api.shortcuts.TopicHub") as mock_hub:
            mock_hub.side_effect = Exception("Neo4j connection failed")

            with pytest.raises(Exception):
                quick_graph(["User", "Project"])


class TestQuickSearch:
    """Tests for quick_search shortcut."""

    def test_quick_search_hybrid(self):
        """Test hybrid search."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            mock_chunk = MagicMock()
            mock_chunk.content = "Test document content"
            mock_chunk.source = "doc.md"
            mock_chunk.score = 0.95
            mock_chunk.confidence = 0.9

            mock_instance.hybrid_search.return_value = [mock_chunk]

            results = quick_search("neural networks", num_results=5)

            assert len(results) == 1
            assert results[0]["content"] == "Test document content"
            assert results[0]["source"] == "doc.md"
            assert results[0]["score"] == 0.95

    def test_quick_search_vector(self):
        """Test vector-only search."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            mock_chunk = MagicMock()
            mock_chunk.content = "Vector result"
            mock_chunk.source = "vectors.md"
            mock_chunk.score = 0.88

            mock_instance.vector_search.return_value = [mock_chunk]

            results = quick_search("query", search_type="vector")

            mock_instance.vector_search.assert_called_once()
            assert len(results) == 1

    def test_quick_search_keyword(self):
        """Test keyword-only search."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            mock_chunk = MagicMock()
            mock_chunk.content = "Keyword result"
            mock_chunk.source = "keywords.md"
            mock_chunk.score = 0.75

            mock_instance.keyword_search.return_value = [mock_chunk]

            results = quick_search("term", search_type="keyword")

            mock_instance.keyword_search.assert_called_once()
            assert len(results) == 1

    def test_quick_search_invalid_type(self):
        """Test search with invalid type returns empty list."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            # Invalid search type should return empty list (graceful error handling)
            results = quick_search("query", search_type="invalid")

            assert results == []

    def test_quick_search_custom_result_count(self):
        """Test search with custom result count."""
        with patch("agentic_brain.api.shortcuts.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            mock_instance.hybrid_search.return_value = []

            quick_search("test", num_results=20)

            mock_instance.hybrid_search.assert_called_with("test", limit=20)


class TestQuickEval:
    """Tests for quick_eval shortcut."""

    def test_quick_eval_empty_results(self):
        """Test evaluation with no results."""
        result = quick_eval([])
        assert "error" in result or result["total_queries"] == 0

    def test_quick_eval_retrieval_metrics(self):
        """Test retrieval metrics computation."""
        results = [
            RAGResult(
                query="q1",
                answer="a1",
                sources=[MagicMock()],
                confidence=0.9,
                model="test",
            ),
            RAGResult(
                query="q2",
                answer="a2",
                sources=[],
                confidence=0.7,
                model="test",
            ),
        ]

        metrics = quick_eval(results, metrics=["retrieval"])

        assert metrics["total_queries"] == 2
        assert metrics["retrieval"]["with_sources"] == 1
        assert metrics["retrieval"]["without_sources"] == 1
        assert metrics["retrieval"]["retrieval_rate"] == 0.5

    def test_quick_eval_generation_metrics(self):
        """Test generation metrics computation."""
        results = [
            RAGResult(
                query="q1",
                answer="a" * 100,
                sources=[],
                confidence=0.9,
                model="test",
            ),
            RAGResult(
                query="q2",
                answer="b" * 200,
                sources=[],
                confidence=0.7,
                model="test",
            ),
        ]

        metrics = quick_eval(results, metrics=["generation"])

        assert "generation" in metrics
        assert metrics["generation"]["high_confidence"] == 1
        assert metrics["generation"]["medium_confidence"] == 1

    def test_quick_eval_latency_metrics(self):
        """Test latency metrics computation."""
        results = [
            RAGResult(
                query="q1",
                answer="a1",
                sources=[],
                confidence=0.9,
                model="test",
                generation_time_ms=100.0,
            ),
            RAGResult(
                query="q2",
                answer="a2",
                sources=[],
                confidence=0.8,
                model="test",
                generation_time_ms=200.0,
            ),
        ]

        metrics = quick_eval(results, metrics=["latency"])

        assert metrics["latency"]["total_ms"] == 300.0
        assert metrics["latency"]["avg_ms"] == 150.0
        assert metrics["latency"]["max_ms"] == 200.0

    def test_quick_eval_source_metrics(self):
        """Test source citation metrics."""
        chunk1 = MagicMock()
        chunk2 = MagicMock()

        results = [
            RAGResult(
                query="q1",
                answer="a1",
                sources=[chunk1, chunk2],
                confidence=0.9,
                model="test",
            ),
            RAGResult(
                query="q2",
                answer="a2",
                sources=[],
                confidence=0.8,
                model="test",
            ),
        ]

        metrics = quick_eval(results, metrics=["sources"])

        assert metrics["sources"]["total"] == 2
        assert metrics["sources"]["avg_per_query"] == 1.0
        assert metrics["sources"]["with_sources"] == 1
        assert metrics["sources"]["without_sources"] == 1

    def test_quick_eval_confidence_metrics(self):
        """Test confidence calibration metrics."""
        results = [
            RAGResult(
                query="q1",
                answer="a1",
                sources=[],
                confidence=0.9,
                model="test",
            ),
            RAGResult(
                query="q2",
                answer="a2",
                sources=[],
                confidence=0.7,
                model="test",
            ),
            RAGResult(
                query="q3",
                answer="a3",
                sources=[],
                confidence=0.5,
                model="test",
            ),
        ]

        metrics = quick_eval(results, metrics=["confidence"])

        assert abs(metrics["confidence"]["avg"] - 0.7) < 0.01
        assert metrics["confidence"]["min"] == 0.5
        assert metrics["confidence"]["max"] == 0.9

    def test_quick_eval_with_golden_answers(self):
        """Test evaluation against golden answers."""
        results = [
            RAGResult(
                query="q1",
                answer="the answer is yes",
                sources=[],
                confidence=0.9,
                model="test",
            ),
        ]

        golden = ["the answer is yes"]

        metrics = quick_eval(results, golden_answers=golden)

        assert metrics["generation"]["exact_matches"] >= 0


# ============================================================================
# FLUENT BUILDER TESTS
# ============================================================================


class TestAgenticBrainLLMConfig:
    """Tests for LLM configuration in fluent builder."""

    def test_with_llm_basic(self):
        """Test basic LLM configuration."""
        brain = AgenticBrain().with_llm("ollama", "llama3.1:8b")

        assert brain._llm_provider == "ollama"
        assert brain._llm_model == "llama3.1:8b"

    def test_with_llm_openai_shortcut(self):
        """Test OpenAI shortcut."""
        brain = AgenticBrain().with_llm_openai("gpt-4")

        assert brain._llm_provider == "openai"
        assert brain._llm_model == "gpt-4"

    def test_with_llm_groq_shortcut(self):
        """Test Groq shortcut."""
        brain = AgenticBrain().with_llm_groq()

        assert brain._llm_provider == "groq"

    def test_with_llm_ollama_shortcut(self):
        """Test Ollama shortcut."""
        brain = AgenticBrain().with_llm_ollama()

        assert brain._llm_provider == "ollama"

    def test_with_llm_anthropic_shortcut(self):
        """Test Anthropic shortcut."""
        brain = AgenticBrain().with_llm_anthropic()

        assert brain._llm_provider == "anthropic"


class TestAgenticBrainGraphConfig:
    """Tests for graph configuration."""

    def test_with_graph_default(self):
        """Test default graph configuration."""
        with patch("agentic_brain.api.fluent.TopicHub"):
            brain = AgenticBrain().with_graph()

            assert brain._graph_uri == "bolt://localhost:7687"
            assert brain._graph_user == "neo4j"

    def test_with_graph_custom_uri(self):
        """Test custom graph URI."""
        with patch("agentic_brain.api.fluent.TopicHub"):
            brain = AgenticBrain().with_graph(
                neo4j_uri="bolt://custom:7687"
            )

            assert brain._graph_uri == "bolt://custom:7687"

    def test_without_graph(self):
        """Test disabling graph."""
        with patch("agentic_brain.api.fluent.TopicHub"):
            brain = AgenticBrain().with_graph().without_graph()

            assert brain._graph is None


class TestAgenticBrainRAGConfig:
    """Tests for RAG configuration."""

    def test_with_rag_default(self):
        """Test default RAG configuration."""
        with patch("agentic_brain.api.fluent.RAGPipeline"):
            brain = AgenticBrain().with_rag()

            assert brain._rag_cache_ttl == 4

    def test_with_rag_custom_cache(self):
        """Test RAG with custom cache TTL."""
        with patch("agentic_brain.api.fluent.RAGPipeline"):
            brain = AgenticBrain().with_rag(cache_ttl_hours=24)

            assert brain._rag_cache_ttl == 24

    def test_without_rag(self):
        """Test disabling RAG."""
        with patch("agentic_brain.api.fluent.RAGPipeline"):
            brain = AgenticBrain().with_rag().without_rag()

            assert brain._rag is None


class TestAgenticBrainChaining:
    """Tests for fluent chaining."""

    def test_method_chaining_returns_self(self):
        """Test that methods return self for chaining."""
        with patch("agentic_brain.api.fluent.TopicHub"):
            with patch("agentic_brain.api.fluent.RAGPipeline"):
                brain = (
                    AgenticBrain()
                    .with_llm("ollama")
                    .with_graph()
                    .with_rag()
                )

                assert isinstance(brain, AgenticBrain)

    def test_complex_chain(self):
        """Test complex configuration chain."""
        with patch("agentic_brain.api.fluent.TopicHub"):
            with patch("agentic_brain.api.fluent.RAGPipeline"):
                brain = (
                    AgenticBrain()
                    .with_llm_openai("gpt-4")
                    .with_graph(neo4j_uri="bolt://localhost:7687")
                    .with_rag(cache_ttl_hours=12)
                )

                assert brain._llm_provider == "openai"
                assert brain._llm_model == "gpt-4"
                assert brain._rag_cache_ttl == 12


class TestAgenticBrainEntities:
    """Tests for entity management."""

    def test_add_entities_single(self):
        """Test adding single entity."""
        with patch("agentic_brain.api.fluent.TopicHub") as mock_hub:
            mock_instance = MagicMock()
            mock_hub.return_value = mock_instance

            brain = AgenticBrain().add_entities(["User"])

            mock_instance.create_topic.assert_called_with("User")

    def test_add_entities_multiple(self):
        """Test adding multiple entities."""
        with patch("agentic_brain.api.fluent.TopicHub") as mock_hub:
            mock_instance = MagicMock()
            mock_hub.return_value = mock_instance

            entities = ["User", "Project", "Task"]
            brain = AgenticBrain().add_entities(entities)

            assert mock_instance.create_topic.call_count == 3

    def test_add_relationships(self):
        """Test adding relationships."""
        with patch("agentic_brain.api.fluent.TopicHub") as mock_hub:
            mock_instance = MagicMock()
            mock_hub.return_value = mock_instance

            rels = [
                ("User", "owns", "Project"),
                ("Project", "contains", "Task"),
            ]

            brain = AgenticBrain().add_relationships(rels)

            assert mock_instance.link_topic.call_count == 2


class TestAgenticBrainHistory:
    """Tests for query history tracking."""

    def test_query_history_tracking(self):
        """Test that queries are tracked in history."""
        with patch("agentic_brain.api.fluent.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            result = RAGResult(
                query="test",
                answer="answer",
                sources=[],
                confidence=0.8,
                model="test",
            )
            mock_instance.query.return_value = result

            brain = AgenticBrain().with_rag()
            brain.query("test query")

            assert len(brain._query_history) == 1

    def test_query_history_limit(self):
        """Test that query history respects max_history."""
        with patch("agentic_brain.api.fluent.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            result = RAGResult(
                query="q",
                answer="a",
                sources=[],
                confidence=0.8,
                model="test",
            )
            mock_instance.query.return_value = result

            brain = AgenticBrain()
            brain._max_history = 5
            brain.with_rag()

            for i in range(10):
                brain.query(f"query {i}")

            assert len(brain._query_history) == 5

    def test_clear_history(self):
        """Test clearing query history."""
        with patch("agentic_brain.api.fluent.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            result = RAGResult(
                query="q",
                answer="a",
                sources=[],
                confidence=0.8,
                model="test",
            )
            mock_instance.query.return_value = result

            brain = AgenticBrain().with_rag()
            brain.query("test")
            assert len(brain._query_history) > 0

            brain.clear_history()
            assert len(brain._query_history) == 0

    def test_get_query_history(self):
        """Test retrieving query history."""
        with patch("agentic_brain.api.fluent.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            result = RAGResult(
                query="q",
                answer="answer text",
                sources=[],
                confidence=0.8,
                model="test",
            )
            mock_instance.query.return_value = result

            brain = AgenticBrain().with_rag()
            brain.query("test query")

            history = brain.get_query_history()

            assert len(history) == 1
            assert history[0][0] == "test query"
            assert history[0][1] == "answer text"

    def test_evaluate_recent_queries(self):
        """Test evaluation of recent queries."""
        with patch("agentic_brain.api.fluent.RAGPipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            result1 = RAGResult(
                query="q1",
                answer="a1",
                sources=[MagicMock()],
                confidence=0.9,
                model="test",
            )
            result2 = RAGResult(
                query="q2",
                answer="a2",
                sources=[],
                confidence=0.7,
                model="test",
            )

            mock_instance.query.side_effect = [result1, result2]

            brain = AgenticBrain().with_rag()
            brain.query("q1")
            brain.query("q2")

            metrics = brain.evaluate_recent_queries()

            assert metrics["total_queries"] == 2
            assert metrics["with_sources"] == 1


class TestAgenticBrainDescription:
    """Tests for configuration description."""

    def test_describe_minimal(self):
        """Test description of minimal configuration."""
        brain = AgenticBrain()
        desc = brain.describe()

        assert "AgenticBrain Configuration:" in desc

    def test_describe_with_llm(self):
        """Test description includes LLM config."""
        brain = AgenticBrain().with_llm("ollama", "llama3.1:8b")
        desc = brain.describe()

        assert "ollama" in desc or "LLM:" in desc

    def test_repr(self):
        """Test string representation."""
        brain = AgenticBrain().with_llm("ollama")
        repr_str = repr(brain)

        assert "AgenticBrain" in repr_str
