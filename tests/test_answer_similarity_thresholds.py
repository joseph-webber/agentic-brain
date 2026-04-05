from agentic_brain.evaluation.metrics import answer_similarity


def test_answer_similarity_thresholds():
    assert answer_similarity("yes","yes") > 0.9
    assert answer_similarity("yes","no") < 0.5
