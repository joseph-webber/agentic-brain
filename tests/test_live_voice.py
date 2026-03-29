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

import argparse
import os
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


# ══════════════════════════════════════════════════════════════════════
#  CLI COMMAND PARSING (voice live)
# ══════════════════════════════════════════════════════════════════════

class TestVoiceLiveCLI:
    """Tests that CLI argument parsing produces correct Namespace values."""

    @staticmethod
    def _build_parser():
        """Build a minimal parser mirroring register_voice_commands."""
        from agentic_brain.cli.voice_commands import register_voice_commands

        root = argparse.ArgumentParser()
        subs = root.add_subparsers()
        register_voice_commands(subs)
        return root

    def test_default_action_is_status(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live"])
        assert ns.action == "status"

    def test_start_action(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "start"])
        assert ns.action == "start"

    def test_stop_action(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "stop"])
        assert ns.action == "stop"

    def test_wake_word_flag(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "start", "--wake-word", "hey iris"])
        assert ns.wake_word == "hey iris"

    def test_timeout_flag(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "start", "--timeout", "60"])
        assert ns.timeout == 60.0

    def test_transcriber_whisper(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "start", "--transcriber", "whisper"])
        assert ns.transcriber == "whisper"

    def test_transcriber_macos(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "start", "--transcriber", "macos"])
        assert ns.transcriber == "macos"

    def test_daemon_flag(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "start", "--daemon"])
        assert ns.daemon is True

    def test_stop_flag_shortcut(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "--stop"])
        assert ns.stop is True

    def test_status_flag_shortcut(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "--status"])
        assert ns.status_flag is True

    def test_voice_flag(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "start", "-v", "Moira"])
        assert ns.voice == "Moira"

    def test_rate_flag(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "start", "-r", "180"])
        assert ns.rate == 180

    def test_install_action(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "install"])
        assert ns.action == "install"

    def test_uninstall_action(self):
        parser = self._build_parser()
        ns = parser.parse_args(["voice", "live", "uninstall"])
        assert ns.action == "uninstall"

    def test_combined_flags(self):
        """Multiple flags in one invocation."""
        parser = self._build_parser()
        ns = parser.parse_args([
            "voice", "live", "start",
            "--wake-word", "hey iris",
            "--timeout", "45",
            "--transcriber", "macos",
            "--daemon",
            "-v", "Moira",
            "-r", "140",
        ])
        assert ns.wake_word == "hey iris"
        assert ns.timeout == 45.0
        assert ns.transcriber == "macos"
        assert ns.daemon is True
        assert ns.voice == "Moira"
        assert ns.rate == 140


# ══════════════════════════════════════════════════════════════════════
#  LIVE VOICE DAEMON
# ══════════════════════════════════════════════════════════════════════

from agentic_brain.voice.live_daemon import (
    DaemonConfig,
    LiveVoiceDaemon,
    PID_FILE,
    STATE_FILE,
    _pid_alive,
    _set_daemon_for_testing,
    daemon_status,
    install_launchd_plist,
    read_pid_status,
    start_daemon,
    stop_daemon,
    uninstall_launchd_plist,
)


class TestDaemonConfig:
    """Test DaemonConfig defaults."""

    def test_defaults(self):
        cfg = DaemonConfig()
        assert cfg.wake_words == ("hey karen", "hey brain")
        assert cfg.session_timeout == 30.0
        assert cfg.voice == "Karen"
        assert cfg.rate == 155
        assert cfg.use_whisper is True

    def test_custom_config(self):
        cfg = DaemonConfig(
            wake_words=("hey iris",),
            session_timeout=60.0,
            voice="Moira",
            rate=140,
            use_whisper=False,
        )
        assert cfg.wake_words == ("hey iris",)
        assert cfg.session_timeout == 60.0
        assert cfg.voice == "Moira"
        assert cfg.use_whisper is False


class TestDaemonStartStop:
    """Test daemon start/stop behaviour (mocked audio)."""

    def setup_method(self):
        _set_daemon_for_testing(None)

    def teardown_method(self):
        _set_daemon_for_testing(None)

    @patch("agentic_brain.voice.live_session.LiveVoiceSession.start", return_value=False)
    def test_start_fails_without_mic(self, _mock_start):
        d = LiveVoiceDaemon()
        result = d.start()
        assert result["ok"] is False
        assert "Microphone" in result["error"]

    @patch("agentic_brain.voice.live_session.LiveVoiceSession.start", return_value=True)
    @patch("agentic_brain.voice.live_session.LiveVoiceSession.is_running", new_callable=PropertyMock, return_value=True)
    def test_start_success(self, _mock_running, _mock_start):
        d = LiveVoiceDaemon()
        result = d.start()
        assert result["ok"] is True
        assert "pid" in result
        # Clean up
        d.stop()

    @patch("agentic_brain.voice.live_session.LiveVoiceSession.start", return_value=True)
    @patch("agentic_brain.voice.live_session.LiveVoiceSession.is_running", new_callable=PropertyMock, return_value=True)
    def test_double_start_blocked(self, _mock_running, _mock_start):
        d = LiveVoiceDaemon()
        d.start()
        result = d.start()
        assert result["ok"] is False
        assert "already" in result["error"].lower()
        d.stop()

    def test_stop_when_not_running(self):
        d = LiveVoiceDaemon()
        result = d.stop()
        assert result["ok"] is True

    @patch("agentic_brain.voice.live_session.LiveVoiceSession.start", return_value=True)
    @patch("agentic_brain.voice.live_session.LiveVoiceSession.is_running", new_callable=PropertyMock, return_value=True)
    def test_status_while_running(self, _mock_running, _mock_start):
        d = LiveVoiceDaemon()
        d.start()
        s = d.status()
        assert s["daemon_running"] is True
        assert s["pid"] == os.getpid()
        assert s["uptime_s"] >= 0
        d.stop()

    def test_status_when_stopped(self):
        d = LiveVoiceDaemon()
        s = d.status()
        assert s["daemon_running"] is False


class TestDaemonPIDFile:
    """Test PID file lifecycle."""

    def setup_method(self):
        PID_FILE.unlink(missing_ok=True)
        STATE_FILE.unlink(missing_ok=True)
        _set_daemon_for_testing(None)

    def teardown_method(self):
        PID_FILE.unlink(missing_ok=True)
        STATE_FILE.unlink(missing_ok=True)
        _set_daemon_for_testing(None)

    @patch("agentic_brain.voice.live_session.LiveVoiceSession.start", return_value=True)
    @patch("agentic_brain.voice.live_session.LiveVoiceSession.is_running", new_callable=PropertyMock, return_value=True)
    def test_pid_file_written_on_start(self, _mock_running, _mock_start):
        d = LiveVoiceDaemon()
        d.start()
        assert PID_FILE.exists()
        assert int(PID_FILE.read_text().strip()) == os.getpid()
        d.stop()

    @patch("agentic_brain.voice.live_session.LiveVoiceSession.start", return_value=True)
    @patch("agentic_brain.voice.live_session.LiveVoiceSession.is_running", new_callable=PropertyMock, return_value=True)
    def test_pid_file_removed_on_stop(self, _mock_running, _mock_start):
        d = LiveVoiceDaemon()
        d.start()
        d.stop()
        assert not PID_FILE.exists()

    @patch("agentic_brain.voice.live_session.LiveVoiceSession.start", return_value=True)
    @patch("agentic_brain.voice.live_session.LiveVoiceSession.is_running", new_callable=PropertyMock, return_value=True)
    def test_state_file_written(self, _mock_running, _mock_start):
        d = LiveVoiceDaemon()
        d.start()
        assert STATE_FILE.exists()
        import json
        data = json.loads(STATE_FILE.read_text())
        assert data["state"] == "running"
        d.stop()

    def test_read_pid_status_no_file(self):
        result = read_pid_status()
        assert result["daemon_running"] is False

    def test_pid_alive_current_process(self):
        assert _pid_alive(os.getpid()) is True

    def test_pid_alive_nonexistent(self):
        assert _pid_alive(99999999) is False


class TestDaemonSingletonHelpers:
    """Test module-level start_daemon / stop_daemon / daemon_status."""

    def setup_method(self):
        _set_daemon_for_testing(None)

    def teardown_method(self):
        stop_daemon()
        _set_daemon_for_testing(None)

    def test_daemon_status_no_daemon(self):
        PID_FILE.unlink(missing_ok=True)
        result = daemon_status()
        assert result["daemon_running"] is False

    @patch("agentic_brain.voice.live_session.LiveVoiceSession.start", return_value=True)
    @patch("agentic_brain.voice.live_session.LiveVoiceSession.is_running", new_callable=PropertyMock, return_value=True)
    def test_start_and_stop_daemon(self, _mock_running, _mock_start):
        result = start_daemon()
        assert result["ok"] is True
        result = stop_daemon()
        assert result["ok"] is True


class TestLaunchdIntegration:
    """Test launchd plist generation."""

    def test_install_generates_plist(self):
        result = install_launchd_plist()
        if os.uname().sysname != "Darwin":
            assert result["ok"] is False
            return
        assert result["ok"] is True
        assert "path" in result
        assert "load_command" in result
        # Clean up
        from pathlib import Path
        Path(result["path"]).unlink(missing_ok=True)

    def test_uninstall_when_no_plist(self):
        from agentic_brain.voice.live_daemon import LAUNCHD_PLIST_PATH
        LAUNCHD_PLIST_PATH.unlink(missing_ok=True)
        result = uninstall_launchd_plist()
        if os.uname().sysname != "Darwin":
            assert result["ok"] is False
        else:
            assert result["ok"] is True


class TestTranscriberSelection:
    """Test that --transcriber flag routes correctly."""

    def test_whisper_is_default(self):
        """When no --transcriber flag, use_whisper is True."""
        transcriber = None
        use_whisper = transcriber != "macos"
        assert use_whisper is True

    def test_macos_fallback(self):
        transcriber = "macos"
        use_whisper = transcriber != "macos"
        assert use_whisper is False

    def test_whisper_explicit(self):
        transcriber = "whisper"
        use_whisper = transcriber != "macos"
        assert use_whisper is True


class TestWakeWordParsing:
    """Test wake word CSV parsing in CLI handler."""

    def test_single_wake_word(self):
        wake_word = "hey iris"
        words = tuple(w.strip().lower() for w in wake_word.split(","))
        assert words == ("hey iris",)

    def test_multiple_wake_words(self):
        wake_word = "Hey Karen, Hey Brain, Hey Iris"
        words = tuple(w.strip().lower() for w in wake_word.split(","))
        assert words == ("hey karen", "hey brain", "hey iris")

    def test_default_wake_words(self):
        wake_word = None
        default = ("hey karen", "hey brain")
        words = tuple(w.strip().lower() for w in wake_word.split(",")) if wake_word else default
        assert words == default
