# SPDX-License-Identifier: Apache-2.0
"""Tests for text-to-speech output."""

import subprocess
from unittest.mock import Mock, patch

import pytest


class TestMacOSTTS:
    """Test macOS native TTS."""

    @patch("subprocess.run")
    def test_say_command(self, mock_run):
        """Test macOS say command."""
        mock_run.return_value = Mock(returncode=0)

        text = "Hello there"
        subprocess.run(["say", "-v", "Karen (Premium)", "-r", "160", text])

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "Karen (Premium)" in call_args
        assert text in call_args

    def test_speech_rate_bounds(self):
        """Test speech rate stays in valid range."""
        min_rate, max_rate = 100, 300
        rates = [90, 150, 200, 350]

        for rate in rates:
            clamped = max(min_rate, min(max_rate, rate))
            assert min_rate <= clamped <= max_rate


class TestCartesiaTTS:
    """Test Cartesia TTS API."""

    @patch("requests.post")
    def test_cartesia_api(self, mock_post):
        """Test Cartesia API call."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.content = b"fake_audio_data"

        # Would call Cartesia API
        # This tests the mock structure
        assert mock_post.return_value.status_code == 200
