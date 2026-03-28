# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
SmartRouter package entrypoint.

The smart router is the “big hammer” for multi-provider orchestration: a fleet
of worker LLMs (OpenAI, Groq, Gemini, local Ollama, etc.) coordinated by a
single master (Claude/Copilot).  It focuses on parallelism, load shedding, and
security posture enforcement so we can smash tasks across providers without
hitting rate limits.

This subpackage exposes three core areas:

* `agentic_brain.smart_router.core` – routing logic, SmashMode, and result
  structures.
* `agentic_brain.smart_router.posture` – posture and security controls that
  decide which workers can participate.
* `agentic_brain.smart_router.workers` – concrete worker implementations for
  each provider.

Use these imports when you need to embed SmartRouter directly, or import
`agentic_brain.router.smart_router` for the thin compatibility shim.
"""

from .coordinator import warmup_ping
from .core import SmartRouter, SmashMode, SmashResult, WorkerConfig, get_router
from .posture import PostureMode, SecurityPosture, get_posture
from .workers import (
    AzureOpenAIWorker,
    DeepSeekWorker,
    GeminiWorker,
    GroqWorker,
    LocalWorker,
    OpenAIWorker,
    OpenRouterWorker,
    TogetherWorker,
    get_all_workers,
    get_worker,
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
    "WorkerConfig",
    "get_router",
    "OpenAIWorker",
    "AzureOpenAIWorker",
    "GroqWorker",
    "GeminiWorker",
    "LocalWorker",
    "OpenRouterWorker",
    "TogetherWorker",
    "DeepSeekWorker",
    "get_worker",
    "get_all_workers",
    "RedisCoordinator",
    "turbo_smash",
    "cascade_smash",
    "warmup_ping",
    "SecurityPosture",
    "PostureMode",
    "get_posture",
]
