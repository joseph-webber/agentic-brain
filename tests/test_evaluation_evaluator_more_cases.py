from agentic_brain.evaluation.evaluator import RAGEvaluator
from agentic_brain.evaluation.datasets import Dataset


def test_evaluator_with_no_retrievals_and_no_answers():
    ds = Dataset.from_list(
        [{"id": "1", "question": "q", "gold_answer": "a", "gold_context_ids": ["c1"]}]
    )
    ev = RAGEvaluator()
    rep = ev.evaluate(ds)
    s = rep.summary()
    assert s["answer_similarity"] == 0.0
    assert s["relevancy"] == 0.0


def test_evaluator_with_partial_scores():
    ds = Dataset.from_list(
        [
            {
                "id": "1",
                "question": "q",
                "gold_answer": "a",
                "gold_context_ids": ["c1"],
            },
            {
                "id": "2",
                "question": "q2",
                "gold_answer": "b",
                "gold_context_ids": ["c2"],
            },
        ]
    )
    ev = RAGEvaluator()
    rep = ev.evaluate(
        ds,
        retrievals=[["c1"], ["c2"]],
        retrieved_scores=[[1.0], [0.5]],
        generated_answers=["a", "x"],
    )
    s = rep.summary()
    assert 0.0 <= s["relevancy"] <= 1.0
