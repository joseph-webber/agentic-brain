# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Content Classifier – determine optimal speech speed by content type.

Joseph is blind.  Errors and warnings need a slower pace so he can
absorb the detail.  Familiar confirmations and status updates can
be read much faster – blind power users routinely listen at 350-900 WPM.

Classification Tiers
====================
- **error**     : stack traces, exceptions, failures  → SLOW
- **warning**   : deprecation, caution, watch-out     → SLOW
- **new_info**  : first-time content, explanations     → SLOW
- **complex**   : code, technical detail, numbers      → SLOW
- **question**  : prompts requiring a decision         → NORMAL
- **update**    : progress, what's happening now       → NORMAL
- **familiar**  : repeated phrases, confirmations      → FAST
- **list**      : enumerated items, bullet points      → FAST
- **status**    : health checks, "all ok" messages     → RAPID
- **progress**  : "3 of 10 done", percentage updates   → RAPID

Heuristics are intentionally simple (keyword + pattern matching).
For ambiguous text an optional LLM classifier can be used.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Content types ─────────────────────────────────────────────────────

class ContentType(Enum):
    """Broad classification of spoken content."""

    ERROR = "error"
    WARNING = "warning"
    NEW_INFO = "new_info"
    COMPLEX = "complex"
    QUESTION = "question"
    UPDATE = "update"
    FAMILIAR = "familiar"
    LIST = "list"
    STATUS = "status"
    PROGRESS = "progress"


# Map content types to the speed tier names used by speed_profiles
CONTENT_TYPE_TO_TIER: Dict[ContentType, str] = {
    ContentType.ERROR: "slow",
    ContentType.WARNING: "slow",
    ContentType.NEW_INFO: "slow",
    ContentType.COMPLEX: "slow",
    ContentType.QUESTION: "normal",
    ContentType.UPDATE: "normal",
    ContentType.FAMILIAR: "fast",
    ContentType.LIST: "fast",
    ContentType.STATUS: "rapid",
    ContentType.PROGRESS: "rapid",
}


# ── Keyword patterns ─────────────────────────────────────────────────

_ERROR_KEYWORDS: Set[str] = frozenset({
    "error", "exception", "traceback", "failed", "failure",
    "critical", "fatal", "crash", "panic", "broken",
    "cannot", "unable", "refused", "denied", "timeout",
    "stacktrace", "stack trace", "nullpointer", "segfault",
})

_WARNING_KEYWORDS: Set[str] = frozenset({
    "warning", "caution", "deprecated", "watch out",
    "be careful", "attention", "notice", "alert",
    "potential", "might fail", "could break",
})

_STATUS_KEYWORDS: Set[str] = frozenset({
    "all good", "all ok", "healthy", "running",
    "online", "connected", "up and running", "no issues",
    "everything is fine", "all systems go", "status ok",
    "all tests passed", "build succeeded", "deploy complete",
})

_PROGRESS_PATTERNS: List[re.Pattern] = [
    re.compile(r"\d+\s*(of|out of|/)\s*\d+", re.IGNORECASE),
    re.compile(r"\d+%"),
    re.compile(r"step\s+\d+", re.IGNORECASE),
    re.compile(r"processing\s+\d+", re.IGNORECASE),
    re.compile(r"(done|complete|finished)\s*[:\-]?\s*\d+", re.IGNORECASE),
]

_LIST_PATTERNS: List[re.Pattern] = [
    re.compile(r"^\s*[-•*]\s", re.MULTILINE),
    re.compile(r"^\s*\d+[.)]\s", re.MULTILINE),
    re.compile(r"(first|second|third|next|then|finally)\b", re.IGNORECASE),
]

_QUESTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"\?\s*$", re.MULTILINE),
    re.compile(r"^(should|would|do you|shall|want me to|ready to)\b", re.IGNORECASE),
    re.compile(r"(yes or no|confirm|approve|proceed)\b", re.IGNORECASE),
]

_COMPLEX_PATTERNS: List[re.Pattern] = [
    re.compile(r"```"),                          # code fences
    re.compile(r"def |class |function |import "),  # code
    re.compile(r"[A-Z][a-zA-Z]+\.[a-zA-Z]+\("),  # method calls
    re.compile(r"\b0x[0-9a-fA-F]+\b"),            # hex literals
    re.compile(r"\b\d{5,}\b"),                     # large numbers
]


# ── Classification context ────────────────────────────────────────────

@dataclass
class ClassificationContext:
    """Optional metadata that influences classification.

    Callers can supply extra hints – e.g. "this was an API response",
    "user has seen this text before", etc.
    """

    source: str = ""          # e.g. "jira", "bitbucket", "neo4j"
    is_repeated: bool = False
    is_first_time: bool = False
    urgency: str = "normal"   # "low" | "normal" | "high" | "critical"


@dataclass
class ClassificationResult:
    """Outcome of content classification."""

    content_type: ContentType
    tier: str                     # "slow" | "normal" | "fast" | "rapid"
    confidence: float = 1.0       # 0.0 → 1.0
    matched_signals: List[str] = field(default_factory=list)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.7


# ── LRU Cache ─────────────────────────────────────────────────────────

class _LRUCache:
    """Bounded LRU cache for classification results."""

    def __init__(self, maxsize: int = 256) -> None:
        self._cache: OrderedDict[str, ClassificationResult] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> Optional[ClassificationResult]:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, value: ClassificationResult) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
        self._cache[key] = value

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


# ── Content Classifier ────────────────────────────────────────────────

class ContentClassifier:
    """Classify spoken content to determine optimal speech speed.

    Uses simple keyword / pattern heuristics.  Results are cached by
    a normalised hash of the input text so repeated phrases get an
    instant answer.
    """

    def __init__(self, cache_size: int = 256) -> None:
        self._cache = _LRUCache(maxsize=cache_size)
        self._familiar_hashes: Set[str] = set()

    # ── Public API ────────────────────────────────────────────────

    def classify(
        self,
        text: str,
        context: Optional[ClassificationContext] = None,
    ) -> ClassificationResult:
        """Classify *text* and return the recommended speed tier.

        Results are cached.  When *context.is_repeated* is ``True``
        the text is promoted to the *familiar* type regardless of
        keywords.
        """
        ctx = context or ClassificationContext()
        cache_key = self._hash(text)

        # Check cache first
        cached = self._cache.get(cache_key)
        if cached is not None:
            # Repeated content seen from cache → promote to familiar
            if cache_key in self._familiar_hashes:
                return ClassificationResult(
                    content_type=ContentType.FAMILIAR,
                    tier="fast",
                    confidence=0.9,
                    matched_signals=["seen_before"],
                )
            # Mark as seen so *next* time it becomes familiar
            self._familiar_hashes.add(cache_key)
            return cached

        result = self._classify_heuristic(text, ctx)
        self._cache.put(cache_key, result)
        return result

    def mark_familiar(self, text: str) -> None:
        """Manually mark *text* as familiar content."""
        self._familiar_hashes.add(self._hash(text))

    def clear_cache(self) -> None:
        self._cache.clear()
        self._familiar_hashes.clear()

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    # ── Heuristic engine ──────────────────────────────────────────

    def _classify_heuristic(
        self,
        text: str,
        ctx: ClassificationContext,
    ) -> ClassificationResult:
        """Run keyword + pattern matching to determine content type."""

        lower = text.lower()
        signals: List[str] = []

        # Context overrides
        if ctx.is_repeated:
            return ClassificationResult(
                ContentType.FAMILIAR, "fast", 1.0, ["context_repeated"],
            )
        if ctx.urgency == "critical":
            return ClassificationResult(
                ContentType.ERROR, "slow", 1.0, ["context_critical"],
            )
        if ctx.is_first_time:
            signals.append("context_first_time")

        # Score each category
        scores: Dict[ContentType, float] = {ct: 0.0 for ct in ContentType}

        # Error keywords
        for kw in _ERROR_KEYWORDS:
            if kw in lower:
                scores[ContentType.ERROR] += 1.0
                signals.append(f"error_kw:{kw}")

        # Warning keywords
        for kw in _WARNING_KEYWORDS:
            if kw in lower:
                scores[ContentType.WARNING] += 1.0
                signals.append(f"warn_kw:{kw}")

        # Status keywords
        for kw in _STATUS_KEYWORDS:
            if kw in lower:
                scores[ContentType.STATUS] += 1.0
                signals.append(f"status_kw:{kw}")

        # Progress patterns
        for pat in _PROGRESS_PATTERNS:
            if pat.search(text):
                scores[ContentType.PROGRESS] += 1.5
                signals.append(f"progress_pat:{pat.pattern[:30]}")

        # List patterns
        list_matches = 0
        for pat in _LIST_PATTERNS:
            found = pat.findall(text)
            if found:
                list_matches += len(found)
                signals.append(f"list_pat:{pat.pattern[:30]}")
        if list_matches >= 2:
            scores[ContentType.LIST] += float(list_matches)

        # Question patterns
        for pat in _QUESTION_PATTERNS:
            if pat.search(text):
                scores[ContentType.QUESTION] += 1.5
                signals.append(f"question_pat:{pat.pattern[:30]}")

        # Complex patterns
        for pat in _COMPLEX_PATTERNS:
            if pat.search(text):
                scores[ContentType.COMPLEX] += 1.0
                signals.append(f"complex_pat:{pat.pattern[:30]}")

        # First-time bonus for new_info
        if ctx.is_first_time:
            scores[ContentType.NEW_INFO] += 2.0

        # Pick the winner
        best_type = max(scores, key=lambda ct: scores[ct])
        best_score = scores[best_type]

        if best_score == 0.0:
            # No signals → default to normal update
            return ClassificationResult(
                ContentType.UPDATE, "normal", 0.5, signals or ["no_signal_default"],
            )

        total = sum(scores.values())
        confidence = min(best_score / max(total, 1.0), 1.0)
        tier = CONTENT_TYPE_TO_TIER[best_type]

        return ClassificationResult(
            content_type=best_type,
            tier=tier,
            confidence=round(confidence, 2),
            matched_signals=signals,
        )

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _hash(text: str) -> str:
        """Deterministic hash of normalised text."""
        normalised = " ".join(text.lower().split())
        return hashlib.sha256(normalised.encode()).hexdigest()[:16]


# ── Module-level singleton ────────────────────────────────────────────

_classifier: Optional[ContentClassifier] = None


def get_content_classifier() -> ContentClassifier:
    """Return (or create) the process-wide content classifier."""
    global _classifier
    if _classifier is None:
        _classifier = ContentClassifier()
    return _classifier
