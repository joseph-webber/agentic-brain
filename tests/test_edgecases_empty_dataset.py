# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.datasets import Dataset
from agentic_brain.evaluation.evaluator import RAGEvaluator


def test_empty_dataset_evaluation():
    ds = Dataset()
    ev = RAGEvaluator()
    rep = ev.evaluate(ds)
    assert rep.per_item == []
    assert rep.summary() == {}
