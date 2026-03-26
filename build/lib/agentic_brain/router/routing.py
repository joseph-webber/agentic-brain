# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

# SPDX-License-Identifier: GPL-3.0-or-later
"""
Main LLMRouter class with routing logic.

This is the main entry point for LLM routing. It:
- Manages provider selection and fallback
- Handles HTTP pooling
- Tracks token usage
- Provides both sync and async interfaces
- Implements semantic prompt caching for cost reduction
"""


import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from typing import Optional, TYPE_CHECKING

from .anthropic import chat_anthropic, stream_anthropic
from .azure_openai import chat_azure_openai, stream_azure_openai
from .config import Message, Model, Provider, Response, RouterConfig
from .google import chat_google, stream_google
from .groq import chat_groq, stream_groq
from .http import get_request, post_request
from .ollama import (
    chat_ollama,
    check_ollama_sync,
    list_models_async,
    list_models_sync,
    stream_ollama,
)
from .openai import chat_openai, stream_openai
from .openrouter import chat_openrouter, stream_openrouter
from .provider_checker import (
    ProviderChecker,
    format_error_message,
    format_provider_status_report,
)
from .together import chat_together, stream_together
from .xai import chat_xai, stream_xai

# Optional import for typing without forcing Redis dependency
if TYPE_CHECKING:
    from .redis_cache import RedisInterBotComm, RedisRouterCache

# Lazy import for cache to avoid circular dependencies
_semantic_cache_module = None


def _get_cache_module():
    """Lazy import of cache module."""
    global _semantic_cache_module
    if _semantic_cache_module is None:
        try:
            from agentic_brain import cache as cache_mod

            _semantic_cache_module = cache_mod
        except ImportError:
            _semantic_cache_module = False  # Mark as unavailable
    return _semantic_cache_module if _semantic_cache_module else None


logger = logging.getLogger(__name__)

# Re-export for convenience
__all__ = [
    "LLMRouter",
    "RouterConfig",
    "Provider",
    "Response",
    "Message",
    "Model",
    "get_router",
    "chat_async",
    "chat",
]


class LLMRouter:
    """
    Intelligent LLM routing with automatic fallback (fully async).

    Features:
    - Local-first (Ollama) for privacy and cost
    - Automatic fallback to cloud on failure
    - Multiple provider support
    - Simple async chat interface
    - Cached availability checks

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
    FALLBACK_CHAIN = [
        (Provider.OLLAMA, "llama3.1:8b"),
        (Provider.OLLAMA, "llama3.2:3b"),
        (Provider.OPENROUTER, "meta-llama/llama-3-8b-instruct:free"),
    ]

    def __init__(
        self,
        config: RouterConfig | None = None,
        redis_cache: RedisRouterCache | RedisInterBotComm | None = None,
    ):
        """
        Initialize LLM router.

        Args:
            config: Router configuration
            redis_cache: Optional Redis-backed cache for inter-bot coordination
        """
        self.config = config or RouterConfig()
        self.redis_cache = redis_cache

        # Cached availability check
        self._ollama_available: bool | None = None
        self._ollama_check_time: float = 0
        self._cache_ttl: float = 30.0  # seconds

        # HTTP pool reference (lazy loaded)
        self._http_pool = None

        # HTTP pool usage metrics (use lists for mutability in closures)
        self._pool_requests: list[int] = [0]
        self._direct_requests: list[int] = [0]

        # Token usage tracking
        self._total_tokens: int = 0
        self._tokens_by_provider: dict[str, int] = {}

        # Semantic prompt cache (lazy loaded)
        self._semantic_cache = None
        self._cache_initialized = False

    def _get_http_pool(self):
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

    async def _get_or_start_http_pool(self):
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

    def get_pool_stats(self) -> dict:
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

    def get_token_stats(self) -> dict:
        """
        Get token usage statistics.

        Returns:
            Dict with token counts:
            {
                'total_tokens': int,
                'by_provider': {'ollama': int, 'openai': int, ...},
            }
        """
        return {
            "total_tokens": self._total_tokens,
            "by_provider": dict(self._tokens_by_provider),
        }

    def reset_token_stats(self) -> None:
        """Reset token usage counters."""
        self._total_tokens = 0
        self._tokens_by_provider = {}

    def _get_semantic_cache(self):
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

    def get_cache_stats(self) -> dict | None:
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
        json_data: dict,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> tuple[int, dict | str]:
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
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> tuple[int, dict | str]:
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

    def smart_route(self, message: str) -> tuple[Provider, str]:
        """
        Determine the best provider and model for a given message.

        Args:
            message: User message

        Returns:
            Tuple of (Provider, model_name)
        """
        msg_lower = message.lower()

        # 1. Short, simple queries -> Local fast model (Always local for speed/cost)
        if len(message) < 50 and "complex" not in msg_lower and "code" not in msg_lower:
            return Provider.OLLAMA, "llama3.2:3b"

        # 2. Complex reasoning / detailed analysis
        if "analyze" in msg_lower or "reasoning" in msg_lower or "complex" in msg_lower:
            # Prefer Anthropic for reasoning
            if self.config.anthropic_key:
                return Provider.ANTHROPIC, "claude-3-sonnet-20240229"
            # Fallback to OpenAI
            if self.config.openai_key:
                return Provider.OPENAI, "gpt-4o"
            # Fallback to Local
            return Provider.OLLAMA, "llama3.1:8b"

        # 3. Coding tasks
        if "code" in msg_lower or "function" in msg_lower or "class" in msg_lower:
            # Prefer Anthropic for code
            if self.config.anthropic_key:
                return Provider.ANTHROPIC, "claude-3-5-sonnet-20241022"
            # Fallback to OpenAI
            if self.config.openai_key:
                return Provider.OPENAI, "gpt-4o"
            # Fallback to Local
            return Provider.OLLAMA, "llama3.1:8b"

        # Default -> Local standard model
        return Provider.OLLAMA, "llama3.1:8b"

    async def chat(
        self,
        message: str,
        system: str | None = None,
        provider: Provider | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        use_cache: bool = True,
        persona: str | None = None,
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
        # Smart routing if no provider/model specified
        if provider is None and model is None:
            provider, model = self.smart_route(message)

        provider = provider or self.config.default_provider
        model = model or self.config.default_model

        # Apply persona if specified
        if persona:
            from agentic_brain.personas import get_persona

            p = get_persona(persona)
            if p:
                # Persona ALWAYS overrides system prompt if provided
                system = p.format_system_prompt()
            else:
                logger.warning(f"Persona '{persona}' not found")

        # Check semantic cache first
        cache = self._get_semantic_cache() if use_cache else None
        cache_key = None

        if cache is not None:
            cache_key = cache.create_key(
                prompt=message,
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
                cached_data = self.redis_cache.get_cached(message)
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
            if provider == Provider.OLLAMA:
                response = await self._chat_ollama(message, system, model, temperature)
            elif provider == Provider.OPENAI:
                response = await self._chat_openai(message, system, model, temperature)
            elif provider == Provider.AZURE_OPENAI:
                response = await self._chat_azure_openai(
                    message, system, model, temperature
                )
            elif provider == Provider.ANTHROPIC:
                response = await self._chat_anthropic(
                    message, system, model, temperature
                )
            elif provider == Provider.OPENROUTER:
                response = await self._chat_openrouter(
                    message, system, model, temperature
                )
            elif provider == Provider.GROQ:
                response = await self._chat_groq(message, system, model, temperature)
            elif provider == Provider.TOGETHER:
                response = await self._chat_together(
                    message, system, model, temperature
                )
            elif provider == Provider.GOOGLE:
                response = await self._chat_google(message, system, model, temperature)
            elif provider == Provider.XAI:
                response = await self._chat_xai(message, system, model, temperature)

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
                            prompt=message,
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
        for fallback_provider, fallback_model in self.FALLBACK_CHAIN:
            if fallback_provider == provider:
                continue  # Skip the one that just failed

            try:
                logger.info(
                    f"Trying fallback: provider={fallback_provider.value}, "
                    f"model={fallback_model}"
                )

                if fallback_provider == Provider.OLLAMA:
                    response = await self._chat_ollama(
                        message, system, fallback_model, temperature
                    )
                elif fallback_provider == Provider.OPENROUTER:
                    response = await self._chat_openrouter(
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
        return await chat_ollama(
            message,
            system,
            model,
            temperature,
            self.config,
            self._is_ollama_available,
            self._post_request,
            self._track_tokens,
        )

    async def _chat_openai(
        self,
        message: str,
        system: str | None,
        model: str,
        temperature: float,
    ) -> Response:
        """Internal OpenAI chat method (for testing)."""
        return await chat_openai(
            message,
            system,
            model,
            temperature,
            self.config,
            self._post_request,
            self._track_tokens,
        )

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
        return await chat_anthropic(
            message,
            system,
            model,
            temperature,
            self.config,
            self._post_request,
            self._track_tokens,
        )

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

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
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

    async def check_all_providers(self) -> dict:
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

    def check_all_providers_sync(self) -> dict:
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


async def chat_async(message: str, **kwargs) -> Response:
    """Quick async chat using default router."""
    return await get_router().chat(message, **kwargs)


def chat(message: str, **kwargs) -> Response:
    """Quick sync chat using default router."""
    return get_router().chat_sync(message, **kwargs)
