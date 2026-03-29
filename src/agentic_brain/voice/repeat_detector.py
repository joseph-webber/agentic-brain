# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Repeat detection for voice output.

Prevents the brain from saying the same thing twice in a row.
Uses fuzzy matching (stdlib ``difflib.SequenceMatcher``) to catch
near-duplicates like:
  - "Starting work on JIRA now"  vs  "Starting work on JIRA now."
  - "PR approved"  vs  "PR Approved!"

Configurable via environment:
  AGENTIC_BRAIN_VOICE_NO_REPEATS=true     Block repeats entirely
  AGENTIC_BRAIN_VOICE_REPEAT_THRESHOLD=0.8 Similarity threshold (0-1)
  AGENTIC_BRAIN_VOICE_REPEAT_WINDOW=20     Window size (last N utterances)
"""

from __future__ import annotations

import difflib
import logging
import os
import threading
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = float(
    os.getenv("AGENTIC_BRAIN_VOICE_REPEAT_THRESHOLD", "0.8")
)
_DEFAULT_WINDOW = int(
    os.getenv("AGENTIC_BRAIN_VOICE_REPEAT_WINDOW", "20")
)


class RepeatAction(Enum):
    """What to do when a repeat is detected."""

    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class RepeatResult:
    """Result of a repeat check."""

    is_repeat: bool
    similarity: float
    matched_text: str
    action: RepeatAction

    @property
    def should_block(self) -> bool:
        return self.action == RepeatAction.BLOCK and self.is_repeat


class RepeatDetector:
    """Detects near-duplicate utterances within a sliding window.

    Thread-safe.  Call :meth:`check` before every utterance.

    Usage::

        detector = get_repeat_detector()
        result = detector.check("Good morning Joseph")
        if result.should_block:
            logger.info("Blocked repeat: %s", result.matched_text)
        else:
            speak(text)
            detector.record(text)
    """

    def __init__(
        self,
        *,
        threshold: float = _DEFAULT_THRESHOLD,
        window: int = _DEFAULT_WINDOW,
        action: RepeatAction | None = None,
    ) -> None:
        self._threshold = max(0.0, min(1.0, threshold))
        self._window = max(1, window)
        self._lock = threading.Lock()
        self._history: List[str] = []

        if action is not None:
            self._action = action
        elif os.getenv("AGENTIC_BRAIN_VOICE_NO_REPEATS", "").lower() in (
            "1",
            "true",
            "yes",
        ):
            self._action = RepeatAction.BLOCK
        else:
            self._action = RepeatAction.WARN

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def window(self) -> int:
        return self._window

    @property
    def action(self) -> RepeatAction:
        return self._action

    def check(
        self, text: str, *, threshold: float | None = None
    ) -> RepeatResult:
        """Check whether *text* is a repeat of a recent utterance.

        Returns a :class:`RepeatResult` with similarity and matched text.
        """
        thresh = threshold if threshold is not None else self._threshold
        normalised = self._normalise(text)

        if not normalised:
            return RepeatResult(
                is_repeat=False,
                similarity=0.0,
                matched_text="",
                action=self._action,
            )

        best_ratio = 0.0
        best_match = ""

        with self._lock:
            for prev in reversed(self._history):
                ratio = difflib.SequenceMatcher(
                    None, normalised, self._normalise(prev)
                ).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = prev
                # Exact match – no need to keep looking
                if ratio >= 1.0:
                    break

        is_repeat = best_ratio >= thresh
        return RepeatResult(
            is_repeat=is_repeat,
            similarity=best_ratio,
            matched_text=best_match if is_repeat else "",
            action=self._action,
        )

    def is_repeat(self, text: str, threshold: float | None = None) -> bool:
        """Convenience: ``True`` if *text* is a repeat."""
        return self.check(text, threshold=threshold).is_repeat

    def record(self, text: str) -> None:
        """Add *text* to the sliding history window.

        Call **after** the utterance has actually been spoken.
        """
        with self._lock:
            self._history.append(text)
            if len(self._history) > self._window:
                self._history = self._history[-self._window :]

    def clear(self) -> None:
        """Reset the history window."""
        with self._lock:
            self._history.clear()

    def recent(self, count: int = 10) -> List[str]:
        """Return the last *count* recorded texts (oldest → newest)."""
        with self._lock:
            return list(self._history[-count:])

    @staticmethod
    def _normalise(text: str) -> str:
        """Lower-case and strip punctuation for comparison."""
        return "".join(
            ch for ch in text.lower().strip() if ch.isalnum() or ch.isspace()
        )

    def set_threshold(self, value: float) -> None:
        self._threshold = max(0.0, min(1.0, value))

    def set_window(self, value: int) -> None:
        self._window = max(1, value)
        with self._lock:
            if len(self._history) > self._window:
                self._history = self._history[-self._window :]

    def set_action(self, action: RepeatAction) -> None:
        self._action = action


# ── Singleton ────────────────────────────────────────────────────────

_instance: RepeatDetector | None = None
_instance_lock = threading.Lock()


def get_repeat_detector(**kwargs) -> RepeatDetector:
    """Return (or create) the global RepeatDetector singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RepeatDetector(**kwargs)
    return _instance


def reset_repeat_detector() -> None:
    """Tear down the singleton (useful in tests)."""
    global _instance
    with _instance_lock:
        _instance = None
