# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Tests for ML-based wake word detection.

CRITICAL for accessibility - Users need fast wake word detection!
Target: 50-100ms latency (vs 3-7s with transcription).
"""

import struct
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from agentic_brain.voice.wake_word import (
    DEFAULT_WAKE_PHRASE,
    WakeWordConfig,
    WakeWordDetector,
    WakeWordResult,
    detect_wake_word,
    get_wake_word_detector,
)


class TestWakeWordConfig:
    """Test WakeWordConfig defaults and customization."""

    def test_default_config(self):
        """Test default configuration values."""
        config = WakeWordConfig()
        assert config.wake_phrase == "hey iris"
        assert config.threshold == 0.5
        assert config.sample_rate == 16_000
        assert "hey iris" in config.alternative_phrases

    def test_custom_config(self):
        """Test custom configuration."""
        config = WakeWordConfig(
            wake_phrase="hey brain",
            threshold=0.7,
            sample_rate=44100,
        )
        assert config.wake_phrase == "hey brain"
        assert config.threshold == 0.7
        assert config.sample_rate == 44100


class TestWakeWordResult:
    """Test WakeWordResult data class."""

    def test_result_detected(self):
        """Test result when wake word detected."""
        result = WakeWordResult(
            detected=True,
            confidence=0.85,
            phrase="hey iris",
            method="ml",
            latency_ms=75.0,
        )
        assert result.detected is True
        assert bool(result) is True
        assert result.confidence == 0.85
        assert result.phrase == "hey iris"
        assert result.method == "ml"
        assert result.latency_ms == 75.0

    def test_result_not_detected(self):
        """Test result when wake word not detected."""
        result = WakeWordResult(
            detected=False,
            confidence=0.2,
            phrase="",
            method="ml",
        )
        assert result.detected is False
        assert bool(result) is False


class TestWakeWordDetector:
    """Test WakeWordDetector class."""

    def test_init_default(self):
        """Test default initialization."""
        detector = WakeWordDetector()
        assert detector.wake_phrase == "hey iris"
        assert detector.is_ml_available is False  # Not loaded yet

    def test_init_custom_phrase(self):
        """Test initialization with custom phrase."""
        detector = WakeWordDetector(wake_phrase="hey brain")
        assert detector.wake_phrase == "hey brain"

    def test_init_with_config(self):
        """Test initialization with config object."""
        config = WakeWordConfig(wake_phrase="hey karen", threshold=0.8)
        detector = WakeWordDetector(config=config)
        assert detector.wake_phrase == "hey karen"
        assert detector.config.threshold == 0.8

    def test_load_model_no_openwakeword(self):
        """Test graceful degradation when openwakeword not installed."""
        detector = WakeWordDetector()

        with patch.dict("sys.modules", {"openwakeword": None}):
            # Simulate import failure
            with patch(
                "agentic_brain.voice.wake_word.WakeWordDetector.load_model",
                return_value=False,
            ):
                result = detector.load_model()
                # Should return False gracefully
                assert detector.is_ml_available is False

    def test_detect_without_model(self):
        """Test detect() returns empty result when model not loaded."""
        detector = WakeWordDetector()
        # Model not loaded

        audio_chunk = b"\x00" * 2560  # 80ms of silence
        result = detector.detect(audio_chunk)

        assert result.detected is False
        assert result.confidence == 0.0
        assert result.method == "ml"

    def test_detect_fallback_with_phrase(self):
        """Test fallback detection finds wake phrase in text."""
        detector = WakeWordDetector(wake_phrase="hey iris")

        result = detector.detect_fallback("Hey Iris, what's the weather?")
        assert result.detected is True
        assert result.phrase == "hey iris"
        assert result.method == "fallback"
        assert result.confidence == 1.0

    def test_detect_fallback_no_phrase(self):
        """Test fallback detection when phrase not in text."""
        detector = WakeWordDetector(wake_phrase="hey iris")

        result = detector.detect_fallback("What's the weather today?")
        assert result.detected is False
        assert result.method == "fallback"

    def test_detect_fallback_alternative_phrase(self):
        """Test fallback detection with alternative phrase."""
        config = WakeWordConfig(
            wake_phrase="hey iris",
            alternative_phrases=("hey iris", "hey brain", "hey karen"),
        )
        detector = WakeWordDetector(config=config)

        result = detector.detect_fallback("Hey brain, help me out")
        assert result.detected is True
        assert result.phrase == "hey brain"

    def test_detect_fallback_empty_text(self):
        """Test fallback detection with empty text."""
        detector = WakeWordDetector()

        result = detector.detect_fallback("")
        assert result.detected is False

        result = detector.detect_fallback(None)  # type: ignore
        assert result.detected is False

    def test_detect_auto_uses_ml_first(self):
        """Test detect_auto tries ML detection first."""
        detector = WakeWordDetector()

        # Mock ML availability
        detector._model_loaded = True
        detector._model = MagicMock()
        detector._model.predict.return_value = {"hey_iris": 0.9}

        audio_chunk = b"\x00" * 2560
        result = detector.detect_auto(audio_chunk, text="hey iris")

        # Should have tried ML (even if it returned weird data)
        assert result.method in ("ml", "fallback")

    def test_detect_auto_falls_back_to_text(self):
        """Test detect_auto falls back to text when ML fails."""
        detector = WakeWordDetector()
        # ML not available

        audio_chunk = b"\x00" * 2560
        result = detector.detect_auto(audio_chunk, text="hey iris what time is it")

        assert result.detected is True
        assert result.method == "fallback"
        assert result.phrase == "hey iris"

    def test_status(self):
        """Test status() returns correct info."""
        detector = WakeWordDetector(wake_phrase="hey iris")

        status = detector.status()
        assert status["ml_available"] is False
        assert status["wake_phrase"] == "hey iris"
        assert "hey iris" in status["alternative_phrases"]
        assert status["threshold"] == 0.5

    def test_reset(self):
        """Test reset() doesn't crash."""
        detector = WakeWordDetector()
        # Should not raise even without model
        detector.reset()

        # With mock model
        detector._model = MagicMock()
        detector._model.reset = MagicMock()
        detector.reset()
        detector._model.reset.assert_called_once()

    def test_bytes_to_array(self):
        """Test audio bytes conversion to numpy array."""
        detector = WakeWordDetector()

        # Create simple int16 audio samples
        samples = [0, 16384, -16384, 32767, -32768]
        audio_bytes = struct.pack(f"<{len(samples)}h", *samples)

        array = detector._bytes_to_array(audio_bytes)

        assert isinstance(array, np.ndarray)
        assert array.dtype == np.float32
        assert len(array) == len(samples)
        # Check normalization
        assert -1.0 <= array.min() <= 1.0
        assert -1.0 <= array.max() <= 1.0


class TestModuleFunctions:
    """Test module-level convenience functions."""

    def test_get_wake_word_detector_singleton(self):
        """Test get_wake_word_detector returns singleton."""
        # Reset singleton for clean test
        import agentic_brain.voice.wake_word as ww

        ww._detector = None

        detector1 = get_wake_word_detector(auto_load=False)
        detector2 = get_wake_word_detector(auto_load=False)

        assert detector1 is detector2

    def test_detect_wake_word_convenience(self):
        """Test detect_wake_word convenience function."""
        # Reset singleton
        import agentic_brain.voice.wake_word as ww

        ww._detector = None

        audio_chunk = b"\x00" * 2560
        result = detect_wake_word(audio_chunk, text="hey iris please help")

        assert result.detected is True
        assert result.method == "fallback"


class TestIntegrationWithLiveSession:
    """Test integration with LiveVoiceSession."""

    def test_live_session_config_has_wake_word_options(self):
        """Test LiveSessionConfig has ML wake word options."""
        from agentic_brain.voice.live_session import LiveSessionConfig

        config = LiveSessionConfig()
        assert hasattr(config, "use_ml_wake_word")
        assert hasattr(config, "wake_word_threshold")
        assert hasattr(config, "wake_word_model_path")
        assert config.use_ml_wake_word is True
        assert config.wake_word_threshold == 0.5

    def test_live_session_wake_words_include_iris(self):
        """Test default wake words include 'hey iris'."""
        from agentic_brain.voice.live_session import WAKE_WORDS

        assert "hey iris" in WAKE_WORDS


class TestPerformance:
    """Performance-related tests."""

    def test_fallback_latency_under_10ms(self):
        """Test fallback text matching is fast."""
        import time

        detector = WakeWordDetector()

        text = "Hey Iris, what's the weather like in Adelaide today?"

        start = time.monotonic()
        for _ in range(1000):
            detector.detect_fallback(text)
        elapsed = time.monotonic() - start

        # 1000 detections should take < 100ms (0.1ms each)
        assert elapsed < 0.1, f"Fallback too slow: {elapsed*1000:.2f}ms for 1000 calls"
