# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.metrics import answer_similarity


def test_unicode_handling():
    assert answer_similarity("café", "CAFE") > 0.5
