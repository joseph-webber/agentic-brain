"""Tests for audio capture functionality."""
import pytest
from unittest.mock import Mock, patch
import numpy as np

class TestAudioCapture:
    """Test audio capture module."""
    
    def test_sample_rate_conversion(self):
        """Test 24kHz to 16kHz resampling."""
        # Simulate AirPods 24kHz audio
        original = np.random.randn(24000)  # 1 second at 24kHz
        
        # Resample to 16kHz
        from scipy.signal import resample
        resampled = resample(original, 16000)
        
        assert len(resampled) == 16000
    
    def test_silence_detection(self):
        """Test VAD silence detection."""
        # Silent audio (near zero)
        silent = np.zeros(16000) + np.random.randn(16000) * 0.001
        
        # Speech audio (higher amplitude)
        speech = np.random.randn(16000) * 0.1
        
        # Threshold check
        silent_rms = np.sqrt(np.mean(silent**2))
        speech_rms = np.sqrt(np.mean(speech**2))
        
        assert silent_rms < 0.01
        assert speech_rms > 0.01
    
    def test_audio_normalization(self):
        """Test audio level normalization."""
        quiet = np.random.randn(16000) * 0.01
        normalized = quiet / np.max(np.abs(quiet)) * 0.8
        
        assert np.max(np.abs(normalized)) == pytest.approx(0.8, rel=0.01)


class TestDeviceSelection:
    """Test audio device selection."""
    
    @patch('sounddevice.query_devices')
    def test_find_airpods(self, mock_query):
        """Test finding AirPods in device list."""
        mock_query.return_value = [
            {'name': 'MacBook Air Microphone', 'max_input_channels': 1},
            {'name': "User's AirPods Max", 'max_input_channels': 1},
        ]
        
        devices = mock_query()
        airpods = [d for d in devices if 'AirPods' in d['name']]
        
        assert len(airpods) == 1
        assert 'User' in airpods[0]['name']
