import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.config import VoiceConfig
from agentic_brain.voice.emotions import (
    EMOTION_PARAMS,
    EmotionDetector,
    VoiceEmotion,
    apply_emotion,
)
from agentic_brain.voice.expression import ExpressionEngine
from agentic_brain.voice.serializer import VoiceMessage, get_voice_serializer, speak_serialized


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
        assert self.detector.classify("Great news, the tests passed.") == VoiceEmotion.HAPPY

    def test_detects_excited_keyword(self):
        assert self.detector.classify("Amazing achievement unlocked!") == VoiceEmotion.EXCITED

    def test_detects_concerned_keyword(self):
        assert self.detector.classify("Warning: the deploy failed.") == VoiceEmotion.CONCERNED

    def test_detects_urgent_keyword(self):
        assert self.detector.classify("Critical alert, act immediately.") == VoiceEmotion.URGENT

    def test_detects_calm_keyword(self):
        assert self.detector.classify("Take a gentle breath and relax.") == VoiceEmotion.CALM

    def test_detects_professional_keyword(self):
        assert self.detector.classify("Please review the Jira ticket.") == VoiceEmotion.PROFESSIONAL

    def test_detects_friendly_keyword(self):
        assert self.detector.classify("Hello friend, nice to see you.") == VoiceEmotion.FRIENDLY

    def test_uses_work_mode_default(self):
        assert self.detector.classify("status update", work_mode=True) == VoiceEmotion.PROFESSIONAL

    def test_exclamation_marks_influence_positive_text(self):
        assert self.detector.classify("We did it!!") == VoiceEmotion.EXCITED

    def test_empty_text_returns_neutral(self):
        assert self.detector.classify("   ") == VoiceEmotion.NEUTRAL


class TestExpressionEngine:
    def test_work_mode_prefers_professional(self):
        engine = ExpressionEngine(work_mode=True)
        assert engine.detect_emotion("Hello there", lady="Karen") == VoiceEmotion.PROFESSIONAL

    def test_work_mode_preserves_urgent(self):
        engine = ExpressionEngine(work_mode=True)
        assert engine.detect_emotion("Critical alert for production", lady="Karen") == VoiceEmotion.URGENT

    def test_kanya_is_calm_by_default(self):
        engine = ExpressionEngine(work_mode=False)
        assert engine.detect_emotion("Great news, all is well", lady="Kanya") == VoiceEmotion.CALM

    def test_kanya_preserves_concerned_when_needed(self):
        engine = ExpressionEngine(work_mode=False)
        assert engine.detect_emotion("Warning, there is an issue", lady="Kanya") == VoiceEmotion.CONCERNED

    def test_yuna_boosts_happy_to_excited(self):
        engine = ExpressionEngine(work_mode=False)
        assert engine.detect_emotion("Great news for you", lady="Yuna") == VoiceEmotion.EXCITED

    def test_karen_defaults_to_professional_on_neutral(self):
        engine = ExpressionEngine(work_mode=False)
        assert engine.detect_emotion("status update", lady="Karen") == VoiceEmotion.PROFESSIONAL

    def test_expression_engine_styles_voice_config(self):
        engine = ExpressionEngine(work_mode=False)
        emotion, config = engine.style_config(VoiceConfig(rate=160), "Great news", lady="Yuna")
        assert emotion == VoiceEmotion.EXCITED
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
            text="Hello Joseph",
            voice="Karen",
            rate=155,
            pitch=1.2,
            volume=0.9,
            emotion=VoiceEmotion.EXCITED,
        )
        rendered = message.render_for_say()
        assert rendered.startswith("[[pbas")
        assert "[[volm 90]]" in rendered
        assert rendered.endswith("Hello Joseph")

    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_speak_serialized_auto_detects_emotion(self, popen_mock, _which):
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

    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_speak_serialized_respects_explicit_emotion(self, popen_mock, _which):
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

    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_speak_serialized_applies_lady_style(self, popen_mock, _which):
        serializer = get_voice_serializer()
        serializer._audit_enabled = False
        serializer._redis_queue = None
        process = MagicMock()
        process.wait.return_value = 0
        process.poll.return_value = 0
        popen_mock.return_value = process

        assert speak_serialized("Lovely update for wellness", voice="Kanya", lady="Kanya")
        cmd = popen_mock.call_args[0][0]
        assert int(cmd[4]) < 155
