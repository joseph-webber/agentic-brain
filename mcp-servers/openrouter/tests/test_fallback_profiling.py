#!/usr/bin/env python3
"""
🔬 Local LLM Fallback System - Profiling Tests

This module provides comprehensive profiling and benchmarking for the
fallback system that seamlessly switches to local LLMs when cloud APIs
(Claude/Copilot) get rate limited.

Key metrics measured:
- Response latency per model
- Throughput (responses per minute)
- Memory usage during inference
- Model comparison benchmarks

Enterprise Demo Focus:
- Shows seamless fallback capability
- Proves acceptable performance during outages
- Provides baseline for SLA commitments

Run: pytest test_fallback_profiling.py -v --benchmark-only
     pytest test_fallback_profiling.py -v --benchmark-json=benchmark.json

Requires: pip install pytest-benchmark psutil
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

# Try to import optional dependencies
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None

# Configuration
OLLAMA_URL = "http://localhost:11434"
OUTPUT_DIR = Path(__file__).parent / "benchmark_results"
MODELS_TO_BENCHMARK = {
    "llama3.2:3b": {
        "description": "Fast local model",
        "timeout": 30,
        "expected_max_latency": 15,
    },
    "llama3.1:8b": {
        "description": "Quality local model",
        "timeout": 60,
        "expected_max_latency": 45,
    },
    "claude-emulator": {
        "description": "Brain-aware recovery model",
        "timeout": 180,
        "expected_max_latency": 120,
    },
}

# Test prompts with varying complexity
BENCHMARK_PROMPTS = {
    "simple": "Reply with just: OK",
    "medium": "What is Python? One sentence.",
    "complex": "Explain the difference between a list and a tuple in Python. Be brief.",
}


def is_ollama_running() -> bool:
    """Check if Ollama service is running"""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except:
        return False


def get_available_models() -> List[str]:
    """Get list of models available in Ollama"""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            return [line.split()[0] for line in lines if line.strip()]
    except:
        pass
    return []


def call_ollama_api(
    prompt: str, model: str, timeout: int = 60
) -> Tuple[Optional[str], float, Dict]:
    """
    Call Ollama API and return (response, latency, metadata)

    Returns:
        Tuple of (response_text, latency_seconds, metadata_dict)
    """
    metadata = {
        "model": model,
        "prompt_length": len(prompt),
        "success": False,
        "error": None,
    }

    start = time.time()
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
            elapsed = time.time() - start

            metadata.update(
                {
                    "success": True,
                    "response_length": len(data.get("response", "")),
                    "eval_count": data.get("eval_count"),
                    "eval_duration": data.get("eval_duration"),
                    "prompt_eval_count": data.get("prompt_eval_count"),
                    "total_duration": data.get("total_duration"),
                }
            )

            return data.get("response", "").strip(), elapsed, metadata

    except urllib.error.URLError as e:
        elapsed = time.time() - start
        metadata["error"] = f"URL Error: {e.reason}"
        return None, elapsed, metadata
    except Exception as e:
        elapsed = time.time() - start
        metadata["error"] = str(e)
        return None, elapsed, metadata


def get_memory_usage() -> Dict:
    """Get current memory usage stats"""
    if not HAS_PSUTIL:
        return {"available": False}

    mem = psutil.virtual_memory()
    return {
        "available": True,
        "total_gb": round(mem.total / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "percent_used": mem.percent,
    }


def save_benchmark_report(results: Dict, filename: str = None) -> Path:
    """Save benchmark results to JSON file"""
    OUTPUT_DIR.mkdir(exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_{timestamp}.json"

    filepath = OUTPUT_DIR / filename
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)

    return filepath


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def ollama_available():
    """Check Ollama availability once per module"""
    if not is_ollama_running():
        pytest.skip("Ollama not running - skipping profiling tests")
    return True


@pytest.fixture(scope="module")
def available_models(ollama_available):
    """Get available models once per module"""
    return get_available_models()


# ============================================================================
# Benchmark Tests - Response Latency
# ============================================================================


class TestResponseLatency:
    """Benchmark response latency for each model"""

    @pytest.mark.benchmark(group="latency")
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_quick_model_latency(self, benchmark):
        """Benchmark llama3.2:3b response time (fast model)"""

        def run_query():
            response, elapsed, meta = call_ollama_api(
                BENCHMARK_PROMPTS["simple"], "llama3.2:3b", timeout=30
            )
            return elapsed

        # Warmup
        call_ollama_api("warmup", "llama3.2:3b", timeout=60)

        # Benchmark
        result = benchmark.pedantic(run_query, rounds=3, iterations=1, warmup_rounds=1)

        # Assert acceptable latency
        assert result < 15, f"Quick model too slow: {result:.2f}s"

    @pytest.mark.benchmark(group="latency")
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_full_model_latency(self, benchmark):
        """Benchmark llama3.1:8b response time (quality model)"""

        def run_query():
            response, elapsed, meta = call_ollama_api(
                BENCHMARK_PROMPTS["simple"], "llama3.1:8b", timeout=60
            )
            return elapsed

        # Warmup
        call_ollama_api("warmup", "llama3.1:8b", timeout=120)

        result = benchmark.pedantic(run_query, rounds=3, iterations=1, warmup_rounds=1)

        assert result < 45, f"Full model too slow: {result:.2f}s"

    @pytest.mark.benchmark(group="latency")
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    @pytest.mark.timeout(300)
    def test_claude_emulator_latency(self, benchmark):
        """Benchmark claude-emulator response time (brain-aware model)"""

        def run_query():
            response, elapsed, meta = call_ollama_api(
                BENCHMARK_PROMPTS["simple"], "claude-emulator", timeout=180
            )
            return elapsed

        # Warmup (longer for larger model)
        call_ollama_api("warmup", "claude-emulator", timeout=180)

        result = benchmark.pedantic(
            run_query, rounds=2, iterations=1, warmup_rounds=0  # Already warmed up
        )

        assert result < 120, f"Claude emulator too slow: {result:.2f}s"


# ============================================================================
# Benchmark Tests - Throughput
# ============================================================================


class TestThroughput:
    """Benchmark throughput (responses per minute)"""

    @pytest.mark.benchmark(group="throughput")
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_quick_model_throughput(self, benchmark):
        """Measure how many queries llama3.2:3b can handle"""
        queries_completed = 0

        def run_burst():
            nonlocal queries_completed
            queries_completed = 0
            for i in range(5):
                response, _, meta = call_ollama_api(
                    f"Reply: {i}", "llama3.2:3b", timeout=30
                )
                if meta["success"]:
                    queries_completed += 1
            return queries_completed

        # Warmup
        call_ollama_api("warmup", "llama3.2:3b", timeout=60)

        result = benchmark(run_burst)

        # Should complete at least 3 of 5 queries
        assert queries_completed >= 3, f"Only {queries_completed}/5 queries succeeded"

    @pytest.mark.benchmark(group="throughput")
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_concurrent_query_handling(self, benchmark):
        """Test handling of rapid sequential queries"""
        times = []

        def run_sequential():
            times.clear()
            for i in range(3):
                start = time.time()
                response, _, meta = call_ollama_api(
                    f"Count: {i}", "llama3.2:3b", timeout=20
                )
                times.append(time.time() - start)
            return sum(times)

        # Warmup
        call_ollama_api("warmup", "llama3.2:3b", timeout=60)

        total_time = benchmark(run_sequential)

        avg_time = sum(times) / len(times) if times else 0
        print(f"\nSequential query avg: {avg_time:.2f}s")
        assert avg_time < 15, f"Sequential queries too slow: {avg_time:.2f}s avg"


# ============================================================================
# Memory Usage Tests
# ============================================================================


class TestMemoryUsage:
    """Monitor memory usage during inference"""

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not installed")
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_memory_during_quick_model(self):
        """Monitor memory usage during llama3.2:3b inference"""
        mem_before = get_memory_usage()

        # Run inference
        response, elapsed, meta = call_ollama_api(
            BENCHMARK_PROMPTS["complex"], "llama3.2:3b", timeout=30
        )

        mem_after = get_memory_usage()

        print(f"\nMemory before: {mem_before['used_gb']:.2f}GB")
        print(f"Memory after: {mem_after['used_gb']:.2f}GB")
        print(f"Delta: {mem_after['used_gb'] - mem_before['used_gb']:.2f}GB")

        # Memory increase should be reasonable (< 4GB for 3B model)
        delta = mem_after["used_gb"] - mem_before["used_gb"]
        assert delta < 4, f"Excessive memory usage: {delta:.2f}GB increase"

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not installed")
    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_memory_during_full_model(self):
        """Monitor memory usage during llama3.1:8b inference"""
        mem_before = get_memory_usage()

        response, elapsed, meta = call_ollama_api(
            BENCHMARK_PROMPTS["complex"], "llama3.1:8b", timeout=60
        )

        mem_after = get_memory_usage()

        print(f"\nMemory before: {mem_before['used_gb']:.2f}GB")
        print(f"Memory after: {mem_after['used_gb']:.2f}GB")

        # 8B model might use more memory
        delta = mem_after["used_gb"] - mem_before["used_gb"]
        assert delta < 8, f"Excessive memory usage: {delta:.2f}GB increase"


# ============================================================================
# Model Comparison Benchmarks
# ============================================================================


class TestModelComparison:
    """Compare performance across models"""

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_model_comparison_simple(self):
        """Compare all models on simple prompt"""
        results = {}
        prompt = BENCHMARK_PROMPTS["simple"]

        for model, config in MODELS_TO_BENCHMARK.items():
            # Warmup
            call_ollama_api("warmup", model, timeout=config["timeout"])

            # Measure
            response, elapsed, meta = call_ollama_api(
                prompt, model, timeout=config["timeout"]
            )

            results[model] = {
                "latency": elapsed,
                "success": meta["success"],
                "response_length": meta.get("response_length", 0),
                "threshold": config["expected_max_latency"],
                "within_threshold": elapsed < config["expected_max_latency"],
            }

            print(
                f"\n{model}: {elapsed:.2f}s (threshold: {config['expected_max_latency']}s)"
            )

        # Save results
        save_benchmark_report(
            {
                "test": "model_comparison_simple",
                "timestamp": datetime.now().isoformat(),
                "prompt": prompt,
                "results": results,
            },
            "model_comparison_latest.json",
        )

        # At least quick model should pass
        assert results["llama3.2:3b"][
            "within_threshold"
        ], f"Quick model exceeded threshold: {results['llama3.2:3b']['latency']:.2f}s"

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_model_comparison_complex(self):
        """Compare models on complex prompt"""
        results = {}
        prompt = BENCHMARK_PROMPTS["complex"]

        for model, config in MODELS_TO_BENCHMARK.items():
            response, elapsed, meta = call_ollama_api(
                prompt, model, timeout=config["timeout"]
            )

            results[model] = {
                "latency": elapsed,
                "success": meta["success"],
                "response_quality": (
                    len(meta.get("response_length", 0)) > 20
                    if meta["success"]
                    else False
                ),
            }

            print(f"\n{model}: {elapsed:.2f}s, success={meta['success']}")

        # Verify at least one model succeeded
        successes = [r["success"] for r in results.values()]
        assert any(successes), "All models failed on complex prompt"


# ============================================================================
# Regression Detection
# ============================================================================


class TestRegressionDetection:
    """Track metrics over time to detect regressions"""

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_baseline_comparison(self):
        """Compare against baseline performance"""
        baseline_file = Path(__file__).parent / "PERFORMANCE_BASELINE.md"

        # Run current benchmark
        response, elapsed, meta = call_ollama_api(
            BENCHMARK_PROMPTS["simple"], "llama3.2:3b", timeout=30
        )

        current_result = {
            "model": "llama3.2:3b",
            "latency": elapsed,
            "timestamp": datetime.now().isoformat(),
            "success": meta["success"],
        }

        # Save for tracking
        history_file = OUTPUT_DIR / "performance_history.jsonl"
        OUTPUT_DIR.mkdir(exist_ok=True)

        with open(history_file, "a") as f:
            f.write(json.dumps(current_result) + "\n")

        # Check against threshold (from baseline doc)
        threshold = 15  # seconds, as defined in baseline
        assert (
            elapsed < threshold
        ), f"Performance regression! Current: {elapsed:.2f}s, Threshold: {threshold}s"

        print(f"\n✅ Performance OK: {elapsed:.2f}s (threshold: {threshold}s)")

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_generate_full_report(self):
        """Generate comprehensive benchmark report for CI"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "system": {
                "memory": get_memory_usage(),
                "platform": sys.platform,
            },
            "models": {},
            "summary": {"all_passed": True, "failures": []},
        }

        for model, config in MODELS_TO_BENCHMARK.items():
            times = []
            successes = 0

            # Run 3 iterations
            for i in range(3):
                response, elapsed, meta = call_ollama_api(
                    BENCHMARK_PROMPTS["medium"], model, timeout=config["timeout"]
                )
                times.append(elapsed)
                if meta["success"]:
                    successes += 1

            avg_time = sum(times) / len(times)
            passed = avg_time < config["expected_max_latency"]

            report["models"][model] = {
                "avg_latency": round(avg_time, 2),
                "min_latency": round(min(times), 2),
                "max_latency": round(max(times), 2),
                "success_rate": f"{successes}/3",
                "threshold": config["expected_max_latency"],
                "passed": passed,
            }

            if not passed:
                report["summary"]["all_passed"] = False
                report["summary"]["failures"].append(model)

        # Save report
        report_path = save_benchmark_report(report, "ci_benchmark_report.json")
        print(f"\n📊 Full report saved to: {report_path}")

        # Print summary for CI logs
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)
        for model, data in report["models"].items():
            status = "✅" if data["passed"] else "❌"
            print(
                f"{status} {model}: {data['avg_latency']}s avg (threshold: {data['threshold']}s)"
            )
        print("=" * 60)

        # Don't fail the test - this is for reporting
        return report


# ============================================================================
# CI Integration Helpers
# ============================================================================


class TestCIIntegration:
    """Tests designed for CI pipeline integration"""

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_quick_ci_check(self):
        """Quick check suitable for every CI run (< 30s)"""
        response, elapsed, meta = call_ollama_api(
            "Reply: OK", "llama3.2:3b", timeout=30
        )

        # Output in format CI can parse
        result = {
            "test": "quick_ci_check",
            "model": "llama3.2:3b",
            "latency_seconds": round(elapsed, 2),
            "success": meta["success"],
            "passed": meta["success"] and elapsed < 30,
        }

        # Print JSON for CI parsing
        print(f"\n::set-output name=quick_check::{json.dumps(result)}")

        assert result["passed"], f"Quick CI check failed: {result}"

    @pytest.mark.skipif(not is_ollama_running(), reason="Ollama not running")
    def test_output_json_metrics(self):
        """Output JSON metrics for CI artifact collection"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "ollama_running": is_ollama_running(),
            "available_models": get_available_models(),
            "memory": get_memory_usage(),
            "benchmarks": {},
        }

        if is_ollama_running():
            for model in ["llama3.2:3b"]:  # Just quick model for CI
                response, elapsed, meta = call_ollama_api(
                    BENCHMARK_PROMPTS["simple"], model, timeout=30
                )
                metrics["benchmarks"][model] = {
                    "latency": round(elapsed, 2),
                    "success": meta["success"],
                }

        # Save as CI artifact
        OUTPUT_DIR.mkdir(exist_ok=True)
        metrics_path = OUTPUT_DIR / "ci_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        print(f"\n📈 Metrics saved to: {metrics_path}")
        print(json.dumps(metrics, indent=2))


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    # When run directly, output a quick benchmark summary
    print("🔬 Local LLM Fallback System - Profiling")
    print("=" * 50)

    if not is_ollama_running():
        print("❌ Ollama not running! Start with: ollama serve")
        sys.exit(1)

    print("✅ Ollama is running")
    print(f"📋 Available models: {get_available_models()}")
    print(f"💾 Memory: {get_memory_usage()}")

    # Run with pytest-benchmark
    pytest.main(
        [
            __file__,
            "-v",
            "--benchmark-only",
            "--benchmark-json=benchmark_results/latest.json",
            "-x",  # Stop on first failure
        ]
    )
