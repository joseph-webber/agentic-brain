# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
SmartRouter core primitives.

SmartRouter is the “big hammer” router: it spins up multiple worker LLMs in
parallel, enforces SmashMode semantics, and honors the currently selected
SecurityPosture.  Reach for it when you need speed (fire many workers at once),
resilience (automatic fallbacks), or posture-aware routing.

How it compares to the other router layers:

* **LLMRouter** (``agentic_brain.llm.router``) provides a predictable,
  provider-agnostic chat surface.  Use it when you want deterministic retries,
  message normalization, and per-request cost tracking for a single prompt.
* **LLMRouterCore** is the minimal building block that powers LLMRouter’s alias
  resolution and retry logic.  Use it when you are embedding router behaviour
  inside another service and need full control.
* **SmartRouter** sits above both: it coordinates many LLM workers at once,
  keeps heat maps/cost awareness, and respects security posture constraints.

In short: use SmartRouter for orchestration and SmashMode semantics, LLMRouter
for consistent single-request routing, and LLMRouterCore when rolling your own
lightweight adapter.
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import uuid4

from .workers import get_worker

if TYPE_CHECKING:
    from .posture import SecurityPosture


class SmashMode(Enum):
    """Execution strategy used by SmartRouter.

    The SmashMode determines how aggressively we fan out to workers:

    * ``TURBO`` – fire every eligible worker in parallel and keep the first
      successful response.
    * ``CONSENSUS`` – race a curated subset and capture their outputs for human
      comparison.
    * ``CASCADE`` – walk through a prioritized list, preferring free/local
      workers before falling back to paid clouds.
    * ``DEDICATED`` – route to a single “best fit” worker sequence for the
      requested task type.
    """

    TURBO = "turbo"
    CONSENSUS = "consensus"
    CASCADE = "cascade"
    DEDICATED = "dedicated"


@dataclass
class SmashResult:
    """Result produced by an individual smash attempt."""

    task_id: str
    provider: str
    response: str
    elapsed: float
    success: bool
    mode: SmashMode = SmashMode.TURBO
    cost: float = 0.0
    tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerConfig:
    """Configuration metadata for a worker LLM."""

    name: str
    model: str
    api_key_env: str
    endpoint: str
    rate_limit: int = 60  # requests per minute
    cost_per_1k: float = 0.0
    is_free: bool = False
    is_local: bool = False
    typical_latency: float = 5.0  # seconds
    enabled: bool = True


class SmartRouter:
    """
    Master/Worker LLM Router

    Claude (master) delegates to worker LLMs for:
    - Maximum speed (parallel execution)
    - Rate limit protection (spread load)
    - Cost optimization (free first)
    - Reliability (multiple fallbacks)
    """

    # Task type to best worker mapping
    TASK_ROUTES: Dict[str, List[str]] = {
        "code": ["openai", "azure_openai", "groq", "local"],
        "fast": ["groq", "gemini", "local"],
        "free": ["gemini", "groq", "local", "together"],
        "bulk": ["local", "together", "groq"],
        "complex": ["openai", "deepseek", "groq"],
        "creative": ["openai", "gemini", "groq"],
    }

    def __init__(self) -> None:
        self.workers: Dict[str, WorkerConfig] = {}
        self.heat_map: Dict[str, float] = {}  # Track recent usage
        self.stats: Dict[str, Dict[str, Any]] = {}
        self._setup_default_workers()

    def _setup_default_workers(self) -> None:
        """Populate the default worker configurations."""
        defaults = [
            WorkerConfig(
                "openai",
                "gpt-4o-mini",
                "OPENAI_API_KEY",
                "https://api.openai.com/v1/chat/completions",
                rate_limit=500,
                cost_per_1k=0.00015,
                typical_latency=8.0,
            ),
            WorkerConfig(
                "azure_openai",
                "gpt-4o",
                "AZURE_OPENAI_API_KEY",
                os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
                rate_limit=500,
                cost_per_1k=0.0002,
                typical_latency=8.0,
            ),
            WorkerConfig(
                "groq",
                "llama-3.3-70b-versatile",
                "GROQ_API_KEY",
                "https://api.groq.com/openai/v1/chat/completions",
                rate_limit=30,
                is_free=True,
                typical_latency=1.5,
            ),
            WorkerConfig(
                "gemini",
                "gemini-2.0-flash",
                "GOOGLE_API_KEY",
                "https://generativelanguage.googleapis.com/v1beta/models",
                rate_limit=60,
                is_free=True,
                typical_latency=0.5,
            ),
            WorkerConfig(
                "local",
                "llama3.1:8b",
                "",
                "http://localhost:11434/api/generate",
                rate_limit=9999,
                is_free=True,
                is_local=True,
                typical_latency=5.0,
            ),
            WorkerConfig(
                "together",
                "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "TOGETHER_API_KEY",
                "https://api.together.xyz/v1/chat/completions",
                rate_limit=60,
                is_free=True,
                typical_latency=2.0,
            ),
            WorkerConfig(
                "deepseek",
                "deepseek-chat",
                "DEEPSEEK_API_KEY",
                "https://api.deepseek.com/v1/chat/completions",
                rate_limit=60,
                is_free=True,
                typical_latency=2.0,
            ),
            WorkerConfig(
                "openrouter",
                "auto",
                "OPENROUTER_API_KEY",
                "https://openrouter.ai/api/v1/chat/completions",
                rate_limit=20,
                is_free=True,
                typical_latency=3.0,
            ),
        ]
        for w in defaults:
            self.workers[w.name] = w
            self.heat_map[w.name] = 0.0
            self.stats[w.name] = {"requests": 0, "successes": 0, "total_time": 0.0}

    def get_route(self, task_type: str) -> List[str]:
        """Get the preferred worker order for a task type."""
        return self.TASK_ROUTES.get(task_type, ["groq", "gemini", "local"])

    async def route(
        self,
        task_type: str,
        prompt: str,
        mode: SmashMode = SmashMode.DEDICATED,
        timeout: float = 30.0,
        workers: Optional[List[str]] = None,
        posture: Optional["SecurityPosture"] = None,
    ) -> SmashResult:
        """Route a prompt to the best worker(s) based on task type and mode."""
        if mode == SmashMode.TURBO:
            from .coordinator import turbo_smash

            return await turbo_smash(prompt, timeout=timeout, workers=workers)
        if mode == SmashMode.CASCADE:
            from .coordinator import cascade_smash

            return await cascade_smash(prompt, timeout=timeout)

        worker_names = workers or self.get_route(task_type)
        if posture is not None:
            worker_names = posture.filter_workers(worker_names)
            if posture.prefer_free_workers:
                worker_names = sorted(
                    worker_names,
                    key=lambda name: (
                        not self.workers.get(
                            name, WorkerConfig(name, "", "", "")
                        ).is_free,
                        self.heat_map.get(name, 0),
                    ),
                )

        if mode == SmashMode.CONSENSUS:
            from .coordinator import turbo_smash

            coolest = self.get_coolest_workers(3)
            consensus_workers = [
                w for w in worker_names if w in coolest
            ] or worker_names
            result = await turbo_smash(
                prompt, timeout=timeout, workers=consensus_workers
            )
            result.mode = SmashMode.CONSENSUS
            result.metadata["workers"] = consensus_workers
            return result

        # Dedicated routing with fallback
        for worker_name in worker_names:
            start = time.time()
            try:
                worker = get_worker(worker_name)
                result_dict = await asyncio.wait_for(
                    worker.execute(prompt), timeout=timeout
                )
                elapsed = time.time() - start

                self.add_heat(worker_name)
                result = SmashResult(
                    task_id=str(uuid4()),
                    provider=worker_name,
                    response=result_dict.get("response", ""),
                    elapsed=elapsed,
                    success=result_dict.get("success", False),
                    mode=SmashMode.DEDICATED,
                    tokens=result_dict.get("tokens", 0),
                    metadata={"status_code": result_dict.get("status_code")},
                )
                self.record_result(result)
                if result.success:
                    return result
            except Exception as e:
                result = SmashResult(
                    task_id=str(uuid4()),
                    provider=worker_name,
                    response=str(e),
                    elapsed=time.time() - start,
                    success=False,
                    mode=SmashMode.DEDICATED,
                )
                self.record_result(result)
                continue

        return SmashResult(
            task_id=str(uuid4()),
            provider="none",
            response="No workers succeeded for task",
            elapsed=timeout,
            success=False,
            mode=SmashMode.DEDICATED,
        )

    def get_coolest_workers(self, n: int = 3) -> List[str]:
        """Return the ``n`` least-used workers (lowest heat)."""
        sorted_workers = sorted(self.heat_map.items(), key=lambda x: x[1])
        return [w[0] for w in sorted_workers[:n] if self.workers[w[0]].enabled]

    def add_heat(self, worker: str, amount: float = 1.0) -> None:
        """Increment heat for a worker to track recent usage."""
        self.heat_map[worker] = self.heat_map.get(worker, 0) + amount

    def cool_down(self, rate: float = 0.1) -> None:
        """Cool down all workers over time."""
        for w in self.heat_map:
            self.heat_map[w] = max(0, self.heat_map[w] - rate)

    def record_result(self, result: SmashResult) -> None:
        """Record basic stats from a worker result."""
        stats = self.stats.setdefault(
            result.provider, {"requests": 0, "successes": 0, "total_time": 0.0}
        )
        stats["requests"] += 1
        if result.success:
            stats["successes"] += 1
        stats["total_time"] += result.elapsed

    def get_status(self) -> Dict[str, Any]:
        """Expose heat/stats info for observability dashboards."""
        return {
            "workers": {
                name: {
                    "enabled": w.enabled,
                    "is_free": w.is_free,
                    "heat": self.heat_map.get(name, 0),
                    "stats": self.stats.get(name, {}),
                }
                for name, w in self.workers.items()
            },
            "coolest": self.get_coolest_workers(3),
            "free_workers": [
                n for n, w in self.workers.items() if w.is_free and w.enabled
            ],
        }


# Singleton instance
_router: Optional[SmartRouter] = None


def get_router() -> SmartRouter:
    """Return the singleton SmartRouter instance."""
    global _router
    if _router is None:
        _router = SmartRouter()
    return _router
