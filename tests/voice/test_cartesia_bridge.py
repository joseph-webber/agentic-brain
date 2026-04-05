# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for CartesiaTTS bridge with LiveVoiceMode."""

from __future__ import annotations

import threading
import time
from typing import Iterator, List
from unittest.mock import MagicMock, patch

import pytest


class TestCartesiaStreamPlayer:
    """Tests for the streaming audio player."""

    def test_player_init(self) -> None:
        """Player initializes with default sample rate."""
        from agentic_brain.voice.cartesia_bridge import CartesiaStreamPlayer

        player = CartesiaStreamPlayer()
        assert player.sample_rate == 44100
        assert player._stream is None

    def test_player_custom_sample_rate(self) -> None:
        """Player accepts custom sample rate."""
        from agentic_brain.voice.cartesia_bridge import CartesiaStreamPlayer

        player = CartesiaStreamPlayer(sample_rate=22050)
        assert player.sample_rate == 22050

    def test_pcm_f32le_to_wav(self) -> None:
        """PCM to WAV conversion produces valid header."""
        from agentic_brain.voice.cartesia_bridge import CartesiaStreamPlayer

        player = CartesiaStreamPlayer(sample_rate=44100)

        # Create minimal PCM data (4 bytes = 1 float32 sample)
        import struct

        pcm_data = struct.pack("<f", 0.5)
        wav_data = player._pcm_f32le_to_wav(pcm_data)

        # Check WAV header
        assert wav_data[:4] == b"RIFF"
        assert wav_data[8:12] == b"WAVE"
        assert wav_data[12:16] == b"fmt "

    def test_stop_sets_flag(self) -> None:
        """Stop sets the playing flag to False."""
        from agentic_brain.voice.cartesia_bridge import CartesiaStreamPlayer

        player = CartesiaStreamPlayer()
        player._playing = True
        player.stop()
        assert player._playing is False


class TestCartesiaLiveMode:
    """Tests for the CartesiaTTS-connected LiveVoiceMode."""

    def test_init_defaults(self) -> None:
        """CartesiaLiveMode initializes with sensible defaults."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()
        assert mode._voice == "Karen"
        assert mode._rate == 160
        assert mode._sample_rate == 44100
        assert mode._cartesia_calls == 0
        assert mode._fallback_calls == 0

    def test_init_custom_voice(self) -> None:
        """CartesiaLiveMode accepts custom voice settings."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode(voice="Samantha", rate=180)
        assert mode._voice == "Samantha"
        assert mode._rate == 180

    def test_status_without_start(self) -> None:
        """Status works before start() is called."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()
        status = mode.status()
        assert "backend" in status
        assert status["cartesia_calls"] == 0
        assert status["fallback_calls"] == 0

    def test_is_active_before_start(self) -> None:
        """is_active is False before start()."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()
        assert mode.is_active is False

    def test_start_stop_lifecycle(self) -> None:
        """Start and stop work correctly."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()

        # Mock the speak function to avoid actual audio
        mode._speak_cartesia = MagicMock(return_value=True)

        mode.start(voice="Karen", rate=155)
        assert mode.is_active is True

        mode.stop()
        assert mode.is_active is False

    def test_feed_accumulates_buffer(self) -> None:
        """Feed accumulates text in the underlying LiveVoiceMode."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()
        mode._speak_cartesia = MagicMock(return_value=True)

        mode.start()
        mode.feed("Hello ")
        mode.feed("friend")

        # Check buffer accumulated
        live_mode = mode._get_live_mode()
        assert "Hello" in live_mode._buffer or "friend" in live_mode._buffer

        mode.stop()

    def test_feed_triggers_speak_on_sentence(self) -> None:
        """Feed triggers speech when sentence boundary is reached."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()
        speak_mock = MagicMock(return_value=True)
        mode._speak_cartesia = speak_mock

        mode.start()
        mode.feed("Hello there.")  # Complete sentence

        # Sentence should have been spoken
        assert speak_mock.call_count >= 1

        mode.stop()

    def test_flush_speaks_remaining(self) -> None:
        """Flush speaks whatever is left in the buffer."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()
        speak_mock = MagicMock(return_value=True)
        mode._speak_cartesia = speak_mock

        mode.start()
        mode.feed("Hello")  # No sentence boundary
        mode.flush()

        # Should have spoken the partial text
        assert speak_mock.call_count >= 1

        mode.stop()

    def test_interrupt_stops_playback(self) -> None:
        """Interrupt stops both LiveVoiceMode and player."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()
        mode._speak_cartesia = MagicMock(return_value=True)
        mode._player = MagicMock()

        mode.start()
        mode.feed("Hello")
        mode.interrupt()

        assert mode.is_interrupted is True
        mode._player.stop.assert_called_once()

        mode.stop()

    @patch.dict("os.environ", {"CARTESIA_API_KEY": ""})
    def test_fallback_when_no_api_key(self) -> None:
        """Falls back to macOS say when API key not set."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()

        # _get_cartesia should return None
        assert mode._get_cartesia() is None

        status = mode.status()
        assert status["backend"] == "macOS_say"


class TestSingleton:
    """Tests for singleton behavior."""

    def test_get_cartesia_live_mode_singleton(self) -> None:
        """get_cartesia_live_mode returns the same instance."""
        from agentic_brain.voice.cartesia_bridge import (
            _set_cartesia_live_mode_for_testing,
            get_cartesia_live_mode,
        )

        # Reset singleton
        _set_cartesia_live_mode_for_testing(None)

        mode1 = get_cartesia_live_mode()
        mode2 = get_cartesia_live_mode()

        assert mode1 is mode2

        # Clean up
        _set_cartesia_live_mode_for_testing(None)

    def test_set_for_testing(self) -> None:
        """_set_cartesia_live_mode_for_testing replaces singleton."""
        from agentic_brain.voice.cartesia_bridge import (
            CartesiaLiveMode,
            _set_cartesia_live_mode_for_testing,
            get_cartesia_live_mode,
        )

        custom = CartesiaLiveMode(voice="Moira")
        _set_cartesia_live_mode_for_testing(custom)

        result = get_cartesia_live_mode()
        assert result is custom
        assert result._voice == "Moira"

        # Clean up
        _set_cartesia_live_mode_for_testing(None)


class TestIntegration:
    """Integration tests (require mocked Cartesia)."""

    def test_full_flow_with_mock_cartesia(self) -> None:
        """Full flow: feed tokens → sentence → Cartesia → audio."""
        from agentic_brain.voice.cartesia_bridge import (
            CartesiaLiveMode,
            CartesiaStreamPlayer,
        )

        mode = CartesiaLiveMode()

        # Track what was spoken
        spoken_texts: List[str] = []

        def mock_speak(text: str, voice: str, rate: int) -> bool:
            spoken_texts.append(text)
            return True

        mode._speak_cartesia = mock_speak

        # Simulate LLM token stream
        mode.start()
        tokens = ["Hello ", "friend, ", "how ", "are ", "you ", "today?"]
        for token in tokens:
            mode.feed(token)

        mode.stop()

        # Should have spoken at least one sentence
        assert len(spoken_texts) >= 1
        assert any("Hello" in text for text in spoken_texts)

    def test_multiple_sentences(self) -> None:
        """Multiple sentences are spoken separately."""
        from agentic_brain.voice.cartesia_bridge import CartesiaLiveMode

        mode = CartesiaLiveMode()

        spoken_texts: List[str] = []

        def mock_speak(text: str, voice: str, rate: int) -> bool:
            spoken_texts.append(text)
            return True

        mode._speak_cartesia = mock_speak

        mode.start()
        mode.feed("First sentence. ")
        mode.feed("Second sentence. ")
        mode.feed("Third sentence.")
        mode.flush()
        mode.stop()

        # Should have spoken multiple times
        assert len(spoken_texts) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
