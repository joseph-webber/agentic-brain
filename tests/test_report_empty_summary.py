# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.report import EvaluationReport


def test_empty_report_summary_returns_empty_dict():
    r = EvaluationReport()
    assert r.summary() == {}
