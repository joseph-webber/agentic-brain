# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Transcription engines for Project Aria (Live Voice Mode).

Provides three backends:

1. **WhisperTranscriber** – uses ``whisper.cpp`` via the ``pywhispercpp``
   Python binding for local, fast, offline transcription on Apple Silicon.
2. **FasterWhisperTranscriber** – uses ``faster-whisper`` with CTranslate2
   for optimised inference with sub-500ms latency.
3. **MacOSDictationTranscriber** – falls back to macOS built-in dictation
   when Whisper is unavailable.

All engines expose the same interface so the live-mode session can swap
them transparently.

**Streaming Mode**: The streaming transcription feature provides real-time
partial results using overlapping audio windows. This enables sub-500ms
latency for live voice input with proper word boundary handling.

Accuracy tracking is built in: every transcription records confidence,
duration, and error counts for observability.
"""

from __future__ import annotations

import logging
import os
import struct
import subprocess
import tempfile
import threading
import time
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Generator, Iterable, Optional

logger = logging.getLogger(__name__)

# ── Optional heavy imports ───────────────────────────────────────────

_HAS_WHISPER_CPP = False
try:
    from pywhispercpp.model import Model as WhisperModel  # type: ignore[import-untyped]

    _HAS_WHISPER_CPP = True
except ImportError:
    WhisperModel = None  # type: ignore[assignment,misc]

_HAS_FASTER_WHISPER = False
try:
    from faster_whisper import (
        WhisperModel as FasterWhisperModel,  # type: ignore[import-untyped]
    )

    _HAS_FASTER_WHISPER = True
except ImportError:
    FasterWhisperModel = None  # type: ignore[assignment,misc]

_HAS_NUMPY = False
try:
    import numpy as np  # type: ignore[import-untyped]

    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]


# ── Shared types ─────────────────────────────────────────────────────


class TranscriptionError(Exception):
    """Base error for audio transcription operations."""


class AudioFormatError(TranscriptionError):
    """Raised when audio input cannot be decoded or validated."""


class ModelLoadError(TranscriptionError):
    """Raised when a transcription model fails to initialise."""


class TimeoutError(TranscriptionError):
    """Raised when a transcription operation exceeds its timeout."""


@dataclass
class TranscriptionResult:
    """Unified output from any transcription backend."""

    text: str
    confidence: float = 1.0
    is_final: bool = True
    language: str = "en"
    duration_ms: float = 0.0


@dataclass
class TranscriptionMetrics:
    """Accuracy and performance tracking."""

    total_requests: int = 0
    successful: int = 0
    errors: int = 0
    total_audio_ms: float = 0.0
    total_processing_ms: float = 0.0
    avg_confidence: float = 0.0
    _confidence_samples: list[float] = field(default_factory=list)

    def record(
        self: TranscriptionMetrics, result: TranscriptionResult, processing_ms: float
    ) -> None:
        self.total_requests += 1
        self.successful += 1
        self.total_audio_ms += result.duration_ms
        self.total_processing_ms += processing_ms
        self._confidence_samples.append(result.confidence)
        self.avg_confidence = sum(self._confidence_samples) / len(
            self._confidence_samples
        )

    def record_error(self: TranscriptionMetrics) -> None:
        self.total_requests += 1
        self.errors += 1

    @property
    def accuracy_rate(self: TranscriptionMetrics) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful / self.total_requests

    @property
    def realtime_factor(self: TranscriptionMetrics) -> float:
        """Processing time / audio time.  < 1.0 means faster-than-realtime."""
        if self.total_audio_ms == 0:
            return 0.0
        return self.total_processing_ms / self.total_audio_ms

    def to_dict(self: TranscriptionMetrics) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful": self.successful,
            "errors": self.errors,
            "accuracy_rate": round(self.accuracy_rate, 3),
            "avg_confidence": round(self.avg_confidence, 3),
            "realtime_factor": round(self.realtime_factor, 3),
            "total_audio_ms": round(self.total_audio_ms, 1),
            "total_processing_ms": round(self.total_processing_ms, 1),
        }


@dataclass
class StreamingConfig:
    """Configuration for streaming transcription mode."""

    window_secs: float = 2.0
    overlap_secs: float = 0.5
    sample_rate: int = 16_000
    enabled: bool = False
    min_chunk_secs: float = 0.3
    vad_threshold: float = 0.5


@dataclass
class StreamingTranscriptionResult:
    """Result from streaming transcription with partial support."""

    text: str
    is_partial: bool = True
    is_final: bool = False
    confidence: float = 1.0
    segment_index: int = 0
    timestamp_ms: float = 0.0
    stable_text: str = ""


@dataclass
class VADStreamingUpdate:
    """State update from VAD-gated streaming transcription."""

    is_speech: bool
    speech_started: bool = False
    speech_ended: bool = False
    partials: list[StreamingTranscriptionResult] = field(default_factory=list)
    final: Optional[StreamingTranscriptionResult] = None


class StreamingBuffer:
    """Manages overlapping audio windows for streaming transcription.

    Uses a sliding window approach to enable real-time transcription:
    - Accumulates audio chunks until window size is reached
    - Returns segments with overlap to avoid word boundary cuts
    - Tracks segment indices for stitching results
    """

    def __init__(
        self: StreamingBuffer,
        window_secs: float = 2.0,
        overlap_secs: float = 0.5,
        sample_rate: int = 16_000,
    ) -> None:
        self.window_samples = int(window_secs * sample_rate)
        self.overlap_samples = int(overlap_secs * sample_rate)
        self.sample_rate = sample_rate
        self._buffer: list[int] = []
        self._segment_index = 0
        self._lock = threading.Lock()

    def add_chunk(self: StreamingBuffer, chunk: bytes) -> Optional[Any]:
        """Add audio chunk and return segment if window is full.

        Args:
            chunk: Raw PCM int16 audio bytes.

        Returns:
            numpy array of float32 audio if window is ready, None otherwise.
        """
        with self._lock:
            try:
                if not chunk:
                    return None
                if len(chunk) % 2 != 0:
                    raise AudioFormatError(
                        "Streaming audio chunk must contain 16-bit aligned samples"
                    )

                if not _HAS_NUMPY:
                    n_samples = len(chunk) // 2
                    fmt = f"<{n_samples}h"
                    samples = struct.unpack(fmt, chunk)
                    self._buffer.extend(samples)
                else:
                    samples = np.frombuffer(chunk, dtype=np.int16)
                    self._buffer.extend(samples.tolist())

                if len(self._buffer) >= self.window_samples:
                    segment = self._buffer[: self.window_samples]
                    self._buffer = self._buffer[
                        self.window_samples - self.overlap_samples :
                    ]
                    self._segment_index += 1

                    if _HAS_NUMPY:
                        arr = np.array(segment, dtype=np.float32) / 32768.0
                        return arr
                    return [s / 32768.0 for s in segment]
                return None
            except (AudioFormatError, struct.error, ValueError, TypeError) as exc:
                logger.warning("StreamingBuffer: failed to add audio chunk: %s", exc)
                return None

    def flush(self: StreamingBuffer) -> Optional[Any]:
        """Flush remaining buffer as final segment."""
        with self._lock:
            try:
                if not self._buffer:
                    return None
                segment = self._buffer
                self._buffer = []
                self._segment_index += 1

                if _HAS_NUMPY:
                    arr = np.array(segment, dtype=np.float32) / 32768.0
                    return arr
                return [s / 32768.0 for s in segment]
            except (ValueError, TypeError) as exc:
                logger.warning("StreamingBuffer: failed to flush audio buffer: %s", exc)
                self._buffer = []
                return None

    @property
    def segment_index(self: StreamingBuffer) -> int:
        return self._segment_index

    @property
    def buffer_duration_ms(self: StreamingBuffer) -> float:
        return (len(self._buffer) / self.sample_rate) * 1000

    def reset(self: StreamingBuffer) -> None:
        """Clear buffer and reset segment counter."""
        with self._lock:
            self._buffer = []
            self._segment_index = 0


class StreamingStitcher:
    """Stitches streaming transcription results avoiding word cuts.

    Handles overlapping segments by:
    - Tracking stable (confirmed) text
    - Detecting word boundaries in overlaps
    - Merging partial results intelligently
    """

    def __init__(self) -> None:
        self._stable_text = ""
        self._last_partial = ""
        self._overlap_words = 3

    def add_result(
        self, result: StreamingTranscriptionResult
    ) -> StreamingTranscriptionResult:
        """Process streaming result and update stable text.

        Args:
            result: Raw transcription result from a segment.

        Returns:
            Updated result with stable_text populated.
        """
        if result.is_final:
            self._stable_text = (self._stable_text + " " + result.text).strip()
            result.stable_text = self._stable_text
            return result

        new_text = result.text.strip()
        if not new_text:
            result.stable_text = self._stable_text
            return result

        if self._last_partial:
            last_words = self._last_partial.split()[-self._overlap_words :]
            new_words = new_text.split()
            merged = self._merge_overlapping(last_words, new_words)
            if merged:
                new_text = " ".join(merged)

        self._last_partial = new_text
        result.text = new_text
        result.stable_text = self._stable_text
        return result

    def _merge_overlapping(
        self, last_words: list[str], new_words: list[str]
    ) -> Optional[list[str]]:
        """Find overlap point and merge word lists.

        Args:
            last_words: Words from previous segment.
            new_words: Words from new segment.

        Returns:
            Merged word list or None if no overlap found.
        """
        for i in range(min(len(last_words), len(new_words))):
            if last_words[-(i + 1) :] == new_words[: i + 1]:
                return new_words[i + 1 :]
        return None

    def finalize(self) -> str:
        """Finalize and return complete transcription.

        Returns:
            Complete transcribed text with all partials merged.
        """
        if self._last_partial:
            self._stable_text = (self._stable_text + " " + self._last_partial).strip()
        result = self._stable_text
        self.reset()
        return result

    def reset(self) -> None:
        """Reset stitcher state for new transcription."""
        self._stable_text = ""
        self._last_partial = ""


# ── Base class ───────────────────────────────────────────────────────


class BaseTranscriber(ABC):
    """Abstract transcription backend."""

    def __init__(self) -> None:
        self.metrics = TranscriptionMetrics()
        self._lock = threading.Lock()
        self._streaming_buffer: Optional[StreamingBuffer] = None
        self._streaming_stitcher: Optional[StreamingStitcher] = None
        self._streaming_config = StreamingConfig()

    @abstractmethod
    def transcribe_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = 16_000,
    ) -> Optional[TranscriptionResult]:
        """Transcribe raw PCM int16 audio bytes.

        Args:
            audio_data: Raw PCM audio bytes (int16 format).
            sample_rate: Audio sample rate in Hz.

        Returns:
            Transcription result or None on failure.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this backend can be used.

        Returns:
            True if backend is initialized and ready.
        """
        ...

    def load_audio(
        self,
        audio_source: bytes | bytearray | str | Path,
        sample_rate: int = 16_000,
    ) -> tuple[bytes, int]:
        """Load PCM audio from raw bytes or a WAV file path.

        Args:
            audio_source: Raw PCM bytes or path to WAV file.
            sample_rate: Target sample rate in Hz.

        Returns:
            Tuple of (audio_bytes, actual_sample_rate).

        Raises:
            AudioFormatError: If audio format is invalid.
        """
        file_handle: Any | None = None
        wav_reader: wave.Wave_read | None = None

        try:
            if isinstance(audio_source, (bytes, bytearray)):
                audio_bytes = bytes(audio_source)
                if not audio_bytes:
                    raise AudioFormatError("Audio buffer is empty")
                if len(audio_bytes) % 2 != 0:
                    raise AudioFormatError(
                        "Raw PCM audio must contain 16-bit aligned samples"
                    )
                return audio_bytes, sample_rate

            path = Path(audio_source).expanduser()
            if not path.exists():
                raise FileNotFoundError(f"Audio file not found: {path}")
            if not path.is_file():
                raise AudioFormatError(f"Audio source is not a file: {path}")
            if path.suffix.lower() != ".wav":
                raise AudioFormatError(
                    f"Unsupported audio format '{path.suffix or '<none>'}'. "
                    "Only WAV files are currently supported."
                )

            file_handle = path.open("rb")
            wav_reader = wave.open(file_handle, "rb")

            channels = wav_reader.getnchannels()
            sample_width = wav_reader.getsampwidth()
            resolved_sample_rate = wav_reader.getframerate()
            if channels != 1:
                raise AudioFormatError(
                    f"Unsupported channel count {channels}; expected mono audio"
                )
            if sample_width != 2:
                raise AudioFormatError(
                    f"Unsupported sample width {sample_width * 8} bits; expected 16-bit PCM"
                )
            if resolved_sample_rate <= 0:
                raise AudioFormatError("WAV file has invalid sample rate")

            frames = wav_reader.readframes(wav_reader.getnframes())
            if not frames:
                raise AudioFormatError("Audio file contains no PCM frames")
            if len(frames) % 2 != 0:
                raise AudioFormatError(
                    "Decoded WAV audio must contain 16-bit aligned samples"
                )
            return frames, resolved_sample_rate
        except (AudioFormatError, FileNotFoundError):
            raise
        except wave.Error as exc:
            raise AudioFormatError(f"Invalid WAV audio data: {exc}") from exc
        except OSError as exc:
            raise TranscriptionError(f"Failed to read audio source: {exc}") from exc
        finally:
            if wav_reader is not None:
                try:
                    wav_reader.close()
                except Exception:
                    logger.debug("Failed to close WAV reader", exc_info=True)
            if file_handle is not None and not file_handle.closed:
                try:
                    file_handle.close()
                except Exception:
                    logger.debug("Failed to close audio file handle", exc_info=True)

    def transcribe(
        self,
        audio_source: bytes | bytearray | str | Path,
        sample_rate: int = 16_000,
        timeout_seconds: float | None = None,
    ) -> Optional[TranscriptionResult]:
        """Load and transcribe audio with defensive error handling."""
        audio_data: bytes | None = None
        effective_sample_rate = sample_rate
        started_at = time.monotonic()

        try:
            if timeout_seconds is not None and timeout_seconds <= 0:
                raise TimeoutError("Transcription timeout must be greater than zero")

            audio_data, effective_sample_rate = self.load_audio(
                audio_source,
                sample_rate=sample_rate,
            )
            if (
                timeout_seconds is not None
                and (time.monotonic() - started_at) > timeout_seconds
            ):
                raise TimeoutError("Audio loading timed out before transcription")

            result = self.transcribe_bytes(
                audio_data, sample_rate=effective_sample_rate
            )

            if (
                timeout_seconds is not None
                and (time.monotonic() - started_at) > timeout_seconds
            ):
                raise TimeoutError("Transcription timed out")
            return result
        except FileNotFoundError as exc:
            self.metrics.record_error()
            logger.warning("%s: audio file missing: %s", self.name, exc)
            return None
        except (
            AudioFormatError,
            ModelLoadError,
            TimeoutError,
            TranscriptionError,
        ) as exc:
            self.metrics.record_error()
            logger.warning("%s: transcription failed: %s", self.name, exc)
            return None
        except Exception as exc:
            self.metrics.record_error()
            logger.exception("%s: unexpected transcription failure", self.name)
            logger.debug("Unexpected transcription error: %s", exc)
            return None
        finally:
            audio_data = None

    def stream_transcribe(
        self,
        audio_source: bytes | bytearray | str | Path | Iterable[bytes],
        sample_rate: int = 16_000,
        chunk_size: int = 32_000,
    ) -> Generator[StreamingTranscriptionResult, None, None]:
        """Transcribe audio input as a streaming sequence."""
        audio_data: bytes | None = None
        buffered_chunks: list[bytes] | None = None
        effective_sample_rate = sample_rate

        try:
            if chunk_size <= 0:
                raise AudioFormatError("Streaming chunk size must be greater than zero")

            if isinstance(audio_source, (bytes, bytearray, str, Path)):
                audio_data, effective_sample_rate = self.load_audio(
                    audio_source,
                    sample_rate=sample_rate,
                )
                buffered_chunks = [
                    audio_data[i : i + chunk_size]
                    for i in range(0, len(audio_data), chunk_size)
                ]
            else:
                buffered_chunks = []
                for chunk in audio_source:
                    if not chunk:
                        continue
                    if len(chunk) % 2 != 0:
                        raise AudioFormatError(
                            "Streaming PCM chunks must contain 16-bit aligned samples"
                        )
                    buffered_chunks.append(bytes(chunk))

            for chunk in buffered_chunks:
                yield from self.transcribe_streaming(
                    chunk,
                    sample_rate=effective_sample_rate,
                )

            final_result = self.flush_streaming()
            if final_result is not None:
                yield final_result
        except FileNotFoundError as exc:
            self.metrics.record_error()
            logger.warning("%s: streaming audio file missing: %s", self.name, exc)
        except (
            AudioFormatError,
            ModelLoadError,
            TimeoutError,
            TranscriptionError,
        ) as exc:
            self.metrics.record_error()
            logger.warning("%s: streaming transcription failed: %s", self.name, exc)
        except Exception as exc:
            self.metrics.record_error()
            logger.exception(
                "%s: unexpected streaming transcription failure", self.name
            )
            logger.debug("Unexpected streaming error: %s", exc)
        finally:
            buffered_chunks = None
            audio_data = None
            self.reset_streaming()

    def configure_streaming(
        self,
        window_secs: float = 2.0,
        overlap_secs: float = 0.5,
        sample_rate: int = 16_000,
        enabled: bool = True,
    ) -> None:
        """Configure streaming transcription mode.

        Args:
            window_secs: Audio window size in seconds (default 2.0).
            overlap_secs: Overlap between windows (default 0.5).
            sample_rate: Audio sample rate (default 16000).
            enabled: Enable streaming mode.
        """
        try:
            self._streaming_config = StreamingConfig(
                window_secs=window_secs,
                overlap_secs=overlap_secs,
                sample_rate=sample_rate,
                enabled=enabled,
            )
            if enabled:
                self._streaming_buffer = StreamingBuffer(
                    window_secs=window_secs,
                    overlap_secs=overlap_secs,
                    sample_rate=sample_rate,
                )
                self._streaming_stitcher = StreamingStitcher()
            else:
                self._streaming_buffer = None
                self._streaming_stitcher = None
        except Exception as exc:
            self._streaming_buffer = None
            self._streaming_stitcher = None
            self._streaming_config = StreamingConfig(
                sample_rate=sample_rate, enabled=False
            )
            logger.warning("%s: failed to configure streaming: %s", self.name, exc)

    def transcribe_streaming(
        self,
        audio_chunk: bytes,
        sample_rate: int = 16_000,
    ) -> Generator[StreamingTranscriptionResult, None, None]:
        """Transcribe audio incrementally with streaming support.

        Takes audio chunks and yields partial results as windows complete.
        Results include both partial (may change) and stable (confirmed) text.

        Args:
            audio_chunk: Raw PCM int16 audio bytes.
            sample_rate: Audio sample rate.

        Yields:
            StreamingTranscriptionResult with partial/stable transcription.
        """
        segment: Any | None = None
        try:
            if self._streaming_buffer is None:
                self.configure_streaming(sample_rate=sample_rate, enabled=True)
            if self._streaming_buffer is None:
                raise TranscriptionError("Streaming buffer is unavailable")

            segment = self._streaming_buffer.add_chunk(audio_chunk)
            if segment is not None:
                result = self._transcribe_segment(
                    segment,
                    sample_rate,
                    self._streaming_buffer.segment_index,
                )
                if result and self._streaming_stitcher:
                    yield self._streaming_stitcher.add_result(result)
        except (
            AudioFormatError,
            ModelLoadError,
            TimeoutError,
            TranscriptionError,
        ) as exc:
            self.metrics.record_error()
            logger.warning("%s: streaming chunk failed: %s", self.name, exc)
        except Exception as exc:
            self.metrics.record_error()
            logger.exception("%s: unexpected streaming chunk failure", self.name)
            logger.debug("Unexpected streaming chunk error: %s", exc)
        finally:
            segment = None

    def _transcribe_segment(
        self,
        audio_float: Any,
        sample_rate: int,
        segment_index: int,
    ) -> Optional[StreamingTranscriptionResult]:
        """Transcribe a single audio segment (internal).

        Subclasses can override for optimised streaming transcription.
        """
        audio_bytes: bytes | None = None
        try:
            if _HAS_NUMPY:
                audio_bytes = (np.array(audio_float) * 32768).astype(np.int16).tobytes()
            else:
                samples = [int(s * 32768) for s in audio_float]
                audio_bytes = struct.pack(f"<{len(samples)}h", *samples)

            result = self.transcribe_bytes(audio_bytes, sample_rate)
            if result:
                return StreamingTranscriptionResult(
                    text=result.text,
                    is_partial=True,
                    is_final=False,
                    confidence=result.confidence,
                    segment_index=segment_index,
                    timestamp_ms=time.monotonic() * 1000,
                )
            return None
        except struct.error as exc:
            logger.warning("%s: failed to pack streaming audio: %s", self.name, exc)
            return None
        except Exception as exc:
            logger.warning(
                "%s: failed to transcribe streaming segment: %s", self.name, exc
            )
            return None
        finally:
            audio_bytes = None

    def flush_streaming(self) -> Optional[StreamingTranscriptionResult]:
        """Flush remaining audio and finalize transcription.

        Returns:
            Final transcription result with complete stable text.
        """
        segment: Any | None = None
        result: Optional[StreamingTranscriptionResult] = None
        try:
            if self._streaming_buffer is None:
                return None

            segment = self._streaming_buffer.flush()
            if segment is not None:
                result = self._transcribe_segment(
                    segment,
                    self._streaming_config.sample_rate,
                    self._streaming_buffer.segment_index,
                )

            if self._streaming_stitcher:
                final_text = self._streaming_stitcher.finalize()
                if result:
                    result.is_final = True
                    result.is_partial = False
                    result.stable_text = final_text
                elif final_text:
                    result = StreamingTranscriptionResult(
                        text=final_text,
                        is_partial=False,
                        is_final=True,
                        stable_text=final_text,
                        segment_index=self._streaming_buffer.segment_index,
                    )

            return result
        except Exception as exc:
            self.metrics.record_error()
            logger.warning("%s: failed to flush streaming state: %s", self.name, exc)
            return None
        finally:
            segment = None
            self.reset_streaming()

    def reset_streaming(self) -> None:
        """Reset streaming state for a new transcription session."""
        if self._streaming_buffer:
            self._streaming_buffer.reset()
        if self._streaming_stitcher:
            self._streaming_stitcher.reset()

    @property
    def streaming_enabled(self) -> bool:
        return self._streaming_config.enabled

    @property
    def name(self) -> str:
        return self.__class__.__name__


class VADStreamingTranscriber:
    """Wire Silero VAD speech boundaries to streaming transcription.

    This coordinator keeps a rolling VAD window so speech start/end can be
    detected from microphone-sized chunks, then gates faster-whisper streaming
    so we only transcribe active utterances.  When speech starts, the recent
    pre-roll audio is sent into the streaming transcriber immediately.  When
    speech ends, the transcriber is flushed to emit a final transcript.
    """

    def __init__(
        self,
        transcriber: Optional[BaseTranscriber] = None,
        vad: Optional[Any] = None,
        *,
        model_name: str = "tiny.en",
        sample_rate: int = 16_000,
        window_secs: float = 0.5,
        overlap_secs: float = 0.1,
        vad_threshold: float = 0.5,
        min_speech_duration_ms: int = 100,
        min_silence_duration_ms: int = 100,
        vad_window_ms: Optional[int] = None,
    ) -> None:
        from agentic_brain.voice.vad import SileroVAD, VADConfig

        self.sample_rate = sample_rate
        self._transcriber = transcriber or get_streaming_transcriber(
            model_name=model_name,
            window_secs=window_secs,
            overlap_secs=overlap_secs,
            prefer_faster_whisper=True,
        )
        self._transcriber.configure_streaming(
            window_secs=window_secs,
            overlap_secs=overlap_secs,
            sample_rate=sample_rate,
            enabled=True,
        )

        vad_config = VADConfig(
            threshold=vad_threshold,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
            sample_rate=sample_rate,
        )
        self._vad = vad or SileroVAD(config=vad_config)
        self._speech_active = False
        self._silence_samples = 0
        self._utterance_chunks: list[bytes] = []
        self._min_detection_samples = max(
            vad_config.window_size_samples,
            int(sample_rate * min_speech_duration_ms / 1000),
        )
        default_vad_window_ms = max(
            int(window_secs * 1000),
            min_speech_duration_ms + min_silence_duration_ms,
        )
        self._vad_window_samples = max(
            self._min_detection_samples,
            int(sample_rate * (vad_window_ms or default_vad_window_ms) / 1000),
        )
        self._vad_window: list[int] = []

    @property
    def speech_active(self) -> bool:
        """Return True when an utterance is currently being streamed."""
        return self._speech_active

    def process_chunk(self, audio_chunk: bytes) -> VADStreamingUpdate:
        """Process one PCM chunk and emit VAD/transcription updates."""
        samples: list[int] = []
        update = VADStreamingUpdate(is_speech=self._speech_active)
        try:
            samples = self._chunk_to_samples(audio_chunk)
            if not samples:
                return update

            self._append_vad_samples(samples)
            is_speech_now = self._detect_speech()
            update.is_speech = self._speech_active or is_speech_now

            if is_speech_now:
                self._silence_samples = 0
                if not self._speech_active:
                    self._speech_active = True
                    update.speech_started = True
                    self._transcriber.reset_streaming()
                    seed_audio = self._samples_to_bytes(self._vad_window)
                    self._utterance_chunks = [seed_audio] if seed_audio else []
                    if seed_audio:
                        update.partials.extend(
                            self._transcriber.transcribe_streaming(
                                seed_audio,
                                sample_rate=self.sample_rate,
                            )
                        )
                    return update

            if not self._speech_active:
                return update

            if not update.speech_started:
                self._utterance_chunks.append(audio_chunk)
                update.partials.extend(
                    self._transcriber.transcribe_streaming(
                        audio_chunk,
                        sample_rate=self.sample_rate,
                    )
                )

            if is_speech_now:
                return update

            self._silence_samples += len(samples)
            if self._silence_samples >= self._speech_end_samples:
                update.speech_ended = True
                update.final = self._build_final_result()
                self.reset()
                update.is_speech = False

            return update
        except (AudioFormatError, TranscriptionError) as exc:
            logger.warning("VADStreamingTranscriber: failed to process chunk: %s", exc)
            self.reset()
            return update
        except Exception as exc:
            logger.warning(
                "VADStreamingTranscriber: unexpected chunk processing failure: %s",
                exc,
            )
            self.reset()
            return update
        finally:
            samples = []

    def finalize(self) -> Optional[StreamingTranscriptionResult]:
        """Force completion of the current utterance."""
        try:
            if not self._speech_active:
                return None
            return self._build_final_result()
        except Exception as exc:
            logger.warning("VADStreamingTranscriber: finalize failed: %s", exc)
            return None
        finally:
            self.reset()

    def reset(self) -> None:
        """Reset VAD and streaming state for a new utterance."""
        try:
            self._speech_active = False
            self._silence_samples = 0
            self._vad_window = []
            self._utterance_chunks = []
            self._transcriber.reset_streaming()
        except Exception as exc:
            logger.warning("VADStreamingTranscriber: reset failed: %s", exc)

    @property
    def _speech_end_samples(self) -> int:
        return int(self.sample_rate * self._vad.config.min_silence_duration_ms / 1000)

    def _detect_speech(self) -> bool:
        try:
            if not _HAS_NUMPY or len(self._vad_window) < self._min_detection_samples:
                return False
            audio = self._samples_to_ndarray(self._vad_window)
            if audio is None:
                return False
            return any(True for _ in self._vad.detect_speech(audio))
        except Exception as exc:
            logger.warning("VADStreamingTranscriber: VAD detection failed: %s", exc)
            return False

    def _append_vad_samples(self, samples: list[int]) -> None:
        self._vad_window.extend(samples)
        if len(self._vad_window) > self._vad_window_samples:
            self._vad_window = self._vad_window[-self._vad_window_samples :]

    def _build_final_result(self) -> Optional[StreamingTranscriptionResult]:
        audio_data: bytes | None = None
        try:
            audio_data = b"".join(self._utterance_chunks)
            if not audio_data:
                return None
            result = self._transcriber.transcribe_bytes(
                audio_data,
                sample_rate=self.sample_rate,
            )
            if not result or not result.text.strip():
                return None
            return StreamingTranscriptionResult(
                text=result.text.strip(),
                is_partial=False,
                is_final=True,
                confidence=result.confidence,
                stable_text=result.text.strip(),
                timestamp_ms=time.monotonic() * 1000,
            )
        except Exception as exc:
            logger.warning(
                "VADStreamingTranscriber: final transcription failed: %s", exc
            )
            return None
        finally:
            audio_data = None

    def _chunk_to_samples(self, audio_chunk: bytes) -> list[int]:
        try:
            if not audio_chunk:
                return []
            if len(audio_chunk) % 2 != 0:
                raise AudioFormatError(
                    "VAD audio chunk must contain 16-bit aligned samples"
                )
            if _HAS_NUMPY:
                return np.frombuffer(audio_chunk, dtype=np.int16).tolist()
            n_samples = len(audio_chunk) // 2
            if n_samples <= 0:
                return []
            return list(struct.unpack(f"<{n_samples}h", audio_chunk))
        except (AudioFormatError, struct.error, ValueError, TypeError) as exc:
            logger.warning("VADStreamingTranscriber: invalid PCM chunk: %s", exc)
            return []

    def _samples_to_bytes(self, samples: list[int]) -> bytes:
        try:
            if not samples:
                return b""
            if _HAS_NUMPY:
                return np.array(samples, dtype=np.int16).tobytes()
            return struct.pack(f"<{len(samples)}h", *samples)
        except (struct.error, ValueError, TypeError) as exc:
            logger.warning("VADStreamingTranscriber: failed to pack samples: %s", exc)
            return b""

    def _samples_to_ndarray(self, samples: list[int]) -> Any:
        try:
            return np.array(samples, dtype=np.int16)
        except Exception as exc:
            logger.warning("VADStreamingTranscriber: failed to build ndarray: %s", exc)
            return None


# ── Whisper.cpp Transcriber ──────────────────────────────────────────


class WhisperTranscriber(BaseTranscriber):
    """Local transcription via whisper.cpp (pywhispercpp).

    Runs fully offline on Apple Silicon with excellent accuracy.
    Models are auto-downloaded to ``~/.cache/whisper/`` on first use.

    Supported models: tiny, tiny.en, base, base.en, small, small.en,
    medium, medium.en, large-v2, large-v3.
    """

    # Default model directory
    DEFAULT_MODEL_DIR = os.path.expanduser("~/.cache/whisper")

    def __init__(
        self,
        model_name: str = "base.en",
        model_dir: Optional[str] = None,
        n_threads: int = 4,
    ) -> None:
        super().__init__()
        self._model_name = model_name
        self._model_dir = model_dir or self.DEFAULT_MODEL_DIR
        self._n_threads = n_threads
        self._model: Any = None
        self._init_error: Optional[str] = None
        self._initialised = False

    def _ensure_model(self) -> bool:
        """Lazily load the Whisper model."""
        if self._initialised:
            return self._model is not None
        self._initialised = True

        if not _HAS_WHISPER_CPP:
            self._init_error = "pywhispercpp not installed"
            logger.info(
                "WhisperTranscriber: pywhispercpp not available. "
                "Install with: pip install pywhispercpp"
            )
            return False

        try:
            os.makedirs(self._model_dir, exist_ok=True)
            self._model = WhisperModel(
                self._model_name,
                models_dir=self._model_dir,
                n_threads=self._n_threads,
            )
            logger.info(
                "WhisperTranscriber: loaded model '%s' (%d threads)",
                self._model_name,
                self._n_threads,
            )
            return True
        except Exception as exc:
            model_error = ModelLoadError(
                f"Failed to load whisper.cpp model '{self._model_name}': {exc}"
            )
            self._init_error = str(model_error)
            logger.warning("WhisperTranscriber: model load failed: %s", model_error)
            return False

    def is_available(self) -> bool:
        return _HAS_WHISPER_CPP

    def transcribe_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = 16_000,
    ) -> Optional[TranscriptionResult]:
        """Transcribe raw PCM int16 audio."""
        audio_float: Any = None
        segments: Any = None
        with self._lock:
            if not self._ensure_model():
                self.metrics.record_error()
                return None

            t0 = time.monotonic()
            try:
                audio_float = _pcm_to_float32(audio_data)
                if audio_float is None or len(audio_float) == 0:
                    self.metrics.record_error()
                    return None

                duration_ms = (len(audio_float) / sample_rate) * 1000

                segments = self._model.transcribe(audio_float)
                text = " ".join(
                    seg.text.strip() for seg in segments if seg.text.strip()
                )

                if not text:
                    return None

                processing_ms = (time.monotonic() - t0) * 1000
                result = TranscriptionResult(
                    text=text,
                    confidence=0.9,  # whisper.cpp doesn't expose per-segment confidence
                    is_final=True,
                    language="en",
                    duration_ms=duration_ms,
                )
                self.metrics.record(result, processing_ms)
                return result

            except (
                AudioFormatError,
                ModelLoadError,
                TimeoutError,
                TranscriptionError,
            ) as exc:
                self.metrics.record_error()
                logger.warning("WhisperTranscriber: transcription error: %s", exc)
                return None
            except Exception as exc:
                self.metrics.record_error()
                logger.warning("WhisperTranscriber: transcription error: %s", exc)
                return None
            finally:
                segments = None
                audio_float = None


# ── Faster-Whisper Transcriber (CTranslate2) ─────────────────────────


class FasterWhisperTranscriber(BaseTranscriber):
    """High-performance transcription via faster-whisper (CTranslate2).

    Optimised for sub-500ms latency with:
    - CTranslate2 int8 quantisation
    - Batched inference
    - VAD-based segmentation
    - Apple Silicon MPS support (when available)

    Install: pip install faster-whisper

    Models: tiny, tiny.en, base, base.en, small, small.en,
    medium, medium.en, large-v2, large-v3, distil-large-v3
    """

    # Default cache directory
    DEFAULT_MODEL_DIR = os.path.expanduser("~/.cache/huggingface/hub")

    def __init__(
        self,
        model_name: str = "base.en",
        model_dir: Optional[str] = None,
        device: str = "auto",
        compute_type: str = "int8",
        num_workers: int = 4,
        vad_filter: bool = True,
    ) -> None:
        super().__init__()
        self._model_name = model_name
        self._model_dir = model_dir or self.DEFAULT_MODEL_DIR
        self._device = device
        self._compute_type = compute_type
        self._num_workers = num_workers
        self._vad_filter = vad_filter
        self._model: Any = None
        self._init_error: Optional[str] = None
        self._initialised = False

    def _ensure_model(self) -> bool:
        """Lazily load the faster-whisper model."""
        if self._initialised:
            return self._model is not None
        self._initialised = True

        if not _HAS_FASTER_WHISPER:
            self._init_error = "faster-whisper not installed"
            logger.info(
                "FasterWhisperTranscriber: faster-whisper not available. "
                "Install with: pip install faster-whisper"
            )
            return False

        try:
            device = self._device
            if device == "auto":
                # Check for MPS (Apple Silicon) or CUDA
                if _HAS_NUMPY:
                    try:
                        import torch

                        if torch.backends.mps.is_available():
                            device = "cpu"  # faster-whisper uses CPU but CTranslate2 is optimised
                        elif torch.cuda.is_available():
                            device = "cuda"
                        else:
                            device = "cpu"
                    except ImportError:
                        device = "cpu"
                else:
                    device = "cpu"

            self._model = FasterWhisperModel(
                self._model_name,
                device=device,
                compute_type=self._compute_type,
                num_workers=self._num_workers,
                download_root=self._model_dir,
            )
            logger.info(
                "FasterWhisperTranscriber: loaded model '%s' (device=%s, compute=%s)",
                self._model_name,
                device,
                self._compute_type,
            )
            return True
        except Exception as exc:
            model_error = ModelLoadError(
                f"Failed to load faster-whisper model '{self._model_name}': {exc}"
            )
            self._init_error = str(model_error)
            logger.warning(
                "FasterWhisperTranscriber: model load failed: %s",
                model_error,
            )
            return False

    def is_available(self) -> bool:
        return _HAS_FASTER_WHISPER

    def transcribe_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = 16_000,
    ) -> Optional[TranscriptionResult]:
        """Transcribe raw PCM int16 audio with faster-whisper."""
        audio_float: Any = None
        segments: Any = None
        info: Any = None
        with self._lock:
            if not self._ensure_model():
                self.metrics.record_error()
                return None

            t0 = time.monotonic()
            try:
                audio_float = _pcm_to_float32(audio_data)
                if audio_float is None or len(audio_float) == 0:
                    self.metrics.record_error()
                    return None

                duration_ms = (len(audio_float) / sample_rate) * 1000

                segments, info = self._model.transcribe(
                    audio_float,
                    beam_size=5,
                    vad_filter=self._vad_filter,
                    vad_parameters={
                        "min_silence_duration_ms": 300,
                        "speech_pad_ms": 200,
                    },
                )

                text_parts = []
                confidences = []
                for segment in segments:
                    if segment.text.strip():
                        text_parts.append(segment.text.strip())
                        # faster-whisper provides avg_logprob
                        conf = min(1.0, max(0.0, 1.0 + segment.avg_logprob / 5))
                        confidences.append(conf)

                text = " ".join(text_parts)
                if not text:
                    return None

                avg_confidence = (
                    sum(confidences) / len(confidences) if confidences else 0.9
                )

                processing_ms = (time.monotonic() - t0) * 1000
                result = TranscriptionResult(
                    text=text,
                    confidence=avg_confidence,
                    is_final=True,
                    language=info.language if hasattr(info, "language") else "en",
                    duration_ms=duration_ms,
                )
                self.metrics.record(result, processing_ms)
                return result

            except (
                AudioFormatError,
                ModelLoadError,
                TimeoutError,
                TranscriptionError,
            ) as exc:
                self.metrics.record_error()
                logger.warning("FasterWhisperTranscriber: transcription error: %s", exc)
                return None
            except Exception as exc:
                self.metrics.record_error()
                logger.warning("FasterWhisperTranscriber: transcription error: %s", exc)
                return None
            finally:
                info = None
                segments = None
                audio_float = None

    def _transcribe_segment(
        self,
        audio_float: Any,
        sample_rate: int,
        segment_index: int,
    ) -> Optional[StreamingTranscriptionResult]:
        """Optimised streaming segment transcription.

        faster-whisper is particularly good at short segments due to
        efficient VAD and batched processing.
        """
        with self._lock:
            if not self._ensure_model():
                return None

            t0 = time.monotonic()
            segments: Any = None
            info: Any = None
            try:
                segments, info = self._model.transcribe(
                    audio_float,
                    beam_size=3,  # Reduced for speed
                    best_of=1,
                    vad_filter=self._vad_filter,
                )

                text_parts = []
                confidences = []
                for segment in segments:
                    if segment.text.strip():
                        text_parts.append(segment.text.strip())
                        conf = min(1.0, max(0.0, 1.0 + segment.avg_logprob / 5))
                        confidences.append(conf)

                text = " ".join(text_parts)
                if not text:
                    return None

                avg_confidence = (
                    sum(confidences) / len(confidences) if confidences else 0.9
                )
                processing_ms = (time.monotonic() - t0) * 1000

                logger.debug(
                    "FasterWhisper segment %d: '%s' (%.0fms)",
                    segment_index,
                    text[:50],
                    processing_ms,
                )

                return StreamingTranscriptionResult(
                    text=text,
                    is_partial=True,
                    is_final=False,
                    confidence=avg_confidence,
                    segment_index=segment_index,
                    timestamp_ms=time.monotonic() * 1000,
                )

            except (
                AudioFormatError,
                ModelLoadError,
                TimeoutError,
                TranscriptionError,
            ) as exc:
                logger.warning("FasterWhisperTranscriber: segment error: %s", exc)
                return None
            except Exception as exc:
                logger.warning("FasterWhisperTranscriber: segment error: %s", exc)
                return None
            finally:
                segments = None


# ── macOS Dictation fallback ─────────────────────────────────────────


class MacOSDictationTranscriber(BaseTranscriber):
    """Fallback transcriber using macOS ``say``-adjacent APIs.

    Uses the macOS ``/usr/bin/say`` reverse trick: writes audio to a
    temporary WAV file and attempts to use ``SFSpeechRecognizer`` via
    a helper script, or falls back to returning empty (dictation must
    be enabled in System Preferences).

    This is a *best-effort* fallback when whisper.cpp is unavailable.
    """

    def is_available(self) -> bool:
        return os.uname().sysname == "Darwin"

    def transcribe_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = 16_000,
    ) -> Optional[TranscriptionResult]:
        """Transcribe via macOS speech framework."""
        wav_path: Optional[str] = None
        with self._lock:
            t0 = time.monotonic()
            try:
                wav_path = self._write_wav(audio_data, sample_rate)
                text = self._recognise_with_sf(wav_path)

                if not text:
                    return None

                duration_ms = (len(audio_data) / (sample_rate * 2)) * 1000
                processing_ms = (time.monotonic() - t0) * 1000

                result = TranscriptionResult(
                    text=text,
                    confidence=0.8,
                    is_final=True,
                    language="en",
                    duration_ms=duration_ms,
                )
                self.metrics.record(result, processing_ms)
                return result

            except (AudioFormatError, TimeoutError, TranscriptionError) as exc:
                self.metrics.record_error()
                logger.warning("MacOSDictation: error: %s", exc)
                return None
            except Exception as exc:
                self.metrics.record_error()
                logger.warning("MacOSDictation: error: %s", exc)
                return None
            finally:
                if wav_path and os.path.exists(wav_path):
                    try:
                        os.unlink(wav_path)
                    except OSError:
                        logger.debug(
                            "MacOSDictation: failed to remove temp WAV", exc_info=True
                        )
                wav_path = None

    def _write_wav(self, audio_data: bytes, sample_rate: int) -> Optional[str]:
        """Write PCM data to a temporary WAV file."""
        try:
            if not audio_data:
                raise AudioFormatError("Cannot write empty audio buffer to WAV")
            if len(audio_data) % 2 != 0:
                raise AudioFormatError("PCM audio must contain 16-bit aligned samples")
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            return path
        except AudioFormatError:
            raise
        except Exception as exc:
            raise TranscriptionError(
                f"MacOSDictation: WAV write failed: {exc}"
            ) from exc

    def _recognise_with_sf(self, wav_path: Optional[str]) -> Optional[str]:
        """Attempt speech recognition via macOS SFSpeechRecognizer.

        Uses a short Swift snippet executed via ``swift``.  If the Speech
        framework is not available we return None gracefully.
        """
        if not wav_path or not os.path.exists(wav_path):
            return None

        # Swift helper that uses SFSpeechRecognizer
        swift_code = f"""
import Foundation
import Speech

let semaphore = DispatchSemaphore(value: 0)
var resultText = ""

SFSpeechRecognizer.requestAuthorization {{ status in
    guard status == .authorized else {{
        semaphore.signal()
        return
    }}

    let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))!
    let url = URL(fileURLWithPath: "{wav_path}")
    let request = SFSpeechURLRecognitionRequest(url: url)
    request.shouldReportPartialResults = false

    recognizer.recognitionTask(with: request) {{ result, error in
        if let result = result, result.isFinal {{
            resultText = result.bestTranscription.formattedString
        }}
        semaphore.signal()
    }}
}}

_ = semaphore.wait(timeout: .now() + 10)
print(resultText)
"""
        try:
            result = subprocess.run(
                ["swift", "-"],
                input=swift_code,
                capture_output=True,
                text=True,
                timeout=15,
            )
            text = result.stdout.strip()
            return text if text else None
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("macOS speech recognition timed out") from exc
        except FileNotFoundError as exc:
            raise TranscriptionError(
                "Swift runtime not available for dictation"
            ) from exc
        except Exception as exc:
            raise TranscriptionError(
                f"MacOSDictation: Swift recognition failed: {exc}"
            ) from exc


# ── RealtimeSTT Transcriber (optional backend) ───────────────────────────


class RealtimeSTTTranscriber:
    """RealtimeSTT-based transcriber for low-latency streaming.

    Wraps the third-party ``realtimestt`` package and exposes a simple
    callback-based streaming API. This lets the library handle voice
    activity detection and wake word logic directly.
    """

    def __init__(self, **recorder_kwargs: Any) -> None:
        self._recorder: Any | None = None
        self._recorder_kwargs = recorder_kwargs

    def _ensure_recorder(self) -> bool:
        """Lazily construct the underlying ``AudioToTextRecorder``."""
        if self._recorder is not None:
            return True
        try:
            from RealtimeSTT import (  # type: ignore[import-untyped]
                AudioToTextRecorder,
            )

            self._recorder = AudioToTextRecorder(**self._recorder_kwargs)
            return True
        except ImportError:
            logger.warning(
                "RealtimeSTTTranscriber: RealtimeSTT not installed. "
                "Install with: pip install realtimestt",
            )
        except TimeoutError as exc:  # pragma: no cover - defensive
            logger.warning("RealtimeSTTTranscriber: init timed out: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("RealtimeSTTTranscriber: init failed: %s", exc)
        return False

    def transcribe_stream(self, callback: Callable[[str], None]) -> None:
        """Start streaming transcription.

        The callback will be invoked for each recognised utterance.
        """
        if not self._ensure_recorder():
            return
        try:
            # RealtimeSTT handles microphone capture and VAD internally.
            self._recorder.text(callback)
        except TimeoutError as exc:  # pragma: no cover - defensive
            logger.warning("RealtimeSTTTranscriber: streaming timeout: %s", exc)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.warning("RealtimeSTTTranscriber: streaming error: %s", exc)

    def stop(self) -> None:
        """Stop streaming and release underlying resources, if any."""
        if self._recorder is None:
            return
        try:
            stop = getattr(self._recorder, "stop", None)
            if callable(stop):
                stop()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass


# ── Audio conversion helpers ─────────────────────────────────────────


def _pcm_to_float32(audio_data: bytes) -> Any:
    """Convert raw PCM int16 bytes to float32 numpy array (or list).

    Whisper expects float32 audio normalised to [-1, 1].
    """
    try:
        if not audio_data:
            return np.array([], dtype=np.float32) if _HAS_NUMPY else []
        if len(audio_data) % 2 != 0:
            raise AudioFormatError("PCM audio must contain 16-bit aligned samples")

        if _HAS_NUMPY:
            arr = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            return arr / 32768.0

        # Pure-Python fallback (slower but works without numpy)
        n_samples = len(audio_data) // 2
        fmt = f"<{n_samples}h"
        samples = struct.unpack(fmt, audio_data)
        return [s / 32768.0 for s in samples]
    except AudioFormatError:
        raise
    except (struct.error, ValueError, TypeError) as exc:
        raise AudioFormatError(f"Invalid PCM audio data: {exc}") from exc


# ── Factory ──────────────────────────────────────────────────────────


def get_transcriber(
    use_whisper: bool = True,
    model_name: str = "base.en",
    model_dir: Optional[str] = None,
    prefer_faster_whisper: bool = True,
    backend: Optional[str] = None,
    streaming: bool = False,
    streaming_window_secs: float = 2.0,
    streaming_overlap_secs: float = 0.5,
) -> BaseTranscriber | RealtimeSTTTranscriber:
    """Create the best available transcriber.

    Preference order:
      1. FasterWhisperTranscriber (CTranslate2, sub-500ms latency)
      2. WhisperTranscriber (whisper.cpp, local, fast, offline)
      3. MacOSDictationTranscriber (macOS only)

    Args:
        use_whisper: Prefer Whisper backends if available.
        model_name: Whisper model to load.
        model_dir: Override model cache directory.
        prefer_faster_whisper: Use faster-whisper over whisper.cpp if available.
        streaming: Enable streaming transcription mode.
        streaming_window_secs: Audio window size for streaming.
        streaming_overlap_secs: Overlap between streaming windows.

    Returns:
        A :class:`BaseTranscriber` instance.
    """
    transcriber: Optional[BaseTranscriber] = None

    if backend == "realtimestt":
        try:
            from RealtimeSTT import AudioToTextRecorder  # type: ignore[import-untyped]

            _ = AudioToTextRecorder  # Only to verify import
        except ImportError:
            logger.warning(
                "RealtimeSTT backend requested but 'realtimestt' is not installed; "
                "falling back to Whisper/MacOS backends.",
            )
        else:
            logger.info("Using RealtimeSTTTranscriber backend")
            return RealtimeSTTTranscriber()

    if use_whisper and prefer_faster_whisper and _HAS_FASTER_WHISPER:
        logger.info("Using FasterWhisperTranscriber (model=%s)", model_name)
        transcriber = FasterWhisperTranscriber(
            model_name=model_name, model_dir=model_dir
        )
    elif use_whisper and _HAS_WHISPER_CPP:
        logger.info("Using WhisperTranscriber (model=%s)", model_name)
        transcriber = WhisperTranscriber(model_name=model_name, model_dir=model_dir)
    elif os.uname().sysname == "Darwin":
        logger.info("Using MacOSDictationTranscriber (fallback)")
        transcriber = MacOSDictationTranscriber()
    else:
        # Last resort: return whisper transcriber anyway (it'll report unavailable)
        logger.warning("No transcription backend available")
        transcriber = WhisperTranscriber(model_name=model_name, model_dir=model_dir)

    if streaming and transcriber:
        transcriber.configure_streaming(
            window_secs=streaming_window_secs,
            overlap_secs=streaming_overlap_secs,
            enabled=True,
        )
        logger.info(
            "Streaming mode enabled (window=%.1fs, overlap=%.1fs)",
            streaming_window_secs,
            streaming_overlap_secs,
        )

    return transcriber


def get_streaming_transcriber(
    model_name: str = "tiny.en",
    window_secs: float = 0.5,
    overlap_secs: float = 0.1,
    prefer_faster_whisper: bool = True,
) -> BaseTranscriber:
    """Create a transcriber optimised for low-latency streaming.

    Convenience wrapper around :func:`get_transcriber` with streaming enabled
    and optimal settings for real-time voice input.

    Args:
        model_name: Whisper model to load (smaller = faster).
        window_secs: Audio window size in seconds. Defaults to 500ms.
        overlap_secs: Overlap between windows to avoid word cuts. Defaults to 100ms.
        prefer_faster_whisper: Use faster-whisper for best latency.

    Returns:
        A streaming-enabled :class:`BaseTranscriber` instance.
    """
    return get_transcriber(
        use_whisper=True,
        model_name=model_name,
        prefer_faster_whisper=prefer_faster_whisper,
        streaming=True,
        streaming_window_secs=window_secs,
        streaming_overlap_secs=overlap_secs,
    )


def get_vad_streaming_transcriber(
    model_name: str = "tiny.en",
    sample_rate: int = 16_000,
    window_secs: float = 0.5,
    overlap_secs: float = 0.1,
    vad_threshold: float = 0.5,
    min_speech_duration_ms: int = 100,
    min_silence_duration_ms: int = 100,
) -> VADStreamingTranscriber:
    """Create a Silero-VAD-gated streaming transcriber."""
    return VADStreamingTranscriber(
        model_name=model_name,
        sample_rate=sample_rate,
        window_secs=window_secs,
        overlap_secs=overlap_secs,
        vad_threshold=vad_threshold,
        min_speech_duration_ms=min_speech_duration_ms,
        min_silence_duration_ms=min_silence_duration_ms,
    )


def whisper_available() -> bool:
    """Quick check if whisper.cpp is importable."""
    return _HAS_WHISPER_CPP


def faster_whisper_available() -> bool:
    """Quick check if faster-whisper is importable."""
    return _HAS_FASTER_WHISPER
