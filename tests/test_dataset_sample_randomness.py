# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.datasets import Dataset


def test_dataset_sample_randomness():
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
            {
                "id": "3",
                "question": "q3",
                "gold_answer": "c",
                "gold_context_ids": ["c3"],
            },
        ]
    )
    s = ds.sample(2)
    assert len(s) == 2
