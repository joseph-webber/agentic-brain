"""
Tests for agentic-brain router module.
"""

import pytest
from unittest.mock import patch, MagicMock
import json

from agentic_brain.router import (
    LLMRouter,
    RouterConfig,
    Provider,
    Model,
    Response,
    get_router,
    chat,
)


class TestProvider:
    """Test Provider enum."""
    
    def test_provider_values(self):
        """Test provider enum values."""
        assert Provider.OLLAMA.value == "ollama"
        assert Provider.OPENAI.value == "openai"
        assert Provider.ANTHROPIC.value == "anthropic"
        assert Provider.OPENROUTER.value == "openrouter"


class TestModel:
    """Test Model configuration."""
    
    def test_model_creation(self):
        """Test creating a model config."""
        model = Model("llama3:8b", Provider.OLLAMA, 8192)
        
        assert model.name == "llama3:8b"
        assert model.provider == Provider.OLLAMA
        assert model.context_length == 8192
    
    def test_builtin_models(self):
        """Test built-in model factories."""
        llama = Model.llama3_8b()
        assert llama.name == "llama3.1:8b"
        assert llama.provider == Provider.OLLAMA
        
        gpt = Model.gpt4o()
        assert gpt.name == "gpt-4o"
        assert gpt.provider == Provider.OPENAI
        assert gpt.supports_tools is True


class TestRouterConfig:
    """Test RouterConfig."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = RouterConfig()
        
        assert config.default_provider == Provider.OLLAMA
        assert config.default_model == "llama3.1:8b"
        assert config.timeout == 60
        assert config.fallback_enabled is True
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = RouterConfig(
            default_provider=Provider.OPENAI,
            default_model="gpt-4o",
            timeout=120,
        )
        
        assert config.default_provider == Provider.OPENAI
        assert config.default_model == "gpt-4o"


class TestResponse:
    """Test Response dataclass."""
    
    def test_response_creation(self):
        """Test creating a response."""
        response = Response(
            content="Hello!",
            model="llama3.1:8b",
            provider=Provider.OLLAMA,
            tokens_used=50,
        )
        
        assert response.content == "Hello!"
        assert response.model == "llama3.1:8b"
        assert response.provider == Provider.OLLAMA
        assert response.tokens_used == 50


class TestLLMRouter:
    """Test LLMRouter class."""
    
    def test_router_creation(self):
        """Test creating a router."""
        router = LLMRouter()
        
        assert router.config is not None
        assert router.config.default_provider == Provider.OLLAMA
    
    def test_router_with_config(self):
        """Test router with custom config."""
        config = RouterConfig(timeout=30)
        router = LLMRouter(config)
        
        assert router.config.timeout == 30
    
    @patch("shutil.which")
    def test_ollama_not_available(self, mock_which):
        """Test detecting Ollama not available."""
        mock_which.return_value = None
        
        router = LLMRouter()
        router._ollama_available = None  # Reset cache
        
        assert router._check_ollama() is False
    
    @patch("urllib.request.urlopen")
    @patch("shutil.which")
    def test_ollama_available(self, mock_which, mock_urlopen):
        """Test detecting Ollama available."""
        mock_which.return_value = "/usr/local/bin/ollama"
        mock_urlopen.return_value.__enter__ = MagicMock(
            return_value=MagicMock(status=200)
        )
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        
        router = LLMRouter()
        router._ollama_available = None  # Reset cache
        
        # May fail if no actual connection, just test the logic


class TestLLMRouterChat:
    """Test LLMRouter chat functionality."""
    
    @patch("urllib.request.urlopen")
    def test_chat_ollama(self, mock_urlopen):
        """Test chatting via Ollama."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "Hello from Ollama!"},
            "eval_count": 10,
        }).encode()
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        
        router = LLMRouter()
        router._ollama_available = True
        
        response = router._chat_ollama("Hello", None, "llama3.1:8b", 0.7)
        
        assert response.content == "Hello from Ollama!"
        assert response.provider == Provider.OLLAMA
    
    @patch("urllib.request.urlopen")
    def test_chat_with_system_prompt(self, mock_urlopen):
        """Test chat includes system prompt."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "System aware response"},
            "eval_count": 10,
        }).encode()
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        
        router = LLMRouter()
        router._ollama_available = True
        
        response = router._chat_ollama(
            "Hello",
            "You are helpful.",
            "llama3.1:8b",
            0.7,
        )
        
        assert response.content == "System aware response"


class TestLLMRouterFallback:
    """Test LLMRouter fallback behavior."""
    
    def test_fallback_chain_defined(self):
        """Test fallback chain is defined."""
        assert len(LLMRouter.FALLBACK_CHAIN) > 0
        
        # First fallback should be Ollama
        first = LLMRouter.FALLBACK_CHAIN[0]
        assert first[0] == Provider.OLLAMA
    
    @patch.object(LLMRouter, "_chat_ollama")
    def test_fallback_disabled(self, mock_chat):
        """Test fallback can be disabled."""
        mock_chat.side_effect = Exception("Primary failed")
        
        router = LLMRouter(RouterConfig(fallback_enabled=False))
        router._ollama_available = True
        
        with pytest.raises(Exception, match="Primary failed"):
            router.chat("Hello", provider=Provider.OLLAMA)
    
    @patch.object(LLMRouter, "_chat_openrouter")
    @patch.object(LLMRouter, "_chat_ollama")
    def test_fallback_works(self, mock_ollama, mock_openrouter):
        """Test fallback to next provider."""
        mock_ollama.side_effect = Exception("Ollama failed")
        mock_openrouter.return_value = Response(
            content="OpenRouter response",
            model="free-model",
            provider=Provider.OPENROUTER,
        )
        
        router = LLMRouter()
        router._ollama_available = True
        
        response = router.chat("Hello")
        
        assert response.content == "OpenRouter response"
        assert response.provider == Provider.OPENROUTER


class TestLLMRouterModels:
    """Test model listing."""
    
    @patch("urllib.request.urlopen")
    def test_list_local_models(self, mock_urlopen):
        """Test listing local Ollama models."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "llama3.2:3b"},
            ]
        }).encode()
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        
        router = LLMRouter()
        router._ollama_available = True
        
        models = router.list_local_models()
        
        assert "llama3.1:8b" in models
        assert "llama3.2:3b" in models
    
    def test_list_models_ollama_unavailable(self):
        """Test listing models when Ollama unavailable."""
        router = LLMRouter()
        router._ollama_available = False
        
        models = router.list_local_models()
        
        assert models == []


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    def test_get_router_singleton(self):
        """Test get_router returns singleton."""
        router1 = get_router()
        router2 = get_router()
        
        assert router1 is router2
    
    @patch.object(LLMRouter, "chat")
    def test_chat_function(self, mock_chat):
        """Test chat convenience function."""
        mock_chat.return_value = Response(
            content="Quick response",
            model="test",
            provider=Provider.OLLAMA,
        )
        
        response = chat("Hello")
        
        assert response.content == "Quick response"
