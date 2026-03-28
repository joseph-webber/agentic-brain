# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Tests for Project Aria — Live Voice Session & Transcription.

Covers:
  - Wake word detection
  - Silence detection
  - Interrupt handling
  - Session timeout
  - Transcription accuracy mocks
  - Session lifecycle (start/stop/status)
  - Audio helpers (RMS, microphone check)
  - State machine transitions
  - Response pipeline
  - Singleton management
  - Config defaults
  - Metrics tracking
  - Fallback behaviour
"""

from __future__ import annotations

import struct
import threading
import time
from typing import Any, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── Imports under test ───────────────────────────────────────────────

from agentic_brain.voice.live_session import (
    DEFAULT_CHANNELS,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SAMPLE_RATE,
    LiveSessionConfig,
    LiveVoiceSession,
    SessionMetrics,
    SessionState,
    SILENCE_THRESHOLD,
    UTTERANCE_SILENCE_SECS,
    SESSION_TIMEOUT_SECS,
    WAKE_WORDS,
    check_microphone,
    get_live_session,
    live_session_status,
    rms_amplitude,
    start_live_session,
    stop_live_session,
    _set_session_for_testing,
)
from agentic_brain.voice.transcription import (
    BaseTranscriber,
    MacOSDictationTranscriber,
    TranscriptionMetrics,
    TranscriptionResult,
    WhisperTranscriber,
    _pcm_to_float32,
    get_transcriber,
    whisper_available,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_pcm_silence(n_samples: int = 1024) -> bytes:
    """Generate silent PCM (all zeros)."""
    return b"\x00\x00" * n_samples


def _make_pcm_tone(n_samples: int = 1024, amplitude: int = 5000) -> bytes:
    """Generate a simple loud PCM tone (constant value)."""
    return struct.pack(f"<{n_samples}h", *([amplitude] * n_samples))


class FakeTranscriber(BaseTranscriber):
    """Test double that returns canned transcription results."""

    def __init__(self, results: Optional[list[str]] = None) -> None:
        super().__init__()
        self._results = list(results or [])
        self._call_count = 0

    def is_available(self) -> bool:
        return True

    def transcribe_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = 16_000,
    ) -> Optional[TranscriptionResult]:
        self._call_count += 1
        if self._results:
            text = self._results.pop(0)
            result = TranscriptionResult(text=text, confidence=0.95, duration_ms=100.0)
            self.metrics.record(result, processing_ms=50.0)
            return result
        return None


# ══════════════════════════════════════════════════════════════════════
#  AUDIO HELPERS
# ══════════════════════════════════════════════════════════════════════


class TestRMSAmplitude:
    """Tests for rms_amplitude()."""

    def test_silence_is_zero(self):
        data = _make_pcm_silence(512)
        assert rms_amplitude(data) == 0.0

    def test_loud_tone_exceeds_threshold(self):
        data = _make_pcm_tone(512, amplitude=3000)
        assert rms_amplitude(data) > SILENCE_THRESHOLD

    def test_empty_data(self):
        assert rms_amplitude(b"") == 0.0

    def test_odd_length_data(self):
        # Odd-length bytes can't be unpacked to int16 — should return 0
        assert rms_amplitude(b"\x00\x01\x02") == 0.0

    def test_known_rms(self):
        # All samples = 100 → RMS should be 100
        data = struct.pack("<4h", 100, 100, 100, 100)
        assert rms_amplitude(data) == pytest.approx(100.0, abs=0.1)


class TestCheckMicrophone:
    """Tests for check_microphone()."""

    @patch("agentic_brain.voice.live_session._HAS_PYAUDIO", False)
    def test_no_pyaudio_returns_false(self):
        assert check_microphone() is False

    @patch("agentic_brain.voice.live_session._HAS_PYAUDIO", True)
    @patch("agentic_brain.voice.live_session.pyaudio")
    def test_pyaudio_error_returns_false(self, mock_pa):
        mock_pa.PyAudio.side_effect = Exception("no mic")
        assert check_microphone() is False


# ══════════════════════════════════════════════════════════════════════
#  SESSION CONFIG
# ══════════════════════════════════════════════════════════════════════


class TestLiveSessionConfig:
    """Tests for LiveSessionConfig defaults."""

    def test_defaults(self):
        cfg = LiveSessionConfig()
        assert cfg.sample_rate == DEFAULT_SAMPLE_RATE
        assert cfg.channels == DEFAULT_CHANNELS
        assert cfg.chunk_size == DEFAULT_CHUNK_SIZE
        assert cfg.silence_threshold == SILENCE_THRESHOLD
        assert cfg.utterance_silence_secs == UTTERANCE_SILENCE_SECS
        assert cfg.session_timeout_secs == SESSION_TIMEOUT_SECS
        assert cfg.wake_words == WAKE_WORDS
        assert cfg.voice == "Karen"
        assert cfg.rate == 155
        assert cfg.require_wake_word is True
        assert cfg.use_whisper is True

    def test_custom_config(self):
        cfg = LiveSessionConfig(voice="Moira", rate=140, session_timeout_secs=60)
        assert cfg.voice == "Moira"
        assert cfg.rate == 140
        assert cfg.session_timeout_secs == 60


# ══════════════════════════════════════════════════════════════════════
#  SESSION METRICS
# ══════════════════════════════════════════════════════════════════════


class TestSessionMetrics:
    """Tests for SessionMetrics."""

    def test_initial_values(self):
        m = SessionMetrics()
        assert m.utterances_heard == 0
        assert m.avg_response_latency_ms == 0.0
        d = m.to_dict()
        assert "utterances_heard" in d
        assert "avg_response_latency_ms" in d

    def test_record_latency(self):
        m = SessionMetrics()
        m.record_latency(100.0)
        m.record_latency(200.0)
        assert m.avg_response_latency_ms == pytest.approx(150.0)

    def test_to_dict_keys(self):
        m = SessionMetrics()
        d = m.to_dict()
        expected_keys = {
            "utterances_heard",
            "responses_given",
            "interrupts",
            "avg_response_latency_ms",
            "total_listen_secs",
            "wake_word_detections",
            "transcription_errors",
        }
        assert set(d.keys()) == expected_keys


# ══════════════════════════════════════════════════════════════════════
#  SESSION STATE MACHINE
# ══════════════════════════════════════════════════════════════════════


class TestSessionStateMachine:
    """Tests for LiveVoiceSession state transitions."""

    def test_initial_state_is_idle(self):
        s = LiveVoiceSession()
        assert s.state == SessionState.IDLE

    def test_is_running_when_idle(self):
        s = LiveVoiceSession()
        assert s.is_running is False

    def test_state_change_callback(self):
        s = LiveVoiceSession()
        states_seen: list[SessionState] = []
        s.on_state_change(lambda st: states_seen.append(st))
        s._set_state(SessionState.LISTENING)
        assert SessionState.LISTENING in states_seen

    def test_set_state_no_duplicate_event(self):
        s = LiveVoiceSession()
        count = 0

        def cb(st):
            nonlocal count
            count += 1

        s.on_state_change(cb)
        s._set_state(SessionState.LISTENING)
        s._set_state(SessionState.LISTENING)  # Same state — no event
        assert count == 1


# ══════════════════════════════════════════════════════════════════════
#  WAKE WORD DETECTION
# ══════════════════════════════════════════════════════════════════════


class TestWakeWordDetection:
    """Tests for wake word matching."""

    def test_hey_karen_detected(self):
        s = LiveVoiceSession()
        assert s._is_wake_word("Hey Karen") is True

    def test_hey_brain_detected(self):
        s = LiveVoiceSession()
        assert s._is_wake_word("hey brain, what time is it") is True

    def test_case_insensitive(self):
        s = LiveVoiceSession()
        assert s._is_wake_word("HEY KAREN") is True

    def test_no_wake_word(self):
        s = LiveVoiceSession()
        assert s._is_wake_word("What is the weather") is False

    def test_partial_match_rejected(self):
        s = LiveVoiceSession()
        assert s._is_wake_word("karen") is False  # No "hey" prefix

    def test_wake_word_in_sentence(self):
        s = LiveVoiceSession()
        assert s._is_wake_word("I said hey karen just now") is True

    def test_custom_wake_words(self):
        cfg = LiveSessionConfig(wake_words=("hey iris", "oi brain"))
        s = LiveVoiceSession(config=cfg)
        assert s._is_wake_word("Hey Iris") is True
        assert s._is_wake_word("Oi Brain") is True
        assert s._is_wake_word("Hey Karen") is False


# ══════════════════════════════════════════════════════════════════════
#  SILENCE DETECTION
# ══════════════════════════════════════════════════════════════════════


class TestSilenceDetection:
    """Tests for silence / voice activity detection."""

    def test_silence_below_threshold(self):
        data = _make_pcm_silence(512)
        assert rms_amplitude(data) < SILENCE_THRESHOLD

    def test_voice_above_threshold(self):
        data = _make_pcm_tone(512, amplitude=3000)
        assert rms_amplitude(data) > SILENCE_THRESHOLD

    def test_threshold_configurable(self):
        cfg = LiveSessionConfig(silence_threshold=100)
        s = LiveVoiceSession(config=cfg)
        # A quiet tone that exceeds 100 but not 500
        data = _make_pcm_tone(512, amplitude=200)
        rms = rms_amplitude(data)
        assert rms > cfg.silence_threshold
        assert rms < SILENCE_THRESHOLD


# ══════════════════════════════════════════════════════════════════════
#  INTERRUPT HANDLING
# ══════════════════════════════════════════════════════════════════════


class TestInterruptHandling:
    """Tests for interrupt behaviour."""

    def test_interrupt_increments_counter(self):
        s = LiveVoiceSession()
        assert s.metrics.interrupts == 0
        s.interrupt()
        assert s.metrics.interrupts == 1

    def test_interrupt_clears_speaking_flag(self):
        s = LiveVoiceSession()
        s._speaking = True
        s.interrupt()
        assert s._speaking is False

    @patch("agentic_brain.voice.live_session._get_serializer")
    def test_interrupt_resets_serializer(self, mock_get_ser):
        mock_ser = MagicMock()
        mock_get_ser.return_value = mock_ser
        s = LiveVoiceSession()
        s.interrupt()
        mock_ser.reset.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
#  SESSION TIMEOUT
# ══════════════════════════════════════════════════════════════════════


class TestSessionTimeout:
    """Tests for session timeout behaviour."""

    def test_timeout_config_default(self):
        cfg = LiveSessionConfig()
        assert cfg.session_timeout_secs == 30.0

    def test_timeout_config_custom(self):
        cfg = LiveSessionConfig(session_timeout_secs=10.0)
        assert cfg.session_timeout_secs == 10.0

    def test_session_stop_returns_metrics(self):
        s = LiveVoiceSession()
        s._session_start = time.monotonic()
        s._set_state(SessionState.LISTENING)
        result = s.stop()
        assert "metrics" in result
        assert result["state"] == "idle"


# ══════════════════════════════════════════════════════════════════════
#  TRANSCRIPTION
# ══════════════════════════════════════════════════════════════════════


class TestTranscription:
    """Tests for the transcription subsystem."""

    def test_fake_transcriber_returns_text(self):
        t = FakeTranscriber(results=["hello world"])
        r = t.transcribe_bytes(_make_pcm_tone())
        assert r is not None
        assert r.text == "hello world"

    def test_fake_transcriber_exhausts(self):
        t = FakeTranscriber(results=["one"])
        t.transcribe_bytes(_make_pcm_tone())
        r = t.transcribe_bytes(_make_pcm_tone())
        assert r is None

    def test_transcription_metrics_tracking(self):
        t = FakeTranscriber(results=["hello", "world"])
        t.transcribe_bytes(_make_pcm_tone())
        t.transcribe_bytes(_make_pcm_tone())
        assert t.metrics.total_requests == 2
        assert t.metrics.successful == 2
        assert t.metrics.accuracy_rate == 1.0

    def test_transcription_metrics_error(self):
        m = TranscriptionMetrics()
        m.record_error()
        assert m.errors == 1
        assert m.accuracy_rate == 0.0

    def test_pcm_to_float32_pure_python(self):
        data = struct.pack("<4h", 0, 16384, -16384, 32767)
        result = _pcm_to_float32(data)
        assert len(result) == 4
        assert abs(result[0]) < 0.001
        assert result[1] > 0.4

    def test_whisper_available_bool(self):
        # Just check it returns a bool
        assert isinstance(whisper_available(), bool)

    def test_get_transcriber_returns_base(self):
        t = get_transcriber(use_whisper=False)
        assert isinstance(t, BaseTranscriber)


# ══════════════════════════════════════════════════════════════════════
#  RESPONSE PIPELINE
# ══════════════════════════════════════════════════════════════════════


class TestResponsePipeline:
    """Tests for the response callback pipeline."""

    def test_default_echo_response(self):
        s = LiveVoiceSession()
        resp = s._get_response("hello")
        assert "hello" in resp

    def test_custom_callback(self):
        cfg = LiveSessionConfig(response_callback=lambda t: f"BRAIN: {t}")
        s = LiveVoiceSession(config=cfg)
        assert s._get_response("test") == "BRAIN: test"

    def test_callback_error_graceful(self):
        def bad_callback(t):
            raise ValueError("boom")

        cfg = LiveSessionConfig(response_callback=bad_callback)
        s = LiveVoiceSession(config=cfg)
        resp = s._get_response("test")
        assert "trouble" in resp.lower()


# ══════════════════════════════════════════════════════════════════════
#  SINGLETON MANAGEMENT
# ══════════════════════════════════════════════════════════════════════


class TestSingletonManagement:
    """Tests for the module-level session management functions."""

    def setup_method(self):
        _set_session_for_testing(None)

    def teardown_method(self):
        _set_session_for_testing(None)

    def test_status_when_no_session(self):
        result = live_session_status()
        assert result["state"] == "idle"

    def test_stop_when_no_session(self):
        result = stop_live_session()
        assert result["state"] == "idle"

    def test_get_live_session_none(self):
        assert get_live_session() is None

    @patch("agentic_brain.voice.live_session._HAS_PYAUDIO", False)
    def test_start_fails_without_mic(self):
        result = start_live_session()
        assert "error" in result

    def test_start_with_mock_mic(self):
        """Start session with fully mocked audio + transcriber."""
        mock_pa = MagicMock()
        mock_stream = MagicMock()
        # Return silence bytes so the listener thread doesn't crash
        mock_stream.read.return_value = _make_pcm_silence(1024)
        mock_pa.open.return_value = mock_stream

        with patch("agentic_brain.voice.live_session._HAS_PYAUDIO", True), \
             patch("agentic_brain.voice.live_session.pyaudio") as mock_pyaudio_mod:
            mock_pyaudio_mod.PyAudio.return_value = mock_pa
            mock_pyaudio_mod.paInt16 = 8  # pyaudio constant

            result = start_live_session(require_wake_word=False, session_timeout=1)
            assert result["state"] in ("listening", "waiting_for_wake")

            # Clean up
            stop_live_session()


# ══════════════════════════════════════════════════════════════════════
#  SESSION STATUS
# ══════════════════════════════════════════════════════════════════════


class TestSessionStatus:
    """Tests for status() output."""

    def test_status_shape(self):
        s = LiveVoiceSession()
        status = s.status()
        assert "state" in status
        assert "wake_detected" in status
        assert "metrics" in status
        assert "config" in status
        assert status["config"]["voice"] == "Karen"

    def test_status_reflects_state(self):
        s = LiveVoiceSession()
        s._set_state(SessionState.LISTENING)
        assert s.status()["state"] == "listening"


# ══════════════════════════════════════════════════════════════════════
#  TRANSCRIPTION METRICS
# ══════════════════════════════════════════════════════════════════════


class TestTranscriptionMetrics:
    """Tests for TranscriptionMetrics."""

    def test_realtime_factor(self):
        m = TranscriptionMetrics()
        r = TranscriptionResult(text="hi", duration_ms=1000)
        m.record(r, processing_ms=200)
        assert m.realtime_factor == pytest.approx(0.2)

    def test_to_dict(self):
        m = TranscriptionMetrics()
        d = m.to_dict()
        assert "accuracy_rate" in d
        assert "realtime_factor" in d

    def test_empty_metrics(self):
        m = TranscriptionMetrics()
        assert m.accuracy_rate == 0.0
        assert m.realtime_factor == 0.0


# ══════════════════════════════════════════════════════════════════════
#  EVENT HOOKS
# ══════════════════════════════════════════════════════════════════════


class TestEventHooks:
    """Tests for session event hooks."""

    def test_on_utterance_callback(self):
        s = LiveVoiceSession()
        utterances: list[str] = []
        s.on_utterance(lambda t: utterances.append(t))
        # Simulate utterance by calling the callback directly
        s._on_utterance("hello")
        assert "hello" in utterances

    def test_on_wake_callback(self):
        s = LiveVoiceSession()
        wakes: list[bool] = []
        s.on_wake(lambda: wakes.append(True))
        s._on_wake()
        assert len(wakes) == 1
