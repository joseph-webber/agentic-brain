# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Quality Gate — Block bad audio before it reaches Joseph.

Validates every audio file before playback. Blocks clips that are
too quiet, clipping, or otherwise unintelligible, and auto-normalizes
when the problem is fixable.

Integrates with :mod:`agentic_brain.voice.serializer` to intercept
audio before playback.

Usage:
    >>> from agentic_brain.voice.quality_gate import QualityGate
    >>> gate = QualityGate()
    >>> decision = gate.check("output.wav")
    >>> if decision.action == GateAction.PLAY:
    ...     play(decision.audio_path)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from agentic_brain.audio.audio_normalizer import AudioNormalizer
from agentic_brain.audio.quality_analyzer import (
    MIN_ACCEPTABLE_DB,
    QualityReport,
    Severity,
    VoiceQualityAnalyzer,
)

logger = logging.getLogger(__name__)


class GateAction(Enum):
    """What the gate decided to do with an audio file."""

    PLAY = "play"  # Audio is fine — play it
    NORMALIZED = "normalized"  # Auto-fixed and ready to play
    BLOCKED = "blocked"  # Audio is rejected


@dataclass
class GateDecision:
    """Result of a quality gate check."""

    action: GateAction
    audio_path: str
    report: QualityReport
    reason: str = ""
    original_path: str = ""

    @property
    def allowed(self) -> bool:
        return self.action in (GateAction.PLAY, GateAction.NORMALIZED)


class QualityGate:
    """Pre-playback quality gate for voice audio.

    Parameters:
        auto_normalize: Automatically fix volume issues when possible.
        min_db: Minimum RMS dB to allow playback (blocks below this).
        block_clipping: Block audio with significant clipping.
        clipping_threshold: Clipping ratio above which to block.
        analyzer: Custom analyzer instance (uses default if None).
        normalizer: Custom normalizer instance (uses default if None).
    """

    def __init__(
        self,
        *,
        auto_normalize: bool = True,
        min_db: float = MIN_ACCEPTABLE_DB,
        block_clipping: bool = True,
        clipping_threshold: float = 0.01,
        analyzer: VoiceQualityAnalyzer | None = None,
        normalizer: AudioNormalizer | None = None,
    ) -> None:
        self.auto_normalize = auto_normalize
        self.min_db = min_db
        self.block_clipping = block_clipping
        self.clipping_threshold = clipping_threshold
        self._analyzer = analyzer or VoiceQualityAnalyzer(min_db=min_db)
        self._normalizer = normalizer or AudioNormalizer()

    # ── Public API ────────────────────────────────────────────────

    def check(self, audio_path: str | Path) -> GateDecision:
        """Analyze audio and decide: play, normalize, or block.

        This is the main entry point — call before every playback.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            return GateDecision(
                action=GateAction.BLOCKED,
                audio_path=str(audio_path),
                report=QualityReport(file_path=str(audio_path)),
                reason="File not found.",
            )

        try:
            report = self._analyzer.analyze_audio(audio_path)
        except Exception as exc:
            logger.error("Quality analysis failed: %s", exc)
            return GateDecision(
                action=GateAction.BLOCKED,
                audio_path=str(audio_path),
                report=QualityReport(file_path=str(audio_path)),
                reason=f"Analysis error: {exc}",
            )

        # Check for hard blocks first
        block_reason = self._should_block(report)
        if block_reason:
            return GateDecision(
                action=GateAction.BLOCKED,
                audio_path=str(audio_path),
                report=report,
                reason=block_reason,
            )

        # Check if normalization is needed and allowed
        if self.auto_normalize and self._needs_normalization(report):
            return self._try_normalize(audio_path, report)

        # Audio is acceptable as-is
        return GateDecision(
            action=GateAction.PLAY,
            audio_path=str(audio_path),
            report=report,
        )

    def validate(self, audio_path: str | Path) -> bool:
        """Simple pass/fail validation. True if audio can be played."""
        decision = self.check(audio_path)
        return decision.allowed

    # ── Decision logic ────────────────────────────────────────────

    def _should_block(self, report: QualityReport) -> Optional[str]:
        """Return a block reason or None if audio can proceed."""
        # Block empty files
        if report.duration_seconds <= 0:
            return "Audio file is empty (zero duration)."

        # Block severe clipping
        if self.block_clipping and report.clipping_ratio > self.clipping_threshold:
            pct = report.clipping_ratio * 100
            return (
                f"Audio is severely clipped ({pct:.1f}% of samples). "
                "This would sound distorted."
            )

        # Block extremely quiet audio that can't be rescued
        if report.rms_db < (self.min_db - 20):
            return (
                f"Audio is essentially silent at {report.rms_db:.1f} dB RMS. "
                "Normalization would amplify noise."
            )

        return None

    def _needs_normalization(self, report: QualityReport) -> bool:
        """True if audio quality would benefit from normalization."""
        # Too quiet but rescuable
        if report.rms_db < self.min_db:
            return True
        # Moderate clipping that normalization can fix (reduce volume)
        if 0 < report.clipping_ratio <= self.clipping_threshold:
            return True
        return False

    def _try_normalize(self, audio_path: Path, report: QualityReport) -> GateDecision:
        """Attempt auto-normalization and return the decision."""
        try:
            normalized = self._normalizer.normalize_volume(audio_path)
            # Re-analyze the normalized file
            new_report = self._analyzer.analyze_audio(normalized)

            # If normalization actually helped
            if (
                new_report.rms_db > report.rms_db
                or new_report.clarity_score > report.clarity_score
            ):
                logger.info(
                    "Auto-normalized %s: %+.1f dB → %+.1f dB",
                    audio_path.name,
                    report.rms_db,
                    new_report.rms_db,
                )
                return GateDecision(
                    action=GateAction.NORMALIZED,
                    audio_path=str(normalized),
                    report=new_report,
                    reason=f"Volume adjusted from {report.rms_db:.1f} to {new_report.rms_db:.1f} dB.",
                    original_path=str(audio_path),
                )

            # Normalization didn't help — still play original
            if normalized.exists():
                normalized.unlink(missing_ok=True)
            return GateDecision(
                action=GateAction.PLAY,
                audio_path=str(audio_path),
                report=report,
                reason="Normalization attempted but did not improve quality.",
            )

        except Exception as exc:
            logger.warning("Auto-normalization failed: %s", exc)
            # If the original isn't blocked, allow it through
            if report.rms_db >= self.min_db:
                return GateDecision(
                    action=GateAction.PLAY,
                    audio_path=str(audio_path),
                    report=report,
                    reason=f"Normalization failed ({exc}), playing original.",
                )
            return GateDecision(
                action=GateAction.BLOCKED,
                audio_path=str(audio_path),
                report=report,
                reason=f"Too quiet and normalization failed: {exc}",
            )


# ── Module-level singleton ────────────────────────────────────────

_default_gate: QualityGate | None = None


def get_quality_gate() -> QualityGate:
    """Return the global quality gate singleton."""
    global _default_gate
    if _default_gate is None:
        _default_gate = QualityGate()
    return _default_gate


def check_before_playback(audio_path: str | Path) -> GateDecision:
    """Convenience function — check audio through the global gate."""
    return get_quality_gate().check(audio_path)
