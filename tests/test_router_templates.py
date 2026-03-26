# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic_brain.router import LLMRouter, Provider, Response


@pytest.fixture
def router():
    return LLMRouter()


def test_router_has_smart_route(router):
    assert hasattr(router, "smart_route")
    assert callable(router.smart_route)


def test_short_message_routes_to_fast_model(router):
    provider, model = router.smart_route("hi")
    assert provider == Provider.OLLAMA
    assert model == "llama3.2:3b"


def test_code_message_routes_to_quality_model(router):
    router.config.anthropic_key = "test-key"
    provider, model = router.smart_route("Please write code to parse JSON.")
    assert provider == Provider.ANTHROPIC
    assert model == "claude-3-5-sonnet-20241022"


def test_persona_parameter_is_accepted():
    params = inspect.signature(LLMRouter.chat).parameters
    assert "persona" in params


@pytest.mark.asyncio
async def test_chat_uses_smart_routing_by_default(router):
    """Verify that chat uses smart routing when no provider/model specified."""
    # Mock smart_route to control behavior
    router.smart_route = MagicMock(return_value=(Provider.OLLAMA, "llama3.2:3b"))

    router._chat_ollama = AsyncMock(
        return_value=Response(
            content="ok",
            model="llama3.2:3b",
            provider=Provider.OLLAMA,
        )
    )

    response = await router.chat("Hello", use_cache=False)

    assert response.content == "ok"
    router.smart_route.assert_called_once_with("Hello")
    router._chat_ollama.assert_awaited_once()
    _, system_arg, model_arg, _ = router._chat_ollama.call_args.args
    assert system_arg is None
    assert model_arg == "llama3.2:3b"
