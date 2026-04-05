from agentic_brain.evaluation.evaluator import RAGEvaluator
from agentic_brain.evaluation.datasets import Dataset, Example


def make_dataset():
    items = [
        {
            "id": "1",
            "question": "q1",
            "gold_answer": "yes",
            "gold_context_ids": ["c1", "c2"],
        },
        {"id": "2", "question": "q2", "gold_answer": "no", "gold_context_ids": ["c3"]},
        {"id": "3", "question": "q3", "gold_answer": "maybe", "gold_context_ids": []},
    ]
    return Dataset.from_list(items)


def test_evaluator_basic_metrics():
    ds = make_dataset()
    evaluator = RAGEvaluator()
    retrievals = [["c1"], ["c4"], ["cX"]]
    scores = [[0.9], [0.1], [0.2]]
    answers = ["yes", "no", "maybe"]
    report = evaluator.evaluate(ds, retrievals, scores, answers)
    summ = report.summary()
    # ensure keys present
    assert "answer_similarity" in summ
    assert "context_precision" in summ
    assert "context_recall" in summ
    assert "relevancy" in summ
    assert "faithfulness" in summ


def test_evaluator_lengths_match():
    ds = make_dataset()
    evaluator = RAGEvaluator()
    # shorter retrievals/answers should be handled gracefully
    report = evaluator.evaluate(
        ds, retrievals=[["c1"]], retrieved_scores=[[0.9]], generated_answers=["yes"]
    )
    assert len(report.per_item) == len(ds)
