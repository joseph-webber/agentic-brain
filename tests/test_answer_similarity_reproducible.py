from agentic_brain.evaluation.metrics import answer_similarity


def test_answer_similarity_reproducible():
    assert answer_similarity("A B C", "A B C") == answer_similarity("a b c", "A B C")
