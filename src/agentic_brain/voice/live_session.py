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

Implementation is split across:
- :mod:`agentic_brain.voice.state`         – constants, data types
- :mod:`agentic_brain.voice.audio_handlers` – audio stream + ML detector mixins
- :mod:`agentic_brain.voice.session`       – LiveVoiceSession class

See also :mod:`agentic_brain.voice.live_mode` for the *text-streaming*
live mode (LLM token → sentence → speak).
"""

from __future__ import annotations

import logging
import os
import struct
import subprocess
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Optional imports (graceful degradation) ──────────────────────────
# NOTE: _HAS_PYAUDIO and pyaudio are kept here (not in sub-modules) so
# that tests can patch them at this well-known location.

_HAS_PYAUDIO = False
try:
    import pyaudio  # type: ignore[import-untyped]

    _HAS_PYAUDIO = True
except ImportError:
    pyaudio = None  # type: ignore[assignment]

# ── Re-export constants and data types from sub-modules ──────────────

# Re-export LiveVoiceSession from session sub-module
from agentic_brain.voice.session import LiveVoiceSession
from agentic_brain.voice.state import (
    DEFAULT_CHANNELS,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SAMPLE_RATE,
    RESPONSE_LATENCY_TARGET_MS,
    SESSION_TIMEOUT_SECS,
    SILENCE_THRESHOLD,
    UTTERANCE_SILENCE_SECS,
    WAKE_WORD_ML_THRESHOLD,
    WAKE_WORDS,
    LiveSessionConfig,
    SessionMetrics,
    SessionState,
    find_airpods_device,
    rms_amplitude,
)

# ── Audio utilities defined here (so tests can patch _HAS_PYAUDIO/pyaudio) ──


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


# ── Module-level helpers ─────────────────────────────────────────────
# NOTE: _get_serializer and _speak_fallback are kept here so that tests
# can patch them at this location. session.py accesses them via a lazy
# import of this module at call-time.


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

_session: Optional[LiveVoiceSession] = None
_session_lock = threading.Lock()


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


__all__ = [
    # constants
    "DEFAULT_CHANNELS",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_SAMPLE_RATE",
    "RESPONSE_LATENCY_TARGET_MS",
    "SESSION_TIMEOUT_SECS",
    "SILENCE_THRESHOLD",
    "UTTERANCE_SILENCE_SECS",
    "WAKE_WORD_ML_THRESHOLD",
    "WAKE_WORDS",
    # data types
    "LiveSessionConfig",
    "SessionMetrics",
    "SessionState",
    # utilities
    "check_microphone",
    "find_airpods_device",
    "rms_amplitude",
    # session
    "LiveVoiceSession",
    # module-level helpers
    "_get_serializer",
    "_speak_fallback",
    # singleton helpers
    "_set_session_for_testing",
    "get_live_session",
    "live_session_status",
    "start_live_session",
    "stop_live_session",
    # pyaudio compat (for test patching)
    "_HAS_PYAUDIO",
    "pyaudio",
]
