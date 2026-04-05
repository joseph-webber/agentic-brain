from agentic_brain.evaluation.evaluator import RAGEvaluator
from agentic_brain.evaluation.datasets import Dataset


def test_empty_dataset_evaluation():
    ds = Dataset()
    ev = RAGEvaluator()
    rep = ev.evaluate(ds)
    assert rep.per_item == []
    assert rep.summary() == {}
