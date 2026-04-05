from agentic_brain.evaluation.comparison import compare_reports
from agentic_brain.evaluation.report import EvaluationReport


def test_identical_reports_yield_high_p():
    a = EvaluationReport()
    b = EvaluationReport()
    for i in range(20):
        a.add_item({"id": str(i), "faithfulness": 0.5})
        b.add_item({"id": str(i), "faithfulness": 0.5})
    res = compare_reports(a.to_dict(), b.to_dict())
    assert res["faithfulness"]["p_value"] > 0.5
