# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

"""
Production LLM router built on top of ``LLMRouterCore``.

``agentic_brain.llm.router.LLMRouterCore`` is the lightweight, dependency-light
core that owns message normalization, alias resolution, retry/backoff, and cost
tracking for a small set of providers. This module layers production concerns
on top of that core:

- Streaming responses and additional cloud providers (Azure, Groq, Together,
  Google, xAI)
- Semantic prompt caching and Redis-based coordination
- HTTP pooling integration
- Smart routing heuristics and fallback chains

Use ``LLMRouter`` from this module for the full-featured production router.
Use ``LLMRouterCore`` when you need the smallest dependency surface area.
"""


import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from types import ModuleType, TracebackType
from typing import TYPE_CHECKING, Any

from agentic_brain.exceptions import RateLimitError
from agentic_brain.llm.router import LLMRouterCore
from agentic_brain.security.llm_guard import LLMSecurityGuard, SecurityRole

from .anthropic import stream_anthropic
from .azure_openai import chat_azure_openai, stream_azure_openai
from .config import Message, Provider, Response, RouterConfig
from .google import chat_google, stream_google
from .groq import chat_groq, stream_groq
from .http import get_request, post_request
from .ollama import (
    check_ollama_sync,
    list_models_async,
    list_models_sync,
    stream_ollama,
)
from .openai import stream_openai
from .openrouter import chat_openrouter, stream_openrouter
from .provider_checker import ProviderChecker, format_error_message
from .together import chat_together, stream_together
from .xai import chat_xai, stream_xai

# Optional import for typing without forcing Redis dependency
if TYPE_CHECKING:
    from agentic_brain.unified_brain import UnifiedBrain

    from .redis_cache import RedisInterBotComm, RedisRouterCache

# Lazy import for cache to avoid circular dependencies
_MODULE_UNAVAILABLE = object()
_semantic_cache_module: ModuleType | object | None = None
_unified_brain_module: type[UnifiedBrain] | object | None = None


def _get_cache_module() -> ModuleType | None:
    """Lazy import of cache module."""
    global _semantic_cache_module
    if _semantic_cache_module is None:
        try:
            from agentic_brain import cache as cache_mod

            _semantic_cache_module = cache_mod
        except ImportError:
            _semantic_cache_module = _MODULE_UNAVAILABLE  # Mark as unavailable
    if _semantic_cache_module is _MODULE_UNAVAILABLE:
        return None
    return _semantic_cache_module


def _get_unified_brain_class() -> type[UnifiedBrain] | None:
    """Lazy import of UnifiedBrain to avoid hard dependency cycles."""
    global _unified_brain_module
    if _unified_brain_module is None:
        try:
            from agentic_brain.unified_brain import UnifiedBrain as UnifiedBrainClass

            _unified_brain_module = UnifiedBrainClass
        except ImportError:
            _unified_brain_module = _MODULE_UNAVAILABLE
    if _unified_brain_module is _MODULE_UNAVAILABLE:
        return None
    return _unified_brain_module


logger = logging.getLogger(__name__)

# Re-export for convenience
__all__ = [
    "LLMRouter",
    "RouterConfig",
    "Provider",
    "Response",
    "Message",
    "get_router",
    "chat_async",
    "chat",
]


class LLMRouter(LLMRouterCore):
    """
    Production-grade router that extends :class:`LLMRouterCore`.

    ``LLMRouterCore`` provides the dependency-light baseline (message normalization,
    alias resolution, retry/backoff, and cost tracking). ``LLMRouter`` builds on
    that foundation to add streaming, semantic caching, Redis coordination, HTTP
    pooling, and additional providers beyond the lightweight core.

    Features:
    - Local-first (Ollama) for privacy and cost
    - Automatic fallback to cloud on failure
    - Extended provider support (Azure, Groq, Together, Google, xAI)
    - Streaming responses and pooled HTTP transport
    - Semantic + Redis caches for cost reduction
    - Smart routing heuristics and UnifiedBrain integration

    Example:
        >>> router = LLMRouter()
        >>>
        >>> # Async chat
        >>> response = await router.chat("What is Python?")
        >>> print(response.content)
        >>>
        >>> # With system prompt
        >>> response = await router.chat(
        ...     "Explain this code",
        ...     system="You are a helpful coding assistant"
        ... )
        >>>
        >>> # Force specific provider
        >>> response = await router.chat("Hello", provider=Provider.OPENAI)
        >>>
        >>> # Sync wrapper for CLI
        >>> response = router.chat_sync("Hello")
    """

    # Fallback chain: try these in order
    FALLBACK_CHAIN: list[tuple[Provider, str]] = [
        (Provider.OLLAMA, "llama3.1:8b"),
        (Provider.GROQ, "llama-3.1-8b-instant"),
        (Provider.OPENROUTER, "meta-llama/llama-3-8b-instruct:free"),
        (Provider.OPENAI, "gpt-4o-mini"),
        (Provider.ANTHROPIC, "claude-3-haiku-20240307"),
        (Provider.TOGETHER, "meta-llama/Llama-3.1-8B-Instruct-Turbo"),
    ]

    FASTEST_CHAIN: list[tuple[Provider, str]] = [
        (Provider.OLLAMA, "llama3.2:3b"),
        (Provider.GROQ, "llama-3.1-8b-instant"),
        (Provider.OPENROUTER, "meta-llama/llama-3-8b-instruct:free"),
        (Provider.OPENAI, "gpt-4o-mini"),
        (Provider.ANTHROPIC, "claude-3-haiku-20240307"),
        (Provider.TOGETHER, "meta-llama/Llama-3.1-8B-Instruct-Turbo"),
        (Provider.GOOGLE, "gemini-1.5-flash"),
        (Provider.XAI, "grok-2-mini"),
    ]

    CODE_CHAIN: list[tuple[Provider, str]] = [
        (Provider.ANTHROPIC, "claude-3-5-sonnet-20241022"),
        (Provider.OPENAI, "gpt-4o"),
        (Provider.OLLAMA, "llama3.1:8b"),
    ]

    REASONING_CHAIN: list[tuple[Provider, str]] = [
        (Provider.ANTHROPIC, "claude-3-sonnet-20240229"),
        (Provider.OPENAI, "gpt-4o"),
        (Provider.OLLAMA, "llama3.1:8b"),
    ]

    MODEL_PROVIDER_MAP: dict[str, Provider] = {
        "llama3.1:8b": Provider.OLLAMA,
        "llama3.2:3b": Provider.OLLAMA,
        "llama-3.1-8b-instant": Provider.GROQ,
        "meta-llama/llama-3-8b-instruct:free": Provider.OPENROUTER,
        "gpt-4o": Provider.OPENAI,
        "gpt-4o-mini": Provider.OPENAI,
        "claude-3-haiku-20240307": Provider.ANTHROPIC,
        "claude-3-sonnet-20240229": Provider.ANTHROPIC,
        "claude-3-5-sonnet-20241022": Provider.ANTHROPIC,
        "meta-llama/Llama-3.1-8B-Instruct-Turbo": Provider.TOGETHER,
        "gemini-1.5-flash": Provider.GOOGLE,
        "grok-2-mini": Provider.XAI,
    }

    def __init__(
        self,
        config: RouterConfig | None = None,
        redis_cache: RedisRouterCache | RedisInterBotComm | None = None,
        unified_brain: UnifiedBrain | None = None,
    ):
        """
        Initialize LLM router.

        Args:
            config: Router configuration
            redis_cache: Optional Redis-backed cache for inter-bot coordination
            unified_brain: Optional UnifiedBrain instance for high-level routing
        """
        super().__init__(config=config)
        self.redis_cache: RedisRouterCache | RedisInterBotComm | None = redis_cache
        self._prefer_brain_routing = unified_brain is not None
        self.unified_brain: UnifiedBrain | None = (
            unified_brain if unified_brain is not None else self._build_unified_brain()
        )

        # Cached availability check
        self._ollama_available: bool | None = None
        self._ollama_check_time: float = 0
        self._cache_ttl: float = 30.0  # seconds

        # HTTP pool reference (lazy loaded)
        self._http_pool: Any | None = None

        # HTTP pool usage metrics (use lists for mutability in closures)
        self._pool_requests: list[int] = [0]
        self._direct_requests: list[int] = [0]

        self._provider_rr_index: int = 0
        self._provider_usage: dict[str, int] = {}

        # Semantic prompt cache (lazy loaded)
        self._semantic_cache: Any | None = None
        self._cache_initialized: bool = False

    def _build_unified_brain(self) -> UnifiedBrain | None:
        """Create UnifiedBrain if it is available."""
        brain_cls = _get_unified_brain_class()
        if brain_cls is None:
            return None

        try:
            return brain_cls(router=self, redis_cache=self.redis_cache)
        except Exception as exc:
            logger.debug(f"UnifiedBrain unavailable: {exc}")
            return None

    def _get_http_pool(self) -> Any | None:
        """Get HTTP pool if configured and available.

        Auto-starts the pool on first use if not already started.
        Falls back to None if start fails, allowing direct requests to be used.
        """
        if not self.config.use_http_pool:
            return None

        if self._http_pool is not None:
            return self._http_pool

        try:
            from agentic_brain.pooling import PoolManager

            manager = PoolManager.get_instance()
            if manager.is_started:
                self._http_pool = manager.http
                return self._http_pool
            else:
                # Try to start the pool if not already started
                logger.debug("HTTP pool not started, attempting to start it")
                try:
                    manager.start()
                    if manager.is_started:
                        self._http_pool = manager.http
                        logger.debug("HTTP pool started successfully")
                        return self._http_pool
                except Exception as start_error:
                    logger.debug(f"Failed to start HTTP pool: {start_error}")
        except Exception as e:
            logger.debug(f"HTTP pool not available: {e}")

        return None

    async def _get_or_start_http_pool(self) -> Any | None:
        """Async version: Get or start HTTP pool.

        This is the recommended way to use the HTTP pool from async contexts,
        as it properly awaits the PoolManager.start() method.

        Returns:
            HTTPPool instance if available and started, None otherwise.
        """
        if not self.config.use_http_pool:
            return None

        if self._http_pool is not None:
            return self._http_pool

        try:
            from agentic_brain.pooling import PoolManager

            manager = PoolManager.get_instance()
            if manager.is_started:
                self._http_pool = manager.http
                return self._http_pool
            else:
                logger.debug("HTTP pool not started, attempting to start it (async)")
                try:
                    await manager.start()
                    if manager.is_started:
                        self._http_pool = manager.http
                        logger.debug("HTTP pool started successfully (async)")
                        return self._http_pool
                except Exception as start_error:
                    logger.debug(f"Failed to start HTTP pool (async): {start_error}")
        except Exception as e:
            logger.debug(f"HTTP pool not available (async): {e}")

        return None

    def get_pool_stats(self) -> dict[str, int | bool]:
        """
        Get HTTP pool usage statistics.

        Returns:
            Dictionary containing:
            - pool_enabled: bool - whether pool is configured
            - pool_started: bool - whether pool has been started
            - requests_via_pool: int - count of successful pool requests
            - requests_direct: int - count of direct session requests
        """
        from agentic_brain.pooling import PoolManager

        manager = PoolManager.get_instance()
        return {
            "pool_enabled": self.config.use_http_pool,
            "pool_started": manager.is_started,
            "requests_via_pool": self._pool_requests[0],
            "requests_direct": self._direct_requests[0],
        }

    def _get_semantic_cache(self) -> Any | None:
        """Get or initialize semantic cache (lazy loading)."""
        if self._cache_initialized:
            return self._semantic_cache

        self._cache_initialized = True

        if not self.config.cache_enabled:
            logger.debug("Semantic cache disabled in config")
            return None

        cache_module = _get_cache_module()
        if cache_module is None:
            logger.debug("Cache module not available")
            return None

        try:
            cache_config = cache_module.CacheConfig(
                enabled=self.config.cache_enabled,
                ttl_seconds=self.config.cache_ttl_seconds,
                max_entries=self.config.cache_max_entries,
                backend=self.config.cache_backend,
                normalize_whitespace=self.config.cache_normalize_whitespace,
                sqlite_path=self.config.cache_sqlite_path,
                redis_url=self.config.cache_redis_url,
            )
            self._semantic_cache = cache_module.SemanticCache(cache_config)
            logger.info(
                f"Semantic cache initialized: ttl={self.config.cache_ttl_seconds}s, "
                f"max={self.config.cache_max_entries}"
            )
            return self._semantic_cache
        except Exception as e:
            logger.warning(f"Failed to initialize semantic cache: {e}")
            return None

    def get_cache_stats(self) -> dict[str, Any] | None:
        """
        Get semantic cache statistics.

        Returns:
            Dictionary with cache stats or None if cache disabled
        """
        cache = self._get_semantic_cache()
        if cache is None:
            return None
        return cache.get_stats().to_dict()

    async def clear_cache(self) -> int:
        """Clear all cached responses. Returns count cleared."""
        cache = self._get_semantic_cache()
        if cache is None:
            return 0
        return await cache.clear()

    def _track_tokens(self, tokens: int, provider_name: str) -> None:
        """Track token usage for a provider.

        Args:
            tokens: Number of tokens used
            provider_name: Name of the provider
        """
        self._total_tokens += tokens
        self._tokens_by_provider[provider_name] = (
            self._tokens_by_provider.get(provider_name, 0) + tokens
        )

    def _record_provider_use(self, provider: Provider) -> None:
        """Record a provider selection for load-balancing decisions."""
        key = provider.value
        self._provider_usage[key] = self._provider_usage.get(key, 0) + 1

    @staticmethod
    def _route_allowed(
        route: tuple[Provider, str], security_guard: LLMSecurityGuard | None
    ) -> bool:
        return security_guard is None or security_guard.can_use_provider(route[0].value)

    def _available_routes(
        self, security_guard: LLMSecurityGuard | None = None
    ) -> list[tuple[Provider, str]]:
        """Return currently available provider/model routes."""
        routes: list[tuple[Provider, str]] = []

        if self._check_ollama():
            routes.extend(
                [
                    (Provider.OLLAMA, "llama3.2:3b"),
                    (Provider.OLLAMA, "llama3.1:8b"),
                ]
            )

        groq_key = self.config.groq_key or os.environ.get("GROQ_API_KEY")
        if groq_key:
            routes.append((Provider.GROQ, "llama-3.1-8b-instant"))

        # OpenRouter free models are available even without an API key.
        routes.append((Provider.OPENROUTER, "meta-llama/llama-3-8b-instruct:free"))

        openai_key = self.config.openai_key or os.environ.get("OPENAI_API_KEY")
        if openai_key:
            routes.append((Provider.OPENAI, "gpt-4o-mini"))
            routes.append((Provider.OPENAI, "gpt-4o"))

        anthropic_key = self.config.anthropic_key or os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            routes.append((Provider.ANTHROPIC, "claude-3-haiku-20240307"))
            routes.append((Provider.ANTHROPIC, "claude-3-sonnet-20240229"))
            routes.append((Provider.ANTHROPIC, "claude-3-5-sonnet-20241022"))

        together_key = self.config.together_key or os.environ.get("TOGETHER_API_KEY")
        if together_key:
            routes.append((Provider.TOGETHER, "meta-llama/Llama-3.1-8B-Instruct-Turbo"))

        google_key = self.config.google_key or os.environ.get("GOOGLE_API_KEY")
        if google_key:
            routes.append((Provider.GOOGLE, "gemini-1.5-flash"))

        xai_key = self.config.xai_key or os.environ.get("XAI_API_KEY")
        if xai_key:
            routes.append((Provider.XAI, "grok-2-mini"))

        return [route for route in routes if self._route_allowed(route, security_guard)]

    def _select_balanced_route(
        self, routes: list[tuple[Provider, str]]
    ) -> tuple[Provider, str]:
        """Select the least-used available route."""
        if not routes:
            return self.FALLBACK_CHAIN[0]

        return min(
            enumerate(routes),
            key=lambda item: (
                self._provider_usage.get(item[1][0].value, 0),
                self._provider_rr_index + item[0],
            ),
        )[1]

    def _first_available_route(
        self,
        candidates: list[tuple[Provider, str]],
        security_guard: LLMSecurityGuard | None = None,
    ) -> tuple[Provider, str]:
        """Return the first available route from a candidate list."""
        filtered_candidates = [
            route for route in candidates if self._route_allowed(route, security_guard)
        ]
        if not filtered_candidates:
            role = security_guard.role.value if security_guard else "unknown"
            raise PermissionError(f"No allowed LLM providers are available for role '{role}'.")

        available_routes = self._available_routes(security_guard=security_guard)
        available = set(available_routes)
        for route in filtered_candidates:
            if route in available:
                return route
        if available_routes:
            return self._select_balanced_route(available_routes)
        return filtered_candidates[0]

    def _first_available_model(
        self,
        candidates: list[tuple[Provider, str]],
        security_guard: LLMSecurityGuard | None = None,
    ) -> str:
        """Return the model string for the first available route."""
        return self._first_available_route(
            candidates, security_guard=security_guard
        )[1]

    def _provider_is_configured(self, provider: Provider) -> bool:
        """Return whether a provider can be selected conceptually."""
        if provider == Provider.OLLAMA:
            return True
        if provider == Provider.OPENROUTER:
            return True
        if provider == Provider.OPENAI:
            return bool(self.config.openai_key or os.environ.get("OPENAI_API_KEY"))
        if provider == Provider.AZURE_OPENAI:
            return bool(
                self.config.azure_openai_key or os.environ.get("AZURE_OPENAI_API_KEY")
            )
        if provider == Provider.ANTHROPIC:
            return bool(
                self.config.anthropic_key or os.environ.get("ANTHROPIC_API_KEY")
            )
        if provider == Provider.GROQ:
            return bool(self.config.groq_key or os.environ.get("GROQ_API_KEY"))
        if provider == Provider.TOGETHER:
            return bool(self.config.together_key or os.environ.get("TOGETHER_API_KEY"))
        if provider == Provider.GOOGLE:
            return bool(self.config.google_key or os.environ.get("GOOGLE_API_KEY"))
        if provider == Provider.XAI:
            return bool(self.config.xai_key or os.environ.get("XAI_API_KEY"))
        return False

    def _first_configured_route(
        self,
        candidates: list[tuple[Provider, str]],
        security_guard: LLMSecurityGuard | None = None,
    ) -> tuple[Provider, str]:
        """Return the first route whose provider is configured."""
        filtered_candidates = [
            route for route in candidates if self._route_allowed(route, security_guard)
        ]
        if not filtered_candidates:
            role = security_guard.role.value if security_guard else "unknown"
            raise PermissionError(f"No allowed LLM providers are available for role '{role}'.")

        for route in filtered_candidates:
            if self._provider_is_configured(route[0]):
                return route
        return filtered_candidates[-1]

    @staticmethod
    def _merge_route_lists(
        *route_groups: list[tuple[Provider, str]],
    ) -> list[tuple[Provider, str]]:
        """Merge route groups while preserving order and removing duplicates."""
        merged: list[tuple[Provider, str]] = []
        seen: set[tuple[Provider, str]] = set()

        for group in route_groups:
            for route in group:
                if route not in seen:
                    merged.append(route)
                    seen.add(route)

        return merged

    def _fallback_routes_for(
        self,
        provider: Provider,
        model: str,
        message: str,
    ) -> list[tuple[Provider, str]]:
        """Build an ordered fallback list for the current request."""
        primary_route = (provider, model)
        prioritized_routes: list[tuple[Provider, str]] = []

        if primary_route in self.REASONING_CHAIN:
            prioritized_routes = self.REASONING_CHAIN
        elif primary_route in self.CODE_CHAIN or self._is_code_task(message):
            prioritized_routes = self.CODE_CHAIN

        merged_routes = self._merge_route_lists(prioritized_routes, self.FALLBACK_CHAIN)
        return [route for route in merged_routes if route != primary_route]

    def _route_from_brain(self, message: str) -> tuple[Provider, str] | None:
        """Use UnifiedBrain to choose a route when available."""
        if self.unified_brain is None:
            return None

        route_task = getattr(self.unified_brain, "route_task", None)
        if not callable(route_task):
            return None

        try:
            prefer_free = not self._is_code_task(message)
            bot_name = route_task(message, prefer_free=prefer_free)
        except TypeError:
            bot_name = route_task(message)
        except Exception as exc:
            logger.debug(f"UnifiedBrain routing failed: {exc}")
            return None

        bot = getattr(self.unified_brain, "bots", {}).get(bot_name)
        if bot is not None:
            provider = self._map_unified_provider(getattr(bot, "provider", ""))
            model = getattr(bot, "model", None)
            if provider and model:
                return provider, model

        return self._route_from_bot_name(bot_name, message)

    @staticmethod
    def _map_unified_provider(provider_name: str) -> Provider | None:
        """Map UnifiedBrain provider names to Provider enum."""
        if not provider_name:
            return None
        key = provider_name.lower()
        if key == "grok":
            return Provider.XAI
        try:
            return Provider(key)
        except ValueError:
            return None

    def _route_from_bot_name(
        self, bot_name: str | None, message: str
    ) -> tuple[Provider, str] | None:
        """Convert a UnifiedBrain bot name into a provider/model route."""
        if not bot_name:
            return None

        bot_lower = bot_name.lower()
        if "deepseek" in bot_lower or "coder" in bot_lower or "code" in bot_lower:
            return Provider.OPENROUTER, "meta-llama/llama-3-8b-instruct:free"
        if "claude" in bot_lower:
            return Provider.ANTHROPIC, "claude-3-5-sonnet-20241022"
        if "gpt" in bot_lower:
            return Provider.OPENAI, "gpt-4o"
        if "groq" in bot_lower:
            return Provider.GROQ, "llama-3.1-8b-instant"
        if "ollama" in bot_lower or "llama" in bot_lower:
            if self._is_code_task(message):
                return self._first_available_route(self.CODE_CHAIN)
            return self._first_available_route(self.FASTEST_CHAIN)
        return None

    def _is_code_task(self, message: str) -> bool:
        """Detect whether a message is coding-oriented."""
        msg_lower = message.lower()
        code_keywords = (
            "code",
            "coding",
            "implement",
            "function",
            "class",
            "refactor",
            "debug",
            "bug",
            "test",
            "python",
            "javascript",
            "typescript",
            "go ",
            "rust",
            "sql",
        )
        return any(keyword in msg_lower for keyword in code_keywords)

    def _model_to_provider(self, model: str) -> Provider:
        """Infer provider from a model name."""
        return self.MODEL_PROVIDER_MAP.get(model, self.config.default_provider)

    async def _is_ollama_available(self) -> bool:
        """Check Ollama availability with caching."""
        from .ollama import check_ollama_available

        now = time.time()
        if (
            self._ollama_available is not None
            and (now - self._ollama_check_time) < self._cache_ttl
        ):
            return self._ollama_available

        pool = self._get_http_pool()
        self._ollama_available = await check_ollama_available(
            self.config.ollama_host, pool
        )
        self._ollama_check_time = now
        return self._ollama_available

    def _check_ollama(self) -> bool:
        """Sync check for Ollama (for backwards compat)."""
        if self._ollama_available is not None:
            return self._ollama_available

        self._ollama_available = check_ollama_sync(self.config.ollama_host)
        return self._ollama_available or False

    async def _post_request(
        self,
        url: str,
        json_data: dict[str, Any],
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, dict[str, Any] | str]:
        """Make a POST request using HTTP pool if available."""
        timeout = timeout or self.config.timeout
        pool = self._get_http_pool()
        return await post_request(
            url,
            json_data,
            headers,
            timeout,
            pool,
            self._pool_requests,
            self._direct_requests,
        )

    async def _get_request(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, dict[str, Any] | str]:
        """Make a GET request using HTTP pool if available."""
        timeout = timeout or self.config.timeout
        pool = self._get_http_pool()
        return await get_request(
            url,
            headers,
            timeout,
            pool,
            self._pool_requests,
            self._direct_requests,
        )

    def get_fastest_available(self) -> str:
        """Get the fastest available LLM."""
        return self._first_available_model(self.FASTEST_CHAIN)

    def get_best_for_code(self) -> str:
        """Get the best available model for coding tasks."""
        return self._first_available_model(self.CODE_CHAIN)

    def distribute_load(self, tasks: list[str]) -> dict[str, list[str]]:
        """Distribute tasks across multiple LLMs."""
        routes = self._available_routes()
        if not routes:
            routes = self.FALLBACK_CHAIN

        distribution: dict[str, list[str]] = {}
        rr_index = self._provider_rr_index

        for task in tasks:
            if self._prefer_brain_routing and self.unified_brain is not None:
                route = self._route_from_brain(task)
            else:
                route = None

            if route is None:
                if self._is_code_task(task):
                    route = self._first_available_route(self.CODE_CHAIN)
                else:
                    route = routes[rr_index % len(routes)]
                    rr_index += 1

            key = f"{route[0].value}:{route[1]}"
            distribution.setdefault(key, []).append(task)
            self._record_provider_use(route[0])

        self._provider_rr_index = rr_index
        return distribution

    def smart_route(
        self, message: str, security_guard: LLMSecurityGuard | None = None
    ) -> tuple[Provider, str]:
        """
        Determine the best provider and model for a given message.

        Args:
            message: User message

        Returns:
            Tuple of (Provider, model_name)
        """
        brain_route = (
            self._route_from_brain(message) if self._prefer_brain_routing else None
        )
        if brain_route is not None and self._route_allowed(brain_route, security_guard):
            self._record_provider_use(brain_route[0])
            return brain_route

        msg_lower = message.lower()

        # 1. Short, simple queries -> Local fast model when available
        if (
            len(message) < 50
            and "complex" not in msg_lower
            and "code" not in msg_lower
            and "analyze" not in msg_lower
        ):
            route = self._first_configured_route(
                self.FASTEST_CHAIN, security_guard=security_guard
            )
            self._record_provider_use(route[0])
            return route

        # 2. Complex reasoning / detailed analysis
        if "analyze" in msg_lower or "reasoning" in msg_lower or "complex" in msg_lower:
            route = self._first_configured_route(
                self.REASONING_CHAIN, security_guard=security_guard
            )
            self._record_provider_use(route[0])
            return route

        # 3. Coding tasks
        if self._is_code_task(message):
            route = self._first_configured_route(
                self.CODE_CHAIN, security_guard=security_guard
            )
            self._record_provider_use(route[0])
            return route

        # Default -> Prefer configured default provider/model when available.
        preferred_route = (self.config.default_provider, self.config.default_model)
        if self._provider_is_configured(self.config.default_provider) and self._route_allowed(
            preferred_route, security_guard
        ):
            route = preferred_route
        else:
            route = self._first_configured_route(
                self.FALLBACK_CHAIN, security_guard=security_guard
            )
        self._record_provider_use(route[0])
        return route

    async def chat(
        self,
        message: str,
        system: str | None = None,
        messages: list[dict[str, str] | Message] | None = None,
        provider: Provider | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        use_cache: bool = True,
        persona: str | None = None,
        role: SecurityRole | str | None = None,
        user_id: str | None = None,
        security_guard: LLMSecurityGuard | None = None,
    ) -> Response:
        """
        Send chat message to LLM (async).

        Args:
            message: User message
            system: System prompt
            provider: Force specific provider
            model: Force specific model
            temperature: Response randomness (0-1)
            use_cache: Whether to use semantic cache (default True)

        Returns:
            LLM response (may be cached)

        Example:
            >>> response = await router.chat("Hello!")
            >>> print(response.content)
            >>> print(f"Cached: {response.cached}")
        """
        guard = security_guard or LLMSecurityGuard(role)
        rate_limit_user = user_id or guard.default_user_id()
        if not guard.check_rate_limit(rate_limit_user):
            raise RateLimitError(
                limit=guard.permissions.requests_per_minute or 0,
                window="1 minute",
                retry_after=max(1, guard.last_retry_after_seconds),
            )

        # Apply persona if specified
        if persona:
            from agentic_brain.personas import get_persona

            p = get_persona(persona)
            if p:
                # Persona ALWAYS overrides system prompt if provided
                system = p.format_system_prompt()
            else:
                logger.warning(f"Persona '{persona}' not found")

        normalized_messages = guard.filter_messages(
            self.normalize_messages(
                message=message, system=system, messages=messages
            )
        )
        filtered_system = next(
            (item["content"] for item in normalized_messages if item["role"] == "system"),
            None,
        )
        filtered_message = next(
            (
                item["content"]
                for item in reversed(normalized_messages)
                if item["role"] == "user"
            ),
            message,
        )
        route_message = filtered_message or self.prompt_text(normalized_messages)

        # Smart routing if no provider/model specified
        if provider is None and model is None:
            provider, model = self.smart_route(route_message, security_guard=guard)
        else:
            route = self.resolve_model(model, provider)
            provider, model = route.provider, route.model
            if not guard.can_use_provider(provider.value):
                raise PermissionError(
                    f"Role '{guard.role.value}' cannot use provider '{provider.value}'."
                )

        provider = provider or self.config.default_provider
        model = model or self.config.default_model
        prompt_text = self.prompt_text(normalized_messages)

        # Check semantic cache first
        cache = self._get_semantic_cache() if use_cache else None
        cache_key = None

        if cache is not None:
            cache_key = cache.create_key(
                prompt=prompt_text,
                system=system,
                model=model,
                temperature=temperature,
            )
            cached_response = await cache.get(cache_key)
            if cached_response is not None:
                logger.info(f"Cache HIT: model={model}, key={cache_key[:16]}...")
                return Response(
                    content=cached_response,
                    model=model,
                    provider=provider,
                    tokens_used=0,
                    finish_reason="cached",
                    cached=True,
                    cache_key=cache_key,
                )

        # Check Redis InterBot Cache if available (secondary cache)
        if use_cache and self.redis_cache and hasattr(self.redis_cache, "get_cached"):
            try:
                cached_data = self.redis_cache.get_cached(prompt_text)
                if cached_data:
                    logger.info("Redis InterBot Cache HIT")
                    return Response(
                        content=cached_data["response"],
                        model=cached_data.get("model", model),
                        provider=provider,
                        tokens_used=0,
                        finish_reason="cached",
                        cached=True,
                    )
            except Exception as e:
                logger.warning(f"Failed to read from Redis cache: {e}")

        logger.info(f"Attempting LLM call: provider={provider.value}, model={model}")
        logger.debug(
            f"Request: messages=1, temperature={temperature}, "
            f"system_prompt={'yes' if system else 'no'}"
        )

        # Try primary provider (uses internal methods for testability)
        response = None
        try:
            if messages is not None and provider in {
                Provider.OLLAMA,
                Provider.OPENAI,
                Provider.ANTHROPIC,
            }:
                response = await self._chat_messages(
                    normalized_messages,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    security_guard=guard,
                )
            elif provider == Provider.OLLAMA:
                response = await self._chat_ollama(
                    filtered_message, filtered_system, model, temperature
                )
            elif provider == Provider.OPENAI:
                response = await self._chat_openai(
                    filtered_message, filtered_system, model, temperature
                )
            elif provider == Provider.AZURE_OPENAI:
                response = await self._chat_azure_openai(
                    filtered_message, filtered_system, model, temperature
                )
            elif provider == Provider.ANTHROPIC:
                response = await self._chat_anthropic(
                    filtered_message, filtered_system, model, temperature
                )
            elif provider == Provider.OPENROUTER:
                response = await self._chat_openrouter(
                    filtered_message, filtered_system, model, temperature
                )
            elif provider == Provider.GROQ:
                response = await self._chat_groq(
                    filtered_message, filtered_system, model, temperature
                )
            elif provider == Provider.TOGETHER:
                response = await self._chat_together(
                    filtered_message, filtered_system, model, temperature
                )
            elif provider == Provider.GOOGLE:
                response = await self._chat_google(
                    filtered_message, filtered_system, model, temperature
                )
            elif provider == Provider.XAI:
                response = await self._chat_xai(
                    filtered_message, filtered_system, model, temperature
                )

            # Cache successful response
            if response is not None:
                # Save to Semantic Cache
                if cache is not None and cache_key is not None:
                    await cache.set(
                        key=cache_key,
                        response=response.content,
                        model=model,
                        tokens_saved=response.tokens_used,
                    )
                    response.cache_key = cache_key

                # Save to Redis InterBot Cache
                if self.redis_cache and hasattr(self.redis_cache, "cache_response"):
                    try:
                        self.redis_cache.cache_response(
                            prompt=prompt_text,
                            response=response.content,
                            model=model or "unknown",
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save to Redis cache: {e}")

            if response is not None:
                return response

        except Exception as e:
            logger.warning(
                f"LLM provider failed, trying fallback: provider={provider.value}, "
                f"error={type(e).__name__}: {str(e)[:100]}"
            )

            if not self.config.fallback_enabled:
                raise

        # Fallback chain (uses internal methods for testability)
        for fallback_provider, fallback_model in self._fallback_routes_for(
            provider, model, message
        ):

            try:
                logger.info(
                    f"Trying fallback: provider={fallback_provider.value}, "
                    f"model={fallback_model}"
                )

                if messages is not None and fallback_provider in {
                    Provider.OLLAMA,
                    Provider.OPENAI,
                    Provider.ANTHROPIC,
                }:
                    response = await self._chat_messages(
                        normalized_messages,
                        provider=fallback_provider,
                        model=fallback_model,
                        temperature=temperature,
                    )
                elif fallback_provider == Provider.OLLAMA:
                    response = await self._chat_ollama(
                        message, system, fallback_model, temperature
                    )
                elif fallback_provider == Provider.OPENAI:
                    response = await self._chat_openai(
                        message, system, fallback_model, temperature
                    )
                elif fallback_provider == Provider.AZURE_OPENAI:
                    response = await self._chat_azure_openai(
                        message, system, fallback_model, temperature
                    )
                elif fallback_provider == Provider.ANTHROPIC:
                    response = await self._chat_anthropic(
                        message, system, fallback_model, temperature
                    )
                elif fallback_provider == Provider.OPENROUTER:
                    response = await self._chat_openrouter(
                        message, system, fallback_model, temperature
                    )
                elif fallback_provider == Provider.GROQ:
                    response = await self._chat_groq(
                        message, system, fallback_model, temperature
                    )
                elif fallback_provider == Provider.TOGETHER:
                    response = await self._chat_together(
                        message, system, fallback_model, temperature
                    )
                elif fallback_provider == Provider.GOOGLE:
                    response = await self._chat_google(
                        message, system, fallback_model, temperature
                    )
                elif fallback_provider == Provider.XAI:
                    response = await self._chat_xai(
                        message, system, fallback_model, temperature
                    )

                # Cache fallback response
                if response is not None and cache is not None and cache_key is not None:
                    await cache.set(
                        key=cache_key,
                        response=response.content,
                        model=fallback_model,
                        tokens_saved=response.tokens_used,
                    )
                    response.cache_key = cache_key

                if response is not None:
                    return response

            except Exception as e:
                logger.warning(
                    f"LLM provider failed, trying fallback: "
                    f"provider={fallback_provider.value}, "
                    f"error={type(e).__name__}: {str(e)[:100]}"
                )
                continue

        logger.error(
            "All LLM providers failed after exhausting fallback chain", exc_info=True
        )

        # Provide helpful error message
        status_dict = ProviderChecker.check_all()
        error_msg = format_error_message(status_dict)
        logger.error(error_msg)
        raise RuntimeError(f"All LLM providers failed.\n{error_msg}")

    # Internal methods for backward compatibility with tests
    async def _check_ollama_available(self) -> bool:
        """Check if Ollama is available (internal, for testing)."""
        from .ollama import check_ollama_available

        pool = self._get_http_pool()
        return await check_ollama_available(self.config.ollama_host, pool)

    async def _chat_ollama(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal Ollama chat method (for testing)."""
        return await super()._chat_ollama(message, system, model, temperature)

    async def _chat_openai(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal OpenAI chat method (for testing)."""
        return await super()._chat_openai(message, system, model, temperature)

    async def _chat_azure_openai(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal Azure OpenAI chat method (for testing)."""
        return await chat_azure_openai(
            message,
            system,
            model,
            temperature,
            self.config,
            self._post_request,
            self._track_tokens,
        )

    async def _chat_anthropic(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal Anthropic chat method (for testing)."""
        return await super()._chat_anthropic(message, system, model, temperature)

    async def _chat_openrouter(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal OpenRouter chat method (for testing)."""
        return await chat_openrouter(
            message,
            system,
            model,
            temperature,
            self.config,
            self._post_request,
            self._track_tokens,
        )

    async def _chat_groq(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal Groq chat method (for testing)."""
        return await chat_groq(
            message,
            system,
            model,
            temperature,
            self.config,
            self._post_request,
            self._track_tokens,
        )

    async def _chat_together(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal Together chat method (for testing)."""
        return await chat_together(
            message,
            system,
            model,
            temperature,
            self.config,
            self._post_request,
            self._track_tokens,
        )

    async def _chat_google(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal Google chat method (for testing)."""
        return await chat_google(
            message,
            system,
            model,
            temperature,
            self.config,
            self._post_request,
            self._track_tokens,
        )

    async def _chat_xai(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal xAI chat method (for testing)."""
        return await chat_xai(
            message,
            system,
            model,
            temperature,
            self.config,
            self._post_request,
            self._track_tokens,
        )

    async def _stream_ollama(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Internal Ollama streaming method (for testing)."""
        async for token in stream_ollama(
            message, system, model, temperature, self.config, self._is_ollama_available
        ):
            yield token

    async def _stream_openai(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Internal OpenAI streaming method (for testing)."""
        async for token in stream_openai(
            message, system, model, temperature, self.config
        ):
            yield token

    async def _stream_azure_openai(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Internal Azure OpenAI streaming method (for testing)."""
        async for token in stream_azure_openai(
            message, system, model, temperature, self.config
        ):
            yield token

    async def _stream_anthropic(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Internal Anthropic streaming method (for testing)."""
        async for token in stream_anthropic(
            message, system, model, temperature, self.config
        ):
            yield token

    async def _stream_openrouter(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Internal OpenRouter streaming method (for testing)."""
        async for token in stream_openrouter(
            message, system, model, temperature, self.config
        ):
            yield token

    async def _stream_groq(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Internal Groq streaming method (for testing)."""
        async for token in stream_groq(
            message, system, model, temperature, self.config
        ):
            yield token

    async def _stream_together(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Internal Together streaming method (for testing)."""
        async for token in stream_together(
            message, system, model, temperature, self.config
        ):
            yield token

    async def _stream_google(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Internal Google streaming method (for testing)."""
        async for token in stream_google(
            message, system, model, temperature, self.config
        ):
            yield token

    async def _stream_xai(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Internal xAI streaming method (for testing)."""
        async for token in stream_xai(message, system, model, temperature, self.config):
            yield token

    def chat_sync(
        self,
        message: str,
        system: str | None = None,
        provider: Provider | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> Response:
        """
        Synchronous wrapper for chat (for CLI usage).

        Args:
            message: User message
            system: System prompt
            provider: Force specific provider
            model: Force specific model
            temperature: Response randomness (0-1)

        Returns:
            LLM response
        """
        return asyncio.run(
            self.chat(
                message=message,
                system=system,
                provider=provider,
                model=model,
                temperature=temperature,
            )
        )

    async def stream(
        self,
        message: str,
        system: str | None = None,
        provider: Provider | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response tokens (async generator).

        Args:
            message: User message
            system: System prompt
            provider: Force specific provider
            model: Force specific model
            temperature: Response randomness (0-1)

        Yields:
            Response tokens as they arrive

        Example:
            >>> async for token in router.stream("Hello!"):
            ...     print(token, end="", flush=True)
        """
        provider = provider or self.config.default_provider
        model = model or self.config.default_model

        if provider == Provider.OLLAMA:
            async for token in self._stream_ollama(message, system, model, temperature):
                yield token
        elif provider == Provider.OPENAI:
            async for token in self._stream_openai(message, system, model, temperature):
                yield token
        elif provider == Provider.AZURE_OPENAI:
            async for token in self._stream_azure_openai(
                message, system, model, temperature
            ):
                yield token
        elif provider == Provider.ANTHROPIC:
            async for token in self._stream_anthropic(
                message, system, model, temperature
            ):
                yield token
        elif provider == Provider.OPENROUTER:
            async for token in self._stream_openrouter(
                message, system, model, temperature
            ):
                yield token
        elif provider == Provider.GROQ:
            async for token in self._stream_groq(message, system, model, temperature):
                yield token
        elif provider == Provider.TOGETHER:
            async for token in self._stream_together(
                message, system, model, temperature
            ):
                yield token
        elif provider == Provider.GOOGLE:
            async for token in self._stream_google(message, system, model, temperature):
                yield token
        elif provider == Provider.XAI:
            async for token in self._stream_xai(message, system, model, temperature):
                yield token

    async def list_local_models_async(self) -> list[str]:
        """List available Ollama models (async)."""
        return await list_models_async(
            self.config.ollama_host, self._is_ollama_available
        )

    def list_local_models(self) -> list[str]:
        """List available Ollama models (sync)."""
        return list_models_sync(self.config.ollama_host, self._check_ollama())

    async def __aenter__(self) -> LLMRouter:
        """Async context manager entry - starts HTTP pool if enabled."""
        if self.config.use_http_pool:
            await self._get_or_start_http_pool()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit - cleanup."""
        # Reset pool reference (actual pool managed by PoolManager singleton)
        self._http_pool = None
        return None

    @property
    def is_local_available(self) -> bool:
        """Check if local LLM is available (sync)."""
        return self._check_ollama()

    async def is_local_available_async(self) -> bool:
        """Check if local LLM is available (async)."""
        return await self._is_ollama_available()

    async def check_all_providers(self) -> dict[str, dict[str, Any]]:
        """
        Check availability of all LLM providers.

        Returns:
            Dict with provider status:
            {
                'ollama': {'available': bool, 'models': list[str] | None},
                'openai': {'available': bool, 'reason': str},
                'anthropic': {'available': bool, 'reason': str},
                'openrouter': {'available': bool, 'reason': str},
            }
        """
        result = {}

        # Check Ollama - actually ping it and list models
        try:
            ollama_available = await self._is_ollama_available()
            ollama_models = None
            if ollama_available:
                ollama_models = await self.list_local_models_async()
            result["ollama"] = {"available": ollama_available, "models": ollama_models}
        except Exception as e:
            logger.debug(f"Error checking Ollama: {e}")
            result["ollama"] = {"available": False, "models": None}

        # Check OpenAI - verify API key is configured
        openai_key = self.config.openai_key or os.environ.get("OPENAI_API_KEY")
        if openai_key:
            result["openai"] = {"available": True, "reason": "API key configured"}
        else:
            result["openai"] = {"available": False, "reason": "No API key found"}

        # Check Anthropic - verify API key is configured
        anthropic_key = self.config.anthropic_key or os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            result["anthropic"] = {"available": True, "reason": "API key configured"}
        else:
            result["anthropic"] = {"available": False, "reason": "No API key found"}

        # Check OpenRouter - verify API key (note: works without key for free models)
        openrouter_key = self.config.openrouter_key or os.environ.get(
            "OPENROUTER_API_KEY"
        )
        if openrouter_key:
            result["openrouter"] = {"available": True, "reason": "API key configured"}
        else:
            result["openrouter"] = {
                "available": True,
                "reason": "Free models available without API key",
            }

        return result

    def check_all_providers_sync(self) -> dict[str, dict[str, Any]]:
        """Sync wrapper for check_all_providers."""
        return asyncio.run(self.check_all_providers())


# Convenience function
_default_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Get or create default router."""
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter()
    return _default_router


async def chat_async(message: str, **kwargs: Any) -> Response:
    """Quick async chat using default router."""
    return await get_router().chat(message, **kwargs)


def chat(message: str, **kwargs: Any) -> Response:
    """Quick sync chat using default router."""
    return get_router().chat_sync(message, **kwargs)
