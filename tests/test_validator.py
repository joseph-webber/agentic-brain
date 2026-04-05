# SPDX-License-Identifier: Apache-2.0
from agentic_brain.guardrails.validator import InputValidator


def test_length_too_short():
    v = InputValidator(min_length=5)
    res = v.validate("hey")
    assert not res["ok"]


def test_length_ok():
    v = InputValidator(min_length=1, max_length=100)
    res = v.validate("hello world")
    assert res["ok"]


def test_detects_pii():
    v = InputValidator()
    res = v.validate("contact alice@example.com")
    assert not res["ok"] and "pii" in res["reason"]


def test_detects_toxicity():
    v = InputValidator()
    res = v.validate("you are an idiot")
    assert not res["ok"] and "toxicity" in res["reason"]


def test_none_text():
    v = InputValidator()
    res = v.validate(None)
    assert not res["ok"]


def test_max_length():
    v = InputValidator(max_length=10)
    res = v.validate("x" * 20)
    assert not res["ok"]


def test_min_length_zero():
    v = InputValidator(min_length=0)
    res = v.validate("")
    assert not res["ok"]


def test_boundary_length():
    v = InputValidator(min_length=3, max_length=3)
    res = v.validate("abc")
    assert res["ok"]
