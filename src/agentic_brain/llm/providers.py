# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

"""Provider-specific HTTP dispatch for the lightweight LLM router."""

import json
import logging
import os
from typing import TYPE_CHECKING, Any, Sequence

import aiohttp

from agentic_brain.exceptions import (
    APIError,
    ConfigurationError,
    LLMProviderError,
    RateLimitError,
)
from agentic_brain.router.config import Provider, Response

if TYPE_CHECKING:
    from agentic_brain.llm.router import ModelRoute

logger = logging.getLogger(__name__)


class ProviderDispatchMixin:
    """Mixin that adds provider-specific HTTP dispatch to LLMRouterCore.

    The methods here assume ``self`` provides:
    - ``self.config``  (RouterConfig)
    - ``self.PROVIDER_DEFAULT_MODELS``
    - ``self._record_usage(route, *, input_tokens, output_tokens, finish_reason)``
    - ``self._chat_messages(messages, ...)``
    - ``self.normalize_messages(...)``
    """

    async def _perform_post(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, dict[str, Any] | str, dict[str, str]]:
        """POST JSON to a provider endpoint or a test override hook."""
        post_fn = getattr(self, "_post_request", None)
        if callable(post_fn):
            status, result = await post_fn(url, payload, headers, timeout)
            return status, result, {}

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout or self.config.timeout),  # type: ignore[attr-defined]
            ) as response,
        ):
            response_headers = dict(response.headers)
            try:
                result = await response.json()
            except Exception:
                result = await response.text()
            return response.status, result, response_headers

    async def _ensure_ollama_available(self) -> None:
        """Verify Ollama is reachable before sending a local request."""
        check_fn = getattr(self, "_is_ollama_available", None)
        if callable(check_fn):
            available = await check_fn()
            if available:
                return

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self.config.ollama_host}/api/tags",  # type: ignore[attr-defined]
                timeout=aiohttp.ClientTimeout(total=2),
            ) as response,
        ):
            if response.status == 200:
                return
        raise LLMProviderError(
            "ollama",
            self.PROVIDER_DEFAULT_MODELS[Provider.OLLAMA],  # type: ignore[attr-defined]
            Exception("Ollama is not running"),
        )

    def _require_api_key(self, config_value: str | None, env_name: str) -> str:
        """Return a required API key or raise a consistent configuration error."""
        api_key = config_value or os.getenv(env_name)
        if not api_key:
            raise ConfigurationError(env_name, "configured API key")
        return api_key

    def _raise_for_status(
        self,
        *,
        provider: Provider,
        model: str,
        url: str,
        status: int,
        result: dict[str, Any] | str,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Translate HTTP error responses into router exceptions."""
        if status < 400:
            return
        if status == 429:
            retry_after = self._retry_after_seconds(headers, result)  # type: ignore[attr-defined]
            raise RateLimitError(
                limit=1, window="request window", retry_after=retry_after or 1
            )
        raise APIError(
            url,
            status,
            json.dumps(result) if isinstance(result, dict) else str(result),
            None,
        )

    def _require_mapping_response(
        self,
        route: ModelRoute,
        result: dict[str, Any] | str,
    ) -> dict[str, Any]:
        """Validate that the provider returned a JSON object payload."""
        if isinstance(result, dict):
            return result
        raise LLMProviderError(
            route.provider.value,
            route.model,
            TypeError(f"Unexpected response type: {type(result).__name__}"),
        )

    def _response_with_usage(
        self,
        *,
        route: ModelRoute,
        content: str,
        finish_reason: str = "stop",
        input_tokens: int = 0,
        output_tokens: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Response:
        """Create a response object and update usage accounting."""
        estimated_cost = self._record_usage(  # type: ignore[attr-defined]
            route,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
        )
        return Response(
            content=content,
            model=route.model,
            provider=route.provider,
            tokens_used=input_tokens + output_tokens,
            finish_reason=finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_estimate=estimated_cost,
            metadata=metadata or {},
        )

    async def _dispatch_request(
        self,
        route: ModelRoute,
        *,
        messages: Sequence[dict[str, str]],
        temperature: float,
        max_tokens: int | None = None,
    ) -> Response:
        """Dispatch a request to the provider-specific implementation."""
        if route.provider == Provider.OPENAI:
            return await self._dispatch_openai(route, messages, temperature, max_tokens)
        if route.provider == Provider.ANTHROPIC:
            return await self._dispatch_anthropic(
                route, messages, temperature, max_tokens
            )
        if route.provider == Provider.OLLAMA:
            return await self._dispatch_ollama(route, messages, temperature, max_tokens)
        raise ValueError(f"Unsupported provider: {route.provider.value}")

    async def _dispatch_openai(
        self,
        route: ModelRoute,
        messages: Sequence[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> Response:
        api_key = self._require_api_key(self.config.openai_key, "OPENAI_API_KEY")  # type: ignore[attr-defined]
        payload: dict[str, Any] = {
            "model": route.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        url = "https://api.openai.com/v1/chat/completions"
        status, result, headers = await self._perform_post(
            url,
            payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            timeout=self.config.openai_timeout,  # type: ignore[attr-defined]
        )
        self._raise_for_status(
            provider=route.provider,
            model=route.model,
            url=url,
            status=status,
            result=result,
            headers=headers,
        )
        result = self._require_mapping_response(route, result)

        choice = result["choices"][0]
        usage = result.get("usage", {})
        return self._response_with_usage(
            route=route,
            content=choice["message"]["content"],
            finish_reason=choice.get("finish_reason", "stop"),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )

    async def _dispatch_anthropic(
        self,
        route: ModelRoute,
        messages: Sequence[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> Response:
        api_key = self._require_api_key(self.config.anthropic_key, "ANTHROPIC_API_KEY")  # type: ignore[attr-defined]
        system_blocks = [msg["content"] for msg in messages if msg["role"] == "system"]
        provider_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
            if msg["role"] != "system"
        ]
        payload: dict[str, Any] = {
            "model": route.model,
            "messages": provider_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
        }
        if system_blocks:
            payload["system"] = "\n\n".join(system_blocks)

        url = "https://api.anthropic.com/v1/messages"
        status, result, headers = await self._perform_post(
            url,
            payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=self.config.anthropic_timeout,  # type: ignore[attr-defined]
        )
        self._raise_for_status(
            provider=route.provider,
            model=route.model,
            url=url,
            status=status,
            result=result,
            headers=headers,
        )
        result = self._require_mapping_response(route, result)

        usage = result.get("usage", {})
        content_blocks = result.get("content", [])
        text = "".join(
            block.get("text", "") for block in content_blocks if isinstance(block, dict)
        )
        return self._response_with_usage(
            route=route,
            content=text,
            finish_reason=result.get("stop_reason", "stop"),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )

    async def _dispatch_ollama(
        self,
        route: ModelRoute,
        messages: Sequence[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> Response:
        await self._ensure_ollama_available()

        payload: dict[str, Any] = {
            "model": route.model,
            "messages": list(messages),
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        url = f"{self.config.ollama_host}/api/chat"  # type: ignore[attr-defined]
        status, result, headers = await self._perform_post(
            url,
            payload,
            timeout=self.config.ollama_timeout,  # type: ignore[attr-defined]
        )
        self._raise_for_status(
            provider=route.provider,
            model=route.model,
            url=url,
            status=status,
            result=result,
            headers=headers,
        )
        result = self._require_mapping_response(route, result)

        return self._response_with_usage(
            route=route,
            content=result["message"]["content"],
            input_tokens=int(result.get("prompt_eval_count", 0)),
            output_tokens=int(result.get("eval_count", 0)),
            finish_reason="stop",
        )

    async def _chat_openai(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        return await self._chat_messages(  # type: ignore[attr-defined]
            self.normalize_messages(message=message, system=system),  # type: ignore[attr-defined]
            provider=Provider.OPENAI,
            model=model,
            temperature=temperature,
        )

    async def _chat_anthropic(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        return await self._chat_messages(  # type: ignore[attr-defined]
            self.normalize_messages(message=message, system=system),  # type: ignore[attr-defined]
            provider=Provider.ANTHROPIC,
            model=model,
            temperature=temperature,
        )

    async def _chat_ollama(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        return await self._chat_messages(  # type: ignore[attr-defined]
            self.normalize_messages(message=message, system=system),  # type: ignore[attr-defined]
            provider=Provider.OLLAMA,
            model=model,
            temperature=temperature,
        )
