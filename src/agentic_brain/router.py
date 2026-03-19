"""
LLM router with fallback chains.

Routes requests to appropriate LLM providers:
- Cloud (OpenRouter, OpenAI, Anthropic)
- Local (Ollama)
- Automatic fallback on failure

Example:
    >>> from agentic_brain import LLMRouter
    >>> router = LLMRouter()
    >>> response = router.chat("Hello, how are you?")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Any
import logging
import subprocess
import shutil
import json
import urllib.error

logger = logging.getLogger(__name__)


class Provider(Enum):
    """LLM providers."""
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    
    
@dataclass
class Model:
    """Model configuration."""
    name: str
    provider: Provider
    context_length: int = 4096
    supports_tools: bool = False
    
    # Common models
    @staticmethod
    def llama3_8b() -> "Model":
        return Model("llama3.1:8b", Provider.OLLAMA, 8192)
    
    @staticmethod
    def llama3_3b() -> "Model":
        return Model("llama3.2:3b", Provider.OLLAMA, 4096)
    
    @staticmethod
    def gpt4o() -> "Model":
        return Model("gpt-4o", Provider.OPENAI, 128000, True)
    
    @staticmethod
    def claude_sonnet() -> "Model":
        return Model("claude-3-sonnet", Provider.ANTHROPIC, 200000, True)


@dataclass
class RouterConfig:
    """Router configuration."""
    default_provider: Provider = Provider.OLLAMA
    default_model: str = "llama3.1:8b"
    ollama_host: str = "http://localhost:11434"
    timeout: int = 60
    max_retries: int = 3
    fallback_enabled: bool = True
    
    # API keys (loaded from env if not set)
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    openrouter_key: Optional[str] = None


@dataclass
class Message:
    """Chat message."""
    role: str  # system, user, assistant
    content: str


@dataclass
class Response:
    """LLM response."""
    content: str
    model: str
    provider: Provider
    tokens_used: int = 0
    finish_reason: str = "stop"


class LLMRouter:
    """
    Intelligent LLM routing with automatic fallback.
    
    Features:
    - Local-first (Ollama) for privacy and cost
    - Automatic fallback to cloud on failure
    - Multiple provider support
    - Simple chat interface
    
    Example:
        >>> router = LLMRouter()
        >>> 
        >>> # Simple chat
        >>> response = router.chat("What is Python?")
        >>> print(response.content)
        >>> 
        >>> # With system prompt
        >>> response = router.chat(
        ...     "Explain this code",
        ...     system="You are a helpful coding assistant"
        ... )
        >>> 
        >>> # Force specific provider
        >>> response = router.chat("Hello", provider=Provider.OPENAI)
    """
    
    # Fallback chain: try these in order
    FALLBACK_CHAIN = [
        (Provider.OLLAMA, "llama3.1:8b"),
        (Provider.OLLAMA, "llama3.2:3b"),
        (Provider.OPENROUTER, "meta-llama/llama-3-8b-instruct:free"),
    ]
    
    def __init__(self, config: Optional[RouterConfig] = None):
        """
        Initialize LLM router.
        
        Args:
            config: Router configuration
        """
        self.config = config or RouterConfig()
        self._ollama_available: Optional[bool] = None
        
    def _check_ollama(self) -> bool:
        """Check if Ollama is available."""
        if self._ollama_available is not None:
            return self._ollama_available
        
        try:
            # Check if ollama command exists
            if not shutil.which("ollama"):
                self._ollama_available = False
                return False
            
            # Check if server is running
            import urllib.request
            req = urllib.request.Request(
                f"{self.config.ollama_host}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self._ollama_available = resp.status == 200
                
        except (ConnectionError, TimeoutError, OSError, urllib.error.URLError) as e:
            # ConnectionError: network unreachable
            # TimeoutError: request timeout
            # OSError: system error
            # URLError: HTTP error
            logger.debug(f"Ollama availability check failed: {e}")
            self._ollama_available = False
        
        return self._ollama_available or False
    
    def chat(
        self,
        message: str,
        system: Optional[str] = None,
        provider: Optional[Provider] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Response:
        """
        Send chat message to LLM.
        
        Args:
            message: User message
            system: System prompt
            provider: Force specific provider
            model: Force specific model
            temperature: Response randomness (0-1)
            
        Returns:
            LLM response
            
        Example:
            >>> response = router.chat("Hello!")
            >>> print(response.content)
        """
        provider = provider or self.config.default_provider
        model = model or self.config.default_model
        
        # Try primary provider
        try:
            if provider == Provider.OLLAMA:
                return self._chat_ollama(message, system, model, temperature)
            elif provider == Provider.OPENAI:
                return self._chat_openai(message, system, model, temperature)
            elif provider == Provider.ANTHROPIC:
                return self._chat_anthropic(message, system, model, temperature)
            elif provider == Provider.OPENROUTER:
                return self._chat_openrouter(message, system, model, temperature)
        except Exception as e:
            logger.warning(f"Primary provider {provider} failed: {e}")
            
            if not self.config.fallback_enabled:
                raise
        
        # Fallback chain
        for fallback_provider, fallback_model in self.FALLBACK_CHAIN:
            if fallback_provider == provider:
                continue  # Skip the one that just failed
            
            try:
                logger.info(f"Trying fallback: {fallback_provider.value}/{fallback_model}")
                
                if fallback_provider == Provider.OLLAMA:
                    return self._chat_ollama(message, system, fallback_model, temperature)
                elif fallback_provider == Provider.OPENROUTER:
                    return self._chat_openrouter(message, system, fallback_model, temperature)
                    
            except Exception as e:
                logger.warning(f"Fallback {fallback_provider} failed: {e}")
                continue
        
        raise RuntimeError("All LLM providers failed")
    
    def _chat_ollama(
        self,
        message: str,
        system: Optional[str],
        model: str,
        temperature: float,
    ) -> Response:
        """Chat via Ollama."""
        if not self._check_ollama():
            raise RuntimeError("Ollama not available")
        
        import urllib.request
        
        payload = {
            "model": model,
            "messages": [],
            "stream": False,
            "options": {"temperature": temperature},
        }
        
        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].append({"role": "user", "content": message})
        
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.config.ollama_host}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
            result = json.loads(resp.read().decode())
        
        return Response(
            content=result["message"]["content"],
            model=model,
            provider=Provider.OLLAMA,
            tokens_used=result.get("eval_count", 0),
        )
    
    def _chat_openai(
        self,
        message: str,
        system: Optional[str],
        model: str,
        temperature: float,
    ) -> Response:
        """Chat via OpenAI."""
        import urllib.request
        import os
        
        api_key = self.config.openai_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OpenAI API key not configured")
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
            result = json.loads(resp.read().decode())
        
        choice = result["choices"][0]
        return Response(
            content=choice["message"]["content"],
            model=model,
            provider=Provider.OPENAI,
            tokens_used=result.get("usage", {}).get("total_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
        )
    
    def _chat_anthropic(
        self,
        message: str,
        system: Optional[str],
        model: str,
        temperature: float,
    ) -> Response:
        """Chat via Anthropic."""
        import urllib.request
        import os
        
        api_key = self.config.anthropic_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Anthropic API key not configured")
        
        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": message}],
            "temperature": temperature,
        }
        
        if system:
            payload["system"] = system
        
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
            result = json.loads(resp.read().decode())
        
        return Response(
            content=result["content"][0]["text"],
            model=model,
            provider=Provider.ANTHROPIC,
            tokens_used=result.get("usage", {}).get("input_tokens", 0) + 
                       result.get("usage", {}).get("output_tokens", 0),
        )
    
    def _chat_openrouter(
        self,
        message: str,
        system: Optional[str],
        model: str,
        temperature: float,
    ) -> Response:
        """Chat via OpenRouter (free models available)."""
        import urllib.request
        import os
        
        api_key = self.config.openrouter_key or os.environ.get("OPENROUTER_API_KEY")
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=data,
            headers=headers,
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
            result = json.loads(resp.read().decode())
        
        choice = result["choices"][0]
        return Response(
            content=choice["message"]["content"],
            model=model,
            provider=Provider.OPENROUTER,
            tokens_used=result.get("usage", {}).get("total_tokens", 0),
        )
    
    def list_local_models(self) -> list[str]:
        """List available Ollama models."""
        if not self._check_ollama():
            return []
        
        try:
            import urllib.request
            
            req = urllib.request.Request(
                f"{self.config.ollama_host}/api/tags",
                method="GET",
            )
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read().decode())
            
            return [m["name"] for m in result.get("models", [])]
            
        except (ConnectionError, TimeoutError, OSError, json.JSONDecodeError, urllib.error.URLError, ValueError) as e:
            # ConnectionError: network error
            # TimeoutError: request timeout
            # OSError: system error
            # json.JSONDecodeError: invalid JSON response
            # URLError: HTTP error
            # ValueError: JSON parse error
            logger.debug(f"Failed to fetch Ollama models: {e}")
            return []
    
    @property
    def is_local_available(self) -> bool:
        """Check if local LLM is available."""
        return self._check_ollama()


# Convenience function
_default_router: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
    """Get or create default router."""
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter()
    return _default_router


def chat(message: str, **kwargs) -> Response:
    """Quick chat using default router."""
    return get_router().chat(message, **kwargs)
