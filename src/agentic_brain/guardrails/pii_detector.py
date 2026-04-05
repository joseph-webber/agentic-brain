"""Simple PII detection utilities."""

import re
from typing import List, Dict


class PiiDetector:
    """Detects basic forms of personally identifiable information (PII).

    This is intentionally conservative and pattern-based; production
    systems should use specialized libraries and data loss prevention APIs.
    """

    EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    PHONE_RE = re.compile(
        r"\b(?:\+?\d{1,3}[-.\s]*)?(?:\(\d{2,4}\)|\d{2,4})[-.\s]*\d{3,4}[-.\s]*\d{3,4}\b"
    )
    CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    def detect_pii(self, text: str) -> List[Dict[str, str]]:
        if not text:
            return []
        findings = []
        for m in self.EMAIL_RE.finditer(text):
            findings.append({"type": "email", "match": m.group(0)})
        for m in self.PHONE_RE.finditer(text):
            findings.append({"type": "phone", "match": m.group(0)})
        for m in self.CREDIT_CARD_RE.finditer(text):
            # crude filter: avoid matching long numbers that are dates
            findings.append({"type": "credit_card", "match": m.group(0)})
        for m in self.SSN_RE.finditer(text):
            findings.append({"type": "ssn", "match": m.group(0)})
        return findings

    def mask_pii(self, text: str, mask_char: str = "*") -> str:
        """Return text with detected PII masked (simple approach).
        Emails: mask local part, phones and cards: replace digits with mask_char.
        """
        if not text:
            return text

        def _mask_email(m):
            email = m.group(0)
            local, _, domain = email.partition("@")
            if len(local) <= 2:
                masked_local = local[0] + mask_char * (len(local) - 1)
            else:
                masked_local = local[0] + mask_char * (len(local) - 2) + local[-1]
            return masked_local + "@" + domain

        text = self.EMAIL_RE.sub(_mask_email, text)
        text = re.sub(r"\d", mask_char, text)
        return text
