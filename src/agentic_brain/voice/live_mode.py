# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Live Voice Mode (Project Aria) - Real-time conversational voice.

Provides a streaming voice mode where text can be fed incrementally
(e.g. from an LLM token stream) and spoken with minimal latency.

Key features:
* Sentence-boundary buffering — accumulates tokens until a full
  sentence is ready, then speaks immediately.
* Interrupt support — Joseph can say "stop" to cancel in-progress speech.
* Seamless integration with VoiceSerializer (no overlap).

Usage::

    from agentic_brain.voice.live_mode import LiveVoiceMode, get_live_mode

    live = get_live_mode()
    live.start(voice="Karen", rate=160)
    live.feed("Hello Joseph, ")
    live.feed("how are you today?")
    live.flush()   # speak any remaining buffer
    live.stop()
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Regex for sentence boundaries
_SENTENCE_END = re.compile(r"[.!?]\s+|[.!?]$|\n")


class LiveVoiceMode:
    """Real-time voice mode that speaks text as it arrives.

    Buffers incoming text tokens and speaks complete sentences
    through the VoiceSerializer to guarantee no overlap.
    """

    def __init__(
        self,
        voice: str = "Karen",
        rate: int = 160,
        min_chunk_len: int = 20,
        speak_fn: Optional[Callable[..., bool]] = None,
    ) -> None:
        self._voice = voice
        self._rate = rate
        self._min_chunk_len = min_chunk_len
        self._speak_fn = speak_fn

        self._buffer: str = ""
        self._active = False
        self._interrupted = False
        self._lock = threading.Lock()
        self._sentences_spoken: int = 0
        self._total_chars: int = 0
        self._start_time: Optional[float] = None
        self._history: List[str] = []

    # ── Lifecycle ────────────────────────────────────────────────────

    def start(
        self,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
    ) -> None:
        """Activate live mode. Resets buffer and counters."""
        with self._lock:
            self._voice = voice or self._voice
            self._rate = rate or self._rate
            self._buffer = ""
            self._active = True
            self._interrupted = False
            self._sentences_spoken = 0
            self._total_chars = 0
            self._start_time = time.time()
            self._history = []
        logger.info(
            "Live voice mode started (voice=%s, rate=%d)", self._voice, self._rate
        )

    def stop(self) -> None:
        """Deactivate live mode. Flushes remaining buffer."""
        self.flush()
        with self._lock:
            self._active = False
        logger.info(
            "Live voice mode stopped (sentences=%d, chars=%d)",
            self._sentences_spoken,
            self._total_chars,
        )

    def interrupt(self) -> None:
        """Interrupt current speech and discard buffer."""
        with self._lock:
            self._interrupted = True
            self._buffer = ""
        logger.info("Live voice mode interrupted")

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_interrupted(self) -> bool:
        return self._interrupted

    # ── Feed / Flush ─────────────────────────────────────────────────

    def feed(self, text: str) -> int:
        """Feed a text chunk (e.g. a single LLM token).

        Returns the number of sentences spoken as a result of this feed.
        """
        if not text:
            return 0

        with self._lock:
            if not self._active or self._interrupted:
                return 0
            self._buffer += text
            self._total_chars += len(text)

        return self._try_speak()

    def flush(self) -> bool:
        """Speak whatever is left in the buffer."""
        with self._lock:
            if not self._buffer.strip():
                return False
            chunk = self._buffer.strip()
            self._buffer = ""

        if self._interrupted:
            return False

        return self._do_speak(chunk)

    # ── Status ───────────────────────────────────────────────────────

    def status(self) -> Dict:
        """Diagnostic status."""
        with self._lock:
            elapsed = time.time() - self._start_time if self._start_time else 0
        return {
            "active": self._active,
            "interrupted": self._interrupted,
            "voice": self._voice,
            "rate": self._rate,
            "buffer_len": len(self._buffer),
            "sentences_spoken": self._sentences_spoken,
            "total_chars": self._total_chars,
            "elapsed_s": round(elapsed, 1),
            "history_len": len(self._history),
        }

    # ── Internal ─────────────────────────────────────────────────────

    def _try_speak(self) -> int:
        """Extract and speak complete sentences from the buffer."""
        spoken = 0

        while True:
            with self._lock:
                if self._interrupted:
                    break
                match = _SENTENCE_END.search(self._buffer)
                if match is None:
                    # No sentence boundary yet — check if buffer is very long
                    if len(self._buffer) > 200:
                        # Force-speak a long chunk to keep latency down
                        chunk = self._buffer.strip()
                        self._buffer = ""
                    else:
                        break
                else:
                    end_pos = match.end()
                    chunk = self._buffer[:end_pos].strip()
                    self._buffer = self._buffer[end_pos:]

            if not chunk or len(chunk) < 3:
                continue

            if self._do_speak(chunk):
                spoken += 1

        return spoken

    def _do_speak(self, text: str) -> bool:
        """Speak a single chunk through the serializer."""
        if self._interrupted:
            return False

        speak = self._speak_fn or self._default_speak
        try:
            result = speak(text, voice=self._voice, rate=self._rate)
            with self._lock:
                self._sentences_spoken += 1
                self._history.append(text)
            return bool(result)
        except Exception:
            logger.exception("Live mode speak failed for: %s", text[:60])
            return False

    @staticmethod
    def _default_speak(text: str, voice: str = "Karen", rate: int = 160) -> bool:
        from agentic_brain.voice.serializer import get_voice_serializer

        return get_voice_serializer().speak(text, voice=voice, rate=rate)


# ── Singleton ────────────────────────────────────────────────────────

_live_mode: Optional[LiveVoiceMode] = None
_live_lock = threading.Lock()


def get_live_mode() -> LiveVoiceMode:
    """Return the process-wide live mode singleton."""
    global _live_mode
    if _live_mode is None:
        with _live_lock:
            if _live_mode is None:
                _live_mode = LiveVoiceMode()
    return _live_mode


def _set_live_mode_for_testing(lm: Optional[LiveVoiceMode]) -> None:
    """Replace the global live mode (tests only)."""
    global _live_mode
    _live_mode = lm
