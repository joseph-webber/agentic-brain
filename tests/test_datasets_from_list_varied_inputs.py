from agentic_brain.evaluation.datasets import Dataset


def test_from_list_with_missing_fields():
    items = [{"id":1},{"id":2,"question":"q2","gold_answer":"g2","gold_context_ids":["c2"]}]
    ds = Dataset.from_list(items)
    assert len(ds) == 2
