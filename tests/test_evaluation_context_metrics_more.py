import pytest
from agentic_brain.evaluation.metrics import context_precision, context_recall


def test_precision_with_duplicates():
    # duplicates should be treated as distinct retrievals; precision counts correct retrieved / total retrieved
    assert context_precision(["a","a","b"],["a"]) == pytest.approx(2/3)


def test_recall_with_no_overlap():
    assert context_recall(["x"],["a","b"]) == 0.0


def test_precision_and_recall_both_empty():
    assert context_precision([],[]) == 0.0
    assert context_recall([],[]) == 0.0
