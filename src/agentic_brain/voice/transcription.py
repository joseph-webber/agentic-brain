# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Transcription engines for Project Aria (Live Voice Mode).

Provides two backends:

1. **WhisperTranscriber** – uses ``whisper.cpp`` via the ``pywhispercpp``
   Python binding for local, fast, offline transcription on Apple Silicon.
2. **MacOSDictationTranscriber** – falls back to macOS built-in dictation
   when Whisper is unavailable.

Both engines expose the same interface so the live-mode session can swap
them transparently.

Accuracy tracking is built in: every transcription records confidence,
duration, and error counts for observability.
"""

from __future__ import annotations

import io
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
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Optional heavy imports ───────────────────────────────────────────

_HAS_WHISPER_CPP = False
try:
    from pywhispercpp.model import Model as WhisperModel  # type: ignore[import-untyped]

    _HAS_WHISPER_CPP = True
except ImportError:
    WhisperModel = None  # type: ignore[assignment,misc]

_HAS_NUMPY = False
try:
    import numpy as np  # type: ignore[import-untyped]

    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]


# ── Shared types ─────────────────────────────────────────────────────


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

    def record(self, result: TranscriptionResult, processing_ms: float) -> None:
        self.total_requests += 1
        self.successful += 1
        self.total_audio_ms += result.duration_ms
        self.total_processing_ms += processing_ms
        self._confidence_samples.append(result.confidence)
        self.avg_confidence = sum(self._confidence_samples) / len(
            self._confidence_samples
        )

    def record_error(self) -> None:
        self.total_requests += 1
        self.errors += 1

    @property
    def accuracy_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful / self.total_requests

    @property
    def realtime_factor(self) -> float:
        """Processing time / audio time.  < 1.0 means faster-than-realtime."""
        if self.total_audio_ms == 0:
            return 0.0
        return self.total_processing_ms / self.total_audio_ms

    def to_dict(self) -> dict[str, Any]:
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


# ── Base class ───────────────────────────────────────────────────────


class BaseTranscriber(ABC):
    """Abstract transcription backend."""

    def __init__(self) -> None:
        self.metrics = TranscriptionMetrics()
        self._lock = threading.Lock()

    @abstractmethod
    def transcribe_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = 16_000,
    ) -> Optional[TranscriptionResult]:
        """Transcribe raw PCM int16 audio bytes."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this backend can be used."""
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


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
            self._init_error = str(exc)
            logger.warning("WhisperTranscriber: model load failed: %s", exc)
            return False

    def is_available(self) -> bool:
        return _HAS_WHISPER_CPP

    def transcribe_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = 16_000,
    ) -> Optional[TranscriptionResult]:
        """Transcribe raw PCM int16 audio."""
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

            except Exception as exc:
                self.metrics.record_error()
                logger.warning("WhisperTranscriber: transcription error: %s", exc)
                return None


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
        with self._lock:
            t0 = time.monotonic()
            try:
                wav_path = self._write_wav(audio_data, sample_rate)
                text = self._recognise_with_sf(wav_path)
                if wav_path and os.path.exists(wav_path):
                    os.unlink(wav_path)

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

            except Exception as exc:
                self.metrics.record_error()
                logger.warning("MacOSDictation: error: %s", exc)
                return None

    def _write_wav(self, audio_data: bytes, sample_rate: int) -> Optional[str]:
        """Write PCM data to a temporary WAV file."""
        try:
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            return path
        except Exception as exc:
            logger.warning("MacOSDictation: WAV write failed: %s", exc)
            return None

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
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        except Exception as exc:
            logger.debug("MacOSDictation: Swift recognition failed: %s", exc)
            return None


# ── Audio conversion helpers ─────────────────────────────────────────


def _pcm_to_float32(audio_data: bytes) -> Any:
    """Convert raw PCM int16 bytes to float32 numpy array (or list).

    Whisper expects float32 audio normalised to [-1, 1].
    """
    if _HAS_NUMPY:
        arr = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        return arr / 32768.0

    # Pure-Python fallback (slower but works without numpy)
    n_samples = len(audio_data) // 2
    fmt = f"<{n_samples}h"
    try:
        samples = struct.unpack(fmt, audio_data)
        return [s / 32768.0 for s in samples]
    except struct.error:
        return []


# ── Factory ──────────────────────────────────────────────────────────


def get_transcriber(
    use_whisper: bool = True,
    model_name: str = "base.en",
    model_dir: Optional[str] = None,
) -> BaseTranscriber:
    """Create the best available transcriber.

    Preference order:
      1. WhisperTranscriber (local, fast, offline)
      2. MacOSDictationTranscriber (macOS only)

    Args:
        use_whisper: Prefer whisper.cpp if available.
        model_name: Whisper model to load.
        model_dir: Override model cache directory.

    Returns:
        A :class:`BaseTranscriber` instance.
    """
    if use_whisper and _HAS_WHISPER_CPP:
        logger.info("Using WhisperTranscriber (model=%s)", model_name)
        return WhisperTranscriber(model_name=model_name, model_dir=model_dir)

    if os.uname().sysname == "Darwin":
        logger.info("Using MacOSDictationTranscriber (fallback)")
        return MacOSDictationTranscriber()

    # Last resort: return whisper transcriber anyway (it'll report unavailable)
    logger.warning("No transcription backend available")
    return WhisperTranscriber(model_name=model_name, model_dir=model_dir)


def whisper_available() -> bool:
    """Quick check if whisper.cpp is importable."""
    return _HAS_WHISPER_CPP
