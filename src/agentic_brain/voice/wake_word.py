# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
ML-based Wake Word Detection for "Hey Iris".

This module provides fast wake word detection using openWakeWord (Apache 2.0).
Falls back to transcription-based detection when ML model is unavailable.

Performance Targets:
- ML detection: 50-100ms latency
- Transcription fallback: 3-7s latency (not ideal but functional)

Usage::

    detector = WakeWordDetector(wake_phrase="hey iris")
    if detector.load_model():
        # Use fast ML detection
        if detector.detect(audio_chunk):
            print("Wake word detected!")
    else:
        # Fall back to transcription-based detection
        if detector.detect_fallback(transcribed_text):
            print("Wake phrase found in text!")
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

DEFAULT_WAKE_PHRASE = "hey iris"
DEFAULT_THRESHOLD = 0.5
DEFAULT_SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 1280  # 80ms at 16kHz - openWakeWord expects this


@dataclass
class WakeWordConfig:
    """Configuration for wake word detection."""

    wake_phrase: str = DEFAULT_WAKE_PHRASE
    threshold: float = DEFAULT_THRESHOLD
    sample_rate: int = DEFAULT_SAMPLE_RATE
    alternative_phrases: tuple[str, ...] = field(
        default_factory=lambda: ("hey iris", "hi iris", "hey brain", "hey karen")
    )
    use_ml: bool = True


@dataclass
class WakeWordResult:
    """Result of wake word detection."""

    detected: bool
    confidence: float
    phrase: str
    method: str  # "ml" or "fallback"
    latency_ms: float = 0.0

    def __bool__(self) -> bool:
        return self.detected


class WakeWordDetector:
    """ML-based wake word detector with transcription fallback.

    Uses openWakeWord for fast (~50-100ms) wake word detection.
    Falls back to transcription-based matching when ML model unavailable.
    """

    def __init__(
        self,
        wake_phrase: str = DEFAULT_WAKE_PHRASE,
        config: Optional[WakeWordConfig] = None,
    ) -> None:
        """Initialize the wake word detector.

        Args:
            wake_phrase: Primary wake phrase (default: "hey iris")
            config: Full configuration object (overrides wake_phrase if provided)
        """
        if config:
            self.config = config
        else:
            self.config = WakeWordConfig(wake_phrase=wake_phrase)

        self._model: Any = None
        self._model_loaded = False
        self._custom_model_path: Optional[str] = None

    @property
    def wake_phrase(self) -> str:
        """Primary wake phrase."""
        return self.config.wake_phrase

    @property
    def is_ml_available(self) -> bool:
        """True if ML model is loaded and ready."""
        return self._model_loaded and self._model is not None

    def load_model(self, custom_model_path: Optional[str] = None) -> bool:
        """Load the openWakeWord model.

        Args:
            custom_model_path: Path to custom trained model for "hey iris"

        Returns:
            True if model loaded successfully, False otherwise
        """
        if not self.config.use_ml:
            logger.info("WakeWord: ML detection disabled by config")
            return False

        try:
            import openwakeword
            from openwakeword.model import Model

            if custom_model_path:
                # Use custom "hey iris" model if available
                self._model = Model(wakeword_models=[custom_model_path])
                self._custom_model_path = custom_model_path
                logger.info("WakeWord: loaded custom model from %s", custom_model_path)
            else:
                # Use default models (includes common wake words)
                # Note: "hey iris" may need custom training
                self._model = Model()
                logger.info("WakeWord: loaded default openWakeWord models")

            self._model_loaded = True
            return True

        except ImportError:
            logger.warning(
                "WakeWord: openWakeWord not installed. "
                "Install with: pip install openwakeword"
            )
            return False
        except Exception as exc:
            logger.error("WakeWord: failed to load model: %s", exc)
            return False

    def detect(self, audio_chunk: bytes) -> WakeWordResult:
        """Check if wake word detected in audio chunk using ML model.

        Args:
            audio_chunk: Raw PCM audio bytes (int16, mono, 16kHz)

        Returns:
            WakeWordResult with detection status and confidence
        """
        import time

        t0 = time.monotonic()

        if not self._model_loaded or self._model is None:
            return WakeWordResult(
                detected=False,
                confidence=0.0,
                phrase="",
                method="ml",
                latency_ms=0.0,
            )

        try:
            # Convert bytes to numpy array (int16 to float32 normalized)
            audio_array = self._bytes_to_array(audio_chunk)

            # Run prediction
            predictions = self._model.predict(audio_array)

            # Check each wake word model's prediction
            max_confidence = 0.0
            detected_phrase = ""

            for model_name, confidence in predictions.items():
                # Handle numpy array or scalar
                if hasattr(confidence, "__iter__"):
                    conf_value = float(max(confidence))
                else:
                    conf_value = float(confidence)

                if conf_value > max_confidence:
                    max_confidence = conf_value
                    detected_phrase = model_name

            latency_ms = (time.monotonic() - t0) * 1000
            detected = max_confidence >= self.config.threshold

            if detected:
                logger.info(
                    "WakeWord: ML detected '%s' (confidence=%.2f, latency=%.1fms)",
                    detected_phrase,
                    max_confidence,
                    latency_ms,
                )

            return WakeWordResult(
                detected=detected,
                confidence=max_confidence,
                phrase=detected_phrase,
                method="ml",
                latency_ms=latency_ms,
            )

        except Exception as exc:
            logger.warning("WakeWord: ML detection error: %s", exc)
            return WakeWordResult(
                detected=False,
                confidence=0.0,
                phrase="",
                method="ml",
                latency_ms=(time.monotonic() - t0) * 1000,
            )

    def detect_fallback(self, text: str) -> WakeWordResult:
        """Fallback: check transcribed text for wake phrase.

        This is slower (3-7s latency due to transcription) but always works.

        Args:
            text: Transcribed text to search for wake phrase

        Returns:
            WakeWordResult with detection status
        """
        import time

        t0 = time.monotonic()

        if not text:
            return WakeWordResult(
                detected=False,
                confidence=0.0,
                phrase="",
                method="fallback",
                latency_ms=0.0,
            )

        normalised = text.lower().strip()

        # Check primary phrase and alternatives
        all_phrases = (self.config.wake_phrase,) + self.config.alternative_phrases

        for phrase in all_phrases:
            if phrase in normalised:
                latency_ms = (time.monotonic() - t0) * 1000
                logger.info(
                    "WakeWord: fallback detected '%s' in text (latency=%.1fms)",
                    phrase,
                    latency_ms,
                )
                return WakeWordResult(
                    detected=True,
                    confidence=1.0,  # Text match is binary
                    phrase=phrase,
                    method="fallback",
                    latency_ms=latency_ms,
                )

        return WakeWordResult(
            detected=False,
            confidence=0.0,
            phrase="",
            method="fallback",
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def detect_auto(
        self, audio_chunk: bytes, text: Optional[str] = None
    ) -> WakeWordResult:
        """Detect wake word using best available method.

        Tries ML detection first, falls back to text matching if:
        - ML model not loaded
        - ML detection fails
        - Text is provided and ML didn't detect

        Args:
            audio_chunk: Raw PCM audio bytes
            text: Optional transcribed text for fallback

        Returns:
            WakeWordResult from whichever method succeeded
        """
        # Try ML first
        if self.is_ml_available:
            result = self.detect(audio_chunk)
            if result.detected:
                return result

        # Fall back to text if available
        if text:
            return self.detect_fallback(text)

        return WakeWordResult(
            detected=False,
            confidence=0.0,
            phrase="",
            method="none",
            latency_ms=0.0,
        )

    def reset(self) -> None:
        """Reset the detector state (e.g., after wake word detected)."""
        if self._model is not None and hasattr(self._model, "reset"):
            try:
                self._model.reset()
            except Exception:
                pass

    def status(self) -> dict[str, Any]:
        """Return detector status for diagnostics."""
        return {
            "ml_available": self.is_ml_available,
            "wake_phrase": self.config.wake_phrase,
            "alternative_phrases": list(self.config.alternative_phrases),
            "threshold": self.config.threshold,
            "custom_model": self._custom_model_path,
        }

    # ── Private helpers ──────────────────────────────────────────────

    def _bytes_to_array(self, audio_bytes: bytes) -> np.ndarray:
        """Convert raw PCM bytes to numpy array for openWakeWord.

        Args:
            audio_bytes: Raw PCM int16 little-endian audio

        Returns:
            Float32 numpy array normalized to [-1, 1]
        """
        # Unpack int16 samples
        n_samples = len(audio_bytes) // 2
        fmt = f"<{n_samples}h"
        try:
            samples = struct.unpack(fmt, audio_bytes)
        except struct.error:
            return np.array([], dtype=np.float32)

        # Convert to float32 normalized
        audio_array = np.array(samples, dtype=np.float32)
        audio_array = audio_array / 32768.0  # Normalize int16 to [-1, 1]

        return audio_array


# ── Module-level singleton ───────────────────────────────────────────

_detector: Optional[WakeWordDetector] = None


def get_wake_word_detector(
    wake_phrase: str = DEFAULT_WAKE_PHRASE,
    auto_load: bool = True,
) -> WakeWordDetector:
    """Get or create the singleton wake word detector.

    Args:
        wake_phrase: Wake phrase to detect
        auto_load: Automatically load ML model if available

    Returns:
        Configured WakeWordDetector instance
    """
    global _detector

    if _detector is None:
        _detector = WakeWordDetector(wake_phrase=wake_phrase)
        if auto_load:
            _detector.load_model()

    return _detector


def detect_wake_word(audio_chunk: bytes, text: Optional[str] = None) -> WakeWordResult:
    """Convenience function to detect wake word using singleton detector.

    Args:
        audio_chunk: Raw PCM audio bytes
        text: Optional transcribed text for fallback

    Returns:
        WakeWordResult from detection
    """
    detector = get_wake_word_detector()
    return detector.detect_auto(audio_chunk, text)
