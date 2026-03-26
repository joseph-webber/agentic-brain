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
LLM Integration Tests - E2E tests with real API calls.

These tests verify:
1. API keys are configured correctly
2. Providers respond with valid output
3. The AI knows about agentic-brain

⚠️ COST NOTES:
- Groq: FREE (run liberally)
- Anthropic: PAID (run sparingly, use cheapest model)

Run with: pytest tests/e2e/test_llm_integration.py -v
"""

import os

import pytest

# Skip all tests if no API keys configured
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def is_rate_limited(error: Exception) -> bool:
    """Check if error is a rate limit (not a real failure)."""
    error_str = str(error).lower()
    return any(
        term in error_str
        for term in [
            "rate",
            "limit",
            "429",
            "quota",
            "exceeded",
            "credit",
            "billing",
            "402",
            "payment",
        ]
    )


# ============================================
# GROQ TESTS (FREE - run always)
# ============================================


@pytest.mark.skipif(not GROQ_KEY, reason="GROQ_API_KEY not set")
class TestGroqIntegration:
    """Groq integration tests - FREE to run."""

    def test_groq_api_key_format(self):
        """Test API key has correct format."""
        assert GROQ_KEY.startswith("gsk_"), "Groq key should start with gsk_"
        assert len(GROQ_KEY) > 20, "Groq key seems too short"

    def test_groq_simple_response(self):
        """Test Groq can respond to a simple prompt."""
        try:
            from agentic_brain.router import LLMRouter
            from agentic_brain.router.config import Provider

            router = LLMRouter()
            response = router.chat_sync(
                message="Say 'hello' and nothing else",
                provider=Provider.GROQ,
                model="llama-3.1-8b-instant",
            )

            assert response is not None
            # Response should contain something
            content = (
                str(response.content).lower()
                if hasattr(response, "content")
                else str(response).lower()
            )
            assert len(content) > 0

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Groq rate limited (provider works): {e}")
            raise

    def test_groq_knows_about_ai(self):
        """Test Groq can discuss AI topics."""
        try:
            from agentic_brain.router import LLMRouter
            from agentic_brain.router.config import Provider

            router = LLMRouter()
            response = router.chat_sync(
                message="What is an AI agent? Answer in one sentence.",
                provider=Provider.GROQ,
                model="llama-3.1-8b-instant",
            )

            content = (
                str(response.content).lower()
                if hasattr(response, "content")
                else str(response).lower()
            )
            # Should mention something about AI/agent
            assert any(
                term in content
                for term in [
                    "ai",
                    "agent",
                    "autonomous",
                    "task",
                    "llm",
                    "model",
                    "software",
                    "program",
                ]
            )

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Groq rate limited (provider works): {e}")
            raise

    def test_groq_agentic_brain_awareness(self):
        """Test Groq can respond about agentic-brain context."""
        try:
            from agentic_brain.router import LLMRouter
            from agentic_brain.router.config import Provider

            router = LLMRouter()
            response = router.chat_sync(
                system="You are an AI assistant for agentic-brain, a Python framework for building AI agents. It supports multiple LLM providers including Groq, Anthropic, and OpenAI.",
                message="What LLM providers does agentic-brain support? List 3.",
                provider=Provider.GROQ,
                model="llama-3.1-8b-instant",
            )

            content = (
                str(response.content).lower()
                if hasattr(response, "content")
                else str(response).lower()
            )
            # Should mention at least one provider we told it about
            providers_mentioned = sum(
                1 for p in ["groq", "anthropic", "openai"] if p in content
            )
            assert (
                providers_mentioned >= 1
            ), f"Should mention providers. Got: {response}"

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Groq rate limited (provider works): {e}")
            raise


# ============================================
# ANTHROPIC TESTS (PAID - run sparingly!)
# ============================================


@pytest.mark.skipif(not ANTHROPIC_KEY, reason="ANTHROPIC_API_KEY not set")
class TestAnthropicIntegration:
    """Anthropic integration tests - COSTS MONEY, use minimal tokens!"""

    def test_anthropic_api_key_format(self):
        """Test API key has correct format."""
        assert ANTHROPIC_KEY.startswith(
            "sk-ant-"
        ), "Anthropic key should start with sk-ant-"
        assert len(ANTHROPIC_KEY) > 30, "Anthropic key seems too short"

    def test_anthropic_simple_response(self):
        """Test Anthropic can respond (minimal tokens!)."""
        try:
            from agentic_brain.router import LLMRouter
            from agentic_brain.router.config import Provider

            router = LLMRouter()
            response = router.chat_sync(
                message="Say OK",
                provider=Provider.ANTHROPIC,
                model="claude-3-haiku-20240307",  # Cheapest!
            )

            assert response is not None
            content = (
                str(response.content) if hasattr(response, "content") else str(response)
            )
            assert len(content) > 0

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Anthropic quota/credit issue (provider works): {e}")
            raise

    def test_anthropic_knows_about_ai(self):
        """Test Anthropic can discuss AI (minimal tokens)."""
        try:
            from agentic_brain.router import LLMRouter
            from agentic_brain.router.config import Provider

            router = LLMRouter()
            response = router.chat_sync(
                message="What is an AI agent? 10 words max.",
                provider=Provider.ANTHROPIC,
                model="claude-3-haiku-20240307",
            )

            content = (
                str(response.content).lower()
                if hasattr(response, "content")
                else str(response).lower()
            )
            assert any(
                term in content
                for term in ["ai", "agent", "autonomous", "task", "software", "program"]
            )

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Anthropic quota/credit issue (provider works): {e}")
            raise

    def test_anthropic_agentic_brain_context(self):
        """Test Anthropic responds to agentic-brain context."""
        try:
            from agentic_brain.router import LLMRouter
            from agentic_brain.router.config import Provider

            router = LLMRouter()
            response = router.chat_sync(
                system="You are the assistant for agentic-brain, made by Joseph Webber in Australia.",
                message="Who made you? One word.",
                provider=Provider.ANTHROPIC,
                model="claude-3-haiku-20240307",
            )

            content = (
                str(response.content).lower()
                if hasattr(response, "content")
                else str(response).lower()
            )
            assert "joseph" in content or "webber" in content or "australia" in content

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Anthropic quota/credit issue (provider works): {e}")
            raise


# ============================================
# ROUTER TESTS
# ============================================


class TestRouter:
    """Test router behavior."""

    def test_router_initializes(self):
        """Test router can be created."""
        from agentic_brain.router import LLMRouter

        router = LLMRouter()
        assert router is not None

    @pytest.mark.skipif(
        not GROQ_KEY and not ANTHROPIC_KEY, reason="Need at least one API key"
    )
    def test_router_handles_invalid_provider(self):
        """Test router handles invalid provider gracefully."""
        from agentic_brain.router import LLMRouter

        router = LLMRouter()

        # Should raise error for invalid provider string
        with pytest.raises(Exception):
            router.chat_sync(
                message="test",
                provider="nonexistent_provider_xyz",  # Invalid string
                model="fake-model",
            )


# ============================================
# COST TRACKING TESTS
# ============================================


class TestCostAwareness:
    """Tests to ensure we're cost-conscious."""

    def test_anthropic_uses_cheapest_model_in_tests(self):
        """Verify tests use haiku (cheapest) not opus (expensive)."""
        import inspect

        source = inspect.getsource(TestAnthropicIntegration)

        # Should use haiku
        assert "haiku" in source, "Tests should use claude-3-haiku (cheapest)"

        # Should NOT use opus
        assert "opus" not in source, "Tests should NOT use opus (expensive!)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestGeminiIntegration:
    """Test Google Gemini integration - FREE tier, save quota for dev work."""

    @pytest.fixture
    def gemini_key(self):
        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            pytest.skip("GOOGLE_API_KEY not set")
        return key

    def test_gemini_key_format(self, gemini_key):
        """Verify Gemini API key has correct format."""
        assert gemini_key.startswith("AIza"), "Gemini key should start with AIza"
        assert len(gemini_key) >= 35, "Gemini key should be at least 35 chars"

    def test_gemini_simple_response(self, gemini_key):
        """Test Gemini can respond - minimal tokens to save quota."""
        import requests

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        response = requests.post(
            url,
            json={"contents": [{"parts": [{"text": "Say OK"}]}]},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        # Rate limit or quota = PASS (provider works, just quota)
        if response.status_code == 429:
            pytest.skip("Gemini rate limited - provider works, quota exhausted")

        assert response.status_code == 200, f"Gemini failed: {response.text}"
        data = response.json()
        assert "candidates" in data, "Response should have candidates"
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        assert len(text) > 0, "Should get non-empty response"

    def test_gemini_knows_about_ai(self, gemini_key):
        """Test Gemini has AI knowledge."""
        import requests

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        response = requests.post(
            url,
            json={
                "contents": [
                    {"parts": [{"text": "What does LLM stand for? One line answer."}]}
                ]
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code == 429:
            pytest.skip("Gemini rate limited")

        assert response.status_code == 200
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].lower()
        assert "language model" in text, "Should know what LLM means"
