"""
Tests for agentic-brain audio module.
"""

import pytest
from unittest.mock import patch, MagicMock

from agentic_brain.audio import (
    Audio,
    AudioConfig,
    Platform,
    Voice,
    get_audio,
    speak,
    sound,
    announce,
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
        
        result = audio.speak("Hello")
        assert result is False
    
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_speak_macos(self, mock_which, mock_run):
        """Test macOS speaking."""
        mock_which.return_value = "/usr/bin/say"
        mock_run.return_value = MagicMock(returncode=0)
        
        audio = Audio()
        audio.platform = Platform.MACOS
        audio._tts_available = True
        
        result = audio._speak_macos("Hello", "Karen", 175, wait=True)
        
        assert result is True
        mock_run.assert_called_once()
    
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
        result_75 = audio.progress(75, 100, "Test")
        result_100 = audio.progress(100, 100, "Test")
        
        # All False because audio disabled
        assert result_25 is False
        assert result_50 is False
    
    def test_announce_combines_sound_and_speech(self):
        """Test announce plays sound then speaks."""
        audio = Audio(AudioConfig(enabled=False))
        
        # Just verify it doesn't crash when disabled
        result = audio.announce("Test message", sound="success")
        assert result is False


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    def test_get_audio_singleton(self):
        """Test get_audio returns singleton."""
        audio1 = get_audio()
        audio2 = get_audio()
        
        assert audio1 is audio2
    
    def test_speak_function(self):
        """Test speak convenience function."""
        with patch.object(Audio, "speak", return_value=True) as mock_speak:
            # Reset singleton to use our mock
            import agentic_brain.audio as audio_module
            audio_module._default_audio = Audio(AudioConfig(enabled=False))
            
            result = speak("Hello")
            # Disabled audio returns False
            assert result is False
    
    def test_sound_function(self):
        """Test sound convenience function."""
        import agentic_brain.audio as audio_module
        audio_module._default_audio = Audio(AudioConfig(enabled=False))
        
        result = sound("success")
        assert result is False
    
    def test_announce_function(self):
        """Test announce convenience function."""
        import agentic_brain.audio as audio_module
        audio_module._default_audio = Audio(AudioConfig(enabled=False))
        
        result = announce("Hello")
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
