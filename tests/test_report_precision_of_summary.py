from agentic_brain.evaluation.report import EvaluationReport


def test_summary_precision():
    r = EvaluationReport()
    r.add_item({"id":"1","a":0.3333})
    r.add_item({"id":"2","a":0.3334})
    s = r.summary()
    assert abs(s["a"] - 0.33335) < 1e-5
