# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
State types, constants, and lightweight audio utilities for live voice sessions.
"""

from __future__ import annotations

import enum
import logging
import struct
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Optional imports (graceful degradation) ──────────────────────────

_HAS_PYAUDIO = False
try:
    import pyaudio  # type: ignore[import-untyped]

    _HAS_PYAUDIO = True
except ImportError:
    pyaudio = None  # type: ignore[assignment]

# ── Constants ────────────────────────────────────────────────────────

DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_CHANNELS = 1
DEFAULT_CHUNK_SIZE = 1024
SILENCE_THRESHOLD = 500
UTTERANCE_SILENCE_SECS = 2.0
SESSION_TIMEOUT_SECS = 30.0
WAKE_WORDS = ("hey iris", "hey karen", "hey brain")
RESPONSE_LATENCY_TARGET_MS = 500
WAKE_WORD_ML_THRESHOLD = 0.5


# ── Device Discovery ─────────────────────────────────────────────────


def find_airpods_device() -> Optional[int]:
    """Find AirPods input device index.

    Enumerates all PyAudio input devices and returns the index of the
    first device with 'airpods' in its name (case-insensitive).

    Returns:
        Device index if AirPods found, None otherwise.
    """
    if not _HAS_PYAUDIO:
        return None
    try:
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0 and "airpods" in info["name"].lower():
                logger.info("Found AirPods mic at device index %d: %s", i, info["name"])
                pa.terminate()
                return i
        pa.terminate()
    except Exception as exc:
        logger.debug("AirPods device search failed: %s", exc)
    return None


# ── Data Types ───────────────────────────────────────────────────────


class SessionState(enum.Enum):
    """Lifecycle states for a live voice session."""

    IDLE = "idle"
    WAITING_FOR_WAKE = "waiting_for_wake"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class LiveSessionConfig:
    """Configuration knobs for a live voice session."""

    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS
    chunk_size: int = DEFAULT_CHUNK_SIZE
    silence_threshold: int = SILENCE_THRESHOLD
    utterance_silence_secs: float = UTTERANCE_SILENCE_SECS
    session_timeout_secs: float = SESSION_TIMEOUT_SECS
    wake_words: tuple[str, ...] = WAKE_WORDS
    voice: str = "Karen"
    rate: int = 155
    require_wake_word: bool = True
    use_whisper: bool = True
    whisper_model: str = "base.en"
    response_callback: Optional[Callable[[str], str]] = None
    # ML-based wake word detection (fast, 50-100ms latency)
    use_ml_wake_word: bool = True
    wake_word_threshold: float = WAKE_WORD_ML_THRESHOLD
    wake_word_model_path: Optional[str] = None
    prefer_airpods: bool = True
    input_device_index: Optional[int] = None
    # Emotion detection for richer GraphRAG memory and adaptive responses
    detect_emotion: bool = True
    emotion_callback: Optional[Callable[[Any], None]] = None  # EmotionResult callback
    # Primary voice activity detection (Silero VAD)
    use_vad: bool = True
    vad_threshold: float = 0.5
    # Push-to-talk mode (optional, driven by an external PTT controller)
    ptt_mode: bool = False
    ptt_hotkey: Optional[str] = None


@dataclass
class SessionMetrics:
    """Runtime statistics for the live session."""

    utterances_heard: int = 0
    responses_given: int = 0
    interrupts: int = 0
    avg_response_latency_ms: float = 0.0
    total_listen_secs: float = 0.0
    wake_word_detections: int = 0
    transcription_errors: int = 0
    emotions_detected: int = 0
    emotion_counts: dict[str, int] = field(default_factory=dict)
    _latency_samples: list[float] = field(default_factory=list)

    def record_latency(self, ms: float) -> None:
        self._latency_samples.append(ms)
        self.avg_response_latency_ms = sum(self._latency_samples) / len(
            self._latency_samples
        )

    def record_emotion(self, emotion: str) -> None:
        """Record a detected emotion for metrics."""
        self.emotions_detected += 1
        self.emotion_counts[emotion] = self.emotion_counts.get(emotion, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "utterances_heard": self.utterances_heard,
            "responses_given": self.responses_given,
            "interrupts": self.interrupts,
            "avg_response_latency_ms": round(self.avg_response_latency_ms, 1),
            "total_listen_secs": round(self.total_listen_secs, 1),
            "wake_word_detections": self.wake_word_detections,
            "transcription_errors": self.transcription_errors,
            "emotions_detected": self.emotions_detected,
            "emotion_counts": self.emotion_counts,
        }


# ── Audio helpers ────────────────────────────────────────────────────


def rms_amplitude(data: bytes, sample_width: int = 2) -> float:
    """Compute RMS amplitude of raw PCM audio (int16 LE)."""
    if not data:
        return 0.0
    fmt = f"<{len(data) // sample_width}h"
    try:
        samples = struct.unpack(fmt, data)
    except struct.error:
        return 0.0
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5
