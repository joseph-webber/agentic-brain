"""Policy enforcer that composes various guardrails."""
from .pii_detector import PiiDetector
from .toxicity import ToxicityDetector
from .hallucination import HallucinationDetector
from .output_filter import OutputFilter


class PolicyEnforcer:
    """Enforce simple policies and provide structured reasons.

    Methods:
        enforce_input(text) -> dict
        enforce_output(text) -> dict
    """

    def __init__(self):
        self.pii = PiiDetector()
        self.tox = ToxicityDetector()
        self.hall = HallucinationDetector()
        self.filter = OutputFilter()

    def enforce_input(self, text: str) -> dict:
        reasons = []
        pii = self.pii.detect_pii(text)
        if pii:
            reasons.append({"type": "pii", "matches": pii})
        tox = self.tox.detect_toxicity(text)
        if tox:
            reasons.append({"type": "toxicity", "matches": tox})
        hall = self.hall.detect_hallucination(text)
        if hall:
            reasons.append({"type": "hallucination", "matches": hall})
        allowed = len(reasons) == 0
        return {"allowed": allowed, "reasons": reasons}

    def enforce_output(self, text: str) -> dict:
        reasons = []
        masked = self.filter.apply_all(text)
        # if masking removed content considered toxic or pii, record
        tox_orig = self.tox.detect_toxicity(text)
        tox_masked = self.tox.detect_toxicity(masked)
        if tox_orig and not tox_masked:
            reasons.append({"type": "toxicity_masked", "matches": tox_orig})
        pii_orig = self.pii.detect_pii(text)
        pii_masked = self.pii.detect_pii(masked)
        if pii_orig and not pii_masked:
            reasons.append({"type": "pii_masked", "matches": pii_orig})
        halluc = self.hall.detect_hallucination(text)
        if halluc:
            reasons.append({"type": "hallucination", "matches": halluc})
        allowed = True  # outputs are allowed but annotated
        return {"allowed": allowed, "masked_text": masked, "reasons": reasons}
