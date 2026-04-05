# SPDX-License-Identifier: Apache-2.0
from agentic_brain.guardrails.policy import PolicyEnforcer


def test_enforce_input_blocks_pii():
    p = PolicyEnforcer()
    res = p.enforce_input("email me at a@b.com")
    assert not res["allowed"]


def test_enforce_input_blocks_toxicity():
    p = PolicyEnforcer()
    res = p.enforce_input("you are a bastard")
    assert not res["allowed"]


def test_enforce_output_masks():
    p = PolicyEnforcer()
    out = p.enforce_output("reach me at joe@mail.com and you are dumb")
    assert (
        "masked_text" in out
        and "@mail.com" in out["masked_text"]
        and "dumb" not in out["masked_text"]
    )


def test_enforce_output_reports_reasons():
    p = PolicyEnforcer()
    out = p.enforce_output("I think there were 1234 cases and you are an idiot")
    assert any(
        r["type"].startswith("toxicity") or r["type"].startswith("hallucination")
        for r in out["reasons"]
    )
