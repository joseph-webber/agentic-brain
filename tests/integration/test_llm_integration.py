from __future__ import annotations

import json

import httpx
import pytest

from agentic_brain.exceptions import ConfigurationError
from agentic_brain.llm.router import LLMRouterCore
from agentic_brain.router.config import Provider, RouterConfig
from agentic_brain.security.llm_guard import SecurityRole

pytestmark = [pytest.mark.integration, pytest.mark.llm]


class RouterHarness(LLMRouterCore):
    def __init__(self, *, base_url: str, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url
        self.sleep_calls: list[float] = []

    async def _post_request(self, url, payload, headers=None, timeout=None):
        if "api.openai.com" in url:
            local_url = f"{self.base_url}/v1/chat/completions"
        elif "anthropic" in url:
            local_url = f"{self.base_url}/v1/messages"
        elif "/api/chat" in url:
            local_url = f"{self.base_url}/api/chat"
        elif "/api/tags" in url:
            local_url = f"{self.base_url}/api/tags"
        else:
            local_url = url

        async with httpx.AsyncClient(timeout=timeout or 10.0) as client:
            response = await client.post(local_url, json=payload, headers=headers)
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = response.text
        return response.status_code, body

    async def _is_ollama_available(self):
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{self.base_url}/api/tags")
        return response.status_code == 200

    async def _sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)


def make_router(llm_server, **kwargs) -> RouterHarness:
    config = RouterConfig(
        ollama_host=llm_server["base_url"],
        openai_key="test-openai-key",
        anthropic_key="test-anthropic-key",
        max_retries=kwargs.pop("max_retries", 2),
        backoff_base_seconds=0,
        backoff_max_seconds=0,
        **kwargs,
    )
    return RouterHarness(config=config, base_url=llm_server["base_url"])


def test_resolve_model_aliases_across_providers(llm_server):
    router = make_router(llm_server)

    assert router.resolve_model("gpt-fast").provider == Provider.OPENAI
    assert router.resolve_model("claude-fast").provider == Provider.ANTHROPIC
    assert router.resolve_model("ollama").provider == Provider.OLLAMA


@pytest.mark.asyncio
async def test_ollama_chat_uses_local_provider(llm_server):
    router = make_router(llm_server)

    response = await router.chat(
        message="hello", provider=Provider.OLLAMA, role=SecurityRole.USER
    )

    assert response.provider == Provider.OLLAMA
    assert "Mock Ollama reply" in response.content
    assert response.tokens_used == response.input_tokens + response.output_tokens


@pytest.mark.asyncio
async def test_openai_chat_uses_local_provider(llm_server):
    router = make_router(llm_server)

    response = await router.chat(
        message="hello openai", provider=Provider.OPENAI, role=SecurityRole.USER
    )

    assert response.provider == Provider.OPENAI
    assert response.content.startswith("OpenAI mock:")
    assert router.get_token_stats()["by_provider"]["openai"] > 0


@pytest.mark.asyncio
async def test_anthropic_chat_uses_local_provider(llm_server):
    router = make_router(llm_server)

    response = await router.chat(
        message="hello anthropic", provider=Provider.ANTHROPIC, role=SecurityRole.USER
    )

    assert response.provider == Provider.ANTHROPIC
    assert response.content.startswith("Anthropic mock:")


@pytest.mark.asyncio
async def test_router_records_usage_and_can_reset(llm_server):
    router = make_router(llm_server)

    await router.chat(
        message="track usage", provider=Provider.OPENAI, role=SecurityRole.USER
    )
    stats = router.get_token_stats()

    assert stats["total_tokens"] > 0
    assert stats["requests"]

    router.reset_token_stats()
    assert router.get_token_stats()["total_tokens"] == 0


@pytest.mark.asyncio
async def test_router_retries_on_rate_limit_then_succeeds(llm_server):
    llm_server["state"].fail_once("/v1/chat/completions")
    router = make_router(llm_server, max_retries=2)

    response = await router.chat(
        message="retry me", provider=Provider.OPENAI, role=SecurityRole.USER
    )

    assert response.provider == Provider.OPENAI
    assert response.content.startswith("OpenAI mock:")
    assert router.sleep_calls == [1.0]


@pytest.mark.asyncio
async def test_router_falls_back_to_second_provider_when_primary_fails(llm_server):
    llm_server["state"].fail_once("/api/chat")
    router = make_router(llm_server, max_retries=1)

    response = await router.chat(
        message="fallback please",
        models=["llama3.1:8b", "gpt-4o-mini"],
        role=SecurityRole.USER,
    )

    assert response.provider == Provider.OPENAI
    assert response.content.startswith("OpenAI mock:")
    paths = [request["path"] for request in llm_server["state"].requests]
    assert "/api/chat" in paths
    assert "/v1/chat/completions" in paths


def test_missing_openai_credentials_raise_configuration_error(llm_server):
    router = RouterHarness(
        config=RouterConfig(ollama_host=llm_server["base_url"], max_retries=1),
        base_url=llm_server["base_url"],
    )

    with pytest.raises(ConfigurationError):
        router._routes_for_request(models=["gpt-4o-mini"])
