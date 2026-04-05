# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
LiveVoiceSession class.

Module-level helpers (_get_serializer, _speak_fallback) and the singleton
session state live in :mod:`agentic_brain.voice.live_session` so that tests
can patch them at a single well-known location.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

import numpy as np

from agentic_brain.voice.audio_handlers import AudioHandlersMixin
from agentic_brain.voice.state import (
    LiveSessionConfig,
    SessionMetrics,
    SessionState,
    rms_amplitude,
)

logger = logging.getLogger(__name__)


def _live_session_module():
    """Lazy import of live_session to avoid circular imports at load time."""
    import agentic_brain.voice.live_session as _ls

    return _ls


# ── Live Voice Session ───────────────────────────────────────────────


class LiveVoiceSession(AudioHandlersMixin):
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
                from agentic_brain.voice.ptt import PTTConfig, PushToTalkController

                hotkey = self.config.ptt_hotkey or "ctrl+space"
                self._ptt_controller = PushToTalkController(
                    config=PTTConfig(hotkey=hotkey)
                )
                self._ptt_controller.on("transcription", self._handle_ptt_transcription)
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
            _ls = _live_session_module()
            serializer = _ls._get_serializer()
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
                            logger.info(
                                "LiveVoice: wake word detected via transcription (fallback)"
                            )
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
            _ls = _live_session_module()
            serializer = _ls._get_serializer()
            if serializer:
                serializer.speak(
                    text,
                    voice=self.config.voice,
                    rate=self.config.rate,
                    wait=True,
                )
            else:
                _ls._speak_fallback(text, self.config.voice, self.config.rate)
        except Exception as exc:
            logger.error("LiveVoice: speech error: %s", exc)
        finally:
            self._speaking = False
            if not self._stop_event.is_set():
                self._set_state(SessionState.LISTENING)
