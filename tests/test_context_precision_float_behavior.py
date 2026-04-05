# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.metrics import context_precision


def test_context_precision_returns_float():
    v = context_precision(["a"], ["a"])
    assert isinstance(v, float)
