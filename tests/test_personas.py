# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from unittest.mock import AsyncMock

import pytest

from agentic_brain.personas import Persona, PersonaManager, get_persona
from agentic_brain.personas.industries import INDUSTRY_PERSONAS
from agentic_brain.router import LLMRouter, Provider, Response


@pytest.fixture(autouse=True)
def reset_persona_manager():
    """Ensure each test has a fresh PersonaManager singleton."""
    PersonaManager._instance = None
    yield
    PersonaManager._instance = None


class TestPersona:
    def test_persona_creation_and_defaults(self):
        persona = Persona(
            name="test",
            description="Test persona",
            system_prompt="You are a test persona.",
        )

        assert persona.name == "test"
        assert persona.description == "Test persona"
        assert persona.system_prompt == "You are a test persona."
        assert persona.style_guidelines == []
        assert persona.temperature == 0.7
        assert persona.safety_level == "standard"

    def test_format_system_prompt_with_style_guidelines(self):
        persona = Persona(
            name="stylist",
            description="Persona with style",
            system_prompt="Follow these instructions.",
            style_guidelines=["Be concise", "Use bullet points"],
        )

        formatted = persona.format_system_prompt()
        assert formatted.startswith("Follow these instructions.")
        assert "Style Guidelines:" in formatted
        assert "- Be concise" in formatted
        assert "- Use bullet points" in formatted

    def test_format_system_prompt_without_guidelines(self):
        persona = Persona(
            name="plain",
            description="Persona without style",
            system_prompt="Just answer.",
            style_guidelines=[],
        )

        assert persona.format_system_prompt() == "Just answer."


class TestPersonaManager:
    def test_singleton_pattern(self):
        pm1 = PersonaManager.get_instance()
        pm2 = PersonaManager.get_instance()

        assert pm1 is pm2

    def test_default_personas_registered(self):
        pm = PersonaManager.get_instance()
        expected = {"default", "coder", "creative", "analyst"} | set(
            INDUSTRY_PERSONAS.keys()
        )

        persona_names = set(pm.list_personas())
        assert expected.issubset(persona_names)

        for name in expected:
            persona = pm.get(name)
            assert persona is not None
            assert persona.name == name

    def test_register_custom_persona(self):
        pm = PersonaManager.get_instance()
        custom = Persona(
            name="support",
            description="Support specialist",
            system_prompt="You are a helpful support specialist.",
            style_guidelines=[
                "Verify customer details",
                "Provide step-by-step guidance",
            ],
            temperature=0.2,
            safety_level="high",
        )

        pm.register(custom)

        assert pm.get("support") is custom
        assert "support" in pm.list_personas()

    def test_get_persona_helper(self):
        PersonaManager.get_instance()  # Ensure defaults are registered

        coder = get_persona("coder")
        assert coder is not None
        assert coder.name == "coder"

        missing = get_persona("nonexistent")
        assert missing is None


class TestPersonaRouterIntegration:
    @pytest.mark.asyncio
    async def test_router_applies_persona_prompt(self):
        PersonaManager.get_instance()  # Register defaults
        router = LLMRouter()
        router._chat_ollama = AsyncMock(
            return_value=Response(
                content="ok",
                model="llama3.1:8b",
                provider=Provider.OLLAMA,
                tokens_used=10,
            )
        )

        response = await router.chat("Hello", persona="coder", provider=Provider.OLLAMA)

        assert response.content == "ok"
        call_args = router._chat_ollama.call_args
        assert call_args is not None
        system_prompt = call_args[0][1]
        expected_prompt = get_persona("coder").format_system_prompt()
        assert system_prompt == expected_prompt

    @pytest.mark.asyncio
    async def test_router_handles_missing_persona(self):
        router = LLMRouter()
        router._chat_ollama = AsyncMock(
            return_value=Response(
                content="fallback",
                model="llama3.1:8b",
                provider=Provider.OLLAMA,
            )
        )

        await router.chat("Hello", persona="missing", provider=Provider.OLLAMA)

        call_args = router._chat_ollama.call_args
        system_prompt = call_args[0][1]
        assert system_prompt is None
