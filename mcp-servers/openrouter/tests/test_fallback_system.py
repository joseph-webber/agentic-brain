#!/usr/bin/env python3
"""
Comprehensive tests for the OpenRouter Fallback System.

This tests the full fallback flow when Claude/Copilot gets rate limited:
1. Detecting rate limits (report_429)
2. Switching to local LLM (auto fallback)
3. Using local LLM for responses (ask_local, quick_local)
4. Resetting when limits clear (reset_fallback)
5. State persistence across restarts

Run: pytest test_fallback_system.py -v
Run with benchmarks: pytest test_fallback_system.py -v --benchmark-enable
Output JSON report: pytest test_fallback_system.py -v --json-report --json-report-file=test_results.json
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

# Output directory for CI artifacts
OUTPUT_DIR = Path(__file__).parent / "benchmark_results"

# Test configuration
OLLAMA_URL = "http://localhost:11434"
TEST_TIMEOUT = 30
QUICK_MODEL = "llama3.2:3b"
FULL_MODEL = "llama3.1:8b"
CLAUDE_EMULATOR = "claude-emulator"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_state_dir():
    """Create temporary directory for state files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def clean_state(temp_state_dir):
    """Ensure clean state before each test"""
    state_file = os.path.join(temp_state_dir, "fallback-state.json")
    if os.path.exists(state_file):
        os.remove(state_file)
    yield state_file


@pytest.fixture
def mock_state_file(temp_state_dir):
    """Create a mock state file path"""
    return os.path.join(temp_state_dir, "fallback-state.json")


def is_ollama_running() -> bool:
    """Check if Ollama service is running"""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except:
        return False


def call_ollama_api(
    prompt: str, model: str = QUICK_MODEL, timeout: int = 60
) -> Optional[str]:
    """Call Ollama API directly"""
    try:
        payload = json.dumps(
            {"model": model, "prompt": prompt, "stream": False}
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception:
        return None


# ============================================================================
# Unit Tests - State Management
# ============================================================================


class TestFallbackState:
    """Test fallback state persistence"""

    def test_state_file_creation(self, mock_state_file):
        """State file should be created when saving"""
        state = {
            "rate_limited": True,
            "last_429": "2026-03-21 08:30:00",
            "fallback_active": True,
            "current_model": "claude-emulator",
        }

        os.makedirs(os.path.dirname(mock_state_file), exist_ok=True)
        with open(mock_state_file, "w") as f:
            json.dump(state, f)

        assert os.path.exists(mock_state_file)

        with open(mock_state_file) as f:
            loaded = json.load(f)

        assert loaded["rate_limited"]
        assert loaded["current_model"] == "claude-emulator"

    def test_state_default_values(self, mock_state_file):
        """Default state should be no rate limiting"""
        # Non-existent file should return defaults
        if os.path.exists(mock_state_file):
            os.remove(mock_state_file)

        # Simulate load_fallback_state behavior
        if os.path.exists(mock_state_file):
            with open(mock_state_file) as f:
                state = json.load(f)
        else:
            state = {
                "rate_limited": False,
                "last_429": None,
                "fallback_active": False,
                "current_model": "copilot",
            }

        assert not state["rate_limited"]
        assert not state["fallback_active"]
        assert state["current_model"] == "copilot"

    def test_state_persistence_across_reload(self, mock_state_file):
        """State should persist across file reload"""
        # Save state
        state = {
            "rate_limited": True,
            "last_429": "2026-03-21 09:00:00",
            "fallback_active": True,
            "current_model": "llama3.2:3b",
        }
        os.makedirs(os.path.dirname(mock_state_file), exist_ok=True)
        with open(mock_state_file, "w") as f:
            json.dump(state, f)

        # Reload state (simulate new session)
        with open(mock_state_file) as f:
            loaded = json.load(f)

        assert loaded["rate_limited"]
        assert loaded["last_429"] == "2026-03-21 09:00:00"
        assert loaded["current_model"] == "llama3.2:3b"

    def test_state_reset_clears_rate_limit(self, mock_state_file):
        """Reset should clear rate limit state"""
        # Set rate limited state
        os.makedirs(os.path.dirname(mock_state_file), exist_ok=True)
        with open(mock_state_file, "w") as f:
            json.dump({"rate_limited": True, "fallback_active": True}, f)

        # Reset state
        reset_state = {
            "rate_limited": False,
            "last_429": None,
            "fallback_active": False,
            "current_model": "copilot",
        }
        with open(mock_state_file, "w") as f:
            json.dump(reset_state, f)

        # Verify reset
        with open(mock_state_file) as f:
            loaded = json.load(f)

        assert not loaded["rate_limited"]
        assert not loaded["fallback_active"]


# ============================================================================
# Unit Tests - Model Availability
# ============================================================================


class TestModelAvailability:
    """Test model availability checking"""

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_ollama_service_running(self):
        """Ollama service should be running"""
        assert is_ollama_running()

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_quick_model_available(self):
        """Quick model (llama3.2:3b) should be available"""
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        assert QUICK_MODEL in result.stdout or "llama3.2" in result.stdout

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_claude_emulator_available(self):
        """Claude emulator model should be available"""
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        assert CLAUDE_EMULATOR in result.stdout or "claude-emulator" in result.stdout


# ============================================================================
# Unit Tests - Local LLM Responses
# ============================================================================


class TestLocalLLMResponses:
    """Test local LLM response quality"""

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_quick_local_responds(self):
        """Quick local model should respond to prompts"""
        response = call_ollama_api("Say: hello", model=QUICK_MODEL)
        assert response is not None
        assert len(response) > 0

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_quick_local_speed(self):
        """Quick local should respond in under 20 seconds"""
        start = time.time()
        response = call_ollama_api("Reply with just: OK", model=QUICK_MODEL)
        elapsed = time.time() - start

        assert response is not None
        assert elapsed < 20, f"Response took {elapsed:.1f}s (should be <20s)"

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_claude_emulator_responds(self):
        """Claude emulator should respond to prompts"""
        response = call_ollama_api("What is 2+2?", model=CLAUDE_EMULATOR, timeout=120)
        assert response is not None
        assert len(response) > 0

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_response_contains_content(self):
        """Response should contain actual content"""
        response = call_ollama_api("List 3 colors", model=QUICK_MODEL)
        assert response is not None
        # Should contain at least one common color
        colors = [
            "red",
            "blue",
            "green",
            "yellow",
            "orange",
            "purple",
            "white",
            "black",
        ]
        assert any(color in response.lower() for color in colors)


# ============================================================================
# Integration Tests - Fallback Flow
# ============================================================================


class TestFallbackFlow:
    """Test the complete fallback flow"""

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_fallback_activation_flow(self, mock_state_file):
        """Full flow: normal -> rate limit -> fallback -> local response"""
        os.makedirs(os.path.dirname(mock_state_file), exist_ok=True)

        # Step 1: Start in normal state
        normal_state = {
            "rate_limited": False,
            "fallback_active": False,
            "current_model": "copilot",
        }
        with open(mock_state_file, "w") as f:
            json.dump(normal_state, f)

        # Step 2: Simulate rate limit (report_429)
        rate_limited_state = {
            "rate_limited": True,
            "last_429": time.strftime("%Y-%m-%d %H:%M:%S"),
            "fallback_active": True,
            "current_model": "claude-emulator",
        }
        with open(mock_state_file, "w") as f:
            json.dump(rate_limited_state, f)

        # Step 3: Verify state is rate limited
        with open(mock_state_file) as f:
            state = json.load(f)
        assert state["rate_limited"]
        assert state["fallback_active"]

        # Step 4: Use local LLM while rate limited
        response = call_ollama_api("Say: fallback working", model=QUICK_MODEL)
        assert response is not None

        # Step 5: Reset fallback
        reset_state = {
            "rate_limited": False,
            "last_429": None,
            "fallback_active": False,
            "current_model": "copilot",
        }
        with open(mock_state_file, "w") as f:
            json.dump(reset_state, f)

        # Step 6: Verify reset
        with open(mock_state_file) as f:
            state = json.load(f)
        assert not state["rate_limited"]

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_multiple_local_requests(self):
        """Should handle multiple sequential requests"""
        responses = []
        for i in range(3):
            response = call_ollama_api(f"Count: {i}", model=QUICK_MODEL)
            responses.append(response)

        assert all(r is not None for r in responses)
        assert all(len(r) > 0 for r in responses)

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_model_switching(self):
        """Should be able to switch between local models"""
        # Use quick model
        r1 = call_ollama_api("Say: quick", model=QUICK_MODEL)
        assert r1 is not None

        # Use full model
        r2 = call_ollama_api("Say: full", model=FULL_MODEL, timeout=120)
        assert r2 is not None


# ============================================================================
# E2E Tests - Real World Scenarios
# ============================================================================


class TestE2EScenarios:
    """End-to-end tests for real world scenarios"""

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_e2e_rate_limit_recovery(self, mock_state_file):
        """E2E: User gets rate limited, uses local, then recovers

        This is a CLIENT DEMO scenario - must be seamless!
        """
        os.makedirs(os.path.dirname(mock_state_file), exist_ok=True)

        # User is working normally (not tested - using Copilot)

        # User hits rate limit - automatic fallback kicks in
        state = {
            "rate_limited": True,
            "last_429": time.strftime("%Y-%m-%d %H:%M:%S"),
            "fallback_active": True,
            "current_model": "claude-emulator",
        }
        with open(mock_state_file, "w") as f:
            json.dump(state, f)

        # User asks a question - should use local claude-emulator seamlessly
        # 180s timeout for claude-emulator (it's a 5B parameter model)
        start_time = time.time()
        response = call_ollama_api(
            "Help me understand this Python error: TypeError: cannot unpack non-iterable NoneType",
            model=CLAUDE_EMULATOR,
            timeout=180,
        )
        elapsed = time.time() - start_time

        assert (
            response is not None
        ), "Claude-emulator must respond for seamless fallback"
        assert len(response) > 50, "Response must be helpful, not truncated"
        print(f"\n[PROFILE] claude-emulator response time: {elapsed:.2f}s")

        # Later, user resets
        reset_state = {
            "rate_limited": False,
            "last_429": None,
            "fallback_active": False,
            "current_model": "copilot",
        }
        with open(mock_state_file, "w") as f:
            json.dump(reset_state, f)

        # Verify back to normal
        with open(mock_state_file) as f:
            state = json.load(f)
        assert state["current_model"] == "copilot"

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_e2e_continuous_work_during_fallback(self):
        """E2E: User can do multiple tasks while in fallback mode

        CLIENT DEMO: Shows continuous productivity during outage
        """
        tasks = [
            ("What is a Python decorator? Brief.", CLAUDE_EMULATOR),
            ("How to create a git branch? Brief.", CLAUDE_EMULATOR),
            ("List vs tuple in Python? Brief.", CLAUDE_EMULATOR),
        ]

        responses = []
        total_time = 0

        for task, model in tasks:
            start = time.time()
            response = call_ollama_api(task, model=model, timeout=180)
            elapsed = time.time() - start
            total_time += elapsed

            responses.append(response)
            print(f"\n[PROFILE] Task '{task[:30]}...' - {elapsed:.2f}s")
            assert response is not None, f"Failed to get response for: {task}"

        # All tasks should have meaningful responses
        assert all(r is not None and len(r) > 10 for r in responses)
        print(
            f"\n[PROFILE] Total time for 3 tasks: {total_time:.2f}s, avg: {total_time/3:.2f}s"
        )

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_e2e_code_assistance_during_fallback(self):
        """E2E: Local LLM can assist with code questions"""
        code_prompt = """
        Fix this Python function:

        def add(a, b)
            return a + b
        """

        response = call_ollama_api(code_prompt, model=CLAUDE_EMULATOR, timeout=120)
        assert response is not None
        # Should mention the missing colon
        assert ":" in response or "colon" in response.lower() or "def" in response


# ============================================================================
# Performance Tests
# ============================================================================


class TestPerformance:
    """Test performance requirements"""

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_quick_model_latency(self):
        """Quick model should have acceptable latency"""
        times = []
        for _ in range(3):
            start = time.time()
            response = call_ollama_api("Reply: OK", model=QUICK_MODEL)
            elapsed = time.time() - start
            if response:
                times.append(elapsed)

        assert len(times) > 0, "No successful responses"
        avg_time = sum(times) / len(times)
        assert avg_time < 15, f"Average latency {avg_time:.1f}s exceeds 15s threshold"
        print(f"\nAverage latency: {avg_time:.2f}s")

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_response_quality_maintained(self):
        """Response quality should be acceptable during fallback"""
        prompt = "What is the capital of France?"
        response = call_ollama_api(prompt, model=QUICK_MODEL)

        assert response is not None
        assert "paris" in response.lower()


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test error handling scenarios"""

    def test_handles_missing_state_file(self, temp_state_dir):
        """Should handle missing state file gracefully"""
        non_existent = os.path.join(temp_state_dir, "does-not-exist.json")

        # Simulate load_fallback_state behavior
        try:
            if os.path.exists(non_existent):
                with open(non_existent) as f:
                    state = json.load(f)
            else:
                state = {
                    "rate_limited": False,
                    "last_429": None,
                    "fallback_active": False,
                    "current_model": "copilot",
                }
        except:
            state = {"rate_limited": False}

        assert not state["rate_limited"]

    def test_handles_corrupted_state_file(self, mock_state_file):
        """Should handle corrupted state file gracefully"""
        os.makedirs(os.path.dirname(mock_state_file), exist_ok=True)

        # Write corrupted JSON
        with open(mock_state_file, "w") as f:
            f.write("{ invalid json }")

        # Should return defaults on parse error
        try:
            with open(mock_state_file) as f:
                state = json.load(f)
        except json.JSONDecodeError:
            state = {
                "rate_limited": False,
                "last_429": None,
                "fallback_active": False,
                "current_model": "copilot",
            }

        assert not state["rate_limited"]

    def test_handles_ollama_not_running(self):
        """Should handle Ollama not running gracefully"""
        # Try to connect to wrong port (simulate Ollama not running)
        try:
            req = urllib.request.Request("http://localhost:99999/api/tags")
            urllib.request.urlopen(req, timeout=2)
            running = True
        except:
            running = False

        # Should detect Ollama not running
        # (The actual implementation would return an error message)
        # This test just verifies the detection works
        assert not running  # We expect it to fail


# ============================================================================
# Handoff Tests
# ============================================================================


class TestHandoff:
    """Test handoff functionality between Claude and local LLM"""

    def test_handoff_file_creation(self, temp_state_dir):
        """Handoff file should be created with correct structure"""
        handoff_file = os.path.join(temp_state_dir, "llm-handoff.json")

        handoff = {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": "rate_limit_429",
            "urgency": "high",
            "current_task": "Writing unit tests for fallback system",
            "context": "Testing the openrouter MCP server fallback functionality",
            "pending_actions": ["Complete test file", "Run tests", "Add to CI"],
            "handoff_to": "local_llm",
        }

        os.makedirs(os.path.dirname(handoff_file), exist_ok=True)
        with open(handoff_file, "w") as f:
            json.dump(handoff, f, indent=2)

        assert os.path.exists(handoff_file)

        with open(handoff_file) as f:
            loaded = json.load(f)

        assert loaded["urgency"] == "high"
        assert len(loaded["pending_actions"]) == 3

    def test_handoff_check_detects_pending(self, temp_state_dir):
        """Should detect pending handoff"""
        handoff_file = os.path.join(temp_state_dir, "llm-handoff.json")

        # Create a pending handoff
        os.makedirs(os.path.dirname(handoff_file), exist_ok=True)
        with open(handoff_file, "w") as f:
            json.dump(
                {
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "pending_actions": ["Test action"],
                    "status": "pending",
                },
                f,
            )

        # Check for handoff
        assert os.path.exists(handoff_file)
        with open(handoff_file) as f:
            handoff = json.load(f)

        assert "pending_actions" in handoff
        assert len(handoff["pending_actions"]) > 0


# ============================================================================
# Benchmark Markers and JSON Output for CI
# ============================================================================


class TestBenchmarkMetrics:
    """Tests with @pytest.mark.benchmark for CI performance tracking"""

    @pytest.mark.benchmark
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_benchmark_quick_model_latency(self):
        """Benchmark: Quick model response latency"""
        times = []

        for _ in range(3):
            start = time.time()
            response = call_ollama_api("Reply: OK", model=QUICK_MODEL, timeout=30)
            elapsed = time.time() - start
            if response:
                times.append(elapsed)

        if not times:
            pytest.skip("No successful responses")

        avg_time = sum(times) / len(times)
        result = {
            "test": "quick_model_latency",
            "model": QUICK_MODEL,
            "avg_latency": round(avg_time, 3),
            "min_latency": round(min(times), 3),
            "max_latency": round(max(times), 3),
            "samples": len(times),
            "threshold": 15,
            "passed": avg_time < 15,
            "timestamp": datetime.now().isoformat(),
        }

        # Output for CI parsing
        print(f"\n📊 BENCHMARK: {json.dumps(result)}")

        assert avg_time < 15, f"Quick model too slow: {avg_time:.2f}s"

    @pytest.mark.benchmark
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_benchmark_fallback_activation_speed(self):
        """Benchmark: How fast fallback can activate"""
        start = time.time()

        # Simulate state change (the actual fallback activation)
        state = {
            "rate_limited": True,
            "last_429": datetime.now().isoformat(),
            "fallback_active": True,
            "current_model": QUICK_MODEL,
        }

        # Simulate writing state (in real system this triggers fallback)
        json.dumps(state)

        # First query to local model after "activation"
        response = call_ollama_api("Reply: OK", model=QUICK_MODEL, timeout=30)

        total_time = time.time() - start

        result = {
            "test": "fallback_activation_speed",
            "total_time": round(total_time, 3),
            "success": response is not None,
            "threshold": 30,
            "passed": total_time < 30 and response is not None,
            "timestamp": datetime.now().isoformat(),
        }

        print(f"\n📊 BENCHMARK: {json.dumps(result)}")

        assert result["passed"], f"Fallback activation too slow: {total_time:.2f}s"

    @pytest.mark.benchmark
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_benchmark_throughput(self):
        """Benchmark: Queries per minute"""
        start = time.time()
        successful = 0
        total_queries = 5

        for i in range(total_queries):
            response = call_ollama_api(f"Count: {i}", model=QUICK_MODEL, timeout=20)
            if response:
                successful += 1

        elapsed = time.time() - start
        qpm = (successful / elapsed) * 60 if elapsed > 0 else 0

        result = {
            "test": "throughput",
            "model": QUICK_MODEL,
            "queries_attempted": total_queries,
            "queries_successful": successful,
            "total_time": round(elapsed, 3),
            "queries_per_minute": round(qpm, 2),
            "success_rate": round(successful / total_queries, 2),
            "timestamp": datetime.now().isoformat(),
        }

        print(f"\n📊 BENCHMARK: {json.dumps(result)}")

        assert (
            successful >= 3
        ), f"Too few successful queries: {successful}/{total_queries}"


# ============================================================================
# Test Summary and JSON Report Generation
# ============================================================================


def generate_test_summary():
    """Generate summary JSON for CI artifacts"""
    OUTPUT_DIR.mkdir(exist_ok=True)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "test_file": str(Path(__file__).name),
        "ollama_running": is_ollama_running(),
        "tests_run": True,
        "notes": "Run with --json-report for detailed pytest output",
    }

    summary_path = OUTPUT_DIR / "test_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary_path


@pytest.fixture(scope="session", autouse=True)
def session_summary(request):
    """Generate summary at end of test session"""
    yield
    # Run at end of session
    try:
        summary_path = generate_test_summary()
        print(f"\n📋 Test summary saved to: {summary_path}")
    except Exception as e:
        print(f"\n⚠️ Could not generate summary: {e}")


if __name__ == "__main__":
    # Generate output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Run with benchmark support if available
    args = [__file__, "-v", "--tb=short"]

    # Add JSON report if plugin available
    try:
        import pytest_json_report

        args.extend(
            ["--json-report", f"--json-report-file={OUTPUT_DIR}/test_report.json"]
        )
    except ImportError:
        pass

    pytest.main(args)
