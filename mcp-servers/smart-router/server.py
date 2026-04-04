#!/usr/bin/env python3
"""
Smart Router MCP Server - Delegate tasks to multiple LLM providers.

Provides MCP tools for Claude to delegate heavy tasks to:
- OpenAI (GPT-4o, GPT-4o-mini) - Best for code, lots of credit
- Google Gemini (gemini-2.0-flash) - FREE, high limits
- Groq (llama-3.3-70b) - FREE, fastest (500 tok/sec)
- Local Ollama - UNLIMITED, private

SMART CYCLING:
- Rotates providers to let each "cool off"
- Tracks usage heat per provider
- Prefers cooler providers to avoid rate limits
- Not just fallback - proactive load distribution

Usage:
    Claude calls smart_delegate() with a prompt and task type
    Router picks best provider and returns result
    No verbose output - clean JSON responses
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Load environment from brain/.env
env_path = Path.home() / "brain" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))

# MCP imports
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from mcp.server import Server as FastMCP

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("smart-router")

# ============================================================================
# Provider Configuration
# ============================================================================

@dataclass
class ProviderConfig:
    name: str
    model: str
    api_key_env: str
    rate_limit: int  # requests per minute
    cost_per_1k: float  # USD per 1K tokens
    speed: str  # "fast", "medium", "slow"
    best_for: list[str]

PROVIDERS = {
    "openai": ProviderConfig(
        name="OpenAI",
        model="gpt-4o",
        api_key_env="OPENAI_API_KEY",
        rate_limit=500,
        cost_per_1k=0.005,
        speed="medium",
        best_for=["code", "analysis", "quality"],
    ),
    "openai-fast": ProviderConfig(
        name="OpenAI Fast",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        rate_limit=500,
        cost_per_1k=0.00015,
        speed="fast",
        best_for=["fast", "simple", "bulk"],
    ),
    "gemini": ProviderConfig(
        name="Google Gemini",
        model="gemini-2.0-flash",
        api_key_env="GEMINI_API_KEY",
        rate_limit=60,
        cost_per_1k=0.0,
        speed="fast",
        best_for=["free", "bulk", "analysis"],
    ),
    "groq": ProviderConfig(
        name="Groq",
        model="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        rate_limit=30,
        cost_per_1k=0.0,
        speed="fastest",
        best_for=["fast", "chat", "streaming"],
    ),
    "local": ProviderConfig(
        name="Local Ollama",
        model="llama3.1:8b",
        api_key_env="",
        rate_limit=999999,
        cost_per_1k=0.0,
        speed="medium",
        best_for=["private", "bulk", "unlimited"],
    ),
    # Anthropic Haiku - CHEAP model for smoke tests only, NOT for heavy work!
    "anthropic-haiku": ProviderConfig(
        name="Anthropic Haiku",
        model="claude-3-haiku-20240307",
        api_key_env="ANTHROPIC_API_KEY",
        rate_limit=50,
        cost_per_1k=0.00025,  # Very cheap
        speed="fast",
        best_for=["smoke-test", "simple", "validation"],
    ),
}

# Task to provider routing
# NOTE: anthropic-haiku NOT in main routes - only for smoke tests!
TASK_ROUTES = {
    "code": ["openai", "gemini", "local"],
    "fast": ["groq", "openai-fast", "local"],
    "quality": ["openai", "gemini", "groq"],
    "bulk": ["local", "gemini", "groq"],
    "free": ["gemini", "groq", "local"],
    "private": ["local"],
    "analysis": ["openai", "gemini", "groq"],
    "auto": ["openai", "groq", "gemini", "local"],
    "smoke-test": ["anthropic-haiku", "groq", "local"],  # Haiku for CI smoke tests
}

# Rate limit tracking
rate_limits: dict[str, list[float]] = {p: [] for p in PROVIDERS}

# ============================================================================
# ADMIN CONTROLS - Enable/Disable/Limit providers
# ============================================================================

# Provider modes: "full" | "smoke-test-only" | "heartbeat" | "disabled"
provider_modes: dict[str, str] = {p: "full" for p in PROVIDERS}

# Custom rate limits set by admin (overrides default)
admin_rate_limits: dict[str, int] = {}

# Provider notes (admin can add notes why disabled etc)
provider_notes: dict[str, str] = {}

def is_provider_available_for_task(provider: str, task: str) -> bool:
    """Check if provider is available for this task type based on admin mode."""
    mode = provider_modes.get(provider, "full")
    
    if mode == "disabled":
        return False
    elif mode == "heartbeat":
        # Heartbeat = only for health checks, not real work
        return task == "heartbeat"
    elif mode == "smoke-test-only":
        # Only for smoke tests and simple validation
        return task in ("smoke-test", "heartbeat", "simple")
    else:  # "full"
        return True

def get_effective_rate_limit(provider: str) -> int:
    """Get rate limit - admin override or default."""
    if provider in admin_rate_limits:
        return admin_rate_limits[provider]
    config = PROVIDERS.get(provider)
    return config.rate_limit if config else 0

# Smart cycling state - tracks "heat" of each provider
provider_heat: dict[str, float] = {p: 0.0 for p in PROVIDERS}
last_used: dict[str, float] = {p: 0.0 for p in PROVIDERS}
cycle_index: int = 0  # Round-robin index

# Cooldown settings (seconds)
COOLDOWN_RATE = 0.1  # Heat decreases by this per second
HEAT_PER_REQUEST = 1.0  # Heat added per request
MAX_HEAT = 10.0  # Max heat before considered "hot"

# ============================================================================
# Smart Cycling Logic
# ============================================================================

def update_heat():
    """Update provider heat based on time elapsed (cooling off)."""
    now = time.time()
    for p in provider_heat:
        elapsed = now - last_used.get(p, 0)
        # Cool down over time
        cooldown = elapsed * COOLDOWN_RATE
        provider_heat[p] = max(0.0, provider_heat[p] - cooldown)

def add_heat(provider: str):
    """Add heat when provider is used."""
    provider_heat[provider] = min(MAX_HEAT, provider_heat[provider] + HEAT_PER_REQUEST)
    last_used[provider] = time.time()

def get_coolest_provider(candidates: list[str]) -> str:
    """Get the coolest (least recently/heavily used) provider from candidates."""
    update_heat()
    
    if not candidates:
        return None
    
    # Sort by heat (coolest first)
    sorted_candidates = sorted(candidates, key=lambda p: provider_heat.get(p, 0))
    return sorted_candidates[0]

def get_provider_temps() -> dict[str, float]:
    """Get current temperature of all providers."""
    update_heat()
    return {p: round(provider_heat.get(p, 0), 2) for p in PROVIDERS}

def smart_cycle_order(base_order: list[str]) -> list[str]:
    """
    Reorder providers using smart cycling.
    
    Considers:
    - Base task preference order
    - Current heat/cooldown of each provider
    - Rate limit status
    
    Returns reordered list with cooler providers prioritized.
    """
    global cycle_index
    update_heat()
    
    if not base_order:
        return base_order
    
    # Score each provider (lower = better)
    def score(p: str) -> float:
        heat = provider_heat.get(p, 0)
        # Penalty for recent rate limit hits
        recent_requests = len([t for t in rate_limits.get(p, []) if time.time() - t < 60])
        rate_pressure = recent_requests / max(PROVIDERS[p].rate_limit, 1) if p in PROVIDERS else 0
        
        # Base position penalty (preserve task preference somewhat)
        try:
            position_penalty = base_order.index(p) * 0.5
        except ValueError:
            position_penalty = 10
        
        return heat + (rate_pressure * 5) + position_penalty
    
    # Sort by score
    reordered = sorted(base_order, key=score)
    
    # Apply round-robin nudge for variety
    cycle_index = (cycle_index + 1) % len(reordered)
    if cycle_index > 0 and len(reordered) > 1:
        # Occasionally bump a non-first provider to give others a chance
        if provider_heat.get(reordered[0], 0) > 2.0:  # If first is warm
            # Swap with a cooler one
            for i in range(1, len(reordered)):
                if provider_heat.get(reordered[i], 0) < provider_heat.get(reordered[0], 0):
                    reordered[0], reordered[i] = reordered[i], reordered[0]
                    break
    
    return reordered

# ============================================================================
# Provider Callers
# ============================================================================

async def call_openai(prompt: str, model: str = "gpt-4o") -> dict:
    """Call OpenAI API."""
    import httpx
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}
    
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096,
            },
        )
        if resp.status_code != 200:
            return {"error": f"OpenAI error: {resp.status_code} - {resp.text[:200]}"}
        data = resp.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "provider": "openai",
            "model": model,
            "tokens": data.get("usage", {}).get("total_tokens", 0),
        }

async def call_gemini(prompt: str) -> dict:
    """Call Google Gemini API."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY not set"}
    
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return {
            "content": response.text,
            "provider": "gemini",
            "model": "gemini-2.0-flash",
        }
    except Exception as e:
        return {"error": f"Gemini error: {str(e)[:200]}"}

async def call_groq(prompt: str) -> dict:
    """Call Groq API."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY not set"}
    
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return {
            "content": response.choices[0].message.content,
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "tokens": response.usage.total_tokens if response.usage else 0,
        }
    except Exception as e:
        return {"error": f"Groq error: {str(e)[:200]}"}

async def call_local(prompt: str) -> dict:
    """Call local Ollama."""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False,
                },
            )
            if resp.status_code != 200:
                return {"error": f"Ollama error: {resp.status_code}"}
            data = resp.json()
            return {
                "content": data.get("response", ""),
                "provider": "local",
                "model": "llama3.1:8b",
            }
    except Exception as e:
        return {"error": f"Local LLM error: {str(e)[:200]}"}

async def call_anthropic_haiku(prompt: str) -> dict:
    """Call Anthropic Haiku - CHEAP model for smoke tests only!"""
    import httpx
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code != 200:
                return {"error": f"Anthropic error: {resp.status_code} - {resp.text[:200]}"}
            data = resp.json()
            return {
                "content": data["content"][0]["text"],
                "provider": "anthropic-haiku",
                "model": "claude-3-haiku-20240307",
                "tokens": data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0),
            }
    except Exception as e:
        return {"error": f"Anthropic error: {str(e)[:200]}"}

CALLERS = {
    "openai": lambda p: call_openai(p, "gpt-4o"),
    "openai-fast": lambda p: call_openai(p, "gpt-4o-mini"),
    "gemini": call_gemini,
    "groq": call_groq,
    "local": call_local,
    "anthropic-haiku": call_anthropic_haiku,
}

# ============================================================================
# Smart Router Logic
# ============================================================================

def check_rate_limit(provider: str) -> bool:
    """Check if provider is within rate limit."""
    config = PROVIDERS.get(provider)
    if not config:
        return False
    
    now = time.time()
    window = 60  # 1 minute window
    
    # Clean old entries
    rate_limits[provider] = [t for t in rate_limits[provider] if now - t < window]
    
    return len(rate_limits[provider]) < config.rate_limit

def record_request(provider: str):
    """Record a request for rate limiting."""
    rate_limits[provider].append(time.time())

def get_available_providers() -> list[str]:
    """Get list of available providers (have API keys)."""
    available = []
    for name, config in PROVIDERS.items():
        if config.api_key_env == "":
            available.append(name)  # Local doesn't need key
        elif os.environ.get(config.api_key_env):
            available.append(name)
    return available

async def smart_route(prompt: str, task: str = "auto", prefer: str = None) -> dict:
    """
    Route request to best available provider with SMART CYCLING.
    
    Uses heat tracking and cooldown to rotate providers intelligently,
    avoiding rate limits by letting each provider "cool off".
    
    Args:
        prompt: The prompt to send
        task: Task type (code, fast, quality, bulk, free, private, auto)
        prefer: Preferred provider (optional override)
    
    Returns:
        dict with content, provider, model, or error
    """
    start = time.time()
    
    # Get base route order for task
    base_order = TASK_ROUTES.get(task, TASK_ROUTES["auto"])
    
    # If preference specified and available, try it first
    if prefer and prefer in CALLERS:
        base_order = [prefer] + [p for p in base_order if p != prefer]
    
    # Filter to available providers
    available = get_available_providers()
    base_order = [p for p in base_order if p in available]
    
    if not base_order:
        return {"error": "No providers available. Check API keys."}
    
    # SMART CYCLING: reorder based on heat/cooldown
    route_order = smart_cycle_order(base_order)
    
    # Try providers in order
    errors = []
    for provider in route_order:
        if not check_rate_limit(provider):
            errors.append(f"{provider}: rate limited")
            continue
        
        record_request(provider)
        add_heat(provider)  # Track usage for smart cycling
        caller = CALLERS.get(provider)
        if not caller:
            continue
        
        result = await caller(prompt)
        
        if "error" not in result:
            result["duration_ms"] = int((time.time() - start) * 1000)
            result["task"] = task
            return result
        
        errors.append(f"{provider}: {result['error']}")
    
    return {"error": f"All providers failed: {'; '.join(errors)}"}

# ============================================================================
# MCP Server
# ============================================================================

mcp = FastMCP("smart-router")

@mcp.tool()
async def smart_delegate(
    prompt: str,
    task: str = "auto",
    prefer: str = None,
) -> str:
    """
    Delegate a task to the best available LLM provider.
    
    Routes to OpenAI, Gemini, Groq, or Local based on task type.
    Returns the LLM response or error.
    
    Args:
        prompt: The prompt/question to send
        task: Task type - code, fast, quality, bulk, free, private, auto
        prefer: Optional preferred provider - openai, gemini, groq, local
    
    Returns:
        JSON with content, provider used, and timing
    """
    result = await smart_route(prompt, task, prefer)
    return json.dumps(result, indent=2)

@mcp.tool()
async def delegate_code(prompt: str) -> str:
    """
    Delegate a CODE task (analysis, review, generation).
    Uses OpenAI GPT-4o primarily (best for code).
    
    Args:
        prompt: Code-related prompt
    
    Returns:
        LLM response optimized for code tasks
    """
    result = await smart_route(prompt, task="code")
    return json.dumps(result, indent=2)

@mcp.tool()
async def delegate_fast(prompt: str) -> str:
    """
    Delegate a FAST task (quick questions, simple tasks).
    Uses Groq primarily (500 tokens/sec, FREE).
    
    Args:
        prompt: Quick question or simple task
    
    Returns:
        Fast LLM response
    """
    result = await smart_route(prompt, task="fast")
    return json.dumps(result, indent=2)

@mcp.tool()
async def delegate_bulk(prompt: str) -> str:
    """
    Delegate a BULK task (large processing, many requests).
    Uses Local Ollama primarily (UNLIMITED, no rate limits).
    
    Args:
        prompt: Bulk processing task
    
    Returns:
        LLM response with no rate limit concerns
    """
    result = await smart_route(prompt, task="bulk")
    return json.dumps(result, indent=2)

@mcp.tool()
async def delegate_free(prompt: str) -> str:
    """
    Delegate using only FREE providers (Gemini, Groq, Local).
    No OpenAI costs.
    
    Args:
        prompt: Any prompt
    
    Returns:
        Response from free provider
    """
    result = await smart_route(prompt, task="free")
    return json.dumps(result, indent=2)

@mcp.tool()
async def router_status() -> str:
    """
    Get smart router status - available providers, rate limits, health.
    
    Returns:
        JSON status report
    """
    available = get_available_providers()
    
    status = {
        "available_providers": available,
        "providers": {},
        "task_routes": TASK_ROUTES,
    }
    
    for name in available:
        config = PROVIDERS.get(name)
        if config:
            requests_in_window = len(rate_limits.get(name, []))
            status["providers"][name] = {
                "model": config.model,
                "speed": config.speed,
                "cost_per_1k": config.cost_per_1k,
                "rate_limit": config.rate_limit,
                "requests_last_minute": requests_in_window,
                "available": requests_in_window < config.rate_limit,
            }
    
    return json.dumps(status, indent=2)

@mcp.tool()
async def parallel_delegate(prompts: list[str], task: str = "auto") -> str:
    """
    Delegate multiple prompts in PARALLEL to different providers.
    Distributes load across all available providers.
    
    Args:
        prompts: List of prompts to process
        task: Task type for all prompts
    
    Returns:
        JSON list of results
    """
    available = get_available_providers()
    
    async def process_one(i: int, prompt: str) -> dict:
        # Rotate through providers
        prefer = available[i % len(available)] if available else None
        result = await smart_route(prompt, task, prefer)
        result["index"] = i
        return result
    
    tasks = [process_one(i, p) for i, p in enumerate(prompts)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to error dicts
    final = []
    for r in results:
        if isinstance(r, Exception):
            final.append({"error": str(r)})
        else:
            final.append(r)
    
    return json.dumps(final, indent=2)

@mcp.tool()
async def router_temperatures() -> str:
    """
    Get current "temperature" (heat) of all providers.
    Cooler providers are preferred for smart cycling.
    
    Returns:
        JSON with provider temps and recommended order
    """
    temps = get_provider_temps()
    available = get_available_providers()
    
    # Get recommended order for auto task
    base_order = [p for p in TASK_ROUTES["auto"] if p in available]
    smart_order = smart_cycle_order(base_order)
    
    return json.dumps({
        "temperatures": temps,
        "coolest_first": smart_order,
        "note": "Lower temp = cooler = preferred. Heat decays over time."
    }, indent=2)

@mcp.tool()
async def race_delegate(prompt: str) -> str:
    """
    Race multiple providers - return FASTEST response.
    Sends same prompt to all available providers simultaneously.
    
    Args:
        prompt: The prompt to race
    
    Returns:
        Fastest successful response
    """
    available = get_available_providers()
    
    async def try_provider(provider: str) -> dict:
        if not check_rate_limit(provider):
            return {"error": "rate limited", "provider": provider}
        record_request(provider)
        caller = CALLERS.get(provider)
        if not caller:
            return {"error": "no caller", "provider": provider}
        return await caller(prompt)
    
    tasks = [try_provider(p) for p in available]
    
    # Return first successful result
    for coro in asyncio.as_completed(tasks):
        result = await coro
        if "error" not in result:
            return json.dumps(result, indent=2)
    
    return json.dumps({"error": "All providers failed"})

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    mcp.run()
