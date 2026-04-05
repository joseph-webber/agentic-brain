from agentic_brain.evaluation.datasets import Example


def test_example_fields_set():
    ex = Example(id="x", question="q", gold_answer="a", gold_context_ids=["c"])
    assert ex.id == "x" and ex.contexts is None
