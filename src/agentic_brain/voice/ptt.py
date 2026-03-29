# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Push-to-talk (PTT) controller for voice input.

This module implements a small orchestration layer for push-to-talk
voice input.  It is intentionally **UI-agnostic** – no direct keyboard
hooks or GUI bindings – so that different front-ends (CLI, TUI, web
portal) can plug in their own hotkey handling.

The controller exposes a minimal event model:

- ``start`` – fired when recording starts.
- ``stop`` – fired when recording stops (audio buffer passed).
- ``audio`` – fired whenever new audio bytes are appended.
- ``transcription`` – fired when transcription is completed for the
  buffered audio.

Typical usage (pseudocode)::

    ptt = PushToTalkController()

    def on_transcription(text: str) -> None:
        session.handle_ptt_transcription(text)

    ptt.on("transcription", on_transcription)

    # UI layer calls:
    ptt.start_listening()   # hotkey down
    ptt.feed_audio(chunk)   # audio callback(s)
    ptt.stop_listening()    # hotkey up

    text = transcribe_audio(ptt.get_audio_bytes())
    ptt.complete_transcription(text)

The actual audio capture and transcription are handled elsewhere; this
module just glues events together in a thread-safe way.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PTTState(str, Enum):
    """High-level push-to-talk lifecycle states."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"


@dataclass
class PTTConfig:
    """Push-to-talk configuration.

    The *hotkey* is informational here – actual key binding is handled by
    the UI / front-end.  Timing knobs are provided for higher layers that
    want to enforce minimum / maximum recording durations or implement
    silence-based auto-stop.
    """

    hotkey: str = "ctrl+space"  # Default hotkey (front-end responsibility)
    min_duration_ms: int = 200  # Minimum recording duration
    max_duration_ms: int = 30_000  # Maximum recording duration
    auto_stop_silence_ms: int = 1_500  # Stop after this much silence


class PushToTalkController:
    """Controls push-to-talk voice input.

    This class is deliberately small and framework-free.  It coordinates
    state transitions and fires callbacks on interesting events.  Audio
    chunks are treated as opaque ``bytes`` objects – callers remain in
    control of the encoding / sample rate.
    """

    def __init__(self, config: Optional[PTTConfig] = None) -> None:
        self.config = config or PTTConfig()
        self._state: PTTState = PTTState.IDLE
        self._audio_buffer: List[bytes] = []
        self._lock = threading.Lock()
        self._callbacks: Dict[str, List[Callable[..., Any]]] = {
            "start": [],
            "stop": [],
            "audio": [],
            "transcription": [],
        }

    # ── Properties ──────────────────────────────────────────────────

    @property
    def state(self) -> PTTState:
        """Current PTT state."""

        with self._lock:
            return self._state

    # ── Public API ──────────────────────────────────────────────────

    def start_listening(self) -> None:
        """Called by UI when the PTT key is pressed.

        Clears any existing audio buffer and transitions to LISTENING.
        """

        with self._lock:
            if self._state == PTTState.LISTENING:
                return
            self._state = PTTState.LISTENING
            self._audio_buffer.clear()
        logger.debug("PTT: start_listening (hotkey=%s)", self.config.hotkey)
        self._fire_callbacks("start")

    def stop_listening(self) -> None:
        """Called by UI when the PTT key is released.

        Transitions to PROCESSING and fires the ``stop`` event with the
        collected audio chunks.
        """

        with self._lock:
            if self._state != PTTState.LISTENING:
                return
            self._state = PTTState.PROCESSING
            audio_chunks = list(self._audio_buffer)
        logger.debug("PTT: stop_listening (chunks=%d)", len(audio_chunks))
        self._fire_callbacks("stop", audio_chunks)

    def feed_audio(self, chunk: bytes) -> None:
        """Append a new audio chunk while LISTENING.

        Callers are responsible for respecting timing limits from
        :class:`PTTConfig`.  Each call also fires an ``audio`` event so
        higher layers can implement streaming transcription if desired.
        """

        if not chunk:
            return
        with self._lock:
            if self._state != PTTState.LISTENING:
                return
            self._audio_buffer.append(chunk)
            buffer_len = len(self._audio_buffer)
        self._fire_callbacks("audio", chunk, buffer_len)

    def complete_transcription(self, text: str) -> None:
        """Signal that transcription has completed for current buffer.

        This resets the controller back to IDLE and fires the
        ``transcription`` event with the recognised text.
        """

        with self._lock:
            self._state = PTTState.IDLE
        logger.debug("PTT: transcription complete (len=%d)", len(text or ""))
        self._fire_callbacks("transcription", text)

    def reset(self) -> None:
        """Reset controller to IDLE and clear any buffered audio."""

        with self._lock:
            self._state = PTTState.IDLE
            self._audio_buffer.clear()

    def get_audio_chunks(self) -> List[bytes]:
        """Return a *copy* of the current audio buffer.

        Useful for synchronous transcription pipelines.
        """

        with self._lock:
            return list(self._audio_buffer)

    def get_audio_bytes(self) -> bytes:
        """Return concatenated audio bytes for the current buffer."""

        with self._lock:
            return b"".join(self._audio_buffer)

    def on(self, event: str, callback: Callable[..., Any]) -> None:
        """Register a callback for the given event.

        Unknown events are ignored to keep the controller robust against
        typos in client code.
        """

        if event not in self._callbacks:
            logger.warning("PTT: ignoring unknown event %r", event)
            return
        self._callbacks[event].append(callback)

    # ── Internal helpers ────────────────────────────────────────────

    def _fire_callbacks(self, event: str, *args: Any, **kwargs: Any) -> None:
        callbacks = self._callbacks.get(event, [])
        for cb in list(callbacks):
            try:
                cb(*args, **kwargs)
            except Exception:
                logger.debug("PTT callback error for event %s", event, exc_info=True)
