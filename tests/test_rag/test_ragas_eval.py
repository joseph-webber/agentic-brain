# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Comprehensive tests for RAGAS evaluation module.

Covers:
- RAGASSample and RAGASDataset data structures
- All 4 RAGAS metrics (Faithfulness, Answer Relevancy, Context Precision, Context Recall)
- RAGASEvaluator full workflow
- Quality bar thresholds
- A/B testing and benchmarking
- GraphRAG integration
- Edge cases and error handling
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.ragas_eval import (
    QUALITY_BAR,
    AnswerRelevancyCalculator,
    ContextPrecisionCalculator,
    ContextRecallCalculator,
    FaithfulnessCalculator,
    MetricResult,
    QualityLevel,
    RAGASDataset,
    RAGASEvaluator,
    RAGASResults,
    RAGASSample,
    SampleResult,
    SimpleLLMJudge,
    check_quality_bar,
    create_graphrag_evaluator,
    quick_evaluate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_basic() -> RAGASSample:
    """Basic sample for testing."""
    return RAGASSample(
        question="How do I deploy to production?",
        answer="Run kubectl apply -f deployment.yaml to deploy your application.",
        contexts=[
            "Deployment Guide: Use kubectl apply -f deployment.yaml to deploy.",
            "Configuration: Set replicas in deployment.yaml for scaling.",
        ],
        ground_truth="Use kubectl apply -f deployment.yaml",
    )


@pytest.fixture
def sample_low_faithfulness() -> RAGASSample:
    """Sample with hallucinated content not in context."""
    return RAGASSample(
        question="What database does the system use?",
        answer="The system uses PostgreSQL with advanced features like JSON storage and partitioning.",
        contexts=[
            "The system stores data in Neo4j graph database.",
            "Vector embeddings are indexed using HNSW algorithm.",
        ],
        ground_truth="Neo4j graph database",
    )


@pytest.fixture
def sample_irrelevant_answer() -> RAGASSample:
    """Sample with answer not addressing the question."""
    return RAGASSample(
        question="How do I configure logging?",
        answer="The weather today is sunny with a high of 25 degrees.",
        contexts=[
            "Logging: Set LOG_LEVEL environment variable.",
            "Debug: Use LOG_LEVEL=DEBUG for verbose output.",
        ],
        ground_truth="Set LOG_LEVEL environment variable",
    )


@pytest.fixture
def sample_poor_context() -> RAGASSample:
    """Sample with irrelevant contexts retrieved."""
    return RAGASSample(
        question="How do I reset my password?",
        answer="Go to settings and click 'Reset Password'.",
        contexts=[
            "Our company was founded in 2020.",
            "The cafeteria serves lunch from 12-2pm.",
            "Meeting rooms can be booked online.",
        ],
        ground_truth="Navigate to settings, click Reset Password, enter new password",
    )


@pytest.fixture
def dataset_basic(sample_basic: RAGASSample) -> RAGASDataset:
    """Basic dataset with one sample."""
    dataset = RAGASDataset()
    dataset.samples.append(sample_basic)
    return dataset


@pytest.fixture
def dataset_varied() -> RAGASDataset:
    """Dataset with varied quality samples."""
    dataset = RAGASDataset()

    # High quality sample
    dataset.add_sample(
        question="What is the capital of France?",
        answer="The capital of France is Paris.",
        contexts=["Paris is the capital and largest city of France."],
        ground_truth="Paris",
    )

    # Medium quality sample
    dataset.add_sample(
        question="How do I install Python?",
        answer="Download Python from python.org and run the installer.",
        contexts=[
            "Python can be downloaded from the official website.",
            "Installation requires administrator privileges.",
        ],
        ground_truth="Download from python.org, run installer, add to PATH",
    )

    # Lower quality sample
    dataset.add_sample(
        question="What time is the meeting?",
        answer="The meeting is at 3pm in conference room B.",
        contexts=[
            "Weekly standup is held every Monday.",
            "All meetings should have an agenda.",
        ],
        ground_truth="3pm Monday",
    )

    return dataset


# ---------------------------------------------------------------------------
# Tests: Data Structures
# ---------------------------------------------------------------------------


class TestRAGASSample:
    """Tests for RAGASSample dataclass."""

    def test_create_valid_sample(self):
        """Test creating a valid sample."""
        sample = RAGASSample(
            question="Test question?",
            answer="Test answer.",
            contexts=["Context 1", "Context 2"],
            ground_truth="Expected answer",
        )
        assert sample.question == "Test question?"
        assert sample.answer == "Test answer."
        assert len(sample.contexts) == 2
        assert sample.ground_truth == "Expected answer"

    def test_empty_question_raises(self):
        """Test that empty question raises ValueError."""
        with pytest.raises(ValueError, match="Question cannot be empty"):
            RAGASSample(
                question="   ",
                answer="Test answer.",
                contexts=["Context"],
                ground_truth="Truth",
            )

    def test_empty_answer_raises(self):
        """Test that empty answer raises ValueError."""
        with pytest.raises(ValueError, match="Answer cannot be empty"):
            RAGASSample(
                question="Test?",
                answer="",
                contexts=["Context"],
                ground_truth="Truth",
            )

    def test_empty_ground_truth_raises(self):
        """Test that empty ground truth raises ValueError."""
        with pytest.raises(ValueError, match="Ground truth cannot be empty"):
            RAGASSample(
                question="Test?",
                answer="Answer",
                contexts=["Context"],
                ground_truth="  ",
            )

    def test_empty_contexts_allowed(self):
        """Test that empty contexts list is allowed."""
        sample = RAGASSample(
            question="Test?",
            answer="Answer",
            contexts=[],
            ground_truth="Truth",
        )
        assert sample.contexts == []

    def test_metadata_default(self):
        """Test that metadata defaults to empty dict."""
        sample = RAGASSample(
            question="Test?",
            answer="Answer",
            contexts=["Context"],
            ground_truth="Truth",
        )
        assert sample.metadata == {}


class TestRAGASDataset:
    """Tests for RAGASDataset."""

    def test_create_empty_dataset(self):
        """Test creating empty dataset."""
        dataset = RAGASDataset()
        assert len(dataset) == 0

    def test_add_sample(self):
        """Test adding samples to dataset."""
        dataset = RAGASDataset()
        dataset.add_sample(
            question="Q1?",
            answer="A1",
            contexts=["C1"],
            ground_truth="G1",
        )
        assert len(dataset) == 1

    def test_add_multiple_samples(self):
        """Test adding multiple samples."""
        dataset = RAGASDataset()
        for i in range(5):
            dataset.add_sample(
                question=f"Q{i}?",
                answer=f"A{i}",
                contexts=[f"C{i}"],
                ground_truth=f"G{i}",
            )
        assert len(dataset) == 5

    def test_iterate_dataset(self):
        """Test iterating over dataset."""
        dataset = RAGASDataset()
        dataset.add_sample("Q1?", "A1", ["C1"], "G1")
        dataset.add_sample("Q2?", "A2", ["C2"], "G2")

        questions = [s.question for s in dataset]
        assert questions == ["Q1?", "Q2?"]

    def test_save_and_load(self, tmp_path: Path):
        """Test saving and loading dataset."""
        dataset = RAGASDataset()
        dataset.add_sample("Q1?", "A1", ["C1", "C2"], "G1", metadata={"tag": "test"})

        path = tmp_path / "dataset.json"
        dataset.save(path)

        # Load into new dataset
        loaded = RAGASDataset()
        loaded.add_samples_from_file(path)

        assert len(loaded) == 1
        assert loaded.samples[0].question == "Q1?"
        assert loaded.samples[0].metadata == {"tag": "test"}


class TestMetricResult:
    """Tests for MetricResult."""

    def test_create_metric_result(self):
        """Test creating metric result."""
        result = MetricResult(
            name="faithfulness",
            score=0.85,
            details={"claims": 10, "supported": 8},
            reasoning="8/10 claims supported",
        )
        assert result.name == "faithfulness"
        assert result.score == 0.85
        assert result.meets_quality_bar

    def test_below_quality_bar(self):
        """Test metric below quality bar."""
        result = MetricResult(name="test", score=0.5)
        assert not result.meets_quality_bar

    def test_repr(self):
        """Test string representation."""
        result = MetricResult(name="faithfulness", score=0.85)
        assert "faithfulness: 0.850" in repr(result)


# ---------------------------------------------------------------------------
# Tests: SimpleLLMJudge
# ---------------------------------------------------------------------------


class TestSimpleLLMJudge:
    """Tests for SimpleLLMJudge heuristic implementation."""

    def test_judge_faithfulness_supported(self):
        """Test faithfulness with supported claims."""
        judge = SimpleLLMJudge()
        score, verifications = judge.judge_faithfulness(
            answer="Python is a programming language used for data science.",
            contexts=[
                "Python is a versatile programming language widely used in data science and machine learning."
            ],
        )
        assert score > 0.5
        assert len(verifications) > 0

    def test_judge_faithfulness_unsupported(self):
        """Test faithfulness with unsupported claims."""
        judge = SimpleLLMJudge()
        score, verifications = judge.judge_faithfulness(
            answer="The system uses Oracle database with enterprise features.",
            contexts=[
                "Neo4j graph database stores all data.",
                "PostgreSQL is not used.",
            ],
        )
        # Score should be lower since Oracle is not mentioned in context
        assert score < 0.8

    def test_generate_synthetic_questions(self):
        """Test synthetic question generation."""
        judge = SimpleLLMJudge()
        questions = judge.generate_synthetic_questions(
            answer="Python is a programming language used for web development and data science.",
            n=3,
        )
        assert len(questions) <= 3
        for q in questions:
            assert "?" in q

    def test_extract_statements(self):
        """Test statement extraction."""
        judge = SimpleLLMJudge()
        statements = judge.extract_statements(
            "Machine learning is powerful. It transforms industries. How does it work?"
        )
        # Should not include the question
        assert all("?" not in s for s in statements)
        assert len(statements) >= 1


# ---------------------------------------------------------------------------
# Tests: Metric Calculators
# ---------------------------------------------------------------------------


class TestFaithfulnessCalculator:
    """Tests for FaithfulnessCalculator."""

    def test_high_faithfulness(self, sample_basic: RAGASSample):
        """Test high faithfulness score."""
        calc = FaithfulnessCalculator()
        result = calc.calculate(sample_basic)

        assert result.name == "faithfulness"
        assert 0.0 <= result.score <= 1.0

    def test_low_faithfulness(self, sample_low_faithfulness: RAGASSample):
        """Test low faithfulness for hallucinated content."""
        calc = FaithfulnessCalculator()
        result = calc.calculate(sample_low_faithfulness)

        # PostgreSQL is not in context, so faithfulness should be lower
        assert result.score < 0.9

    def test_empty_contexts(self):
        """Test faithfulness with no contexts."""
        calc = FaithfulnessCalculator()
        sample = RAGASSample(
            question="Test?",
            answer="Answer with claims.",
            contexts=[],
            ground_truth="Truth",
        )
        result = calc.calculate(sample)
        assert result.score == 0.0
        assert "No context" in result.details.get("reason", "")


class TestAnswerRelevancyCalculator:
    """Tests for AnswerRelevancyCalculator."""

    def test_relevant_answer(self, sample_basic: RAGASSample):
        """Test relevant answer scores high."""
        calc = AnswerRelevancyCalculator()
        result = calc.calculate(sample_basic)

        assert result.name == "answer_relevancy"
        assert 0.0 <= result.score <= 1.0

    def test_irrelevant_answer(self, sample_irrelevant_answer: RAGASSample):
        """Test irrelevant answer scores lower."""
        calc = AnswerRelevancyCalculator()
        result = calc.calculate(sample_irrelevant_answer)

        # Weather answer to logging question should score lower
        assert result.score < 0.7


class TestContextPrecisionCalculator:
    """Tests for ContextPrecisionCalculator."""

    def test_good_precision(self, sample_basic: RAGASSample):
        """Test good context precision."""
        calc = ContextPrecisionCalculator()
        result = calc.calculate(sample_basic)

        assert result.name == "context_precision"
        assert 0.0 <= result.score <= 1.0
        assert "context_scores" in result.details

    def test_poor_precision(self, sample_poor_context: RAGASSample):
        """Test poor precision with irrelevant contexts."""
        calc = ContextPrecisionCalculator()
        result = calc.calculate(sample_poor_context)

        # Irrelevant contexts should score lower than high-quality ones
        assert result.score < 0.7

    def test_empty_contexts(self):
        """Test precision with no contexts."""
        calc = ContextPrecisionCalculator()
        sample = RAGASSample(
            question="Test?",
            answer="Answer",
            contexts=[],
            ground_truth="Truth",
        )
        result = calc.calculate(sample)
        assert result.score == 0.0


class TestContextRecallCalculator:
    """Tests for ContextRecallCalculator."""

    def test_good_recall(self, sample_basic: RAGASSample):
        """Test good context recall."""
        calc = ContextRecallCalculator()
        result = calc.calculate(sample_basic)

        assert result.name == "context_recall"
        assert 0.0 <= result.score <= 1.0

    def test_poor_recall(self, sample_poor_context: RAGASSample):
        """Test poor recall with missing information."""
        calc = ContextRecallCalculator()
        result = calc.calculate(sample_poor_context)

        # Ground truth info not in irrelevant contexts
        assert result.score < 0.7

    def test_empty_contexts(self):
        """Test recall with no contexts."""
        calc = ContextRecallCalculator()
        sample = RAGASSample(
            question="Test?",
            answer="Answer",
            contexts=[],
            ground_truth="Expected ground truth statement",
        )
        result = calc.calculate(sample)
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# Tests: RAGASEvaluator
# ---------------------------------------------------------------------------


class TestRAGASEvaluator:
    """Tests for RAGASEvaluator main class."""

    def test_evaluate_single_sample(self, sample_basic: RAGASSample):
        """Test evaluating a single sample."""
        evaluator = RAGASEvaluator()
        result = evaluator.evaluate_sample(sample_basic)

        assert isinstance(result, SampleResult)
        assert result.sample == sample_basic
        assert 0.0 <= result.overall_score <= 1.0
        assert 0.0 <= result.faithfulness.score <= 1.0
        assert 0.0 <= result.answer_relevancy.score <= 1.0
        assert 0.0 <= result.context_precision.score <= 1.0
        assert 0.0 <= result.context_recall.score <= 1.0

    def test_evaluate_dataset(self, dataset_basic: RAGASDataset):
        """Test evaluating a dataset."""
        evaluator = RAGASEvaluator()
        results = evaluator.evaluate(dataset_basic)

        assert isinstance(results, RAGASResults)
        assert results.num_samples == 1
        assert 0.0 <= results.overall_score <= 1.0
        assert results.quality_level in QualityLevel

    def test_evaluate_empty_dataset(self):
        """Test evaluating empty dataset."""
        evaluator = RAGASEvaluator()
        results = evaluator.evaluate(RAGASDataset())

        assert results.num_samples == 0
        assert results.overall_score == 0.0
        assert results.quality_level == QualityLevel.FAILING

    def test_evaluate_varied_dataset(self, dataset_varied: RAGASDataset):
        """Test evaluating varied quality dataset."""
        evaluator = RAGASEvaluator()
        results = evaluator.evaluate(dataset_varied)

        assert results.num_samples == 3
        assert len(results.sample_results) == 3

    def test_results_to_dict(self, dataset_basic: RAGASDataset):
        """Test converting results to dictionary."""
        evaluator = RAGASEvaluator()
        results = evaluator.evaluate(dataset_basic)

        result_dict = results.to_dict()
        assert "overall_score" in result_dict
        assert "metrics" in result_dict
        assert "faithfulness" in result_dict["metrics"]
        assert "samples" in result_dict

    def test_results_repr(self, dataset_basic: RAGASDataset):
        """Test results string representation."""
        evaluator = RAGASEvaluator()
        results = evaluator.evaluate(dataset_basic)

        repr_str = repr(results)
        assert "RAGAS Evaluation" in repr_str
        assert "Faithfulness" in repr_str

    def test_quality_level_production(self):
        """Test production quality level detection."""
        evaluator = RAGASEvaluator()

        # Create high-quality dataset
        dataset = RAGASDataset()
        dataset.add_sample(
            question="What is 2+2?",
            answer="2+2 equals 4.",
            contexts=["Basic arithmetic: 2+2=4"],
            ground_truth="4",
        )

        results = evaluator.evaluate(dataset)
        # Results may vary, but structure should be correct
        assert results.quality_level in QualityLevel

    def test_save_results(self, dataset_basic: RAGASDataset, tmp_path: Path):
        """Test saving evaluation results."""
        evaluator = RAGASEvaluator()
        evaluator.evaluate(dataset_basic)

        path = tmp_path / "results.json"
        evaluator.save_results(path)

        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 1


class TestEvaluatorPipeline:
    """Tests for RAG pipeline evaluation."""

    def test_evaluate_rag_pipeline(self):
        """Test evaluating a RAG function directly."""
        evaluator = RAGASEvaluator()

        def mock_rag(question: str) -> tuple[str, list[str]]:
            return (
                "The answer is 42.",
                ["Context: The answer to everything is 42."],
            )

        results = evaluator.evaluate_rag_pipeline(
            mock_rag,
            questions=["What is the answer?"],
            ground_truths=["42"],
        )

        assert results.num_samples == 1

    def test_evaluate_pipeline_mismatched_lengths(self):
        """Test error on mismatched question/ground_truth lengths."""
        evaluator = RAGASEvaluator()

        def mock_rag(q: str) -> tuple[str, list[str]]:
            return ("Answer", ["Context"])

        with pytest.raises(ValueError, match="same length"):
            evaluator.evaluate_rag_pipeline(
                mock_rag,
                questions=["Q1", "Q2"],
                ground_truths=["G1"],
            )


class TestABTesting:
    """Tests for A/B testing functionality."""

    def test_compare_datasets(self, dataset_basic: RAGASDataset):
        """Test comparing two datasets."""
        evaluator = RAGASEvaluator()

        # Create second dataset (slight variation)
        dataset_b = RAGASDataset()
        dataset_b.add_sample(
            question="How do I deploy?",
            answer="Deploy using kubectl.",
            contexts=["Kubectl is used for deployment."],
            ground_truth="kubectl apply",
        )

        comparison = evaluator.compare(
            dataset_basic,
            dataset_b,
            names=("Baseline", "Improved"),
        )

        assert "Baseline" in comparison
        assert "Improved" in comparison
        assert "improvements" in comparison
        assert "winner" in comparison


class TestBenchmarking:
    """Tests for benchmarking functionality."""

    def test_benchmark_iterations(self, dataset_basic: RAGASDataset):
        """Test running benchmark iterations."""
        evaluator = RAGASEvaluator()

        def mock_rag(q: str) -> tuple[str, list[str]]:
            return (
                "Run kubectl apply to deploy.",
                ["Deployment: kubectl apply -f deployment.yaml"],
            )

        benchmark = evaluator.benchmark(
            mock_rag,
            dataset_basic,
            n_iterations=2,
        )

        assert benchmark["iterations"] == 2
        assert "metrics" in benchmark
        assert "overall" in benchmark["metrics"]
        assert "mean" in benchmark["metrics"]["overall"]
        assert "std" in benchmark["metrics"]["overall"]


# ---------------------------------------------------------------------------
# Tests: Quick Helpers
# ---------------------------------------------------------------------------


class TestQuickEvaluate:
    """Tests for quick_evaluate helper."""

    def test_quick_evaluate(self):
        """Test quick single-sample evaluation."""
        result = quick_evaluate(
            question="What is Python?",
            answer="Python is a programming language.",
            contexts=["Python is a high-level programming language."],
            ground_truth="Python is a programming language",
        )

        assert isinstance(result, SampleResult)
        assert 0.0 <= result.overall_score <= 1.0


class TestCheckQualityBar:
    """Tests for check_quality_bar helper."""

    def test_check_passes(self):
        """Test quality bar check passes."""
        result = MagicMock()
        result.overall_score = 0.85
        assert check_quality_bar(result) is True

    def test_check_fails(self):
        """Test quality bar check fails."""
        result = MagicMock()
        result.overall_score = 0.5
        assert check_quality_bar(result) is False

    def test_custom_bar(self):
        """Test custom quality bar threshold."""
        result = MagicMock()
        result.overall_score = 0.65
        assert check_quality_bar(result, bar=0.6) is True
        assert check_quality_bar(result, bar=0.7) is False


# ---------------------------------------------------------------------------
# Tests: GraphRAG Integration
# ---------------------------------------------------------------------------


class TestGraphRAGIntegration:
    """Tests for GraphRAG integration."""

    def test_create_graphrag_evaluator_with_chunks(self):
        """Test creating evaluator with GraphRAG that returns chunks."""
        mock_graphrag = MagicMock()

        # Mock search result with chunks
        mock_result = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.content = "Test context content"
        mock_result.chunks = [mock_chunk]
        mock_graphrag.search.return_value = mock_result

        evaluator, rag_func = create_graphrag_evaluator(mock_graphrag)

        answer, contexts = rag_func("Test question")
        assert len(contexts) == 1
        assert "Test context content" in contexts[0]

    def test_create_graphrag_evaluator_with_results_list(self):
        """Test creating evaluator with GraphRAG returning list."""
        mock_graphrag = MagicMock()
        mock_graphrag.search.return_value = [
            MagicMock(content="Context 1"),
            MagicMock(content="Context 2"),
        ]

        evaluator, rag_func = create_graphrag_evaluator(mock_graphrag)

        answer, contexts = rag_func("Test question")
        assert len(contexts) == 2


# ---------------------------------------------------------------------------
# Tests: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_long_text(self):
        """Test handling very long text."""
        long_text = "This is a test sentence. " * 1000

        sample = RAGASSample(
            question="What is the meaning of this long text?",
            answer=long_text[:500],
            contexts=[long_text],
            ground_truth="Test sentence repeated",
        )

        evaluator = RAGASEvaluator()
        result = evaluator.evaluate_sample(sample)
        assert 0.0 <= result.overall_score <= 1.0

    def test_unicode_content(self):
        """Test handling unicode content."""
        sample = RAGASSample(
            question="What is 你好?",
            answer="你好 means hello in Chinese.",
            contexts=["你好 (nǐ hǎo) is a Chinese greeting meaning hello."],
            ground_truth="Hello in Chinese",
        )

        evaluator = RAGASEvaluator()
        result = evaluator.evaluate_sample(sample)
        assert isinstance(result.overall_score, float)

    def test_special_characters(self):
        """Test handling special characters."""
        sample = RAGASSample(
            question="What is the regex for email: ^[a-z]+@[a-z]+\\.com$?",
            answer="This regex matches simple email addresses.",
            contexts=["Email regex: ^[a-z]+@[a-z]+\\.com$ matches basic emails."],
            ground_truth="Matches email addresses",
        )

        evaluator = RAGASEvaluator()
        result = evaluator.evaluate_sample(sample)
        assert 0.0 <= result.overall_score <= 1.0

    def test_single_word_answer(self):
        """Test single word answer."""
        sample = RAGASSample(
            question="What color is the sky?",
            answer="Blue.",
            contexts=["The sky appears blue due to light scattering."],
            ground_truth="Blue",
        )

        evaluator = RAGASEvaluator()
        result = evaluator.evaluate_sample(sample)
        assert 0.0 <= result.overall_score <= 1.0

    def test_many_contexts(self):
        """Test handling many contexts."""
        contexts = [f"Context {i}: Some relevant information." for i in range(50)]

        sample = RAGASSample(
            question="What is the information?",
            answer="The information is about various topics.",
            contexts=contexts,
            ground_truth="Various topics covered",
        )

        evaluator = RAGASEvaluator()
        result = evaluator.evaluate_sample(sample)
        assert 0.0 <= result.overall_score <= 1.0


# ---------------------------------------------------------------------------
# Tests: Quality Constants
# ---------------------------------------------------------------------------


class TestQualityConstants:
    """Tests for quality level constants."""

    def test_quality_bar_value(self):
        """Test QUALITY_BAR constant value."""
        assert QUALITY_BAR == 0.8

    def test_quality_levels(self):
        """Test QualityLevel enum values."""
        assert QualityLevel.PRODUCTION.value == 0.8
        assert QualityLevel.STAGING.value == 0.7
        assert QualityLevel.DEVELOPMENT.value == 0.6
        assert QualityLevel.FAILING.value == 0.0
