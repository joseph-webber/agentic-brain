#!/usr/bin/env python3
"""Unified LLM provider interface with circuit breakers and latency tracking.

Supports: Ollama (local), Claude, GPT, Gemini, Grok
Each provider implements the same call() interface.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Sequence

from tools.voice.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry


def _http_json(url: str, payload: dict, headers: dict, timeout: int = 20) -> dict:
    """POST JSON and return parsed response."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class LLMProvider:
    """Base class for all LLM providers."""

    name: str = "base"
    default_model: str = ""
    supports_streaming: bool = False

    def __init__(self) -> None:
        registry = CircuitBreakerRegistry.get()
        self._breaker: CircuitBreaker = registry.breaker(
            self.name,
            failure_threshold=3,
            recovery_timeout=30.0,
        )

    @property
    def available(self) -> bool:
        """Check if provider is configured and circuit is not open."""
        return self._breaker.allow_request() and self._check_configured()

    def _check_configured(self) -> bool:
        raise NotImplementedError

    def call(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 200,
        temperature: float = 0.7,
    ) -> str:
        """Call the LLM. Raises on failure. Returns response text."""
        if not self._breaker.allow_request():
            raise RuntimeError(f"{self.name} circuit breaker is open")

        t0 = time.monotonic()
        try:
            result = self._do_call(
                messages,
                model=model or self.default_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            latency = (time.monotonic() - t0) * 1000
            self._breaker.record_success(latency)
            return result
        except Exception:
            self._breaker.record_failure()
            raise

    def _do_call(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        raise NotImplementedError

    def stats(self) -> dict[str, Any]:
        return self._breaker.stats()


class OllamaProvider(LLMProvider):
    """Local Ollama — always-available fallback. Never fails (unless Ollama is down)."""

    name = "ollama"
    default_model = "llama3.2:3b"
    FAST_MODEL = "llama3.2:3b"
    QUALITY_MODEL = "llama3.1:8b"

    def __init__(self) -> None:
        super().__init__()
        self.url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        # Ollama gets a more forgiving breaker
        self._breaker.failure_threshold = 5
        self._breaker.recovery_timeout = 10.0

    def _check_configured(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.url}/api/tags", method="GET")
            urllib.request.urlopen(req, timeout=3)
            return True
        except Exception:
            return False

    def _do_call(self, messages, *, model, max_tokens, temperature) -> str:
        payload = {
            "model": model,
            "messages": list(messages),
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        data = _http_json(
            f"{self.url}/api/chat",
            payload,
            {"Content-Type": "application/json"},
            timeout=30,
        )
        text = data.get("message", {}).get("content", "").strip()
        if not text:
            raise RuntimeError("Ollama returned empty response")
        return text


class ClaudeProvider(LLMProvider):
    """Anthropic Claude — best reasoning."""

    name = "claude"
    default_model = "claude-sonnet-4-20250514"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")

    def _check_configured(self) -> bool:
        return bool(self.api_key)

    def _do_call(self, messages, *, model, max_tokens, temperature) -> str:
        system_msg = ""
        chat_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                chat_msgs.append({"role": m["role"], "content": m["content"]})

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": chat_msgs,
        }
        if system_msg:
            payload["system"] = system_msg

        data = _http_json(
            "https://api.anthropic.com/v1/messages",
            payload,
            {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=25,
        )
        blocks = data.get("content", [])
        text = " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if not text.strip():
            raise RuntimeError("Claude returned empty response")
        return text.strip()


class GPTProvider(LLMProvider):
    """OpenAI GPT — strong coding and general purpose."""

    name = "gpt"
    default_model = "gpt-4o-mini"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = os.getenv("OPENAI_API_KEY", "")

    def _check_configured(self) -> bool:
        return bool(self.api_key)

    def _do_call(self, messages, *, model, max_tokens, temperature) -> str:
        data = _http_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": model,
                "messages": list(messages),
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            timeout=20,
        )
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text.strip():
            raise RuntimeError("GPT returned empty response")
        return text.strip()


class GeminiProvider(LLMProvider):
    """Google Gemini — strong on facts and multimodal."""

    name = "gemini"
    default_model = "gemini-2.0-flash"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_KEY", "")

    def _check_configured(self) -> bool:
        return bool(self.api_key)

    def _do_call(self, messages, *, model, max_tokens, temperature) -> str:
        # Gemini uses a different message format
        contents = []
        system_instruction = None
        for m in messages:
            if m["role"] == "system":
                system_instruction = m["content"]
            else:
                role = "user" if m["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m["content"]}]})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
            f":generateContent?key={self.api_key}"
        )
        data = _http_json(
            url, payload, {"Content-Type": "application/json"}, timeout=20
        )
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = " ".join(p.get("text", "") for p in parts)
        if not text.strip():
            raise RuntimeError("Gemini returned empty response")
        return text.strip()


class GrokProvider(LLMProvider):
    """xAI Grok — creative and current events."""

    name = "grok"
    default_model = "grok-3-mini-fast"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY", "")

    def _check_configured(self) -> bool:
        return bool(self.api_key)

    def _do_call(self, messages, *, model, max_tokens, temperature) -> str:
        # Grok uses OpenAI-compatible API
        data = _http_json(
            "https://api.x.ai/v1/chat/completions",
            {
                "model": model,
                "messages": list(messages),
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            timeout=20,
        )
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text.strip():
            raise RuntimeError("Grok returned empty response")
        return text.strip()


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

_ALL_PROVIDERS: list[type[LLMProvider]] = [
    OllamaProvider,
    ClaudeProvider,
    GPTProvider,
    GeminiProvider,
    GrokProvider,
]

_provider_instances: dict[str, LLMProvider] | None = None


def get_providers() -> dict[str, LLMProvider]:
    """Lazy-init and return all provider instances."""
    global _provider_instances
    if _provider_instances is None:
        _provider_instances = {}
        for cls in _ALL_PROVIDERS:
            inst = cls()
            _provider_instances[inst.name] = inst
    return _provider_instances


def get_provider(name: str) -> LLMProvider:
    providers = get_providers()
    if name not in providers:
        raise KeyError(f"Unknown provider: {name}. Available: {list(providers)}")
    return providers[name]


def available_providers() -> list[str]:
    """Return names of providers whose circuit is not open and are configured."""
    return [name for name, p in get_providers().items() if p.available]
