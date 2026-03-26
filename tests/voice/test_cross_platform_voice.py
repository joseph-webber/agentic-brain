# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Tests for Cross-Platform Voice Support

Tests platform detection, voice availability, and speech synthesis
across macOS, Windows, and Linux.
"""

import asyncio
import platform
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

from agentic_brain.voice.cloud_tts import check_cloud_tts_available, speak_cloud
from agentic_brain.voice.linux import list_linux_voices, speak_linux
from agentic_brain.voice.platform import (
    VoicePlatform,
    check_voice_available,
    detect_platform,
    get_platform_info,
    get_recommended_voice_method,
)
from agentic_brain.voice.resilient import ResilientVoice, VoiceConfig, speak
from agentic_brain.voice.windows import list_windows_voices, speak_windows


class TestPlatformDetection:
    """Test platform detection logic"""

    def test_detect_platform(self):
        """Test that platform detection returns valid value"""
        detected = detect_platform()
        assert isinstance(detected, VoicePlatform)
        assert detected in [
            VoicePlatform.MACOS,
            VoicePlatform.WINDOWS,
            VoicePlatform.LINUX,
            VoicePlatform.UNKNOWN,
        ]

    def test_detect_platform_matches_system(self):
        """Test that detection matches actual platform"""
        system = platform.system()
        detected = detect_platform()

        if system == "Darwin":
            assert detected == VoicePlatform.MACOS
        elif system == "Windows":
            assert detected == VoicePlatform.WINDOWS
        elif system == "Linux":
            assert detected == VoicePlatform.LINUX

    def test_check_voice_available(self):
        """Test voice availability check"""
        availability = check_voice_available()

        assert isinstance(availability, dict)
        assert "pyttsx3" in availability
        assert "gtts" in availability
        assert "audio_player" in availability

        # At least one system should be available
        assert any(availability.values()), "No voice system available!"

    def test_get_recommended_voice_method(self):
        """Test that recommendation returns valid method"""
        recommended = get_recommended_voice_method()

        # Should return a method or None
        if recommended:
            assert isinstance(recommended, str)
            assert len(recommended) > 0

    def test_get_platform_info(self):
        """Test platform info collection"""
        info = get_platform_info()

        assert isinstance(info, dict)
        assert "system" in info
        assert "detected_platform" in info
        assert "recommended_voice" in info


class TestWindowsVoice:
    """Test Windows voice support"""

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    @pytest.mark.asyncio
    async def test_speak_windows(self):
        """Test Windows speech"""
        text = "Test message"
        result = await speak_windows(text, rate=150)
        assert isinstance(result, bool)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    @pytest.mark.asyncio
    async def test_list_windows_voices(self):
        """Test listing Windows voices"""
        voices = await list_windows_voices()
        assert isinstance(voices, list)


class TestLinuxVoice:
    """Test Linux voice support"""

    @pytest.mark.skipif(platform.system() != "Linux", reason="Linux-specific test")
    @pytest.mark.asyncio
    async def test_speak_linux(self):
        """Test Linux speech"""
        text = "Test message"
        result = await speak_linux(text, rate=150)
        assert isinstance(result, bool)

    @pytest.mark.skipif(platform.system() != "Linux", reason="Linux-specific test")
    @pytest.mark.asyncio
    async def test_list_linux_voices(self):
        """Test listing Linux voices"""
        voices = await list_linux_voices()
        assert isinstance(voices, list)


class TestCloudTTS:
    """Test cloud TTS fallback"""

    @pytest.mark.asyncio
    async def test_check_cloud_tts_available(self):
        """Test cloud TTS availability check"""
        availability = check_cloud_tts_available()

        assert isinstance(availability, dict)
        assert "gtts" in availability
        assert "azure" in availability
        assert "aws_polly" in availability

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_speak_cloud_gtts(self):
        """Test Google TTS (requires internet)"""
        # This is an integration test - requires internet
        text = "Test message"
        result = await speak_cloud(text, provider="gtts")
        assert isinstance(result, bool)


class TestResilientVoice:
    """Test resilient voice system"""

    @pytest.mark.asyncio
    async def test_resilient_voice_init(self):
        """Test ResilientVoice initialization"""
        config = VoiceConfig()
        voice = ResilientVoice(config)

        assert voice._config is not None
        assert len(voice._fallbacks) > 0

    @pytest.mark.asyncio
    async def test_speak_returns_bool(self):
        """Test that speak() returns boolean"""
        result = await speak("Test", voice="Karen", rate=155)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_speak_with_empty_text(self):
        """Test speaking empty text"""
        result = await speak("", voice="Karen", rate=155)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_speak_with_long_text(self):
        """Test speaking long text"""
        long_text = "This is a long text message. " * 50
        result = await speak(long_text, voice="Karen", rate=155)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_speak_different_rates(self):
        """Test speaking at different rates"""
        text = "Test message"

        # Slow
        result1 = await speak(text, rate=100)
        assert isinstance(result1, bool)

        # Normal
        result2 = await speak(text, rate=150)
        assert isinstance(result2, bool)

        # Fast
        result3 = await speak(text, rate=200)
        assert isinstance(result3, bool)


class TestCrossPlatformIntegration:
    """Integration tests for cross-platform voice"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_voice_works_on_current_platform(self):
        """Test that voice works on the current platform"""
        text = "Cross-platform voice test"
        result = await speak(text)

        # Should always return True (even if fallback to sound)
        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fallback_chain(self):
        """Test that fallback chain is properly configured"""
        config = VoiceConfig()
        voice = ResilientVoice(config)

        # Should have fallbacks configured
        assert len(voice._fallbacks) > 0

        # Should have priority ordering
        priorities = [f.priority for f in voice._fallbacks]
        assert priorities == sorted(priorities)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_voice_with_special_characters(self):
        """Test voice with special characters"""
        text = "Test with quotes 'single' and \"double\""
        result = await speak(text)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_voice_stats(self):
        """Test voice statistics collection"""
        # Speak something
        await speak("Test")

        # Get stats
        from agentic_brain.voice.resilient import get_voice_stats

        stats = get_voice_stats()

        assert isinstance(stats, dict)
        assert "voice" in stats


class TestVoiceConfig:
    """Test voice configuration"""

    def test_default_config(self):
        """Test default configuration"""
        config = VoiceConfig()

        assert config.default_voice == "Karen"
        assert config.default_rate == 155
        assert config.timeout == 30
        assert config.enable_fallbacks is True

    def test_custom_config(self):
        """Test custom configuration"""
        config = VoiceConfig(
            default_voice="Alex", default_rate=180, timeout=60, enable_fallbacks=False
        )

        assert config.default_voice == "Alex"
        assert config.default_rate == 180
        assert config.timeout == 60
        assert config.enable_fallbacks is False


class TestMockedPlatforms:
    """Test voice behavior on different platforms (mocked)"""

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    @pytest.mark.asyncio
    async def test_macos_fallback_chain(self):
        """Test macOS fallback chain setup"""
        with patch("agentic_brain.voice.resilient.detect_platform") as mock:
            mock.return_value = VoicePlatform.MACOS

            voice = ResilientVoice()

            # Should have macOS-specific fallbacks
            fallback_names = [f.name for f in voice._fallbacks]
            assert "say_with_voice" in fallback_names
            assert "cloud_tts" in fallback_names

    @pytest.mark.asyncio
    async def test_windows_fallback_chain(self):
        """Test Windows fallback chain setup"""
        with patch("agentic_brain.voice.resilient.detect_platform") as mock:
            mock.return_value = VoicePlatform.WINDOWS

            voice = ResilientVoice()

            # Should have Windows-specific fallbacks
            fallback_names = [f.name for f in voice._fallbacks]
            assert "windows_voice" in fallback_names
            assert "cloud_tts" in fallback_names

    @pytest.mark.asyncio
    async def test_linux_fallback_chain(self):
        """Test Linux fallback chain setup"""
        with patch("agentic_brain.voice.resilient.detect_platform") as mock:
            mock.return_value = VoicePlatform.LINUX

            voice = ResilientVoice()

            # Should have Linux-specific fallbacks
            fallback_names = [f.name for f in voice._fallbacks]
            assert "linux_voice" in fallback_names
            assert "cloud_tts" in fallback_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
