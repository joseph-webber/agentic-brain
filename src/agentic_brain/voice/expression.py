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

"""Context-aware expression engine for voice output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional

from agentic_brain.voice.config import VoiceConfig
from agentic_brain.voice.emotions import EmotionDetector, VoiceEmotion, apply_emotion


class ExpressionEngine:
    """Resolve emotion using text and work-mode context."""

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
        if self.is_work_mode() and emotion in {
            VoiceEmotion.FRIENDLY,
            VoiceEmotion.HAPPY,
            VoiceEmotion.EXCITED,
            VoiceEmotion.NEUTRAL,
        }:
            emotion = VoiceEmotion.PROFESSIONAL

        return emotion
