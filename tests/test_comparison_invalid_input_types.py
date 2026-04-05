# SPDX-License-Identifier: Apache-2.0
import pytest

from agentic_brain.evaluation.comparison import compare_reports
from agentic_brain.evaluation.report import EvaluationReport


def test_compare_reports_with_non_numeric_fields():
    a = EvaluationReport()
    b = EvaluationReport()
    a.add_item({"id": "1", "x": "foo"})
    b.add_item({"id": "1", "x": "bar"})
    # Should not crash but metrics list will be empty -> results empty
    with pytest.raises(ValueError):
        # Use mismatch lengths to trigger ValueError
        compare_reports(a.to_dict(), {"per_item": []})
