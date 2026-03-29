# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Project Aria — Live Voice Session (bidirectional conversational voice).

This module implements the DREAM FEATURE: real-time voice conversation
with the brain.  Joseph speaks, the brain listens, transcribes, thinks,
and responds — all with voice.  No typing needed.

Architecture
============

1. **Wake-word detection** – listens for "Hey Karen" or "Hey Brain" via
   the local :class:`WhisperTranscriber` (whisper.cpp on M2) or macOS
   dictation as a fallback.
2. **Continuous listening** – after wake, the session streams audio and
   transcribes in real-time.
3. **Silence detection** – 2 s of silence marks the end of an utterance.
   30 s of silence times the session out.
4. **Interrupt detection** – if Joseph speaks while the brain is talking,
   the current utterance is immediately terminated.
5. **Voice response** – responses are spoken through the singleton
   :class:`VoiceSerializer`, respecting the global speech lock.

All heavy audio work happens in background threads.  Target latency is
< 500 ms from end-of-speech to start-of-response.

Works fully offline with whisper.cpp.

See also :mod:`agentic_brain.voice.live_mode` for the *text-streaming*
live mode (LLM token → sentence → speak).
"""

from __future__ import annotations

import enum
import logging
import os
import struct
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np

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


def check_microphone() -> bool:
    """Return True if a microphone can be opened via PyAudio."""
    if not _HAS_PYAUDIO:
        return False
    try:
        pa = pyaudio.PyAudio()
        try:
            info = pa.get_default_input_device_info()
            return info is not None
        finally:
            pa.terminate()
    except Exception:
        return False


# ── Live Voice Session ───────────────────────────────────────────────


class LiveVoiceSession:
    """A real-time bidirectional voice conversation session.

    Usage::

        session = LiveVoiceSession(config=LiveSessionConfig(
            response_callback=my_llm_callback,
        ))
        session.start()
        # ... session runs in background threads ...
        session.stop()
        print(session.metrics.to_dict())
    """

    def __init__(self, config: Optional[LiveSessionConfig] = None) -> None:
        self.config = config or LiveSessionConfig()
        self._state = SessionState.IDLE
        self._state_lock = threading.Lock()
        self._metrics = SessionMetrics()
        self._stop_event = threading.Event()
        self._listen_thread: Optional[threading.Thread] = None
        self._last_voice_activity: float = 0.0
        self._session_start: float = 0.0
        self._transcriber: Any = None
        self._pa: Any = None
        self._stream: Any = None
        self._wake_detected = not self.config.require_wake_word
        self._on_state_change: Optional[Callable[[SessionState], None]] = None
        self._on_utterance: Optional[Callable[[str], None]] = None
        self._on_wake: Optional[Callable[[], None]] = None
        self._on_emotion: Optional[Callable[[Any], None]] = self.config.emotion_callback
        self._speaking = False
        # ML-based wake word detector (fast detection)
        self._wake_detector: Any = None
        # ML-based emotion detector (for GraphRAG memory)
        self._emotion_detector: Any = None
        self._last_emotion_result: Any = None
        # Silero VAD (primary voice activity detector when available)
        self._vad: Any = None
        # Optional push-to-talk controller (external hotkey-driven input)
        self._ptt_controller: Any = None
        if self.config.ptt_mode:
            try:
                from agentic_brain.voice.ptt import PushToTalkController, PTTConfig

                hotkey = self.config.ptt_hotkey or "ctrl+space"
                self._ptt_controller = PushToTalkController(
                    config=PTTConfig(hotkey=hotkey)
                )
                self._ptt_controller.on(
                    "transcription", self._handle_ptt_transcription
                )
            except Exception:
                logger.debug("LiveVoice: PTT initialisation failed", exc_info=True)

    # ── Properties ───────────────────────────────────────────────

    @property
    def state(self) -> SessionState:
        with self._state_lock:
            return self._state

    @property
    def metrics(self) -> SessionMetrics:
        return self._metrics

    @property
    def is_running(self) -> bool:
        return self.state not in (
            SessionState.IDLE,
            SessionState.ERROR,
            SessionState.STOPPING,
        )

    # ── Event hooks ──────────────────────────────────────────────

    def on_state_change(self, callback: Callable[[SessionState], None]) -> None:
        """Register a callback fired on every state transition."""
        self._on_state_change = callback

    def on_utterance(self, callback: Callable[[str], None]) -> None:
        """Register a callback fired when a complete utterance is captured."""
        self._on_utterance = callback

    def on_wake(self, callback: Callable[[], None]) -> None:
        """Register a callback fired when the wake word is detected."""
        self._on_wake = callback

    def on_emotion(self, callback: Callable[[Any], None]) -> None:
        """Register a callback fired when emotion is detected for an utterance.

        The callback receives an EmotionResult object with:
        - emotion: The detected basic emotion (Emotion enum)
        - confidence: Detection confidence 0.0-1.0
        - valence: Emotional valence -1.0 to 1.0
        - arousal: Arousal level 0.0 to 1.0
        """
        self._on_emotion = callback

    @property
    def last_emotion(self) -> Any:
        """Return the most recently detected EmotionResult, or None."""
        return self._last_emotion_result

    # ── State machine ────────────────────────────────────────────

    def _set_state(self, new_state: SessionState) -> None:
        with self._state_lock:
            old = self._state
            self._state = new_state
        if old != new_state:
            logger.info("LiveVoice: %s -> %s", old.value, new_state.value)
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception:
                    logger.debug("State change callback error", exc_info=True)

    # ── Public API ───────────────────────────────────────────────

    def start(self) -> bool:
        """Start the live voice session.

        Returns True on success, False if the microphone is unavailable.
        """
        if self.is_running:
            logger.warning("LiveVoice: session already running")
            return False

        self._init_transcriber()
        self._init_wake_detector()
        self._init_emotion_detector()
        self._init_vad()

        if not self._open_audio_stream():
            logger.error("LiveVoice: microphone unavailable")
            self._set_state(SessionState.ERROR)
            return False

        self._stop_event.clear()
        self._session_start = time.monotonic()
        self._last_voice_activity = time.monotonic()
        self._wake_detected = not self.config.require_wake_word

        if self.config.require_wake_word:
            self._set_state(SessionState.WAITING_FOR_WAKE)
        else:
            self._set_state(SessionState.LISTENING)

        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            name="live-voice-listener",
            daemon=True,
        )
        self._listen_thread.start()
        return True

    def stop(self) -> dict[str, Any]:
        """Stop the session gracefully.  Returns final metrics."""
        self._set_state(SessionState.STOPPING)
        self._stop_event.set()

        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=3.0)

        self._close_audio_stream()
        self._metrics.total_listen_secs = time.monotonic() - self._session_start
        self._set_state(SessionState.IDLE)
        return self.status()

    def interrupt(self) -> None:
        """Interrupt the brain's current speech immediately."""
        self._metrics.interrupts += 1
        self._speaking = False
        try:
            from agentic_brain.voice._speech_lock import interrupt_speech

            interrupt_speech()
        except ImportError:
            logger.debug("interrupt_speech not available")
        try:
            serializer = _get_serializer()
            if serializer:
                serializer.reset()
        except Exception:
            logger.debug("Serializer reset failed", exc_info=True)

    def status(self) -> dict[str, Any]:
        """Return a JSON-serialisable status snapshot."""
        status_dict = {
            "state": self.state.value,
            "wake_detected": self._wake_detected,
            "metrics": self._metrics.to_dict(),
            "config": {
                "voice": self.config.voice,
                "rate": self.config.rate,
                "wake_words": list(self.config.wake_words),
                "session_timeout_secs": self.config.session_timeout_secs,
                "require_wake_word": self.config.require_wake_word,
                "use_whisper": self.config.use_whisper,
                "use_ml_wake_word": self.config.use_ml_wake_word,
                "detect_emotion": self.config.detect_emotion,
                "ptt_mode": self.config.ptt_mode,
            },
        }
        # Add wake word detector status if available
        if self._wake_detector is not None:
            try:
                status_dict["wake_detector"] = self._wake_detector.status()
            except Exception:
                pass
        # Add emotion detector status and last result
        if self._emotion_detector is not None:
            status_dict["emotion_detector"] = {
                "has_audio_support": self._emotion_detector.has_audio_support,
                "has_text_support": self._emotion_detector.has_text_support,
            }
        if self._last_emotion_result is not None:
            try:
                status_dict["last_emotion"] = self._last_emotion_result.to_dict()
            except Exception:
                pass
        return status_dict

    # ── Audio stream ─────────────────────────────────────────────

    def _open_audio_stream(self, input_device_index: Optional[int] = None) -> bool:
        if not _HAS_PYAUDIO:
            logger.warning("LiveVoice: PyAudio not installed")
            return False

        # Determine device index: explicit > config > AirPods preference > default
        device_idx = input_device_index
        if device_idx is None:
            device_idx = self.config.input_device_index
        if device_idx is None and self.config.prefer_airpods:
            device_idx = find_airpods_device()

        try:
            self._pa = pyaudio.PyAudio()
            open_kwargs: dict[str, Any] = {
                "format": pyaudio.paInt16,
                "channels": self.config.channels,
                "rate": self.config.sample_rate,
                "input": True,
                "frames_per_buffer": self.config.chunk_size,
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
                use_whisper=self.config.use_whisper,
                model_name=self.config.whisper_model,
            )
        except Exception as exc:
            logger.warning("LiveVoice: transcriber init failed: %s", exc)
            self._transcriber = None

    # ── Wake Word Detector ───────────────────────────────────────

    def _init_wake_detector(self) -> None:
        """Initialize ML-based wake word detector if enabled."""
        if not self.config.use_ml_wake_word:
            logger.info("LiveVoice: ML wake word detection disabled")
            return

        try:
            from agentic_brain.voice.wake_word import WakeWordConfig, WakeWordDetector

            wake_config = WakeWordConfig(
                wake_phrase=self.config.wake_words[0] if self.config.wake_words else "hey iris",
                threshold=self.config.wake_word_threshold,
                sample_rate=self.config.sample_rate,
                alternative_phrases=self.config.wake_words,
                use_ml=True,
            )
            self._wake_detector = WakeWordDetector(config=wake_config)

            if self._wake_detector.load_model(self.config.wake_word_model_path):
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

    def _init_emotion_detector(self) -> None:
        """Initialize ML-based emotion detector if enabled."""
        if not self.config.detect_emotion:
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
            self._metrics.record_emotion(result.emotion.value)

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

    def _init_vad(self) -> None:
        """Initialize Silero VAD detector if enabled.

        VAD is optional and will gracefully degrade to RMS-based detection
        when PyTorch/Silero is unavailable.
        """
        if not self.config.use_vad:
            logger.info("LiveVoice: VAD disabled by config")
            return

        try:
            from agentic_brain.voice.vad import SileroVAD, VADConfig

            vad_config = VADConfig(
                threshold=self.config.vad_threshold,
                sample_rate=self.config.sample_rate,
            )
            self._vad = SileroVAD(config=vad_config)

            # Ensure the model can be loaded; if not, disable VAD.
            if not self._vad.ensure_model():  # type: ignore[func-returns-value]
                logger.info("LiveVoice: Silero VAD not available, falling back to RMS")
                self._vad = None
                return

            logger.info("LiveVoice: Silero VAD initialised as primary VAD")
        except Exception as exc:
            logger.warning("LiveVoice: VAD init failed: %s", exc)
            self._vad = None

    # ── Core listen loop ─────────────────────────────────────────

    def _listen_loop(self) -> None:
        silence_start: Optional[float] = None
        audio_chunks: list[bytes] = []

        while not self._stop_event.is_set():
            elapsed_silence = time.monotonic() - self._last_voice_activity
            if elapsed_silence > self.config.session_timeout_secs:
                logger.info(
                    "LiveVoice: session timed out after %.0fs silence",
                    elapsed_silence,
                )
                break

            chunk = self._read_chunk()
            if chunk is None:
                time.sleep(0.01)
                continue

            rms = rms_amplitude(chunk)

            # Primary voice activity detection via Silero VAD when available.
            is_voice = False
            if self._vad is not None:
                try:
                    samples = np.frombuffer(chunk, dtype=np.int16)
                    if samples.size:
                        is_voice = any(True for _ in self._vad.detect_speech(samples))
                except Exception:
                    is_voice = rms > self.config.silence_threshold
            else:
                is_voice = rms > self.config.silence_threshold

            # Interrupt detection: Joseph speaks while brain talking
            if is_voice and self._speaking:
                logger.info("LiveVoice: interrupt detected (RMS=%.0f)", rms)
                self.interrupt()

            # ── Wake word gate ───────────────────────────────────
            if not self._wake_detected:
                # Try ML-based detection first (fast path: 50-100ms)
                if self._detect_wake_word_ml(chunk):
                    self._wake_detected = True
                    self._metrics.wake_word_detections += 1
                    self._last_voice_activity = time.monotonic()
                    self._set_state(SessionState.LISTENING)
                    logger.info("LiveVoice: wake word detected via ML (fast path)")
                    if self._on_wake:
                        try:
                            self._on_wake()
                        except Exception:
                            pass
                    self._respond("Yes?")
                    audio_chunks.clear()
                    continue

                # Fallback: transcription-based detection (slower: 3-7s)
                if is_voice:
                    audio_chunks.append(chunk)
                    silence_start = None
                else:
                    if audio_chunks:
                        text = self._transcribe(audio_chunks)
                        audio_chunks.clear()
                        if text and self._is_wake_word(text):
                            self._wake_detected = True
                            self._metrics.wake_word_detections += 1
                            self._last_voice_activity = time.monotonic()
                            self._set_state(SessionState.LISTENING)
                            logger.info("LiveVoice: wake word detected via transcription (fallback)")
                            if self._on_wake:
                                try:
                                    self._on_wake()
                                except Exception:
                                    pass
                            self._respond("Yes?")
                continue

            # ── Continuous listening ─────────────────────────────
            if is_voice:
                audio_chunks.append(chunk)
                silence_start = None
                self._last_voice_activity = time.monotonic()
                if self.state != SessionState.LISTENING:
                    self._set_state(SessionState.LISTENING)
            else:
                if silence_start is None:
                    silence_start = time.monotonic()

                silence_duration = time.monotonic() - (
                    silence_start or time.monotonic()
                )

                if (
                    audio_chunks
                    and silence_duration >= self.config.utterance_silence_secs
                ):
                    self._set_state(SessionState.PROCESSING)
                    # Save audio before transcription for emotion detection
                    audio_data = b"".join(audio_chunks)
                    text = self._transcribe(audio_chunks)
                    audio_chunks.clear()
                    silence_start = None

                    if text:
                        self._metrics.utterances_heard += 1

                        # Detect emotion from the utterance (audio + text)
                        self._detect_emotion(audio_data, text)

                        if self._on_utterance:
                            try:
                                self._on_utterance(text)
                            except Exception:
                                logger.debug("Utterance callback error", exc_info=True)

                        response = self._get_response(text)
                        if response:
                            t0 = time.monotonic()
                            self._respond(response)
                            latency_ms = (time.monotonic() - t0) * 1000
                            self._metrics.record_latency(latency_ms)

        self._close_audio_stream()

    def _read_chunk(self) -> Optional[bytes]:
        if self._stream is None:
            return None
        try:
            return self._stream.read(
                self.config.chunk_size,
                exception_on_overflow=False,
            )
        except Exception:
            return None

    # ── Transcription ────────────────────────────────────────────

    def _transcribe(self, chunks: list[bytes]) -> Optional[str]:
        if not chunks:
            return None
        audio_data = b"".join(chunks)
        if self._transcriber:
            try:
                result = self._transcriber.transcribe_bytes(
                    audio_data,
                    sample_rate=self.config.sample_rate,
                )
                if result and result.text.strip():
                    return result.text.strip()
            except Exception as exc:
                self._metrics.transcription_errors += 1
                logger.warning("LiveVoice: transcription error: %s", exc)
        return None

    # ── Wake word matching ───────────────────────────────────────

    def _is_wake_word(self, text: str) -> bool:
        normalised = text.lower().strip()
        return any(wake in normalised for wake in self.config.wake_words)

    # ── Response pipeline ────────────────────────────────────────

    def _get_response(self, user_text: str) -> Optional[str]:
        if self.config.response_callback:
            try:
                return self.config.response_callback(user_text)
            except Exception as exc:
                logger.error("LiveVoice: response callback error: %s", exc)
                return "Sorry, I had trouble processing that."
        return f"I heard you say: {user_text}"

    def _respond(self, text: str) -> None:
        self._set_state(SessionState.RESPONDING)
        self._speaking = True
        self._metrics.responses_given += 1
        try:
            serializer = _get_serializer()
            if serializer:
                serializer.speak(
                    text,
                    voice=self.config.voice,
                    rate=self.config.rate,
                    wait=True,
                )
            else:
                _speak_fallback(text, self.config.voice, self.config.rate)
        except Exception as exc:
            logger.error("LiveVoice: speech error: %s", exc)
        finally:
            self._speaking = False
            if not self._stop_event.is_set():
                self._set_state(SessionState.LISTENING)


# ── Module-level helpers ─────────────────────────────────────────────

_session: Optional[LiveVoiceSession] = None
_session_lock = threading.Lock()


def _get_serializer():
    """Lazy import of the singleton voice serializer."""
    try:
        from agentic_brain.voice.serializer import get_voice_serializer

        return get_voice_serializer()
    except Exception:
        return None


def _speak_fallback(text: str, voice: str, rate: int) -> None:
    """Last-resort speech via macOS ``say`` command."""
    try:
        sysname = os.uname().sysname
    except AttributeError:
        sysname = ""
    if sysname != "Darwin":
        logger.warning("LiveVoice: no speech fallback on %s", sysname)
        return
    try:
        subprocess.run(
            ["say", "-v", voice, "-r", str(rate), text],
            timeout=30,
            capture_output=True,
        )
    except Exception as exc:
        logger.error("LiveVoice: say fallback failed: %s", exc)


# ── Singleton session management (for MCP tools / CLI) ───────────────


def start_live_session(
    voice: str = "Karen",
    rate: int = 155,
    require_wake_word: bool = True,
    session_timeout: float = SESSION_TIMEOUT_SECS,
    response_callback: Optional[Callable[[str], str]] = None,
) -> dict[str, Any]:
    """Start a live voice session.  Returns status dict."""
    global _session
    with _session_lock:
        if _session and _session.is_running:
            return {"error": "Session already running", **_session.status()}

        config = LiveSessionConfig(
            voice=voice,
            rate=rate,
            require_wake_word=require_wake_word,
            session_timeout_secs=session_timeout,
            response_callback=response_callback,
        )
        _session = LiveVoiceSession(config=config)
        ok = _session.start()
        if not ok:
            return {
                "error": (
                    "Failed to start – microphone unavailable. "
                    "Install PyAudio: pip install pyaudio"
                ),
                "state": "error",
            }
        return _session.status()


def stop_live_session() -> dict[str, Any]:
    """Stop the current live voice session.  Returns final metrics."""
    global _session
    with _session_lock:
        if not _session or not _session.is_running:
            return {"state": "idle", "message": "No active session"}
        return _session.stop()


def live_session_status() -> dict[str, Any]:
    """Return the current live voice session status."""
    with _session_lock:
        if not _session:
            return {"state": "idle", "message": "No session created"}
        return _session.status()


def get_live_session() -> Optional[LiveVoiceSession]:
    """Return the singleton session (or None)."""
    return _session


def _set_session_for_testing(s: Optional[LiveVoiceSession]) -> None:
    """Replace the global session — **test-only**."""
    global _session
    _session = s
