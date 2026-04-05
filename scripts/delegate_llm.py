#!/usr/bin/env python3
"""
🚀 SMART LLM ROUTER - Maximum Performance, Zero Rate Limits!

Routes tasks to the BEST provider based on task type:
    CODE    → OpenAI (codex-level, fast, you have credit)
    FAST    → Groq (500 tok/sec, FREE) or Local
    QUALITY → OpenAI gpt-4o or Gemini Pro
    BULK    → Local (UNLIMITED) or Gemini (high limits)
    FREE    → Local → Gemini → Groq fallback chain

Usage:
    # Smart auto-routing (recommended)
    delegate "Review this code" --task code
    delegate "Quick question" --task fast
    delegate "Analyze deeply" --task quality

    # Direct provider
    delegate "..." --provider openai

    # Parallel race (first wins)
    delegate "..." --race

    # Bulk processing (uses unlimited local)
    delegate "..." --task bulk

Environment (loaded from ~/brain/.env):
    OPENAI_API_KEY   - Lots of credit, USE IT!
    GEMINI_API_KEY   - FREE, high daily limit
    GROQ_API_KEY     - FREE, 30 req/min limit
"""

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# Load env from ~/brain/.env
def load_env():
    env_file = Path.home() / "brain" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key and value and not os.getenv(key):
                    os.environ[key] = value


load_env()


# =============================================================================
# SMART ROUTING CONFIG
# =============================================================================


@dataclass
class ProviderConfig:
    name: str
    models: dict  # task_type -> model
    rate_limit: int = 0  # requests per minute, 0 = unlimited
    env_key: str = ""
    priority: int = 5


PROVIDERS: Dict[str, ProviderConfig] = {
    "local": ProviderConfig(
        name="Ollama (Local)",
        models={
            "fast": "llama3.2:3b",
            "code": "llama3.1:8b",
            "quality": "llama3.1:8b",
            "bulk": "llama3.2:3b",
        },
        rate_limit=0,  # UNLIMITED!
        priority=1,
    ),
    "openai": ProviderConfig(
        name="OpenAI",
        models={
            "fast": "gpt-4o-mini",
            "code": "gpt-4o",  # Best for code!
            "quality": "gpt-4o",
            "bulk": "gpt-4o-mini",
        },
        rate_limit=500,  # Very high limit
        env_key="OPENAI_API_KEY",
        priority=2,
    ),
    "gemini": ProviderConfig(
        name="Google Gemini",
        models={
            "fast": "models/gemini-2.0-flash",
            "code": "models/gemini-2.5-pro",  # Great for code
            "quality": "models/gemini-3-pro-preview",  # Latest!
            "bulk": "models/gemini-2.0-flash-lite",  # High limits
        },
        rate_limit=60,  # Per minute
        env_key="GEMINI_API_KEY",
        priority=3,
    ),
    "groq": ProviderConfig(
        name="Groq",
        models={
            "fast": "llama-3.3-70b-versatile",  # Latest fast model
            "code": "llama-3.3-70b-versatile",
            "quality": "llama-3.3-70b-versatile",
            "bulk": "llama-3.1-8b-instant",
        },
        rate_limit=30,  # Conservative
        env_key="GROQ_API_KEY",
        priority=4,
    ),
}

# Smart routing by task type
TASK_ROUTING = {
    "code": ["openai", "gemini", "local"],  # OpenAI best for code
    "fast": ["groq", "local", "gemini"],  # Groq fastest
    "quality": ["openai", "gemini", "local"],  # Best models first
    "bulk": ["local", "gemini", "groq"],  # Unlimited first
    "free": ["local", "gemini", "groq"],  # Free options
    "auto": ["openai", "gemini", "groq", "local"],  # Try best first
}


# Rate limit tracking
@dataclass
class RateLimiter:
    requests: list = field(default_factory=list)

    def can_request(self, limit: int, window: int = 60) -> bool:
        if limit == 0:
            return True
        now = time.time()
        self.requests = [t for t in self.requests if now - t < window]
        return len(self.requests) < limit

    def record(self):
        self.requests.append(time.time())


RATE_LIMITERS: Dict[str, RateLimiter] = {p: RateLimiter() for p in PROVIDERS}


# =============================================================================
# PROVIDER IMPLEMENTATIONS
# =============================================================================


async def call_local(prompt: str, model: str = "llama3.1:8b") -> str:
    """Local Ollama - UNLIMITED, always available."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            return f"ERROR: Ollama {response.status_code}"
    except Exception as e:
        return f"ERROR (local): {e}"


async def call_openai(prompt: str, model: str = "gpt-4o") -> str:
    """OpenAI - Best for code! You have credit, USE IT."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,  # Lower for code
            max_tokens=4096,
        )
        RATE_LIMITERS["openai"].record()
        return response.choices[0].message.content
    except ImportError:
        return "ERROR: pip install openai"
    except Exception as e:
        return f"ERROR (openai): {e}"


async def call_gemini(prompt: str, model: str = "gemini-2.0-flash") -> str:
    """Google Gemini - FREE, high daily limits."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
            ),
        )
        RATE_LIMITERS["gemini"].record()
        return response.text
    except ImportError:
        return "ERROR: pip install google-genai"
    except Exception as e:
        return f"ERROR (gemini): {e}"


async def call_groq(prompt: str, model: str = "llama-3.1-70b-versatile") -> str:
    """Groq - FREE, super fast (500 tok/sec)."""
    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4096,
        )
        RATE_LIMITERS["groq"].record()
        return response.choices[0].message.content
    except ImportError:
        return "ERROR: pip install groq"
    except Exception as e:
        return f"ERROR (groq): {e}"


CALLERS = {
    "local": call_local,
    "openai": call_openai,
    "gemini": call_gemini,
    "groq": call_groq,
}


# =============================================================================
# SMART ROUTING ENGINE
# =============================================================================


def is_available(provider: str) -> bool:
    """Check if provider is available and not rate limited."""
    config = PROVIDERS[provider]

    # Check API key
    if config.env_key and not os.getenv(config.env_key):
        return False

    # Check rate limit
    if not RATE_LIMITERS[provider].can_request(config.rate_limit):
        return False

    return True


async def smart_route(prompt: str, task: str = "auto") -> Tuple[str, str]:
    """
    Smart route to best available provider for this task.
    Returns (provider_used, response).
    """
    route = TASK_ROUTING.get(task, TASK_ROUTING["auto"])

    for provider in route:
        if not is_available(provider):
            continue

        config = PROVIDERS[provider]
        model = config.models.get(task, config.models.get("code"))

        result = await CALLERS[provider](prompt, model)

        if not result.startswith("ERROR"):
            return (provider, result)

    # All failed - try local as last resort
    return ("local", await call_local(prompt))


async def race_providers(prompt: str, providers: list = None) -> Tuple[str, str]:
    """Race multiple providers, return first success."""
    if providers is None:
        providers = ["openai", "gemini", "groq"]

    async def try_provider(p):
        if not is_available(p):
            return (p, "SKIPPED: not available")
        config = PROVIDERS[p]
        model = config.models["code"]
        result = await CALLERS[p](prompt, model)
        return (p, result)

    # Create tasks
    tasks = [asyncio.create_task(try_provider(p)) for p in providers]

    # Return first non-error result
    for coro in asyncio.as_completed(tasks):
        provider, result = await coro
        if not result.startswith("ERROR") and not result.startswith("SKIPPED"):
            # Cancel remaining tasks
            for t in tasks:
                t.cancel()
            return (provider, result)

    # All failed
    return ("none", "ERROR: All providers failed")


async def parallel_query(prompt: str, providers: list = None) -> Dict[str, str]:
    """Query multiple providers in parallel, return all results."""
    if providers is None:
        providers = ["local", "openai", "gemini"]

    async def query_one(p):
        if not is_available(p):
            return "SKIPPED: not available"
        config = PROVIDERS[p]
        return await CALLERS[p](prompt, config.models["code"])

    tasks = [query_one(p) for p in providers]
    results = await asyncio.gather(*tasks)
    return dict(zip(providers, results))


# =============================================================================
# STATUS & CLI
# =============================================================================


def check_status() -> Dict[str, Any]:
    """Check all providers status."""
    status = {}
    for name, config in PROVIDERS.items():
        available = True
        reason = "ready"

        if config.env_key and not os.getenv(config.env_key):
            available = False
            reason = "no API key"
        elif not RATE_LIMITERS[name].can_request(config.rate_limit):
            available = False
            reason = "rate limited"

        status[name] = {
            "name": config.name,
            "available": available,
            "reason": reason,
            "rate_limit": config.rate_limit or "unlimited",
            "recent_calls": len(RATE_LIMITERS[name].requests),
        }
    return status


def print_status():
    """Print colorful status."""
    print("\n🚀 SMART LLM ROUTER STATUS")
    print("=" * 50)

    status = check_status()
    for p, info in status.items():
        icon = "✅" if info["available"] else "❌"
        limit = info["rate_limit"]
        calls = info["recent_calls"]
        print(f"  {icon} {info['name']:20} [{limit}/min] ({calls} recent)")

    print("\n📋 TASK ROUTING:")
    for task, route in TASK_ROUTING.items():
        print(f"  {task:8} → {' → '.join(route)}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="🚀 Smart LLM Router - Maximum performance!",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("prompt", nargs="?", help="Prompt to send")
    parser.add_argument(
        "--task",
        "-t",
        default="auto",
        choices=["code", "fast", "quality", "bulk", "free", "auto"],
        help="Task type for smart routing",
    )
    parser.add_argument(
        "--provider",
        "-p",
        choices=["local", "openai", "gemini", "groq"],
        help="Force specific provider",
    )
    parser.add_argument("--file", "-f", help="Include file content")
    parser.add_argument(
        "--race", "-r", action="store_true", help="Race providers (first wins)"
    )
    parser.add_argument("--parallel", action="store_true", help="Query all providers")
    parser.add_argument("--status", "-s", action="store_true", help="Show status")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")

    args = parser.parse_args()

    if args.status:
        if args.json:
            print(json.dumps(check_status(), indent=2))
        else:
            print_status()
        return

    if not args.prompt:
        parser.print_help()
        return

    # Build prompt
    prompt = args.prompt
    if args.file:
        content = Path(args.file).read_text()
        prompt = f"{prompt}\n\n```\n{content}\n```"

    # Execute
    if args.race:
        provider, result = asyncio.run(race_providers(prompt))
    elif args.parallel:
        results = asyncio.run(parallel_query(prompt))
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for p, r in results.items():
                print(f"\n{'='*50}\n📡 {PROVIDERS[p].name}\n{'='*50}\n{r}")
        return
    elif args.provider:
        config = PROVIDERS[args.provider]
        model = config.models.get(args.task, config.models["code"])
        result = asyncio.run(CALLERS[args.provider](prompt, model))
        provider = args.provider
    else:
        provider, result = asyncio.run(smart_route(prompt, args.task))

    # Output
    if args.json:
        print(json.dumps({"provider": provider, "response": result}))
    else:
        print(f"[{provider}] {result}")


if __name__ == "__main__":
    main()
