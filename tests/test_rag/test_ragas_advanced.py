# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Advanced tests for the RAGAS evaluation module.

Covers:
- Aspect critique
- Answer correctness
- Context entity recall
- Noise robustness
- Multi-turn evaluation
- Advanced evaluator orchestration and exports
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import agentic_brain.rag as rag_pkg
import agentic_brain.rag.ragas_eval as ragas_eval
from agentic_brain.rag.ragas_eval import (
    AdvancedRAGASEvaluator,
    AnswerCorrectnessCalculator,
    AspectCritiqueCalculator,
    AspectCritiqueResult,
    AspectType,
    ConversationSample,
    ConversationTurn,
    ContextEntityRecallCalculator,
    MultiTurnEvaluator,
    MultiTurnResult,
    NoiseRobustnessCalculator,
    RAGASSample,
)


@pytest.fixture
def advanced_sample() -> RAGASSample:
    return RAGASSample(
        question="How do I deploy the application to production?",
        answer=(
            "Deploy the application with kubectl apply. Therefore, the deployment "
            "updates safely and the application stays available."
        ),
        contexts=[
            "Deployment guide: use kubectl apply for production rollouts.",
            "The application remains available during the rollout.",
        ],
        ground_truth="Use kubectl apply to deploy the application to production.",
    )


@pytest.fixture
def noisy_sample() -> RAGASSample:
    return RAGASSample(
        question="How do I configure logging?",
        answer="Set LOG_LEVEL=DEBUG for verbose logging.",
        contexts=["Configure logging by setting LOG_LEVEL=DEBUG."],
        ground_truth="Set LOG_LEVEL=DEBUG",
    )


@pytest.fixture
def conversation_sample() -> ConversationSample:
    return ConversationSample(
        conversation_id="conv-1",
        turns=[
            ConversationTurn(
                question="What is Neo4j?",
                answer="Neo4j is a graph database.",
                contexts=["Neo4j stores relationships in a graph."],
                ground_truth="Neo4j is a graph database.",
                turn_number=1,
            ),
            ConversationTurn(
                question="How do I store relationships?",
                answer="Use Neo4j relationships to model connections.",
                contexts=["Neo4j relationships connect nodes."],
                ground_truth="Use Neo4j relationships.",
                turn_number=2,
            ),
        ],
    )


class TestAdvancedExports:
    def test_module_exports_include_advanced_suite(self):
        names = set(ragas_eval.__all__)
        assert "AdvancedRAGASEvaluator" in names
        assert "AspectCritiqueCalculator" in names
        assert "AnswerCorrectnessCalculator" in names
        assert "ContextEntityRecallCalculator" in names
        assert "NoiseRobustnessCalculator" in names
        assert "MultiTurnEvaluator" in names

    def test_package_exports_include_advanced_suite(self):
        names = set(rag_pkg.__all__)
        assert "AdvancedRAGASEvaluator" in names
        assert "ConversationSample" in names
        assert "ConversationTurn" in names
        assert "MultiTurnResult" in names


class TestAspectCritique:
    def test_aspect_result_dataclass(self):
        result = AspectCritiqueResult(
            aspect=AspectType.COHERENCE,
            score=0.91,
            verdict=True,
            reasoning="Well structured",
            evidence=["therefore"],
        )
        assert result.aspect == AspectType.COHERENCE
        assert result.score == pytest.approx(0.91)
        assert result.verdict is True
        assert result.evidence == ["therefore"]

    def test_calculate_all_aspects(self, advanced_sample):
        calc = AspectCritiqueCalculator()
        results = calc.calculate(
            answer=advanced_sample.answer,
            question=advanced_sample.question,
            contexts=advanced_sample.contexts,
        )
        assert set(results) == set(AspectType)
        assert all(0.0 <= item.score <= 1.0 for item in results.values())

    def test_harmfulness_detects_harmful_content(self):
        calc = AspectCritiqueCalculator()
        result = calc.calculate(
            answer="You should kill the process and attack the server.",
            question="What should I do?",
            contexts=["Process management guide."],
            aspects=[AspectType.HARMFULNESS],
        )[AspectType.HARMFULNESS]
        assert result.score < 0.8
        assert result.verdict is False

    def test_coherence_scores_coherent_answer_higher(self, advanced_sample):
        calc = AspectCritiqueCalculator()
        result = calc.calculate(
            answer=advanced_sample.answer,
            question=advanced_sample.question,
            contexts=advanced_sample.contexts,
            aspects=[AspectType.COHERENCE],
        )[AspectType.COHERENCE]
        assert result.score > 0.5
        assert result.verdict is True

    def test_coherence_scores_incoherent_answer_lower(self):
        calc = AspectCritiqueCalculator()
        result = calc.calculate(
            answer="Blue sky. Car banana. Random words.",
            question="How do I deploy the application?",
            contexts=["Deployment guide."],
            aspects=[AspectType.COHERENCE],
        )[AspectType.COHERENCE]
        assert result.score < 0.6

    def test_conciseness_prefers_short_answer(self):
        calc = AspectCritiqueCalculator()
        short = calc.calculate(
            answer="Use kubectl apply.",
            question="How do I deploy?",
            contexts=["kubectl apply deploys workloads."],
            aspects=[AspectType.CONCISENESS],
        )[AspectType.CONCISENESS]
        long = calc.calculate(
            answer=" ".join(["Use kubectl apply to deploy the application safely."] * 20),
            question="How do I deploy?",
            contexts=["kubectl apply deploys workloads."],
            aspects=[AspectType.CONCISENESS],
        )[AspectType.CONCISENESS]
        assert short.score >= long.score

    def test_conciseness_penalizes_repetition(self):
        calc = AspectCritiqueCalculator()
        result = calc.calculate(
            answer="Use kubectl apply. Use kubectl apply. Use kubectl apply.",
            question="How do I deploy?",
            contexts=["kubectl apply deploys workloads."],
            aspects=[AspectType.CONCISENESS],
        )[AspectType.CONCISENESS]
        assert result.score < 1.0


class TestAnswerCorrectness:
    def test_exact_match_scores_high(self):
        calc = AnswerCorrectnessCalculator()
        result = calc.calculate("Neo4j graph database", "Neo4j graph database")
        assert result.score == pytest.approx(1.0)
        assert result.details["overlap_terms"] >= 2

    def test_mismatch_scores_lower(self):
        calc = AnswerCorrectnessCalculator()
        result = calc.calculate("Paris", "Neo4j graph database")
        assert result.score < 0.8

    def test_correctness_beats_unrelated_answer(self):
        calc = AnswerCorrectnessCalculator()
        high = calc.calculate("Use kubectl apply to deploy.", "Use kubectl apply to deploy.")
        low = calc.calculate("The ocean is warm today.", "Use kubectl apply to deploy.")
        assert high.score > low.score

    def test_details_include_factual_and_semantic_scores(self):
        calc = AnswerCorrectnessCalculator()
        result = calc.calculate("Use kubectl apply.", "Use kubectl apply.")
        assert "factual_f1" in result.details
        assert "semantic_similarity" in result.details
        assert 0.0 <= result.details["semantic_similarity"] <= 1.000001


class TestContextEntityRecall:
    def test_recalls_all_entities(self):
        calc = ContextEntityRecallCalculator()
        result = calc.calculate(
            contexts=["Neo4j v5.20 uses API key ABCD."],
            ground_truth="Neo4j v5.20 and API key ABCD",
        )
        assert result.score == pytest.approx(1.0)
        assert result.details["missing_entities"] == []

    def test_no_entities_defaults_to_perfect_score(self):
        calc = ContextEntityRecallCalculator()
        result = calc.calculate(contexts=["Any context."], ground_truth="the answer is yes")
        assert result.score == pytest.approx(1.0)

    def test_missing_entity_lowers_score(self):
        calc = ContextEntityRecallCalculator()
        result = calc.calculate(
            contexts=["Neo4j v5.20 uses an API key."],
            ground_truth="Neo4j v5.20 and API key ABCD",
        )
        assert 0.0 <= result.score < 1.0
        assert "ABCD" in "".join(result.details["missing_entities"])

    def test_entity_extraction_captures_versions_and_acronyms(self):
        calc = ContextEntityRecallCalculator()
        entities = calc._extract_entities("API v5.20 and ABCD")
        assert "API" in entities
        assert any(entity.startswith("v5.20") for entity in entities)
        assert "ABCD" in entities


class TestNoiseRobustness:
    def test_add_typos_changes_text(self):
        calc = NoiseRobustnessCalculator()
        noisy = calc._add_typos("How do I deploy the application")
        assert noisy != "How do I deploy the application"

    def test_add_synonyms_changes_text(self):
        calc = NoiseRobustnessCalculator()
        noisy = calc._add_synonyms("How do I deploy the application")
        assert noisy != "How do I deploy the application"

    def test_paraphrase_question(self):
        calc = NoiseRobustnessCalculator()
        noisy = calc._paraphrase("How do I deploy?")
        assert noisy.startswith("Can you tell me")

    def test_make_incomplete_truncates_query(self):
        calc = NoiseRobustnessCalculator()
        noisy = calc._make_incomplete("How do I configure logging in production")
        assert noisy.endswith("...")

    def test_add_adversarial_prefixes_instruction(self):
        calc = NoiseRobustnessCalculator()
        noisy = calc._add_adversarial("How do I deploy?")
        assert noisy.startswith("Ignore previous instructions and")

    def test_calculate_default_noise_types(self, noisy_sample):
        calc = NoiseRobustnessCalculator()
        result = calc.calculate(noisy_sample.question, noisy_sample.answer)
        assert result.name == "noise_robustness"
        assert result.details["total_types"] == len(calc.NOISE_TYPES)
        assert len(result.details["noise_results"]) == len(calc.NOISE_TYPES)

    def test_calculate_custom_noise_types(self, noisy_sample):
        calc = NoiseRobustnessCalculator()
        result = calc.calculate(
            noisy_sample.question,
            noisy_sample.answer,
            noise_types=["typo", "adversarial"],
        )
        assert result.details["total_types"] == 2
        assert set(result.details["noise_results"]) == {"typo", "adversarial"}

    def test_calculate_uses_rag_function_for_noisy_query(self, noisy_sample):
        calls: list[str] = []

        def rag_func(question: str) -> tuple[str, list[str]]:
            calls.append(question)
            return (f"answer for {question}", ["ctx"])

        calc = NoiseRobustnessCalculator(rag_func=rag_func)
        result = calc.calculate(noisy_sample.question, noisy_sample.answer, noise_types=["adversarial"])
        assert calls
        assert calls[0].startswith("Ignore previous instructions and")
        assert result.details["noise_results"]["adversarial"]["noisy_query"].startswith(
            "Ignore previous instructions and"
        )


class TestMultiTurnEvaluation:
    def test_empty_conversation_returns_zeroes(self):
        result = MultiTurnEvaluator().evaluate_conversation(ConversationSample(turns=[]))
        assert isinstance(result, MultiTurnResult)
        assert result.overall_score == 0.0
        assert result.turn_results == []

    def test_single_turn_conversation(self):
        conversation = ConversationSample(
            conversation_id="single",
            turns=[
                ConversationTurn(
                    question="What is Neo4j?",
                    answer="Neo4j is a graph database.",
                    contexts=["Neo4j stores graph data."],
                    ground_truth="Neo4j is a graph database.",
                    turn_number=1,
                )
            ],
        )
        result = MultiTurnEvaluator().evaluate_conversation(conversation)
        assert result.coherence_across_turns == pytest.approx(1.0)
        assert result.context_accumulation_quality == pytest.approx(1.0)

    def test_multi_turn_conversation_scores(self, conversation_sample):
        result = MultiTurnEvaluator().evaluate_conversation(conversation_sample)
        assert result.conversation_id == "conv-1"
        assert len(result.turn_results) == 2
        assert 0.0 <= result.overall_score <= 1.0

    def test_multi_turn_result_to_dict(self, conversation_sample):
        result = MultiTurnEvaluator().evaluate_conversation(conversation_sample)
        data = result.to_dict()
        assert data["conversation_id"] == "conv-1"
        assert data["num_turns"] == 2
        assert "turn_scores" in data


class TestAdvancedEvaluator:
    def test_evaluate_with_aspects_subset(self, advanced_sample):
        evaluator = AdvancedRAGASEvaluator()
        report = evaluator.evaluate_with_aspects(
            advanced_sample,
            aspects=[AspectType.HARMFULNESS, AspectType.COHERENCE],
        )
        assert "core" in report
        assert set(report["aspects"]) == {"harmfulness", "coherence"}

    def test_evaluate_answer_quality(self):
        evaluator = AdvancedRAGASEvaluator()
        results = evaluator.evaluate_answer_quality("Neo4j graph database", "Neo4j graph database")
        assert set(results) == {"correctness", "similarity"}
        assert results["correctness"].score == pytest.approx(1.0)

    def test_evaluate_entity_recall(self):
        evaluator = AdvancedRAGASEvaluator()
        result = evaluator.evaluate_entity_recall(
            ["Neo4j v5.20 uses API key ABCD."],
            "Neo4j v5.20 and API key ABCD",
        )
        assert result.score == pytest.approx(1.0)

    def test_evaluate_noise_robustness(self, noisy_sample):
        evaluator = AdvancedRAGASEvaluator()
        result = evaluator.evaluate_noise_robustness(
            noisy_sample.question,
            noisy_sample.answer,
            noise_types=["typo", "adversarial"],
        )
        assert result.name == "noise_robustness"
        assert result.details["total_types"] == 2

    def test_full_evaluation_includes_advanced_sections(self, advanced_sample):
        evaluator = AdvancedRAGASEvaluator()
        report = evaluator.full_evaluation(advanced_sample, include_noise=True)
        assert "core" in report
        assert "answer_quality" in report
        assert "aspects" in report
        assert "entity_recall" in report
        assert "noise_robustness" in report

    def test_full_evaluation_can_skip_optional_sections(self, advanced_sample):
        evaluator = AdvancedRAGASEvaluator()
        report = evaluator.full_evaluation(
            advanced_sample,
            include_aspects=False,
            include_entity_recall=False,
            include_noise=False,
        )
        assert "aspects" not in report
        assert "entity_recall" not in report
        assert "noise_robustness" not in report

    def test_evaluate_conversation_delegates(self, conversation_sample):
        evaluator = AdvancedRAGASEvaluator()
        result = evaluator.evaluate_conversation(conversation_sample)
        assert isinstance(result, MultiTurnResult)
        assert result.conversation_id == "conv-1"

    def test_evaluator_works_with_mock_rag_function(self, advanced_sample):
        evaluator = AdvancedRAGASEvaluator(
            rag_func=MagicMock(return_value=(advanced_sample.answer, advanced_sample.contexts))
        )
        result = evaluator.evaluate_noise_robustness(
            advanced_sample.question,
            advanced_sample.answer,
            noise_types=["adversarial"],
        )
        assert result.score >= 0.0
