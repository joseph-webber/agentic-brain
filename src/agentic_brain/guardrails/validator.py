"""Input validation utilities for agentic-brain guardrails.
"""

from .pii_detector import PiiDetector
from .toxicity import ToxicityDetector


class InputValidator:
    """Validates user inputs against multiple guardrails.

    Usage:
        v = InputValidator()
        result = v.validate(text)
    """

    def __init__(self, max_length: int = 2000, min_length: int = 1):
        self.max_length = max_length
        self.min_length = min_length
        self.pii = PiiDetector()
        self.tox = ToxicityDetector()

    def validate_length(self, text: str):
        if text is None:
            return False, "text is None"
        if text == "":
            return False, "text is empty"
        n = len(text)
        if n < self.min_length:
            return False, f"text too short ({n} < {self.min_length})"
        if n > self.max_length:
            return False, f"text too long ({n} > {self.max_length})"
        return True, ""

    def validate_no_pii(self, text: str):
        matches = self.pii.detect_pii(text)
        if matches:
            return False, f"pii_detected: {matches}"
        return True, ""

    def validate_no_toxicity(self, text: str):
        matches = self.tox.detect_toxicity(text)
        if matches:
            return False, f"toxicity_detected: {matches}"
        return True, ""

    def validate(self, text: str):
        """Run all validations. Returns dict with status and reasons."""
        ok, reason = self.validate_length(text)
        if not ok:
            return {"ok": False, "reason": reason}
        ok, reason = self.validate_no_pii(text)
        if not ok:
            return {"ok": False, "reason": reason}
        ok, reason = self.validate_no_toxicity(text)
        if not ok:
            return {"ok": False, "reason": reason}
        return {"ok": True, "reason": "passed"}
