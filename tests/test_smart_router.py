# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
🔥 SMART ROUTER CI TESTS 🔥

Tests for the master/worker LLM architecture.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.personas import get_persona
from agentic_brain.router import LLMRouter, Provider, Response, RouterConfig
from agentic_brain.smart_router.core import (
    SmartRouter,
    SmashMode,
    SmashResult,
    WorkerConfig,
    get_router,
)
from agentic_brain.smart_router.posture import PostureMode, SecurityPosture, get_posture


class TestSmartRouter:
    """Test the SmartRouter core"""

    def test_router_initialization(self):
        """Router initializes with default workers"""
        router = SmartRouter()
        assert "openai" in router.workers
        assert "groq" in router.workers
        assert "gemini" in router.workers
        assert "local" in router.workers

    def test_get_route_for_task(self):
        """Router returns correct workers for task types"""
        router = SmartRouter()

        code_route = router.get_route("code")
        assert "openai" in code_route

        fast_route = router.get_route("fast")
        assert "groq" in fast_route

        free_route = router.get_route("free")
        assert "local" in free_route

    def test_heat_tracking(self):
        """Router tracks worker usage (heat)"""
        router = SmartRouter()

        initial_heat = router.heat_map.get("openai", 0)
        router.add_heat("openai", 2.0)
        assert router.heat_map["openai"] == initial_heat + 2.0

        router.cool_down(1.0)
        assert router.heat_map["openai"] == initial_heat + 1.0

    def test_coolest_workers(self):
        """Router returns least used workers"""
        router = SmartRouter()

        # Heat up some workers
        router.add_heat("openai", 10.0)
        router.add_heat("groq", 5.0)

        coolest = router.get_coolest_workers(2)
        assert "openai" not in coolest[:2] or "groq" not in coolest[:2]

    def test_record_result(self):
        """Router records worker results"""
        router = SmartRouter()

        result = SmashResult(
            task_id="test-1",
            provider="groq",
            response="Hello!",
            elapsed=1.5,
            success=True,
        )

        router.record_result(result)
        stats = router.stats.get("groq", {})
        assert stats.get("requests", 0) >= 1
        assert stats.get("successes", 0) >= 1

    def test_get_status(self):
        """Router returns status dict"""
        router = SmartRouter()
        status = router.get_status()

        assert "workers" in status
        assert "coolest" in status
        assert "free_workers" in status
        assert len(status["free_workers"]) > 0


class TestSecurityPosture:
    """Test security posture modes"""

    def test_open_posture(self):
        """Open posture allows all workers"""
        posture = get_posture("open")
        assert posture.is_worker_allowed("openai")
        assert posture.is_worker_allowed("groq")
        assert posture.is_worker_allowed("local")

    def test_airgapped_posture(self):
        """Airgapped only allows local"""
        posture = get_posture("airgapped")
        assert posture.is_worker_allowed("local")
        assert not posture.is_worker_allowed("openai")
        assert not posture.is_worker_allowed("groq")

    def test_restricted_posture(self):
        """Restricted limits to approved workers"""
        posture = get_posture("restricted")
        assert posture.is_worker_allowed("openai")
        assert posture.is_worker_allowed("local")
        # Others should be blocked
        assert not posture.is_worker_allowed("groq")

    def test_compliance_posture(self):
        """Compliance enables logging"""
        posture = get_posture("compliance")
        assert posture.log_prompts is True
        assert posture.log_responses is True
        assert posture.redact_pii is True

    def test_cost_saver_posture(self):
        """Cost saver prefers free workers"""
        posture = get_posture("cost_saver")
        assert posture.prefer_free_workers is True
        assert posture.is_worker_allowed("groq")
        assert posture.is_worker_allowed("gemini")
        assert posture.is_worker_allowed("local")

    def test_filter_workers(self):
        """Posture filters worker lists"""
        posture = SecurityPosture(
            mode=PostureMode.RESTRICTED, allowed_workers=["openai", "local"]
        )

        workers = ["openai", "groq", "gemini", "local"]
        filtered = posture.filter_workers(workers)

        assert "openai" in filtered
        assert "local" in filtered
        assert "groq" not in filtered
        assert "gemini" not in filtered

    def test_blocked_workers(self):
        """Blocked workers are excluded"""
        posture = SecurityPosture(
            mode=PostureMode.STANDARD, blocked_workers=["openrouter"]
        )

        assert posture.is_worker_allowed("openai")
        assert not posture.is_worker_allowed("openrouter")


class TestSmashResult:
    """Test SmashResult dataclass"""

    def test_result_creation(self):
        """SmashResult creates correctly"""
        result = SmashResult(
            task_id="test-123",
            provider="groq",
            response="Hello world!",
            elapsed=1.2,
            success=True,
            tokens=50,
        )

        assert result.task_id == "test-123"
        assert result.provider == "groq"
        assert result.success is True
        assert result.elapsed == 1.2
        assert result.mode == SmashMode.TURBO  # default


class TestSingletonRouter:
    """Test singleton router pattern"""

    def test_get_router_singleton(self):
        """get_router returns same instance"""
        router1 = get_router()
        router2 = get_router()
        assert router1 is router2


class TestLLMRouterSmartRouting:
    """Test LLMRouter smart routing behaviors."""

    def test_short_message_routes_to_fast(self):
        """Short messages should route to fast local model."""
        router = LLMRouter()
        provider, model = router.smart_route("Hi")
        assert provider == Provider.OLLAMA
        assert model == "llama3.2:3b"

    def test_code_message_routes_to_code_capable_model(self):
        """Messages mentioning code should use the workhorse model."""
        config = RouterConfig(anthropic_key="test-key")
        router = LLMRouter(config)
        provider, model = router.smart_route("Write code to sort a list")
        assert provider == Provider.ANTHROPIC
        assert model == "claude-3-5-sonnet-20241022"

    def test_complex_routes_to_powerful_model(self):
        """Complex reasoning should prefer cloud models when keys are set."""
        config = RouterConfig(anthropic_key="test-key")
        router = LLMRouter(config)
        provider, model = router.smart_route(
            "Provide complex reasoning and analysis of quantum entanglement."
        )
        assert provider == Provider.ANTHROPIC
        assert model == "claude-3-sonnet-20240229"

    @pytest.mark.asyncio
    async def test_fallback_when_cloud_unavailable(self):
        """Fallback to local when cloud provider fails."""
        router = LLMRouter()
        router._chat_openai = AsyncMock(side_effect=RuntimeError("boom"))
        router._chat_ollama = AsyncMock(
            return_value=Response(
                content="ok",
                model="llama3.1:8b",
                provider=Provider.OLLAMA,
            )
        )

        response = await router.chat(
            "Hello",
            provider=Provider.OPENAI,
            model="gpt-4o",
            use_cache=False,
        )

        assert response.provider == Provider.OLLAMA
        assert response.model == "llama3.1:8b"
        router._chat_openai.assert_awaited_once()
        router._chat_ollama.assert_awaited_once()
        _, _, model_arg, _ = router._chat_ollama.call_args.args
        assert model_arg == "llama3.1:8b"

    @pytest.mark.asyncio
    async def test_provider_switching(self):
        """Explicit provider selection should bypass smart routing."""
        router = LLMRouter()
        router._chat_openai = AsyncMock(
            return_value=Response(
                content="ok",
                model="gpt-4o",
                provider=Provider.OPENAI,
            )
        )
        router._chat_ollama = AsyncMock()

        response = await router.chat(
            "Hello",
            provider=Provider.OPENAI,
            model="gpt-4o",
            use_cache=False,
        )

        assert response.provider == Provider.OPENAI
        assert response.model == "gpt-4o"
        router._chat_openai.assert_awaited_once()
        router._chat_ollama.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_persona_integration(self):
        """Persona system should set system prompt for routing."""
        router = LLMRouter()
        router._chat_ollama = AsyncMock(
            return_value=Response(
                content="ok",
                model="llama3.2:3b",
                provider=Provider.OLLAMA,
            )
        )

        persona = get_persona("coder")
        assert persona is not None
        expected_system = persona.format_system_prompt()

        await router.chat(
            "Hello",
            persona="coder",
            use_cache=False,
        )

        router._chat_ollama.assert_awaited_once()
        _, system_arg, _, _ = router._chat_ollama.call_args.args
        assert system_arg == expected_system


# Integration tests (require API keys)
@pytest.mark.integration
@pytest.mark.skipif(True, reason="Requires API keys")
class TestTurboSmash:
    """Integration tests for Turbo smash mode"""

    @pytest.mark.asyncio
    async def test_turbo_smash_parallel(self):
        """Fire all workers in parallel"""
        from agentic_brain.smart_router.coordinator import turbo_smash

        result = await turbo_smash("Say hello in one word")
        assert result.success
        assert result.elapsed < 30

    @pytest.mark.asyncio
    async def test_warmup_ping(self):
        """Warmup measures response times"""
        from agentic_brain.smart_router.coordinator import warmup_ping

        times = await warmup_ping()
        assert isinstance(times, dict)
        # At least local should respond
        assert "local" in times or len(times) > 0
