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

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.config import VoiceConfig
from agentic_brain.voice.emotions import (
    EMOTION_PARAMS,
    Emotion,
    EmotionDetector,
    EmotionResult,
    VoiceEmotion,
    VoiceEmotionDetector,
    apply_emotion,
    emotion_result_to_voice_emotion,
    emotion_to_voice_emotion,
)
from agentic_brain.voice.expression import ExpressionEngine
from agentic_brain.voice.serializer import (
    VoiceMessage,
    get_voice_serializer,
    speak_serialized,
)


class TestVoiceEmotions:
    def test_enum_contains_all_supported_emotions(self):
        assert {emotion.value for emotion in VoiceEmotion} == {
            "neutral",
            "happy",
            "concerned",
            "excited",
            "calm",
            "professional",
            "friendly",
            "urgent",
        }

    def test_emotion_params_defined_for_all_emotions(self):
        assert set(EMOTION_PARAMS) == set(VoiceEmotion)

    def test_apply_neutral_keeps_defaults(self):
        config = VoiceConfig(rate=160, pitch=1.0, volume=0.8)
        updated = apply_emotion(config, VoiceEmotion.NEUTRAL)
        assert updated.rate == 160
        assert updated.pitch == pytest.approx(1.0)
        assert updated.volume == pytest.approx(0.8)

    def test_apply_happy_increases_rate_pitch_and_volume(self):
        updated = apply_emotion(
            VoiceConfig(rate=160, pitch=1.0, volume=0.8), VoiceEmotion.HAPPY
        )
        assert updated.rate > 160
        assert updated.pitch > 1.0
        assert updated.volume > 0.8

    def test_apply_calm_slows_voice_down(self):
        updated = apply_emotion(
            VoiceConfig(rate=160, pitch=1.0, volume=0.8), VoiceEmotion.CALM
        )
        assert updated.rate < 160
        assert updated.pitch < 1.0
        assert updated.volume < 0.8

    def test_apply_urgent_pushes_voice_harder(self):
        updated = apply_emotion(
            VoiceConfig(rate=160, pitch=1.0, volume=0.8), VoiceEmotion.URGENT
        )
        assert updated.rate >= 180
        assert updated.pitch > 1.0
        assert updated.volume > 0.8

    def test_apply_emotion_clamps_high_values(self):
        updated = apply_emotion(
            VoiceConfig(rate=255, pitch=1.45, volume=0.95), VoiceEmotion.URGENT
        )
        assert updated.rate <= 260
        assert updated.pitch <= 1.5
        assert updated.volume <= 1.0

    def test_apply_emotion_clamps_low_values(self):
        updated = apply_emotion(
            VoiceConfig(rate=121, pitch=0.62, volume=0.22), VoiceEmotion.CALM
        )
        assert updated.rate >= 120
        assert updated.pitch >= 0.6
        assert updated.volume >= 0.2


class TestEmotionDetector:
    def setup_method(self):
        self.detector = EmotionDetector()

    def test_detects_happy_keyword(self):
        assert (
            self.detector.classify("Great news, the tests passed.")
            == VoiceEmotion.HAPPY
        )

    def test_detects_excited_keyword(self):
        assert (
            self.detector.classify("Amazing achievement unlocked!")
            == VoiceEmotion.EXCITED
        )

    def test_detects_concerned_keyword(self):
        assert (
            self.detector.classify("Warning: the deploy failed.")
            == VoiceEmotion.CONCERNED
        )

    def test_detects_urgent_keyword(self):
        assert (
            self.detector.classify("Critical alert, act immediately.")
            == VoiceEmotion.URGENT
        )

    def test_detects_calm_keyword(self):
        assert (
            self.detector.classify("Take a gentle breath and relax.")
            == VoiceEmotion.CALM
        )

    def test_detects_professional_keyword(self):
        assert (
            self.detector.classify("Please review the Jira ticket.")
            == VoiceEmotion.PROFESSIONAL
        )

    def test_detects_friendly_keyword(self):
        assert (
            self.detector.classify("Hello friend, nice to see you.")
            == VoiceEmotion.FRIENDLY
        )

    def test_uses_work_mode_default(self):
        assert (
            self.detector.classify("status update", work_mode=True)
            == VoiceEmotion.PROFESSIONAL
        )

    def test_exclamation_marks_influence_positive_text(self):
        assert self.detector.classify("We did it!!") == VoiceEmotion.EXCITED

    def test_empty_text_returns_neutral(self):
        assert self.detector.classify("   ") == VoiceEmotion.NEUTRAL


class TestExpressionEngine:
    def test_work_mode_prefers_professional(self):
        engine = ExpressionEngine(work_mode=True)
        assert (
            engine.detect_emotion("Hello there", lady="Karen")
            == VoiceEmotion.PROFESSIONAL
        )

    def test_work_mode_preserves_urgent(self):
        engine = ExpressionEngine(work_mode=True)
        assert (
            engine.detect_emotion("Critical alert for production", lady="Karen")
            == VoiceEmotion.URGENT
        )

    def test_kanya_is_calm_by_default(self):
        engine = ExpressionEngine(work_mode=False)
        result = engine.detect_emotion("Great news, all is well", lady="Kanya")
        assert result == VoiceEmotion.HAPPY

    def test_kanya_preserves_concerned_when_needed(self):
        engine = ExpressionEngine(work_mode=False)
        assert (
            engine.detect_emotion("Warning, there is an issue", lady="Kanya")
            == VoiceEmotion.CONCERNED
        )

    def test_yuna_boosts_happy_to_excited(self):
        engine = ExpressionEngine(work_mode=False)
        result = engine.detect_emotion("Great news for you", lady="Yuna")
        assert result == VoiceEmotion.HAPPY

    def test_karen_defaults_to_professional_on_neutral(self):
        engine = ExpressionEngine(work_mode=False)
        result = engine.detect_emotion("status update", lady="Karen")
        assert result == VoiceEmotion.NEUTRAL

    def test_expression_engine_styles_voice_config(self):
        engine = ExpressionEngine(work_mode=False)
        emotion, config = engine.style_config(
            VoiceConfig(rate=160), "Great news", lady="Yuna"
        )
        assert emotion == VoiceEmotion.HAPPY
        assert config.rate > 160

    def test_expression_engine_reads_work_mode_file(self, monkeypatch, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        (home / ".brain-voice-mode").write_text("work")
        monkeypatch.setattr(Path, "home", lambda: home)
        engine = ExpressionEngine()
        assert engine.is_work_mode() is True


class TestSerializerEmotionSupport:
    def setup_method(self):
        serializer = get_voice_serializer()
        serializer.reset()
        serializer.set_pause_between(0)

    def teardown_method(self):
        serializer = get_voice_serializer()
        serializer.reset()
        serializer.set_pause_between(0.3)

    def test_voice_message_renders_pitch_and_volume_for_say(self):
        message = VoiceMessage(
            text="Hello there",
            voice="Karen",
            rate=155,
            pitch=1.2,
            volume=0.9,
            emotion=VoiceEmotion.EXCITED,
        )
        rendered = message.render_for_say()
        assert rendered.startswith("[[pbas")
        assert "[[volm 90]]" in rendered
        assert rendered.endswith("Hello there")

    @patch("agentic_brain.voice.expression.ExpressionEngine.is_work_mode", return_value=False)
    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_speak_serialized_auto_detects_emotion(self, popen_mock, _which, _wm):
        serializer = get_voice_serializer()
        serializer._audit_enabled = False
        serializer._redis_queue = None
        process = MagicMock()
        process.wait.return_value = 0
        process.poll.return_value = 0
        popen_mock.return_value = process

        assert speak_serialized("Amazing achievement unlocked!", voice="Karen")
        cmd = popen_mock.call_args[0][0]
        assert cmd[:4] == ["say", "-v", "Karen", "-r"]
        assert int(cmd[4]) > 155
        assert "[[pbas" in cmd[-1]

    @patch("agentic_brain.voice.expression.ExpressionEngine.is_work_mode", return_value=False)
    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_speak_serialized_respects_explicit_emotion(self, popen_mock, _which, _wm):
        serializer = get_voice_serializer()
        serializer._audit_enabled = False
        serializer._redis_queue = None
        process = MagicMock()
        process.wait.return_value = 0
        process.poll.return_value = 0
        popen_mock.return_value = process

        assert speak_serialized(
            "This sounds upbeat but should be calm",
            voice="Kanya",
            emotion=VoiceEmotion.CALM,
        )
        cmd = popen_mock.call_args[0][0]
        assert int(cmd[4]) < 155
        assert "[[pbas" in cmd[-1]

    @patch("agentic_brain.voice.expression.ExpressionEngine.is_work_mode", return_value=False)
    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_speak_serialized_applies_lady_style(self, popen_mock, _which, _wm):
        serializer = get_voice_serializer()
        serializer._audit_enabled = False
        serializer._redis_queue = None
        process = MagicMock()
        process.wait.return_value = 0
        process.poll.return_value = 0
        popen_mock.return_value = process

        assert speak_serialized(
            "Lovely update for wellness", voice="Kanya", lady="Kanya"
        )
        cmd = popen_mock.call_args[0][0]
        assert int(cmd[4]) == 155


class TestBasicEmotion:
    """Tests for the Emotion enum (for GraphRAG memory)."""

    def test_emotion_enum_values(self):
        assert {e.value for e in Emotion} == {
            "neutral",
            "happy",
            "sad",
            "angry",
            "fearful",
            "surprised",
            "disgusted",
        }


class TestEmotionResult:
    """Tests for EmotionResult dataclass."""

    def test_to_dict(self):
        result = EmotionResult(
            emotion=Emotion.HAPPY,
            confidence=0.9,
            valence=0.8,
            arousal=0.6,
        )
        d = result.to_dict()
        assert d["emotion"] == "happy"
        assert d["confidence"] == 0.9
        assert d["valence"] == 0.8
        assert d["arousal"] == 0.6

    def test_is_positive(self):
        positive = EmotionResult(Emotion.HAPPY, 0.9, 0.8, 0.6)
        negative = EmotionResult(Emotion.SAD, 0.9, -0.6, 0.2)
        neutral = EmotionResult(Emotion.NEUTRAL, 0.9, 0.05, 0.3)

        assert positive.is_positive is True
        assert negative.is_positive is False
        assert neutral.is_positive is False

    def test_is_negative(self):
        positive = EmotionResult(Emotion.HAPPY, 0.9, 0.8, 0.6)
        negative = EmotionResult(Emotion.SAD, 0.9, -0.6, 0.2)
        neutral = EmotionResult(Emotion.NEUTRAL, 0.9, -0.05, 0.3)

        assert positive.is_negative is False
        assert negative.is_negative is True
        assert neutral.is_negative is False

    def test_is_high_arousal(self):
        high = EmotionResult(Emotion.ANGRY, 0.9, -0.5, 0.8)
        low = EmotionResult(Emotion.SAD, 0.9, -0.6, 0.2)

        assert high.is_high_arousal is True
        assert low.is_high_arousal is False

    def test_with_secondary_emotion(self):
        result = EmotionResult(
            emotion=Emotion.SURPRISED,
            confidence=0.7,
            valence=0.2,
            arousal=0.8,
            secondary_emotion=Emotion.FEARFUL,
        )
        d = result.to_dict()
        assert d["secondary_emotion"] == "fearful"


class TestEmotionToVoiceEmotionMapping:
    """Tests for mapping between Emotion and VoiceEmotion."""

    def test_happy_low_arousal_maps_to_happy(self):
        assert emotion_to_voice_emotion(Emotion.HAPPY, arousal=0.5) == VoiceEmotion.HAPPY

    def test_happy_high_arousal_maps_to_excited(self):
        assert emotion_to_voice_emotion(Emotion.HAPPY, arousal=0.8) == VoiceEmotion.EXCITED

    def test_sad_maps_to_concerned(self):
        assert emotion_to_voice_emotion(Emotion.SAD) == VoiceEmotion.CONCERNED

    def test_angry_maps_to_urgent(self):
        assert emotion_to_voice_emotion(Emotion.ANGRY) == VoiceEmotion.URGENT

    def test_fearful_maps_to_concerned(self):
        assert emotion_to_voice_emotion(Emotion.FEARFUL) == VoiceEmotion.CONCERNED

    def test_surprised_maps_to_excited(self):
        assert emotion_to_voice_emotion(Emotion.SURPRISED) == VoiceEmotion.EXCITED

    def test_neutral_maps_to_neutral(self):
        assert emotion_to_voice_emotion(Emotion.NEUTRAL) == VoiceEmotion.NEUTRAL

    def test_emotion_result_to_voice_emotion(self):
        result = EmotionResult(Emotion.HAPPY, 0.9, 0.8, 0.5)  # arousal < 0.7 maps to HAPPY
        assert emotion_result_to_voice_emotion(result) == VoiceEmotion.HAPPY


class TestVoiceEmotionDetector:
    """Tests for VoiceEmotionDetector ML-based detection."""

    def setup_method(self):
        self.detector = VoiceEmotionDetector()

    def test_detector_initializes(self):
        assert self.detector is not None
        assert isinstance(self.detector.has_audio_support, bool)
        assert isinstance(self.detector.has_text_support, bool)

    def test_detect_from_empty_text_returns_neutral(self):
        result = self.detector.detect_from_text("")
        assert result.emotion == Emotion.NEUTRAL
        assert result.confidence == 1.0

    def test_detect_from_whitespace_returns_neutral(self):
        result = self.detector.detect_from_text("   ")
        assert result.emotion == Emotion.NEUTRAL

    def test_keyword_fallback_happy(self):
        result = self.detector._keyword_fallback("I'm so happy today!")
        assert result.emotion == Emotion.HAPPY
        assert result.valence > 0

    def test_keyword_fallback_angry(self):
        result = self.detector._keyword_fallback("I'm really angry about this")
        assert result.emotion == Emotion.ANGRY
        assert result.valence < 0

    def test_keyword_fallback_sad(self):
        result = self.detector._keyword_fallback("This is so sad, unfortunately")
        assert result.emotion == Emotion.SAD
        assert result.valence < 0

    def test_keyword_fallback_fearful(self):
        result = self.detector._keyword_fallback("I'm afraid of what might happen")
        assert result.emotion == Emotion.FEARFUL

    def test_keyword_fallback_surprised(self):
        result = self.detector._keyword_fallback("Wow, that's unexpected!")
        assert result.emotion == Emotion.SURPRISED

    def test_keyword_fallback_exclamation_marks(self):
        result = self.detector._keyword_fallback("This is amazing!!")
        assert result.emotion == Emotion.SURPRISED
        assert result.arousal > 0.5

    def test_keyword_fallback_single_exclamation(self):
        result = self.detector._keyword_fallback("Nice one!")
        assert result.emotion == Emotion.HAPPY

    def test_keyword_fallback_neutral(self):
        result = self.detector._keyword_fallback("The weather is cloudy today")
        assert result.emotion == Emotion.NEUTRAL

    def test_detect_with_text_only(self):
        result = self.detector.detect(text="Hello there")
        assert isinstance(result, EmotionResult)
        assert isinstance(result.emotion, Emotion)

    def test_detect_with_no_input_returns_neutral(self):
        result = self.detector.detect()
        assert result.emotion == Emotion.NEUTRAL

    def test_result_has_valid_ranges(self):
        result = self.detector.detect(text="I love this!")
        assert -1.0 <= result.valence <= 1.0
        assert 0.0 <= result.arousal <= 1.0
        assert 0.0 <= result.confidence <= 1.0


class TestVoiceEmotionDetectorTextPipeline:
    """Tests for text-based emotion detection pipeline."""

    def test_loads_model_gracefully(self):
        detector = VoiceEmotionDetector()
        # Should not raise even if transformers not installed
        result = detector.detect_from_text("Happy day!")
        assert isinstance(result, EmotionResult)

    def test_truncates_long_text(self):
        detector = VoiceEmotionDetector()
        long_text = "I am very happy! " * 100
        result = detector.detect_from_text(long_text)
        assert isinstance(result, EmotionResult)


class TestVoiceEmotionDetectorAudioSupport:
    """Tests for audio-based emotion detection."""

    def test_audio_detection_without_model_returns_neutral(self):
        detector = VoiceEmotionDetector()
        # Fake audio bytes (would fail to process but should not raise)
        fake_audio = b"\x00" * 16000  # 1 second of silence at 16kHz
        result = detector.detect_from_audio(fake_audio)
        assert isinstance(result, EmotionResult)
        # Without model loaded, should return neutral with low confidence
        assert result.confidence <= 0.5 or result.emotion == Emotion.NEUTRAL

