# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock

import pytest

from agentic_brain.exceptions import APIError, ConfigurationError, RateLimitError
from agentic_brain.llm.router import LLMRouter
from agentic_brain.router.config import Provider, Response, RouterConfig


def test_normalize_messages_unified_format():
    router = LLMRouter()

    messages = router.normalize_messages(
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
    )

    assert messages == [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]


def test_resolve_friendly_alias_to_provider_and_model():
    router = LLMRouter()

    route = router.resolve_model("claude")

    assert route.provider == Provider.ANTHROPIC
    assert route.model.startswith("claude-")
    assert route.alias == "CL"


def test_resolve_model_rejects_openrouter_models():
    router = LLMRouter()

    with pytest.raises(ValueError, match="OpenRouter"):
        router.resolve_model("meta-llama/llama-3-8b-instruct:free")


def test_priority_models_skip_unconfigured_cloud_routes():
    router = LLMRouter(
        RouterConfig(openai_key=None, anthropic_key=None),
        models=["L2", "OP2", "CL2"],
    )

    assert [(route.provider, route.model) for route in router.priority_models] == [
        (Provider.OLLAMA, "llama3.1:8b")
    ]


def test_models_request_requires_configured_provider():
    router = LLMRouter(RouterConfig(openai_key=None), models=["L2"])

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        router._routes_for_request(models=["OP2"])


@pytest.mark.asyncio
async def test_rate_limit_backoff_retries_same_route():
    router = LLMRouter(RouterConfig(max_retries=2, backoff_base_seconds=0.5))
    router._sleep = AsyncMock()

    response = Response(
        content="ok",
        model="gpt-4o-mini",
        provider=Provider.OPENAI,
        input_tokens=100,
        output_tokens=50,
        tokens_used=150,
        cost_estimate=0.000045,
    )

    router._dispatch_request = AsyncMock(
        side_effect=[RateLimitError(limit=1, window="minute", retry_after=3), response]
    )

    result = await router.chat(message="Hello", model="OP2")

    assert result.content == "ok"
    router._sleep.assert_awaited_once_with(3.0)
    assert router._dispatch_request.await_count == 2


@pytest.mark.asyncio
async def test_falls_back_to_next_model_on_provider_error():
    router = LLMRouter(
        RouterConfig(openai_key="sk-openai", anthropic_key="sk-anthropic"),
        models=["OP2", "CL2"],
    )

    async def dispatch(route, **kwargs):
        if route.provider == Provider.OPENAI:
            raise APIError(
                "https://api.openai.com/v1/chat/completions", 500, "boom", None
            )
        return router._response_with_usage(
            route=route,
            content="fallback worked",
            input_tokens=120,
            output_tokens=80,
        )

    router._dispatch_request = dispatch

    result = await router.chat(message="Try fallback")

    assert result.provider == Provider.ANTHROPIC
    assert result.content == "fallback worked"

    stats = router.get_token_stats()
    assert stats["total_tokens"] == 200
    assert stats["estimated_cost_total"] > 0
    assert "anthropic" in stats["estimated_cost_by_provider"]
