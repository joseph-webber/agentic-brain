# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Audio stream and ML detector initialisation / teardown mixin for LiveVoiceSession.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from agentic_brain.voice.state import LiveSessionConfig, find_airpods_device

logger = logging.getLogger(__name__)


def _get_live_session_module():
    """Lazy import of live_session to avoid circular imports at load time."""
    import agentic_brain.voice.live_session as _ls
    return _ls


class AudioHandlersMixin:
    """Mixin that adds audio stream and ML detector management to LiveVoiceSession.

    Assumes ``self`` provides:
    - ``self.config``  (LiveSessionConfig)
    - ``self._metrics``  (SessionMetrics)
    - ``self._transcriber``, ``self._wake_detector``, etc. (set in __init__)
    - ``self._on_emotion``  (Optional callback)
    - ``self._last_emotion_result``

    Note: pyaudio is accessed at call-time via live_session module so that
    ``patch("agentic_brain.voice.live_session.pyaudio", ...)`` works in tests.
    """

    # ── Audio stream ─────────────────────────────────────────────

    def _open_audio_stream(self, input_device_index: Optional[int] = None) -> bool:
        _ls = _get_live_session_module()
        if not _ls._HAS_PYAUDIO:
            logger.warning("LiveVoice: PyAudio not installed")
            return False

        _pyaudio = _ls.pyaudio

        # Determine device index: explicit > config > AirPods preference > default
        device_idx = input_device_index
        if device_idx is None:
            device_idx = self.config.input_device_index  # type: ignore[attr-defined]
        if device_idx is None and self.config.prefer_airpods:  # type: ignore[attr-defined]
            device_idx = find_airpods_device()

        try:
            self._pa = _pyaudio.PyAudio()
            open_kwargs: dict[str, Any] = {
                "format": _pyaudio.paInt16,
                "channels": self.config.channels,  # type: ignore[attr-defined]
                "rate": self.config.sample_rate,  # type: ignore[attr-defined]
                "input": True,
                "frames_per_buffer": self.config.chunk_size,  # type: ignore[attr-defined]
            }
            if device_idx is not None:
                open_kwargs["input_device_index"] = device_idx
                logger.info("LiveVoice: using input device index %d", device_idx)

            self._stream = self._pa.open(**open_kwargs)
            return True
        except Exception as exc:
            logger.error("LiveVoice: cannot open mic: %s", exc)
            if self._pa:
                self._pa.terminate()
                self._pa = None
            return False

    def _close_audio_stream(self) -> None:
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    # ── Transcriber ──────────────────────────────────────────────

    def _init_transcriber(self) -> None:
        try:
            from agentic_brain.voice.transcription import get_transcriber

            self._transcriber = get_transcriber(
                use_whisper=self.config.use_whisper,  # type: ignore[attr-defined]
                model_name=self.config.whisper_model,  # type: ignore[attr-defined]
            )
        except Exception as exc:
            logger.warning("LiveVoice: transcriber init failed: %s", exc)
            self._transcriber = None

    # ── Wake Word Detector ───────────────────────────────────────

    def _init_wake_detector(self) -> None:
        """Initialize ML-based wake word detector if enabled."""
        if not self.config.use_ml_wake_word:  # type: ignore[attr-defined]
            logger.info("LiveVoice: ML wake word detection disabled")
            return

        try:
            from agentic_brain.voice.wake_word import WakeWordConfig, WakeWordDetector

            wake_config = WakeWordConfig(
                wake_phrase=self.config.wake_words[0] if self.config.wake_words else "hey iris",  # type: ignore[attr-defined]
                threshold=self.config.wake_word_threshold,  # type: ignore[attr-defined]
                sample_rate=self.config.sample_rate,  # type: ignore[attr-defined]
                alternative_phrases=self.config.wake_words,  # type: ignore[attr-defined]
                use_ml=True,
            )
            self._wake_detector = WakeWordDetector(config=wake_config)

            if self._wake_detector.load_model(self.config.wake_word_model_path):  # type: ignore[attr-defined]
                logger.info("LiveVoice: ML wake word detector ready (fast path)")
            else:
                logger.info("LiveVoice: ML wake word unavailable, using transcription fallback")
        except Exception as exc:
            logger.warning("LiveVoice: wake detector init failed: %s", exc)
            self._wake_detector = None

    def _detect_wake_word_ml(self, audio_chunk: bytes) -> bool:
        """Try ML-based wake word detection (fast, 50-100ms).

        Returns True if wake word detected via ML model.
        """
        if self._wake_detector is None or not self._wake_detector.is_ml_available:
            return False

        try:
            result = self._wake_detector.detect(audio_chunk)
            return result.detected
        except Exception:
            return False

    # ── Emotion Detector ─────────────────────────────────────────

    def _init_emotion_detector(self) -> None:
        """Initialize ML-based emotion detector if enabled."""
        if not self.config.detect_emotion:  # type: ignore[attr-defined]
            logger.info("LiveVoice: emotion detection disabled")
            return

        try:
            from agentic_brain.voice.emotions import VoiceEmotionDetector

            self._emotion_detector = VoiceEmotionDetector()
            logger.info(
                "LiveVoice: emotion detector ready (audio=%s, text=%s)",
                self._emotion_detector.has_audio_support,
                self._emotion_detector.has_text_support,
            )
        except Exception as exc:
            logger.warning("LiveVoice: emotion detector init failed: %s", exc)
            self._emotion_detector = None

    def _detect_emotion(self, audio_data: bytes, text: Optional[str]) -> Any:
        """Detect emotion from audio and/or transcribed text.

        Returns EmotionResult or None if detection is disabled/failed.
        """
        if self._emotion_detector is None:
            return None

        try:
            result = self._emotion_detector.detect(audio=audio_data, text=text)
            self._last_emotion_result = result
            self._metrics.record_emotion(result.emotion.value)  # type: ignore[attr-defined]

            if self._on_emotion:
                try:
                    self._on_emotion(result)
                except Exception:
                    logger.debug("Emotion callback error", exc_info=True)

            logger.debug(
                "LiveVoice: detected emotion=%s confidence=%.2f valence=%.2f arousal=%.2f",
                result.emotion.value,
                result.confidence,
                result.valence,
                result.arousal,
            )
            return result
        except Exception as exc:
            logger.debug("LiveVoice: emotion detection failed: %s", exc)
            return None

    # ── Silero VAD ───────────────────────────────────────────────

    def _init_vad(self) -> None:
        """Initialize Silero VAD detector if enabled.

        VAD is optional and will gracefully degrade to RMS-based detection
        when PyTorch/Silero is unavailable.
        """
        if not self.config.use_vad:  # type: ignore[attr-defined]
            logger.info("LiveVoice: VAD disabled by config")
            return

        try:
            from agentic_brain.voice.vad import SileroVAD, VADConfig

            vad_config = VADConfig(
                threshold=self.config.vad_threshold,  # type: ignore[attr-defined]
                sample_rate=self.config.sample_rate,  # type: ignore[attr-defined]
            )
            self._vad = SileroVAD(config=vad_config)

            if not self._vad.ensure_model():  # type: ignore[func-returns-value]
                logger.info("LiveVoice: Silero VAD not available, falling back to RMS")
                self._vad = None
                return

            logger.info("LiveVoice: Silero VAD initialised as primary VAD")
        except Exception as exc:
            logger.warning("LiveVoice: VAD init failed: %s", exc)
            self._vad = None
