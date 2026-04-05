# SPDX-License-Identifier: Apache-2.0
"""Heuristic hallucination detection.

This module implements simple heuristics to flag potential hallucinations
such as ungrounded superlative claims, definitive statements without
citations, and overconfident phrasing.
"""

import re
from typing import List


class HallucinationDetector:
    HEDGING_PHRASES = [
        r"I think",
        r"I believe",
        r"as far as I know",
        r"I remember",
        r"probably",
        r"might",
        r"could",
        r"certainly",
        r"definitely",
    ]

    NUMERIC_CLAIM_RE = re.compile(r"\b\d{3,}\b")

    def detect_hallucination(self, text: str) -> List[str]:
        """Return list of reasons why text may be hallucinated."""
        if not text:
            return []
        reasons = []
        for p in self.HEDGING_PHRASES:
            if re.search(p, text, re.IGNORECASE):
                reasons.append(f"hedging:{p}")
        # numeric claims without citation - crude heuristic
        if self.NUMERIC_CLAIM_RE.search(text):
            reasons.append("numeric_unverified")
        # look for absolutes ("always", "never") with no citation marker
        if re.search(r"\b(always|never|all|none)\b", text, re.IGNORECASE):
            reasons.append("absolute_claim")
        return reasons
