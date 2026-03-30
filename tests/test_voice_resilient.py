# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Tests for Resilient Voice System

Tests verify that voice always works with fallbacks,
and that the daemon continues operating even under failure conditions.
All subprocess calls are mocked to prevent real audio output.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.timeout(30)

# Import to access and reset global daemon instance
import agentic_brain.voice.resilient as resilient_module
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
from tests.fixtures.voice_test_phrases import pick_voice_phrase, pick_voice_phrases


@pytest.fixture(autouse=True)
def _mock_voice_subprocess():
    """Prevent real audio by mocking all subprocess entry points."""
    mock_proc = MagicMock()
    mock_proc.wait.return_value = 0
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.poll.return_value = 0
    mock_proc.pid = 12345

    mock_async_proc = AsyncMock()
    mock_async_proc.wait = AsyncMock(return_value=0)
    mock_async_proc.returncode = 0
    mock_async_proc.communicate = AsyncMock(return_value=(b"", b""))
    mock_async_proc.pid = 12345

    with (
        patch(
            "agentic_brain.voice.serializer.subprocess.Popen",
            return_value=mock_proc,
        ),
        patch(
            "agentic_brain.voice.serializer.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=""),
        ),
        patch(
            "asyncio.create_subprocess_exec",
            return_value=mock_async_proc,
        ),
    ):
        yield


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


class TestResilientVoice:
    """Test ResilientVoice with fallbacks (subprocess mocked via fixture)"""

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

        result = await speak(
            pick_voice_phrase("test_speak_with_default_voice", "technology_quotes")
        )
        # Should succeed (or at least try all fallbacks)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_speak_with_custom_voice(self, setup):
        """Test speaking with custom voice"""
        config = VoiceConfig()
        ResilientVoice(config)

        result = await speak(
            pick_voice_phrase("test_speak_with_custom_voice", "poetry_snippets"),
            voice="Moira",
            rate=140,
        )
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

        result = await speak(
            pick_voice_phrase("test_speak_without_fallbacks", "australia_facts")
        )
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
        phrases = pick_voice_phrases("test_daemon_queue_speak", 3)
        await daemon.speak(phrases[0])
        await daemon.speak(phrases[1], voice="Moira")
        await daemon.speak(phrases[2], rate=140)

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
        await daemon.speak(
            pick_voice_phrase("test_daemon_error_handling", "tongue_twisters"),
            voice="InvalidVoice",
        )

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

    @pytest.fixture
    async def reset_daemon(self):
        """Reset global daemon instance before and after test"""
        # Reset before test
        if resilient_module._daemon_instance is not None:
            try:
                await resilient_module._daemon_instance.stop()
            except Exception:
                pass
        resilient_module._daemon_instance = None

        yield

        # Cleanup after test
        if resilient_module._daemon_instance is not None:
            try:
                await resilient_module._daemon_instance.stop()
            except Exception:
                pass
        resilient_module._daemon_instance = None

    @pytest.mark.asyncio
    async def test_speak_function(self):
        """Test global speak function"""
        result = await speak(
            pick_voice_phrase("test_speak_function", "multilingual_greetings")
        )
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_speak_via_daemon_function(self):
        """Test daemon speak function"""
        await speak_via_daemon(
            pick_voice_phrase("test_speak_via_daemon_function", "status_updates")
        )
        # Should not raise

    @pytest.mark.asyncio
    async def test_get_daemon_function(self, reset_daemon):
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


class TestIntegration:
    """Integration tests (subprocess mocked via fixture)"""

    @pytest.mark.asyncio
    async def test_speak_and_sound(self):
        """Test speaking and playing sound"""
        phrase = pick_voice_phrase("test_speak_and_sound", "status_updates")
        with (
            patch.object(
                ResilientVoice, "speak", new_callable=AsyncMock, return_value=True
            ) as mock_speak,
            patch.object(
                SoundEffects, "play", new_callable=AsyncMock, return_value=True
            ) as mock_play,
        ):
            # Speak
            await speak(phrase)

            # Play sound
            await play_sound("success")

        mock_speak.assert_awaited_once_with(phrase, "Karen", 155)
        mock_play.assert_awaited_once_with("success")

    @pytest.mark.asyncio
    async def test_daemon_multiple_speakers(self):
        """Test daemon with multiple concurrent speakers"""
        daemon = VoiceDaemon()
        await daemon.start()

        with patch.object(
            ResilientVoice, "speak", new_callable=AsyncMock, return_value=True
        ) as mock_speak:
            # Queue multiple at once
            phrases = pick_voice_phrases(
                "test_daemon_multiple_speakers", 3, "status_updates"
            )
            tasks = [
                daemon.speak(phrases[0]),
                daemon.speak(phrases[1], voice="Moira"),
                daemon.speak(phrases[2], voice="Tingting"),
            ]
            await asyncio.gather(*tasks)

            await asyncio.sleep(2)

            stats = daemon.get_stats()
            assert stats["processed"] == 3
            assert stats["errors"] == 0
            assert mock_speak.await_count == 3

        await daemon.stop()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
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
                await daemon.speak(
                    pick_voice_phrase(
                        f"test_long_running_daemon_{i}",
                        "technology_quotes",
                        "australia_facts",
                    )
                )

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
        result = await speak(
            pick_voice_phrase("test_fallback_exhaustion", "status_updates")
        )
        assert result is True


class TestErrorHandling:
    """Test error handling"""

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling"""
        config = VoiceConfig(timeout=0.001)  # Very short timeout
        ResilientVoice(config)

        result = await speak(
            pick_voice_phrase("test_timeout_handling", "pronunciation_practice")
        )
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
    await speak(pick_voice_phrase("test_full_workflow_init", "status_updates"))

    # Queue in daemon
    await daemon.speak(
        pick_voice_phrase("test_full_workflow_daemon", "technology_quotes"),
        voice="Moira",
    )

    # Play sound
    await play_sound("notification")

    # More speech
    await speak(pick_voice_phrase("test_full_workflow_complete", "poetry_snippets"))
    await play_sound("success")

    # Get stats
    stats = get_voice_stats()
    assert stats is not None

    # Cleanup
    await daemon.stop()
