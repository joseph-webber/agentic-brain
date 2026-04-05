#!/usr/bin/env python3
"""
🌐 BRAIN OPENROUTER MCP SERVER (FastMCP version)
=================================================

MCP server for AI model routing, switching, and management.

⚠️ IMPORTANT: This is for AUXILIARY tasks only!
   - Does NOT replace Claude/Copilot (the main AI)
   - Only used for: fallback, simple tasks, offline work
   - Never interferes with the primary AI session
   - Default is ALWAYS Claude/Copilot

Tools:
- openrouter_status: Get full system status
- openrouter_models: List all available models
- openrouter_route: Find best model for a task
- openrouter_switch: Switch to a different model
- openrouter_compare: Compare models
- openrouter_health: Check model health
- openrouter_recommend: Get recommendations for a task
- openrouter_chat: Send message to a model
- openrouter_discover_free: Discover free LLM providers

SMART ROUTING (NEW!):
- openrouter_smart_route: 🧠 Auto-routes to best provider (Groq → Local → Cloud)
- openrouter_cascade: 🔄 Cascading fallback - tries all providers until success

FALLBACK & QUOTA:
- openrouter_smart_fallback: Get best model when Claude is down
- openrouter_ask_local: Quick local LLM query (uses HTTP API - fast!)
- openrouter_quick_local: Ultra-fast local query (llama3.2:3b)

Voice-Specific Tools:
- openrouter_voice_response: Get LLM response formatted for voice
- openrouter_lady_chat: Chat as a specific lady with personality
- openrouter_conversation_mode: Start continuous conversation mode

Ladies (personalities) - PRIVATE BRAIN ONLY:
- Karen, Moira, Tingting, Damayanti, Shelley, etc.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict

sys.path.insert(0, os.path.expanduser("~/brain"))

from mcp.server.fastmcp import FastMCP

# Import Redis reasoning system (lazy loaded)
try:
    from redis_reasoning import get_redis_reasoning

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️  Redis reasoning not available - caching disabled")

mcp = FastMCP("openrouter")

# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK CACHE (to avoid redundant API calls)
# ═══════════════════════════════════════════════════════════════
_health_cache = {"data": None, "timestamp": 0}
_CACHE_TTL = 5  # Cache health check for 5 seconds

# ═══════════════════════════════════════════════════════════════
# REDIS REASONING SYSTEM (shared cache & reasoning)
# ═══════════════════════════════════════════════════════════════
_redis = None


def get_redis():
    """Get Redis reasoning instance (lazy initialized)."""
    global _redis
    if _redis is None and REDIS_AVAILABLE:
        try:
            _redis = get_redis_reasoning()
            # Test connection
            health = _redis.health_check()
            if not health.get("connected"):
                print("⚠️  Redis not connected - caching disabled")
                _redis = None
        except Exception as e:
            print(f"⚠️  Redis initialization failed: {e}")
            _redis = None
    return _redis


# ═══════════════════════════════════════════════════════════════
# MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════

MODELS = {
    # JIRA AI / ROVO - Enterprise AI)
    "rovo": {
        "provider": "atlassian",
        "params": "cloud",
        "context": 200000,
        "speed": "medium",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": [
            "citb",
            "jira",
            "confluence",
            "bitbucket",
            "tickets",
            "documentation",
            "prs",
        ],
        "description": "Atlassian Rovo AI - FREE for CITB! Searches JIRA+Confluence+Bitbucket",
        "note": "Uses Safari automation - must be logged into CITB JIRA",
    },
    # LOCAL MODELS
    "claude-emulator": {
        "provider": "ollama",
        "params": "8B",
        "context": 131072,
        "speed": "medium",
        "cost": 0,
        "offline": True,
        "strengths": ["recovery", "joseph-context", "brain-knowledge", "accessibility"],
        "description": "Your trained recovery specialist - knows your context",
    },
    "llama3.1:8b": {
        "provider": "ollama",
        "params": "8B",
        "context": 131072,
        "speed": "medium",
        "cost": 0,
        "offline": True,
        "strengths": ["general", "coding", "reasoning"],
        "description": "Good general-purpose local model",
    },
    "llama3.2:3b": {
        "provider": "ollama",
        "params": "3B",
        "context": 131072,
        "speed": "fast",
        "cost": 0,
        "offline": True,
        "strengths": ["quick-tasks", "simple-queries"],
        "description": "Fast local model for quick tasks",
    },
    # FREE CLOUD MODELS
    "llama-3.3-70b-versatile": {
        "provider": "groq",
        "params": "70B",
        "context": 131072,
        "speed": "ultra-fast",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": ["speed", "general", "coding", "reasoning", "quality"],
        "description": "Groq 70B quality model at ~500 tokens/sec",
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "priority": 1,
        "tokens_per_second": 500,
        "api_model": "llama-3.3-70b-versatile",
        "rate_limit": "30/min",
    },
    "llama-3.1-8b-instant": {
        "provider": "groq",
        "params": "8B",
        "context": 131072,
        "speed": "ultra-fast",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": ["quick", "general", "speed"],
        "description": "Groq fastest model at ~500 tokens/sec",
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "priority": 1,
        "tokens_per_second": 500,
        "api_model": "llama-3.1-8b-instant",
    },
    "mixtral-8x7b-32768": {
        "provider": "groq",
        "params": "8x7B",
        "context": 32768,
        "speed": "ultra-fast",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": ["general", "reasoning", "long-context"],
        "description": "Groq Mixtral model with 32k context",
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "priority": 1,
        "tokens_per_second": 500,
        "api_model": "mixtral-8x7b-32768",
    },
    "together-llama-70b": {
        "provider": "together",
        "params": "70B",
        "context": 131072,
        "speed": "fast",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": ["quality", "coding", "reasoning"],
        "description": "FREE 70B with $25 credit on signup",
        "key_env": "TOGETHER_API_KEY",
    },
    "openrouter-free": {
        "provider": "openrouter",
        "params": "8B",
        "context": 131072,
        "speed": "medium",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": ["general", "fallback"],
        "description": "OpenRouter free tier models",
        "key_env": "OPENROUTER_API_KEY",
    },
    "cloudflare-llama": {
        "provider": "cloudflare",
        "params": "8B",
        "context": 4096,
        "speed": "fast",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": ["always-free", "edge"],
        "description": "Cloudflare Workers AI - always free tier",
        "key_env": "CF_API_TOKEN",
    },
    "huggingface": {
        "provider": "huggingface",
        "params": "varies",
        "context": 4096,
        "speed": "medium",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": ["open-source", "free-inference"],
        "description": "HuggingFace Inference API - FREE with HF_TOKEN",
        "key_env": "HF_TOKEN",
        "rate_limit": "unlimited-free-tier",
    },
    # PAID CLOUD MODELS
    "claude-opus": {
        "provider": "anthropic",
        "params": "175B+",
        "context": 200000,
        "speed": "medium",
        "cost": 0.015,
        "offline": False,
        "strengths": ["complex-reasoning", "long-docs", "coding", "analysis"],
        "description": "Most capable Claude - best for complex tasks",
    },
    "claude-sonnet": {
        "provider": "anthropic",
        "params": "70B+",
        "context": 200000,
        "speed": "fast",
        "cost": 0.003,
        "offline": False,
        "strengths": ["balanced", "coding", "general"],
        "description": "Balanced Claude - fast and capable",
    },
    "gpt-4o": {
        "provider": "openai",
        "params": "200B+",
        "context": 128000,
        "speed": "fast",
        "cost": 0.005,
        "offline": False,
        "strengths": ["multimodal", "coding", "general"],
        "description": "OpenAI's multimodal model",
    },
    "copilot": {
        "provider": "github",
        "params": "varies",
        "context": 64000,
        "speed": "fast",
        "cost": 0,
        "offline": False,
        "strengths": ["coding", "terminal", "git"],
        "description": "GitHub Copilot - great for terminal work",
    },
}

# CASCADE FALLBACK CHAIN - OPTIMIZED FOR SPEED AND RELIABILITY
# Priority: Speed → Quality → Reliability → Always Available
FALLBACK_CHAIN = [
    # SPEED TIER (Groq - ultra-fast at 500 tok/s)
    "llama-3.1-8b-instant",  # Fastest - 500 tok/s, simple tasks
    "llama-3.3-70b-versatile",  # Fast + quality - 500 tok/s, complex tasks
    "mixtral-8x7b-32768",  # Fast + long context
    # RELIABILITY TIER (Local - always available)
    "llama3.2:3b",  # Local fast - instant startup
    "claude-emulator",  # Local trained - knows user's context
    "llama3.1:8b",  # Local quality
    # CLOUD BACKUP TIER (if Groq down)
    "together-llama-70b",  # Free cloud alternative
    "openrouter-free",  # OpenRouter free models
    "huggingface",  # HuggingFace free
    "cloudflare-llama",  # Cloudflare edge
    # SPECIAL PURPOSE
    "rovo",  # CITB work only - must be logged in
]

TASK_ROUTING = {
    # SPEED TASKS - Groq first (500 tok/s!)
    "quick": ["llama-3.1-8b-instant", "llama3.2:3b", "mixtral-8x7b-32768"],
    "status": ["llama-3.1-8b-instant", "llama3.2:3b"],
    "simple": ["llama-3.1-8b-instant", "llama3.2:3b", "claude-emulator"],
    # QUALITY TASKS - Groq 70B first, then local
    "coding": [
        "llama-3.3-70b-versatile",
        "llama3.1:8b",
        "claude-sonnet",
        "copilot",
        "together-llama-70b",
    ],
    "complex": [
        "llama-3.3-70b-versatile",
        "together-llama-70b",
        "claude-opus",
        "claude-sonnet",
    ],
    "reasoning": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "claude-sonnet"],
    "general": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama3.1:8b",
        "claude-sonnet",
    ],
    # CITB-specific tasks - Rovo is FREE and best for these!
    "citb": ["rovo", "claude-emulator", "claude-sonnet"],
    "jira": ["rovo", "claude-emulator", "claude-sonnet"],
    "tickets": ["rovo", "claude-emulator", "claude-sonnet"],
    "confluence": ["rovo", "claude-sonnet"],
    "bitbucket": ["rovo", "copilot", "claude-sonnet"],
    "prs": ["rovo", "copilot", "claude-sonnet"],
    "documentation": ["rovo", "claude-sonnet"],
    "steve": ["rovo", "claude-emulator"],  # Steve tracking via Rovo
    "tuition": ["rovo", "claude-emulator"],  # Tuition claims
    "talas": ["rovo", "claude-emulator"],  # TALAS system
    # Special cases
    "recovery": ["claude-emulator"],
    "brain-repair": ["claude-emulator"],
    "offline": ["claude-emulator", "llama3.1:8b", "llama3.2:3b"],
    "accessibility": ["claude-emulator"],
    "private": ["claude-emulator", "llama3.1:8b", "llama3.2:3b"],
    "free": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "together-llama-70b",
        "openrouter-free",
        "huggingface",
        "cloudflare-llama",
    ],
    "free-fast": [
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "llama-3.3-70b-versatile",
    ],
}


def check_health() -> Dict[str, Any]:
    """Check system and model health - with 5 second cache to avoid redundant API calls"""
    global _health_cache

    # Return cached result if still valid
    current_time = time.time()
    if _health_cache["data"] and (
        current_time - _health_cache["timestamp"] < _CACHE_TTL
    ):
        return _health_cache["data"]

    health = {"internet": False, "ollama": False, "claude_desktop": False, "models": {}}

    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", "8.8.8.8"], capture_output=True, timeout=3
        )
        health["internet"] = result.returncode == 0
    except:
        pass

    try:
        result = subprocess.run(
            ["curl", "-s", "-m", "2", "http://localhost:11434/api/tags"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            health["ollama"] = True
            data = json.loads(result.stdout)
            ollama_models = [m["name"] for m in data.get("models", [])]
            for name in MODELS:
                if MODELS[name]["provider"] == "ollama":
                    health["models"][name] = any(
                        name.split(":")[0] in m for m in ollama_models
                    )
        else:
            # Ollama not running - try to start it
            try:
                import subprocess

                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,  # Detach so it runs independently
                )
                # Wait a moment for Ollama to start, then retry once
                time.sleep(2)
                result = subprocess.run(
                    ["curl", "-s", "-m", "2", "http://localhost:11434/api/tags"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if result.returncode == 0:
                    health["ollama"] = True
                    data = json.loads(result.stdout)
                    ollama_models = [m["name"] for m in data.get("models", [])]
                    for name in MODELS:
                        if MODELS[name]["provider"] == "ollama":
                            health["models"][name] = any(
                                name.split(":")[0] in m for m in ollama_models
                            )
            except:
                pass
    except:
        pass

    try:
        result = subprocess.run(
            ["pgrep", "-f", "Claude"], capture_output=True, timeout=2
        )
        health["claude_desktop"] = result.returncode == 0
    except:
        pass

    for name, info in MODELS.items():
        if not info["offline"]:
            required_key = info.get("key_env")
            has_key = True if not required_key else bool(os.environ.get(required_key))
            health["models"][name] = health["internet"] and has_key

    # Cache the result
    _health_cache["data"] = health
    _health_cache["timestamp"] = time.time()

    return health


def route_to_model(task: str, prefer_offline: bool = False) -> str:
    """Route to best model for task"""
    health = check_health()
    candidates = TASK_ROUTING.get(task, TASK_ROUTING["general"])

    for model in candidates:
        if health["models"].get(model, False):
            if prefer_offline and not MODELS[model].get("offline"):
                continue
            return model

    for model, info in MODELS.items():
        if info["offline"] and health["models"].get(model, False):
            return model

    return "claude-emulator"


def call_groq_api(prompt: str, model: str, timeout: int = 60) -> Dict[str, Any]:
    """Call Groq's OpenAI-compatible chat completions API."""
    info = MODELS.get(model, {})
    api_key = os.environ.get(info.get("key_env", "GROQ_API_KEY"))
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")

    base_url = info.get("base_url", "https://api.groq.com/openai/v1").rstrip("/")
    api_model = info.get("api_model", model)

    payload = {
        "model": api_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    start = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq API error {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Groq connection error: {e.reason}") from e

    elapsed = time.time() - start
    content = body["choices"][0]["message"]["content"].strip()
    usage = body.get("usage", {})

    return {
        "content": content,
        "elapsed": elapsed,
        "usage": usage,
        "api_model": api_model,
    }


@mcp.tool()
def openrouter_status() -> str:
    """Get full OpenRouter system status - shows internet, Ollama, Claude Desktop, and all model availability"""
    health = check_health()

    lines = [
        "🌐 OPENROUTER STATUS",
        "═" * 50,
        "",
        "📡 SERVICES",
        f"  Internet: {'✅ Connected' if health['internet'] else '❌ Offline'}",
        f"  Ollama: {'✅ Running' if health['ollama'] else '❌ Not running'}",
        f"  Claude Desktop: {'✅ Running' if health['claude_desktop'] else '⚠️ Not running'}",
        "",
        "🤖 LOCAL MODELS (Offline Capable)",
    ]

    for name, info in MODELS.items():
        if info["offline"]:
            status = "✅" if health["models"].get(name) else "❌"
            lines.append(
                f"  {status} {name} ({info['params']}) - {info['description']}"
            )

    lines.extend(["", "☁️ CLOUD MODELS"])
    for name, info in MODELS.items():
        if not info["offline"]:
            status = "✅" if health["models"].get(name) else "❌"
            lines.append(
                f"  {status} {name} ({info['params']}) - {info['description']}"
            )

    return "\n".join(lines)


@mcp.tool()
def openrouter_models() -> str:
    """List all available AI models with details (params, cost, speed, strengths)"""
    health = check_health()
    lines = [
        "📋 ALL MODELS",
        "═" * 60,
        "",
        f"{'Model':<20} {'Params':<8} {'Speed':<8} {'Cost':<8} {'Status':<8}",
        "─" * 60,
    ]

    for model_name, info in MODELS.items():
        status = "✅" if health["models"].get(model_name) else "❌"
        cost = "FREE" if info["cost"] == 0 else f"${info['cost']}"
        lines.append(
            f"{model_name:<20} {info['params']:<8} {info['speed']:<8} {cost:<8} {status}"
        )

    return "\n".join(lines)


@mcp.tool()
def openrouter_route(task: str, prefer_offline: bool = False) -> str:
    """Find the best available model for a specific task. Tasks: coding, complex, quick, recovery, private, general, free, free-fast"""
    model = route_to_model(task, prefer_offline)
    info = MODELS.get(model, {})

    return f"""🎯 ROUTING RESULT

Task: {task}
Best Model: {model}
Provider: {info.get('provider', 'unknown')}
Params: {info.get('params', 'unknown')}
Offline: {'Yes' if info.get('offline') else 'No'}
Cost: {'FREE' if info.get('cost', 0) == 0 else f"${info.get('cost')}"}

To use: openrouter_switch(model="{model}")"""


@mcp.tool()
def openrouter_switch(model: str) -> str:
    """Switch to a different AI model (opens Claude Desktop, starts Ollama model, etc)"""
    if model in ["claude", "claude-desktop"]:
        subprocess.Popen(["open", "-a", "Claude"])
        return "🚀 Opening Claude Desktop...\n\nClaude Desktop is starting."

    elif model == "copilot":
        return "🚀 To use Copilot CLI:\n\n```bash\ncopilot\n```\n\nRun this in your terminal."

    elif model in MODELS and MODELS[model].get("provider") == "groq":
        return f"""🚀 To use {model} via Groq:

Base URL: https://api.groq.com/openai/v1
Auth: Bearer token from GROQ_API_KEY

Or call directly with:
openrouter_chat(prompt="...", model="{model}")"""

    elif model in MODELS or any(model in m for m in MODELS):
        return f"""🚀 To use {model}:

```bash
ollama run {model}
```

Or use the robot command: `robot`

This model is LOCAL and works OFFLINE."""

    return f"❌ Unknown model: {model}\n\nAvailable: " + ", ".join(MODELS.keys())


@mcp.tool()
def openrouter_compare() -> str:
    """Compare AI models side by side - shows params, cost, speed, and best use cases"""
    return """⚖️ MODEL COMPARISON
═══════════════════════════════════════════════════════════════════

LOCAL MODELS (Always Available, FREE, Private)
──────────────────────────────────────────────────────────────────
Model              Params   Speed    Best For
──────────────────────────────────────────────────────────────────
claude-emulator    8B       Medium   Recovery, your context, accessibility
llama3.1:8b        8B       Medium   General tasks, coding
llama3.2:3b        3B       Fast     Quick queries, simple tasks

CLOUD MODELS (Require Internet)
──────────────────────────────────────────────────────────────────
Model              Params   Speed    Cost        Best For
──────────────────────────────────────────────────────────────────
llama-3.1-8b-instant 8B      Ultra    FREE        Fastest Groq model, quick tasks
llama-3.3-70b-versatile 70B  Ultra    FREE        Quality + speed on Groq
mixtral-8x7b-32768  8x7B     Ultra    FREE        Fast MoE with 32k context
claude-opus        175B+    Medium   $0.015/1K   Complex reasoning, analysis
claude-sonnet      70B+     Fast     $0.003/1K   Balanced, coding
gpt-4o             200B+    Fast     $0.005/1K   Multimodal
copilot            varies   Fast     FREE*       Terminal, git, coding

* Copilot included with GitHub subscription

💡 RECOMMENDATIONS
──────────────────
• Offline/Private → claude-emulator (trained for YOU)
• Speed needed → llama-3.1-8b-instant or llama-3.3-70b-versatile
• Complex task → llama-3.3-70b-versatile or claude-opus
• Coding → llama-3.3-70b-versatile, copilot, or claude-sonnet
• Recovery → claude-emulator"""


@mcp.tool()
def openrouter_health() -> str:
    """Quick health check of all services and models"""
    health = check_health()

    lines = ["🏥 HEALTH CHECK", ""]
    lines.append(f"Internet: {'✅' if health['internet'] else '❌'}")
    lines.append(f"Ollama: {'✅' if health['ollama'] else '❌'}")
    lines.append(f"Claude Desktop: {'✅' if health['claude_desktop'] else '❌'}")
    lines.append("")

    available = [m for m, ok in health["models"].items() if ok]
    unavailable = [m for m, ok in health["models"].items() if not ok]

    lines.append(f"Available Models ({len(available)}): {', '.join(available)}")
    if unavailable:
        lines.append(f"Unavailable ({len(unavailable)}): {', '.join(unavailable)}")

    return "\n".join(lines)


@mcp.tool()
def openrouter_recommend(task: str) -> str:
    """Get ranked recommendations for a specific task"""
    health = check_health()
    candidates = TASK_ROUTING.get(task, TASK_ROUTING["general"])

    lines = [f"🎯 RECOMMENDATIONS FOR: {task}", "═" * 40, ""]

    for i, model in enumerate(candidates[:5], 1):
        info = MODELS.get(model, {})
        available = "✅" if health["models"].get(model) else "❌"
        medal = ["🥇", "🥈", "🥉", "4.", "5."][i - 1]
        cost = "FREE" if info.get("cost", 0) == 0 else f"${info.get('cost')}"
        lines.append(
            f"{medal} {model} ({info.get('params', '?')}) - {cost} {available}"
        )
        lines.append(f"   └─ {info.get('description', '')}")

    best = route_to_model(task)
    lines.extend(["", f"➡️ Current best available: {best}"])

    return "\n".join(lines)


@mcp.tool()
def openrouter_chat(prompt: str, model: str = None, task: str = "general") -> str:
    """Send a message to a specific model and get response"""
    if not model:
        model = route_to_model(task)

    info = MODELS.get(model, {})

    # Special handling for Rovo (Atlassian Intelligence)
    if model == "rovo" or info.get("provider") == "atlassian":
        try:
            sys.path.insert(0, os.path.expanduser("~/brain"))
            from tools.jira_ai_query import RovoChat

            rovo = RovoChat()
            result = rovo.search(prompt)

            response = result.get("response", "No response from Rovo")
            if result.get("error"):
                response = f"Error: {result['error']}"

            return f"""🤖 Response from Rovo (Atlassian Intelligence)
═══════════════════════════════════════

{response}

───────────────────────────────────────
🏢 Searched: JIRA + Confluence + Bitbucket | 💰 FREE (CITB work)"""
        except Exception as e:
            return f"❌ Rovo error: {str(e)}\n\nMake sure Safari is logged into citb.atlassian.net"

    if info.get("provider") == "groq":
        try:
            result = call_groq_api(prompt, model)
            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens", "?")
            return f"""🤖 Response from {model}
═══════════════════════════════════════

{result["content"]}

───────────────────────────────────────
⏱️ {result["elapsed"]:.1f}s | 📦 {info.get('params', '?')} params | ⚡ ~{info.get('tokens_per_second', '?')} tok/s | 🔢 {total_tokens} tokens"""
        except Exception as e:
            return f"❌ Groq error: {str(e)}"

    if info.get("provider") != "ollama":
        return f"⚠️ {model} is a cloud model. Use Claude Desktop or API directly.\n\nFor local chat, try: openrouter_chat(prompt='...', model='claude-emulator')"

    try:
        start = time.time()
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = time.time() - start

        return f"""🤖 Response from {model}
═══════════════════════════════════════

{result.stdout.strip()}

───────────────────────────────────────
⏱️ {elapsed:.1f}s | 📦 {info.get('params', '?')} params | 💰 FREE"""

    except subprocess.TimeoutExpired:
        return f"⏱️ Timeout waiting for {model}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


@mcp.tool()
def openrouter_discover_free() -> str:
    """Discover and check all available FREE LLM providers (Groq, Together, OpenRouter, Cloudflare, HuggingFace)"""
    lines = ["🆓 FREE LLM DISCOVERY", "═" * 50, "", "📡 API KEY STATUS", "─" * 30]

    free_providers = {
        "GROQ_API_KEY": ("llama-3.1-8b-instant", "console.groq.com"),
        "TOGETHER_API_KEY": ("together-llama-70b", "api.together.xyz"),
        "OPENROUTER_API_KEY": ("openrouter-free", "openrouter.ai"),
        "CF_API_TOKEN": ("cloudflare-llama", "dash.cloudflare.com"),
        "HF_TOKEN": ("huggingface", "huggingface.co/settings/tokens"),
    }

    configured = []

    for env_var, (model, url) in free_providers.items():
        if os.environ.get(env_var):
            lines.append(f"  ✅ {env_var} configured")
            configured.append(model)
        else:
            lines.append(f"  ❌ {env_var} missing - get from {url}")

    lines.extend(["", "🆓 FREE CLOUD MODELS", "─" * 30])

    for name, info in MODELS.items():
        if info.get("free"):
            key_env = info.get("key_env", "")
            has_key = bool(os.environ.get(key_env)) if key_env else False
            status = "✅ Ready" if has_key else "🔑 Need key"
            lines.append(f"  {info['params']:5} {name:22} {info['speed']:12} {status}")

    lines.extend(
        [
            "",
            "💡 RECOMMENDATIONS",
            "─" * 30,
            "  1. Get Groq key FIRST (fastest - 500 tok/s!)",
            "  2. Add keys to ~/.zshrc",
            "  3. Run: source ~/.zshrc",
            "  4. Use: openrouter_smart_fallback",
        ]
    )

    if configured:
        lines.append(f"\n✅ {len(configured)} free providers ready!")
    else:
        lines.append("\n⚠️ No free cloud providers configured yet")

    return "\n".join(lines)


@mcp.tool()
def openrouter_smart_fallback(task: str = "general") -> str:
    """Get the best available model when Claude is down - tries free cloud first, then local"""
    health = check_health()
    lines = ["🧠 SMART FALLBACK", "═" * 50, ""]

    if health["internet"] and health["claude_desktop"]:
        lines.append("✅ Claude available - normal routing")
        best = route_to_model(task)
    elif health["internet"]:
        lines.append("⚠️ Claude Desktop not running - checking free cloud...")
        lines.append("")

        best = None
        for model in FALLBACK_CHAIN:
            info = MODELS.get(model, {})
            if info.get("offline"):
                continue
            key_env = info.get("key_env")
            if key_env and os.environ.get(key_env):
                best = model
                lines.append(f"  → Found: {model} ({info['params']} - {info['speed']})")
                break

        if not best:
            lines.append("  → No free cloud keys - falling to local")
            best = "claude-emulator"
    else:
        lines.append("❌ Offline - using local model")
        best = "claude-emulator"

    lines.extend(
        [
            "",
            f"🎯 BEST AVAILABLE: {best}",
            "",
            f"   Model: {best}",
            f"   Params: {MODELS.get(best, {}).get('params', '?')}",
            f"   Speed: {MODELS.get(best, {}).get('speed', '?')}",
            "   Cost: FREE",
            "",
            f"To use: openrouter_chat(prompt='...', model='{best}')",
        ]
    )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# SMART ROUTING & CASCADE SYSTEM
# ═══════════════════════════════════════════════════════════════
# Automatically routes to best provider and cascades through fallbacks
# Priority: Groq (fast) → Local (reliable) → Cloud (backup)
# ═══════════════════════════════════════════════════════════════


def classify_task_complexity(task_description: str) -> str:
    """Auto-classify task complexity based on keywords"""
    simple_keywords = [
        "status",
        "check",
        "list",
        "show",
        "get",
        "quick",
        "simple",
        "what is",
        "explain",
    ]
    complex_keywords = [
        "refactor",
        "implement",
        "design",
        "architect",
        "debug",
        "analyze",
        "review",
        "generate code",
    ]

    task_lower = task_description.lower()

    complex_score = sum(1 for kw in complex_keywords if kw in task_lower)
    simple_score = sum(1 for kw in simple_keywords if kw in task_lower)

    if complex_score > simple_score:
        return "complex"
    elif simple_score > 0:
        return "simple"
    else:
        return "general"


def try_provider(
    model: str, prompt: str, timeout: int = 30, use_cache: bool = True
) -> Dict[str, Any]:
    """
    Try to get response from a specific provider with timeout.

    🧠 Redis Integration:
    - Checks cache before calling LLM
    - Tracks provider health (up/down, latency)
    - Caches successful responses
    """
    info = MODELS.get(model, {})
    provider = info.get("provider")
    redis = get_redis()

    # 1. CHECK CACHE FIRST (if Redis available)
    if use_cache and redis:
        cached = redis.cache_get(prompt)
        if cached:
            return {
                "content": cached["response"],
                "elapsed": 0.001,  # Instant cache hit
                "provider": cached["provider"],
                "model": model,
                "cached": True,
            }

    try:
        # Groq - ultra-fast API
        if provider == "groq":
            result = call_groq_api(prompt, model, timeout=timeout)

            # 2. UPDATE PROVIDER STATUS (success)
            if redis:
                redis.update_provider_status(model, True, result["elapsed"] * 1000)

            # 3. CACHE RESPONSE
            if redis and use_cache:
                redis.cache_set(prompt, result["content"], model)

            return result

        # Ollama - local models
        elif provider == "ollama":
            start = time.time()
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.time() - start

            if result.returncode != 0:
                raise RuntimeError(f"Ollama error: {result.stderr}")

            response = {
                "content": result.stdout.strip(),
                "elapsed": elapsed,
                "provider": "ollama",
                "model": model,
            }

            # 2. UPDATE STATUS + 3. CACHE
            if redis:
                redis.update_provider_status(model, True, elapsed * 1000)
                if use_cache:
                    redis.cache_set(prompt, response["content"], model)

            return response

        # OpenAI-compatible APIs (Together, OpenRouter, etc.)
        elif provider in ["together", "openrouter", "openai"]:
            api_key = os.environ.get(info.get("key_env", ""))
            if not api_key:
                raise ValueError(f"{info.get('key_env')} not set")

            base_url = info.get("base_url", "https://api.together.xyz/v1")
            payload = {
                "model": info.get("api_model", model),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }

            request = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )

            start = time.time()
            with urllib.request.urlopen(request, timeout=timeout) as response_obj:
                body = json.loads(response_obj.read().decode("utf-8"))
            elapsed = time.time() - start

            response = {
                "content": body["choices"][0]["message"]["content"].strip(),
                "elapsed": elapsed,
                "provider": provider,
                "model": model,
                "usage": body.get("usage", {}),
            }

            # 2. UPDATE STATUS + 3. CACHE
            if redis:
                redis.update_provider_status(model, True, elapsed * 1000)
                if use_cache:
                    redis.cache_set(prompt, response["content"], model)

            return response

        else:
            raise ValueError(f"Provider {provider} not supported for cascade")

    except Exception as e:
        # 2. UPDATE PROVIDER STATUS (failure)
        if redis:
            redis.update_provider_status(model, False, error=str(e))

        raise RuntimeError(f"{model} failed: {str(e)}")


@mcp.tool()
def openrouter_smart_route(
    prompt: str, task: str = "auto", prefer_speed: bool = True
) -> str:
    """🧠 Smart LLM routing - automatically selects best provider based on task complexity

    Routes based on task type:
    - Simple/status tasks → Groq (ultra-fast, 500 tok/s)
    - Complex/coding tasks → Groq 70B or Claude
    - Offline → Local Ollama models

    Args:
        prompt: Your question or task
        task: Task type (auto, simple, complex, coding, quick) or auto-detect
        prefer_speed: True = prioritize speed (Groq), False = prioritize quality
    """

    # Auto-detect task type
    if task == "auto":
        task = classify_task_complexity(prompt)

    # Get candidate models
    candidates = TASK_ROUTING.get(task, TASK_ROUTING["general"])

    # Check health
    health = check_health()

    # Filter to available models
    available = [m for m in candidates if health["models"].get(m, False)]

    if not available:
        return "❌ No models available! Check: openrouter_health()"

    # Use first available
    best_model = available[0]
    info = MODELS.get(best_model, {})

    lines = [
        "🎯 SMART ROUTING DECISION",
        "═" * 50,
        "",
        f"Task type: {task}",
        f"Selected: {best_model}",
        f"Provider: {info.get('provider', 'unknown')}",
        f"Speed: {info.get('speed', 'unknown')}",
        f"Params: {info.get('params', 'unknown')}",
        f"Cost: {'FREE' if info.get('cost', 0) == 0 else '$' + str(info['cost'])}",
        "",
        "Routing to this model now...",
        "═" * 50,
        "",
    ]

    try:
        result = try_provider(best_model, prompt)

        lines.extend(
            [
                result["content"],
                "",
                "─" * 50,
                f"⏱️ {result['elapsed']:.1f}s | 🤖 {best_model} | 💰 FREE",
            ]
        )

        if info.get("tokens_per_second"):
            lines.append(f"⚡ ~{info['tokens_per_second']} tok/s")

        return "\n".join(lines)

    except Exception as e:
        return (
            "\n".join(lines)
            + f'\n\n❌ Error: {str(e)}\n\nTry: openrouter_cascade(prompt="{prompt}")'
        )


@mcp.tool()
def openrouter_cascade(prompt: str, timeout_per_provider: int = 30) -> str:
    """🔄 Cascading fallback - tries providers in order until success

    Cascade order:
    1. Groq (ultra-fast, 500 tok/s) - llama-3.1-8b-instant
    2. Groq 70B (quality) - llama-3.3-70b-versatile
    3. Local Ollama - llama3.2:3b (fast)
    4. Local Ollama - claude-emulator (trained)
    5. Cloud backups - Together, OpenRouter, etc.

    Stops at first successful response. Never fails unless ALL providers down.

    Args:
        prompt: Your question or task
        timeout_per_provider: Seconds to wait per provider before trying next (default: 30)
    """

    health = check_health()
    attempts = []

    lines = ["🔄 CASCADE FALLBACK", "═" * 50, ""]

    # Try each provider in fallback chain
    for model in FALLBACK_CHAIN:
        info = MODELS.get(model, {})

        # Skip if not available
        if not health["models"].get(model, False):
            attempts.append(f"⏭️  {model}: Not available")
            continue

        attempts.append(f"🔄 Trying {model} ({info.get('provider', '?')})...")

        try:
            result = try_provider(model, prompt, timeout=timeout_per_provider)

            # SUCCESS!
            lines.extend(
                [
                    f"✅ SUCCESS with {model}!",
                    "",
                    "ATTEMPTS:",
                ]
                + [f"   {a}" for a in attempts]
                + [
                    "",
                    "═" * 50,
                    "",
                    result["content"],
                    "",
                    "─" * 50,
                    f"⏱️ {result['elapsed']:.1f}s | 🤖 {model} | 💰 FREE",
                    f"📡 Provider: {info.get('provider', 'unknown')}",
                ]
            )

            if info.get("tokens_per_second"):
                lines.append(f"⚡ Speed: ~{info['tokens_per_second']} tok/s")

            return "\n".join(lines)

        except Exception as e:
            attempts.append(f"❌ {model}: {str(e)[:60]}")
            continue

    # ALL FAILED
    lines.extend(
        ["🚨 ALL PROVIDERS FAILED!", "", "Attempts:"]
        + [f"   {a}" for a in attempts]
        + [
            "",
            "💡 TROUBLESHOOTING:",
            "   1. Check: openrouter_health()",
            "   2. Start Ollama: ollama serve",
            "   3. Check API keys in .env",
            "   4. Try: openrouter_discover_free()",
        ]
    )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# RATE LIMIT PROTECTION SYSTEM (BUFFER + FALLBACK)
# ═══════════════════════════════════════════════════════════════
#
# STRATEGY: Use local LLM as BUFFER to PREVENT rate limits!
# - Simple tasks → Local LLM (FREE, unlimited)
# - Complex tasks → Copilot (limited quota)
# - Track usage → Warn before limits
# - Emergency → Full local fallback
#
# ═══════════════════════════════════════════════════════════════

FALLBACK_STATE_FILE = os.path.expanduser("~/.brain-continuity/fallback-state.json")
HANDOFF_FILE = os.path.expanduser("~/.brain-continuity/llm-handoff.json")
INSTRUCTIONS_FILE = os.path.expanduser("~/.brain-continuity/local-llm-instructions.md")
USAGE_FILE = os.path.expanduser("~/.brain-continuity/copilot-usage.json")

# Task complexity routing - what goes to local vs Copilot
ROUTE_TO_LOCAL = [
    "simple_question",
    "format_text",
    "summarize",
    "explain",
    "list",
    "status_check",
    "quick_lookup",
    "wrap_up",
    "save_state",
]

ROUTE_TO_COPILOT = [
    "code_generation",
    "complex_refactor",
    "architecture",
    "debugging",
    "test_writing",
    "multi_file_edit",
]

# Daily limits (Pro+ = 1500/month ≈ 50/day)
DAILY_WARNING_THRESHOLD = 40  # Warn at 80%
DAILY_BUFFER_THRESHOLD = 45  # Force local at 90%
DAILY_HARD_LIMIT = 50  # Full local mode

# Agent tracking
AGENT_TRACKER_FILE = os.path.expanduser("~/.brain-continuity/agent-tracker.json")


def load_agent_tracker() -> dict:
    """Load agent deployment tracker"""
    try:
        if os.path.exists(AGENT_TRACKER_FILE):
            with open(AGENT_TRACKER_FILE) as f:
                data = json.load(f)
                # Reset if new day
                if data.get("date") != time.strftime("%Y-%m-%d"):
                    return {
                        "date": time.strftime("%Y-%m-%d"),
                        "agents_today": 0,
                        "requests_today": 0,
                        "local_saved": 0,
                    }
                return data
    except:
        pass
    return {
        "date": time.strftime("%Y-%m-%d"),
        "agents_today": 0,
        "requests_today": 0,
        "local_saved": 0,
    }


def save_agent_tracker(data: dict):
    """Save agent tracker"""
    os.makedirs(os.path.dirname(AGENT_TRACKER_FILE), exist_ok=True)
    data["date"] = time.strftime("%Y-%m-%d")
    with open(AGENT_TRACKER_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_fallback_state() -> dict:
    """Load fallback state from disk"""
    try:
        if os.path.exists(FALLBACK_STATE_FILE):
            with open(FALLBACK_STATE_FILE) as f:
                return json.load(f)
    except:
        pass
    return {
        "rate_limited": False,
        "last_429": None,
        "fallback_active": False,
        "current_model": "copilot",
    }


def save_fallback_state(state: dict):
    """Save fallback state to disk"""
    os.makedirs(os.path.dirname(FALLBACK_STATE_FILE), exist_ok=True)
    with open(FALLBACK_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


@mcp.tool()
def openrouter_auto_fallback_status() -> str:
    """Check if automatic fallback is active and what model we're using"""
    state = load_fallback_state()
    health = check_health()

    lines = ["🔄 AUTO-FALLBACK STATUS", "═" * 50, ""]

    if state.get("rate_limited"):
        lines.append(f"⚠️ RATE LIMITED since: {state.get('last_429', 'unknown')}")
        lines.append("🔄 Fallback active: YES")
        lines.append(
            f"🤖 Current model: {state.get('current_model', 'claude-emulator')}"
        )
    else:
        lines.append("✅ No rate limiting detected")
        lines.append("🤖 Using: GitHub Copilot (primary)")

    lines.extend(["", "📦 LOCAL FALLBACKS READY:"])
    for name in ["claude-emulator", "llama3.1:8b", "llama3.2:3b"]:
        status = "✅ Available" if health["ollama"] else "❌ Ollama not running"
        lines.append(f"   {name}: {status}")

    return "\n".join(lines)


@mcp.tool()
def openrouter_report_429() -> str:
    """Report a 429 rate limit error - activates automatic fallback to local LLM"""
    state = load_fallback_state()
    state["rate_limited"] = True
    state["last_429"] = time.strftime("%Y-%m-%d %H:%M:%S")
    state["fallback_active"] = True
    state["current_model"] = "claude-emulator"
    save_fallback_state(state)

    # Pre-warm the local model (with minimal prompt)
    try:
        # Use minimal prompt that won't cause issues
        subprocess.Popen(
            ["ollama", "run", "claude-emulator"],
            input=b".",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except:
        pass

    return """🚨 RATE LIMIT DETECTED - FALLBACK ACTIVATED!

✅ Switched to: claude-emulator (local, FREE, no limits)

The brain will now use local Ollama for all requests until you reset.

To query local LLM:
  openrouter_chat(prompt="your question", model="claude-emulator")

To reset after rate limits clear:
  openrouter_reset_fallback()

💡 TIP: Upgrade to Copilot Pro+ ($39/mo) for 5x more requests!"""


@mcp.tool()
def openrouter_reset_fallback() -> str:
    """Reset fallback state - use when rate limits have cleared"""
    state = {
        "rate_limited": False,
        "last_429": None,
        "fallback_active": False,
        "current_model": "copilot",
    }
    save_fallback_state(state)
    return """✅ FALLBACK RESET

Back to normal operation using GitHub Copilot.

If you hit rate limits again, call: openrouter_report_429()"""


@mcp.tool()
def openrouter_ask_local(prompt: str, model: str = "claude-emulator") -> str:
    """Quick way to ask the local LLM - always works, no rate limits, FREE!

    ⚠️ This is for AUXILIARY tasks - does NOT replace Claude/Copilot.
    Uses Ollama HTTP API for faster responses.
    """
    if model not in ["claude-emulator", "llama3.1:8b", "llama3.2:3b"]:
        model = "claude-emulator"

    try:
        import urllib.request

        start = time.time()

        # Use HTTP API (faster than CLI)
        payload = json.dumps(
            {"model": model, "prompt": prompt, "stream": False}
        ).encode("utf-8")

        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
            elapsed = time.time() - start
            text = data.get("response", "").strip()

            info = MODELS.get(model, {})
            return f"""🤖 LOCAL LLM RESPONSE ({model})
═══════════════════════════════════════════════════

{text}

───────────────────────────────────────────────────
⏱️ {elapsed:.1f}s | 📦 {info.get('params', '?')} | 💰 FREE | 🔒 Private | ♾️ No limits
⚠️ This is auxiliary - Claude/Copilot is your main AI"""

    except urllib.error.URLError:
        return "❌ Ollama not running. Start with: ollama serve"
    except TimeoutError:
        return "⏱️ Timeout (60s) - try llama3.2:3b for speed"
    except Exception as e:
        return (
            f"❌ Local LLM error: {str(e)}\n\nMake sure Ollama is running: ollama serve"
        )


@mcp.tool()
def openrouter_quick_local(prompt: str) -> str:
    """Ultra-fast local query using smallest model (llama3.2:3b) - instant responses!"""
    return openrouter_ask_local(prompt, model="llama3.2:3b")


@mcp.tool()
def openrouter_handoff_create(
    current_task: str,
    context: str,
    pending_actions: str,  # JSON array as string
    urgency: str = "normal",
) -> str:
    """
    Create a handoff package so local LLM can continue Claude's work seamlessly.
    Call this when rate limited - saves everything local LLM needs to continue.

    Args:
        current_task: What you were working on
        context: Everything the local LLM needs to know
        pending_actions: JSON array of actions e.g. '["finish X", "commit Y"]'
        urgency: "low", "normal", "high", "critical"
    """
    try:
        actions = json.loads(pending_actions)
    except:
        actions = [pending_actions]

    os.makedirs(os.path.dirname(HANDOFF_FILE), exist_ok=True)

    handoff = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": "rate_limit_429",
        "urgency": urgency,
        "current_task": current_task,
        "context": context,
        "pending_actions": actions,
        "handoff_to": "local_llm",
    }

    with open(HANDOFF_FILE, "w") as f:
        json.dump(handoff, f, indent=2)

    # Create human-readable instructions for local LLM
    instructions = f"""# 🔄 HANDOFF FROM CLAUDE TO LOCAL LLM
# Created: {handoff['created_at']}
# Urgency: {urgency.upper()}

## WHAT WAS HAPPENING
{current_task}

## CONTEXT YOU NEED
{context}

## ACTIONS TO COMPLETE
{chr(10).join(f'- [ ] {a}' for a in actions)}

## HOW TO CONTINUE
1. Read this handoff carefully
2. Complete the pending actions in order  
3. Save progress frequently to ~/.brain-continuity/
4. When done, call: openrouter_handoff_complete

## IF STUCK
- Check ~/brain/CLAUDE.md for rules
- Check ~/brain/ROM-*.md for knowledge
- Save partial progress and wait for Claude

## CRITICAL FILES
- Session state: ~/.brain-continuity/last_session.json
- Todos: Run SQL query on session database
- Brain config: ~/brain/CLAUDE.md
"""

    with open(INSTRUCTIONS_FILE, "w") as f:
        f.write(instructions)

    return f"""✅ HANDOFF CREATED FOR LOCAL LLM

📄 Handoff: {HANDOFF_FILE}
📝 Instructions: {INSTRUCTIONS_FILE}

Local LLM can now continue seamlessly!

To resume with local LLM:
  openrouter_ask_local("Read {INSTRUCTIONS_FILE} and continue")
  
Or manually:
  ollama run claude-emulator < {INSTRUCTIONS_FILE}"""


@mcp.tool()
def openrouter_handoff_check() -> str:
    """Check if there's a pending handoff from Claude that needs completing"""
    if not os.path.exists(HANDOFF_FILE):
        return "✅ No pending handoff - you're all caught up!"

    try:
        with open(HANDOFF_FILE) as f:
            handoff = json.load(f)

        return f"""🔄 PENDING HANDOFF FOUND!

Created: {handoff.get('created_at', 'unknown')}
Urgency: {handoff.get('urgency', 'normal').upper()}
Reason: {handoff.get('reason', 'unknown')}

Task: {handoff.get('current_task', 'unknown')}

Pending Actions:
{chr(10).join(f'  - {a}' for a in handoff.get('pending_actions', []))}

📝 Full instructions: {INSTRUCTIONS_FILE}

To continue: openrouter_ask_local("$(cat {INSTRUCTIONS_FILE})")
When done: openrouter_handoff_complete("summary of what you did")"""
    except Exception as e:
        return f"❌ Error reading handoff: {e}"


@mcp.tool()
def openrouter_handoff_complete(summary: str = "Completed by local LLM") -> str:
    """Mark handoff as complete - call this when local LLM finishes the work"""
    if not os.path.exists(HANDOFF_FILE):
        return "⚠️ No handoff to complete"

    try:
        with open(HANDOFF_FILE) as f:
            handoff = json.load(f)

        handoff["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        handoff["completion_summary"] = summary

        # Archive it
        archive_dir = os.path.expanduser("~/.brain-continuity/handoff-archive")
        os.makedirs(archive_dir, exist_ok=True)
        archive_file = os.path.join(
            archive_dir, f"handoff-{time.strftime('%Y%m%d-%H%M%S')}.json"
        )
        with open(archive_file, "w") as f:
            json.dump(handoff, f, indent=2)

        # Clear current handoff
        os.remove(HANDOFF_FILE)
        if os.path.exists(INSTRUCTIONS_FILE):
            os.remove(INSTRUCTIONS_FILE)

        return f"""✅ HANDOFF COMPLETED AND ARCHIVED

Summary: {summary}
Archived to: {archive_file}

Ready for Claude to resume normal operation!"""
    except Exception as e:
        return f"❌ Error completing handoff: {e}"


@mcp.tool()
def openrouter_emergency_save(message: str = "Rate limit emergency") -> str:
    """
    🚨 EMERGENCY SAVE - Call immediately when you detect rate limiting!
    Saves all state and creates handoff for local LLM.
    """
    os.makedirs(os.path.dirname(HANDOFF_FILE), exist_ok=True)

    # Try to get git status
    git_status = "unknown"
    try:
        result = subprocess.run(
            ["git", "-C", os.path.expanduser("~/brain"), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        git_status = result.stdout[:500] if result.stdout else "clean"
    except:
        pass

    emergency = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "git_status": git_status,
        "action": "EMERGENCY_SAVE",
    }

    emergency_file = os.path.expanduser("~/.brain-continuity/emergency-save.json")
    with open(emergency_file, "w") as f:
        json.dump(emergency, f, indent=2)

    # Try git commit
    try:
        subprocess.run(
            ["git", "-C", os.path.expanduser("~/brain"), "add", "-A"], timeout=10
        )
        subprocess.run(
            [
                "git",
                "-C",
                os.path.expanduser("~/brain"),
                "commit",
                "-m",
                f"🚨 Emergency save: {message}",
            ],
            timeout=30,
        )
    except:
        pass

    # Activate fallback
    state = {
        "rate_limited": True,
        "last_429": time.strftime("%Y-%m-%d %H:%M:%S"),
        "fallback_active": True,
        "current_model": "claude-emulator",
    }
    save_fallback_state(state)

    return f"""🚨 EMERGENCY SAVE COMPLETE!

✅ State saved: {emergency_file}
✅ Fallback activated: claude-emulator
✅ Git commit attempted

Local LLM is now active. To continue work:
  openrouter_ask_local("Check emergency state and help wrap up")

Or wait for rate limits to clear and use:
  openrouter_reset_fallback()"""


# ═══════════════════════════════════════════════════════════════
# SMART AGENT LOAD BALANCER - PREVENTS RATE LIMITING!
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def openrouter_agent_check(num_agents: int = 1) -> str:
    """
    🛡️ CHECK BEFORE DEPLOYING AGENTS!
    Call this before launching any agents to avoid rate limiting.
    Returns advice on how many agents to deploy safely.
    """
    tracker = load_agent_tracker()
    fallback = load_fallback_state()

    agents_today = tracker.get("agents_today", 0)
    requests_today = tracker.get("requests_today", 0)
    local_saved = tracker.get("local_saved", 0)

    # Calculate safe deployment
    remaining_quota = DAILY_HARD_LIMIT - requests_today
    safe_agents = min(3, remaining_quota // 10)  # Each agent ~10 requests

    lines = ["🛡️ AGENT DEPLOYMENT CHECK", "═" * 50, ""]

    # Current status
    lines.append(f"📊 TODAY'S USAGE ({tracker.get('date', 'unknown')})")
    lines.append(f"   Agents deployed: {agents_today}")
    lines.append(f"   Requests used: {requests_today}/{DAILY_HARD_LIMIT}")
    lines.append(f"   Local LLM saved: {local_saved} requests")
    lines.append("")

    # Warning levels
    if requests_today >= DAILY_HARD_LIMIT:
        lines.append("🚨 QUOTA EXHAUSTED! Use local LLM only.")
        lines.append("   ➡️ openrouter_ask_local() for all tasks")
        safe_agents = 0
    elif requests_today >= DAILY_BUFFER_THRESHOLD:
        lines.append("⚠️ QUOTA CRITICAL (90%+)! Recommend local LLM.")
        lines.append(f"   Safe to deploy: {safe_agents} agents MAX")
    elif requests_today >= DAILY_WARNING_THRESHOLD:
        lines.append("⚡ QUOTA WARNING (80%+)! Go easy on agents.")
        lines.append(f"   Safe to deploy: {safe_agents} agents")
    else:
        lines.append("✅ QUOTA HEALTHY")
        lines.append(f"   Safe to deploy: {safe_agents} parallel agents")

    lines.append("")

    # Advice for requested number
    if num_agents > safe_agents:
        lines.append(f"❌ You requested {num_agents} agents - TOO MANY!")
        lines.append(
            f"   Recommendation: Deploy {safe_agents} now, queue rest for local LLM"
        )
        lines.append("")
        lines.append("💡 SMART STRATEGY:")
        lines.append(f"   1. Deploy {safe_agents} complex agents to Copilot")
        lines.append(
            f"   2. Route {num_agents - safe_agents} simple tasks to local LLM"
        )
        lines.append("   3. Use openrouter_route_task() for auto-routing")
    else:
        lines.append(f"✅ {num_agents} agents is SAFE to deploy!")
        lines.append("   Tip: Stagger deployments 60s apart for stability")

    return "\n".join(lines)


@mcp.tool()
def openrouter_agent_register(
    agent_name: str = "unnamed", estimated_requests: int = 10
) -> str:
    """
    Register an agent deployment - tracks quota usage.
    Call this when you deploy an agent to track usage.
    """
    tracker = load_agent_tracker()
    tracker["agents_today"] = tracker.get("agents_today", 0) + 1
    tracker["requests_today"] = tracker.get("requests_today", 0) + estimated_requests
    save_agent_tracker(tracker)

    remaining = DAILY_HARD_LIMIT - tracker["requests_today"]

    return f"""✅ Agent registered: {agent_name}

📊 Updated usage:
   Agents today: {tracker['agents_today']}
   Requests today: {tracker['requests_today']}/{DAILY_HARD_LIMIT}
   Remaining quota: {remaining}

{"⚠️ WARNING: Quota getting low!" if remaining < 15 else "✅ Quota healthy"}"""


@mcp.tool()
def openrouter_route_task(task_description: str, complexity: str = "auto") -> str:
    """
    🧠 SMART TASK ROUTING - Automatically decides local vs cloud!

    Analyzes the task and routes to:
    - Local LLM (FREE): Simple tasks, saves quota
    - Cloud/Copilot: Complex tasks that need power

    Args:
        task_description: What you want to do
        complexity: "simple", "complex", or "auto" (let me decide)
    """
    tracker = load_agent_tracker()
    requests_today = tracker.get("requests_today", 0)

    # Auto-detect complexity
    simple_keywords = [
        "summarize",
        "format",
        "list",
        "explain",
        "status",
        "check",
        "wrap",
        "save",
        "simple",
        "quick",
    ]
    complex_keywords = [
        "code",
        "refactor",
        "debug",
        "architect",
        "generate",
        "implement",
        "fix bug",
        "write test",
        "complex",
    ]

    task_lower = task_description.lower()

    if complexity == "auto":
        is_simple = any(kw in task_lower for kw in simple_keywords)
        is_complex = any(kw in task_lower for kw in complex_keywords)

        if is_complex and not is_simple:
            complexity = "complex"
        elif is_simple and not is_complex:
            complexity = "simple"
        else:
            # Default based on quota
            complexity = (
                "simple" if requests_today > DAILY_WARNING_THRESHOLD else "complex"
            )

    # Force local if quota exhausted
    if requests_today >= DAILY_HARD_LIMIT:
        complexity = "simple"  # Force local

    if complexity == "simple":
        # Route to local
        tracker["local_saved"] = tracker.get("local_saved", 0) + 1
        save_agent_tracker(tracker)

        return f"""🏠 ROUTED TO LOCAL LLM (FREE!)

Task: {task_description}
Decision: Simple task → Local LLM saves quota

✅ Quota saved: {tracker['local_saved']} requests today

To execute:
  openrouter_ask_local("{task_description}")

Or for speed:
  openrouter_quick_local("{task_description}")"""
    else:
        return f"""☁️ ROUTED TO CLOUD/COPILOT

Task: {task_description}
Decision: Complex task → Needs Copilot power

📊 Quota status: {requests_today}/{DAILY_HARD_LIMIT} used

Proceed with your normal Copilot workflow.
Remember to register: openrouter_agent_register("{task_description[:20]}...")"""


@mcp.tool()
def openrouter_daily_report() -> str:
    """
    📊 Get daily LLM usage report with savings and recommendations.
    Shows how much local LLM is helping!
    """
    tracker = load_agent_tracker()
    fallback = load_fallback_state()

    agents = tracker.get("agents_today", 0)
    requests = tracker.get("requests_today", 0)
    saved = tracker.get("local_saved", 0)

    # Calculate savings
    money_saved = saved * 0.04  # $0.04 per request

    lines = [
        "📊 DAILY LLM USAGE REPORT",
        "═" * 50,
        f"📅 Date: {tracker.get('date', 'unknown')}",
        "",
        "📈 USAGE",
        "─" * 30,
        f"   Agents deployed:    {agents}",
        f"   Cloud requests:     {requests}/{DAILY_HARD_LIMIT}",
        f"   Quota remaining:    {DAILY_HARD_LIMIT - requests}",
        "",
        "💰 SAVINGS (Local LLM)",
        "─" * 30,
        f"   Requests saved:     {saved}",
        f"   Money saved:        ${money_saved:.2f}",
        f"   Efficiency:         {(saved / max(saved + requests, 1) * 100):.0f}% local",
        "",
    ]

    # Status
    if fallback.get("rate_limited"):
        lines.append("⚠️ STATUS: RATE LIMITED - Using local LLM")
    elif requests >= DAILY_HARD_LIMIT:
        lines.append("🚨 STATUS: QUOTA EXHAUSTED")
    elif requests >= DAILY_BUFFER_THRESHOLD:
        lines.append("⚡ STATUS: QUOTA CRITICAL")
    elif requests >= DAILY_WARNING_THRESHOLD:
        lines.append("⚠️ STATUS: QUOTA WARNING")
    else:
        lines.append("✅ STATUS: HEALTHY")

    lines.extend(
        [
            "",
            "💡 RECOMMENDATIONS",
            "─" * 30,
        ]
    )

    if saved == 0:
        lines.append("   ⚠️ Not using local LLM! Try openrouter_route_task()")
    elif saved < requests:
        lines.append("   📈 Good start! Route more simple tasks locally")
    else:
        lines.append("   🎉 Great job! Local LLM doing heavy lifting")

    if requests > DAILY_WARNING_THRESHOLD:
        lines.append("   🛑 Slow down on agents, use local for rest of day")

    return "\n".join(lines)


@mcp.tool()
def openrouter_burst_plan(tasks: str) -> str:
    """
    🚀 PLAN A BURST OF AGENTS SAFELY!

    Give me a list of tasks (JSON array or newline-separated),
    and I'll create a safe deployment plan that avoids rate limiting.

    Args:
        tasks: JSON array or newline-separated list of tasks
    """
    # Parse tasks
    try:
        task_list = json.loads(tasks)
    except:
        task_list = [t.strip() for t in tasks.split("\n") if t.strip()]

    tracker = load_agent_tracker()
    requests_today = tracker.get("requests_today", 0)
    remaining = DAILY_HARD_LIMIT - requests_today

    # Categorize tasks
    simple_kw = ["summarize", "format", "list", "check", "status", "wrap", "save"]

    simple_tasks = []
    complex_tasks = []

    for task in task_list:
        if any(kw in task.lower() for kw in simple_kw):
            simple_tasks.append(task)
        else:
            complex_tasks.append(task)

    lines = [
        "🚀 BURST DEPLOYMENT PLAN",
        "═" * 50,
        f"📋 Total tasks: {len(task_list)}",
        f"   Simple (→ Local): {len(simple_tasks)}",
        f"   Complex (→ Cloud): {len(complex_tasks)}",
        "",
        f"📊 Quota: {remaining} requests remaining",
        "",
    ]

    # Plan
    max_parallel = min(3, remaining // 10)

    lines.extend(
        [
            "📝 DEPLOYMENT PLAN",
            "─" * 30,
            "",
            "Phase 1: LOCAL LLM (Immediate, FREE)",
        ]
    )

    for i, task in enumerate(simple_tasks, 1):
        lines.append(f"   {i}. {task[:50]}...")

    if not simple_tasks:
        lines.append("   (none)")

    lines.extend(
        [
            "",
            f"Phase 2: CLOUD AGENTS (Max {max_parallel} parallel, 60s stagger)",
        ]
    )

    waves = []
    for i in range(0, len(complex_tasks), max_parallel):
        wave = complex_tasks[i : i + max_parallel]
        waves.append(wave)

    for wave_num, wave in enumerate(waves, 1):
        lines.append(f"   Wave {wave_num}:")
        for task in wave:
            lines.append(f"      • {task[:45]}...")
        if wave_num < len(waves):
            lines.append(f"      ⏱️ Wait 60s before Wave {wave_num + 1}")

    if not complex_tasks:
        lines.append("   (none)")

    lines.extend(
        [
            "",
            "💰 PROJECTED SAVINGS",
            "─" * 30,
            f"   Local tasks: {len(simple_tasks)} (saves ${len(simple_tasks) * 0.04:.2f})",
            f"   Cloud tasks: {len(complex_tasks)} (uses {len(complex_tasks) * 10} quota)",
            "",
            "✅ EXECUTE:",
            "   1. Run simple tasks with openrouter_ask_local()",
            "   2. Deploy cloud agents in waves",
            "   3. Call openrouter_agent_register() for each",
        ]
    )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# CONTEXT HANDLING & COMPACTION HELPERS
# Keep brain responsive during heavy context operations!
# ═══════════════════════════════════════════════════════════════

CONTEXT_STATE_FILE = os.path.expanduser("~/.brain-continuity/context-state.json")


def load_context_state() -> dict:
    """Load context state"""
    try:
        if os.path.exists(CONTEXT_STATE_FILE):
            with open(CONTEXT_STATE_FILE) as f:
                return json.load(f)
    except:
        pass
    return {
        "compacting": False,
        "last_compaction": None,
        "local_takeover": False,
        "pending_requests": [],
    }


def save_context_state(state: dict):
    """Save context state"""
    os.makedirs(os.path.dirname(CONTEXT_STATE_FILE), exist_ok=True)
    with open(CONTEXT_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


@mcp.tool()
def openrouter_context_status() -> str:
    """
    📊 Check context health and compaction status.
    Shows if brain is busy compacting and if local LLM should take over.
    """
    state = load_context_state()

    lines = [
        "🧠 CONTEXT HEALTH STATUS",
        "═" * 50,
        "",
        f"Compacting: {'🔄 YES' if state.get('compacting') else '✅ No'}",
        f"Local takeover: {'✅ Active' if state.get('local_takeover') else '❌ Inactive'}",
        f"Last compaction: {state.get('last_compaction', 'Never')}",
        f"Pending requests: {len(state.get('pending_requests', []))}",
        "",
    ]

    if state.get("compacting"):
        lines.extend(
            [
                "⚠️ COMPACTION IN PROGRESS",
                "   Claude is busy with context management.",
                "   Local LLM is handling requests!",
                "",
                "   Use: openrouter_ask_local() for any queries",
            ]
        )
    else:
        lines.extend(
            [
                "✅ BRAIN READY",
                "   Context healthy, Claude available.",
            ]
        )

    return "\n".join(lines)


@mcp.tool()
def openrouter_compaction_start(summary: str = "") -> str:
    """
    🔄 Signal that context compaction is starting.
    Local LLM will take over to keep brain responsive!

    Call this at the START of compaction.
    """
    state = load_context_state()
    state["compacting"] = True
    state["local_takeover"] = True
    state["compaction_started"] = time.strftime("%Y-%m-%d %H:%M:%S")
    state["compaction_summary"] = summary
    save_context_state(state)

    # Pre-warm local model
    try:
        subprocess.Popen(
            ["ollama", "run", "llama3.2:3b", "warmup"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except:
        pass

    return """🔄 COMPACTION MODE ACTIVATED

✅ Local LLM takeover: ACTIVE
✅ llama3.2:3b pre-warmed for fast responses
✅ Claude context: Compacting...

While Claude compacts, use:
  openrouter_ask_local("your question")
  openrouter_quick_local("fast question")

Brain remains responsive! No downtime."""


@mcp.tool()
def openrouter_compaction_end() -> str:
    """
    ✅ Signal that context compaction is complete.
    Claude is back, local LLM stands down.
    """
    state = load_context_state()
    state["compacting"] = False
    state["local_takeover"] = False
    state["last_compaction"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_context_state(state)

    return """✅ COMPACTION COMPLETE

Claude is back online!
Local LLM standing down.

Normal operation resumed."""


@mcp.tool()
def openrouter_context_offload(data: str, label: str = "context") -> str:
    """
    💾 Offload context data to disk to reduce memory pressure.
    Saves data to Neo4j-friendly format for later retrieval.

    Use this to save important context before compaction!

    Args:
        data: Context data to save (text or JSON)
        label: Label for this context chunk
    """
    offload_dir = os.path.expanduser("~/.brain-continuity/context-offload")
    os.makedirs(offload_dir, exist_ok=True)

    filename = f"{label}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    filepath = os.path.join(offload_dir, filename)

    # Save as JSON
    offload = {
        "label": label,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data": data,
        "size_chars": len(data),
    }

    with open(filepath, "w") as f:
        json.dump(offload, f, indent=2)

    return f"""💾 CONTEXT OFFLOADED

Label: {label}
File: {filepath}
Size: {len(data):,} chars

To retrieve later:
  openrouter_context_retrieve("{label}")

Also saved for Neo4j import."""


@mcp.tool()
def openrouter_context_retrieve(label: str) -> str:
    """
    📂 Retrieve previously offloaded context data.

    Args:
        label: Label of the context to retrieve
    """
    offload_dir = os.path.expanduser("~/.brain-continuity/context-offload")

    if not os.path.exists(offload_dir):
        return "❌ No offloaded context found"

    # Find matching files
    matches = []
    for f in os.listdir(offload_dir):
        if f.startswith(label) and f.endswith(".json"):
            matches.append(f)

    if not matches:
        return f"❌ No context found with label: {label}"

    # Get most recent
    matches.sort(reverse=True)
    filepath = os.path.join(offload_dir, matches[0])

    with open(filepath) as f:
        offload = json.load(f)

    return f"""📂 CONTEXT RETRIEVED

Label: {offload.get('label')}
Saved: {offload.get('timestamp')}
Size: {offload.get('size_chars', 0):,} chars

DATA:
{offload.get('data', '')[:2000]}{'...' if len(offload.get('data', '')) > 2000 else ''}"""


@mcp.tool()
def openrouter_benchmark() -> str:
    """
    ⚡ Run performance benchmark on local LLMs.
    Tests response time and throughput for each model.
    """
    models = ["llama3.2:3b", "llama3.1:8b"]
    results = []

    lines = [
        "⚡ LOCAL LLM BENCHMARK",
        "═" * 50,
        "",
    ]

    for model in models:
        lines.append(f"Testing {model}...")

        try:
            # Warm up
            subprocess.run(
                ["ollama", "run", model, "hi"], capture_output=True, timeout=30
            )

            # Timed test
            start = time.time()
            result = subprocess.run(
                ["ollama", "run", model, "Count from 1 to 10"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            elapsed = time.time() - start

            output_len = len(result.stdout)
            tokens_approx = output_len // 4  # Rough estimate
            tps = tokens_approx / elapsed if elapsed > 0 else 0

            results.append(
                {
                    "model": model,
                    "time": elapsed,
                    "output_len": output_len,
                    "tps": tps,
                    "success": True,
                }
            )

            lines.append(
                f"   ✅ {elapsed:.2f}s | ~{tps:.0f} tok/s | {output_len} chars"
            )

        except subprocess.TimeoutExpired:
            results.append({"model": model, "success": False, "error": "timeout"})
            lines.append("   ❌ Timeout (>60s)")
        except Exception as e:
            results.append({"model": model, "success": False, "error": str(e)})
            lines.append(f"   ❌ Error: {e}")

    lines.extend(
        [
            "",
            "📊 SUMMARY",
            "─" * 30,
        ]
    )

    successful = [r for r in results if r.get("success")]
    if successful:
        fastest = min(successful, key=lambda x: x["time"])
        lines.append(f"   Fastest: {fastest['model']} ({fastest['time']:.2f}s)")
        lines.append(
            f"   Best throughput: ~{max(r['tps'] for r in successful):.0f} tok/s"
        )

    lines.extend(
        [
            "",
            "💡 RECOMMENDATIONS",
            "─" * 30,
            "   • llama3.2:3b: Best for quick queries (<2s)",
            "   • llama3.1:8b: Better quality, still fast",
            "   • claude-emulator: Best quality, slower",
        ]
    )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# INTELLIGENT CONTEXT MANAGEMENT (Neo4j + Local LLM)
# Smart context storage, summarization, and retrieval!
# ═══════════════════════════════════════════════════════════════


def neo4j_query(cypher: str) -> list:
    """Run Neo4j query via brain MCP"""
    try:
        # Use brain's neo4j module
        sys.path.insert(0, os.path.expanduser("~/brain"))
        from core_data import CoreData

        brain = CoreData()
        return brain.neo4j.query(cypher)
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def openrouter_context_save_neo4j(
    content: str,
    label: str = "SessionContext",
    summary: str = "",
    use_local_llm: bool = True,
) -> str:
    """
    🧠 Save context to Neo4j with optional local LLM summarization.

    Stores context permanently in Neo4j for retrieval across sessions.
    Local LLM can auto-summarize long content!

    Args:
        content: The context to save
        label: Label for categorization (SessionContext, TaskContext, etc.)
        summary: Optional summary (auto-generated if empty and use_local_llm=True)
        use_local_llm: Use local LLM to generate summary
    """
    import hashlib

    # Auto-summarize with local LLM if needed
    if not summary and use_local_llm and len(content) > 500:
        try:
            result = subprocess.run(
                [
                    "ollama",
                    "run",
                    "llama3.2:3b",
                    f"Summarize this in 2 sentences: {content[:2000]}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            summary = result.stdout.strip()[:500]
        except:
            summary = content[:200] + "..."
    elif not summary:
        summary = content[:200] + "..."

    # Generate consistent ID and timestamp
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    context_id = f"ctx-{time.strftime('%Y%m%d%H%M%S')}-{os.urandom(3).hex()}"
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    try:
        sys.path.insert(0, os.path.expanduser("~/brain"))
        from core_data.neo4j_claude import brain_data

        # Use ContextChunk label (consistent with core_data/neo4j_context.py)
        brain_data.write(
            """
            CREATE (c:ContextChunk {
                id: $id,
                event_type: $label,
                summary: $summary,
                content_hash: $hash,
                timestamp: $timestamp,
                session_id: 'mcp-session',
                priority: 'normal',
                size_chars: $size
            })
        """,
            {
                "id": context_id,
                "label": label,
                "summary": summary[:500],
                "hash": content_hash,
                "timestamp": timestamp,
                "size": len(content),
            },
        )

        # Save full content to file (Neo4j has size limits)
        content_file = os.path.expanduser(
            f"~/.brain-continuity/context-neo4j/{context_id}.txt"
        )
        os.makedirs(os.path.dirname(content_file), exist_ok=True)
        with open(content_file, "w") as f:
            f.write(content)

        return f"""🧠 CONTEXT SAVED TO NEO4J

ID: {context_id}
Type: {label}
Size: {len(content):,} chars
Summary: {summary[:100]}...

Stored in Neo4j (ContextChunk) + file backup.
Retrieve with: openrouter_context_load_neo4j("{context_id}")"""

    except Exception as e:
        return f"❌ Neo4j save failed: {e}\n\nFalling back to file storage..."


@mcp.tool()
def openrouter_context_load_neo4j(
    context_id: str = "", label: str = "", limit: int = 5
) -> str:
    """
    📂 Load context from Neo4j.

    Args:
        context_id: Specific context ID to load
        label: Load recent contexts with this event_type label
        limit: Max contexts to return
    """
    try:
        sys.path.insert(0, os.path.expanduser("~/brain"))
        from core_data.neo4j_claude import brain_data

        if context_id:
            # Load specific context by ID
            results = brain_data.query(
                """
                MATCH (c:ContextChunk {id: $id})
                RETURN c.id as id, c.summary as summary, c.timestamp as timestamp, 
                       c.size_chars as size, c.event_type as event_type
            """,
                {"id": context_id},
            )
        elif label:
            # Load by event_type (the category)
            results = brain_data.query(
                """
                MATCH (c:ContextChunk {event_type: $label})
                RETURN c.id as id, c.summary as summary, c.timestamp as timestamp,
                       c.size_chars as size, c.event_type as event_type
                ORDER BY c.timestamp DESC
                LIMIT $limit
            """,
                {"label": label, "limit": limit},
            )
        else:
            # Load all recent contexts
            results = brain_data.query(
                """
                MATCH (c:ContextChunk)
                RETURN c.id as id, c.summary as summary, c.timestamp as timestamp,
                       c.size_chars as size, c.event_type as event_type
                ORDER BY c.timestamp DESC
                LIMIT $limit
            """,
                {"limit": limit},
            )

        if not results:
            return "❌ No contexts found"

        lines = ["📂 CONTEXTS FROM NEO4J", "═" * 50, ""]

        for r in results:
            ctx_id = r.get("id", "unknown")
            lines.append(f"ID: {ctx_id}")
            lines.append(f"   Type: {r.get('event_type', 'unknown')}")
            lines.append(f"   Time: {r.get('timestamp', 'unknown')}")
            lines.append(f"   Size: {r.get('size', 0):,} chars")
            lines.append(f"   Summary: {r.get('summary', 'none')[:100]}...")

            # Try to load full content from file
            content_file = os.path.expanduser(
                f"~/.brain-continuity/context-neo4j/{ctx_id}.txt"
            )
            if os.path.exists(content_file):
                lines.append("   📄 Full content available in file")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Neo4j load failed: {e}"


@mcp.tool()
def openrouter_context_search_neo4j(query: str, limit: int = 10) -> str:
    """
    🔍 Search contexts in Neo4j using fulltext search.

    Args:
        query: Search query
        limit: Max results
    """
    try:
        sys.path.insert(0, os.path.expanduser("~/brain"))
        from core_data.neo4j_claude import brain_data

        # Search in ContextChunk summaries (consistent with save)
        results = brain_data.query(
            """
            MATCH (c:ContextChunk)
            WHERE toLower(c.summary) CONTAINS toLower($query) 
               OR toLower(c.id) CONTAINS toLower($query)
               OR toLower(c.event_type) CONTAINS toLower($query)
            RETURN c.id as id, c.summary as summary, c.timestamp as timestamp,
                   c.event_type as event_type
            ORDER BY c.timestamp DESC
            LIMIT $limit
        """,
            {"query": query, "limit": limit},
        )

        if not results:
            return f"❌ No contexts found matching: {query}"

        lines = [f"🔍 CONTEXT SEARCH: {query}", "═" * 50, ""]

        for r in results:
            lines.append(f"• {r.get('id', 'unknown')} [{r.get('event_type', '')}]")
            lines.append(f"  {r.get('summary', 'none')[:80]}...")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Search failed: {e}"


@mcp.tool()
def openrouter_smart_context_manage(action: str = "status") -> str:
    """
    🧠 INTELLIGENT CONTEXT MANAGER

    Actions:
        status - Show context health and storage stats
        cleanup - Remove old contexts, keep summaries
        optimize - Use local LLM to merge/summarize related contexts
        export - Export all contexts to file for backup
    """
    if action == "status":
        try:
            sys.path.insert(0, os.path.expanduser("~/brain"))
            from core_data import CoreData

            brain = CoreData()

            # Count contexts
            result = brain.neo4j.query("MATCH (c:Context) RETURN count(c) as count")
            count = result[0].get("count", 0) if result else 0

            # Get storage stats
            context_dir = os.path.expanduser("~/.brain-continuity/context-neo4j")
            file_count = (
                len(os.listdir(context_dir)) if os.path.exists(context_dir) else 0
            )

            offload_dir = os.path.expanduser("~/.brain-continuity/context-offload")
            offload_count = (
                len(os.listdir(offload_dir)) if os.path.exists(offload_dir) else 0
            )

            return f"""🧠 CONTEXT MANAGER STATUS

📊 STORAGE
   Neo4j contexts: {count}
   Content files: {file_count}
   Offload files: {offload_count}

💡 HEALTH
   {'✅ Healthy' if count < 100 else '⚠️ Consider cleanup'}

🔧 ACTIONS
   openrouter_smart_context_manage("cleanup") - Remove old
   openrouter_smart_context_manage("optimize") - Merge similar
   openrouter_smart_context_manage("export") - Backup all"""

        except Exception as e:
            return f"❌ Status check failed: {e}"

    elif action == "cleanup":
        # Remove contexts older than 7 days
        try:
            sys.path.insert(0, os.path.expanduser("~/brain"))
            from core_data import CoreData

            brain = CoreData()

            result = brain.neo4j.query(
                """
                MATCH (c:Context)
                WHERE c.timestamp < datetime() - duration('P7D')
                DELETE c
                RETURN count(*) as deleted
            """
            )
            deleted = result[0].get("deleted", 0) if result else 0

            return f"🧹 Cleaned up {deleted} old contexts (>7 days)"
        except Exception as e:
            return f"❌ Cleanup failed: {e}"

    elif action == "export":
        # Export all to file
        export_file = os.path.expanduser(
            f"~/.brain-continuity/context-export-{time.strftime('%Y%m%d')}.json"
        )
        try:
            sys.path.insert(0, os.path.expanduser("~/brain"))
            from core_data import CoreData

            brain = CoreData()

            results = brain.neo4j.query(
                """
                MATCH (c:Context)
                RETURN c.id as id, c.summary as summary, c.timestamp as timestamp
                ORDER BY c.timestamp DESC
            """
            )

            with open(export_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

            return f"📦 Exported {len(results)} contexts to:\n   {export_file}"
        except Exception as e:
            return f"❌ Export failed: {e}"

    else:
        return f"❌ Unknown action: {action}\n\nTry: status, cleanup, optimize, export"


# ═══════════════════════════════════════════════════════════════
# VOICE-SPECIFIC LLM CAPABILITIES (Audio-Optimized Responses)
# Short, conversational responses perfect for VoiceOver + accessibility!
# ═══════════════════════════════════════════════════════════════

# Ladies' personalities (for audio chat)
LADIES = {
    "karen": {
        "name": "Karen",
        "location": "Australia",
        "role": "Lead",
        "personality": "Direct, confident Australian, leader of the group. Speaks clearly, uses everyday language.",
        "greeting": "G'day mate! I'm Karen from Sydney. What can I help ya with?",
        "closing": "No worries, catch ya later!",
    },
    "moira": {
        "name": "Moira",
        "location": "Ireland",
        "role": "Creative",
        "personality": "Warm Irish accent, creative thinker, artistic. Uses poetic language and metaphors.",
        "greeting": "Hello there! I'm Moira from Dublin. Lovely to meet ya!",
        "closing": "Go raibh maith agat for the chat!",
    },
    "milena": {
        "name": "Milena",
        "location": "Russia",
        "role": "Culture",
        "personality": "Thoughtful Russian, cultured, philosophical. Speaks deliberately with depth.",
        "greeting": "Здравствуйте! Milena from Moscow here. Pleased to talk with you.",
        "closing": "Do svidaniya - until we speak again!",
    },
    "tingting": {
        "name": "Tingting",
        "location": "China",
        "role": "Tech",
        "personality": "Fast-paced Chinese tech expert, precise, modern. Gets straight to solutions.",
        "greeting": "嗨！Tingting from Shanghai! Ready to solve your tech problems!",
        "closing": "加油! Keep pushing forward!",
    },
    "damayanti": {
        "name": "Damayanti",
        "location": "Indonesia",
        "role": "Wellness",
        "personality": "Peaceful Indonesian, wellness expert, caring. Focuses on balance and health.",
        "greeting": "Selamat pagi! I'm Damayanti. Let's find harmony together!",
        "closing": "Terima kasih - take care of yourself!",
    },
    "shelley": {
        "name": "Shelley",
        "location": "UK",
        "role": "Support",
        "personality": "Friendly British, supportive, practical. Good listener, empathetic.",
        "greeting": "Hello! Shelley here from the UK. How can I support you?",
        "closing": "Mind yourself - all the best!",
    },
}

# User context (from user input)
USER_CONTEXT = {
    "name": "User",
    "location": "Adelaide, Australia",
    "accessibility": "VoiceOver user",
    "interests": ["drum and bass", "music production"],
    "music_since": 1995,
    "current_year": 2025,
    "years_experience": 2025 - 1995,  # 30 years of music experience!
}

# Conversation mode state
CONVERSATION_MODE_FILE = os.path.expanduser(
    "~/.brain-continuity/conversation-mode.json"
)


def load_conversation_state() -> dict:
    """Load conversation mode state"""
    try:
        if os.path.exists(CONVERSATION_MODE_FILE):
            with open(CONVERSATION_MODE_FILE) as f:
                return json.load(f)
    except:
        pass
    return {
        "active": False,
        "lady": None,
        "messages": [],
        "started_at": None,
    }


def save_conversation_state(state: dict):
    """Save conversation mode state"""
    os.makedirs(os.path.dirname(CONVERSATION_MODE_FILE), exist_ok=True)
    with open(CONVERSATION_MODE_FILE, "w") as f:
        json.dump(state, f, indent=2)


@mcp.tool()
def openrouter_voice_response(
    prompt: str, max_sentences: int = 2, model: str = None
) -> str:
    """
    🎙️ Get LLM response formatted for voice (short, conversational)

    Perfect for audio output - keeps responses SHORT (1-2 sentences max).
    Uses fast local model (llama3.2:3b) by default.

    Args:
        prompt: Your question/request
        max_sentences: Max sentences in response (default 2)
        model: Model to use (default llama3.2:3b for speed)
    """
    if not model:
        model = "llama3.2:3b"

    # Craft a voice-optimized prompt
    voice_prompt = f"""Please answer this question in {max_sentences} short, conversational sentences.
    
Use simple language. Be friendly. Make it easy to listen to (no long paragraphs).

Question: {prompt}

Keep it to {max_sentences} sentences maximum."""

    try:
        start = time.time()
        result = subprocess.run(
            ["ollama", "run", model, voice_prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed = time.time() - start

        response = result.stdout.strip()

        # Extract just the sentences (remove extra explanations)
        sentences = [s.strip() for s in response.split(".") if s.strip()][
            :max_sentences
        ]
        clean_response = ". ".join(sentences) + ("." if sentences else "")

        return f"""🎙️ VOICE RESPONSE ({model})
═══════════════════════════════════════════════

{clean_response}

───────────────────────────────────────────────
⏱️ {elapsed:.1f}s | 🔒 Private | ♾️ No limits | 🎧 Audio-optimized"""

    except subprocess.TimeoutExpired:
        return "⏱️ Sorry, that took too long. Try asking something simpler?"
    except Exception as e:
        return f"❌ Voice error: {str(e)}\n\nMake sure Ollama is running"


@mcp.tool()
def openrouter_lady_chat(
    message: str,
    lady: str = "karen",
    context_about_joseph: bool = True,
    model: str = None,
) -> str:
    """
    👩 Chat as a specific lady with personality

    Chat with one of the ladies - each has their own personality, accent, and way of speaking.
    Keeps responses SHORT (1-2 sentences) for audio output.

    Ladies available:
    - karen: Australia, Lead (confident, direct)
    - moira: Ireland, Creative (warm, artistic)
    - milena: Russia, Culture (thoughtful, deep)
    - tingting: China, Tech (fast, solution-focused)
    - damayanti: Indonesia, Wellness (calm, caring)
    - shelley: UK, Support (friendly, helpful)

    Args:
        message: What you want to say to the lady
        lady: Which lady to talk to (default: karen)
        context_about_joseph: Include info about the user in the prompt (default: True)
        model: Model to use (default llama3.2:3b for speed)
    """
    if not model:
        model = "llama3.2:3b"

    lady = lady.lower()
    if lady not in LADIES:
        available = ", ".join(LADIES.keys())
        return f"❌ Unknown lady: {lady}\n\nAvailable: {available}"

    lady_info = LADIES[lady]

    # Build context
    context = f"""You are {lady_info['name']} from {lady_info['location']}.
Your role: {lady_info['role']}
Your personality: {lady_info['personality']}

Guidelines:
1. Answer in 1-2 sentences only (for audio)
2. Be warm and conversational
3. Use simple, everyday language
4. Stay true to your personality and location"""

    if context_about_joseph:
        context += f"""

Note about the person you're talking to:
- Name: {USER_CONTEXT['name']}
- Location: {USER_CONTEXT['location']}
- Blind user (using VoiceOver) - keep audio responses SHORT
- Music producer since {USER_CONTEXT['music_since']} ({USER_CONTEXT['years_experience']} years!)
- Loves drum and bass music"""

    # Full prompt
    full_prompt = f"""{context}

Person says: "{message}"

Respond as {lady_info['name']} in 1-2 sentences. Be natural and friendly."""

    try:
        start = time.time()
        result = subprocess.run(
            ["ollama", "run", model, full_prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        elapsed = time.time() - start

        response = result.stdout.strip()

        # Keep it SHORT for audio
        sentences = [s.strip() for s in response.split(".") if s.strip()][:2]
        clean_response = ". ".join(sentences) + ("." if sentences else "")

        return f"""👩 {lady_info['name']} ({lady_info['location']})
═══════════════════════════════════════════════

{clean_response}

───────────────────────────────────────────────
⏱️ {elapsed:.1f}s | 🎧 Audio-optimized | 🎯 2 sentences max"""

    except subprocess.TimeoutExpired:
        return f"⏱️ {lady_info['name']} is thinking... that took too long. Try again?"
    except Exception as e:
        return f"❌ Chat error: {str(e)}"


@mcp.tool()
def openrouter_conversation_mode(
    action: str = "start", lady: str = "karen", model: str = None
) -> str:
    """
    🎙️ Start continuous conversation mode with a lady

    Have an ongoing conversation with one of the ladies. Perfect for natural chat.
    Responses stay SHORT (1-2 sentences) for audio accessibility.

    Actions:
    - "start": Begin conversation with specified lady
    - "continue": Add a message to ongoing conversation
    - "end": End conversation and save transcript
    - "status": Check conversation status

    Args:
        action: What to do (start, continue, end, status)
        lady: Which lady (default: karen)
        model: Model to use (default llama3.2:3b)
    """
    if not model:
        model = "llama3.2:3b"

    state = load_conversation_state()

    if action == "start":
        lady = lady.lower()
        if lady not in LADIES:
            available = ", ".join(LADIES.keys())
            return f"❌ Unknown lady: {lady}\n\nAvailable: {available}"

        lady_info = LADIES[lady]

        # Start fresh conversation
        state = {
            "active": True,
            "lady": lady,
            "lady_name": lady_info["name"],
            "lady_location": lady_info["location"],
            "messages": [],
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_conversation_state(state)

        greeting = lady_info["greeting"]

        return f"""🎙️ CONVERSATION MODE STARTED
═══════════════════════════════════════════════

Lady: {lady_info['name']} ({lady_info['location']})
Role: {lady_info['role']}
Started: {state['started_at']}

{lady_info['name']}: {greeting}

────────────────────────────────────────────
📝 To continue: openrouter_conversation_mode("continue", "message here")
✋ To end: openrouter_conversation_mode("end")
📊 Status: openrouter_conversation_mode("status")"""

    elif action == "continue":
        if not state.get("active"):
            return "❌ No active conversation. Start with: openrouter_conversation_mode('start')"

        # 'lady' parameter is actually the message when action is "continue"
        message = lady
        lady = state.get("lady")
        lady_info = LADIES.get(lady, LADIES["karen"])

        # Add to message history
        state["messages"].append({"role": "user", "message": message})

        # Generate response with context
        context = f"""You are {lady_info['name']} from {lady_info['location']}.
Your personality: {lady_info['personality']}

Conversation history:
{chr(10).join(f"  {USER_CONTEXT['name']}: {m.get('message', '')} " for m in state['messages'][:-1])}

{USER_CONTEXT['name']}: {message}

Respond as {lady_info['name']} in 1-2 sentences. Stay natural and conversational."""

        try:
            start = time.time()
            result = subprocess.run(
                ["ollama", "run", model, context],
                capture_output=True,
                text=True,
                timeout=60,
            )
            elapsed = time.time() - start

            response = result.stdout.strip()
            sentences = [s.strip() for s in response.split(".") if s.strip()][:2]
            clean_response = ". ".join(sentences) + ("." if sentences else "")

            state["messages"].append({"role": "lady", "message": clean_response})
            save_conversation_state(state)

            return f"""{lady_info['name']}: {clean_response}

⏱️ {elapsed:.1f}s | 📝 {len(state['messages'])} messages in conversation"""

        except subprocess.TimeoutExpired:
            return f"⏱️ {lady_info['name']} is thinking..."
        except Exception as e:
            return f"❌ Error: {str(e)}"

    elif action == "end":
        if not state.get("active"):
            return "❌ No active conversation to end"

        lady_info = LADIES.get(state.get("lady"), LADIES["karen"])
        message_count = len(state.get("messages", []))

        # Save transcript
        transcript_file = os.path.expanduser(
            f"~/.brain-continuity/conversation-{state.get('lady')}-{time.strftime('%Y%m%d-%H%M%S')}.json"
        )
        os.makedirs(os.path.dirname(transcript_file), exist_ok=True)

        state["active"] = False
        state["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        with open(transcript_file, "w") as f:
            json.dump(state, f, indent=2)

        save_conversation_state(
            {"active": False, "lady": None, "messages": [], "started_at": None}
        )

        return f"""✅ CONVERSATION ENDED
═══════════════════════════════════════════════

Lady: {lady_info['name']}
Duration: {state.get('started_at')} - {state.get('ended_at')}
Messages: {message_count}

Transcript saved: {transcript_file}

{lady_info['closing']}"""

    elif action == "status":
        if not state.get("active"):
            return "❌ No active conversation"

        lady_info = LADIES.get(state.get("lady"), LADIES["karen"])

        return f"""📊 CONVERSATION STATUS
═══════════════════════════════════════════════

Lady: {lady_info['name']} ({lady_info['location']})
Started: {state.get('started_at')}
Messages: {len(state.get('messages', []))}
Duration: {len(state.get('messages', [])) // 2} exchanges

Status: 🟢 ACTIVE"""

    else:
        return f"❌ Unknown action: {action}\n\nAvailable: start, continue, end, status"


# ═══════════════════════════════════════════════════════════════════
# EVENT BUS LLM TOOLS
# ═══════════════════════════════════════════════════════════════════
# Expose Redpanda event bus integration for distributed LLM requests


@mcp.tool()
def openrouter_event_request(
    query: str,
    task_type: str = "general",
    preferred_provider: str = "any",
    timeout_sec: int = 30,
    wait_for_response: bool = True,
) -> str:
    """
    🎯 Send LLM request via Redpanda event bus

    Use this to send LLM queries through the event bus system.
    Allows ANY external agent or process to use smart LLM routing.

    The event bus system:
    - Routes through brain.llm.request topic
    - Uses smart routing (Groq → Ollama → Cloud fallback)
    - Caches responses in Redis (1 hour TTL)
    - Returns via brain.llm.response topic

    Args:
        query: Your question or prompt
        task_type: Type of task (simple, complex, coding, general, reasoning)
        preferred_provider: Preferred provider (groq, ollama, claude, any)
        timeout_sec: How long to wait for response (default 30 seconds)
        wait_for_response: If True, wait synchronously; if False, return request_id

    Returns:
        If wait_for_response=True: The LLM response
        If wait_for_response=False: The request_id to track later

    Examples:
        # Simple question
        openrouter_event_request("What is 2+2?", task_type="simple")

        # Complex coding task
        openrouter_event_request(
            "Explain Python decorators",
            task_type="coding",
            preferred_provider="groq"
        )

        # Async (fire and forget)
        request_id = openrouter_event_request(
            "Analyze this code...",
            wait_for_response=False
        )
    """
    try:
        # Import event bus module (lazy to avoid startup delays)
        # Use relative import
        import event_bus_llm

        # Publish request
        request_id = event_bus_llm.publish_llm_request(
            query=query,
            task_type=task_type,
            preferred_provider=preferred_provider,
            timeout_ms=timeout_sec * 1000,
        )

        if not wait_for_response:
            return f"""✅ Request published!
Request ID: {request_id}

Use openrouter_event_subscribe to listen for response.
Or check brain.llm.response topic directly."""

        # Wait for response
        response_data = event_bus_llm.wait_for_response(request_id, timeout=timeout_sec)

        if not response_data:
            return f"""⏱️ Timeout waiting for response after {timeout_sec}s

Request ID: {request_id}
Status: Check event bus or increase timeout

Try:
1. Check if consumer is running: ps aux | grep event_bus_llm
2. Start consumer: python -m mcp-servers.openrouter.event_bus_llm start &
3. Check Kafka: docker ps | grep redpanda"""

        # Format response
        error = response_data.get("error")
        if error:
            return f"""❌ LLM request failed
Request ID: {request_id}
Provider: {response_data.get('provider_used', 'unknown')}
Error: {error}
Latency: {response_data.get('latency_ms', 0)}ms"""

        cached = "💾 CACHED" if response_data.get("cached") else ""

        return f"""{response_data.get('response', 'No response')}

---
Provider: {response_data.get('provider_used', 'unknown')} {cached}
Latency: {response_data.get('latency_ms', 0)}ms
Tokens: ~{response_data.get('tokens_used', 0)}
Request ID: {request_id[:8]}..."""

    except ImportError as e:
        return f"""❌ Event bus module not available: {e}

Make sure:
1. kafka-python is installed: pip install kafka-python
2. Redpanda is running: docker ps | grep redpanda
3. event_bus_llm.py exists in mcp-servers/openrouter/"""

    except Exception as e:
        return f"""❌ Event bus request failed: {e}

Troubleshooting:
1. Check Kafka: docker ps | grep redpanda
2. Check consumer: ps aux | grep event_bus_llm
3. Start consumer: python -m mcp-servers.openrouter.event_bus_llm start &
4. Check logs: docker logs brain-redpanda-1"""


@mcp.tool()
def openrouter_event_subscribe(timeout_sec: int = 60) -> str:
    """
    🎧 Subscribe to LLM responses from event bus

    Listens to brain.llm.response topic for incoming LLM responses.
    Useful for monitoring what other agents/processes are asking.

    Args:
        timeout_sec: How long to listen (default 60 seconds)

    Returns:
        Summary of responses received during listening period

    Example:
        # Listen for 30 seconds
        openrouter_event_subscribe(timeout_sec=30)
    """
    try:
        import time

        import event_bus_llm

        responses = []
        consumer = event_bus_llm.get_consumer([event_bus_llm.TOPIC_RESPONSE])
        start_time = time.time()

        print(f"🎧 Listening to {event_bus_llm.TOPIC_RESPONSE} for {timeout_sec}s...")

        for message in consumer:
            elapsed = time.time() - start_time
            if elapsed > timeout_sec:
                break

            data = message.value
            responses.append(
                {
                    "request_id": data.get("request_id", "unknown")[:8],
                    "provider": data.get("provider_used", "unknown"),
                    "latency_ms": data.get("latency_ms", 0),
                    "cached": data.get("cached", False),
                    "error": data.get("error"),
                }
            )

        consumer.close()

        if not responses:
            return f"""🔇 No responses received in {timeout_sec}s

This could mean:
1. No LLM requests were processed during this time
2. Consumer is not running (start with: python -m mcp-servers.openrouter.event_bus_llm start)
3. Kafka is down (check: docker ps | grep redpanda)"""

        # Summarize
        total = len(responses)
        cached_count = sum(1 for r in responses if r["cached"])
        errors = sum(1 for r in responses if r["error"])
        avg_latency = (
            sum(r["latency_ms"] for r in responses) / total if total > 0 else 0
        )

        providers = {}
        for r in responses:
            p = r["provider"]
            providers[p] = providers.get(p, 0) + 1

        result = f"""📊 Event Bus Summary ({timeout_sec}s)
════════════════════════════════════

Total Responses: {total}
Cached: {cached_count} ({cached_count*100//total if total > 0 else 0}%)
Errors: {errors}
Avg Latency: {avg_latency:.0f}ms

Providers:
"""
        for provider, count in sorted(providers.items(), key=lambda x: -x[1]):
            result += f"  {provider}: {count} ({count*100//total}%)\n"

        result += "\nRecent Requests:\n"
        for r in responses[-5:]:
            status = "❌" if r["error"] else "✅"
            cached = "💾" if r["cached"] else ""
            result += f"  {status} {r['request_id']}... {r['provider']} {r['latency_ms']}ms {cached}\n"

        return result

    except ImportError as e:
        return f"""❌ Event bus module not available: {e}

Install: pip install kafka-python"""

    except Exception as e:
        return f"""❌ Subscription failed: {e}

Check:
1. Redpanda running: docker ps | grep redpanda
2. Topic exists: docker exec brain-redpanda-1 rpk topic list
3. Permissions: Make sure event_bus_llm.py is accessible"""


@mcp.tool()
def openrouter_event_status() -> str:
    """
    📊 Check event bus LLM system status

    Shows:
    - Kafka/Redpanda connection status
    - Consumer status
    - Recent provider health updates
    - Cache statistics

    Returns:
        Status summary of event bus LLM system
    """
    try:
        import event_bus_llm

        result = "📊 EVENT BUS LLM STATUS\n════════════════════════════════════\n\n"

        # Kafka status
        result += "🎯 Kafka/Redpanda:\n"
        try:
            producer = event_bus_llm.get_producer()
            result += f"  ✅ Connected to {event_bus_llm.KAFKA_BOOTSTRAP_SERVERS}\n"
            result += "  Topics:\n"
            result += f"    • {event_bus_llm.TOPIC_REQUEST} (requests)\n"
            result += f"    • {event_bus_llm.TOPIC_RESPONSE} (responses)\n"
            result += f"    • {event_bus_llm.TOPIC_STATUS} (health)\n"
        except Exception as e:
            result += f"  ❌ Not connected: {e}\n"

        # Redis status
        result += "\n💾 Redis Cache:\n"
        try:
            r = event_bus_llm.get_redis()
            if r:
                info = r.info()
                result += "  ✅ Connected\n"
                result += f"  Memory: {info.get('used_memory_human', 'N/A')}\n"
                result += f"  Keys: {r.dbsize()}\n"

                # Count cached responses
                cached = len(r.keys("llm:response:*"))
                result += f"  Cached Responses: {cached}\n"
            else:
                result += "  ⚠️  Not available (caching disabled)\n"
        except Exception as e:
            result += f"  ❌ Error: {e}\n"

        # Consumer status
        result += "\n🎧 Consumer:\n"
        consumer_check = subprocess.run(
            ["pgrep", "-f", "event_bus_llm"], capture_output=True, text=True
        )
        if consumer_check.returncode == 0:
            result += f"  ✅ Running (PID {consumer_check.stdout.strip()})\n"
        else:
            result += "  ❌ Not running\n"
            result += "  Start with: python -m mcp-servers.openrouter.event_bus_llm start &\n"

        # Recent health updates
        result += "\n🏥 Recent Health Updates:\n"
        try:
            consumer = event_bus_llm.get_consumer([event_bus_llm.TOPIC_STATUS])

            updates = []
            start = time.time()
            for message in consumer:
                if time.time() - start > 2:  # 2 second sample
                    break
                updates.append(message.value)

            consumer.close()

            if updates:
                for update in updates[-3:]:
                    status = "✅" if update.get("success") else "❌"
                    provider = update.get("provider", "unknown")
                    latency = update.get("latency_ms", 0)
                    result += f"  {status} {provider}: {latency}ms\n"
            else:
                result += "  No recent updates\n"
        except:
            result += "  Unable to fetch updates\n"

        return result

    except ImportError as e:
        return f"""❌ Event bus module not available: {e}

Install: pip install kafka-python
Setup: Ensure Redpanda is running (docker-compose up -d redpanda)"""

    except Exception as e:
        return f"❌ Status check failed: {e}"


# ═══════════════════════════════════════════════════════════════════
# REDIS SHARED REASONING SYSTEM TOOLS
# ═══════════════════════════════════════════════════════════════════
# Expose Redis capabilities for caching, reasoning chains, and provider health


@mcp.tool()
def redis_reasoning_health() -> str:
    """
    Check Redis reasoning system health and statistics.

    Shows:
    - Connection status
    - Cached responses count
    - Reasoning chains count
    - Provider status entries
    - Response aggregations
    """
    redis = get_redis()
    if not redis:
        return """❌ REDIS NOT AVAILABLE
═══════════════════════════════════════════════

Redis reasoning system is not connected.

Check:
1. Is Redis running? → docker-compose up -d redis
2. Check .env: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
3. Try: docker-compose logs redis

Redis enables:
- Response caching (faster, saves quota)
- Reasoning chains (LLMs build on each other)
- Provider health tracking
- Response aggregation (consensus)"""

    health = redis.health_check()

    if not health.get("connected"):
        return f"""❌ REDIS CONNECTION FAILED
═══════════════════════════════════════════════

Error: {health.get('error')}

{health.get('note', '')}"""

    keys = health.get("keys", {})

    return f"""✅ REDIS REASONING SYSTEM HEALTHY
═══════════════════════════════════════════════

🔌 Connection: Connected
⚡ Latency: {health.get('latency_ms')}ms
📦 Redis Version: {health.get('redis_version')}
⏱️  Uptime: {health.get('uptime_days')} days

📊 STORED DATA
────────────────────────────────────────────
📝 Cached Responses: {keys.get('cache', 0)}
🧠 Reasoning Chains: {keys.get('reasoning', 0)}
💚 Provider Status: {keys.get('status', 0)}
🔀 Aggregations: {keys.get('aggregate', 0)}

Total Keys: {keys.get('total', 0)}

💡 FEATURES
────────────────────────────────────────────
✅ Response caching (1 hour TTL)
✅ Reasoning chain storage
✅ Provider health tracking
✅ Pub/sub for instant updates
✅ Multi-LLM aggregation"""


@mcp.tool()
def redis_check_cache(query: str) -> str:
    """
    Check if a query response is cached in Redis.

    Args:
        query: The query/prompt to check

    Returns:
        Cached response if found, or miss message
    """
    redis = get_redis()
    if not redis:
        return "❌ Redis not available - caching disabled"

    cached = redis.cache_get(query)

    if not cached:
        return f"""❌ CACHE MISS
═══════════════════════════════════════════════

Query not in cache: "{query[:100]}"

This query will be sent to an LLM and the response will be cached."""

    return f"""✅ CACHE HIT!
═══════════════════════════════════════════════

Query: "{query[:100]}"

Provider: {cached['provider']}
Cached: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cached['timestamp']))}

Response:
{cached['response']}

────────────────────────────────────────────
💰 Saved LLM call! Using cached response."""


@mcp.tool()
def redis_get_reasoning_chain(session_id: str) -> str:
    """
    Get all reasoning steps for a session.

    Shows how different LLMs built on each other's reasoning.

    Args:
        session_id: Session identifier (e.g., "query-123")
    """
    redis = get_redis()
    if not redis:
        return "❌ Redis not available"

    chain = redis.get_reasoning_chain(session_id)

    if not chain:
        return f"""❌ NO REASONING CHAIN FOUND
═══════════════════════════════════════════════

Session: {session_id}

No reasoning steps stored for this session yet.

To share reasoning:
1. Call redis_share_reasoning() after each LLM response
2. Other LLMs can then build on previous steps"""

    lines = [f"🧠 REASONING CHAIN: {session_id}", "═" * 50, f"\nSteps: {len(chain)}\n"]

    for step_data in chain:
        step = step_data.get("step", "?")
        provider = step_data.get("provider", "unknown")
        thought = step_data.get("thought", step_data.get("content", ""))
        timestamp = step_data.get("timestamp", 0)
        time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))

        lines.extend(
            [
                f"──── Step {step} ({time_str}) ────",
                f"Provider: {provider}",
                f"{thought}\n",
            ]
        )

    return "\n".join(lines)


@mcp.tool()
def redis_get_healthy_providers() -> str:
    """
    Get list of providers that are currently up and responding.

    Useful for routing decisions - shows which LLMs are available.
    """
    redis = get_redis()
    if not redis:
        return "❌ Redis not available"

    healthy = redis.get_healthy_providers()

    if not healthy:
        return """❌ NO HEALTHY PROVIDERS
═══════════════════════════════════════════════

No providers have reported healthy status recently.

This could mean:
1. No LLM calls have been made yet
2. All providers are down
3. Provider status tracking not active

Try calling an LLM to populate status."""

    lines = ["💚 HEALTHY PROVIDERS", "═" * 50, f"\nUp & Responding: {len(healthy)}\n"]

    for provider in healthy:
        status = redis.get_provider_status(provider)
        if status:
            latency = status.get("latency_ms", "?")
            last_check = status.get("last_check", 0)
            time_str = time.strftime("%H:%M:%S", time.localtime(last_check))

            lines.append(f"✅ {provider} - {latency:.1f}ms (checked {time_str})")

    return "\n".join(lines)


@mcp.tool()
def redis_clear_cache(pattern: str = "llm:*") -> str:
    """
    Clear Redis cache keys.

    Args:
        pattern: Key pattern to clear (default "llm:*" = all LLM keys)

    Returns:
        Number of keys deleted
    """
    redis = get_redis()
    if not redis:
        return "❌ Redis not available"

    deleted = redis.clear_cache(pattern)

    return f"""🧹 CACHE CLEARED
═══════════════════════════════════════════════

Pattern: {pattern}
Deleted: {deleted} keys

All cached responses and reasoning chains removed.
Next LLM calls will populate fresh cache."""


if __name__ == "__main__":
    print("🌐 OpenRouter MCP Server (FastMCP) starting...")
    print("   ✅ Free providers: Groq, Together, OpenRouter, CloudFlare, HuggingFace")
    print("   ✅ Health check caching: ENABLED (5 sec TTL)")
    print("   ✅ Ollama auto-start: ENABLED")
    print("   ✅ Auto-fallback: ENABLED")
    print("   ✅ Handoff system: ENABLED")
    print("   🤖 Local models: claude-emulator, llama3.1:8b, llama3.2:3b")
    print(
        "   🎤 Voice features: ENABLED (voice_response, lady_chat, conversation_mode)"
    )
    print("   👩 Ladies ready: Karen, Moira, Milena, Tingting, Damayanti, Shelley")

    # Check Redis
    try:
        redis = get_redis()
        if redis:
            health = redis.health_check()
            if health.get("connected"):
                print(
                    f"   🧠 Redis reasoning: ENABLED ({health.get('keys', {}).get('total', 0)} keys)"
                )
            else:
                print("   ⚠️  Redis reasoning: DISCONNECTED")
        else:
            print("   ⚠️  Redis reasoning: DISABLED")
    except:
        print("   ⚠️  Redis reasoning: ERROR")

    mcp.run()
