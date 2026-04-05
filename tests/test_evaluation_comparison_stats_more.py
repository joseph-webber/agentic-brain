# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.comparison import compare_reports
from agentic_brain.evaluation.report import EvaluationReport


def test_compare_reports_values_close():
    a = EvaluationReport()
    b = EvaluationReport()
    for i in range(10):
        a.add_item({"id": str(i), "faithfulness": 0.5 + i * 0.01})
        b.add_item({"id": str(i), "faithfulness": 0.5 + i * 0.009})
    res = compare_reports(a.to_dict(), b.to_dict())
    assert "faithfulness" in res
    assert "p_value" in res["faithfulness"]
