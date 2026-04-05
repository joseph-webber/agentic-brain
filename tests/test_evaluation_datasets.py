from agentic_brain.evaluation.datasets import Dataset, Example


def test_dataset_from_list_and_len():
    items = [
        {"id": "1", "question": "Q", "gold_answer": "A", "gold_context_ids": ["c1"]}
    ]
    ds = Dataset.from_list(items)
    assert len(ds) == 1
    ex = ds.examples[0]
    assert ex.id == "1" and ex.gold_answer == "A"


def test_dataset_add_and_iter():
    ds = Dataset()
    ex = Example(id="2", question="q", gold_answer="a", gold_context_ids=["c2"])
    ds.add(ex)
    for e in ds:
        assert e.id == "2"
