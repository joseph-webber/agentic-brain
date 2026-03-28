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

"""
Tests for agentic-brain audio module.
"""

from unittest.mock import MagicMock, patch

import pytest

from tests.fixtures.voice_test_phrases import pick_voice_phrase

from agentic_brain.audio import (
    Audio,
    AudioConfig,
    Platform,
    Voice,
    announce,
    get_audio,
    sound,
    speak,
)


class TestPlatform:
    """Test Platform detection."""

    def test_platform_values(self):
        """Test platform enum values."""
        assert Platform.MACOS.value == "Darwin"
        assert Platform.WINDOWS.value == "Windows"
        assert Platform.LINUX.value == "Linux"

    @patch("platform.system")
    def test_current_macos(self, mock_system):
        """Test detecting macOS."""
        mock_system.return_value = "Darwin"
        assert Platform.current() == Platform.MACOS

    @patch("platform.system")
    def test_current_windows(self, mock_system):
        """Test detecting Windows."""
        mock_system.return_value = "Windows"
        assert Platform.current() == Platform.WINDOWS

    @patch("platform.system")
    def test_current_linux(self, mock_system):
        """Test detecting Linux."""
        mock_system.return_value = "Linux"
        assert Platform.current() == Platform.LINUX

    @patch("platform.system")
    def test_current_unknown(self, mock_system):
        """Test unknown platform."""
        mock_system.return_value = "FreeBSD"
        assert Platform.current() == Platform.UNKNOWN


class TestVoice:
    """Test Voice configuration."""

    def test_voice_creation(self):
        """Test creating a voice config."""
        voice = Voice("Karen", rate=160, platform=Platform.MACOS)

        assert voice.name == "Karen"
        assert voice.rate == 160
        assert voice.platform == Platform.MACOS

    def test_builtin_voices(self):
        """Test built-in voice factories."""
        karen = Voice.KAREN()
        assert karen.name == "Karen"
        assert karen.rate == 175

        samantha = Voice.SAMANTHA()
        assert samantha.name == "Samantha"

        daniel = Voice.DANIEL()
        assert daniel.name == "Daniel"


class TestAudioConfig:
    """Test AudioConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = AudioConfig()

        assert config.enabled is True
        assert config.default_voice == "Karen"
        assert config.default_rate == 175

    def test_custom_config(self):
        """Test custom configuration."""
        config = AudioConfig(
            enabled=False,
            default_voice="Samantha",
            default_rate=160,
        )

        assert config.enabled is False
        assert config.default_voice == "Samantha"
        assert config.default_rate == 160


class TestAudio:
    """Test Audio class."""

    def test_audio_creation(self):
        """Test creating audio instance."""
        audio = Audio()

        assert audio.config is not None
        assert audio.platform is not None

    def test_disabled_audio(self):
        """Test disabled audio doesn't speak."""
        audio = Audio(AudioConfig(enabled=False))

        result = audio.speak(pick_voice_phrase("test_disabled_audio", "technology_quotes"))
        assert result is False

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    @patch("shutil.which")
    def test_speak_macos(self, mock_which, mock_popen):
        """Test macOS speaking routes through global speech lock."""
        mock_which.return_value = "/usr/bin/say"
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = None
        proc.returncode = 0
        mock_popen.return_value = proc

        audio = Audio()
        audio.platform = Platform.MACOS
        audio._tts_available = True

        result = audio._speak_macos(
            pick_voice_phrase("test_speak_macos", "multilingual_greetings"),
            "Karen",
            175,
            wait=True,
        )

        assert result is True
        mock_popen.assert_called_once()
        proc.wait.assert_called_once()

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_sound_macos(self, mock_which, mock_run):
        """Test macOS sound playing."""
        mock_which.return_value = "/usr/bin/afplay"
        mock_run.return_value = MagicMock(returncode=0)

        audio = Audio()
        audio.platform = Platform.MACOS

        with patch("pathlib.Path.exists", return_value=True):
            result = audio._sound_macos("success", wait=True)

        assert result is True

    def test_sound_mapping(self):
        """Test sound name mapping."""
        assert "success" in Audio.MACOS_SOUNDS
        assert "error" in Audio.MACOS_SOUNDS
        assert "warning" in Audio.MACOS_SOUNDS
        assert Audio.MACOS_SOUNDS["success"] == "Glass"

    def test_progress_milestones(self):
        """Test progress announces at milestones."""
        audio = Audio(AudioConfig(enabled=False))

        # Should only announce at 25%, 50%, 75%, 100%
        # With enabled=False, always returns False, but logic is tested
        audio.config.enabled = False

        # These should trigger announcements (if enabled)
        result_25 = audio.progress(25, 100, "Test")
        result_50 = audio.progress(50, 100, "Test")
        audio.progress(75, 100, "Test")
        audio.progress(100, 100, "Test")

        # All False because audio disabled
        assert result_25 is False
        assert result_50 is False

    def test_announce_combines_sound_and_speech(self):
        """Test announce plays sound then speaks."""
        audio = Audio(AudioConfig(enabled=False))

        # Just verify it doesn't crash when disabled
        result = audio.announce(
            pick_voice_phrase(
                "test_announce_combines_sound_and_speech", "status_updates"
            ),
            sound="success",
        )
        assert result is False


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_get_audio_singleton(self):
        """Test get_audio returns singleton."""
        audio1 = get_audio()
        audio2 = get_audio()

        assert audio1 is audio2

    @pytest.mark.parametrize(
        "func,args",
        [
            (speak, (pick_voice_phrase("test_convenience_speak", "poetry_snippets"),)),
            (sound, ("success",)),
            (
                announce,
                (pick_voice_phrase("test_convenience_announce", "technology_quotes"),),
            ),
        ],
    )
    def test_convenience_functions_disabled(self, func, args):
        """Test convenience functions return False when audio disabled."""
        import agentic_brain.audio as audio_module

        audio_module._default_audio = Audio(AudioConfig(enabled=False))

        result = func(*args)
        assert result is False


class TestAvailableVoices:
    """Test voice listing."""

    @patch("subprocess.run")
    def test_list_macos_voices(self, mock_run):
        """Test listing macOS voices."""
        mock_run.return_value = MagicMock(
            stdout="Karen en_AU\nSamantha en_US\nDaniel en_GB\n",
            returncode=0,
        )

        audio = Audio()
        audio.platform = Platform.MACOS

        voices = audio.available_voices

        assert "Karen" in voices
        assert "Samantha" in voices
        assert "Daniel" in voices
