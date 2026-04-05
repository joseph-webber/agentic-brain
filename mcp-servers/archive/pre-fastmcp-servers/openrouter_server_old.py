#!/usr/bin/env python3
"""
🌐 BRAIN OPENROUTER MCP SERVER
==============================

MCP server for AI model routing, switching, and management.

Tools:
- openrouter_status: Get full system status
- openrouter_models: List all available models
- openrouter_route: Find best model for a task
- openrouter_switch: Switch to a different model
- openrouter_compare: Compare models
- openrouter_health: Check model health
- openrouter_recommend: Get recommendations for a task
- openrouter_chat: Send message to a model
"""

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

# Add brain to path
sys.path.insert(0, os.path.expanduser("~/brain"))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# ═══════════════════════════════════════════════════════════════
# MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════

MODELS = {
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
    "groq-llama-70b": {
        "provider": "groq",
        "params": "70B",
        "context": 131072,
        "speed": "ultra-fast",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": ["speed", "general", "coding", "reasoning"],
        "description": "FREE 70B at 500 tokens/sec - fastest cloud option!",
        "key_env": "GROQ_API_KEY",
        "rate_limit": "30/min",
    },
    "groq-llama-8b": {
        "provider": "groq",
        "params": "8B",
        "context": 131072,
        "speed": "ultra-fast",
        "cost": 0,
        "offline": False,
        "free": True,
        "strengths": ["quick", "general"],
        "description": "FREE fast 8B model",
        "key_env": "GROQ_API_KEY",
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

# Smart fallback chain when Claude unavailable
FALLBACK_CHAIN = [
    "groq-llama-70b",  # 1st: Fastest FREE 70B
    "together-llama-70b",  # 2nd: Quality FREE 70B
    "groq-llama-8b",  # 3rd: Fast FREE 8B
    "openrouter-free",  # 4th: OpenRouter free tier
    "cloudflare-llama",  # 5th: Always free
    "claude-emulator",  # 6th: Local fallback
    "llama3.1:8b",  # 7th: Local alternative
]

TASK_ROUTING = {
    "recovery": ["claude-emulator"],
    "brain-repair": ["claude-emulator"],
    "offline": ["claude-emulator", "llama3.1:8b", "llama3.2:3b"],
    "quick": ["groq-llama-8b", "llama3.2:3b", "claude-sonnet", "gpt-4o"],
    "coding": [
        "groq-llama-70b",
        "claude-sonnet",
        "copilot",
        "together-llama-70b",
        "llama3.1:8b",
    ],
    "complex": ["groq-llama-70b", "claude-opus", "together-llama-70b", "claude-sonnet"],
    "general": [
        "groq-llama-70b",
        "claude-sonnet",
        "together-llama-8b",
        "llama3.1:8b",
        "gpt-4o",
    ],
    "jira": ["claude-emulator", "claude-sonnet"],
    "accessibility": ["claude-emulator"],
    "private": ["claude-emulator", "llama3.1:8b", "llama3.2:3b"],
    "free": [
        "groq-llama-70b",
        "groq-llama-8b",
        "together-llama-70b",
        "openrouter-free",
        "cloudflare-llama",
    ],
    "free-fast": ["groq-llama-70b", "groq-llama-8b"],
}

# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════


def check_health() -> Dict[str, Any]:
    """Check system and model health"""
    health = {"internet": False, "ollama": False, "claude_desktop": False, "models": {}}

    # Check internet
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", "8.8.8.8"], capture_output=True, timeout=3
        )
        health["internet"] = result.returncode == 0
    except:
        pass

    # Check Ollama
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
    except:
        pass

    # Check Claude Desktop
    try:
        result = subprocess.run(
            ["pgrep", "-f", "Claude"], capture_output=True, timeout=2
        )
        health["claude_desktop"] = result.returncode == 0
    except:
        pass

    # Cloud models depend on internet
    for name, info in MODELS.items():
        if not info["offline"]:
            health["models"][name] = health["internet"]

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

    # Fallback
    for model, info in MODELS.items():
        if info["offline"] and health["models"].get(model, False):
            return model

    return "claude-emulator"


# ═══════════════════════════════════════════════════════════════
# MCP SERVER
# ═══════════════════════════════════════════════════════════════

server = Server("openrouter")


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="openrouter_status",
            description="Get full OpenRouter system status - shows internet, Ollama, Claude Desktop, and all model availability",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="openrouter_models",
            description="List all available AI models with details (params, cost, speed, strengths)",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="openrouter_route",
            description="Find the best available model for a specific task",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task type: coding, complex, quick, recovery, private, general, free, free-fast",
                        "enum": [
                            "coding",
                            "complex",
                            "quick",
                            "recovery",
                            "private",
                            "general",
                            "jira",
                            "accessibility",
                            "offline",
                            "free",
                            "free-fast",
                        ],
                    },
                    "prefer_offline": {
                        "type": "boolean",
                        "description": "Prefer offline models even if cloud is available",
                        "default": False,
                    },
                },
                "required": ["task"],
            },
        ),
        Tool(
            name="openrouter_switch",
            description="Switch to a different AI model (opens Claude Desktop, starts Ollama model, etc)",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model to switch to: claude-emulator, llama3.1:8b, llama3.2:3b, claude (desktop), copilot",
                    }
                },
                "required": ["model"],
            },
        ),
        Tool(
            name="openrouter_compare",
            description="Compare AI models side by side - shows params, cost, speed, and best use cases",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="openrouter_health",
            description="Quick health check of all services and models",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="openrouter_recommend",
            description="Get ranked recommendations for a specific task",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task to get recommendations for",
                    }
                },
                "required": ["task"],
            },
        ),
        Tool(
            name="openrouter_chat",
            description="Send a message to a specific model and get response",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Message to send"},
                    "model": {
                        "type": "string",
                        "description": "Model to use (optional - auto-routes if not specified)",
                    },
                    "task": {
                        "type": "string",
                        "description": "Task type for auto-routing",
                        "default": "general",
                    },
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="openrouter_discover_free",
            description="Discover and check all available FREE LLM providers (Groq, Together, OpenRouter, Cloudflare, HuggingFace)",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="openrouter_smart_fallback",
            description="Get the best available model when Claude is down - tries free cloud first, then local",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task type for routing",
                        "default": "general",
                    }
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:

    if name == "openrouter_status":
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

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "openrouter_models":
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

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "openrouter_route":
        task = arguments.get("task", "general")
        prefer_offline = arguments.get("prefer_offline", False)
        model = route_to_model(task, prefer_offline)
        info = MODELS.get(model, {})

        result = f"""🎯 ROUTING RESULT

Task: {task}
Best Model: {model}
Provider: {info.get('provider', 'unknown')}
Params: {info.get('params', 'unknown')}
Offline: {'Yes' if info.get('offline') else 'No'}
Cost: {'FREE' if info.get('cost', 0) == 0 else f"${info.get('cost')}"}

To use: openrouter_switch(model="{model}")
Or CLI: openrouter use {model.split(':')[0]}"""

        return [TextContent(type="text", text=result)]

    elif name == "openrouter_switch":
        model = arguments.get("model", "")

        if model in ["claude", "claude-desktop"]:
            subprocess.Popen(["open", "-a", "Claude"])
            return [
                TextContent(
                    type="text",
                    text="🚀 Opening Claude Desktop...\n\nClaude Desktop is starting. You can now use the full Claude experience.",
                )
            ]

        elif model == "copilot":
            return [
                TextContent(
                    type="text",
                    text="🚀 To use Copilot CLI:\n\n```bash\ncopilot\n```\n\nRun this in your terminal.",
                )
            ]

        elif model in MODELS or any(model in m for m in MODELS):
            return [
                TextContent(
                    type="text",
                    text=f"""🚀 To use {model}:

```bash
ollama run {model}
```

Or use the robot command:
```bash
robot
```

This model is LOCAL and works OFFLINE.""",
                )
            ]

        else:
            return [
                TextContent(
                    type="text",
                    text=f"❌ Unknown model: {model}\n\nAvailable: "
                    + ", ".join(MODELS.keys()),
                )
            ]

    elif name == "openrouter_compare":
        comparison = """⚖️ MODEL COMPARISON
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
claude-opus        175B+    Medium   $0.015/1K   Complex reasoning, analysis
claude-sonnet      70B+     Fast     $0.003/1K   Balanced, coding
gpt-4o             200B+    Fast     $0.005/1K   Multimodal
copilot            varies   Fast     FREE*       Terminal, git, coding

* Copilot included with GitHub subscription

💡 RECOMMENDATIONS
──────────────────
• Offline/Private → claude-emulator (trained for YOU)
• Speed needed → llama3.2:3b or claude-sonnet  
• Complex task → claude-opus
• Coding → copilot or claude-sonnet
• Recovery → claude-emulator"""

        return [TextContent(type="text", text=comparison)]

    elif name == "openrouter_health":
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

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "openrouter_recommend":
        task = arguments.get("task", "general")
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

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "openrouter_discover_free":
        lines = [
            "🆓 FREE LLM DISCOVERY",
            "═" * 50,
            "",
            "📡 API KEY STATUS",
            "─" * 30,
        ]

        # Check each free provider key
        free_providers = {
            "GROQ_API_KEY": ("groq-llama-70b", "console.groq.com"),
            "TOGETHER_API_KEY": ("together-llama-70b", "api.together.xyz"),
            "OPENROUTER_API_KEY": ("openrouter-free", "openrouter.ai"),
            "CF_API_TOKEN": ("cloudflare-llama", "dash.cloudflare.com"),
            "HF_TOKEN": ("huggingface", "huggingface.co/settings/tokens"),
        }

        configured = []
        missing = []

        for env_var, (model, url) in free_providers.items():
            if os.environ.get(env_var):
                lines.append(f"  ✅ {env_var} configured")
                configured.append(model)
            else:
                lines.append(f"  ❌ {env_var} missing - get from {url}")
                missing.append(env_var)

        lines.extend(
            [
                "",
                "🆓 FREE CLOUD MODELS",
                "─" * 30,
            ]
        )

        for name, info in MODELS.items():
            if info.get("free"):
                key_env = info.get("key_env", "")
                has_key = bool(os.environ.get(key_env)) if key_env else False
                status = "✅ Ready" if has_key else "🔑 Need key"
                lines.append(
                    f"  {info['params']:5} {name:22} {info['speed']:12} {status}"
                )

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

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "openrouter_smart_fallback":
        task = arguments.get("task", "general")
        health = check_health()

        lines = [
            "🧠 SMART FALLBACK",
            "═" * 50,
            "",
        ]

        # Check Claude availability
        if health["internet"] and health["claude_desktop"]:
            lines.append("✅ Claude available - normal routing")
            best = route_to_model(task)
        elif health["internet"]:
            lines.append("⚠️ Claude Desktop not running - checking free cloud...")
            lines.append("")

            # Try free cloud providers in order
            best = None
            for model in FALLBACK_CHAIN:
                info = MODELS.get(model, {})
                if info.get("offline"):
                    continue
                key_env = info.get("key_env")
                if key_env and os.environ.get(key_env):
                    best = model
                    lines.append(
                        f"  → Found: {model} ({info['params']} - {info['speed']})"
                    )
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

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "openrouter_chat":
        prompt = arguments.get("prompt", "")
        model = arguments.get("model")
        task = arguments.get("task", "general")

        if not model:
            model = route_to_model(task)

        info = MODELS.get(model, {})

        if info.get("provider") != "ollama":
            return [
                TextContent(
                    type="text",
                    text=f"⚠️ {model} is a cloud model. Use Claude Desktop or API directly.\n\nFor local chat, try: openrouter_chat(prompt='...', model='claude-emulator')",
                )
            ]

        try:
            start = time.time()
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )
            elapsed = time.time() - start

            response = f"""🤖 Response from {model}
═══════════════════════════════════════

{result.stdout.strip()}

───────────────────────────────────────
⏱️ {elapsed:.1f}s | 📦 {info.get('params', '?')} params | 💰 FREE"""

            return [TextContent(type="text", text=response)]

        except subprocess.TimeoutExpired:
            return [TextContent(type="text", text=f"⏱️ Timeout waiting for {model}")]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio

    print("🌐 OpenRouter MCP Server starting...", file=sys.stderr)
    asyncio.run(main())
