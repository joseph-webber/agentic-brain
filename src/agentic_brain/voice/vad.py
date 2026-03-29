"""Voice Activity Detection using Silero VAD."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VADConfig:
    """VAD configuration.

    Attributes:
        threshold: Speech probability threshold (0-1).
        min_speech_duration_ms: Minimum speech duration to start a segment.
        min_silence_duration_ms: Minimum silence duration to end a segment.
        sample_rate: Audio sample rate in Hz.
        window_size_samples: Analysis window size in samples (Silero requires >=512 at 16 kHz).
    """

    threshold: float = 0.5
    min_speech_duration_ms: int = 250
    min_silence_duration_ms: int = 100
    sample_rate: int = 16_000
    window_size_samples: int = 512


@dataclass
class SpeechSegment:
    """A detected speech segment.

    Attributes:
        start_sample: Start index of the segment (inclusive).
        end_sample: End index of the segment (exclusive).
        audio: The audio samples for the segment (mono, float32 or int16).
        confidence: Average speech probability over the segment.
    """

    start_sample: int
    end_sample: int
    audio: np.ndarray
    confidence: float


class SileroVAD:
    """Silero VAD wrapper for real-time voice activity detection.

    This class lazily loads the Silero VAD model via ``torch.hub`` and
    provides an iterator over :class:`SpeechSegment` for a given mono
    waveform.  It is intentionally stateless – each call to
    :meth:`detect_speech` runs an independent analysis so it can be used in
    both batch and streaming pipelines.

    The implementation follows the reference usage from
    https://github.com/snakers4/silero-vad while keeping torch import
    optional so the rest of the voice stack is not blocked if PyTorch is
    unavailable.
    """

    def __init__(self, config: Optional[VADConfig] = None) -> None:
        self.config = config or VADConfig()
        self._model = None
        self._utils = None

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def ensure_model(self) -> bool:
        """Load the Silero VAD model on first use.

        Returns ``True`` on success, ``False`` if the model could not be
        loaded (missing torch, no internet the first time, etc.).  Callers
        should gracefully degrade when this returns ``False``.
        """

        if self._model is not None and self._utils is not None:
            return True

        try:
            import torch

            self._model, self._utils = torch.hub.load(  # type: ignore[assignment]
                "snakers4/silero-vad",
                "silero_vad",
                trust_repo=True,
                onnx=False,
                force_reload=False,
            )
            logger.info("Silero VAD model loaded successfully")
            return True
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.warning("Failed to load Silero VAD: %s", exc)
            self._model = None
            self._utils = None
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_speech(self, audio: np.ndarray) -> Iterator[SpeechSegment]:
        """Detect speech segments in an audio buffer.

        Args:
            audio: Mono PCM samples as a NumPy array.  ``float32`` in
                ``[-1, 1]`` or integer type (e.g. int16).  The sample rate
                must match :attr:`VADConfig.sample_rate`.

        Yields:
            :class:`SpeechSegment` objects for each detected speech region.
        """

        if not self.ensure_model():
            return

        if audio.ndim != 1:
            raise ValueError("SileroVAD expects mono audio (1-D array)")

        # Normalise audio to float32 in [-1, 1]
        if not np.issubdtype(audio.dtype, np.floating):
            max_val = np.iinfo(audio.dtype).max
            audio_f32 = audio.astype(np.float32) / float(max_val)
        else:
            audio_f32 = audio.astype(np.float32)

        try:
            import torch

            # Silero expects shape [batch, samples]
            wav_tensor = torch.from_numpy(audio_f32).unsqueeze(0)

            (get_speech_ts,) = self._utils  # type: ignore[misc]
            speech_ts = get_speech_ts(  # type: ignore[call-arg]
                wav_tensor,
                self._model,
                sampling_rate=self.config.sample_rate,
                threshold=self.config.threshold,
                min_speech_duration_ms=self.config.min_speech_duration_ms,
                min_silence_duration_ms=self.config.min_silence_duration_ms,
                window_size_samples=self.config.window_size_samples,
            )

            for seg in speech_ts or []:
                start = int(seg.get("start", 0))
                end = int(seg.get("end", 0))
                if start < 0 or end <= start or end > len(audio_f32):
                    continue
                segment_audio = audio_f32[start:end]

                # Compute a simple confidence score: mean speech probability
                # using the model on this window.  This is an approximation
                # but good enough for routing decisions.
                with torch.no_grad():
                    probs = self._model(segment_audio.unsqueeze(0))  # type: ignore[arg-type]
                confidence = float(probs.squeeze().mean().item())

                yield SpeechSegment(
                    start_sample=start,
                    end_sample=end,
                    audio=segment_audio.copy(),
                    confidence=confidence,
                )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Silero VAD detection failed: %s", exc)
            return
