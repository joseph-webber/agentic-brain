"""Context-aware expression engine for the ladies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional

from agentic_brain.voice.config import VoiceConfig
from agentic_brain.voice.emotions import EmotionDetector, VoiceEmotion, apply_emotion


@dataclass(frozen=True)
class LadyExpressionStyle:
    default_emotion: VoiceEmotion | None = None
    happy_boost: bool = False
    force_calm: bool = False


LADY_EXPRESSION_STYLES: Final[dict[str, LadyExpressionStyle]] = {
    "kanya": LadyExpressionStyle(default_emotion=VoiceEmotion.CALM, force_calm=True),
    "yuna": LadyExpressionStyle(happy_boost=True),
    "karen": LadyExpressionStyle(default_emotion=VoiceEmotion.PROFESSIONAL),
}


class ExpressionEngine:
    """Resolve emotion using text, work-mode context, and lady personality."""

    def __init__(
        self,
        *,
        work_mode: Optional[bool] = None,
        detector: EmotionDetector | None = None,
    ) -> None:
        self._work_mode = work_mode
        self._detector = detector or EmotionDetector()

    def detect_emotion(self, text: str, lady: str | None = None) -> VoiceEmotion:
        """Detect the best-fitting emotion for the utterance."""

        emotion = self._detector.classify(text, work_mode=self.is_work_mode())
        return self._apply_context(emotion, lady=lady)

    def style_config(
        self,
        voice_config: VoiceConfig,
        text: str,
        *,
        lady: str | None = None,
        emotion: VoiceEmotion | None = None,
    ) -> tuple[VoiceEmotion, VoiceConfig]:
        """Return the resolved emotion and updated config for the utterance."""

        resolved = emotion or self.detect_emotion(text, lady=lady)
        return resolved, apply_emotion(voice_config, resolved)

    def is_work_mode(self) -> bool:
        """Return whether work mode is active."""

        if self._work_mode is not None:
            return self._work_mode

        mode_file = Path.home() / ".brain-voice-mode"
        try:
            value = mode_file.read_text().strip().lower()
        except OSError:
            return False
        return value in {"work", "boss"}

    def _apply_context(
        self, emotion: VoiceEmotion, *, lady: str | None
    ) -> VoiceEmotion:
        style = LADY_EXPRESSION_STYLES.get((lady or "").lower())

        if self.is_work_mode() and emotion in {
            VoiceEmotion.FRIENDLY,
            VoiceEmotion.HAPPY,
            VoiceEmotion.EXCITED,
            VoiceEmotion.NEUTRAL,
        }:
            emotion = VoiceEmotion.PROFESSIONAL

        if style is None:
            return emotion

        if style.force_calm and emotion not in {
            VoiceEmotion.URGENT,
            VoiceEmotion.CONCERNED,
        }:
            return VoiceEmotion.CALM

        if style.happy_boost and emotion == VoiceEmotion.HAPPY:
            return VoiceEmotion.EXCITED

        if emotion == VoiceEmotion.NEUTRAL and style.default_emotion is not None:
            return style.default_emotion

        return emotion
