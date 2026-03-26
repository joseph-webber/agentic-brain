# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
🔥 SMART LLM ROUTER - MASTER/WORKER ARCHITECTURE 🔥

Claude is the MASTER THREAD - orchestrates, delegates, NEVER rate limited.
Other LLMs are WORKER THREADS - they do the heavy lifting.

Architecture:
    MASTER (Claude/Copilot)
        │
        ├── Worker: OpenAI (gpt-4o) - Complex code
        ├── Worker: Groq (llama-3.3) - FASTEST responses
        ├── Worker: Gemini (2.0-flash) - FREE, fast
        ├── Worker: DeepSeek (v3) - FREE credits
        ├── Worker: Together (llama-3.3) - FREE credits
        ├── Worker: Local Ollama - UNLIMITED
        └── Worker: OpenRouter (50+ models) - Fallback

Modes:
    - TURBO: Fire ALL workers, fastest wins
    - CONSENSUS: Fire 3+, compare results
    - CASCADE: Try FREE first, fall back to paid
    - DEDICATED: Route to best worker for task type

Usage:
    from agentic_brain.smart_router import SmartRouter, turbo_smash

    router = SmartRouter()
    result = await router.route("code", "Write a function...")

    # Or fire all at once
    result = await turbo_smash("Say hi!")
"""

from .core import SmartRouter, SmashMode, SmashResult
from .posture import PostureMode, SecurityPosture
from .workers import (
    AzureOpenAIWorker,
    DeepSeekWorker,
    GeminiWorker,
    GroqWorker,
    LocalWorker,
    OpenAIWorker,
    OpenRouterWorker,
    TogetherWorker,
)


class RedisCoordinator:  # pragma: no cover
    """Lazy proxy to avoid import-time cycles.

    Returns an instance of the real coordinator class.
    """

    def __new__(cls, *args, **kwargs):
        from .coordinator import RedisCoordinator as _RedisCoordinator

        return _RedisCoordinator(*args, **kwargs)


async def turbo_smash(prompt: str, timeout: float = 30.0, workers=None) -> SmashResult:
    """Lazy import wrapper for turbo smash."""

    from .coordinator import turbo_smash as _turbo_smash

    return await _turbo_smash(prompt, timeout=timeout, workers=workers)


async def cascade_smash(prompt: str, timeout: float = 30.0) -> SmashResult:
    """Lazy import wrapper for cascade smash."""

    from .coordinator import cascade_smash as _cascade_smash

    return await _cascade_smash(prompt, timeout=timeout)


__all__ = [
    "SmartRouter",
    "SmashMode",
    "SmashResult",
    "OpenAIWorker",
    "AzureOpenAIWorker",
    "GroqWorker",
    "GeminiWorker",
    "LocalWorker",
    "OpenRouterWorker",
    "TogetherWorker",
    "DeepSeekWorker",
    "RedisCoordinator",
    "turbo_smash",
    "cascade_smash",
    "SecurityPosture",
    "PostureMode",
]
