# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Parallel execution helpers for SmartRouter.

The coordinator is responsible for the SmashMode behaviours that involve more
than one worker at a time (turbo, consensus, cascade, warmup pings).  It owns
the “fire everything” orchestration and the optional Redis-backed coordination
needed when multiple processes are smashing the same task.
"""

import asyncio
import time
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from .core import SmashMode, SmashResult, get_router
from .workers import get_all_workers, get_worker

if TYPE_CHECKING:
    from .workers import BaseWorker


WorkerFactoryPair = Tuple[
    Callable[[str], "BaseWorker"], Callable[[], List["BaseWorker"]]
]


def _resolve_worker_fns() -> WorkerFactoryPair:
    """Resolve worker factories from the currently-imported module.

    Some tests intentionally clear `sys.modules` entries under `agentic_brain.*`
    to validate lazy-loading. That can leave function objects alive while a new
    module instance is imported and patched. Resolving factories dynamically
    keeps patching/reload behavior deterministic.
    """

    import sys

    current_module = sys.modules.get("agentic_brain.smart_router.coordinator")
    if current_module is not None and hasattr(current_module, "get_worker"):
        return (
            current_module.get_worker,  # type: ignore[attr-defined]
            current_module.get_all_workers,  # type: ignore[attr-defined]
        )

    return get_worker, get_all_workers


class RedisCoordinator:
    """
    Redis-based coordination for distributed smashing.
    Falls back to in-memory if Redis unavailable.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.client = None
        self._in_memory_results: Dict[str, SmashResult] = {}

    async def connect(self) -> bool:
        """Connect to Redis (optional)"""
        try:
            import redis.asyncio as redis_lib

            self.client = redis_lib.from_url(self.redis_url)
            await self.client.ping()
            return True
        except Exception:
            self.client = None
            return False

    async def publish_result(self, result: SmashResult) -> bool:
        """Publish result - first one wins!"""
        if self.client:
            import json
            from dataclasses import asdict

            key = f"llm:response:{result.task_id}"
            won = await self.client.setnx(key, json.dumps(asdict(result)))
            if won:
                await self.client.expire(key, 300)
            return bool(won)
        else:
            # In-memory fallback
            if result.task_id not in self._in_memory_results:
                self._in_memory_results[result.task_id] = result
                return True
            return False


async def turbo_smash(
    prompt: str,
    timeout: float = 30.0,
    workers: Optional[List[str]] = None,
) -> SmashResult:
    """
    🔥 FIRE ALL LLMS - FASTEST WINS! 🔥

    This is the core function for maximum speed.
    Claude (master) fires all workers in parallel.
    First successful response wins.

    Args:
        prompt: The prompt to send to all workers
        timeout: Max time to wait
        workers: Specific workers to use (None = all)

    Returns:
        SmashResult from the fastest worker
    """
    task_id = str(uuid4())
    router = get_router()

    get_worker_fn, get_all_workers_fn = _resolve_worker_fns()

    # Get workers to fire
    if workers:
        worker_instances = [get_worker_fn(w) for w in workers]
    else:
        worker_instances = get_all_workers_fn()

    async def fire_worker(worker: "BaseWorker") -> SmashResult:
        """Fire a single worker."""
        start = time.time()
        try:
            result_dict = await worker.execute(prompt)
            elapsed = time.time() - start

            # Add heat to router
            router.add_heat(worker.name)

            return SmashResult(
                task_id=task_id,
                provider=worker.name,
                response=result_dict.get("response", ""),
                elapsed=elapsed,
                success=result_dict.get("success", False),
                mode=SmashMode.TURBO,
                tokens=result_dict.get("tokens", 0),
            )
        except Exception as e:
            return SmashResult(
                task_id=task_id,
                provider=worker.name,
                response=str(e),
                elapsed=time.time() - start,
                success=False,
                mode=SmashMode.TURBO,
            )

    # 🔥 FIRE ALL WORKERS IN PARALLEL! 🔥
    tasks = [asyncio.create_task(fire_worker(w)) for w in worker_instances]

    # Wait for first successful completion
    done = set()
    pending = set(tasks)
    winner = None

    start_time = time.time()
    while pending and (time.time() - start_time) < timeout:
        newly_done, pending = await asyncio.wait(
            pending, timeout=0.1, return_when=asyncio.FIRST_COMPLETED
        )
        done.update(newly_done)

        # Check for winner
        for task in newly_done:
            result = task.result()
            if result.success:
                winner = result
                break

        if winner:
            break

    # Cancel remaining tasks
    for task in pending:
        task.cancel()

    # Record stats
    for task in done:
        try:
            result = task.result()
            router.record_result(result)
        except Exception:
            pass

    if winner:
        return winner

    # Return best failure if no success
    for task in done:
        try:
            return task.result()
        except Exception:
            pass

    return SmashResult(
        task_id=task_id,
        provider="none",
        response="All workers failed or timed out",
        elapsed=timeout,
        success=False,
        mode=SmashMode.TURBO,
    )


async def cascade_smash(
    prompt: str,
    timeout: float = 30.0,
) -> SmashResult:
    """
    💰 CASCADE MODE - Try FREE workers first, paid as fallback

    Order: Groq → Gemini → Local → Together → OpenRouter → OpenAI
    """
    cascade_order = ["groq", "gemini", "local", "together", "openrouter", "openai"]
    task_id = str(uuid4())

    get_worker_fn, _ = _resolve_worker_fns()

    for worker_name in cascade_order:
        try:
            worker = get_worker_fn(worker_name)
            start = time.time()
            result_dict = await asyncio.wait_for(
                worker.execute(prompt), timeout=timeout
            )

            if result_dict.get("success"):
                return SmashResult(
                    task_id=task_id,
                    provider=worker_name,
                    response=result_dict.get("response", ""),
                    elapsed=time.time() - start,
                    success=True,
                    mode=SmashMode.CASCADE,
                )
        except Exception:
            continue

    return SmashResult(
        task_id=task_id,
        provider="none",
        response="All cascade workers failed",
        elapsed=timeout,
        success=False,
        mode=SmashMode.CASCADE,
    )


async def warmup_ping() -> Dict[str, Optional[float]]:
    """
    🏁 WARMUP PING - Measure all worker response times

    Call this on session start to know who's fastest TODAY.
    Returns dict of worker_name -> response_time_seconds
    """
    prompt = "Say 'ready' in one word."
    workers = get_all_workers()
    results = {}

    async def ping_worker(worker):
        start = time.time()
        try:
            result = await asyncio.wait_for(worker.execute(prompt), timeout=10.0)
            elapsed = time.time() - start
            if result.get("success"):
                return worker.name, elapsed
            return worker.name, None
        except Exception:
            return worker.name, None

    tasks = [ping_worker(w) for w in workers]
    pings = await asyncio.gather(*tasks)

    for name, elapsed in pings:
        results[name] = elapsed

    return results
