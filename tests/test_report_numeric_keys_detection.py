from agentic_brain.evaluation.report import EvaluationReport


def test_report_detects_numeric_keys():
    r = EvaluationReport()
    r.add_item({"id": "1", "a": 1.0, "b": 2})
    r.add_item({"id": "2", "a": 3.0, "b": 4})
    s = r.summary()
    assert s["a"] == 2.0
    assert s["b"] == 3.0
