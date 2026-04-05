from agentic_brain.evaluation.datasets import Dataset, Example


def test_dataset_sampling_returns_list():
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
    s = ds.sample(1)
    assert isinstance(s, list)
    assert len(s) == 1
