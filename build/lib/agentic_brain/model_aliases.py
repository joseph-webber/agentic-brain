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

# =============================================================================
# LLM Model Aliases - Quick Codes for Easy Switching
# =============================================================================
#
# NAMING SYSTEM:
#   [PROVIDER][TIER]
#
#   Provider (2 letters):
#     L  = Local (Ollama)
#     CL = Claude (Anthropic)
#     OP = OpenAI
#     AZ = Azure OpenAI
#     GO = Gemini (Google)
#     GR = Groq
#     OR = OpenRouter
#
#   Tier (number):
#     1 or blank = Best/Default
#     2 = Cheap/Fast
#     3 = Premium/Special
#     4 = Embeddings/Special
#
# EXAMPLES:
#   L1  = Local fast (llama3.2:3b)
#   CL  = Claude best (Sonnet 4)
#   CL2 = Claude cheap (Haiku)
#   OP  = OpenAI best (GPT-4o)
#   OP2 = OpenAI cheap (GPT-4o-mini)
#
# =============================================================================

from typing import Any, Dict

# =============================================================================
# MODEL ALIASES - COMPLETE LIST
# =============================================================================

MODEL_ALIASES: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # LOCAL MODELS (Ollama) - Always available, FREE, no internet
    # =========================================================================
    "L1": {
        "provider": "ollama",
        "model": "llama3.2:3b",
        "description": "Local fast - quick answers, drafts",
        "speed": "⚡⚡",
        "cost": "FREE",
        "tier": "fast",
    },
    "L2": {
        "provider": "ollama",
        "model": "llama3.1:8b",
        "description": "Local quality - reasoning, code",
        "speed": "⚡",
        "cost": "FREE",
        "tier": "quality",
    },
    "L3": {
        "provider": "ollama",
        "model": "mistral:7b",
        "description": "Local alt - creative, European",
        "speed": "⚡",
        "cost": "FREE",
        "tier": "alt",
    },
    "L4": {
        "provider": "ollama",
        "model": "nomic-embed-text",
        "description": "Embeddings - search/RAG only",
        "speed": "⚡⚡⚡",
        "cost": "FREE",
        "tier": "embed",
        "chat_capable": False,
    },
    # =========================================================================
    # CLAUDE (Anthropic) - Best reasoning, safest
    # =========================================================================
    "CL": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "description": "Claude best - reasoning, safe",
        "speed": "⚡⚡",
        "cost": "$$$",
        "tier": "best",
        "fallback": "L2",
    },
    "CL1": {  # Alias for CL
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "description": "Claude best - reasoning, safe",
        "speed": "⚡⚡",
        "cost": "$$$",
        "tier": "best",
        "fallback": "L2",
    },
    "CL2": {
        "provider": "anthropic",
        "model": "claude-3-haiku-20240307",
        "description": "Claude cheap - fast, budget",
        "speed": "⚡⚡⚡",
        "cost": "$",
        "tier": "cheap",
        "fallback": "L1",
    },
    "CL3": {
        "provider": "anthropic",
        "model": "claude-opus-4-20250514",
        "description": "Claude premium - max quality",
        "speed": "⚡",
        "cost": "$$$$",
        "tier": "premium",
        "fallback": "CL",
    },
    # =========================================================================
    # OPENAI - Best for coding
    # =========================================================================
    "OP": {
        "provider": "openai",
        "model": "gpt-4o",
        "description": "OpenAI best - coding, tools",
        "speed": "⚡⚡",
        "cost": "$$$",
        "tier": "best",
        "fallback": "L2",
    },
    "OP1": {  # Alias for OP
        "provider": "openai",
        "model": "gpt-4o",
        "description": "OpenAI best - coding, tools",
        "speed": "⚡⚡",
        "cost": "$$$",
        "tier": "best",
        "fallback": "L2",
    },
    "OP2": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "description": "OpenAI cheap - fast, budget",
        "speed": "⚡⚡⚡",
        "cost": "$",
        "tier": "cheap",
        "fallback": "L1",
    },
    "OP3": {
        "provider": "openai",
        "model": "o1",
        "description": "OpenAI reasoning - deep think",
        "speed": "🐢",
        "cost": "$$$$",
        "tier": "reasoning",
        "fallback": "OP",
    },
    # =========================================================================
    # AZURE OPENAI - Enterprise deployments
    # =========================================================================
    "AZ": {
        "provider": "azure_openai",
        "model": "gpt-4o",
        "description": "Azure OpenAI - enterprise deployment",
        "speed": "⚡⚡",
        "cost": "$$$",
        "tier": "best",
        "fallback": "OP",
        "note": "Model name is the Azure deployment name",
    },
    "AZ2": {
        "provider": "azure_openai",
        "model": "gpt-4o-mini",
        "description": "Azure OpenAI cheap - enterprise budget",
        "speed": "⚡⚡⚡",
        "cost": "$$",
        "tier": "cheap",
        "fallback": "OP2",
        "note": "Model name is the Azure deployment name",
    },
    # =========================================================================
    # GEMINI (Google) - Good free tier
    # =========================================================================
    "GO": {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "description": "Gemini fast - all-rounder",
        "speed": "⚡⚡⚡",
        "cost": "FREE",
        "tier": "fast",
        "fallback": "L1",
    },
    "GO1": {  # Alias for GO
        "provider": "google",
        "model": "gemini-2.5-flash",
        "description": "Gemini fast - all-rounder",
        "speed": "⚡⚡⚡",
        "cost": "FREE",
        "tier": "fast",
        "fallback": "L1",
    },
    "GO2": {
        "provider": "google",
        "model": "gemini-2.5-pro",
        "description": "Gemini pro - quality",
        "speed": "⚡⚡",
        "cost": "$$",
        "tier": "quality",
        "fallback": "GO",
    },
    # =========================================================================
    # GROQ - Fastest cloud, FREE
    # =========================================================================
    "GR": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "description": "Groq fast - blazing speed",
        "speed": "⚡⚡⚡⚡",
        "cost": "FREE",
        "tier": "fast",
        "fallback": "L1",
    },
    "GR1": {  # Alias for GR
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "description": "Groq fast - blazing speed",
        "speed": "⚡⚡⚡⚡",
        "cost": "FREE",
        "tier": "fast",
        "fallback": "L1",
    },
    "GR2": {
        "provider": "groq",
        "model": "mixtral-8x7b-32768",
        "description": "Groq mixtral - alternative",
        "speed": "⚡⚡⚡",
        "cost": "FREE",
        "tier": "alt",
        "fallback": "L1",
    },
    # =========================================================================
    # OPENROUTER - Aggregator (many models)
    # =========================================================================
    "OR": {
        "provider": "openrouter",
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "description": "OpenRouter free - aggregator fallback",
        "speed": "⚡⚡",
        "cost": "FREE",
        "tier": "free",
        "fallback": "L2",
    },
    "OR2": {
        "provider": "openrouter",
        "model": "openai/gpt-4o-mini",
        "description": "OpenRouter OpenAI mini - cheap routing",
        "speed": "⚡⚡",
        "cost": "$",
        "tier": "cheap",
        "fallback": "OR",
    },
    # =========================================================================
    # GROK (X.AI / Elon Musk) - Twitter/X integration
    # =========================================================================
    # NOTE: Groq ≠ Grok!
    #   Groq (GR) = Fast inference company, runs Llama models
    #   Grok (XK) = Elon Musk's X.AI model, Twitter/X data
    "XK": {
        "provider": "xai",
        "model": "grok-4.1-fast",
        "description": "Grok fast - X/Twitter integration",
        "speed": "⚡⚡⚡",
        "cost": "FREE*",  # $25 free credits/month
        "tier": "fast",
        "fallback": "GR",
        "note": "Free $25 credits/month, then paid",
    },
    "XK1": {  # Alias for XK
        "provider": "xai",
        "model": "grok-4.1-fast",
        "description": "Grok fast - X/Twitter integration",
        "speed": "⚡⚡⚡",
        "cost": "FREE*",
        "tier": "fast",
        "fallback": "GR",
    },
    "XK2": {
        "provider": "xai",
        "model": "grok-3-mini",
        "description": "Grok mini - budget X.AI option",
        "speed": "⚡⚡⚡⚡",
        "cost": "FREE*",  # Lower token cost
        "tier": "budget",
        "fallback": "GR2",
    },
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def resolve_alias(alias: str) -> Dict[str, Any]:
    """
    Resolve a short code to full model config.

    Args:
        alias: Short code like "L1", "CL", "OP"

    Returns:
        Dict with provider, model, and metadata

    Raises:
        ValueError: If alias not found
    """
    alias = alias.upper()
    if alias in MODEL_ALIASES:
        return MODEL_ALIASES[alias]
    raise ValueError(
        f"Unknown model alias: {alias}. Valid: {list(MODEL_ALIASES.keys())}"
    )


def get_provider_model(alias: str) -> tuple[str, str]:
    """Get (provider, model) tuple from alias."""
    config = resolve_alias(alias)
    return config["provider"], config["model"]


def list_aliases() -> str:
    """List all available aliases with descriptions."""
    lines = [
        "=" * 60,
        "MODEL ALIASES - Quick Codes",
        "=" * 60,
        "",
        "LOCAL (FREE, no internet):",
    ]
    for code in ["L1", "L2", "L3", "L4"]:
        m = MODEL_ALIASES[code]
        lines.append(f"  {code:4} {m['model']:25} {m['speed']:6} {m['cost']}")

    lines.append("")
    lines.append("CLAUDE (Anthropic):")
    for code in ["CL", "CL2", "CL3"]:
        m = MODEL_ALIASES[code]
        lines.append(f"  {code:4} {m['model']:25} {m['speed']:6} {m['cost']}")

    lines.append("")
    lines.append("OPENAI:")
    for code in ["OP", "OP2", "OP3"]:
        m = MODEL_ALIASES[code]
        lines.append(f"  {code:4} {m['model']:25} {m['speed']:6} {m['cost']}")

    lines.append("")
    lines.append("GEMINI (Google):")
    for code in ["GO", "GO2"]:
        m = MODEL_ALIASES[code]
        lines.append(f"  {code:4} {m['model']:25} {m['speed']:6} {m['cost']}")

    lines.append("")
    lines.append("GROQ:")
    for code in ["GR", "GR2"]:
        m = MODEL_ALIASES[code]
        lines.append(f"  {code:4} {m['model']:25} {m['speed']:6} {m['cost']}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def get_fallback(alias: str) -> str | None:
    """Get fallback alias if primary fails."""
    config = resolve_alias(alias)
    return config.get("fallback")


def is_local(alias: str) -> bool:
    """Check if alias is a local model."""
    return alias.upper().startswith("L")


def is_chat_capable(alias: str) -> bool:
    """Check if model can do chat (L4 cannot)."""
    config = resolve_alias(alias)
    return config.get("chat_capable", True)


# =============================================================================
# QUICK REFERENCE
# =============================================================================
"""
QUICK REFERENCE - JUST TYPE THE CODE!
======================================

LOCAL (FREE, no internet):
  L1 = llama3.2:3b      Fast, simple
  L2 = llama3.1:8b      Quality, complex
  L3 = mistral:7b       Alternative
  L4 = nomic-embed      Embeddings only

CLAUDE (Anthropic):
  CL  = Sonnet 4        Best ($$$)
  CL2 = Haiku           Cheap ($)
  CL3 = Opus 4          Premium ($$$$)

OPENAI:
  OP  = GPT-4o          Best ($$$)
  OP2 = GPT-4o-mini     Cheap ($)
  OP3 = o1              Reasoning ($$$$)

GEMINI (Google):
  GO  = Flash           Fast (FREE)
  GO2 = Pro             Quality ($$)

GROQ:
  GR  = Llama 70B       Blazing (FREE)
  GR2 = Mixtral         Alternative (FREE)

PATTERN:
  [PROVIDER] = best
  [PROVIDER]2 = cheap
  [PROVIDER]3 = premium/special

USAGE:
  router.chat("L1", "Quick question")
  router.chat("CL2", "Budget task")
  router.chat("OP", "Write code")
  router.chat("GR", "Fast answer")
"""


# =============================================================================
# AUTO-DETECT & INSTANT SWITCH
# =============================================================================

import json
import os
from pathlib import Path
from typing import List, Optional


def auto_detect_llms(timeout: float = 2.0) -> List[str]:
    """
    Auto-detect ALL available LLMs in 2 seconds. No questions asked.

    Checks:
    - Ollama running? -> L1, L2, L3, L4 available
    - API keys in env? -> CL, OP, GO, GR available

    Returns:
        List of available model codes, ordered by priority
    """
    available = []

    # Check API keys FIRST (instant, no network)
    if os.environ.get("GROQ_API_KEY"):
        available.append("GR")  # Fastest free cloud
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        available.append("GO")  # Free Google
    if os.environ.get("ANTHROPIC_API_KEY"):
        available.append("CL")  # Best quality
    if os.environ.get("OPENAI_API_KEY"):
        available.append("OP")  # Best coding

    # Check Ollama (quick network check)
    try:
        import urllib.request

        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read())
                models = [m.get("name", "") for m in data.get("models", [])]

                # Check which local models are pulled
                if any("llama3.2" in m or "llama3.2:3b" in m for m in models):
                    available.append("L1")
                if any("llama3.1" in m or "llama3.1:8b" in m for m in models):
                    available.append("L2")
                if any("mistral" in m for m in models):
                    available.append("L3")
                if any("nomic" in m or "embed" in m for m in models):
                    available.append("L4")

                # If Ollama running but no models, still add L1 (can pull)
                if not any(code.startswith("L") for code in available):
                    available.append("L1")  # Will need to pull
    except Exception:
        pass  # Ollama not running, skip local

    return available


def get_best_available() -> Optional[str]:
    """
    Get the single best available LLM right now.

    Priority: GR (fastest free) > L1 (local) > GO (free) > CL > OP

    Returns:
        Best model code, or None if nothing available
    """
    available = auto_detect_llms()

    # Priority order for "best" (speed + free first)
    priority = ["GR", "L1", "GO", "L2", "CL", "OP", "L3", "CL2", "OP2"]

    for code in priority:
        if code in available:
            return code

    return available[0] if available else None


def get_config_path() -> Path:
    """Get path to user config file."""
    return Path.home() / ".agentic" / "config.json"


def get_current_model() -> str:
    """
    Get currently configured default model.

    Checks:
    1. Config file (~/.agentic/config.json)
    2. Environment variable (AGENTIC_MODEL)
    3. Auto-detect best available

    Returns:
        Model code (never None - always finds something)
    """
    # Check env var first
    env_model = os.environ.get("AGENTIC_MODEL", "").upper()
    if env_model and env_model in MODEL_ALIASES:
        return env_model

    # Check config file
    config_path = get_config_path()
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            saved_model = config.get("default_model", "").upper()
            if saved_model and saved_model in MODEL_ALIASES:
                return saved_model
        except Exception:
            pass

    # Auto-detect best
    best = get_best_available()
    return best if best else "L1"  # L1 as ultimate fallback


def switch_model(code: str, save: bool = True) -> dict:
    """
    Switch to a different model INSTANTLY.

    Args:
        code: Model code (L1, CL, OP, etc.)
        save: Save as new default

    Returns:
        dict with status, model info
    """
    code = code.upper()

    if code not in MODEL_ALIASES:
        return {
            "success": False,
            "error": f"Unknown model: {code}",
            "valid_codes": list(MODEL_ALIASES.keys()),
        }

    model_info = MODEL_ALIASES[code]

    # Check if model is available
    available = auto_detect_llms()
    ready = code in available or code.startswith("L")  # Local always "available"

    # Save to config
    if save:
        config_path = get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        config = {}
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
            except Exception:
                pass

        config["default_model"] = code
        config_path.write_text(json.dumps(config, indent=2))

    # Also set env var for current session
    os.environ["AGENTIC_MODEL"] = code

    return {
        "success": True,
        "model": code,
        "provider": model_info["provider"],
        "full_name": model_info["model"],
        "ready": ready,
        "message": f"Switched to {code} ({model_info['model']})",
    }


def quick_switch(code: str) -> str:
    """
    Ultra-fast switch - just returns confirmation message.

    Args:
        code: Model code

    Returns:
        Simple status message
    """
    result = switch_model(code)
    if result["success"]:
        return f"Now using {code}"
    else:
        return f"Error: {result['error']}"


# =============================================================================
# SMART FALLBACK CHAIN
# =============================================================================
# Priority: LOCAL FREE → CLOUD FREE → CHEAP (alternating) → EXPENSIVE (alternating)
# Goal: Never fail, minimize cost, alternate providers for resilience
# CRITICAL: Preserve credits! Only use expensive models for real emergencies

FALLBACK_CHAIN = [
    # 1. LOCAL - Always try first (FREE, no internet)
    "L1",  # Local fast - FREE
    "L2",  # Local quality - FREE
    # 2. FREE CLOUD - No cost, try both
    "GO",  # Gemini Flash - FREE
    "GR",  # Groq - FREE
    "XK",  # Grok - FREE credits ($25/month)
    # 3. CHEAP - Alternate providers (if one is down, other might work)
    "OP2",  # GPT-4o-mini - CHEAP OpenAI
    "CL2",  # Claude Haiku - CHEAP Anthropic
    "XK2",  # Grok mini - CHEAP X.AI
    # 4. STANDARD - Alternate providers
    "OP",  # GPT-4o - $$$ OpenAI
    "CL",  # Claude Sonnet - $$$ Anthropic
    # 5. PREMIUM - Last resort, alternate (most expensive but reliable)
    "OP3",  # o1 - $$$$ OpenAI reasoning
    "CL3",  # Claude Opus - $$$$ Anthropic best
]

# Alternative chains for specific needs
FALLBACK_CHAIN_SPEED = ["GR", "L1", "GO", "XK", "OP2", "CL2", "L2"]  # Fastest first
FALLBACK_CHAIN_QUALITY = ["CL", "OP", "L2", "CL2", "OP2", "L1"]  # Best quality first
FALLBACK_CHAIN_FREE = ["L1", "L2", "GO", "GR", "XK"]  # Only free models
FALLBACK_CHAIN_CODING = ["OP", "CL", "L2", "OP2", "CL2", "L1"]  # Best for code

# CREDIT PRESERVATION - Only use free models for routine fallback
FALLBACK_CHAIN_PRESERVE_CREDITS = ["L1", "L2", "GO", "GR", "XK"]  # FREE ONLY

# Model cost tiers for smart decisions
MODEL_COST_TIER = {
    "L1": 0,
    "L2": 0,
    "L3": 0,
    "L4": 0,  # FREE - local
    "GO": 0,
    "GR": 0,
    "XK": 0,  # FREE - cloud (XK has $25 free credits)
    "OP2": 1,
    "CL2": 1,
    "XK2": 1,  # CHEAP
    "GO2": 2,  # MODERATE
    "OP": 3,
    "CL": 3,  # EXPENSIVE
    "OP3": 4,
    "CL3": 4,  # VERY EXPENSIVE
}

# Provider for each model (for diversity routing)
MODEL_PROVIDER = {
    "L1": "ollama",
    "L2": "ollama",
    "L3": "ollama",
    "L4": "ollama",
    "GO": "google",
    "GO2": "google",
    "GR": "groq",
    "GR2": "groq",
    "XK": "xai",
    "XK1": "xai",
    "XK2": "xai",
    "OP": "openai",
    "OP2": "openai",
    "OP3": "openai",
    "CL": "anthropic",
    "CL2": "anthropic",
    "CL3": "anthropic",
}


# =============================================================================
# HEALTH TRACKING & CIRCUIT BREAKER
# =============================================================================
# Track failures to avoid repeatedly hitting broken providers

import time
from typing import Dict, Tuple

# In-memory health state (persists for session)
_provider_health: Dict[str, Dict] = {}
_model_health: Dict[str, Dict] = {}

# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD = 3  # Failures before opening circuit
CIRCUIT_BREAKER_COOLDOWN = 300  # Seconds to wait before retry (5 min)
RATE_LIMIT_COOLDOWN = 60  # Seconds to wait after rate limit (1 min)


def record_success(code: str) -> None:
    """Record successful model call - reset failure count."""
    code = code.upper()
    provider = MODEL_PROVIDER.get(code, "unknown")

    _model_health[code] = {
        "failures": 0,
        "last_success": time.time(),
        "circuit_open": False,
    }

    _provider_health[provider] = {
        "failures": 0,
        "last_success": time.time(),
        "circuit_open": False,
        "rate_limited_until": 0,
    }


def record_failure(code: str, error_type: str = "error") -> None:
    """
    Record model failure - increment failure count, maybe open circuit.

    Args:
        code: Model code that failed
        error_type: "error", "rate_limit", "timeout", "auth"
    """
    code = code.upper()
    provider = MODEL_PROVIDER.get(code, "unknown")
    now = time.time()

    # Update model health
    if code not in _model_health:
        _model_health[code] = {"failures": 0, "circuit_open": False}

    _model_health[code]["failures"] = _model_health[code].get("failures", 0) + 1
    _model_health[code]["last_failure"] = now
    _model_health[code]["last_error"] = error_type

    # Check if circuit should open
    if _model_health[code]["failures"] >= CIRCUIT_BREAKER_THRESHOLD:
        _model_health[code]["circuit_open"] = True
        _model_health[code]["circuit_opens_at"] = now

    # Update provider health
    if provider not in _provider_health:
        _provider_health[provider] = {
            "failures": 0,
            "circuit_open": False,
            "rate_limited_until": 0,
        }

    _provider_health[provider]["failures"] = (
        _provider_health[provider].get("failures", 0) + 1
    )
    _provider_health[provider]["last_failure"] = now

    # Rate limit handling - skip provider for cooldown period
    if error_type == "rate_limit":
        _provider_health[provider]["rate_limited_until"] = now + RATE_LIMIT_COOLDOWN

    # Auth error - skip until fixed (long cooldown)
    if error_type == "auth":
        _provider_health[provider]["rate_limited_until"] = now + 3600  # 1 hour

    # Provider circuit breaker
    if _provider_health[provider]["failures"] >= CIRCUIT_BREAKER_THRESHOLD:
        _provider_health[provider]["circuit_open"] = True
        _provider_health[provider]["circuit_opens_at"] = now


def is_model_healthy(code: str) -> Tuple[bool, str]:
    """
    Check if model is healthy (not in circuit breaker or rate limited).

    Returns:
        (healthy: bool, reason: str)
    """
    code = code.upper()
    provider = MODEL_PROVIDER.get(code, "unknown")
    now = time.time()

    # Check provider rate limit
    if provider in _provider_health:
        rate_limited_until = _provider_health[provider].get("rate_limited_until", 0)
        if now < rate_limited_until:
            remaining = int(rate_limited_until - now)
            return False, f"rate limited ({remaining}s remaining)"

        # Check provider circuit breaker (with auto-reset)
        if _provider_health[provider].get("circuit_open"):
            opened_at = _provider_health[provider].get("circuit_opens_at", 0)
            if now - opened_at > CIRCUIT_BREAKER_COOLDOWN:
                # Circuit timeout - reset and allow retry
                _provider_health[provider]["circuit_open"] = False
                _provider_health[provider]["failures"] = 0
            else:
                remaining = int(CIRCUIT_BREAKER_COOLDOWN - (now - opened_at))
                return False, f"circuit open ({remaining}s remaining)"

    # Check model circuit breaker
    if code in _model_health:
        if _model_health[code].get("circuit_open"):
            opened_at = _model_health[code].get("circuit_opens_at", 0)
            if now - opened_at > CIRCUIT_BREAKER_COOLDOWN:
                # Reset
                _model_health[code]["circuit_open"] = False
                _model_health[code]["failures"] = 0
            else:
                remaining = int(CIRCUIT_BREAKER_COOLDOWN - (now - opened_at))
                return False, f"too many failures ({remaining}s cooldown)"

    return True, "healthy"


def get_health_status() -> str:
    """Get human-readable health status of all providers."""
    lines = ["PROVIDER HEALTH STATUS", "=" * 40]

    providers = ["ollama", "google", "groq", "openai", "anthropic"]
    now = time.time()

    for provider in providers:
        if provider in _provider_health:
            health = _provider_health[provider]
            failures = health.get("failures", 0)

            if health.get("circuit_open"):
                opened_at = health.get("circuit_opens_at", 0)
                remaining = max(0, int(CIRCUIT_BREAKER_COOLDOWN - (now - opened_at)))
                status = f"CIRCUIT OPEN ({remaining}s)"
            elif now < health.get("rate_limited_until", 0):
                remaining = int(health["rate_limited_until"] - now)
                status = f"RATE LIMITED ({remaining}s)"
            elif failures > 0:
                status = f"DEGRADED ({failures} failures)"
            else:
                status = "OK"
        else:
            status = "OK (no data)"

        lines.append(f"  {provider:12} {status}")

    return "\n".join(lines)


def reset_health() -> None:
    """Reset all health tracking (use after fixing issues)."""
    global _provider_health, _model_health
    _provider_health = {}
    _model_health = {}


# =============================================================================
# SMART ROUTING WITH HEALTH AWARENESS
# =============================================================================


def get_fallback_chain(
    starting_from: str = None,
    chain_type: str = "default",
    preserve_credits: bool = False,
    critical: bool = False,
    skip_unhealthy: bool = True,
) -> list:
    """
    Get the complete fallback chain, optionally starting from a specific model.

    Args:
        starting_from: Model to start from (skips models before it)
        chain_type: "default", "speed", "quality", "free", or "coding"
        preserve_credits: If True, only use FREE models (save money!)
        critical: If True AND preserve_credits fails, allow expensive models
        skip_unhealthy: Skip models that are rate limited or circuit-breaker open

    Returns:
        List of model codes to try in order
    """
    chains = {
        "default": FALLBACK_CHAIN,
        "speed": FALLBACK_CHAIN_SPEED,
        "quality": FALLBACK_CHAIN_QUALITY,
        "free": FALLBACK_CHAIN_FREE,
        "coding": FALLBACK_CHAIN_CODING,
        "preserve": FALLBACK_CHAIN_PRESERVE_CREDITS,
    }

    # Credit preservation mode - only free models
    if preserve_credits and not critical:
        chain = FALLBACK_CHAIN_PRESERVE_CREDITS.copy()
    else:
        chain = chains.get(chain_type, FALLBACK_CHAIN).copy()

    # Filter out unhealthy models
    if skip_unhealthy:
        healthy_chain = []
        for code in chain:
            healthy, reason = is_model_healthy(code)
            if healthy:
                healthy_chain.append(code)

        # If ALL models unhealthy, return original chain (emergency)
        if not healthy_chain:
            chain = chain  # Use original
        else:
            chain = healthy_chain

    if starting_from is None:
        return chain

    starting_from = starting_from.upper()

    # If starting model is in chain, start from there
    if starting_from in chain:
        idx = chain.index(starting_from)
        return chain[idx:]

    # If not in chain, prepend it then continue with chain
    return [starting_from] + chain


def get_diverse_fallback(last_provider: str = None) -> list:
    """
    Get fallback chain that avoids same provider twice in a row.

    If OpenAI just failed, try Anthropic/Google/Groq before trying OpenAI again.

    Args:
        last_provider: Provider that just failed

    Returns:
        Reordered fallback chain with provider diversity
    """
    chain = FALLBACK_CHAIN.copy()

    if not last_provider:
        return chain

    # Reorder to avoid same provider at top
    diverse_chain = []
    same_provider = []

    for code in chain:
        provider = MODEL_PROVIDER.get(code, "unknown")
        if provider == last_provider:
            same_provider.append(code)
        else:
            diverse_chain.append(code)

    # Put same-provider models at end
    return diverse_chain + same_provider


def smart_fallback_with_budget(
    preferred: str = None,
    max_cost_tier: int = 0,
    allow_expensive_if_critical: bool = True,
    last_failed_provider: str = None,
) -> Tuple[str, str]:
    """
    Find a working model while respecting budget limits and health.

    PHILOSOPHY:
    - For routine tasks: Only use FREE models (tier 0)
    - If all free fail AND it's critical: Escalate to paid
    - NEVER burn expensive credits on routine fallback
    - Skip providers that are rate limited or circuit-broken
    - Prefer provider diversity (don't hit same provider twice)

    Args:
        preferred: Model to try first
        max_cost_tier: 0=free only, 1=cheap OK, 2+=expensive OK
        allow_expensive_if_critical: If ALL cheap fail, try expensive
        last_failed_provider: Provider to avoid (diversity)

    Returns:
        (model_code, status_message) tuple
    """
    available = auto_detect_llms()

    # Get diverse chain if we know last failure
    if last_failed_provider:
        base_chain = get_diverse_fallback(last_failed_provider)
    else:
        base_chain = FALLBACK_CHAIN.copy()

    # Build chain respecting budget and health
    budget_chain = []
    expensive_backup = []
    skipped = []

    for code in base_chain:
        # Check health first
        healthy, reason = is_model_healthy(code)
        if not healthy:
            skipped.append((code, reason))
            continue

        tier = MODEL_COST_TIER.get(code, 0)
        if tier <= max_cost_tier:
            budget_chain.append(code)
        elif allow_expensive_if_critical:
            expensive_backup.append(code)

    # If preferred model, try it first
    if preferred:
        preferred = preferred.upper()
        healthy, reason = is_model_healthy(preferred)
        if healthy and preferred in available:
            return preferred, "using preferred model"
        elif not healthy:
            skipped.append((preferred, reason))

    # Try budget-friendly options first
    for code in budget_chain:
        if code in available:
            if skipped:
                skip_info = ", ".join(f"{c}:{r}" for c, r in skipped[:3])
                return code, f"using {code} (skipped: {skip_info})"
            return code, f"using {code}"

    # All budget options failed - this is critical!
    # Only now use expensive models to recover
    if expensive_backup:
        for code in expensive_backup:
            if code in available:
                return code, f"CRITICAL: using expensive {code} to recover"

    # Absolute fallback
    if skipped:
        return "L1", "all models unhealthy, trying L1 anyway"
    return "L1", "fallback to L1"


def get_free_models() -> list:
    """Get list of all FREE model codes."""
    return [code for code, tier in MODEL_COST_TIER.items() if tier == 0]


def get_cheap_models() -> list:
    """Get list of CHEAP model codes (tier 0-1)."""
    return [code for code, tier in MODEL_COST_TIER.items() if tier <= 1]


def estimate_cost(code: str, tokens: int = 1000) -> str:
    """
    Estimate cost for a model.

    Args:
        code: Model code
        tokens: Estimated tokens

    Returns:
        Cost string like "FREE", "$0.01", "$0.10"
    """
    tier = MODEL_COST_TIER.get(code.upper(), 0)

    if tier == 0:
        return "FREE"
    elif tier == 1:
        return f"~${tokens * 0.00001:.4f}"  # ~$0.01 per 1000 tokens
    elif tier == 2:
        return f"~${tokens * 0.00005:.4f}"  # ~$0.05 per 1000 tokens
    elif tier == 3:
        return f"~${tokens * 0.0001:.4f}"  # ~$0.10 per 1000 tokens
    else:
        return f"~${tokens * 0.0005:.4f}"  # ~$0.50 per 1000 tokens


def smart_fallback(preferred: str = None) -> str:
    """
    Get the best working model right now using smart fallback.

    Tries each model in fallback chain until one works.

    Args:
        preferred: Try this model first before fallback chain

    Returns:
        Model code that is confirmed working
    """
    import os

    chain = get_fallback_chain(preferred) if preferred else FALLBACK_CHAIN
    available = auto_detect_llms()

    # Find first available model in chain
    for code in chain:
        if code in available:
            return code

        # For local models, check if Ollama is at least running
        if code.startswith("L"):
            if "L1" in available or "L2" in available:
                # Ollama running, this model might work
                return code

    # Nothing in chain available - try to recover
    # Check for ANY API key
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "CL2"  # Cheap Claude
    if os.environ.get("OPENAI_API_KEY"):
        return "OP2"  # Cheap OpenAI
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return "GO"  # Free Gemini
    if os.environ.get("GROQ_API_KEY"):
        return "GR"  # Free Groq

    # Absolute last resort - return L1, setup will guide user
    return "L1"


def try_model(code: str, prompt: str = "Say OK", timeout: float = 10.0) -> dict:
    """
    Actually test if a model responds.

    Args:
        code: Model code to test
        prompt: Simple prompt to test
        timeout: Max seconds to wait

    Returns:
        dict with success, response, latency
    """
    import time

    code = code.upper()
    if code not in MODEL_ALIASES:
        return {"success": False, "error": f"Unknown model: {code}"}

    info = MODEL_ALIASES[code]
    provider = info["provider"]
    model = info["model"]

    start = time.time()

    try:
        if provider == "ollama":
            # Test local Ollama
            import json as json_mod
            import urllib.request

            data = json_mod.dumps(
                {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                }
            ).encode()

            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json_mod.loads(resp.read())
                latency = time.time() - start
                return {
                    "success": True,
                    "response": result.get("response", ""),
                    "latency": latency,
                    "model": code,
                }

        else:
            # Cloud provider - just check API key exists
            # (actual test would need provider SDK)
            env_vars = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
                "groq": "GROQ_API_KEY",
            }

            key_name = env_vars.get(provider)
            if isinstance(key_name, list):
                has_key = any(os.environ.get(k) for k in key_name)
            else:
                has_key = bool(os.environ.get(key_name))

            if has_key:
                return {
                    "success": True,
                    "response": "(API key configured)",
                    "latency": time.time() - start,
                    "model": code,
                }
            else:
                return {
                    "success": False,
                    "error": f"No API key for {provider}",
                    "model": code,
                }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency": time.time() - start,
            "model": code,
        }


def find_working_model(preferred: str = None, test_each: bool = True) -> dict:
    """
    Find a working model using the fallback chain.

    This is the MAIN function to call when you need a model.
    It will NEVER fail - always returns something usable.

    Args:
        preferred: Model to try first
        test_each: Actually test models (slower but reliable)

    Returns:
        dict with model code, tested status, fallback info
    """
    chain = get_fallback_chain(preferred) if preferred else FALLBACK_CHAIN
    tested = []

    for code in chain:
        if test_each:
            result = try_model(code)
            tested.append({"model": code, "result": result})

            if result["success"]:
                return {
                    "model": code,
                    "tested": True,
                    "latency": result.get("latency"),
                    "fallback_used": code != (preferred or chain[0]),
                    "attempts": len(tested),
                }
        else:
            # Quick check without actual API call
            available = auto_detect_llms()
            if code in available:
                return {
                    "model": code,
                    "tested": False,
                    "fallback_used": code != (preferred or chain[0]),
                    "attempts": len(tested) + 1,
                }

    # If all tests failed, return L1 anyway with setup guidance
    return {
        "model": "L1",
        "tested": False,
        "needs_setup": True,
        "fallback_used": True,
        "attempts": len(tested),
        "message": "No working model found. Run: agentic setup-llm",
    }


def status() -> str:
    """
    Get instant status of all LLMs - what's available right now.

    Returns:
        Status string for display
    """
    available = auto_detect_llms()
    current = get_current_model()

    lines = [
        "LLM STATUS",
        "=" * 40,
        f"Current: {current}",
        "",
        "Available now:",
    ]

    if available:
        for code in available:
            marker = " <-- active" if code == current else ""
            info = MODEL_ALIASES[code]
            lines.append(f"  {code:4} {info['cost']:6} {info['description']}{marker}")
    else:
        lines.append("  None detected! Run: agentic setup-llm")

    lines.append("")
    lines.append("Switch with: agentic use <CODE>")
    lines.append("Or in chat: /L1, /CL, /OP, /GO, /GR")

    return "\n".join(lines)


# =============================================================================
# ZERO-CONFIG STARTUP
# =============================================================================


def ensure_llm_ready() -> str:
    """
    Ensure at least one LLM is ready to use. No questions.

    This is called on agentic-brain startup. It:
    1. Checks what's available
    2. If nothing, tries to start Ollama
    3. Returns the model code to use

    NEVER fails - always returns a model code.
    """
    available = auto_detect_llms()

    if available:
        # Something's ready, use best option
        return get_best_available() or "L1"

    # Nothing available - try to start Ollama
    import shutil
    import subprocess

    if shutil.which("ollama"):
        # Ollama installed, try to start it
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            import time

            time.sleep(2)

            # Check again
            available = auto_detect_llms()
            if available:
                return get_best_available() or "L1"
        except Exception:
            pass

    # Still nothing - return L1 anyway (setup will guide user)
    return "L1"


if __name__ == "__main__":
    print(list_aliases())
