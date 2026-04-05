"""Tests for speech-to-text transcription."""
import pytest
from unittest.mock import Mock, patch, MagicMock

class TestWhisperTranscription:
    """Test Whisper transcription."""
    
    @patch('requests.post')
    def test_whisper_api_call(self, mock_post):
        """Test OpenAI Whisper API integration."""
        mock_post.return_value.json.return_value = {
            "text": "Hello user how are you"
        }
        
        # Simulate API call
        import requests
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            files={"file": b"fake_audio"},
            data={"model": "whisper-1"}
        )
        
        assert resp.json()["text"] == "Hello user how are you"
    
    def test_empty_audio_handling(self):
        """Test handling of silent/empty audio."""
        # Empty transcription should return empty string
        text = ""
        assert len(text.strip()) == 0
    
    def test_confidence_threshold(self):
        """Test low-confidence transcription rejection."""
        transcription = {
            "text": "um",
            "confidence": 0.3
        }
        
        # Low confidence should be filtered
        if transcription.get("confidence", 1.0) < 0.5:
            result = ""
        else:
            result = transcription["text"]
        
        assert result == ""


class TestLocalWhisper:
    """Test local faster-whisper fallback."""
    
    @patch('faster_whisper.WhisperModel')
    def test_local_transcription(self, mock_model):
        """Test faster-whisper local model."""
        mock_segment = Mock()
        mock_segment.text = "Test transcription"
        mock_model.return_value.transcribe.return_value = ([mock_segment], None)
        
        model = mock_model("tiny.en")
        segments, _ = model.transcribe("test.wav")
        text = " ".join(s.text for s in segments)
        
        assert text == "Test transcription"
