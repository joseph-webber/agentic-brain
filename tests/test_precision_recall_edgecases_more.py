from agentic_brain.evaluation.metrics import context_precision, context_recall


def test_precision_with_none_inputs():
    assert context_precision(None, ["a"]) == 0.0
    assert context_recall(None, []) == 0.0
