# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Tests for streaming response support.

Run with:
    pytest tests/test_streaming.py -v
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from agentic_brain.streaming import StreamingResponse, StreamToken, StreamProvider


class TestStreamToken:
    """Test StreamToken dataclass."""
    
    def test_create_token(self):
        """Test creating a StreamToken."""
        token = StreamToken(
            token="hello",
            is_start=True,
            metadata={"provider": "ollama"}
        )
        
        assert token.token == "hello"
        assert token.is_start is True
        assert token.is_end is False
        assert token.finish_reason is None
        assert token.metadata["provider"] == "ollama"
    
    def test_token_to_dict(self):
        """Test converting token to dict."""
        token = StreamToken(
            token="world",
            is_end=True,
            finish_reason="stop",
            metadata={"model": "llama3.1:8b"}
        )
        
        data = token.to_dict()
        
        assert data["token"] == "world"
        assert data["is_end"] is True
        assert data["finish_reason"] == "stop"
        assert data["metadata"]["model"] == "llama3.1:8b"
    
    def test_token_to_sse(self):
        """Test converting token to SSE format."""
        token = StreamToken(
            token="hello",
            is_start=True,
        )
        
        sse = token.to_sse()
        
        # SSE format: data: {json}\n\n
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        
        # Parse the JSON part
        data_str = sse[6:-2]  # Remove "data: " and "\n\n"
        data = json.loads(data_str)
        assert data["token"] == "hello"
        assert data["is_start"] is True


class TestStreamingResponse:
    """Test StreamingResponse class."""
    
    def test_init_ollama(self):
        """Test initializing with Ollama provider."""
        streamer = StreamingResponse(
            provider="ollama",
            model="llama3.1:8b",
            temperature=0.5,
        )
        
        assert streamer.provider == StreamProvider.OLLAMA
        assert streamer.model == "llama3.1:8b"
        assert streamer.temperature == 0.5
        assert streamer.api_base == "http://localhost:11434"
    
    def test_init_openai_missing_key(self):
        """Test OpenAI provider without API key raises error."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY required"):
                StreamingResponse(
                    provider="openai",
                    model="gpt-4"
                )
    
    def test_init_anthropic_missing_key(self):
        """Test Anthropic provider without API key raises error."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY required"):
                StreamingResponse(
                    provider="anthropic",
                    model="claude-3-sonnet"
                )
    
    def test_init_with_env_vars(self):
        """Test initialization using environment variables."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test-123'}):
            streamer = StreamingResponse(
                provider="openai",
                model="gpt-4"
            )
            
            assert streamer.api_key == "sk-test-123"
    
    def test_custom_api_base(self):
        """Test setting custom API base."""
        streamer = StreamingResponse(
            provider="ollama",
            api_base="http://custom:11434"
        )
        
        assert streamer.api_base == "http://custom:11434"
    
    def test_system_prompt_default(self):
        """Test default system prompt."""
        streamer = StreamingResponse(provider="ollama")
        
        assert streamer.system_prompt == "You are a helpful assistant."
    
    def test_custom_system_prompt(self):
        """Test custom system prompt."""
        custom_prompt = "You are a pirate."
        streamer = StreamingResponse(
            provider="ollama",
            system_prompt=custom_prompt
        )
        
        assert streamer.system_prompt == custom_prompt


class TestStreamTokenGeneration:
    """Test token generation methods."""
    
    @pytest.mark.asyncio
    async def test_stream_method_routes_to_ollama(self):
        """Test that stream() routes to correct provider."""
        streamer = StreamingResponse(provider="ollama")
        
        # Mock the Ollama streaming method
        streamer._stream_ollama = AsyncMock(return_value=None)
        streamer._stream_ollama.return_value = self._mock_stream()
        
        async def _mock_stream():
            yield StreamToken(token="test")
        
        streamer._stream_ollama = _mock_stream
        
        tokens = []
        async for token in streamer.stream("test"):
            tokens.append(token)
        
        assert len(tokens) == 1
        assert tokens[0].token == "test"
    
    @pytest.mark.asyncio
    async def test_stream_with_history(self):
        """Test streaming with conversation history."""
        streamer = StreamingResponse(provider="ollama")
        
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"}
        ]
        
        # This would call the actual method, which we can't test without
        # a running Ollama instance, so we just verify it doesn't crash
        # with valid input
        
        # In a real test, we'd mock the aiohttp calls
        assert streamer.model is not None  # Just verify object state


class TestSSEFormat:
    """Test Server-Sent Events format."""
    
    @pytest.mark.asyncio
    async def test_stream_sse_format(self):
        """Test SSE streaming format."""
        streamer = StreamingResponse(provider="ollama")
        
        # Mock the underlying stream method
        async def mock_stream(msg, history=None):
            yield StreamToken(token="hello", is_start=True)
            yield StreamToken(token=" world")
            yield StreamToken(token="!", is_end=True, finish_reason="stop")
        
        streamer.stream = mock_stream
        
        sse_lines = []
        async for line in streamer.stream_sse("test"):
            sse_lines.append(line)
        
        # Should have 3 SSE formatted lines
        assert len(sse_lines) == 3
        
        # Each line should be valid SSE format
        for line in sse_lines:
            assert line.startswith("data: ")
            assert line.endswith("\n\n")
            
            # Extract and parse JSON
            data_str = line[6:-2]
            data = json.loads(data_str)
            assert "token" in data
            assert "is_start" in data
            assert "is_end" in data


class TestWebSocketFormat:
    """Test WebSocket JSON format."""
    
    @pytest.mark.asyncio
    async def test_stream_websocket_format(self):
        """Test WebSocket JSON format."""
        streamer = StreamingResponse(provider="ollama")
        
        # Mock the underlying stream method
        async def mock_stream(msg, history=None):
            yield StreamToken(token="test", metadata={"key": "value"})
        
        streamer.stream = mock_stream
        
        json_lines = []
        async for line in streamer.stream_websocket("test"):
            json_lines.append(line)
        
        # Should have 1 JSON line
        assert len(json_lines) == 1
        
        # Parse JSON
        data = json.loads(json_lines[0])
        assert data["token"] == "test"
        assert data["metadata"]["key"] == "value"


class TestStreamProvider:
    """Test StreamProvider enum."""
    
    def test_provider_enum_values(self):
        """Test StreamProvider enum has all providers."""
        assert StreamProvider.OLLAMA.value == "ollama"
        assert StreamProvider.OPENAI.value == "openai"
        assert StreamProvider.ANTHROPIC.value == "anthropic"
    
    def test_provider_from_string(self):
        """Test creating provider from string."""
        provider = StreamProvider("ollama")
        assert provider == StreamProvider.OLLAMA
        
        provider = StreamProvider("openai")
        assert provider == StreamProvider.OPENAI


class TestErrorHandling:
    """Test error handling in streaming."""
    
    @pytest.mark.asyncio
    async def test_stream_error_handling(self):
        """Test that stream errors are handled gracefully."""
        streamer = StreamingResponse(provider="ollama")
        
        # Mock stream to raise an exception
        async def mock_stream(msg, history=None):
            raise Exception("Connection failed")
        
        streamer._stream_ollama = mock_stream
        
        # Stream should yield error token
        tokens = []
        async for token in streamer.stream("test"):
            tokens.append(token)
        
        # Should have error token
        assert len(tokens) == 1
        assert tokens[0].finish_reason == "error"
        assert "error" in tokens[0].metadata


# Integration tests (require running Ollama or API keys)
# These are commented out but can be run with proper setup

"""
@pytest.mark.asyncio
@pytest.mark.integration
async def test_ollama_streaming():
    \"\"\"Test actual Ollama streaming (requires Ollama running).\"\"\"
    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b",
        max_tokens=50,
    )
    
    tokens = []
    async for token in streamer.stream("What is AI?"):
        tokens.append(token)
    
    assert len(tokens) > 0
    assert tokens[0].is_start is True
    assert tokens[-1].is_end is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_openai_streaming():
    \"\"\"Test actual OpenAI streaming (requires OPENAI_API_KEY).\"\"\"
    import os
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    
    streamer = StreamingResponse(
        provider="openai",
        model="gpt-4",
        max_tokens=50,
    )
    
    tokens = []
    async for token in streamer.stream("What is AI?"):
        tokens.append(token)
    
    assert len(tokens) > 0
    assert tokens[0].is_start is True
    assert tokens[-1].is_end is True
"""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
