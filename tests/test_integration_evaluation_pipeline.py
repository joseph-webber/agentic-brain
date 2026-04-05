# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.datasets import Dataset
from agentic_brain.evaluation.evaluator import RAGEvaluator


def test_integration_simple_pipeline():
    ds = Dataset.from_list(
        [
            {
                "id": "1",
                "question": "q1",
                "gold_answer": "ans1",
                "gold_context_ids": ["c1", "c2"],
            },
            {
                "id": "2",
                "question": "q2",
                "gold_answer": "ans2",
                "gold_context_ids": ["c3"],
            },
        ]
    )
    ev = RAGEvaluator()
    retrievals = [["c1", "cX"], ["c3"]]
    scores = [[0.8, 0.2], [0.9]]
    answers = ["ans1", "wrong"]
    report = ev.evaluate(ds, retrievals, scores, answers)
    d = report.to_dict()
    assert len(d["per_item"]) == 2
