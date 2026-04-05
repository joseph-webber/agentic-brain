# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""SpeechBrain-based emotion recognition helpers.

This module provides a thin wrapper around the
``speechbrain/emotion-recognition-wav2vec2`` checkpoint so that
higher-level voice components can easily run emotion detection on
recorded audio files.

The detector is intentionally file-path based (``detect(audio_path)``)
so it can be called from CLI tools, daemons, and background workers
without keeping large audio tensors in memory.

Usage
-----
    from agentic_brain.voice.emotion import SpeechBrainEmotionDetector

    detector = SpeechBrainEmotionDetector()
    result = detector.detect("/path/to/audio.wav")
    print(result["emotion"], result["confidence"])

To enable this feature, install the optional emotion dependencies:

    pip install "brain[emotion]"

or, when using ``agentic-brain`` directly:

    pip install "agentic-brain[voice-emotion-audio]"
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

try:  # Optional dependency
    from speechbrain.pretrained import EncoderClassifier
except Exception:  # pragma: no cover - handled via runtime error
    EncoderClassifier = None  # type: ignore[assignment]


class SpeechBrainEmotionDetector:
    """SpeechBrain-based emotion recognition.

    Wraps the :mod:`speechbrain` ``EncoderClassifier`` interface using
    the ``speechbrain/emotion-recognition-wav2vec2`` checkpoint.

    The underlying model predicts one of the standard basic emotions:
    neutral, happy, sad, angry, fearful, surprised, and disgusted.
    """

    MODEL_SOURCE: str = "speechbrain/emotion-recognition-wav2vec2"
    MODEL_DIR: str = "models/emotion-recognition"

    def __init__(self) -> None:
        self._classifier: Any | None = None

    def _ensure_model(self) -> None:
        """Lazily load the SpeechBrain model.

        Raises:
            RuntimeError: If SpeechBrain is not installed or the model
                cannot be loaded.
        """

        if self._classifier is not None:
            return

        if EncoderClassifier is None:
            raise RuntimeError(
                "SpeechBrain is not installed. "
                "Install the 'emotion' extra (pip install brain[emotion]) "
                "or 'agentic-brain[voice-emotion-audio]'."
            )

        try:
            self._classifier = EncoderClassifier.from_hparams(
                source=self.MODEL_SOURCE,
                savedir=self.MODEL_DIR,
            )
            logger.info(
                "SpeechBrainEmotionDetector: loaded model %s into %s",
                self.MODEL_SOURCE,
                self.MODEL_DIR,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to load SpeechBrain emotion model: %s", exc)
            raise

    def detect(self, audio_path: str) -> Dict[str, Any]:
        """Detect emotion from an audio file.

        Args:
            audio_path: Path to an audio file supported by SpeechBrain
                (typically mono WAV/FLAC around 16 kHz).

        Returns:
            A dict with keys:

            - ``emotion``: predicted label string.
            - ``confidence``: top-score probability as a float.
            - ``probabilities``: mapping of label -> probability.
        """

        self._ensure_model()

        # Run classification; SpeechBrain returns tensors/arrays
        out_prob, score, index, text_lab = self._classifier.classify_file(audio_path)

        # Primary label ("neutral", "happy", etc.)
        if isinstance(text_lab, (list, tuple)) and text_lab:
            label = str(text_lab[0])
        else:  # pragma: no cover - highly unlikely shape
            label = str(text_lab)

        # Confidence score may be a tensor or list; normalise to float
        try:
            top_score = float(score[0])  # type: ignore[index]
        except Exception:  # pragma: no cover - fallback path
            top_score = float(score)

        probabilities: Dict[str, float] = {}
        try:
            # Convert probabilities tensor to a list of floats
            first = out_prob[0]
            probs = first.tolist() if hasattr(first, "tolist") else list(first)

            labels = list(
                getattr(self._classifier.hparams.label_encoder, "ind2lab", [])
            )
            for k, v in zip(labels, probs):
                probabilities[str(k)] = float(v)
        except Exception as exc:  # pragma: no cover - best-effort mapping
            logger.warning(
                "Failed to build probability map from SpeechBrain output: %s", exc
            )

        return {
            "emotion": label,
            "confidence": float(top_score),
            "probabilities": probabilities,
        }
