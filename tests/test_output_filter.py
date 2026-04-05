# SPDX-License-Identifier: Apache-2.0
from agentic_brain.guardrails.output_filter import OutputFilter


def test_filter_profanity_and_pii():
    f = OutputFilter()
    text = "Contact bob@mail.com you are an asshole"
    out = f.apply_all(text)
    assert "@mail.com" in out and "asshole" not in out


def test_mask_pii_only():
    f = OutputFilter()
    out = f.mask_pii("Call 555-1234")
    assert "5" not in out


def test_filter_none_text():
    f = OutputFilter()
    assert f.apply_all(None) is None


def test_filter_no_change_for_safe_text():
    f = OutputFilter()
    s = "Hello world"
    assert f.apply_all(s) == s


def test_profanity_mask_length():
    f = OutputFilter()
    out = f.filter_profanity("you are an idiot")
    assert "idiot" not in out and len(out) >= 1


def test_mask_email_keeps_domain():
    f = OutputFilter()
    out = f.mask_pii("alice@example.com")
    assert "@example.com" in out
