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
import logging
import os
from dataclasses import dataclass
from typing import Any, Sequence

from agentic_brain.exceptions import (
    ConfigurationError,
    LLMProviderError,
    RateLimitError,
)
from agentic_brain.model_aliases import MODEL_ALIASES, resolve_alias
from agentic_brain.router.config import Message, Provider, Response, RouterConfig
from agentic_brain.security.llm_guard import LLMSecurityGuard, SecurityRole

from agentic_brain.llm.providers import ProviderDispatchMixin
from agentic_brain.llm.strategies import RetryStrategyMixin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelRoute:
    """Resolved provider/model pair."""

    provider: Provider
    model: str
    alias: str | None = None


class LLMRouterCore(RetryStrategyMixin, ProviderDispatchMixin):
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
            self.normalize_messages(message=message, system=system, messages=messages)
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


class LLMRouter(LLMRouterCore):
    """Standalone lightweight router."""
