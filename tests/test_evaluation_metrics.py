# SPDX-License-Identifier: Apache-2.0
import pytest

from agentic_brain.evaluation.metrics import (
    answer_similarity,
    context_precision,
    context_recall,
    faithfulness_score,
    relevancy_score,
)


def test_answer_similarity_identical():
    assert answer_similarity("Hello", "Hello") == 1.0


def test_answer_similarity_case_and_whitespace():
    assert pytest.approx(answer_similarity(" Hello ", "hello"), 0.001) == 1.0


def test_answer_similarity_different():
    assert answer_similarity("abc", "xyz") < 0.2


def test_context_precision_empty_retrieved():
    assert context_precision([], ["a"]) == 0.0


def test_context_precision_perfect():
    assert context_precision(["a", "b"], ["a", "b", "c"]) == 1.0


def test_context_recall_empty_gold():
    assert context_recall(["a"], []) == 0.0


def test_context_recall_partial():
    assert pytest.approx(context_recall(["a", "b"], ["b", "c"])) == 0.5


def test_relevancy_score_empty():
    assert relevancy_score([]) == 0.0


def test_relevancy_score_mean():
    assert relevancy_score([1, 0.5, 0]) == pytest.approx(0.5)


def test_faithfulness_no_support_but_similar():
    # similar answers but no support
    f = faithfulness_score("yes", [], "yes")
    assert 0.6 <= f <= 0.8


def test_faithfulness_support_present():
    f = faithfulness_score("no", ["ctx1"], "yes")
    assert f >= 0.3
