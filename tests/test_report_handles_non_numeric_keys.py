from agentic_brain.evaluation.report import EvaluationReport


def test_report_ignores_non_numeric_on_summary():
    r = EvaluationReport()
    r.add_item({"id": "1", "x": "foo"})
    s = r.summary()
    assert s == {}
