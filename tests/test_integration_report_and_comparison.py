from agentic_brain.evaluation.comparison import compare_reports
from agentic_brain.evaluation.datasets import Dataset
from agentic_brain.evaluation.evaluator import RAGEvaluator
from agentic_brain.evaluation.report import EvaluationReport


def test_full_integration():
    ds = Dataset.from_list(
        [
            {
                "id": "1",
                "question": "q1",
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
    r1 = ev.evaluate(
        ds,
        retrievals=[["c1"], ["cX"]],
        retrieved_scores=[[1.0], [0.1]],
        generated_answers=["a", "x"],
    ).to_dict()
    r2 = ev.evaluate(
        ds,
        retrievals=[["c1"], ["c2"]],
        retrieved_scores=[[1.0], [0.9]],
        generated_answers=["a", "b"],
    ).to_dict()
    comp = compare_reports(r1, r2)
    assert isinstance(comp, dict)
