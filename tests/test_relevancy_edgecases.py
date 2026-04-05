from agentic_brain.evaluation.metrics import relevancy_score


def test_relevancy_scores_with_non_numeric_castable():
    assert relevancy_score(["1", "0.5"]) == pytest.approx(0.75)
