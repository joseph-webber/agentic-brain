# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.metrics import answer_similarity


def test_answer_similarity_large_texts():
    a = "Lorem ipsum " * 100
    b = "lorem ipsum" * 100
    v = answer_similarity(a, b)
    assert v > 0.7
