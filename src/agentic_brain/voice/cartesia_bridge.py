# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Cartesia Bridge - Connect LiveVoiceMode to CartesiaTTS streaming.

This module bridges the sentence-buffering LiveVoiceMode with Cartesia's
ultra-low-latency WebSocket TTS for real-time streaming voice output.

Architecture
============

    LLM tokens → LiveVoiceMode (buffer) → complete sentence → CartesiaTTS (stream) → audio

Key features:
* 40ms time-to-first-audio via Cartesia Sonic 3
* Streaming playback - audio plays as chunks arrive
* VoiceSerializer lock respected - no overlap possible
* Graceful fallback to macOS ``say`` if Cartesia unavailable

Usage::

    from agentic_brain.voice.cartesia_bridge import (
        get_cartesia_live_mode,
        CartesiaLiveMode,
    )

    live = get_cartesia_live_mode()
    live.start()
    live.feed("Hello Joseph, ")
    live.feed("how are you today?")
    live.flush()
    live.stop()
"""

from __future__ import annotations

import array
import logging
import os
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Optional

if TYPE_CHECKING:
    from agentic_brain.voice.cartesia_tts import CartesiaTTS
    from agentic_brain.voice.live_mode import LiveVoiceMode

logger = logging.getLogger(__name__)

# PyAudio is optional - fallback to file-based playback
_HAS_PYAUDIO = False
try:
    import pyaudio  # type: ignore[import-untyped]

    _HAS_PYAUDIO = True
except ImportError:
    pyaudio = None  # type: ignore[assignment]


class CartesiaStreamPlayer:
    """Play streaming PCM audio chunks with minimal latency.

    Accepts raw PCM f32le chunks from Cartesia WebSocket and plays them
    via PyAudio. Falls back to file-based playback if PyAudio unavailable.
    """

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._lock = threading.Lock()
        self._playing = False

    def _ensure_stream(self) -> bool:
        """Initialize PyAudio stream if not already open."""
        if not _HAS_PYAUDIO:
            return False

        with self._lock:
            if self._stream is not None:
                return True

            try:
                self._pa = pyaudio.PyAudio()
                self._stream = self._pa.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=self.sample_rate,
                    output=True,
                    frames_per_buffer=1024,
                )
                return True
            except Exception:
                logger.exception("Failed to initialize PyAudio stream")
                self._cleanup()
                return False

    def _cleanup(self) -> None:
        """Close PyAudio resources."""
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            if self._pa is not None:
                try:
                    self._pa.terminate()
                except Exception:
                    pass
                self._pa = None

    def play_chunks(self, chunks: Iterator[bytes]) -> bool:
        """Play streaming audio chunks.

        Args:
            chunks: Iterator of raw PCM f32le bytes from Cartesia.

        Returns:
            True if playback completed successfully.
        """
        self._playing = True
        chunks_played = 0

        try:
            if self._ensure_stream():
                # PyAudio streaming - lowest latency
                for chunk in chunks:
                    if not self._playing:
                        break
                    if chunk:
                        self._stream.write(chunk)
                        chunks_played += 1
                return chunks_played > 0
            else:
                # Fallback: collect all chunks and play via afplay
                return self._play_fallback(chunks)
        except Exception:
            logger.exception("Error during streaming playback")
            return False
        finally:
            self._playing = False

    def _play_fallback(self, chunks: Iterator[bytes]) -> bool:
        """Fallback playback via file + afplay (macOS)."""
        all_audio = b"".join(chunk for chunk in chunks if chunk)
        if not all_audio:
            return False

        # Convert f32le to wav
        wav_data = self._pcm_f32le_to_wav(all_audio)

        cache_dir = Path.home() / ".cache" / "agentic-brain" / "cartesia-stream"
        cache_dir.mkdir(parents=True, exist_ok=True)
        wav_path = cache_dir / f"stream_{int(time.time() * 1000)}.wav"

        try:
            wav_path.write_bytes(wav_data)
            result = subprocess.run(
                ["afplay", str(wav_path)],
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except Exception:
            logger.exception("Fallback playback failed")
            return False
        finally:
            try:
                wav_path.unlink()
            except Exception:
                pass

    def _pcm_f32le_to_wav(self, pcm_data: bytes) -> bytes:
        """Convert raw PCM f32le to WAV format."""
        # Convert f32 to s16
        num_samples = len(pcm_data) // 4
        f32_samples = struct.unpack(f"<{num_samples}f", pcm_data)
        s16_samples = array.array(
            "h", [int(max(-1.0, min(1.0, s)) * 32767) for s in f32_samples]
        )

        # Build WAV header
        sample_rate = self.sample_rate
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_size = len(s16_samples) * 2
        file_size = 36 + data_size

        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            file_size,
            b"WAVE",
            b"fmt ",
            16,  # fmt chunk size
            1,  # PCM format
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b"data",
            data_size,
        )

        return header + s16_samples.tobytes()

    def stop(self) -> None:
        """Interrupt current playback."""
        self._playing = False

    def close(self) -> None:
        """Release all audio resources."""
        self.stop()
        self._cleanup()


class CartesiaLiveMode:
    """LiveVoiceMode connected to CartesiaTTS streaming output.

    Extends LiveVoiceMode with Cartesia WebSocket streaming for ultra-low
    latency TTS. Falls back to macOS ``say`` when Cartesia is unavailable.
    """

    def __init__(
        self,
        voice: str = "Karen",
        rate: int = 160,
        cartesia_voice_id: Optional[str] = None,
        sample_rate: int = 44100,
    ) -> None:
        self._voice = voice
        self._rate = rate
        self._cartesia_voice_id = cartesia_voice_id or os.getenv("CARTESIA_VOICE_ID")
        self._sample_rate = sample_rate

        # Lazy-loaded components
        self._live_mode: Optional[LiveVoiceMode] = None
        self._cartesia_tts: Optional[CartesiaTTS] = None
        self._player: Optional[CartesiaStreamPlayer] = None
        self._lock = threading.Lock()

        # Metrics
        self._cartesia_calls = 0
        self._fallback_calls = 0
        self._total_latency_ms = 0.0
        self._start_time: Optional[float] = None

    def _get_live_mode(self) -> LiveVoiceMode:
        """Get or create the underlying LiveVoiceMode."""
        if self._live_mode is None:
            from agentic_brain.voice.live_mode import LiveVoiceMode

            self._live_mode = LiveVoiceMode(
                voice=self._voice,
                rate=self._rate,
                speak_fn=self._speak_cartesia,
            )
        return self._live_mode

    def _get_cartesia(self) -> Optional[CartesiaTTS]:
        """Lazy-load CartesiaTTS if available."""
        if self._cartesia_tts is None:
            api_key = os.getenv("CARTESIA_API_KEY")
            if not api_key:
                logger.debug("CARTESIA_API_KEY not set - will use fallback")
                return None

            try:
                from agentic_brain.voice.cartesia_tts import CartesiaTTS

                self._cartesia_tts = CartesiaTTS(
                    api_key=api_key,
                    default_voice_id=self._cartesia_voice_id,
                    sample_rate=self._sample_rate,
                )
            except Exception:
                logger.exception("Failed to initialize CartesiaTTS")
                return None

        return self._cartesia_tts

    def _get_player(self) -> CartesiaStreamPlayer:
        """Get or create the streaming audio player."""
        if self._player is None:
            self._player = CartesiaStreamPlayer(sample_rate=self._sample_rate)
        return self._player

    def _speak_cartesia(self, text: str, voice: str = "Karen", rate: int = 160) -> bool:
        """Speak via Cartesia streaming, with fallback to macOS say.

        This is the speech function injected into LiveVoiceMode.
        """
        if not text or not text.strip():
            return False

        start_time = time.time()

        # Acquire VoiceSerializer lock to prevent overlap
        try:
            from agentic_brain.voice.serializer import get_voice_serializer

            serializer = get_voice_serializer()
        except Exception:
            logger.debug("VoiceSerializer unavailable, proceeding without lock")
            serializer = None

        try:
            cartesia = self._get_cartesia()
            if cartesia is None:
                return self._speak_fallback(text, voice, rate)

            # Stream audio from Cartesia
            chunks = cartesia.synthesize_streaming(text)
            player = self._get_player()

            # Play with serializer lock if available
            if serializer is not None:
                with serializer._speech_lock:
                    success = player.play_chunks(chunks)
            else:
                success = player.play_chunks(chunks)

            if success:
                latency_ms = (time.time() - start_time) * 1000
                with self._lock:
                    self._cartesia_calls += 1
                    self._total_latency_ms += latency_ms
                logger.debug(
                    "Cartesia streaming complete: %d ms, text=%s",
                    int(latency_ms),
                    text[:50],
                )
                return True
            else:
                logger.warning("Cartesia streaming failed, using fallback")
                return self._speak_fallback(text, voice, rate)

        except Exception:
            logger.exception("Cartesia speak error, falling back to macOS say")
            return self._speak_fallback(text, voice, rate)

    def _speak_fallback(self, text: str, voice: str, rate: int) -> bool:
        """Fallback to macOS say command."""
        with self._lock:
            self._fallback_calls += 1

        try:
            from agentic_brain.voice.serializer import speak_serialized

            return speak_serialized(text, voice=voice, rate=rate)
        except Exception:
            # Ultimate fallback: direct subprocess
            try:
                result = subprocess.run(
                    ["say", "-v", voice, "-r", str(rate), text],
                    capture_output=True,
                    timeout=30,
                )
                return result.returncode == 0
            except Exception:
                logger.exception("All speech methods failed")
                return False

    # ── Public API (mirrors LiveVoiceMode) ────────────────────────────

    def start(
        self,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
    ) -> None:
        """Activate live mode."""
        self._voice = voice or self._voice
        self._rate = rate or self._rate
        self._start_time = time.time()
        self._get_live_mode().start(voice=self._voice, rate=self._rate)
        logger.info("CartesiaLiveMode started (voice=%s)", self._voice)

    def stop(self) -> None:
        """Deactivate live mode and release resources."""
        if self._live_mode is not None:
            self._live_mode.stop()
        if self._player is not None:
            self._player.close()
        logger.info(
            "CartesiaLiveMode stopped (cartesia=%d, fallback=%d)",
            self._cartesia_calls,
            self._fallback_calls,
        )

    def interrupt(self) -> None:
        """Interrupt current speech and discard buffer."""
        if self._live_mode is not None:
            self._live_mode.interrupt()
        if self._player is not None:
            self._player.stop()

    def feed(self, text: str) -> int:
        """Feed a text chunk (e.g. a single LLM token).

        Returns the number of sentences spoken.
        """
        return self._get_live_mode().feed(text)

    def flush(self) -> bool:
        """Speak whatever is left in the buffer."""
        return self._get_live_mode().flush()

    @property
    def is_active(self) -> bool:
        """Check if live mode is active."""
        return self._live_mode is not None and self._live_mode.is_active

    @property
    def is_interrupted(self) -> bool:
        """Check if live mode was interrupted."""
        return self._live_mode is not None and self._live_mode.is_interrupted

    def status(self) -> dict:
        """Get diagnostic status."""
        base = self._get_live_mode().status() if self._live_mode else {}
        with self._lock:
            avg_latency = (
                self._total_latency_ms / self._cartesia_calls
                if self._cartesia_calls > 0
                else 0
            )
        base.update(
            {
                "backend": (
                    "cartesia" if self._cartesia_tts is not None else "macOS_say"
                ),
                "cartesia_calls": self._cartesia_calls,
                "fallback_calls": self._fallback_calls,
                "avg_latency_ms": round(avg_latency, 1),
                "has_pyaudio": _HAS_PYAUDIO,
            }
        )
        return base


# ── Singleton ────────────────────────────────────────────────────────

_cartesia_live_mode: Optional[CartesiaLiveMode] = None
_cartesia_live_lock = threading.Lock()


def get_cartesia_live_mode() -> CartesiaLiveMode:
    """Return the process-wide CartesiaLiveMode singleton."""
    global _cartesia_live_mode
    if _cartesia_live_mode is None:
        with _cartesia_live_lock:
            if _cartesia_live_mode is None:
                _cartesia_live_mode = CartesiaLiveMode()
    return _cartesia_live_mode


def _set_cartesia_live_mode_for_testing(
    mode: Optional[CartesiaLiveMode],
) -> None:
    """Replace the global CartesiaLiveMode (tests only)."""
    global _cartesia_live_mode
    _cartesia_live_mode = mode


__all__ = [
    "CartesiaLiveMode",
    "CartesiaStreamPlayer",
    "get_cartesia_live_mode",
]
