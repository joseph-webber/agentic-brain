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

"""
Tests for agentic-brain router module (async).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.router import (
    LLMRouter,
    Model,
    Provider,
    Response,
    RouterConfig,
    chat,
    chat_async,
    get_router,
)


class TestProvider:
    """Test Provider enum."""

    def test_provider_values(self):
        """Test provider enum values."""
        assert Provider.OLLAMA.value == "ollama"
        assert Provider.OPENAI.value == "openai"
        assert Provider.ANTHROPIC.value == "anthropic"
        assert Provider.OPENROUTER.value == "openrouter"


class TestModel:
    """Test Model configuration."""

    def test_model_creation(self):
        """Test creating a model config."""
        model = Model("llama3:8b", Provider.OLLAMA, 8192)

        assert model.name == "llama3:8b"
        assert model.provider == Provider.OLLAMA
        assert model.context_length == 8192

    def test_builtin_models(self):
        """Test built-in model factories."""
        llama = Model.llama3_8b()
        assert llama.name == "llama3.1:8b"
        assert llama.provider == Provider.OLLAMA

        gpt = Model.gpt4o()
        assert gpt.name == "gpt-4o"
        assert gpt.provider == Provider.OPENAI
        assert gpt.supports_tools is True


class TestRouterConfig:
    """Test RouterConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = RouterConfig()

        assert config.default_provider == Provider.OLLAMA
        assert config.default_model == "llama3.1:8b"
        assert config.timeout == 60
        assert config.fallback_enabled is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = RouterConfig(
            default_provider=Provider.OPENAI,
            default_model="gpt-4o",
            timeout=120,
        )

        assert config.default_provider == Provider.OPENAI
        assert config.default_model == "gpt-4o"


class TestResponse:
    """Test Response dataclass."""

    def test_response_creation(self):
        """Test creating a response."""
        response = Response(
            content="Hello!",
            model="llama3.1:8b",
            provider=Provider.OLLAMA,
            tokens_used=50,
        )

        assert response.content == "Hello!"
        assert response.model == "llama3.1:8b"
        assert response.provider == Provider.OLLAMA
        assert response.tokens_used == 50


class TestLLMRouter:
    """Test LLMRouter class."""

    def test_router_creation(self):
        """Test creating a router."""
        router = LLMRouter()

        assert router.config is not None
        assert router.config.default_provider == Provider.OLLAMA

    def test_router_with_config(self):
        """Test router with custom config."""
        config = RouterConfig(timeout=30)
        router = LLMRouter(config)

        assert router.config.timeout == 30

    @patch("shutil.which")
    def test_ollama_not_available_sync(self, mock_which):
        """Test detecting Ollama not available (sync)."""
        mock_which.return_value = None

        router = LLMRouter()
        router._ollama_available = None  # Reset cache

        assert router._check_ollama() is False

    def test_cache_ttl_set(self):
        """Test cache TTL is properly set."""
        router = LLMRouter()
        assert router._cache_ttl == 30.0


@pytest.mark.asyncio
class TestLLMRouterAsync:
    """Test LLMRouter async functionality."""

    async def test_ollama_not_available_async(self):
        """Test detecting Ollama not available (async)."""
        router = LLMRouter()
        router._ollama_available = None

        with patch("shutil.which", return_value=None):
            result = await router._check_ollama_available()
            assert result is False

    async def test_cached_availability_check(self):
        """Test availability check uses cache."""
        router = LLMRouter()
        router._ollama_available = True
        router._ollama_check_time = 9999999999  # Far future

        # Should return cached value without checking
        result = await router._is_ollama_available()
        assert result is True


@pytest.mark.asyncio
class TestLLMRouterChat:
    """Test LLMRouter chat functionality (async)."""

    async def test_chat_ollama(self):
        """Test chatting via Ollama (async)."""
        router = LLMRouter()
        router._ollama_available = True
        router._ollama_check_time = 9999999999

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "message": {"content": "Hello from Ollama!"},
                "eval_count": 10,
            }
        )

        mock_session = AsyncMock()
        mock_session.post = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch(
            "aiohttp.ClientSession",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ):
            response = await router._chat_ollama("Hello", None, "llama3.1:8b", 0.7)

        assert response.content == "Hello from Ollama!"
        assert response.provider == Provider.OLLAMA

    async def test_chat_with_system_prompt(self):
        """Test chat includes system prompt (async)."""
        router = LLMRouter()
        router._ollama_available = True
        router._ollama_check_time = 9999999999

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "message": {"content": "System aware response"},
                "eval_count": 10,
            }
        )

        mock_session = AsyncMock()
        mock_session.post = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch(
            "aiohttp.ClientSession",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ):
            response = await router._chat_ollama(
                "Hello",
                "You are helpful.",
                "llama3.1:8b",
                0.7,
            )

        assert response.content == "System aware response"


class TestLLMRouterFallback:
    """Test LLMRouter fallback behavior."""

    def test_fallback_chain_defined(self):
        """Test fallback chain is defined."""
        assert len(LLMRouter.FALLBACK_CHAIN) > 0

        # First fallback should be Ollama
        first = LLMRouter.FALLBACK_CHAIN[0]
        assert first[0] == Provider.OLLAMA

    @pytest.mark.asyncio
    async def test_fallback_disabled(self):
        """Test fallback can be disabled."""
        router = LLMRouter(RouterConfig(fallback_enabled=False))
        router._ollama_available = True
        router._ollama_check_time = 9999999999

        with (
            patch.object(
                router, "_chat_messages", side_effect=Exception("Primary failed")
            ),
            pytest.raises(Exception, match="Primary failed"),
        ):
            await router.chat("Hello", provider=Provider.OLLAMA, model="llama3.1:8b")

    @pytest.mark.asyncio
    async def test_fallback_works(self):
        """Test fallback to next provider."""
        router = LLMRouter()
        router._ollama_available = True
        router._ollama_check_time = 9999999999

        async def fake_chat_messages(
            messages, *, provider, model, temperature, **kwargs
        ):
            if provider == Provider.OLLAMA:
                raise Exception("Ollama failed")
            raise AssertionError(f"Unexpected provider: {provider}")

        with (
            patch.object(router, "_chat_messages", side_effect=fake_chat_messages),
            patch.object(
                router,
                "_chat_openrouter",
                return_value=Response(
                    content="OpenRouter response",
                    model="free-model",
                    provider=Provider.OPENROUTER,
                ),
            ),
        ):
            response = await router.chat(
                "Hello",
                provider=Provider.OLLAMA,
                model="llama3.1:8b",
            )

        assert response.content == "OpenRouter response"
        assert response.provider == Provider.OPENROUTER

    @pytest.mark.asyncio
    async def test_code_fallback_prefers_claude_then_gpt_then_ollama(self):
        """Code requests should prefer OpenAI before dropping to local Ollama."""
        router = LLMRouter()
        router._ollama_available = True
        router._ollama_check_time = 9999999999

        seen_providers = []

        async def fake_chat_messages(
            messages, *, provider, model, temperature, **kwargs
        ):
            seen_providers.append(provider)
            if provider == Provider.ANTHROPIC:
                raise Exception("Anthropic failed")
            if provider == Provider.OPENAI:
                return Response(
                    content="OpenAI code fallback",
                    model="gpt-4o",
                    provider=Provider.OPENAI,
                )
            raise AssertionError(f"Unexpected provider: {provider}")

        with (
            patch.object(router, "_chat_messages", side_effect=fake_chat_messages),
            patch.object(router, "_chat_ollama") as mock_ollama,
        ):
            response = await router.chat(
                "Debug this Python function and fix the failing test",
                provider=Provider.ANTHROPIC,
                model="claude-3-5-sonnet-20241022",
            )

        assert response.content == "OpenAI code fallback"
        assert response.provider == Provider.OPENAI
        assert seen_providers == [Provider.ANTHROPIC, Provider.OPENAI]
        mock_ollama.assert_not_called()


@pytest.mark.asyncio
class TestLLMRouterModels:
    """Test model listing (async)."""

    async def test_list_local_models_async(self):
        """Test listing local Ollama models (async)."""
        router = LLMRouter()
        router._ollama_available = True
        router._ollama_check_time = 9999999999

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "models": [
                    {"name": "llama3.1:8b"},
                    {"name": "llama3.2:3b"},
                ]
            }
        )

        mock_session = AsyncMock()
        mock_session.get = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch(
            "aiohttp.ClientSession",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            ),
        ):
            models = await router.list_local_models_async()

        assert "llama3.1:8b" in models
        assert "llama3.2:3b" in models

    async def test_list_models_ollama_unavailable_async(self):
        """Test listing models when Ollama unavailable (async)."""
        router = LLMRouter()
        router._ollama_available = False
        router._ollama_check_time = 9999999999

        models = await router.list_local_models_async()

        assert models == []


class TestLLMRouterSync:
    """Test sync wrappers."""

    def test_list_models_sync(self):
        """Test listing models (sync wrapper)."""
        router = LLMRouter()
        router._ollama_available = False

        models = router.list_local_models()

        assert models == []

    def test_is_local_available_sync(self):
        """Test is_local_available property."""
        router = LLMRouter()
        router._ollama_available = False

        assert router.is_local_available is False


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_get_router_singleton(self):
        """Test get_router returns singleton."""
        router1 = get_router()
        router2 = get_router()

        assert router1 is router2

    @pytest.mark.asyncio
    async def test_chat_async_function(self):
        """Test async chat convenience function."""
        with patch.object(
            LLMRouter,
            "chat",
            return_value=Response(
                content="Quick response",
                model="test",
                provider=Provider.OLLAMA,
            ),
        ):
            response = await chat_async("Hello")
            assert response.content == "Quick response"

    def test_chat_sync_function(self):
        """Test sync chat convenience function."""
        with patch.object(
            LLMRouter,
            "chat_sync",
            return_value=Response(
                content="Sync response",
                model="test",
                provider=Provider.OLLAMA,
            ),
        ):
            response = chat("Hello")
            assert response.content == "Sync response"


@pytest.mark.asyncio
class TestStreaming:
    """Test streaming functionality."""

    async def test_stream_ollama_method_exists(self):
        """Test stream method exists."""
        router = LLMRouter()
        assert hasattr(router, "stream")
        assert hasattr(router, "_stream_ollama")
        assert hasattr(router, "_stream_openai")
        assert hasattr(router, "_stream_anthropic")
        assert hasattr(router, "_stream_openrouter")


class TestTokenTracking:
    """Test token usage tracking."""

    def test_initial_token_stats(self):
        """Test initial token stats are zero."""
        router = LLMRouter()
        stats = router.get_token_stats()
        assert stats["total_tokens"] == 0
        assert stats["by_provider"] == {}

    def test_reset_token_stats(self):
        """Test resetting token stats."""
        router = LLMRouter()
        router._total_tokens = 100
        router._tokens_by_provider = {"ollama": 100}
        router.reset_token_stats()
        assert router._total_tokens == 0
        assert router._tokens_by_provider == {}

    def test_token_stats_isolation(self):
        """Test that token stats are isolated per router instance."""
        router1 = LLMRouter()
        router2 = LLMRouter()

        router1._total_tokens = 50
        router1._tokens_by_provider = {"ollama": 50}

        stats1 = router1.get_token_stats()
        stats2 = router2.get_token_stats()

        assert stats1["total_tokens"] == 50
        assert stats2["total_tokens"] == 0


class TestAsyncContextManager:
    """Test async context manager support for LLMRouter."""

    @pytest.mark.asyncio
    async def test_context_manager_entry_exit(self):
        """Test context manager entry and exit."""
        async with LLMRouter() as router:
            assert router is not None
            assert isinstance(router, LLMRouter)

    @pytest.mark.asyncio
    async def test_context_manager_can_chat(self):
        """Test that chat works within async context manager."""
        async with LLMRouter() as router:
            # Just verify it doesn't crash and router is usable
            stats = router.get_pool_stats()
            assert "pool_enabled" in stats
            assert isinstance(stats["pool_enabled"], bool)

    @pytest.mark.asyncio
    async def test_context_manager_cleans_up(self):
        """Test that context manager cleans up pool reference on exit."""
        router = LLMRouter()
        # Before entering context, pool should be None
        assert router._http_pool is None

        async with router:
            # Inside context, pool reference may be set (if enabled)
            pass

        # After exiting context, pool reference should be reset to None
        assert router._http_pool is None

    @pytest.mark.asyncio
    async def test_context_manager_has_required_methods(self):
        """Test that LLMRouter has async context manager methods."""
        router = LLMRouter()
        assert hasattr(router, "__aenter__")
        assert hasattr(router, "__aexit__")
        assert callable(router.__aenter__)
        assert callable(router.__aexit__)


class TestProviderTimeouts:
    """Test per-provider timeout configuration."""

    def test_default_timeouts(self):
        """Test default provider timeouts."""
        config = RouterConfig()
        assert config.ollama_timeout == 120
        assert config.openai_timeout == 60
        assert config.anthropic_timeout == 90
        assert config.openrouter_timeout == 60

    def test_custom_timeouts(self):
        """Test custom provider timeouts."""
        config = RouterConfig(ollama_timeout=30, anthropic_timeout=120)
        assert config.ollama_timeout == 30
        assert config.anthropic_timeout == 120
        # Others should use defaults
        assert config.openai_timeout == 60
        assert config.openrouter_timeout == 60

    def test_timeout_is_independent_fallback(self):
        """Test that timeout field works independently as fallback."""
        config = RouterConfig(timeout=45)
        assert config.timeout == 45
        # Provider-specific timeouts should still use their defaults
        assert config.ollama_timeout == 120
        assert config.openai_timeout == 60


class TestProviderHealth:
    """Test provider health check methods."""

    def test_check_all_providers_returns_dict(self):
        """Test check_all_providers_sync returns dict with all providers."""
        router = LLMRouter()
        result = router.check_all_providers_sync()

        assert isinstance(result, dict)
        assert "ollama" in result
        assert "openai" in result
        assert "anthropic" in result
        assert "openrouter" in result

    def test_check_all_providers_ollama_structure(self):
        """Test ollama provider response structure."""
        router = LLMRouter()
        result = router.check_all_providers_sync()

        ollama = result["ollama"]
        assert "available" in ollama
        assert "models" in ollama
        assert isinstance(ollama["available"], bool)

    def test_check_all_providers_openai_structure(self):
        """Test openai provider response structure."""
        router = LLMRouter()
        result = router.check_all_providers_sync()

        openai = result["openai"]
        assert "available" in openai
        assert "reason" in openai
        assert isinstance(openai["available"], bool)
        assert isinstance(openai["reason"], str)

    def test_check_all_providers_anthropic_structure(self):
        """Test anthropic provider response structure."""
        router = LLMRouter()
        result = router.check_all_providers_sync()

        anthropic = result["anthropic"]
        assert "available" in anthropic
        assert "reason" in anthropic
        assert isinstance(anthropic["available"], bool)
        assert isinstance(anthropic["reason"], str)

    def test_check_all_providers_openrouter_structure(self):
        """Test openrouter provider response structure."""
        router = LLMRouter()
        result = router.check_all_providers_sync()

        openrouter = result["openrouter"]
        assert "available" in openrouter
        assert "reason" in openrouter
        assert isinstance(openrouter["available"], bool)
        assert isinstance(openrouter["reason"], str)

    @pytest.mark.asyncio
    async def test_check_all_providers_async(self):
        """Test async check_all_providers method."""
        router = LLMRouter()
        result = await router.check_all_providers()

        assert isinstance(result, dict)
        assert "ollama" in result
        assert "openai" in result
        assert "anthropic" in result
        assert "openrouter" in result

    def test_check_all_providers_without_keys(self):
        """Test provider check without API keys."""
        router = LLMRouter(
            config=RouterConfig(
                openai_key=None,
                anthropic_key=None,
                openrouter_key=None,
            )
        )
        result = router.check_all_providers_sync()

        # Should indicate no API keys
        assert result["openai"]["available"] is False
        assert "No API key" in result["openai"]["reason"]
        assert result["anthropic"]["available"] is False
        assert "No API key" in result["anthropic"]["reason"]

    def test_check_all_providers_with_keys(self):
        """Test provider check with API keys configured."""
        router = LLMRouter(
            config=RouterConfig(
                openai_key="sk-test-key",
                anthropic_key="sk-test-key",
                openrouter_key="sk-test-key",
            )
        )
        result = router.check_all_providers_sync()

        # Should indicate keys are configured
        assert result["openai"]["available"] is True
        assert "API key" in result["openai"]["reason"]
        assert result["anthropic"]["available"] is True
        assert "API key" in result["anthropic"]["reason"]
        assert result["openrouter"]["available"] is True
