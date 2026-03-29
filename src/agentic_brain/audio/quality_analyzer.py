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
Voice Quality Analyzer — Accessibility-first audio diagnostics.

Ensures all voice output is clear and intelligible before Joseph hears it.
Detects clipping, distortion, silence, and volume issues.

Usage:
    >>> from agentic_brain.audio.quality_analyzer import VoiceQualityAnalyzer
    >>> analyzer = VoiceQualityAnalyzer()
    >>> report = analyzer.analyze_audio("speech.wav")
    >>> print(report)
"""

from __future__ import annotations

import logging
import math
import shutil
import struct
import subprocess
import wave
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# Thresholds tuned for speech accessibility
MIN_ACCEPTABLE_DB = -30.0
MAX_ACCEPTABLE_DB = -3.0
CLIPPING_THRESHOLD = 0.98  # fraction of max sample value
SILENCE_THRESHOLD_DB = -40.0
TARGET_LOUDNESS_DB = -16.0
MIN_CLARITY_SCORE = 0.6


class Severity(Enum):
    """Issue severity level."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class QualityIssue:
    """A single quality problem detected in the audio."""

    severity: Severity
    code: str
    message: str
    recommendation: str


@dataclass
class QualityReport:
    """Complete audio quality analysis result."""

    file_path: str
    duration_seconds: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    bit_depth: int = 0

    # Volume metrics (dBFS)
    peak_db: float = -96.0
    rms_db: float = -96.0
    mean_db: float = -96.0

    # Quality metrics
    clarity_score: float = 0.0  # 0.0-1.0
    silence_ratio: float = 0.0  # 0.0-1.0
    clipping_ratio: float = 0.0  # 0.0-1.0
    dynamic_range_db: float = 0.0
    crest_factor_db: float = 0.0

    issues: List[QualityIssue] = field(default_factory=list)
    passed: bool = True

    @property
    def is_too_quiet(self) -> bool:
        return self.rms_db < MIN_ACCEPTABLE_DB

    @property
    def is_clipping(self) -> bool:
        return self.clipping_ratio > 0.001

    @property
    def is_too_loud(self) -> bool:
        return self.peak_db > MAX_ACCEPTABLE_DB

    @property
    def grade(self) -> str:
        """Human-readable quality grade."""
        if not self.passed:
            return "FAIL"
        if self.clarity_score >= 0.9:
            return "EXCELLENT"
        if self.clarity_score >= 0.7:
            return "GOOD"
        if self.clarity_score >= 0.5:
            return "FAIR"
        return "POOR"

    def summary(self) -> str:
        """Return a VoiceOver-friendly text summary."""
        lines = [
            f"Audio Quality Report: {self.grade}",
            f"File: {Path(self.file_path).name}",
            f"Duration: {self.duration_seconds:.1f} seconds",
            f"Volume: {self.rms_db:.1f} dB RMS, {self.peak_db:.1f} dB peak",
            f"Clarity: {self.clarity_score:.0%}",
            f"Silence: {self.silence_ratio:.0%}",
        ]
        if self.issues:
            lines.append(f"Issues found: {len(self.issues)}")
            for issue in self.issues:
                lines.append(f"  [{issue.severity.value}] {issue.message}")
        else:
            lines.append("No issues detected.")
        return "\n".join(lines)


class VoiceQualityAnalyzer:
    """Analyzes audio files for voice quality and accessibility compliance.

    Parameters:
        min_db: Minimum acceptable RMS level in dBFS.
        max_peak_db: Maximum acceptable peak level in dBFS.
        silence_threshold_db: Level below which audio is considered silence.
        clipping_threshold: Fraction of max sample value that counts as clipping.
    """

    def __init__(
        self,
        *,
        min_db: float = MIN_ACCEPTABLE_DB,
        max_peak_db: float = MAX_ACCEPTABLE_DB,
        silence_threshold_db: float = SILENCE_THRESHOLD_DB,
        clipping_threshold: float = CLIPPING_THRESHOLD,
    ) -> None:
        self.min_db = min_db
        self.max_peak_db = max_peak_db
        self.silence_threshold_db = silence_threshold_db
        self.clipping_threshold = clipping_threshold

    # ── Public API ────────────────────────────────────────────────

    def analyze_audio(self, audio_path: str | Path) -> QualityReport:
        """Analyze an audio file and return a complete quality report.

        Supports WAV and AIFF files natively. Other formats require sox.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        ext = audio_path.suffix.lower()
        if ext in (".wav", ".wave"):
            return self._analyze_wav(audio_path)
        if ext in (".aiff", ".aif"):
            return self._analyze_with_sox(audio_path)
        if shutil.which("sox"):
            return self._analyze_with_sox(audio_path)

        raise ValueError(
            f"Unsupported format '{ext}' and sox not available for conversion."
        )

    def quick_check(self, audio_path: str | Path) -> bool:
        """Fast pass/fail check — True if audio is acceptable."""
        try:
            report = self.analyze_audio(audio_path)
            return report.passed
        except Exception:
            return False

    # ── WAV analysis ──────────────────────────────────────────────

    def _analyze_wav(self, path: Path) -> QualityReport:
        """Analyze a WAV file using the stdlib wave module."""
        report = QualityReport(file_path=str(path))

        with wave.open(str(path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        report.channels = n_channels
        report.sample_rate = framerate
        report.bit_depth = sampwidth * 8
        report.duration_seconds = n_frames / framerate if framerate else 0.0

        if n_frames == 0:
            report.passed = False
            report.issues.append(
                QualityIssue(
                    Severity.CRITICAL,
                    "EMPTY_FILE",
                    "Audio file contains no samples.",
                    "Re-generate the audio file.",
                )
            )
            return report

        samples = self._decode_samples(raw, sampwidth, n_channels)
        self._compute_metrics(report, samples, sampwidth)
        self._run_checks(report)
        return report

    def _analyze_with_sox(self, path: Path) -> QualityReport:
        """Use sox to analyze non-WAV formats."""
        report = QualityReport(file_path=str(path))

        sox = shutil.which("sox")
        if not sox:
            raise RuntimeError("sox is required for non-WAV analysis")

        # Get stats via sox
        try:
            result = subprocess.run(
                [sox, str(path), "-n", "stat"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            # sox stat outputs to stderr
            stats = result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            raise RuntimeError(f"sox stat failed: {exc}") from exc

        report = self._parse_sox_stats(stats, report)

        # Also try soxi for file info
        soxi = shutil.which("soxi")
        if soxi:
            try:
                info = subprocess.run(
                    [soxi, str(path)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self._parse_soxi_info(info.stdout, report)
            except Exception:
                pass

        self._run_checks(report)
        return report

    # ── Sample decoding ───────────────────────────────────────────

    @staticmethod
    def _decode_samples(raw: bytes, sampwidth: int, n_channels: int) -> list[float]:
        """Decode raw PCM bytes to normalized floats [-1.0, 1.0]."""
        fmt_map = {1: "b", 2: "h", 4: "i"}
        fmt_char = fmt_map.get(sampwidth)
        if fmt_char is None:
            raise ValueError(f"Unsupported sample width: {sampwidth}")

        n_samples = len(raw) // sampwidth
        samples_int = struct.unpack(f"<{n_samples}{fmt_char}", raw)

        max_val = float(2 ** (sampwidth * 8 - 1))

        if n_channels > 1:
            # Mix down to mono by averaging channels
            mono: list[float] = []
            for i in range(0, n_samples, n_channels):
                chunk = samples_int[i : i + n_channels]
                mono.append(sum(chunk) / (n_channels * max_val))
            return mono

        return [s / max_val for s in samples_int]

    # ── Metrics computation ───────────────────────────────────────

    def _compute_metrics(
        self,
        report: QualityReport,
        samples: list[float],
        sampwidth: int,
    ) -> None:
        """Compute all quality metrics from sample data."""
        n = len(samples)
        if n == 0:
            return

        abs_samples = [abs(s) for s in samples]
        peak = max(abs_samples)
        rms = math.sqrt(sum(s * s for s in samples) / n)
        mean_abs = sum(abs_samples) / n

        # dBFS values (full scale)
        report.peak_db = self._to_dbfs(peak)
        report.rms_db = self._to_dbfs(rms)
        report.mean_db = self._to_dbfs(mean_abs)

        # Dynamic range: difference between peak and RMS
        report.dynamic_range_db = report.peak_db - report.rms_db
        report.crest_factor_db = report.dynamic_range_db

        # Clipping: samples near or at max value
        clip_thresh = self.clipping_threshold
        clipped = sum(1 for s in abs_samples if s >= clip_thresh)
        report.clipping_ratio = clipped / n

        # Silence ratio: frames below silence threshold
        silence_lin = self._from_dbfs(self.silence_threshold_db)
        silent = sum(1 for s in abs_samples if s < silence_lin)
        report.silence_ratio = silent / n

        # Clarity score: composite of volume, clipping, silence, dynamic range
        report.clarity_score = self._compute_clarity(report)

    def _compute_clarity(self, report: QualityReport) -> float:
        """Compute a 0.0-1.0 clarity score from multiple factors."""
        score = 1.0

        # Penalize if too quiet
        if report.rms_db < self.min_db:
            deficit = self.min_db - report.rms_db
            score -= min(0.4, deficit * 0.02)

        # Penalize clipping
        if report.clipping_ratio > 0.0:
            score -= min(0.3, report.clipping_ratio * 100)

        # Penalize excessive silence (>60%)
        if report.silence_ratio > 0.6:
            excess = report.silence_ratio - 0.6
            score -= min(0.2, excess * 0.5)

        # Penalize very low dynamic range (compressed/distorted)
        if report.dynamic_range_db < 3.0:
            score -= 0.1

        # Penalize if too loud (near 0 dBFS peak)
        if report.peak_db > self.max_peak_db:
            overshoot = report.peak_db - self.max_peak_db
            score -= min(0.2, overshoot * 0.05)

        return max(0.0, min(1.0, score))

    # ── Quality checks ────────────────────────────────────────────

    def _run_checks(self, report: QualityReport) -> None:
        """Run all quality checks and populate issues list."""
        report.issues.clear()
        report.passed = True

        # Too quiet
        if report.rms_db < self.min_db:
            sev = (
                Severity.ERROR
                if report.rms_db < (self.min_db - 10)
                else Severity.WARNING
            )
            report.issues.append(
                QualityIssue(
                    sev,
                    "TOO_QUIET",
                    f"Audio is too quiet at {report.rms_db:.1f} dB RMS "
                    f"(minimum: {self.min_db:.1f} dB).",
                    f"Normalize volume to {TARGET_LOUDNESS_DB:.0f} dB.",
                )
            )
            if sev == Severity.ERROR:
                report.passed = False

        # Clipping
        if report.clipping_ratio > 0.001:
            pct = report.clipping_ratio * 100
            sev = Severity.ERROR if pct > 1.0 else Severity.WARNING
            report.issues.append(
                QualityIssue(
                    sev,
                    "CLIPPING",
                    f"Clipping detected: {pct:.2f}% of samples at maximum.",
                    "Reduce volume or apply a limiter.",
                )
            )
            if sev == Severity.ERROR:
                report.passed = False

        # Too loud
        if report.peak_db > self.max_peak_db:
            report.issues.append(
                QualityIssue(
                    Severity.WARNING,
                    "TOO_LOUD",
                    f"Peak level {report.peak_db:.1f} dB exceeds "
                    f"maximum {self.max_peak_db:.1f} dB.",
                    "Apply a limiter or reduce gain.",
                )
            )

        # Excessive silence
        if report.silence_ratio > 0.7:
            report.issues.append(
                QualityIssue(
                    Severity.WARNING,
                    "EXCESSIVE_SILENCE",
                    f"Audio is {report.silence_ratio:.0%} silence.",
                    "Trim silence from edges or check recording.",
                )
            )

        # Very short
        if 0 < report.duration_seconds < 0.1:
            report.issues.append(
                QualityIssue(
                    Severity.WARNING,
                    "TOO_SHORT",
                    f"Audio is only {report.duration_seconds:.3f}s long.",
                    "File may be truncated — check the TTS output.",
                )
            )

        # Low dynamic range (possible distortion)
        if report.dynamic_range_db < 2.0 and report.duration_seconds > 0.5:
            report.issues.append(
                QualityIssue(
                    Severity.INFO,
                    "LOW_DYNAMIC_RANGE",
                    f"Dynamic range is only {report.dynamic_range_db:.1f} dB.",
                    "Audio may sound flat or distorted.",
                )
            )

        # Update clarity if issues changed
        report.clarity_score = self._compute_clarity(report)

    # ── Sox stat parsing ──────────────────────────────────────────

    @staticmethod
    def _parse_sox_stats(stats: str, report: QualityReport) -> QualityReport:
        """Parse sox stat output into a report."""
        for line in stats.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()

            try:
                if "length" in key and "seconds" in key:
                    report.duration_seconds = float(val)
                elif key == "samples read":
                    pass  # informational
                elif "rms" in key and "amplitude" in key:
                    rms_lin = float(val)
                    if rms_lin > 0:
                        report.rms_db = 20.0 * math.log10(rms_lin)
                elif "maximum amplitude" in key:
                    peak_lin = float(val)
                    if peak_lin > 0:
                        report.peak_db = 20.0 * math.log10(peak_lin)
                elif "mean" in key and "norm" in key:
                    mean_lin = float(val)
                    if mean_lin > 0:
                        report.mean_db = 20.0 * math.log10(mean_lin)
            except (ValueError, ZeroDivisionError):
                continue

        return report

    @staticmethod
    def _parse_soxi_info(info: str, report: QualityReport) -> None:
        """Parse soxi output for file metadata."""
        for line in info.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()

            try:
                if "sample rate" in key:
                    report.sample_rate = int(val)
                elif "channels" in key:
                    report.channels = int(val)
                elif "precision" in key and "bit" in val.lower():
                    report.bit_depth = int(val.split("-")[0].strip())
            except (ValueError, IndexError):
                continue

    # ── Utilities ─────────────────────────────────────────────────

    @staticmethod
    def _to_dbfs(linear: float) -> float:
        """Convert linear amplitude to dBFS."""
        if linear <= 0:
            return -96.0
        return 20.0 * math.log10(linear)

    @staticmethod
    def _from_dbfs(db: float) -> float:
        """Convert dBFS to linear amplitude."""
        return 10.0 ** (db / 20.0)
