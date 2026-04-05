#!/usr/bin/env python3
"""
🧠 Local LLM MCP Server - AMAZING Integration
Direct brain access to local Ollama models
"""

import subprocess
import json
import time
import os
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("local-llm", "1.0.0")
except ImportError:
    # Fallback for testing
    class MockMCP:
        def tool(self):
            return lambda f: f

        def run(self):
            pass

    mcp = MockMCP()

MODELS = {"fast": "llama3.2:3b", "balanced": "llama3.1:8b", "brain": "claude-emulator"}

BRAIN_CONTEXT = """You are Iris Lumina, an AI brain assistant.
Designed for accessibility, optimized for VoiceOver users.
Be concise, professional, warm. Help with coding and communication."""

METRICS_FILE = Path.home() / ".brain-continuity" / "local-llm-metrics.json"


def load_metrics():
    try:
        if METRICS_FILE.exists():
            return json.loads(METRICS_FILE.read_text())
    except:
        pass
    return {"requests": 0, "successes": 0, "total_time": 0, "quota_saved": 0}


def save_metrics(m):
    METRICS_FILE.parent.mkdir(exist_ok=True)
    METRICS_FILE.write_text(json.dumps(m))


def run_ollama(model: str, prompt: str, timeout: int = 60):
    metrics = load_metrics()
    start = time.time()

    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start
        metrics["requests"] += 1
        metrics["total_time"] += elapsed

        if result.returncode == 0:
            metrics["successes"] += 1
            metrics["quota_saved"] += 1
            save_metrics(metrics)
            return {
                "success": True,
                "response": result.stdout.strip(),
                "model": model,
                "time": f"{elapsed:.2f}s",
            }
        save_metrics(metrics)
        return {"success": False, "error": result.stderr}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def local_quick(prompt: str) -> dict:
    """⚡ Quick query (1-3s) using llama3.2:3b"""
    return run_ollama(MODELS["fast"], prompt, timeout=15)


@mcp.tool()
def local_ask(prompt: str, model: str = "balanced", use_brain: bool = False) -> dict:
    """🧠 Query with model selection: fast/balanced/brain"""
    model_name = MODELS.get(model, MODELS["balanced"])
    full_prompt = f"{BRAIN_CONTEXT}\n\nUser: {prompt}\n\nIris:" if use_brain else prompt
    timeout = {"fast": 15, "balanced": 60, "brain": 120}.get(model, 60)
    return run_ollama(model_name, full_prompt, timeout)


@mcp.tool()
def local_smart(prompt: str) -> dict:
    """🎯 Auto-routes to best model based on prompt"""
    if len(prompt) < 50:
        return run_ollama(MODELS["fast"], prompt, 15)
    elif len(prompt) > 200:
        return run_ollama(MODELS["brain"], f"{BRAIN_CONTEXT}\n\n{prompt}", 120)
    return run_ollama(MODELS["balanced"], prompt, 60)


@mcp.tool()
def local_iris(prompt: str) -> dict:
    """💜 Full Iris Lumina personality response"""
    full_prompt = f"{BRAIN_CONTEXT}\n\nUser says: {prompt}\n\nIris responds:"
    return run_ollama(MODELS["brain"], full_prompt, 120)


@mcp.tool()
def local_status() -> dict:
    """📊 Get local LLM status and metrics"""
    metrics = load_metrics()
    try:
        ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=5)
        loaded = ps.stdout if ps.returncode == 0 else "None"
    except:
        loaded = "Unknown"

    avg = metrics["total_time"] / metrics["requests"] if metrics["requests"] > 0 else 0
    rate = (
        metrics["successes"] / metrics["requests"] * 100
        if metrics["requests"] > 0
        else 0
    )

    return {
        "models": list(MODELS.values()),
        "loaded": loaded,
        "requests": metrics["requests"],
        "success_rate": f"{rate:.0f}%",
        "avg_time": f"{avg:.2f}s",
        "quota_saved": metrics["quota_saved"],
        "money_saved": f"${metrics['quota_saved'] * 0.04:.2f}",
    }


@mcp.tool()
def local_warmup(model: str = "fast") -> dict:
    """🔥 Pre-warm model for instant responses"""
    return run_ollama(
        MODELS.get(model, MODELS["fast"]),
        "warmup",
        {"fast": 30, "balanced": 60, "brain": 180}.get(model, 60),
    )


@mcp.tool()
def local_benchmark() -> dict:
    """⚡ Test all model speeds"""
    results = {}
    for name, model in MODELS.items():
        start = time.time()
        try:
            r = subprocess.run(
                ["ollama", "run", model, "Say: OK"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            results[name] = {
                "time": f"{time.time()-start:.2f}s",
                "ok": r.returncode == 0,
            }
        except:
            results[name] = {"ok": False, "error": "timeout"}
    return results


if __name__ == "__main__":
    mcp.run()
