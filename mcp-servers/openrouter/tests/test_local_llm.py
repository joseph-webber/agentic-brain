#!/usr/bin/env python3
"""
Local LLM Integration Tests for Brain
Run: pytest test_local_llm.py -v
"""
import json
import os
import subprocess
import time

import pytest

# Test configuration
OLLAMA_MODELS = ["llama3.2:3b", "llama3.1:8b"]
MAX_RESPONSE_TIME = 30  # seconds
WARMUP_MAX_TIME = 120  # seconds for cold start


def run_ollama(model: str, prompt: str, timeout: int = 30) -> tuple:
    """Run Ollama and return (response, elapsed_time)"""
    start = time.time()
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start
        return result.stdout.strip(), elapsed, result.returncode
    except subprocess.TimeoutExpired:
        return None, timeout, -1


class TestOllamaService:
    """Test Ollama service availability"""

    def test_ollama_installed(self):
        """Ollama CLI should be installed"""
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "ollama" in result.stdout.lower()

    def test_ollama_running(self):
        """Ollama service should be running"""
        result = subprocess.run(
            ["pgrep", "-x", "ollama"], capture_output=True, text=True
        )
        assert (
            result.returncode == 0
        ), "Ollama service not running! Start with: ollama serve"

    def test_ollama_api_responding(self):
        """Ollama API should respond on port 11434"""
        import urllib.request

        try:
            with urllib.request.urlopen(
                "http://localhost:11434/api/tags", timeout=5
            ) as response:
                assert response.status == 200
        except Exception as e:
            pytest.fail(f"Ollama API not responding: {e}")


class TestModels:
    """Test required models are available"""

    def test_models_installed(self):
        """All required models should be installed"""
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        assert result.returncode == 0

        for model in OLLAMA_MODELS:
            assert model in result.stdout, f"Model {model} not installed!"

    @pytest.mark.parametrize("model", OLLAMA_MODELS)
    def test_model_responds(self, model):
        """Each model should respond to a simple query"""
        response, elapsed, code = run_ollama(model, "Reply: OK", timeout=60)

        assert code == 0, f"Model {model} failed to respond"
        assert response is not None, f"Model {model} returned no response"
        assert len(response) > 0, f"Model {model} returned empty response"
        print(f"\n{model}: '{response[:50]}...' in {elapsed:.2f}s")


class TestPerformance:
    """Test model performance benchmarks"""

    def test_fast_model_speed(self):
        """llama3.2:3b should respond in under 15 seconds (warmed)"""
        # First query warms up
        run_ollama("llama3.2:3b", "warmup", timeout=60)

        # Second query should be fast
        response, elapsed, code = run_ollama("llama3.2:3b", "Say: FAST", timeout=15)

        assert code == 0
        assert elapsed < 15, f"llama3.2:3b too slow: {elapsed:.2f}s"
        print(f"\nllama3.2:3b response time: {elapsed:.2f}s")

    def test_concurrent_queries(self):
        """Should handle multiple rapid queries"""
        times = []
        for i in range(3):
            _, elapsed, code = run_ollama("llama3.2:3b", f"Count: {i}", timeout=20)
            assert code == 0
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        print(f"\nAverage response time: {avg_time:.2f}s")
        assert avg_time < 15, f"Average time too slow: {avg_time:.2f}s"


class TestIntegration:
    """Test brain integration features"""

    def test_brain_context_understanding(self):
        """Model should understand brain context"""
        prompt = "You are Iris Lumina, helping the user. Say hello."
        response, elapsed, code = run_ollama("llama3.2:3b", prompt, timeout=30)

        assert code == 0
        # Should mention Joseph or be a greeting
        assert any(
            word in response.lower() for word in ["joseph", "hello", "hi", "help"]
        )

    def test_code_understanding(self):
        """Model should understand basic code"""
        prompt = "What does this Python do: print('hello')"
        response, elapsed, code = run_ollama("llama3.2:3b", prompt, timeout=30)

        assert code == 0
        assert any(
            word in response.lower() for word in ["print", "hello", "output", "display"]
        )

    def test_json_output(self):
        """Model should be able to output JSON"""
        prompt = 'Output only this JSON: {"status": "ok"}'
        response, elapsed, code = run_ollama("llama3.2:3b", prompt, timeout=30)

        assert code == 0
        # Should contain JSON-like structure
        assert "{" in response and "}" in response


class TestFallback:
    """Test fallback behavior"""

    def test_fallback_context_file_exists(self):
        """Brain context file should exist for handoffs"""
        context_file = os.path.expanduser(
            "~/.brain-continuity/local-llm-brain-context.md"
        )
        assert os.path.exists(context_file), "Local LLM brain context file missing!"

    def test_model_switching(self):
        """Should be able to switch between models"""
        # Query fast model
        r1, t1, c1 = run_ollama("llama3.2:3b", "Model 1", timeout=30)
        assert c1 == 0

        # Query medium model
        r2, t2, c2 = run_ollama("llama3.1:8b", "Model 2", timeout=60)
        assert c2 == 0

        print(f"\nModel switch test: llama3.2:3b={t1:.1f}s, llama3.1:8b={t2:.1f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
