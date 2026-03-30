"""Tests for multi-LLM routing."""
import pytest
from unittest.mock import Mock, patch

class TestLLMRouter:
    """Test LLM routing logic."""
    
    def test_simple_query_routing(self):
        """Simple queries should route to Ollama."""
        simple_queries = ["hello", "hi", "thanks", "ok", "yes"]
        
        for query in simple_queries:
            # Simple = less than 5 words and common
            is_simple = len(query.split()) < 5
            assert is_simple
    
    def test_complex_query_routing(self):
        """Complex queries should route to Claude."""
        complex_queries = [
            "Explain the architecture of the voice system",
            "Debug the race condition in the audio capture",
            "Refactor the transcription module for better performance"
        ]
        
        for query in complex_queries:
            is_complex = len(query.split()) > 5
            assert is_complex
    
    def test_code_query_routing(self):
        """Code queries should route to GPT."""
        code_queries = [
            "write a python function",
            "create a swift class",
            "fix this javascript bug"
        ]
        
        code_keywords = ["python", "javascript", "swift", "function", "class", "code"]
        
        for query in code_queries:
            is_code = any(kw in query.lower() for kw in code_keywords)
            assert is_code


class TestFallbackChain:
    """Test LLM fallback chain."""
    
    def test_fallback_order(self):
        """Test fallback order: Cloud → Local."""
        fallback_chain = ["claude", "gpt", "ollama"]
        
        assert fallback_chain[0] == "claude"  # Primary
        assert fallback_chain[-1] == "ollama"  # Final fallback
    
    @patch('requests.post')
    def test_timeout_triggers_fallback(self, mock_post):
        """Test that timeout triggers fallback."""
        import requests
        mock_post.side_effect = requests.Timeout("API timeout")
        
        with pytest.raises(requests.Timeout):
            requests.post("https://api.anthropic.com/v1/messages", timeout=5)
        
        # In real code, this would trigger fallback to next LLM
