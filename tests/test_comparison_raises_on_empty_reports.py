import pytest

from agentic_brain.evaluation.comparison import compare_reports
from agentic_brain.evaluation.report import EvaluationReport


def test_compare_raises_on_empty_per_item():
    a = EvaluationReport().to_dict()
    b = EvaluationReport().to_dict()
    with pytest.raises(ValueError):
        compare_reports(a, b)
