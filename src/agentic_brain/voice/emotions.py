# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""Voice emotion models and prosody helpers."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum
from typing import Final

from agentic_brain.voice.config import VoiceConfig


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
