# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Tests for agentic-brain voice module.

CRITICAL for accessibility - Joseph is blind and relies on voice output!
"""

import os
import platform
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add source to path for imports to work correctly in test runner
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.audio import Audio, AudioConfig, Platform
from agentic_brain.voice.config import LANGUAGE_PACKS, VoiceConfig, VoiceQuality


class TestVoiceConfig:
    """Test Voice configuration."""

    def test_voice_config_defaults(self):
        """Test default configuration values."""
        config = VoiceConfig()
        # Default might be from env var, but let's assume default env
        if "AGENTIC_BRAIN_VOICE" not in os.environ:
            assert config.voice_name == "Karen"
            assert config.rate == 160
            assert config.quality == VoiceQuality.PREMIUM

    def test_voice_languages_available(self):
        """Test language packs are available."""
        assert "en-AU" in LANGUAGE_PACKS
        assert "ja-JP" in LANGUAGE_PACKS
        assert "ko-KR" in LANGUAGE_PACKS
        assert "vi-VN" in LANGUAGE_PACKS

        # Check specific details
        assert LANGUAGE_PACKS["ja-JP"].default_voice == "Kyoko"
        assert LANGUAGE_PACKS["zh-CN"].default_voice == "Tingting"

    def test_voice_quality_enum(self):
        """Test VoiceQuality enum."""
        assert VoiceQuality.STANDARD.value == "standard"
        assert VoiceQuality.PREMIUM.value == "premium"
        assert VoiceQuality.NEURAL.value == "neural"


class TestVoiceFunctionality:
    """Test voice functionality."""

    @patch("agentic_brain.audio.subprocess.run")
    @patch("agentic_brain.audio.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.audio.Platform.current")
    def test_voice_rate_adjustment(self, mock_platform, mock_which, mock_run):
        """Test voice rate is correctly passed to system command."""
        mock_platform.return_value = Platform.MACOS
        mock_run.return_value = MagicMock(returncode=0)

        # AudioConfig sets default_rate=175 by default
        config = AudioConfig(default_voice="Karen", default_rate=200)
        audio = Audio(config)

        # Mock speak
        with patch.object(audio, "_speak_macos", return_value=True) as mock_speak:
            audio.speak("Test rate")
            # Verify rate passed to _speak_macos
            mock_speak.assert_called_with("Test rate", "Karen", 200, True)

    def test_voice_disabled_mode(self):
        """Test disabled mode."""
        # Config enabled=False
        audio_config = AudioConfig(enabled=False)
        audio = Audio(audio_config)

        # Manually disable it in voice_config too because AudioConfig might not sync properly in test context
        # without proper init or if logic is subtle.
        # But my AudioConfig implementation syncs enabled to voice_config.enabled.

        with patch("agentic_brain.audio.subprocess.run") as mock_run:
            result = audio.speak("Should not speak")
            assert result is False
            assert not mock_run.called

    def test_voice_fallback(self):
        """Test fallback voice logic."""
        pack = LANGUAGE_PACKS["en-AU"]
        assert pack.fallback_voice == "Karen"

        pack_fr = LANGUAGE_PACKS["fr-FR"]
        assert pack_fr.fallback_voice == "Thomas"

    def test_multilingual_support(self):
        """Test multilingual support exists."""
        # Verify 15+ languages
        assert len(LANGUAGE_PACKS) >= 15

        # Verify specific languages requested
        required_langs = [
            "ja-JP",
            "ko-KR",
            "zh-CN",
            "vi-VN",
            "th-TH",
            "id-ID",
            "es-ES",
            "es-MX",
            "fr-FR",
            "de-DE",
            "it-IT",
            "pt-BR",
            "ga-IE",
            "pl-PL",
        ]
        for lang in required_langs:
            assert lang in LANGUAGE_PACKS

    def test_voice_provider_selection(self):
        """Test provider selection config."""
        config = VoiceConfig(provider="elevenlabs")
        assert config.provider == "elevenlabs"


class TestIntegration:
    """Integration tests."""

    def test_integration_with_audio_module(self):
        """Test that audio module imports and uses new config."""
        from agentic_brain.audio import AudioConfig
        from agentic_brain.voice.config import VoiceConfig

        config = AudioConfig()
        assert hasattr(config, "voice_config")
        assert isinstance(config.voice_config, VoiceConfig)
