# SPDX-License-Identifier: Apache-2.0
from agentic_brain.guardrails.pii_detector import PiiDetector


def test_detect_email():
    p = PiiDetector()
    assert p.detect_pii("contact me at alice@example.com")


def test_detect_phone():
    p = PiiDetector()
    assert any(f["type"] == "phone" for f in p.detect_pii("Call +1 (555) 123-4567"))


def test_detect_ssn():
    p = PiiDetector()
    res = p.detect_pii("My ssn is 123-45-6789")
    assert any(f["type"] == "ssn" for f in res)


def test_mask_email():
    p = PiiDetector()
    masked = p.mask_pii("user@example.com")
    assert "@example.com" in masked and "user" not in masked


def test_mask_digits():
    p = PiiDetector()
    masked = p.mask_pii("Call 555-123-4567")
    assert "5" not in masked


def test_no_pii_on_empty():
    p = PiiDetector()
    assert p.detect_pii("") == []
