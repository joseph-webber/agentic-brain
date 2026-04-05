from agentic_brain.evaluation.report import EvaluationReport


def test_to_dict_contains_summary_and_items():
    r = EvaluationReport()
    r.add_item({"id":"1","a":1})
    d = r.to_dict()
    assert "per_item" in d and "summary" in d
