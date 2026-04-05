# SPDX-License-Identifier: Apache-2.0
"""Basic toxicity detection and filtering."""

import re
from typing import List


class ToxicityDetector:
    """Detects simple toxic language using keyword lists.

    This is intentionally simple for unit testing. Real deployments should
    use ML-based detectors or external safety APIs.
    """

    DEFAULT_TOXIC_WORDS = [
        "idiot",
        "stupid",
        "dumb",
        "hate",
        "kill",
        "bastard",
        "damn",
        "asshole",
    ]

    def __init__(self, toxic_words: List[str] = None):
        self.words = toxic_words or self.DEFAULT_TOXIC_WORDS
        # build regex to match whole words, case-insensitive
        words_escaped = [re.escape(w) for w in self.words]
        # match whole words, case-insensitive; build pattern robustly
        pattern = r"\b(?:" + "|".join(words_escaped) + r")\b"
        self.re = re.compile(pattern, re.IGNORECASE)

    def detect_toxicity(self, text: str) -> List[str]:
        if not text:
            return []
        return list({m.group(0).lower() for m in self.re.finditer(text)})

    def is_toxic(self, text: str) -> bool:
        return bool(self.re.search(text or ""))

    def sanitize(self, text: str, mask_char: str = "*") -> str:
        def repl(m):
            return mask_char * len(m.group(0))

        return self.re.sub(repl, text or "")
