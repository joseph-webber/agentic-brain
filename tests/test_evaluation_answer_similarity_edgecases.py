from agentic_brain.evaluation.metrics import answer_similarity


def test_answer_similarity_none_inputs():
    assert answer_similarity(None, "a") == 0.0
    assert answer_similarity(None, None) == 0.0


def test_answer_similarity_empty_both():
    assert answer_similarity("", "") == 1.0


def test_answer_similarity_partial_overlap():
    v = answer_similarity("The cat sat on the mat", "cat on mat")
    assert 0.2 < v < 1.0
