# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Voice emotion models, ML-based detection, and prosody helpers.

This module provides:
- VoiceEmotion enum for speaking emotion types
- Emotion (basic emotions for GraphRAG memory)
- EmotionResult dataclass with valence/arousal dimensions
- VoiceEmotionDetector for ML-based emotion detection from audio/text
- EmotionDetector for fast keyword-based classification
- Prosody adjustment functions for voice synthesis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Final, Optional

from agentic_brain.voice.config import VoiceConfig

logger = logging.getLogger(__name__)

# ── Optional ML imports (graceful degradation) ───────────────────────

_HAS_TRANSFORMERS = False
_HAS_SPEECHBRAIN = False
_HAS_LIBROSA = False

try:
    import transformers  # noqa: F401

    _HAS_TRANSFORMERS = True
except ImportError:
    pass

try:
    import speechbrain  # noqa: F401

    _HAS_SPEECHBRAIN = True
except ImportError:
    pass

try:
    import librosa  # noqa: F401

    _HAS_LIBROSA = True
except ImportError:
    pass


# ── Basic Emotion Enum (for GraphRAG memory) ─────────────────────────


class Emotion(str, Enum):
    """Basic emotions for GraphRAG memory storage and analysis.

    These map to Ekman's basic emotions plus neutral, providing
    a standardized vocabulary for emotional state tracking.
    """

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SURPRISED = "surprised"
    DISGUSTED = "disgusted"


# ── Emotion Result Dataclass ─────────────────────────────────────────


@dataclass
class EmotionResult:
    """Result of emotion detection with dimensional values.

    Attributes:
        emotion: The detected primary emotion.
        confidence: Confidence score from 0.0 to 1.0.
        valence: Emotional valence from -1.0 (negative) to 1.0 (positive).
        arousal: Arousal level from 0.0 (calm) to 1.0 (excited).
        secondary_emotion: Optional secondary detected emotion.
        raw_scores: Optional dict of all emotion scores from ML model.
    """

    emotion: Emotion
    confidence: float
    valence: float
    arousal: float
    secondary_emotion: Optional[Emotion] = None
    raw_scores: Optional[dict[str, float]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "emotion": self.emotion.value,
            "confidence": round(self.confidence, 3),
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "secondary_emotion": (
                self.secondary_emotion.value if self.secondary_emotion else None
            ),
            "raw_scores": self.raw_scores,
        }

    @property
    def is_positive(self) -> bool:
        """Return True if emotion has positive valence."""
        return self.valence > 0.1

    @property
    def is_negative(self) -> bool:
        """Return True if emotion has negative valence."""
        return self.valence < -0.1

    @property
    def is_high_arousal(self) -> bool:
        """Return True if emotion is high arousal."""
        return self.arousal > 0.6


# ── Emotion Dimension Mappings ───────────────────────────────────────

# Valence and arousal values for each basic emotion (Russell's circumplex)
EMOTION_DIMENSIONS: Final[dict[Emotion, tuple[float, float]]] = {
    Emotion.NEUTRAL: (0.0, 0.3),
    Emotion.HAPPY: (0.8, 0.6),
    Emotion.SAD: (-0.6, 0.2),
    Emotion.ANGRY: (-0.5, 0.8),
    Emotion.FEARFUL: (-0.7, 0.7),
    Emotion.SURPRISED: (0.2, 0.8),
    Emotion.DISGUSTED: (-0.6, 0.5),
}


# ── VoiceEmotionDetector (ML-based) ──────────────────────────────────


class VoiceEmotionDetector:
    """ML-based emotion detection from voice audio or transcribed text.

    Uses SpeechBrain for audio-based detection (more accurate, slower)
    and transformers for text-based detection (faster fallback).

    Example:
        detector = VoiceEmotionDetector()

        # From audio bytes (WAV format, 16kHz)
        result = detector.detect_from_audio(audio_bytes)
        print(f"Detected: {result.emotion.value} ({result.confidence:.1%})")

        # From transcribed text (faster)
        result = detector.detect_from_text("I'm so happy to see you!")
        print(f"Valence: {result.valence:.2f}, Arousal: {result.arousal:.2f}")
    """

    # Model identifiers (lazy-loaded)
    TEXT_MODEL = "j-hartmann/emotion-english-distilroberta-base"
    AUDIO_MODEL = "speechbrain/emotion-recognition-wav2vec2-IEMOCAP"

    def __init__(self) -> None:
        self._audio_model: Any = None
        self._text_model: Any = None
        self._text_pipeline: Any = None
        self._audio_classifier: Any = None

    @property
    def has_audio_support(self) -> bool:
        """Return True if audio emotion detection is available."""
        return _HAS_SPEECHBRAIN and _HAS_LIBROSA

    @property
    def has_text_support(self) -> bool:
        """Return True if text emotion detection is available."""
        return _HAS_TRANSFORMERS

    def _load_text_model(self) -> bool:
        """Lazy-load the text emotion classification pipeline."""
        if self._text_pipeline is not None:
            return True

        if not _HAS_TRANSFORMERS:
            logger.debug("transformers not available for text emotion detection")
            return False

        try:
            from transformers import pipeline

            self._text_pipeline = pipeline(
                "text-classification",
                model=self.TEXT_MODEL,
                top_k=None,
                device=-1,  # CPU by default
            )
            logger.info("VoiceEmotionDetector: text model loaded (%s)", self.TEXT_MODEL)
            return True
        except Exception as exc:
            logger.warning("Failed to load text emotion model: %s", exc)
            return False

    def _load_audio_model(self) -> bool:
        """Lazy-load the SpeechBrain audio emotion classifier."""
        if self._audio_classifier is not None:
            return True

        if not _HAS_SPEECHBRAIN:
            logger.debug("speechbrain not available for audio emotion detection")
            return False

        try:
            from speechbrain.inference.interfaces import foreign_class

            self._audio_classifier = foreign_class(
                source=self.AUDIO_MODEL,
                pymodule_file="custom_interface.py",
                classname="CustomEncoderWav2vec2Classifier",
            )
            logger.info(
                "VoiceEmotionDetector: audio model loaded (%s)", self.AUDIO_MODEL
            )
            return True
        except Exception as exc:
            logger.warning("Failed to load audio emotion model: %s", exc)
            return False

    def _map_text_label_to_emotion(self, label: str) -> Emotion:
        """Map transformers model labels to our Emotion enum."""
        label_lower = label.lower()
        mapping = {
            "joy": Emotion.HAPPY,
            "happiness": Emotion.HAPPY,
            "sadness": Emotion.SAD,
            "anger": Emotion.ANGRY,
            "fear": Emotion.FEARFUL,
            "surprise": Emotion.SURPRISED,
            "disgust": Emotion.DISGUSTED,
            "neutral": Emotion.NEUTRAL,
        }
        return mapping.get(label_lower, Emotion.NEUTRAL)

    def _map_audio_label_to_emotion(self, label: str) -> Emotion:
        """Map SpeechBrain IEMOCAP labels to our Emotion enum."""
        label_lower = label.lower()
        mapping = {
            "hap": Emotion.HAPPY,
            "happiness": Emotion.HAPPY,
            "happy": Emotion.HAPPY,
            "sad": Emotion.SAD,
            "sadness": Emotion.SAD,
            "ang": Emotion.ANGRY,
            "anger": Emotion.ANGRY,
            "angry": Emotion.ANGRY,
            "fea": Emotion.FEARFUL,
            "fear": Emotion.FEARFUL,
            "fearful": Emotion.FEARFUL,
            "sur": Emotion.SURPRISED,
            "surprise": Emotion.SURPRISED,
            "surprised": Emotion.SURPRISED,
            "dis": Emotion.DISGUSTED,
            "disgust": Emotion.DISGUSTED,
            "neu": Emotion.NEUTRAL,
            "neutral": Emotion.NEUTRAL,
        }
        return mapping.get(label_lower, Emotion.NEUTRAL)

    def detect_from_audio(
        self, audio: bytes, sample_rate: int = 16000
    ) -> EmotionResult:
        """Detect emotion from raw audio bytes.

        Uses SpeechBrain wav2vec2 model for high-accuracy emotion detection.
        Requires `pip install agentic-brain[voice-emotion]`.

        Args:
            audio: Raw PCM audio bytes (int16, mono).
            sample_rate: Audio sample rate in Hz (default 16000).

        Returns:
            EmotionResult with detected emotion and dimensional values.
        """
        if not self._load_audio_model():
            # Fall back to neutral if no model
            return EmotionResult(
                emotion=Emotion.NEUTRAL,
                confidence=0.0,
                valence=0.0,
                arousal=0.3,
            )

        try:
            import numpy as np

            # Convert bytes to float32 array for SpeechBrain
            audio_array = (
                np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            )

            # Resample if needed
            if sample_rate != 16000 and _HAS_LIBROSA:
                import librosa

                audio_array = librosa.resample(
                    audio_array, orig_sr=sample_rate, target_sr=16000
                )

            # Run inference
            import torch

            audio_tensor = torch.tensor(audio_array).unsqueeze(0)
            out_prob, score, index, text_lab = self._audio_classifier.classify_batch(
                audio_tensor
            )

            # Get top prediction
            label = text_lab[0] if isinstance(text_lab, list) else str(text_lab)
            confidence = (
                float(score[0]) if hasattr(score, "__getitem__") else float(score)
            )
            emotion = self._map_audio_label_to_emotion(label)

            # Get dimensional values from lookup
            valence, arousal = EMOTION_DIMENSIONS.get(emotion, (0.0, 0.3))

            # Build raw scores dict if available
            raw_scores = None
            if out_prob is not None:
                try:
                    probs = (
                        out_prob[0].tolist()
                        if hasattr(out_prob[0], "tolist")
                        else list(out_prob[0])
                    )
                    labels = ["neu", "hap", "sad", "ang"]  # IEMOCAP labels
                    raw_scores = dict(zip(labels, probs[: len(labels)], strict=False))
                except Exception:
                    pass

            return EmotionResult(
                emotion=emotion,
                confidence=confidence,
                valence=valence,
                arousal=arousal,
                raw_scores=raw_scores,
            )

        except Exception as exc:
            logger.warning("Audio emotion detection failed: %s", exc)
            return EmotionResult(
                emotion=Emotion.NEUTRAL,
                confidence=0.0,
                valence=0.0,
                arousal=0.3,
            )

    def detect_from_text(self, text: str) -> EmotionResult:
        """Detect emotion from transcribed text.

        Uses a DistilRoBERTa model fine-tuned for emotion classification.
        Faster than audio detection but less accurate for subtle emotions.

        Args:
            text: The text to analyze for emotion.

        Returns:
            EmotionResult with detected emotion and dimensional values.
        """
        if not text or not text.strip():
            return EmotionResult(
                emotion=Emotion.NEUTRAL,
                confidence=1.0,
                valence=0.0,
                arousal=0.3,
            )

        if not self._load_text_model():
            # Fall back to keyword-based detection
            return self._keyword_fallback(text)

        try:
            # Run inference
            results = self._text_pipeline(text[:512])  # Truncate to model max

            if not results:
                return self._keyword_fallback(text)

            # Results is list of dicts: [{"label": "joy", "score": 0.9}, ...]
            # Sort by score descending
            sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)

            top = sorted_results[0]
            emotion = self._map_text_label_to_emotion(top["label"])
            confidence = float(top["score"])

            # Get secondary emotion if present
            secondary = None
            if len(sorted_results) > 1 and sorted_results[1]["score"] > 0.15:
                secondary = self._map_text_label_to_emotion(sorted_results[1]["label"])

            # Get dimensional values
            valence, arousal = EMOTION_DIMENSIONS.get(emotion, (0.0, 0.3))

            # Build raw scores
            raw_scores = {r["label"]: r["score"] for r in sorted_results}

            return EmotionResult(
                emotion=emotion,
                confidence=confidence,
                valence=valence,
                arousal=arousal,
                secondary_emotion=secondary,
                raw_scores=raw_scores,
            )

        except Exception as exc:
            logger.warning("Text emotion detection failed: %s", exc)
            return self._keyword_fallback(text)

    def _keyword_fallback(self, text: str) -> EmotionResult:
        """Fast keyword-based fallback when ML models unavailable."""
        text_lower = text.lower()

        # Quick keyword checks
        happy_keywords = (
            "happy",
            "joy",
            "great",
            "wonderful",
            "love",
            "excited",
            "amazing",
        )
        sad_keywords = (
            "sad",
            "sorry",
            "unfortunately",
            "disappointing",
            "miss",
            "upset",
        )
        angry_keywords = ("angry", "furious", "annoyed", "frustrated", "hate")
        fearful_keywords = ("afraid", "scared", "worried", "anxious", "nervous", "fear")
        surprised_keywords = (
            "surprised",
            "wow",
            "unexpected",
            "shocking",
            "amazing",
            "omg",
        )

        if any(kw in text_lower for kw in angry_keywords):
            return EmotionResult(Emotion.ANGRY, 0.7, -0.5, 0.8)
        if any(kw in text_lower for kw in fearful_keywords):
            return EmotionResult(Emotion.FEARFUL, 0.7, -0.7, 0.7)
        if any(kw in text_lower for kw in sad_keywords):
            return EmotionResult(Emotion.SAD, 0.7, -0.6, 0.2)
        if any(kw in text_lower for kw in surprised_keywords):
            return EmotionResult(Emotion.SURPRISED, 0.7, 0.2, 0.8)
        if any(kw in text_lower for kw in happy_keywords):
            return EmotionResult(Emotion.HAPPY, 0.7, 0.8, 0.6)

        # Check for exclamation marks (excitement indicator)
        if text.count("!") >= 2:
            return EmotionResult(Emotion.SURPRISED, 0.5, 0.3, 0.7)
        if "!" in text:
            return EmotionResult(Emotion.HAPPY, 0.5, 0.5, 0.5)

        return EmotionResult(Emotion.NEUTRAL, 0.5, 0.0, 0.3)

    def detect(
        self, audio: Optional[bytes] = None, text: Optional[str] = None
    ) -> EmotionResult:
        """Detect emotion from audio and/or text.

        If both are provided, audio takes precedence as it's more accurate.
        Falls back to text if audio detection fails.

        Args:
            audio: Optional raw audio bytes.
            text: Optional transcribed text.

        Returns:
            EmotionResult with detected emotion.
        """
        if audio is not None and self.has_audio_support:
            result = self.detect_from_audio(audio)
            if result.confidence > 0.5:
                return result

        if text is not None:
            return self.detect_from_text(text)

        return EmotionResult(Emotion.NEUTRAL, 0.5, 0.0, 0.3)


# ── Emotion to VoiceEmotion Mapping ──────────────────────────────────


def emotion_to_voice_emotion(emotion: Emotion, arousal: float = 0.5) -> VoiceEmotion:
    """Map a basic Emotion to a VoiceEmotion for TTS prosody.

    Uses arousal level to distinguish between similar emotions
    (e.g., HAPPY vs EXCITED based on arousal).

    Args:
        emotion: The detected basic emotion.
        arousal: Arousal level 0.0-1.0 for nuanced mapping.

    Returns:
        Corresponding VoiceEmotion for TTS.
    """
    mapping: dict[Emotion, VoiceEmotion] = {
        Emotion.NEUTRAL: VoiceEmotion.NEUTRAL,
        Emotion.HAPPY: VoiceEmotion.HAPPY if arousal < 0.7 else VoiceEmotion.EXCITED,
        Emotion.SAD: VoiceEmotion.CONCERNED,
        Emotion.ANGRY: VoiceEmotion.URGENT,
        Emotion.FEARFUL: VoiceEmotion.CONCERNED,
        Emotion.SURPRISED: VoiceEmotion.EXCITED,
        Emotion.DISGUSTED: VoiceEmotion.CONCERNED,
    }
    return mapping.get(emotion, VoiceEmotion.NEUTRAL)


def emotion_result_to_voice_emotion(result: EmotionResult) -> VoiceEmotion:
    """Convert an EmotionResult to a VoiceEmotion for TTS.

    Args:
        result: EmotionResult from VoiceEmotionDetector.

    Returns:
        VoiceEmotion suitable for prosody adjustment.
    """
    return emotion_to_voice_emotion(result.emotion, result.arousal)


# ── VoiceEmotion Enum (for TTS prosody) ──────────────────────────────


class VoiceEmotion(str, Enum):
    """Supported speaking emotions for the ladies."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    CONCERNED = "concerned"
    EXCITED = "excited"
    CALM = "calm"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    URGENT = "urgent"


EMOTION_PARAMS: Final[dict[VoiceEmotion, dict[str, float]]] = {
    VoiceEmotion.NEUTRAL: {"rate_delta": 0, "pitch_delta": 0.0, "volume_delta": 0.0},
    VoiceEmotion.HAPPY: {"rate_delta": 8, "pitch_delta": 0.08, "volume_delta": 0.05},
    VoiceEmotion.CONCERNED: {
        "rate_delta": -8,
        "pitch_delta": -0.06,
        "volume_delta": -0.02,
    },
    VoiceEmotion.EXCITED: {"rate_delta": 18, "pitch_delta": 0.18, "volume_delta": 0.12},
    VoiceEmotion.CALM: {"rate_delta": -18, "pitch_delta": -0.10, "volume_delta": -0.08},
    VoiceEmotion.PROFESSIONAL: {
        "rate_delta": -4,
        "pitch_delta": -0.02,
        "volume_delta": 0.0,
    },
    VoiceEmotion.FRIENDLY: {"rate_delta": 4, "pitch_delta": 0.04, "volume_delta": 0.03},
    VoiceEmotion.URGENT: {"rate_delta": 22, "pitch_delta": 0.10, "volume_delta": 0.18},
}


class EmotionDetector:
    """Simple keyword-based emotion classification."""

    _KEYWORDS: Final[dict[VoiceEmotion, tuple[str, ...]]] = {
        VoiceEmotion.URGENT: (
            "critical",
            "urgent",
            "immediately",
            "right now",
            "asap",
            "emergency",
            "alert",
        ),
        VoiceEmotion.EXCITED: (
            "amazing",
            "incredible",
            "celebrate",
            "celebration",
            "achievement",
            "won",
            "fantastic",
        ),
        VoiceEmotion.HAPPY: (
            "great",
            "good news",
            "happy",
            "glad",
            "lovely",
            "pleased",
            "thanks",
            "thank you",
        ),
        VoiceEmotion.CONCERNED: (
            "warning",
            "problem",
            "issue",
            "error",
            "failed",
            "trouble",
            "concern",
            "careful",
        ),
        VoiceEmotion.CALM: (
            "breathe",
            "relax",
            "calm",
            "meditation",
            "mindful",
            "gentle",
            "wellness",
        ),
        VoiceEmotion.PROFESSIONAL: (
            "jira",
            "ticket",
            "sprint",
            "deploy",
            "deployment",
            "review",
            "bitbucket",
            "pull request",
            "production",
        ),
        VoiceEmotion.FRIENDLY: (
            "hello",
            "hi",
            "chat",
            "catch up",
            "friend",
            "nice to see",
            "how are you",
        ),
    }

    def classify(
        self,
        text: str,
        *,
        default: VoiceEmotion = VoiceEmotion.NEUTRAL,
        work_mode: bool = False,
    ) -> VoiceEmotion:
        """Classify the text into one of the supported emotions."""

        normalized = text.strip().lower()
        if not normalized:
            return default

        for emotion in (
            VoiceEmotion.URGENT,
            VoiceEmotion.CONCERNED,
            VoiceEmotion.EXCITED,
            VoiceEmotion.HAPPY,
            VoiceEmotion.CALM,
            VoiceEmotion.PROFESSIONAL,
            VoiceEmotion.FRIENDLY,
        ):
            if any(keyword in normalized for keyword in self._KEYWORDS[emotion]):
                return emotion

        if "!" in normalized:
            return (
                VoiceEmotion.EXCITED
                if normalized.count("!") >= 2
                else VoiceEmotion.HAPPY
            )

        if work_mode:
            return VoiceEmotion.PROFESSIONAL

        return default


def _clamp_rate(rate: int) -> int:
    return max(120, min(260, rate))


def _clamp_pitch(pitch: float) -> float:
    return max(0.6, min(1.5, pitch))


def _clamp_volume(volume: float) -> float:
    return max(0.2, min(1.0, volume))


def apply_emotion(voice_config: VoiceConfig, emotion: VoiceEmotion) -> VoiceConfig:
    """Return a new voice config with emotion-specific prosody adjustments."""

    params = EMOTION_PARAMS[emotion]
    return replace(
        voice_config,
        rate=_clamp_rate(int(round(voice_config.rate + params["rate_delta"]))),
        pitch=_clamp_pitch(voice_config.pitch + params["pitch_delta"]),
        volume=_clamp_volume(voice_config.volume + params["volume_delta"]),
    )
