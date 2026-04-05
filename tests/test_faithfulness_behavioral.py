# SPDX-License-Identifier: Apache-2.0
from agentic_brain.evaluation.metrics import faithfulness_score


def test_faithfulness_prefers_similarity():
    f_sim = faithfulness_score("yes", "ctx", "yes")
    f_diff = faithfulness_score("no", "ctx", "yes")
    assert f_sim > f_diff
