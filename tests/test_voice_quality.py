# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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
Tests for voice quality analyzer, audio normalizer, and quality gate.

At least 20 tests covering:
- Volume detection
- Clipping detection
- Normalization
- Quality gate blocking bad audio
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.timeout(30)

from agentic_brain.audio.audio_normalizer import AudioNormalizer
from agentic_brain.audio.quality_analyzer import (
    MIN_ACCEPTABLE_DB,
    QualityIssue,
    QualityReport,
    Severity,
    VoiceQualityAnalyzer,
)
from agentic_brain.voice.quality_gate import (
    GateAction,
    GateDecision,
    QualityGate,
    check_before_playback,
    get_quality_gate,
)

# ── Fixtures: generate WAV test files ─────────────────────────────


def _make_wav(
    path: Path,
    *,
    freq: float = 440.0,
    duration: float = 1.0,
    amplitude: float = 0.5,
    sample_rate: int = 22050,
    channels: int = 1,
    sampwidth: int = 2,
) -> Path:
    """Generate a sine-wave WAV file for testing."""
    n_frames = int(sample_rate * duration)
    max_val = 2 ** (sampwidth * 8 - 1) - 1

    samples = []
    for i in range(n_frames * channels):
        frame_idx = i // channels
        t = frame_idx / sample_rate
        value = int(amplitude * max_val * math.sin(2 * math.pi * freq * t))
        samples.append(value)

    fmt_map = {1: "b", 2: "h", 4: "i"}
    fmt_char = fmt_map[sampwidth]
    raw = struct.pack(f"<{len(samples)}{fmt_char}", *samples)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)

    return path


def _make_silent_wav(
    path: Path, duration: float = 1.0, sample_rate: int = 22050
) -> Path:
    """Generate a silent WAV file."""
    return _make_wav(path, amplitude=0.0, duration=duration, sample_rate=sample_rate)


def _make_clipping_wav(
    path: Path, duration: float = 0.5, sample_rate: int = 22050
) -> Path:
    """Generate a heavily clipped WAV file (square wave at max amplitude)."""
    n_frames = int(sample_rate * duration)
    max_val = 32767  # 16-bit max
    samples = []
    for i in range(n_frames):
        # Square wave at full scale — guaranteed clipping
        samples.append(max_val if (i % 100) < 50 else -max_val)

    raw = struct.pack(f"<{n_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)
    return path


def _make_quiet_wav(path: Path, amplitude: float = 0.001) -> Path:
    """Generate a very quiet WAV file."""
    return _make_wav(path, amplitude=amplitude, duration=0.5)


def _make_empty_wav(path: Path) -> Path:
    """Generate a WAV file with zero frames."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(b"")
    return path


@pytest.fixture
def tmp_wav(tmp_path: Path) -> Path:
    """Normal-volume sine wave."""
    return _make_wav(tmp_path / "normal.wav", amplitude=0.5)


@pytest.fixture
def silent_wav(tmp_path: Path) -> Path:
    return _make_silent_wav(tmp_path / "silent.wav")


@pytest.fixture
def clipping_wav(tmp_path: Path) -> Path:
    return _make_clipping_wav(tmp_path / "clipping.wav")


@pytest.fixture
def quiet_wav(tmp_path: Path) -> Path:
    return _make_quiet_wav(tmp_path / "quiet.wav")


@pytest.fixture
def empty_wav(tmp_path: Path) -> Path:
    return _make_empty_wav(tmp_path / "empty.wav")


@pytest.fixture
def loud_wav(tmp_path: Path) -> Path:
    return _make_wav(tmp_path / "loud.wav", amplitude=0.99)


@pytest.fixture
def stereo_wav(tmp_path: Path) -> Path:
    return _make_wav(tmp_path / "stereo.wav", amplitude=0.5, channels=2)


@pytest.fixture
def analyzer() -> VoiceQualityAnalyzer:
    return VoiceQualityAnalyzer()


@pytest.fixture
def normalizer() -> AudioNormalizer:
    return AudioNormalizer()


@pytest.fixture
def gate() -> QualityGate:
    return QualityGate()


# ══════════════════════════════════════════════════════════════════
# QUALITY ANALYZER TESTS
# ══════════════════════════════════════════════════════════════════


class TestVoiceQualityAnalyzer:
    """Tests for VoiceQualityAnalyzer."""

    def test_analyze_normal_audio(self, analyzer: VoiceQualityAnalyzer, tmp_wav: Path):
        """Normal audio should produce a passing report."""
        report = analyzer.analyze_audio(tmp_wav)
        assert report.passed
        assert report.duration_seconds == pytest.approx(1.0, abs=0.01)
        assert report.sample_rate == 22050
        assert report.channels == 1
        assert report.bit_depth == 16

    def test_volume_detection_normal(
        self, analyzer: VoiceQualityAnalyzer, tmp_wav: Path
    ):
        """Normal volume should be within acceptable range."""
        report = analyzer.analyze_audio(tmp_wav)
        # A 0.5 amplitude sine has peak ~-6 dB and RMS ~-9 dB
        assert -12.0 < report.peak_db < 0.0
        assert -15.0 < report.rms_db < 0.0

    def test_volume_detection_quiet(
        self, analyzer: VoiceQualityAnalyzer, quiet_wav: Path
    ):
        """Very quiet audio should be detected as too quiet."""
        report = analyzer.analyze_audio(quiet_wav)
        assert report.is_too_quiet
        assert report.rms_db < MIN_ACCEPTABLE_DB

    def test_volume_detection_loud(
        self, analyzer: VoiceQualityAnalyzer, loud_wav: Path
    ):
        """Loud audio near 0 dBFS should be flagged."""
        report = analyzer.analyze_audio(loud_wav)
        assert report.peak_db > -1.0

    def test_clipping_detection(
        self, analyzer: VoiceQualityAnalyzer, clipping_wav: Path
    ):
        """Square wave at max amplitude should detect clipping."""
        report = analyzer.analyze_audio(clipping_wav)
        assert report.is_clipping
        assert report.clipping_ratio > 0.0
        any_clip_issue = any(i.code == "CLIPPING" for i in report.issues)
        assert any_clip_issue

    def test_no_clipping_on_normal(self, analyzer: VoiceQualityAnalyzer, tmp_wav: Path):
        """Normal sine wave should not flag clipping."""
        report = analyzer.analyze_audio(tmp_wav)
        assert not report.is_clipping
        assert report.clipping_ratio == pytest.approx(0.0, abs=0.001)

    def test_silence_detection(self, analyzer: VoiceQualityAnalyzer, silent_wav: Path):
        """Silent file should have 100% silence ratio."""
        report = analyzer.analyze_audio(silent_wav)
        assert report.silence_ratio == pytest.approx(1.0, abs=0.01)

    def test_empty_file_fails(self, analyzer: VoiceQualityAnalyzer, empty_wav: Path):
        """Empty WAV should fail with EMPTY_FILE issue."""
        report = analyzer.analyze_audio(empty_wav)
        assert not report.passed
        assert any(i.code == "EMPTY_FILE" for i in report.issues)

    def test_file_not_found_raises(self, analyzer: VoiceQualityAnalyzer):
        """Analyzing nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            analyzer.analyze_audio("/nonexistent/file.wav")

    def test_clarity_score_range(self, analyzer: VoiceQualityAnalyzer, tmp_wav: Path):
        """Clarity score should be between 0 and 1."""
        report = analyzer.analyze_audio(tmp_wav)
        assert 0.0 <= report.clarity_score <= 1.0

    def test_clarity_score_high_for_good_audio(
        self, analyzer: VoiceQualityAnalyzer, tmp_wav: Path
    ):
        """Good audio should have clarity score above 0.7."""
        report = analyzer.analyze_audio(tmp_wav)
        assert report.clarity_score >= 0.7

    def test_clarity_score_low_for_quiet_audio(
        self, analyzer: VoiceQualityAnalyzer, quiet_wav: Path
    ):
        """Very quiet audio should have reduced clarity score."""
        report = analyzer.analyze_audio(quiet_wav)
        assert report.clarity_score < 0.8

    def test_stereo_analysis(self, analyzer: VoiceQualityAnalyzer, stereo_wav: Path):
        """Stereo files should be analyzed (mixed to mono internally)."""
        report = analyzer.analyze_audio(stereo_wav)
        assert report.channels == 2
        assert report.passed

    def test_report_summary_voiceover_friendly(
        self, analyzer: VoiceQualityAnalyzer, tmp_wav: Path
    ):
        """Summary should be a readable string (no raw numbers)."""
        report = analyzer.analyze_audio(tmp_wav)
        summary = report.summary()
        assert "Audio Quality Report" in summary
        assert "Duration" in summary
        assert "Volume" in summary

    def test_grade_excellent_for_clean_audio(
        self, analyzer: VoiceQualityAnalyzer, tmp_wav: Path
    ):
        """Clean audio should grade EXCELLENT or GOOD."""
        report = analyzer.analyze_audio(tmp_wav)
        assert report.grade in ("EXCELLENT", "GOOD")

    def test_quick_check_returns_bool(
        self, analyzer: VoiceQualityAnalyzer, tmp_wav: Path
    ):
        """quick_check should return True for good audio."""
        assert analyzer.quick_check(tmp_wav) is True

    def test_quick_check_false_for_empty(
        self, analyzer: VoiceQualityAnalyzer, empty_wav: Path
    ):
        """quick_check should return False for empty audio."""
        assert analyzer.quick_check(empty_wav) is False

    def test_dynamic_range(self, analyzer: VoiceQualityAnalyzer, tmp_wav: Path):
        """Dynamic range should be positive for a sine wave."""
        report = analyzer.analyze_audio(tmp_wav)
        assert report.dynamic_range_db > 0


# ══════════════════════════════════════════════════════════════════
# AUDIO NORMALIZER TESTS
# ══════════════════════════════════════════════════════════════════


class TestAudioNormalizer:
    """Tests for AudioNormalizer."""

    def test_normalize_volume_creates_file(
        self, normalizer: AudioNormalizer, tmp_wav: Path
    ):
        """Normalizing should produce an output file."""
        result = normalizer.normalize_volume(tmp_wav)
        assert result.exists()
        assert result != tmp_wav

    def test_normalize_volume_custom_output(
        self, normalizer: AudioNormalizer, tmp_wav: Path, tmp_path: Path
    ):
        """Custom output path should be respected."""
        out = tmp_path / "custom_output.wav"
        result = normalizer.normalize_volume(tmp_wav, output_path=out)
        assert result == out
        assert out.exists()

    def test_normalize_changes_volume(
        self, normalizer: AudioNormalizer, quiet_wav: Path
    ):
        """Normalizing a quiet file should increase its volume."""
        result = normalizer.normalize_volume(quiet_wav, target_db=-16)
        assert result.exists()
        # Re-analyze to confirm
        from agentic_brain.audio.quality_analyzer import VoiceQualityAnalyzer

        analyzer = VoiceQualityAnalyzer()
        original = analyzer.analyze_audio(quiet_wav)
        normalized = analyzer.analyze_audio(result)
        assert normalized.rms_db > original.rms_db

    def test_normalize_file_not_found(self, normalizer: AudioNormalizer):
        """Should raise for missing file."""
        with pytest.raises(FileNotFoundError):
            normalizer.normalize_volume("/no/such/file.wav")

    def test_trim_edges_creates_file(self, normalizer: AudioNormalizer, tmp_wav: Path):
        """trim_edges should produce an output file."""
        result = normalizer.trim_edges(tmp_wav)
        assert result.exists()

    def test_trim_edges_file_not_found(self, normalizer: AudioNormalizer):
        """Should raise for missing file."""
        with pytest.raises(FileNotFoundError):
            normalizer.trim_edges("/no/such/file.wav")

    def test_remove_silence_creates_file(
        self, normalizer: AudioNormalizer, tmp_wav: Path
    ):
        """remove_silence should produce an output file."""
        result = normalizer.remove_silence(tmp_wav)
        assert result.exists()

    def test_remove_silence_file_not_found(self, normalizer: AudioNormalizer):
        """Should raise for missing file."""
        with pytest.raises(FileNotFoundError):
            normalizer.remove_silence("/no/such/file.wav")

    def test_sox_available_property(self, normalizer: AudioNormalizer):
        """sox_available should reflect actual sox installation."""
        import shutil

        expected = shutil.which("sox") is not None
        assert normalizer.sox_available == expected

    def test_python_fallback_normalize(self, tmp_wav: Path, tmp_path: Path):
        """Pure-Python fallback should work when sox is missing."""
        normalizer = AudioNormalizer(sox_path="/nonexistent/sox")
        assert not normalizer.sox_available
        out = tmp_path / "py_normalized.wav"
        result = normalizer.normalize_volume(tmp_wav, output_path=out)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_python_fallback_trim(self, tmp_wav: Path, tmp_path: Path):
        """Pure-Python trim should work without sox."""
        normalizer = AudioNormalizer(sox_path="/nonexistent/sox")
        out = tmp_path / "py_trimmed.wav"
        result = normalizer.trim_edges(tmp_wav, output_path=out)
        assert result.exists()


# ══════════════════════════════════════════════════════════════════
# QUALITY GATE TESTS
# ══════════════════════════════════════════════════════════════════


class TestQualityGate:
    """Tests for QualityGate."""

    def test_gate_passes_good_audio(self, gate: QualityGate, tmp_wav: Path):
        """Good audio should pass the gate."""
        decision = gate.check(tmp_wav)
        assert decision.allowed
        assert decision.action == GateAction.PLAY

    def test_gate_blocks_missing_file(self, gate: QualityGate):
        """Missing file should be blocked."""
        decision = gate.check("/no/such/file.wav")
        assert not decision.allowed
        assert decision.action == GateAction.BLOCKED
        assert "not found" in decision.reason.lower()

    def test_gate_blocks_clipping(self, clipping_wav: Path):
        """Heavily clipped audio should be blocked."""
        gate = QualityGate(block_clipping=True, clipping_threshold=0.01)
        decision = gate.check(clipping_wav)
        assert decision.action == GateAction.BLOCKED
        assert "clip" in decision.reason.lower()

    def test_gate_auto_normalizes_quiet(self, quiet_wav: Path):
        """Quiet audio should be auto-normalized when enabled."""
        gate = QualityGate(auto_normalize=True, min_db=-30.0)
        decision = gate.check(quiet_wav)
        # It should either normalize or block (if too quiet to rescue)
        assert decision.action in (GateAction.NORMALIZED, GateAction.BLOCKED)

    def test_gate_blocks_empty(self, gate: QualityGate, empty_wav: Path):
        """Empty audio should be blocked."""
        decision = gate.check(empty_wav)
        assert decision.action == GateAction.BLOCKED
        assert "empty" in decision.reason.lower()

    def test_gate_no_normalize_when_disabled(self, quiet_wav: Path):
        """With auto_normalize=False, quiet audio should still pass or block."""
        gate = QualityGate(auto_normalize=False)
        decision = gate.check(quiet_wav)
        assert decision.action != GateAction.NORMALIZED

    def test_gate_decision_properties(self, gate: QualityGate, tmp_wav: Path):
        """Decision should have correct properties."""
        decision = gate.check(tmp_wav)
        assert decision.audio_path == str(tmp_wav)
        assert isinstance(decision.report, QualityReport)

    def test_validate_shortcut(self, gate: QualityGate, tmp_wav: Path):
        """validate() should return True for good audio."""
        assert gate.validate(tmp_wav) is True

    def test_validate_rejects_empty(self, gate: QualityGate, empty_wav: Path):
        """validate() should return False for empty audio."""
        assert gate.validate(empty_wav) is False

    def test_module_level_check(self, tmp_wav: Path):
        """Module-level convenience function should work."""
        decision = check_before_playback(tmp_wav)
        assert decision.allowed

    def test_singleton_gate(self):
        """get_quality_gate should return same instance."""
        # Reset singleton for test isolation
        import agentic_brain.voice.quality_gate as qg_mod

        qg_mod._default_gate = None
        g1 = get_quality_gate()
        g2 = get_quality_gate()
        assert g1 is g2
        qg_mod._default_gate = None  # cleanup

    def test_gate_handles_analysis_error(self, gate: QualityGate, tmp_path: Path):
        """If analysis throws, gate should block gracefully."""
        bad_file = tmp_path / "corrupt.wav"
        bad_file.write_bytes(b"NOT A WAV FILE AT ALL")
        decision = gate.check(bad_file)
        assert decision.action == GateAction.BLOCKED
        assert "error" in decision.reason.lower()


# ══════════════════════════════════════════════════════════════════
# QUALITY REPORT TESTS
# ══════════════════════════════════════════════════════════════════


class TestQualityReport:
    """Tests for QualityReport dataclass."""

    def test_default_report_values(self):
        report = QualityReport(file_path="test.wav")
        assert report.duration_seconds == 0.0
        assert report.passed is True
        assert report.issues == []

    def test_is_too_quiet_property(self):
        report = QualityReport(file_path="test.wav", rms_db=-40.0)
        assert report.is_too_quiet

    def test_is_clipping_property(self):
        report = QualityReport(file_path="test.wav", clipping_ratio=0.05)
        assert report.is_clipping

    def test_grade_fail(self):
        report = QualityReport(file_path="test.wav", passed=False)
        assert report.grade == "FAIL"

    def test_grade_excellent(self):
        report = QualityReport(file_path="test.wav", clarity_score=0.95)
        assert report.grade == "EXCELLENT"

    def test_grade_good(self):
        report = QualityReport(file_path="test.wav", clarity_score=0.75)
        assert report.grade == "GOOD"

    def test_grade_fair(self):
        report = QualityReport(file_path="test.wav", clarity_score=0.55)
        assert report.grade == "FAIR"

    def test_grade_poor(self):
        report = QualityReport(file_path="test.wav", clarity_score=0.3)
        assert report.grade == "POOR"

    def test_summary_includes_issues(self):
        report = QualityReport(
            file_path="test.wav",
            duration_seconds=1.0,
            rms_db=-20.0,
            peak_db=-6.0,
            clarity_score=0.8,
            silence_ratio=0.1,
            issues=[QualityIssue(Severity.WARNING, "TEST", "Test issue", "Fix it")],
        )
        summary = report.summary()
        assert "Issues found: 1" in summary
        assert "Test issue" in summary
