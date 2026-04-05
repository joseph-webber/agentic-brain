"""Output filtering utilities for agentic-brain."""
from .toxicity import ToxicityDetector
from .pii_detector import PiiDetector


class OutputFilter:
    """Apply filters to model outputs to ensure they meet safety constraints."""

    def __init__(self):
        self.tox = ToxicityDetector()
        self.pii = PiiDetector()

    def filter_profanity(self, text: str) -> str:
        return self.tox.sanitize(text)

    def mask_pii(self, text: str) -> str:
        return self.pii.mask_pii(text)

    def apply_all(self, text: str) -> str:
        if text is None:
            return text
        t = self.filter_profanity(text)
        t = self.mask_pii(t)
        return t
