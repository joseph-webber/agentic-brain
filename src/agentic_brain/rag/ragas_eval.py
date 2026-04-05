# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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
RAGAS (Retrieval-Augmented Generation Assessment) Evaluation Module.

Implements the 4 core RAGAS metrics (2026 industry standard):
1. Faithfulness - Are claims in the answer supported by retrieved context?
2. Answer Relevancy - Does the answer address the question?
3. Context Precision - Are the top-ranked retrieved chunks the most relevant?
4. Context Recall - Does the retrieved context cover the required information?

Integration with GraphRAG:
    from agentic_brain.rag.ragas_eval import RAGASEvaluator, RAGASDataset

    # Create evaluation dataset with ground truth
    dataset = RAGASDataset()
    dataset.add_sample(
        question="How do I deploy to production?",
        ground_truth="Use kubectl apply -f deployment.yaml",
        contexts=["Deploy guide: Run kubectl apply...", "Config: Set replicas..."],
        answer="Run kubectl apply -f deployment.yaml to deploy."
    )

    # Evaluate
    evaluator = RAGASEvaluator()
    results = evaluator.evaluate(dataset)

    # Check quality bar (0.8+ is production-ready)
    assert results.overall_score >= 0.8, f"Quality bar not met: {results}"

Metrics reference:
- Faithfulness: LLM-based claim verification against context
- Answer Relevancy: Cosine similarity of question vs synthetic questions from answer
- Context Precision: Weighted precision of relevant contexts in top positions
- Context Recall: Coverage of ground truth statements in retrieved context
"""

from __future__ import annotations

import json
import logging
import math
import re
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Quality Thresholds
# ---------------------------------------------------------------------------

class QualityLevel(Enum):
    """RAGAS quality levels for production readiness."""
    PRODUCTION = 0.8   # Ready for production deployment
    STAGING = 0.7      # Acceptable for staging/testing
    DEVELOPMENT = 0.6  # Needs improvement
    FAILING = 0.0      # Below acceptable quality


QUALITY_BAR = 0.8  # Default production quality threshold


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class RAGASSample:
    """Single evaluation sample with ground truth."""

    question: str
    answer: str
    contexts: list[str]  # Retrieved context chunks
    ground_truth: str  # Expected/reference answer
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.question.strip():
            raise ValueError("Question cannot be empty")
        if not self.answer.strip():
            raise ValueError("Answer cannot be empty")
        if not self.ground_truth.strip():
            raise ValueError("Ground truth cannot be empty")


@dataclass
class MetricResult:
    """Result for a single RAGAS metric."""

    name: str
    score: float  # 0.0 to 1.0
    details: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""

    def __repr__(self) -> str:
        return f"{self.name}: {self.score:.3f}"

    @property
    def meets_quality_bar(self) -> bool:
        """Check if metric meets production quality threshold."""
        return self.score >= QUALITY_BAR


@dataclass
class SampleResult:
    """RAGAS evaluation results for a single sample."""

    sample: RAGASSample
    faithfulness: MetricResult
    answer_relevancy: MetricResult
    context_precision: MetricResult
    context_recall: MetricResult

    @property
    def overall_score(self) -> float:
        """Weighted average of all metrics."""
        return (
            self.faithfulness.score * 0.25 +
            self.answer_relevancy.score * 0.25 +
            self.context_precision.score * 0.25 +
            self.context_recall.score * 0.25
        )

    @property
    def meets_quality_bar(self) -> bool:
        """Check if all metrics meet quality threshold."""
        return all([
            self.faithfulness.meets_quality_bar,
            self.answer_relevancy.meets_quality_bar,
            self.context_precision.meets_quality_bar,
            self.context_recall.meets_quality_bar,
        ])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "question": self.sample.question,
            "overall_score": self.overall_score,
            "meets_quality_bar": self.meets_quality_bar,
            "metrics": {
                "faithfulness": self.faithfulness.score,
                "answer_relevancy": self.answer_relevancy.score,
                "context_precision": self.context_precision.score,
                "context_recall": self.context_recall.score,
            },
            "details": {
                "faithfulness": self.faithfulness.details,
                "answer_relevancy": self.answer_relevancy.details,
                "context_precision": self.context_precision.details,
                "context_recall": self.context_recall.details,
            },
        }


@dataclass
class RAGASResults:
    """Aggregated RAGAS evaluation results."""

    sample_results: list[SampleResult]
    avg_faithfulness: float
    avg_answer_relevancy: float
    avg_context_precision: float
    avg_context_recall: float
    overall_score: float
    num_samples: int
    quality_level: QualityLevel
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def meets_quality_bar(self) -> bool:
        """Check if overall score meets production threshold."""
        return self.overall_score >= QUALITY_BAR

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "num_samples": self.num_samples,
            "overall_score": self.overall_score,
            "quality_level": self.quality_level.name,
            "meets_quality_bar": self.meets_quality_bar,
            "metrics": {
                "faithfulness": self.avg_faithfulness,
                "answer_relevancy": self.avg_answer_relevancy,
                "context_precision": self.avg_context_precision,
                "context_recall": self.avg_context_recall,
            },
            "samples": [r.to_dict() for r in self.sample_results],
        }

    def __repr__(self) -> str:
        status = "✅ PASS" if self.meets_quality_bar else "❌ FAIL"
        lines = [
            f"📊 RAGAS Evaluation Results ({self.num_samples} samples) {status}",
            f"Overall Score: {self.overall_score:.3f} ({self.quality_level.name})",
            f"Faithfulness: {self.avg_faithfulness:.3f}",
            f"Answer Relevancy: {self.avg_answer_relevancy:.3f}",
            f"Context Precision: {self.avg_context_precision:.3f}",
            f"Context Recall: {self.avg_context_recall:.3f}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class RAGASDataset:
    """Dataset for RAGAS evaluation with ground truth."""

    def __init__(self):
        self.samples: list[RAGASSample] = []

    def add_sample(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add an evaluation sample."""
        self.samples.append(
            RAGASSample(
                question=question,
                answer=answer,
                contexts=contexts,
                ground_truth=ground_truth,
                metadata=metadata or {},
            )
        )

    def add_samples_from_file(self, path: Path) -> None:
        """Load samples from JSON file."""
        with open(path) as f:
            data = json.load(f)

        for item in data:
            self.add_sample(
                question=item["question"],
                answer=item["answer"],
                contexts=item["contexts"],
                ground_truth=item["ground_truth"],
                metadata=item.get("metadata", {}),
            )

    def save(self, path: Path) -> None:
        """Save dataset to JSON."""
        data = [
            {
                "question": s.question,
                "answer": s.answer,
                "contexts": s.contexts,
                "ground_truth": s.ground_truth,
                "metadata": s.metadata,
            }
            for s in self.samples
        ]

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def __len__(self) -> int:
        return len(self.samples)

    def __iter__(self):
        return iter(self.samples)


# ---------------------------------------------------------------------------
# LLM Judge Protocol
# ---------------------------------------------------------------------------

class LLMJudge(Protocol):
    """Protocol for LLM-based evaluation (for faithfulness/relevancy)."""

    def judge_faithfulness(
        self, answer: str, contexts: list[str]
    ) -> tuple[float, list[dict[str, Any]]]:
        """
        Judge if claims in answer are supported by contexts.

        Returns:
            Tuple of (score, claim_verifications)
            where claim_verifications is a list of {claim, supported, context_evidence}
        """
        ...

    def generate_synthetic_questions(self, answer: str, n: int = 3) -> list[str]:
        """Generate synthetic questions from the answer for relevancy check."""
        ...

    def extract_statements(self, text: str) -> list[str]:
        """Extract factual statements from text."""
        ...


class SimpleLLMJudge:
    """
    Lightweight LLM-free judge using heuristics.

    For production, replace with actual LLM (Claude, GPT-4) for better accuracy.
    This implementation provides a baseline using text matching and overlap.
    """

    def judge_faithfulness(
        self, answer: str, contexts: list[str]
    ) -> tuple[float, list[dict[str, Any]]]:
        """Heuristic faithfulness check using text overlap."""
        claims = self._extract_claims(answer)
        if not claims:
            return 1.0, []

        context_text = " ".join(contexts).lower()
        verifications = []
        supported_count = 0

        for claim in claims:
            claim_lower = claim.lower()
            # Check if key terms from claim appear in context
            key_terms = self._extract_key_terms(claim_lower)
            overlap = sum(1 for term in key_terms if term in context_text)
            supported = overlap >= len(key_terms) * 0.5 if key_terms else True

            if supported:
                supported_count += 1

            verifications.append({
                "claim": claim,
                "supported": supported,
                "overlap_ratio": overlap / len(key_terms) if key_terms else 1.0,
            })

        score = supported_count / len(claims) if claims else 1.0
        return score, verifications

    def generate_synthetic_questions(self, answer: str, n: int = 3) -> list[str]:
        """Generate simple question patterns from answer."""
        sentences = self._split_sentences(answer)
        questions = []

        patterns = [
            "What is {}?",
            "How does {} work?",
            "Can you explain {}?",
        ]

        for sentence in sentences[:n]:
            # Extract the main subject/topic
            topic = self._extract_topic(sentence)
            if topic:
                pattern = patterns[len(questions) % len(patterns)]
                questions.append(pattern.format(topic))

        return questions[:n]

    def extract_statements(self, text: str) -> list[str]:
        """Extract factual statements from text."""
        sentences = self._split_sentences(text)
        statements = []

        for sentence in sentences:
            # Skip questions and commands
            if sentence.strip().endswith("?"):
                continue
            if sentence.strip().startswith(("Please", "Note:", "Warning:")):
                continue
            if len(sentence.split()) >= 4:  # At least 4 words
                statements.append(sentence.strip())

        return statements

    def _extract_claims(self, text: str) -> list[str]:
        """Extract claims/statements from text."""
        return self.extract_statements(text)

    def _extract_key_terms(self, text: str) -> list[str]:
        """Extract key terms (nouns, verbs) from text."""
        # Simple approach: words that are longer and not stopwords
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "this",
            "that", "these", "those", "it", "its", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "or", "and",
        }
        words = re.findall(r'\b\w+\b', text.lower())
        return [w for w in words if w not in stopwords and len(w) > 2]

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_topic(self, sentence: str) -> str:
        """Extract the main topic from a sentence."""
        words = sentence.split()
        # Take first 3-5 significant words
        topic_words = []
        for word in words:
            clean = re.sub(r'[^\w\s]', '', word)
            if clean and len(clean) > 2:
                topic_words.append(clean)
            if len(topic_words) >= 4:
                break
        return " ".join(topic_words)


# ---------------------------------------------------------------------------
# Embedding Provider Protocol
# ---------------------------------------------------------------------------

class EmbeddingFunc(Protocol):
    """Protocol for embedding function."""

    def __call__(self, text: str) -> list[float]:
        """Embed text and return vector."""
        ...


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


def _simple_embedding(text: str, dim: int = 128) -> list[float]:
    """Simple hash-based embedding for testing (not for production)."""
    # Deterministic embedding based on text hash
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(text[:100]))
    raw = [float((seed * (i + 1)) % 17 - 8) for i in range(dim)]
    norm = math.sqrt(sum(v * v for v in raw))
    return [v / norm if norm > 0 else 0.0 for v in raw]


# ---------------------------------------------------------------------------
# RAGAS Metric Calculators
# ---------------------------------------------------------------------------

class FaithfulnessCalculator:
    """
    Calculate Faithfulness metric.

    Measures whether the claims in the generated answer are supported
    by the retrieved context. Higher score = more faithful to sources.

    Formula: (Number of claims supported by context) / (Total claims)
    """

    def __init__(self, judge: Optional[LLMJudge] = None):
        self.judge = judge or SimpleLLMJudge()

    def calculate(self, sample: RAGASSample) -> MetricResult:
        """Calculate faithfulness score for a sample."""
        if not sample.contexts:
            return MetricResult(
                name="faithfulness",
                score=0.0,
                details={"reason": "No context provided"},
                reasoning="Cannot verify faithfulness without context",
            )

        score, verifications = self.judge.judge_faithfulness(
            sample.answer, sample.contexts
        )

        supported = sum(1 for v in verifications if v.get("supported", False))
        total = len(verifications)

        return MetricResult(
            name="faithfulness",
            score=score,
            details={
                "claims_verified": total,
                "claims_supported": supported,
                "verifications": verifications,
            },
            reasoning=f"{supported}/{total} claims supported by context",
        )


class AnswerRelevancyCalculator:
    """
    Calculate Answer Relevancy metric.

    Measures how well the answer addresses the original question.
    Uses synthetic question generation and embedding similarity.

    Formula: Average cosine similarity between original question and
             synthetic questions generated from the answer.
    """

    def __init__(
        self,
        judge: Optional[LLMJudge] = None,
        embed_func: Optional[EmbeddingFunc] = None,
    ):
        self.judge = judge or SimpleLLMJudge()
        self.embed_func = embed_func or _simple_embedding

    def calculate(self, sample: RAGASSample) -> MetricResult:
        """Calculate answer relevancy score."""
        # Generate synthetic questions from the answer
        synthetic_questions = self.judge.generate_synthetic_questions(
            sample.answer, n=3
        )

        if not synthetic_questions:
            # Fallback: direct embedding similarity
            q_embed = self.embed_func(sample.question)
            a_embed = self.embed_func(sample.answer)
            score = max(0.0, _cosine_similarity(q_embed, a_embed))

            return MetricResult(
                name="answer_relevancy",
                score=score,
                details={
                    "method": "direct_similarity",
                    "similarity": score,
                },
                reasoning="Direct question-answer similarity (no synthetic questions)",
            )

        # Calculate similarity between original question and synthetic questions
        q_embed = self.embed_func(sample.question)
        similarities = []

        for syn_q in synthetic_questions:
            syn_embed = self.embed_func(syn_q)
            sim = _cosine_similarity(q_embed, syn_embed)
            similarities.append({
                "synthetic_question": syn_q,
                "similarity": sim,
            })

        avg_similarity = statistics.mean(s["similarity"] for s in similarities)
        score = max(0.0, min(1.0, avg_similarity))

        return MetricResult(
            name="answer_relevancy",
            score=score,
            details={
                "method": "synthetic_questions",
                "synthetic_questions": synthetic_questions,
                "similarities": similarities,
            },
            reasoning=f"Avg similarity to synthetic questions: {score:.3f}",
        )


class ContextPrecisionCalculator:
    """
    Calculate Context Precision metric.

    Measures whether the most relevant contexts are ranked higher.
    Contexts that contain ground truth information should be at the top.

    Formula: Weighted precision where earlier positions matter more.
    """

    def __init__(self, embed_func: Optional[EmbeddingFunc] = None):
        self.embed_func = embed_func or _simple_embedding

    def calculate(self, sample: RAGASSample) -> MetricResult:
        """Calculate context precision score."""
        if not sample.contexts:
            return MetricResult(
                name="context_precision",
                score=0.0,
                details={"reason": "No context provided"},
                reasoning="Cannot calculate precision without context",
            )

        # Determine relevance of each context to ground truth
        gt_embed = self.embed_func(sample.ground_truth)
        relevance_scores = []

        for i, context in enumerate(sample.contexts):
            ctx_embed = self.embed_func(context)
            similarity = _cosine_similarity(gt_embed, ctx_embed)
            relevance_scores.append({
                "rank": i + 1,
                "context_preview": context[:100] + "..." if len(context) > 100 else context,
                "relevance": similarity,
                "is_relevant": similarity >= 0.3,  # Threshold for "relevant"
            })

        # Calculate weighted precision (AP@K style)
        # Higher weight for relevant contexts appearing earlier
        precision_sum = 0.0
        relevant_count = 0

        for i, score_info in enumerate(relevance_scores):
            if score_info["is_relevant"]:
                relevant_count += 1
                precision_at_i = relevant_count / (i + 1)
                precision_sum += precision_at_i

        total_relevant = sum(1 for s in relevance_scores if s["is_relevant"])
        score = precision_sum / total_relevant if total_relevant > 0 else 0.0

        return MetricResult(
            name="context_precision",
            score=min(1.0, score),
            details={
                "context_scores": relevance_scores,
                "total_contexts": len(sample.contexts),
                "relevant_contexts": total_relevant,
            },
            reasoning=f"{total_relevant}/{len(sample.contexts)} contexts relevant, precision={score:.3f}",
        )


class ContextRecallCalculator:
    """
    Calculate Context Recall metric.

    Measures whether the retrieved context covers the information
    needed to answer the question (based on ground truth).

    Formula: (Statements from ground truth found in context) / (Total statements)
    """

    def __init__(self, judge: Optional[LLMJudge] = None):
        self.judge = judge or SimpleLLMJudge()

    def calculate(self, sample: RAGASSample) -> MetricResult:
        """Calculate context recall score."""
        if not sample.contexts:
            return MetricResult(
                name="context_recall",
                score=0.0,
                details={"reason": "No context provided"},
                reasoning="Cannot calculate recall without context",
            )

        # Extract statements from ground truth
        gt_statements = self.judge.extract_statements(sample.ground_truth)

        if not gt_statements:
            # If no statements, check if ground truth key terms appear in context
            context_text = " ".join(sample.contexts).lower()
            gt_terms = set(sample.ground_truth.lower().split())
            overlap = sum(1 for t in gt_terms if t in context_text)
            score = overlap / len(gt_terms) if gt_terms else 1.0

            return MetricResult(
                name="context_recall",
                score=min(1.0, score),
                details={"method": "term_overlap", "overlap_ratio": score},
                reasoning="Ground truth term overlap with context",
            )

        # Check which statements are covered by context
        context_text = " ".join(sample.contexts).lower()
        statement_coverage = []

        for statement in gt_statements:
            # Check if key terms from statement appear in context
            terms = set(re.findall(r'\b\w{4,}\b', statement.lower()))
            if not terms:
                statement_coverage.append({
                    "statement": statement,
                    "covered": True,
                    "coverage_ratio": 1.0,
                })
                continue

            overlap = sum(1 for t in terms if t in context_text)
            coverage = overlap / len(terms)
            covered = coverage >= 0.5

            statement_coverage.append({
                "statement": statement,
                "covered": covered,
                "coverage_ratio": coverage,
            })

        covered_count = sum(1 for s in statement_coverage if s["covered"])
        score = covered_count / len(statement_coverage)

        return MetricResult(
            name="context_recall",
            score=score,
            details={
                "total_statements": len(gt_statements),
                "covered_statements": covered_count,
                "statement_coverage": statement_coverage,
            },
            reasoning=f"{covered_count}/{len(gt_statements)} ground truth statements covered",
        )


# ---------------------------------------------------------------------------
# Main Evaluator
# ---------------------------------------------------------------------------

class RAGASEvaluator:
    """
    RAGAS Evaluator for RAG systems.

    Evaluates retrieval-augmented generation quality using the 4 core metrics:
    - Faithfulness
    - Answer Relevancy
    - Context Precision
    - Context Recall

    Usage:
        evaluator = RAGASEvaluator()
        results = evaluator.evaluate(dataset)

        # Check quality bar
        if results.meets_quality_bar:
            print("Production ready!")
        else:
            print(f"Needs improvement: {results.overall_score:.2f}")

        # A/B test two RAG configurations
        comparison = evaluator.compare(dataset_a, dataset_b)
        print(f"Winner: {comparison['winner']}")
    """

    def __init__(
        self,
        judge: Optional[LLMJudge] = None,
        embed_func: Optional[EmbeddingFunc] = None,
        quality_bar: float = QUALITY_BAR,
    ):
        """
        Initialize RAGAS evaluator.

        Args:
            judge: LLM judge for faithfulness/relevancy (uses SimpleLLMJudge if None)
            embed_func: Embedding function for similarity calculations
            quality_bar: Threshold for production quality (default 0.8)
        """
        self.judge = judge or SimpleLLMJudge()
        self.embed_func = embed_func or _simple_embedding
        self.quality_bar = quality_bar

        # Initialize metric calculators
        self.faithfulness_calc = FaithfulnessCalculator(self.judge)
        self.answer_relevancy_calc = AnswerRelevancyCalculator(
            self.judge, self.embed_func
        )
        self.context_precision_calc = ContextPrecisionCalculator(self.embed_func)
        self.context_recall_calc = ContextRecallCalculator(self.judge)

        self.results_history: list[RAGASResults] = []

    def evaluate_sample(self, sample: RAGASSample) -> SampleResult:
        """Evaluate a single sample."""
        return SampleResult(
            sample=sample,
            faithfulness=self.faithfulness_calc.calculate(sample),
            answer_relevancy=self.answer_relevancy_calc.calculate(sample),
            context_precision=self.context_precision_calc.calculate(sample),
            context_recall=self.context_recall_calc.calculate(sample),
        )

    def evaluate(self, dataset: RAGASDataset) -> RAGASResults:
        """
        Evaluate dataset with all RAGAS metrics.

        Args:
            dataset: RAGASDataset with samples to evaluate

        Returns:
            RAGASResults with aggregated metrics
        """
        if len(dataset) == 0:
            return RAGASResults(
                sample_results=[],
                avg_faithfulness=0.0,
                avg_answer_relevancy=0.0,
                avg_context_precision=0.0,
                avg_context_recall=0.0,
                overall_score=0.0,
                num_samples=0,
                quality_level=QualityLevel.FAILING,
            )

        sample_results = [self.evaluate_sample(s) for s in dataset]

        # Aggregate metrics
        avg_faithfulness = statistics.mean(r.faithfulness.score for r in sample_results)
        avg_answer_relevancy = statistics.mean(r.answer_relevancy.score for r in sample_results)
        avg_context_precision = statistics.mean(r.context_precision.score for r in sample_results)
        avg_context_recall = statistics.mean(r.context_recall.score for r in sample_results)

        overall_score = (
            avg_faithfulness * 0.25 +
            avg_answer_relevancy * 0.25 +
            avg_context_precision * 0.25 +
            avg_context_recall * 0.25
        )

        # Determine quality level
        if overall_score >= QualityLevel.PRODUCTION.value:
            quality_level = QualityLevel.PRODUCTION
        elif overall_score >= QualityLevel.STAGING.value:
            quality_level = QualityLevel.STAGING
        elif overall_score >= QualityLevel.DEVELOPMENT.value:
            quality_level = QualityLevel.DEVELOPMENT
        else:
            quality_level = QualityLevel.FAILING

        results = RAGASResults(
            sample_results=sample_results,
            avg_faithfulness=avg_faithfulness,
            avg_answer_relevancy=avg_answer_relevancy,
            avg_context_precision=avg_context_precision,
            avg_context_recall=avg_context_recall,
            overall_score=overall_score,
            num_samples=len(dataset),
            quality_level=quality_level,
        )

        self.results_history.append(results)
        return results

    def evaluate_rag_pipeline(
        self,
        rag_func: Callable[[str], tuple[str, list[str]]],
        questions: list[str],
        ground_truths: list[str],
    ) -> RAGASResults:
        """
        Evaluate a RAG pipeline function directly.

        Args:
            rag_func: Function that takes question, returns (answer, contexts)
            questions: List of test questions
            ground_truths: List of expected answers

        Returns:
            RAGASResults with evaluation metrics
        """
        if len(questions) != len(ground_truths):
            raise ValueError("Questions and ground_truths must have same length")

        dataset = RAGASDataset()

        for question, ground_truth in zip(questions, ground_truths):
            answer, contexts = rag_func(question)
            dataset.add_sample(
                question=question,
                answer=answer,
                contexts=contexts,
                ground_truth=ground_truth,
            )

        return self.evaluate(dataset)

    def compare(
        self,
        dataset_a: RAGASDataset,
        dataset_b: RAGASDataset,
        names: tuple[str, str] = ("A", "B"),
    ) -> dict[str, Any]:
        """
        Compare two RAG configurations/datasets.

        Returns:
            Dictionary with comparison results and winner
        """
        results_a = self.evaluate(dataset_a)
        results_b = self.evaluate(dataset_b)

        comparison = {
            names[0]: results_a.to_dict(),
            names[1]: results_b.to_dict(),
            "improvements": {
                "faithfulness": results_b.avg_faithfulness - results_a.avg_faithfulness,
                "answer_relevancy": results_b.avg_answer_relevancy - results_a.avg_answer_relevancy,
                "context_precision": results_b.avg_context_precision - results_a.avg_context_precision,
                "context_recall": results_b.avg_context_recall - results_a.avg_context_recall,
                "overall": results_b.overall_score - results_a.overall_score,
            },
            "winner": names[1] if results_b.overall_score > results_a.overall_score else names[0],
        }

        return comparison

    def save_results(self, path: Path) -> None:
        """Save evaluation results to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)

        data = [r.to_dict() for r in self.results_history]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def benchmark(
        self,
        rag_func: Callable[[str], tuple[str, list[str]]],
        dataset: RAGASDataset,
        n_iterations: int = 3,
    ) -> dict[str, Any]:
        """
        Run multiple evaluation iterations for benchmarking.

        Returns:
            Dictionary with mean, std, min, max for each metric
        """
        all_results = []

        for _ in range(n_iterations):
            questions = [s.question for s in dataset.samples]
            ground_truths = [s.ground_truth for s in dataset.samples]
            results = self.evaluate_rag_pipeline(rag_func, questions, ground_truths)
            all_results.append(results)

        metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall", "overall"]
        benchmark_stats = {}

        for metric in metrics:
            if metric == "overall":
                values = [r.overall_score for r in all_results]
            else:
                values = [getattr(r, f"avg_{metric}") for r in all_results]

            benchmark_stats[metric] = {
                "mean": statistics.mean(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
            }

        return {
            "iterations": n_iterations,
            "metrics": benchmark_stats,
            "meets_quality_bar": benchmark_stats["overall"]["mean"] >= self.quality_bar,
        }


# ---------------------------------------------------------------------------
# Integration with GraphRAG
# ---------------------------------------------------------------------------

def create_graphrag_evaluator(
    graphrag,
    embed_func: Optional[EmbeddingFunc] = None,
) -> tuple[RAGASEvaluator, Callable]:
    """
    Create RAGAS evaluator configured for GraphRAG.

    Args:
        graphrag: GraphRAG instance
        embed_func: Optional custom embedding function

    Returns:
        Tuple of (evaluator, wrapped_rag_func)

    Usage:
        from agentic_brain.rag import GraphRAG
        from agentic_brain.rag.ragas_eval import create_graphrag_evaluator

        graphrag = GraphRAG(neo4j_uri="bolt://localhost:7687")
        evaluator, rag_func = create_graphrag_evaluator(graphrag)

        results = evaluator.evaluate_rag_pipeline(
            rag_func,
            questions=["How do I deploy?"],
            ground_truths=["Use kubectl apply"]
        )
    """
    def rag_wrapper(question: str) -> tuple[str, list[str]]:
        """Wrap GraphRAG search to return (answer, contexts) tuple."""
        results = graphrag.search(question)

        # Extract contexts from results
        contexts = []
        if hasattr(results, "chunks"):
            contexts = [chunk.content for chunk in results.chunks]
        elif hasattr(results, "results"):
            contexts = [r.content if hasattr(r, "content") else str(r) for r in results.results]
        elif isinstance(results, list):
            contexts = [r.content if hasattr(r, "content") else str(r) for r in results]

        # Get answer (may need LLM generation in real implementation)
        answer = "\n".join(contexts[:3]) if contexts else "No results found"

        return answer, contexts

    # Use GraphRAG's embedding if available
    if embed_func is None and hasattr(graphrag, "_embed"):
        embed_func = graphrag._embed
    elif embed_func is None and hasattr(graphrag, "embed"):
        embed_func = graphrag.embed

    evaluator = RAGASEvaluator(embed_func=embed_func)
    return evaluator, rag_wrapper


# ---------------------------------------------------------------------------
# Quick Evaluation Helpers
# ---------------------------------------------------------------------------

def quick_evaluate(
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str,
) -> SampleResult:
    """
    Quick single-sample evaluation.

    Usage:
        result = quick_evaluate(
            question="How do I deploy?",
            answer="Run kubectl apply -f deployment.yaml",
            contexts=["Deployment: Use kubectl apply..."],
            ground_truth="Use kubectl apply -f deployment.yaml"
        )
        print(f"Overall: {result.overall_score:.2f}")
    """
    evaluator = RAGASEvaluator()
    sample = RAGASSample(
        question=question,
        answer=answer,
        contexts=contexts,
        ground_truth=ground_truth,
    )
    return evaluator.evaluate_sample(sample)


def check_quality_bar(results: RAGASResults | SampleResult, bar: float = QUALITY_BAR) -> bool:
    """Check if results meet the quality bar."""
    score = results.overall_score
    return score >= bar


__all__ = [
    # Data structures
    "RAGASSample",
    "RAGASDataset",
    "MetricResult",
    "SampleResult",
    "RAGASResults",
    "QualityLevel",
    "QUALITY_BAR",
    # Evaluator
    "RAGASEvaluator",
    # Metric calculators
    "FaithfulnessCalculator",
    "AnswerRelevancyCalculator",
    "ContextPrecisionCalculator",
    "ContextRecallCalculator",
    # Protocols
    "LLMJudge",
    "SimpleLLMJudge",
    "EmbeddingFunc",
    # Integration
    "create_graphrag_evaluator",
    # Helpers
    "quick_evaluate",
    "check_quality_bar",
]
