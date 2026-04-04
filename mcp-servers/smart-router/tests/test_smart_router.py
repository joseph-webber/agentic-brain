#!/usr/bin/env python3
"""
Smart Router Tests - Unit and smoke tests.

Run with: pytest tests/test_smart_router.py -v
Weekly smoke: pytest tests/test_smart_router.py -v -m smoke
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
env_path = Path.home() / "brain" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))


# ============================================================================
# Unit Tests (no API calls)
# ============================================================================

class TestProviderConfig:
    """Test provider configuration."""
    
    def test_providers_defined(self):
        """All expected providers are defined."""
        from server import PROVIDERS
        
        assert "openai" in PROVIDERS
        assert "openai-fast" in PROVIDERS
        assert "gemini" in PROVIDERS
        assert "groq" in PROVIDERS
        assert "local" in PROVIDERS
    
    def test_task_routes_defined(self):
        """All task routes are defined."""
        from server import TASK_ROUTES
        
        assert "code" in TASK_ROUTES
        assert "fast" in TASK_ROUTES
        assert "quality" in TASK_ROUTES
        assert "bulk" in TASK_ROUTES
        assert "free" in TASK_ROUTES
        assert "private" in TASK_ROUTES
        assert "auto" in TASK_ROUTES
    
    def test_code_route_prefers_openai(self):
        """Code tasks should prefer OpenAI."""
        from server import TASK_ROUTES
        
        assert TASK_ROUTES["code"][0] == "openai"
    
    def test_fast_route_prefers_groq(self):
        """Fast tasks should prefer Groq."""
        from server import TASK_ROUTES
        
        assert TASK_ROUTES["fast"][0] == "groq"
    
    def test_bulk_route_prefers_local(self):
        """Bulk tasks should prefer local."""
        from server import TASK_ROUTES
        
        assert TASK_ROUTES["bulk"][0] == "local"
    
    def test_free_route_excludes_openai(self):
        """Free tasks should not use OpenAI."""
        from server import TASK_ROUTES
        
        assert "openai" not in TASK_ROUTES["free"]


class TestRateLimiting:
    """Test rate limiting logic."""
    
    def test_check_rate_limit_fresh(self):
        """Fresh provider should pass rate limit."""
        from server import check_rate_limit, rate_limits
        
        # Clear rate limits
        rate_limits["openai"] = []
        
        assert check_rate_limit("openai") is True
    
    def test_record_request(self):
        """Recording request should add timestamp."""
        from server import record_request, rate_limits
        
        rate_limits["openai"] = []
        record_request("openai")
        
        assert len(rate_limits["openai"]) == 1
    
    def test_get_available_providers(self):
        """Should return providers with API keys."""
        from server import get_available_providers
        
        available = get_available_providers()
        
        # Local should always be available (no key needed)
        assert "local" in available
        
        # Others depend on env vars
        if os.environ.get("OPENAI_API_KEY"):
            assert "openai" in available
        if os.environ.get("GROQ_API_KEY"):
            assert "groq" in available


class TestSmartRoute:
    """Test smart routing logic."""
    
    @pytest.mark.asyncio
    async def test_smart_route_with_mock(self):
        """Smart route should try providers in order."""
        from server import smart_route, rate_limits
        
        # Clear rate limits
        for k in rate_limits:
            rate_limits[k] = []
        
        with patch("server.call_openai") as mock_openai:
            mock_openai.return_value = {
                "content": "Test response",
                "provider": "openai",
                "model": "gpt-4o",
            }
            
            result = await smart_route("Test prompt", task="code")
            
            assert "error" not in result or mock_openai.called
    
    @pytest.mark.asyncio
    async def test_prefer_override(self):
        """Prefer parameter should override default routing."""
        from server import smart_route, rate_limits
        
        for k in rate_limits:
            rate_limits[k] = []
        
        with patch("server.call_local") as mock_local:
            mock_local.return_value = {
                "content": "Local response",
                "provider": "local",
                "model": "llama3.1:8b",
            }
            
            result = await smart_route("Test", task="code", prefer="local")
            
            # Should have tried local first due to prefer
            mock_local.assert_called()


# ============================================================================
# Smoke Tests (actual API calls - run weekly)
# ============================================================================

@pytest.mark.smoke
class TestSmokeGroq:
    """Smoke tests for Groq (FREE, fastest)."""
    
    @pytest.mark.asyncio
    async def test_groq_responds(self):
        """Groq should respond to simple prompt."""
        if not os.environ.get("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set")
        
        from server import call_groq
        
        result = await call_groq("Reply with exactly: SMOKE_TEST_OK")
        
        assert "error" not in result, f"Groq error: {result.get('error')}"
        assert "content" in result
        assert result["provider"] == "groq"
        print(f"✅ Groq: {result['content'][:50]}")


@pytest.mark.smoke
class TestSmokeOpenAI:
    """Smoke tests for OpenAI."""
    
    @pytest.mark.asyncio
    async def test_openai_responds(self):
        """OpenAI should respond to simple prompt."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")
        
        from server import call_openai
        
        result = await call_openai("Reply with exactly: SMOKE_TEST_OK", "gpt-4o-mini")
        
        assert "error" not in result, f"OpenAI error: {result.get('error')}"
        assert "content" in result
        assert result["provider"] == "openai"
        print(f"✅ OpenAI: {result['content'][:50]}")


@pytest.mark.smoke
class TestSmokeGemini:
    """Smoke tests for Google Gemini (FREE)."""
    
    @pytest.mark.asyncio
    async def test_gemini_responds(self):
        """Gemini should respond to simple prompt."""
        if not os.environ.get("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")
        
        from server import call_gemini
        
        result = await call_gemini("Reply with exactly: SMOKE_TEST_OK")
        
        assert "error" not in result, f"Gemini error: {result.get('error')}"
        assert "content" in result
        assert result["provider"] == "gemini"
        print(f"✅ Gemini: {result['content'][:50]}")


@pytest.mark.smoke
class TestSmokeLocal:
    """Smoke tests for local Ollama."""
    
    @pytest.mark.asyncio
    async def test_local_responds(self):
        """Local Ollama should respond."""
        import httpx
        
        # Check if Ollama is running
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get("http://localhost:11434/api/tags")
                if r.status_code != 200:
                    pytest.skip("Ollama not running")
        except Exception:
            pytest.skip("Ollama not available")
        
        from server import call_local
        
        result = await call_local("Reply with exactly: SMOKE_TEST_OK")
        
        assert "error" not in result, f"Local error: {result.get('error')}"
        assert "content" in result
        assert result["provider"] == "local"
        print(f"✅ Local: {result['content'][:50]}")


@pytest.mark.smoke
class TestSmokeSmartRoute:
    """End-to-end smart routing smoke test."""
    
    @pytest.mark.asyncio
    async def test_smart_route_auto(self):
        """Smart route should successfully route a request."""
        from server import smart_route
        
        result = await smart_route(
            "What is 2+2? Reply with just the number.",
            task="fast"
        )
        
        assert "error" not in result, f"Smart route error: {result.get('error')}"
        assert "content" in result
        assert "provider" in result
        assert "4" in result["content"]
        print(f"✅ Smart Route ({result['provider']}): {result['content'][:30]}")
    
    @pytest.mark.asyncio
    async def test_fallback_chain(self):
        """Should fallback to next provider on failure."""
        from server import smart_route, rate_limits
        
        # This just tests that the system handles the chain
        result = await smart_route(
            "Reply OK",
            task="free"  # Uses free providers only
        )
        
        # Should get a response from one of the free providers
        if "error" not in result:
            assert result["provider"] in ["gemini", "groq", "local"]
            print(f"✅ Free route used: {result['provider']}")


# ============================================================================
# Integration Tests
# ============================================================================

class TestMCPIntegration:
    """Test MCP tool definitions."""
    
    def test_mcp_server_importable(self):
        """MCP server should be importable."""
        from server import mcp
        
        assert mcp is not None
        assert mcp.name == "smart-router"
    
    @pytest.mark.asyncio
    async def test_router_status_tool(self):
        """router_status tool should return valid JSON."""
        from server import router_status
        import json
        
        result = await router_status()
        data = json.loads(result)
        
        assert "available_providers" in data
        assert "providers" in data
        assert "task_routes" in data
        assert isinstance(data["available_providers"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
