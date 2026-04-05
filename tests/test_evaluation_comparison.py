import pytest
from agentic_brain.evaluation.report import EvaluationReport
from agentic_brain.evaluation.comparison import compare_reports


def make_report(vals):
    r = EvaluationReport()
    for i, v in enumerate(vals):
        r.add_item({"id":str(i), "faithfulness": v, "relevancy": v})
    return r


def test_compare_reports_basic():
    a = make_report([0.1,0.2,0.3]).to_dict()
    b = make_report([0.2,0.1,0.25]).to_dict()
    res = compare_reports(a,b)
    assert "faithfulness" in res and "relevancy" in res
    assert "p_value" in res["faithfulness"]


def test_compare_reports_length_mismatch():
    a = make_report([0.1,0.2]).to_dict()
    b = make_report([0.1]).to_dict()
    with pytest.raises(ValueError):
        compare_reports(a,b)
