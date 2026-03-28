from unittest.mock import AsyncMock

import pytest

from agentic_brain.exceptions import APIError, RateLimitError
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
    router = LLMRouter(models=["OP2", "CL2"])

    async def dispatch(route, **kwargs):
        if route.provider == Provider.OPENAI:
            raise APIError("https://api.openai.com/v1/chat/completions", 500, "boom", None)
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
