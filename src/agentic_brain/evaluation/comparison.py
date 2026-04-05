"""Comparison utilities for A/B testing of RAG outputs."""

import math
from statistics import mean
from typing import Any, Dict

try:
    from scipy import stats  # type: ignore

    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False


def _paired_ttest(a, b):
    # compute paired t-test manually
    if len(a) != len(b):
        raise ValueError("Lists must have same length")
    n = len(a)
    if n < 2:
        return float("nan"), float("nan")
    diffs = [x - y for x, y in zip(a, b, strict=False)]
    mean_diff = mean(diffs)
    sd = math.sqrt(sum((d - mean_diff) ** 2 for d in diffs) / (n - 1))
    if sd == 0:
        return float("inf"), 1.0
    t = mean_diff / (sd / math.sqrt(n))
    # two-sided p-value via survival function using math (approx via Student's t CDF not available) -> fallback
    # Conservative fallback: use large-sample normal approx
    from math import erf, sqrt

    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
    return t, p


def compare_reports(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two reports (as produced by EvaluationReport.to_dict()) and run paired t-tests

    Returns a dict with metric-wise means and p-values.
    """
    per_a = a.get("per_item", [])
    per_b = b.get("per_item", [])
    if not per_a or not per_b or len(per_a) != len(per_b):
        raise ValueError(
            "Reports must have equal non-empty per_item lists for comparison"
        )
    # find numeric metric keys
    metrics = set()
    for k, v in per_a[0].items():
        if isinstance(v, (int, float)):
            metrics.add(k)
    results = {}
    for m in metrics:
        vals_a = [it.get(m, 0.0) for it in per_a]
        vals_b = [it.get(m, 0.0) for it in per_b]
        mean_a = mean(vals_a)
        mean_b = mean(vals_b)
        if _HAVE_SCIPY:
            t, p = stats.ttest_rel(vals_a, vals_b)
            # if SciPy returns nan (e.g. zero variance), fallback to manual implementation
            try:
                import math

                if p is None or math.isnan(p):
                    t, p = _paired_ttest(vals_a, vals_b)
            except Exception:
                t, p = _paired_ttest(vals_a, vals_b)
        else:
            t, p = _paired_ttest(vals_a, vals_b)
        results[m] = {"mean_a": mean_a, "mean_b": mean_b, "p_value": p}
    return results
