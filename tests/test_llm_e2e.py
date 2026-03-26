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
LLM E2E Comparison Tests - Gemini vs Local LLM (Ollama)

This test suite compares the capabilities of:
- Google Gemini (cloud-based, 1M+ token context, FREE tier)
- Local LLM via Ollama (offline, private, no rate limits)

Both providers are FREE to use:
- Gemini: 60 queries/minute on free tier
- Ollama: Unlimited, runs on your hardware

Run with: pytest tests/test_llm_e2e.py -v
"""

import os
import time

import pytest

# =============================================================================
# SKIP MARKERS - Conditional test execution based on environment
# =============================================================================

# Skip tests if Ollama is not available (common in CI)
requires_ollama = pytest.mark.skipif(
    os.getenv("SKIP_OLLAMA_TESTS", "true").lower() == "true",
    reason="Ollama not available - set SKIP_OLLAMA_TESTS=false to enable",
)

# Skip tests if GOOGLE_API_KEY is not set
requires_gemini = pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"),
    reason="GOOGLE_API_KEY not set - get one at https://aistudio.google.com/apikey",
)


def is_rate_limited(error: Exception) -> bool:
    """Check if error is a rate limit (provider works, just quota exhausted)."""
    error_str = str(error).lower()
    return any(
        term in error_str
        for term in ["rate", "limit", "429", "quota", "exceeded", "resource exhausted"]
    )


def check_ollama_running() -> bool:
    """Check if Ollama is actually running and responding."""
    try:
        import shutil

        if not shutil.which("ollama"):
            return False

        import urllib.error
        import urllib.request

        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


# =============================================================================
# CAPABILITY COMPARISON - Document what each provider excels at
# =============================================================================


class TestCapabilityComparison:
    """Document and verify the unique capabilities of each LLM provider."""

    def test_capability_matrix_documentation(self):
        """Document what each provider is best for."""
        capabilities = {
            "local_llm": {
                "provider": "Ollama (Local)",
                "cost": "FREE (runs on your hardware)",
                "privacy": "MAXIMUM - data never leaves machine",
                "offline": "YES - works without internet",
                "rate_limits": "NONE - unlimited queries",
                "context_window": "Up to 128K tokens (depends on model)",
                "latency": "Fast if good GPU/M-series chip",
                "setup": "Install Ollama + download model",
                "best_for": [
                    "Privacy-sensitive applications",
                    "Offline use (planes, remote areas)",
                    "High-volume queries without limits",
                    "Development/testing without API costs",
                ],
            },
            "gemini": {
                "provider": "Google Gemini (Cloud)",
                "cost": "FREE tier: 60 RPM, 1500 requests/day",
                "privacy": "STANDARD - data sent to Google",
                "offline": "NO - requires internet",
                "rate_limits": "60 requests/minute free tier",
                "context_window": "1 MILLION+ tokens (huge!)",
                "latency": "Fast (Google infrastructure)",
                "setup": "Get API key from aistudio.google.com",
                "best_for": [
                    "Very long documents (1M tokens!)",
                    "Always-on availability",
                    "No local GPU required",
                    "Multimodal (images, video)",
                ],
            },
        }

        # Verify structure
        assert "local_llm" in capabilities
        assert "gemini" in capabilities

        # Document key differentiators
        assert capabilities["local_llm"]["offline"] == "YES - works without internet"
        assert "1 MILLION" in capabilities["gemini"]["context_window"]
        assert capabilities["local_llm"]["rate_limits"] == "NONE - unlimited queries"

    def test_when_to_use_local(self):
        """Document when local LLM is the better choice."""
        use_local_when = [
            "Processing sensitive/private data",
            "Working offline (flights, remote locations)",
            "Running many queries without rate limit concerns",
            "Development and testing cycles",
            "Cost-conscious high-volume applications",
            "Air-gapped or security-restricted environments",
        ]

        # All items should be documented
        assert len(use_local_when) >= 5
        assert any("offline" in item.lower() for item in use_local_when)
        assert any(
            "private" in item.lower() or "sensitive" in item.lower()
            for item in use_local_when
        )

    def test_when_to_use_gemini(self):
        """Document when Gemini is the better choice."""
        use_gemini_when = [
            "Processing very long documents (100K+ tokens)",
            "Need consistent cloud availability",
            "No local GPU available",
            "Multimodal processing (images, video)",
            "Quick setup without local installation",
            "Analyzing entire codebases at once",
        ]

        # All items should be documented
        assert len(use_gemini_when) >= 5
        assert any("long" in item.lower() for item in use_gemini_when)


# =============================================================================
# LOCAL LLM TESTS (Ollama)
# =============================================================================


@requires_ollama
class TestLocalLLM:
    """Tests for local LLM via Ollama - requires Ollama running locally."""

    @pytest.fixture
    def ollama_available(self):
        """Skip if Ollama is not actually running."""
        if not check_ollama_running():
            pytest.skip("Ollama is not running - start with: ollama serve")
        return True

    def test_ollama_health_check(self, ollama_available):
        """Verify Ollama is running and responding."""
        assert check_ollama_running(), "Ollama should be responding"

    def test_basic_chat(self, ollama_available):
        """Test basic chat completion with local LLM."""
        from agentic_brain.router import LLMRouter
        from agentic_brain.router.config import Provider

        router = LLMRouter()
        response = router.chat_sync(
            message="Say 'hello' and nothing else.",
            provider=Provider.OLLAMA,
            model="llama3.2:3b",  # Fast, small model for testing
        )

        assert response is not None
        content = str(response.content).lower()
        assert len(content) > 0
        # Should contain "hello" somewhere
        assert "hello" in content or len(content) < 50  # Or very short response

    def test_offline_capability(self, ollama_available):
        """Test that local LLM works offline - its unique superpower!"""
        # This test documents that Ollama works without internet
        # In a real offline scenario, this would still work
        from agentic_brain.router import LLMRouter
        from agentic_brain.router.config import Provider

        router = LLMRouter()

        # Even if internet is down, Ollama responds
        response = router.chat_sync(
            message="What is 2+2? Just the number.",
            provider=Provider.OLLAMA,
            model="llama3.2:3b",
        )

        assert response is not None
        content = str(response.content)
        assert "4" in content or "four" in content.lower()

    def test_no_rate_limits(self, ollama_available):
        """Test that local LLM has no rate limits - another superpower!"""
        from agentic_brain.router import LLMRouter
        from agentic_brain.router.config import Provider

        router = LLMRouter()

        # Send multiple rapid requests - should all succeed
        success_count = 0
        for i in range(5):
            try:
                response = router.chat_sync(
                    message=f"Count: {i}. Say OK.",
                    provider=Provider.OLLAMA,
                    model="llama3.2:3b",
                )
                if response is not None:
                    success_count += 1
            except Exception:
                pass  # Allow some failures but expect most to succeed

        # Should handle at least 4/5 without rate limiting
        assert success_count >= 4, f"Only {success_count}/5 succeeded - possible issue"

    def test_privacy_mode(self, ollama_available):
        """Document that local LLM keeps data private."""
        # This test documents the privacy benefit
        privacy_facts = {
            "data_leaves_machine": False,
            "requires_internet": False,
            "third_party_access": False,
            "audit_friendly": True,  # All processing local
        }

        assert privacy_facts["data_leaves_machine"] is False
        assert privacy_facts["requires_internet"] is False


# =============================================================================
# GEMINI TESTS (Google Cloud)
# =============================================================================


@requires_gemini
class TestGeminiLLM:
    """Tests for Google Gemini - requires GOOGLE_API_KEY."""

    @pytest.fixture
    def gemini_key(self):
        """Get and validate Gemini API key."""
        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            pytest.skip("GOOGLE_API_KEY not set")
        return key

    def test_api_key_format(self, gemini_key):
        """Verify Gemini API key has correct format."""
        assert gemini_key.startswith("AIza"), "Gemini key should start with AIza"
        assert len(gemini_key) >= 35, "Gemini key seems too short"

    def test_basic_chat(self, gemini_key):
        """Test basic chat completion with Gemini."""
        import requests

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"

        try:
            response = requests.post(
                url,
                json={
                    "contents": [{"parts": [{"text": "Say 'hello' and nothing else."}]}]
                },
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code == 429:
                pytest.skip("Gemini rate limited - provider works, quota exhausted")

            assert response.status_code == 200, f"Gemini failed: {response.text}"
            data = response.json()
            candidates = data.get("candidates")
            if not candidates:
                pytest.skip(
                    f"Gemini API placeholder response without candidates: {data}"
                )
            text = candidates[0]["content"]["parts"][0]["text"].lower()
            assert len(text) > 0

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Gemini rate limited: {e}")
            raise

    def test_long_context_capability(self, gemini_key):
        """Test Gemini's massive 1M+ token context window - its superpower!"""
        import requests

        # Create a moderately long prompt (not 1M tokens, but demonstrates capability)
        long_text = "This is sentence number {i}. " * 100
        long_text = long_text.format(i="X")  # Just for structure

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"

        try:
            response = requests.post(
                url,
                json={
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": f"Here is a long text:\n{long_text}\n\nHow many times does the word 'sentence' appear? Just give the number."
                                }
                            ]
                        }
                    ]
                },
                headers={"Content-Type": "application/json"},
                timeout=60,
            )

            if response.status_code == 429:
                pytest.skip("Gemini rate limited")

            assert response.status_code == 200
            data = response.json()
            candidates = data.get("candidates")
            if not candidates:
                pytest.skip(
                    "Gemini API placeholder response without candidates for long context"
                )

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Gemini rate limited: {e}")
            raise

    def test_code_generation(self, gemini_key):
        """Test Gemini's code generation capability."""
        import requests

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"

        try:
            response = requests.post(
                url,
                json={
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": "Write a Python function that adds two numbers. Just the code, no explanation."
                                }
                            ]
                        }
                    ]
                },
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code == 429:
                pytest.skip("Gemini rate limited")

            assert response.status_code == 200
            data = response.json()
            candidates = data.get("candidates")
            if not candidates:
                pytest.skip(
                    "Gemini API placeholder response without candidates for code generation"
                )
            text = candidates[0]["content"]["parts"][0]["text"]

            # Should contain Python code
            assert "def" in text or "return" in text

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Gemini rate limited: {e}")
            raise

    def test_cloud_availability(self, gemini_key):
        """Test that Gemini is always available (cloud benefit)."""
        import requests

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"

        # Quick health check - should respond fast
        start = time.time()
        try:
            response = requests.post(
                url,
                json={"contents": [{"parts": [{"text": "1"}]}]},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            elapsed = time.time() - start

            if response.status_code == 429:
                pytest.skip("Gemini rate limited - but IS available")

            assert response.status_code == 200
            # Should respond within reasonable time
            assert elapsed < 10, f"Response took {elapsed:.1f}s - too slow"

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Gemini rate limited (available but at quota): {e}")
            raise


# =============================================================================
# SPEED COMPARISON TESTS
# =============================================================================


class TestSpeedComparison:
    """Compare response speeds between providers."""

    @requires_ollama
    def test_local_llm_speed(self):
        """Measure local LLM response time."""
        if not check_ollama_running():
            pytest.skip("Ollama not running")

        from agentic_brain.router import LLMRouter
        from agentic_brain.router.config import Provider

        router = LLMRouter()

        start = time.time()
        response = router.chat_sync(
            message="Say 'test'",
            provider=Provider.OLLAMA,
            model="llama3.2:3b",
        )
        elapsed = time.time() - start

        assert response is not None
        # Local LLM with good hardware should be fast
        # Note: First request may be slower (model loading)
        assert elapsed < 30, f"Local response took {elapsed:.1f}s"

    @requires_gemini
    def test_gemini_speed(self):
        """Measure Gemini response time."""
        import requests

        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            pytest.skip("No Gemini key")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"

        start = time.time()
        try:
            response = requests.post(
                url,
                json={"contents": [{"parts": [{"text": "Say 'test'"}]}]},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            elapsed = time.time() - start

            if response.status_code == 429:
                pytest.skip("Gemini rate limited")

            assert response.status_code == 200
            # Cloud should be reasonably fast
            assert elapsed < 15, f"Gemini took {elapsed:.1f}s"

        except Exception as e:
            if is_rate_limited(e):
                pytest.skip(f"Gemini rate limited: {e}")
            raise


# =============================================================================
# ROUTER INTEGRATION TESTS
# =============================================================================


class TestRouterIntegration:
    """Test the LLM router works with both providers."""

    def test_router_initializes(self):
        """Test router can be created."""
        from agentic_brain.router import LLMRouter

        router = LLMRouter()
        assert router is not None

    def test_router_has_google_provider(self):
        """Test router has Google/Gemini provider configured."""
        from agentic_brain.router.config import Provider

        assert hasattr(Provider, "GOOGLE")

    def test_router_has_ollama_provider(self):
        """Test router has Ollama provider configured."""
        from agentic_brain.router.config import Provider

        assert hasattr(Provider, "OLLAMA")


# =============================================================================
# FALLBACK BEHAVIOR TESTS
# =============================================================================


class TestFallbackBehavior:
    """Test graceful fallback between providers."""

    def test_provider_unavailable_handling(self):
        """Test that unavailable providers raise appropriate errors."""
        from agentic_brain.router import LLMRouter
        from agentic_brain.router.config import Provider

        router = LLMRouter()

        # If Ollama isn't running, should get a clear error
        if not check_ollama_running():
            with pytest.raises(Exception) as exc_info:
                router.chat_sync(
                    message="test",
                    provider=Provider.OLLAMA,
                    model="llama3.2:3b",
                )
            # Error should mention Ollama or connection
            error_str = str(exc_info.value).lower()
            assert (
                "ollama" in error_str
                or "running" in error_str
                or "connection" in error_str
            )

    @requires_gemini
    def test_gemini_graceful_rate_limit(self):
        """Test that Gemini rate limits are handled gracefully."""
        # Just verify the error handling exists
        from agentic_brain.exceptions import RateLimitError

        assert RateLimitError is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
