from agentic_brain.evaluation.metrics import relevancy_score


def test_relevancy_with_negative_values():
    assert relevancy_score([-1, 1]) == 0.0
    # negative behaves as numbers, mean is 0.0
