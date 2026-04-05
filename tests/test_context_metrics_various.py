# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.metrics import context_precision, context_recall


def test_context_precision_fractional():
    assert context_precision(["a", "b", "c"], ["b"]) == pytest.approx(1 / 3)


def test_context_recall_fractional():
    assert context_recall(["a", "b"], ["a", "b", "c"]) == pytest.approx(2 / 3)
