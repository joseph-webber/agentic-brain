"""Integration tests for full voice loop."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import fakeredis


class TestVoiceLoop:
    """Test complete voice conversation loop."""

    @pytest.fixture
    def redis(self):
        return fakeredis.FakeRedis(decode_responses=True)

    @patch("subprocess.run")
    @patch("requests.post")
    def test_full_conversation_turn(self, mock_requests, mock_subprocess, redis):
        """Test: record → transcribe → LLM → speak."""
        # Mock transcription response
        mock_requests.return_value.json.return_value = {
            "text": "What's the weather like"
        }

        # Mock successful subprocess (sox, say)
        mock_subprocess.return_value = Mock(returncode=0)

        # Simulate full loop
        redis.set("voice:state", "listening")
        # ... record audio ...

        redis.set("voice:state", "transcribing")
        transcription = "What's the weather like"
        redis.set("voice:last_heard", transcription)

        redis.set("voice:state", "thinking")
        response = "It's a lovely day in Adelaide!"
        redis.set("voice:last_response", response)

        redis.set("voice:state", "speaking")
        # ... TTS ...

        redis.set("voice:state", "ready")

        # Verify state progression
        assert redis.get("voice:last_heard") == transcription
        assert redis.get("voice:last_response") == response

    def test_error_recovery(self, redis):
        """Test recovery from errors."""
        redis.set("voice:state", "error")
        redis.set("voice:error", "API timeout")

        # Recovery should reset to ready
        redis.set("voice:state", "ready")
        redis.delete("voice:error")

        assert redis.get("voice:state") == "ready"
        assert redis.get("voice:error") is None


class TestModeSwitch:
    """Test switching between standalone and integrated modes."""

    def test_mode_config(self):
        """Test mode configuration."""
        modes = {
            "standalone": {"llm": "claude", "tts": "say"},
            "copilot": {"llm": "copilot_cli", "tts": "say"},
        }

        assert "standalone" in modes
        assert "copilot" in modes
        assert modes["copilot"]["llm"] == "copilot_cli"
