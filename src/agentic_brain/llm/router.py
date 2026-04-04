# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

"""Lightweight multi-provider LLM router using only the patterns we need.

This module keeps only the ideas we actually need:
- one messages format across providers
- alias resolution
- per-request cost estimation
- retry + fallback behaviour
- rate-limit aware backoff
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Sequence

import aiohttp

from agentic_brain.exceptions import (
    APIError,
    ConfigurationError,
    LLMProviderError,
    RateLimitError,
)
from agentic_brain.model_aliases import MODEL_ALIASES, resolve_alias
from agentic_brain.router.config import Message, Provider, Response, RouterConfig
from agentic_brain.security.llm_guard import LLMSecurityGuard, SecurityRole

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelRoute:
    """Resolved provider/model pair."""

    provider: Provider
    model: str
    alias: str | None = None


class LLMRouterCore:
    """Lightweight router core for Ollama, OpenAI, and Anthropic.

    This module intentionally excludes OpenRouter because the full-featured
    OpenRouter integration lives in ``agentic_brain.router.openrouter`` and the
    heavier router stack under ``agentic_brain.router.routing``.

    Cloud fallback routes are only added when the required API key is
    configured, so the lightweight router does not queue requests it cannot
    authenticate.
    """

    SUPPORTED_PROVIDERS: set[Provider] = {
        Provider.ANTHROPIC,
        Provider.OPENAI,
        Provider.OLLAMA,
    }

    PROVIDER_DEFAULT_MODELS: dict[Provider, str] = {
        Provider.OLLAMA: "llama3.1:8b",
        Provider.OPENAI: "gpt-4o-mini",
        Provider.ANTHROPIC: "claude-3-haiku-20240307",
    }

    PROVIDER_API_KEY_ENV_VARS: dict[Provider, str] = {
        Provider.OPENAI: "OPENAI_API_KEY",
        Provider.ANTHROPIC: "ANTHROPIC_API_KEY",
    }

    FRIENDLY_ALIASES: dict[str, str] = {
        "local": "L2",
        "local-fast": "L1",
        "ollama": "L2",
        "ollama-fast": "L1",
        "gpt": "OP",
        "gpt-fast": "OP2",
        "openai": "OP",
        "claude": "CL",
        "claude-fast": "CL2",
        "anthropic": "CL",
        "sonnet": "CL",
        "haiku": "CL2",
    }

    COST_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
        "gpt-4o": (0.0025, 0.01),
        "gpt-4o-mini": (0.00015, 0.0006),
        "claude-3-haiku": (0.00025, 0.00125),
        "claude-3-5-sonnet": (0.003, 0.015),
        "claude-sonnet-4": (0.003, 0.015),
        "ollama": (0.0, 0.0),
    }

    RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}

    def __init__(
        self,
        config: RouterConfig | None = None,
        *,
        models: Sequence[str] | None = None,
        aliases: dict[str, str] | None = None,
    ) -> None:
        self.config = config or RouterConfig()
        self._aliases = self._build_alias_map(aliases or self.config.model_aliases)
        configured_models = list(models or self.config.priority_models)
        self.priority_models = self._configured_routes(
            self._resolve_routes(configured_models)
        )
        self._total_tokens = 0
        self._tokens_by_provider: dict[str, int] = {}
        self._estimated_cost_total = 0.0
        self._estimated_cost_by_provider: dict[str, float] = {}
        self._request_history: list[dict[str, Any]] = []

    def _build_alias_map(self, custom_aliases: dict[str, str] | None) -> dict[str, str]:
        """Build the case-insensitive alias map for supported lightweight providers."""
        alias_map = {key.lower(): value for key, value in self.FRIENDLY_ALIASES.items()}
        for alias, data in MODEL_ALIASES.items():
            provider_name = str(data.get("provider", "")).lower()
            if provider_name not in {"anthropic", "openai", "ollama"}:
                continue
            alias_map[alias.lower()] = alias
        if custom_aliases:
            alias_map.update(
                {key.lower(): value for key, value in custom_aliases.items()}
            )
        return alias_map

    def normalize_messages(
        self,
        *,
        message: str | None = None,
        system: str | None = None,
        messages: Sequence[dict[str, Any] | Message] | None = None,
    ) -> list[dict[str, str]]:
        """Normalize message inputs to a single provider-neutral format."""
        if messages:
            normalized: list[dict[str, str]] = []
            for item in messages:
                role = (
                    item.role
                    if isinstance(item, Message)
                    else str(item.get("role", "user"))
                )
                content = (
                    item.content
                    if isinstance(item, Message)
                    else str(item.get("content", ""))
                )
                normalized.append({"role": role, "content": content})
            return normalized

        normalized = []
        if system:
            normalized.append({"role": "system", "content": system})
        if message is not None:
            normalized.append({"role": "user", "content": message})
        return normalized

    def prompt_text(self, messages: Sequence[dict[str, str]]) -> str:
        """Stable text form for caching and logging."""
        return "\n".join(f"{msg['role']}:{msg['content']}" for msg in messages)

    def _resolve_routes(self, models: Sequence[str]) -> list[ModelRoute]:
        """Resolve a sequence of models into unique provider/model routes."""
        routes: list[ModelRoute] = []
        seen: set[tuple[Provider, str]] = set()
        for item in models:
            route = self.resolve_model(item)
            key = (route.provider, route.model)
            if key not in seen:
                routes.append(route)
                seen.add(key)
        return routes

    def resolve_model(
        self,
        model: str | None,
        provider: Provider | None = None,
    ) -> ModelRoute:
        """Resolve a friendly alias or raw model ID into a concrete route."""
        if provider and not model:
            return ModelRoute(
                provider=provider, model=self.PROVIDER_DEFAULT_MODELS[provider]
            )

        if not model:
            default_provider = provider or self.config.default_provider
            default_model = (
                self.config.default_model
                or self.PROVIDER_DEFAULT_MODELS[default_provider]
            )
            return self.resolve_model(default_model, default_provider)

        lookup = model.strip()
        alias_key = lookup.lower()
        alias = self._aliases.get(alias_key)
        if alias:
            resolved = resolve_alias(alias)
            route_provider = Provider(resolved["provider"])
            if route_provider in self.SUPPORTED_PROVIDERS:
                return ModelRoute(
                    provider=route_provider,
                    model=str(resolved["model"]),
                    alias=alias.upper(),
                )
            if route_provider == Provider.OPENROUTER:
                raise ValueError(
                    "OpenRouter is not supported by the lightweight LLM router. "
                    "Use agentic_brain.router.openrouter or the full router instead."
                )
            lookup = str(resolved["model"])

        if self._looks_like_openrouter_model(lookup):
            raise ValueError(
                "OpenRouter models are not supported by the lightweight LLM router. "
                "Use agentic_brain.router.openrouter or the full router instead."
            )

        inferred_provider = provider or self._infer_provider(lookup)
        if inferred_provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider for lightweight router: {inferred_provider.value}"
            )
        return ModelRoute(provider=inferred_provider, model=lookup)

    def _infer_provider(self, model: str) -> Provider:
        """Infer the provider from a raw model name."""
        model_lower = model.lower()
        if model_lower.startswith("gpt-") or model_lower.startswith("o1"):
            return Provider.OPENAI
        if model_lower.startswith("claude-"):
            return Provider.ANTHROPIC
        return Provider.OLLAMA

    def _looks_like_openrouter_model(self, model: str) -> bool:
        """Return ``True`` when a raw model string appears to target OpenRouter."""
        model_lower = model.lower()
        return ":free" in model_lower or model_lower.startswith("openrouter/")

    def _is_provider_configured(self, provider: Provider) -> bool:
        """Check whether the provider can be used by this lightweight router."""
        if provider == Provider.OLLAMA:
            return True
        if provider == Provider.OPENAI:
            return bool(self.config.openai_key or os.getenv("OPENAI_API_KEY"))
        if provider == Provider.ANTHROPIC:
            return bool(self.config.anthropic_key or os.getenv("ANTHROPIC_API_KEY"))
        return False

    def _configured_routes(self, routes: Sequence[ModelRoute]) -> list[ModelRoute]:
        """Filter fallback routes down to providers that are currently configured."""
        configured: list[ModelRoute] = []
        for route in routes:
            if self._is_provider_configured(route.provider):
                configured.append(route)
                continue
            logger.debug(
                "Skipping unconfigured lightweight LLM route: provider=%s model=%s",
                route.provider.value,
                route.model,
            )
        return configured

    def _configuration_error_for_provider(
        self, provider: Provider
    ) -> ConfigurationError:
        """Create a consistent configuration error for a provider."""
        env_name = self.PROVIDER_API_KEY_ENV_VARS.get(provider)
        if env_name:
            return ConfigurationError(env_name, "configured API key")
        return ConfigurationError(provider.value, "supported lightweight provider")

    def _routes_for_request(
        self,
        *,
        provider: Provider | None = None,
        model: str | None = None,
        models: Sequence[str] | None = None,
        security_guard: LLMSecurityGuard | None = None,
    ) -> list[ModelRoute]:
        """Return ordered routes for the request, skipping unconfigured fallbacks."""
        if models:
            resolved_routes = self._resolve_routes(models)
            available_routes = self._configured_routes(resolved_routes)
            if security_guard is not None:
                available_routes = [
                    route
                    for route in available_routes
                    if security_guard.can_use_provider(route.provider.value)
                ]
            if available_routes:
                return available_routes
            if security_guard is not None and resolved_routes:
                raise PermissionError(
                    f"Role '{security_guard.role.value}' cannot use the requested providers."
                )
            if resolved_routes:
                raise self._configuration_error_for_provider(
                    resolved_routes[0].provider
                )
            return []

        primary = self.resolve_model(model, provider) if (provider or model) else None
        ordered = [primary] if primary else []
        for route in self.priority_models:
            if route and route not in ordered:
                ordered.append(route)
        available_routes = [route for route in ordered if route is not None]
        if security_guard is not None:
            available_routes = [
                route
                for route in available_routes
                if security_guard.can_use_provider(route.provider.value)
            ]
            if not available_routes:
                raise PermissionError(
                    f"Role '{security_guard.role.value}' cannot use the requested providers."
                )
        if primary and not self._is_provider_configured(primary.provider):
            return available_routes
        return self._configured_routes(available_routes)

    def _record_usage(
        self,
        route: ModelRoute,
        *,
        input_tokens: int,
        output_tokens: int,
        finish_reason: str = "stop",
    ) -> float:
        total_tokens = input_tokens + output_tokens
        self._total_tokens += total_tokens
        provider_key = route.provider.value
        self._tokens_by_provider[provider_key] = (
            self._tokens_by_provider.get(provider_key, 0) + total_tokens
        )

        estimated_cost = self._estimate_cost(route, input_tokens, output_tokens)
        if self.config.cost_tracking_enabled:
            self._estimated_cost_total += estimated_cost
            self._estimated_cost_by_provider[provider_key] = (
                self._estimated_cost_by_provider.get(provider_key, 0.0) + estimated_cost
            )

        self._request_history.append(
            {
                "provider": provider_key,
                "model": route.model,
                "alias": route.alias,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "finish_reason": finish_reason,
                "cost_estimate": estimated_cost,
            }
        )
        return estimated_cost

    def _estimate_cost(
        self, route: ModelRoute, input_tokens: int, output_tokens: int
    ) -> float:
        if route.provider == Provider.OLLAMA:
            return 0.0

        price_key = route.model
        for candidate in self.COST_PER_1K_TOKENS:
            if route.model.startswith(candidate):
                price_key = candidate
                break
        input_rate, output_rate = self.COST_PER_1K_TOKENS.get(price_key, (0.0, 0.0))
        return round(
            ((input_tokens / 1000) * input_rate)
            + ((output_tokens / 1000) * output_rate),
            8,
        )

    def get_token_stats(self) -> dict[str, Any]:
        """Return tracked token and cost statistics for this router instance."""
        return {
            "total_tokens": self._total_tokens,
            "by_provider": dict(self._tokens_by_provider),
            "estimated_cost_total": round(self._estimated_cost_total, 8),
            "estimated_cost_by_provider": {
                key: round(value, 8)
                for key, value in self._estimated_cost_by_provider.items()
            },
            "requests": list(self._request_history),
        }

    def reset_token_stats(self) -> None:
        """Reset accumulated token and cost statistics."""
        self._total_tokens = 0
        self._tokens_by_provider = {}
        self._estimated_cost_total = 0.0
        self._estimated_cost_by_provider = {}
        self._request_history = []

    async def _sleep(self, seconds: float) -> None:
        """Sleep hook used by retry logic, kept overridable for tests."""
        await asyncio.sleep(seconds)

    def _retry_after_seconds(
        self,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | str | None = None,
    ) -> int | None:
        retry_after = None
        if headers:
            for key, value in headers.items():
                if key.lower() == "retry-after":
                    retry_after = value
                    break

        if retry_after:
            if retry_after.isdigit():
                return int(retry_after)
            try:
                retry_dt = parsedate_to_datetime(retry_after)
                if retry_dt.tzinfo is None:
                    retry_dt = retry_dt.replace(tzinfo=UTC)
                return max(
                    0, int((retry_dt - datetime.now(UTC)).total_seconds())
                )
            except Exception:
                return None

        if isinstance(body, dict):
            for key in ("retry_after", "retryAfter"):
                value = body.get(key)
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
            error_body = body.get("error")
            if isinstance(error_body, dict):
                value = error_body.get("retry_after") or error_body.get("retryAfter")
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        return None

    def _backoff_seconds(self, attempt: int, retry_after: int | None = None) -> float:
        """Calculate retry delay for the current attempt."""
        if retry_after is not None:
            return float(retry_after)
        return min(
            self.config.backoff_base_seconds * (2 ** (attempt - 1)),
            self.config.backoff_max_seconds,
        )

    async def _call_with_backoff(
        self,
        route: ModelRoute,
        *,
        messages: Sequence[dict[str, str]],
        temperature: float,
        max_tokens: int | None = None,
    ) -> Response:
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return await self._dispatch_request(
                    route,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except RateLimitError as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    raise
                retry_after = (
                    exc.debug_info.get("retry_after")
                    if hasattr(exc, "debug_info")
                    else None
                )
                await self._sleep(self._backoff_seconds(attempt, retry_after))
            except APIError as exc:
                last_error = exc
                status = (
                    exc.debug_info.get("status_code")
                    if hasattr(exc, "debug_info")
                    else None
                )
                if (
                    status not in self.RETRYABLE_STATUS_CODES
                    or attempt >= self.config.max_retries
                ):
                    raise
                await self._sleep(self._backoff_seconds(attempt))
            except aiohttp.ClientError as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    raise LLMProviderError(route.provider.value, route.model, exc)
                await self._sleep(self._backoff_seconds(attempt))

        raise LLMProviderError(route.provider.value, route.model, last_error)

    async def _chat_messages(
        self,
        messages: Sequence[dict[str, str]],
        *,
        provider: Provider | None = None,
        model: str | None = None,
        models: Sequence[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        security_guard: LLMSecurityGuard | None = None,
    ) -> Response:
        """Send normalized messages using the first route that succeeds."""
        routes = self._routes_for_request(
            provider=provider,
            model=model,
            models=models,
            security_guard=security_guard,
        )
        last_error: Exception | None = None
        for route in routes:
            try:
                return await self._call_with_backoff(
                    route,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM route failed: provider=%s model=%s error=%s",
                    route.provider.value,
                    route.model,
                    type(exc).__name__,
                )
                continue

        if last_error:
            raise last_error
        raise RuntimeError("No routes available for LLM request")

    async def chat(
        self,
        *,
        message: str | None = None,
        messages: Sequence[dict[str, Any] | Message] | None = None,
        system: str | None = None,
        provider: Provider | None = None,
        model: str | None = None,
        models: Sequence[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        role: SecurityRole | str | None = None,
        user_id: str | None = None,
        security_guard: LLMSecurityGuard | None = None,
    ) -> Response:
        """Normalize inputs and execute a chat request."""
        guard = security_guard or LLMSecurityGuard(role)
        rate_limit_user = user_id or guard.default_user_id()
        if not guard.check_rate_limit(rate_limit_user):
            raise RateLimitError(
                limit=guard.permissions.requests_per_minute or 0,
                window="1 minute",
                retry_after=max(1, guard.last_retry_after_seconds),
            )

        if provider is not None or model is not None:
            resolved_route = self.resolve_model(model, provider)
            provider, model = resolved_route.provider, resolved_route.model
            if not guard.can_use_provider(provider.value):
                raise PermissionError(
                    f"Role '{guard.role.value}' cannot use provider '{provider.value}'."
                )

        normalized = guard.filter_messages(
            self.normalize_messages(
                message=message, system=system, messages=messages
            )
        )
        return await self._chat_messages(
            normalized,
            provider=provider,
            model=model,
            models=models,
            temperature=temperature,
            max_tokens=max_tokens,
            security_guard=guard,
        )

    def chat_sync(self, **kwargs: Any) -> Response:
        """Synchronous wrapper around :meth:`chat`."""
        return asyncio.run(self.chat(**kwargs))

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
                timeout=aiohttp.ClientTimeout(total=timeout or self.config.timeout),
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
                f"{self.config.ollama_host}/api/tags",
                timeout=aiohttp.ClientTimeout(total=2),
            ) as response,
        ):
            if response.status == 200:
                return
        raise LLMProviderError(
            "ollama",
            self.PROVIDER_DEFAULT_MODELS[Provider.OLLAMA],
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
            retry_after = self._retry_after_seconds(headers, result)
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
        estimated_cost = self._record_usage(
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

    async def _dispatch_openai(
        self,
        route: ModelRoute,
        messages: Sequence[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> Response:
        api_key = self._require_api_key(self.config.openai_key, "OPENAI_API_KEY")
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
            timeout=self.config.openai_timeout,
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
        api_key = self._require_api_key(self.config.anthropic_key, "ANTHROPIC_API_KEY")
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
            timeout=self.config.anthropic_timeout,
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

        url = f"{self.config.ollama_host}/api/chat"
        status, result, headers = await self._perform_post(
            url,
            payload,
            timeout=self.config.ollama_timeout,
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
        return await self._chat_messages(
            self.normalize_messages(message=message, system=system),
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
        return await self._chat_messages(
            self.normalize_messages(message=message, system=system),
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
        return await self._chat_messages(
            self.normalize_messages(message=message, system=system),
            provider=Provider.OLLAMA,
            model=model,
            temperature=temperature,
        )


class LLMRouter(LLMRouterCore):
    """Standalone lightweight router."""
