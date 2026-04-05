# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.datasets import Dataset
from agentic_brain.evaluation.evaluator import RAGEvaluator


def test_evaluator_handles_missing_entries():
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
    report = ev.evaluate(
        ds, retrievals=[["c1"]], retrieved_scores=None, generated_answers=None
    )
    assert len(report.per_item) == 2
