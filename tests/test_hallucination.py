# SPDX-License-Identifier: Apache-2.0
from agentic_brain.guardrails.hallucination import HallucinationDetector


def test_detect_hedging():
    h = HallucinationDetector()
    assert any(
        r.startswith("hedging") for r in h.detect_hallucination("I think this is true")
    )


def test_detect_numeric_unverified():
    h = HallucinationDetector()
    assert "numeric_unverified" in h.detect_hallucination("There were 12345 incidents")


def test_detect_absolute():
    h = HallucinationDetector()
    assert "absolute_claim" in h.detect_hallucination("Everyone always lies")


def test_no_hallucination_on_safe_text():
    h = HallucinationDetector()
    assert h.detect_hallucination("Hello world") == []


def test_multiple_reasons():
    h = HallucinationDetector()
    res = h.detect_hallucination(
        "I believe there were 1234 events and everyone always knew"
    )
    assert len(res) >= 2


def test_empty_text():
    h = HallucinationDetector()
    assert h.detect_hallucination("") == []
