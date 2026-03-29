# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.personas import PersonaManager, get_persona
from agentic_brain.router import LLMRouter, Provider, Response, RouterConfig


@pytest.fixture
def router():
    return LLMRouter()


class TestSmartRouting:
    def test_short_simple_message(self, router):
        """Test routing for short, simple messages."""
        msg = "hi"
        provider, model = router.smart_route(msg)
        assert provider == Provider.OLLAMA
        assert model == "llama3.2:3b"

    def test_medium_message(self, router):
        """Test routing for medium messages (default)."""
        msg = "Tell me a story about a cat." + " " * 150
        # Medium message with no keywords -> Default to OLLAMA
        provider, model = router.smart_route(msg)
        assert provider == Provider.OLLAMA
        assert model == "llama3.1:8b"

    def test_code_message(self, router):
        """Test routing for code-related messages."""
        # Ensure Anthropic key is set for this test
        router.config.anthropic_key = "test-key"
        msg = "Write some python code"
        provider, model = router.smart_route(msg)
        assert provider == Provider.ANTHROPIC
        assert model == "claude-3-5-sonnet-20241022"

    def test_complex_message_anthropic(self, router):
        """Test routing for complex messages."""
        router.config.anthropic_key = "test-key"
        msg = "Analyze the complex geopolitical implications of this event with detailed reasoning."
        provider, model = router.smart_route(msg)
        assert provider == Provider.ANTHROPIC
        assert model == "claude-3-sonnet-20240229"

    def test_complex_message_openai(self, router):
        """Test routing for complex messages."""
        router.config.anthropic_key = None
        router.config.openai_key = "test-key"
        msg = "Analyze the complex geopolitical implications of this event with detailed reasoning."
        provider, model = router.smart_route(msg)
        assert provider == Provider.OPENAI
        assert model == "gpt-4o"

    def test_complex_message_no_keys(self, router):
        """Test routing for complex messages."""
        router.config.anthropic_key = None
        router.config.openai_key = None
        msg = "Analyze the complex geopolitical implications of this event with detailed reasoning."
        provider, model = router.smart_route(msg)
        assert provider == Provider.OLLAMA
        assert model == "llama3.1:8b"


class TestPersonas:
    @pytest.mark.asyncio
    async def test_chat_with_persona(self, router):
        """Test that chat uses the persona's system prompt."""
        # Mock _chat_ollama to verify arguments
        router._chat_ollama = AsyncMock()
        router._chat_ollama.return_value = Response(
            content="Mock response", model="llama3.1:8b", provider=Provider.OLLAMA
        )

        # Call with persona
        await router.chat("Hello", persona="coder", provider=Provider.OLLAMA)

        # Verify system prompt was set from persona
        call_args = router._chat_ollama.call_args
        assert call_args is not None
        system_arg = call_args[0][1]  # (message, system, model, temp)
        assert "expert software engineer" in system_arg
        assert "Style Guidelines:" in system_arg
        assert "PEP 8" in system_arg

    @pytest.mark.asyncio
    async def test_chat_invalid_persona(self, router):
        """Test that invalid persona is ignored."""
        router._chat_ollama = AsyncMock()
        router._chat_ollama.return_value = Response(
            content="Mock response", model="llama3.1:8b", provider=Provider.OLLAMA
        )

        await router.chat("Hello", persona="invalid_persona", provider=Provider.OLLAMA)

        # Verify system prompt is None (default)
        call_args = router._chat_ollama.call_args
        system_arg = call_args[0][1]
        assert system_arg is None

    @pytest.mark.asyncio
    async def test_chat_persona_override(self, router):
        """Test that explicit system prompt overrides persona."""
        # Ensure persona exists
        coder = get_persona("coder")
        assert coder is not None, "Coder persona not found"

        router._chat_ollama = AsyncMock()
        router._chat_ollama.return_value = Response(
            content="Mock response", model="llama3.1:8b", provider=Provider.OLLAMA
        )

        await router.chat(
            "Hello", system="Original system", persona="coder", provider=Provider.OLLAMA
        )

        call_args = router._chat_ollama.call_args
        system_arg = call_args[0][1]

        # Persona prompt should be used
        expected_system = coder.format_system_prompt()
        assert system_arg == expected_system
        assert "Original system" not in system_arg
