from agentic_brain.evaluation.comparison import compare_reports
from agentic_brain.evaluation.report import EvaluationReport


def test_ttest_returns_reasonable_p():
    a = EvaluationReport()
    b = EvaluationReport()
    for i in range(30):
        a.add_item({"id": str(i), "relevancy": 0.5})
        b.add_item({"id": str(i), "relevancy": 0.6})
    res = compare_reports(a.to_dict(), b.to_dict())
    p = res["relevancy"]["p_value"]
    assert 0.0 <= p <= 1.0
