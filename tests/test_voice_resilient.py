# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Tests for Resilient Voice System

Tests verify that voice always works with fallbacks,
and that the daemon continues operating even under failure conditions.
"""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.voice.resilient import (
    ResilientVoice,
    SoundEffects,
    VoiceConfig,
    VoiceDaemon,
    get_daemon,
    get_voice_stats,
    play_sound,
    speak,
    speak_via_daemon,
)


class TestVoiceConfig:
    """Test VoiceConfig"""

    def test_default_config(self):
        config = VoiceConfig()
        assert config.default_voice == "Karen"
        assert config.default_rate == 155
        assert config.timeout == 30
        assert config.enable_fallbacks is True

    def test_custom_config(self):
        config = VoiceConfig(default_voice="Moira", default_rate=140, timeout=60)
        assert config.default_voice == "Moira"
        assert config.default_rate == 140
        assert config.timeout == 60


@pytest.mark.skipif(
    os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true",
    reason="Voice tests call real speak() which hangs on CI without audio device",
)
class TestResilientVoice:
    """Test ResilientVoice with fallbacks"""

    @pytest.fixture
    def setup(self):
        """Setup for each test"""
        ResilientVoice._setup_fallbacks()
        yield
        # Cleanup
        ResilientVoice._config = None

    @pytest.mark.asyncio
    async def test_speak_with_default_voice(self, setup):
        """Test speaking with default voice"""
        config = VoiceConfig()
        ResilientVoice(config)

        result = await speak("Hello World")
        # Should succeed (or at least try all fallbacks)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_speak_with_custom_voice(self, setup):
        """Test speaking with custom voice"""
        config = VoiceConfig()
        ResilientVoice(config)

        result = await speak("Hello Moira", voice="Moira", rate=140)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_speak_with_special_characters(self, setup):
        """Test text with special characters"""
        config = VoiceConfig()
        ResilientVoice(config)

        text = 'Hello "World"! It\'s working.'
        result = await speak(text)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_speak_with_empty_text(self, setup):
        """Test with empty text"""
        config = VoiceConfig()
        ResilientVoice(config)

        result = await speak("")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_fallback_chain_order(self, setup):
        """Test that fallbacks are in correct priority order"""
        config = VoiceConfig()
        ResilientVoice(config)

        assert len(ResilientVoice._fallbacks) >= 3
        # Check priority ordering
        for i in range(len(ResilientVoice._fallbacks) - 1):
            assert (
                ResilientVoice._fallbacks[i].priority
                <= ResilientVoice._fallbacks[i + 1].priority
            )

    @pytest.mark.asyncio
    async def test_voice_stats(self, setup):
        """Test voice statistics tracking"""
        config = VoiceConfig()
        ResilientVoice(config)

        stats = ResilientVoice.get_stats()
        assert isinstance(stats, dict)

        for _fallback_name, fallback_stats in stats.items():
            assert "success" in fallback_stats
            assert "failure" in fallback_stats
            assert "success_rate" in fallback_stats

    @pytest.mark.asyncio
    async def test_speak_without_fallbacks(self, setup):
        """Test with fallbacks disabled"""
        config = VoiceConfig(enable_fallbacks=False)
        ResilientVoice(config)

        result = await speak("Testing without fallbacks")
        assert isinstance(result, bool)


class TestVoiceDaemon:
    """Test VoiceDaemon"""

    @pytest.mark.asyncio
    async def test_daemon_initialization(self):
        """Test daemon initialization"""
        daemon = VoiceDaemon()
        assert daemon._running is False
        assert daemon.processed == 0
        assert daemon.errors == 0

    @pytest.mark.asyncio
    async def test_daemon_start_stop(self):
        """Test daemon start and stop"""
        daemon = VoiceDaemon()

        await daemon.start()
        assert daemon._running is True

        await asyncio.sleep(0.1)
        await daemon.stop()
        assert daemon._running is False

    @pytest.mark.asyncio
    async def test_daemon_queue_speak(self):
        """Test queueing speech via daemon"""
        daemon = VoiceDaemon()
        await daemon.start()

        # Queue some speech
        await daemon.speak("Test 1")
        await daemon.speak("Test 2", voice="Moira")
        await daemon.speak("Test 3", rate=140)

        # Give daemon time to process
        await asyncio.sleep(1)

        stats = daemon.get_stats()
        assert stats["queue_size"] <= 3  # Should be processing

        await daemon.stop()

    @pytest.mark.asyncio
    async def test_daemon_error_handling(self):
        """Test daemon handles errors gracefully"""
        daemon = VoiceDaemon()
        await daemon.start()

        # Queue invalid input
        await daemon.speak("")
        await daemon.speak("Testing", voice="InvalidVoice")

        await asyncio.sleep(0.5)

        stats = daemon.get_stats()
        # Daemon should still be running
        assert stats["running"] is True

        await daemon.stop()

    @pytest.mark.asyncio
    async def test_daemon_stats(self):
        """Test daemon statistics"""
        daemon = VoiceDaemon()

        stats = daemon.get_stats()
        assert "running" in stats
        assert "queue_size" in stats
        assert "processed" in stats
        assert "errors" in stats
        assert "error_rate" in stats


class TestSoundEffects:
    """Test SoundEffects"""

    def test_sound_effects_exist(self):
        """Test that default sounds exist"""
        for sound_name, sound_path in SoundEffects.SOUNDS.items():
            # Verify sound paths (may not exist in test environment)
            assert isinstance(sound_name, str)
            assert isinstance(sound_path, str)

    @pytest.mark.asyncio
    async def test_play_valid_sound(self):
        """Test playing valid sound"""
        result = await play_sound("success")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_play_invalid_sound(self):
        """Test playing invalid sound"""
        result = await play_sound("nonexistent_sound")
        # Should handle gracefully
        assert isinstance(result, bool)


class TestConvenienceFunctions:
    """Test convenience functions"""

    @pytest.mark.asyncio
    async def test_speak_function(self):
        """Test global speak function"""
        result = await speak("Testing convenience function")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_speak_via_daemon_function(self):
        """Test daemon speak function"""
        await speak_via_daemon("Testing daemon function")
        # Should not raise

    @pytest.mark.asyncio
    async def test_get_daemon_function(self):
        """Test get_daemon function"""
        daemon = await get_daemon()
        assert daemon is not None
        assert isinstance(daemon, VoiceDaemon)
        # Should return same instance on second call
        daemon2 = await get_daemon()
        assert daemon is daemon2

        await daemon.stop()

    def test_get_voice_stats_function(self):
        """Test get_voice_stats function"""
        stats = get_voice_stats()
        assert isinstance(stats, dict)
        assert "voice" in stats


@pytest.mark.skipif(
    os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true",
    reason="Voice integration tests hang on CI without audio device",
)
class TestIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_speak_and_sound(self):
        """Test speaking and playing sound"""
        # Speak
        await speak("Process complete")

        # Play sound
        await play_sound("success")

        # Both should complete without error

    @pytest.mark.asyncio
    async def test_daemon_multiple_speakers(self):
        """Test daemon with multiple concurrent speakers"""
        daemon = VoiceDaemon()
        await daemon.start()

        # Queue multiple at once
        tasks = [
            daemon.speak("Karen speaking"),
            daemon.speak("Moira speaking", voice="Moira"),
            daemon.speak("Tingting speaking", voice="Tingting"),
        ]
        await asyncio.gather(*tasks)

        await asyncio.sleep(1)
        await daemon.stop()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    @pytest.mark.skipif(
        os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true",
        reason="Daemon test hangs on GitHub Actions CI - no audio device",
    )
    async def test_long_running_daemon(self):
        """Test daemon running for extended period"""
        daemon = VoiceDaemon()
        await daemon.start()

        # Mock ResilientVoice.speak to avoid hanging on CI (no audio device).
        # We're testing daemon queue management, not actual speech synthesis.
        with patch.object(
            ResilientVoice, "speak", new_callable=AsyncMock, return_value=True
        ):
            # Queue many items
            for i in range(10):
                await daemon.speak(f"Message {i}")

            # Wait for processing
            await asyncio.sleep(2)

            stats = daemon.get_stats()
            # Daemon should still be running
            assert stats["running"] is True

        await daemon.stop()

    @pytest.mark.asyncio
    async def test_fallback_exhaustion(self):
        """Test what happens when all fallbacks fail"""
        config = VoiceConfig()
        ResilientVoice(config)

        # Mock all fallback methods to fail
        for fallback in ResilientVoice._fallbacks:
            fallback.method = AsyncMock(return_value=False)

        # Should still return True (best effort)
        result = await speak("All fallbacks failed")
        assert result is True


class TestErrorHandling:
    """Test error handling"""

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling"""
        config = VoiceConfig(timeout=0.001)  # Very short timeout
        ResilientVoice(config)

        result = await speak("This might timeout")
        # Should still try fallbacks
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_subprocess_error_handling(self):
        """Test subprocess error handling"""
        config = VoiceConfig()
        ResilientVoice(config)

        # Try speaking with invalid characters (but safe)
        result = await speak("Test\n\r\0")
        assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_full_workflow():
    """Full workflow test"""
    config = VoiceConfig(default_voice="Karen", default_rate=155)

    # Initialize
    ResilientVoice(config)
    daemon = VoiceDaemon(config)
    await daemon.start()

    # Speak
    await speak("Voice system initialized")

    # Queue in daemon
    await daemon.speak("Task starting", voice="Moira")

    # Play sound
    await play_sound("notification")

    # More speech
    await speak("Task complete")
    await play_sound("success")

    # Get stats
    stats = get_voice_stats()
    assert stats is not None

    # Cleanup
    await daemon.stop()
