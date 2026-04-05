#!/usr/bin/env python3
"""Multi-LLM orchestration engine — the brain's intelligence layer.

Strategies:
  - FASTEST:    Race multiple LLMs, return the first response.
  - SMARTEST:   Route to the best provider for the task type.
  - CONSENSUS:  Query 2-3 LLMs, merge the best parts.
  - FALLBACK:   Try providers in priority order until one succeeds.

This is the core that makes the voice system world-class.
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Sequence

from tools.voice.llm_providers import (
    LLMProvider,
    available_providers,
    get_provider,
    get_providers,
)


# ---------------------------------------------------------------------------
# Task-type specialisation routing
# ---------------------------------------------------------------------------

SPECIALISATION: dict[str, list[str]] = {
    "code": ["gpt", "claude", "ollama", "gemini", "grok"],
    "reasoning": ["claude", "gpt", "gemini", "grok", "ollama"],
    "creative": ["grok", "claude", "gpt", "gemini", "ollama"],
    "facts": ["gemini", "gpt", "claude", "grok", "ollama"],
    "speed": ["ollama", "gpt", "gemini", "grok", "claude"],
    "general": ["claude", "gpt", "gemini", "grok", "ollama"],
}

# Keywords that suggest a task type
_TASK_SIGNALS: dict[str, list[str]] = {
    "code": [
        "code",
        "python",
        "javascript",
        "typescript",
        "function",
        "class",
        "debug",
        "refactor",
        "regex",
        "json",
        "sql",
        "api",
        "script",
        "write a",
        "implement",
        "build a",
    ],
    "reasoning": [
        "explain",
        "why",
        "how does",
        "what if",
        "compare",
        "analyse",
        "analyze",
        "pros and cons",
        "trade-off",
        "should i",
        "reason",
    ],
    "creative": [
        "story",
        "poem",
        "creative",
        "imagine",
        "brainstorm",
        "idea",
        "funny",
        "joke",
        "name for",
        "slogan",
        "write me",
    ],
    "facts": [
        "what is",
        "who is",
        "when did",
        "where is",
        "how many",
        "define",
        "capital of",
        "population",
        "history of",
    ],
}


def detect_task_type(text: str) -> str:
    """Detect the task type from user text."""
    lower = text.lower()
    scores: dict[str, int] = {k: 0 for k in SPECIALISATION}
    for task_type, signals in _TASK_SIGNALS.items():
        for signal in signals:
            if signal in lower:
                scores[task_type] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


def _ordered_providers(task_type: str) -> list[str]:
    """Return provider names in preference order, filtering to available only."""
    avail = set(available_providers())
    preferred = SPECIALISATION.get(task_type, SPECIALISATION["general"])
    ordered = [p for p in preferred if p in avail]
    # Always ensure Ollama is last resort if available
    if "ollama" in avail and "ollama" not in ordered:
        ordered.append("ollama")
    return ordered


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


def strategy_fastest(
    messages: Sequence[dict[str, str]],
    *,
    task_type: str = "general",
    max_tokens: int = 200,
    temperature: float = 0.7,
    max_parallel: int = 3,
) -> dict[str, Any]:
    """Race multiple LLMs in parallel, return the first valid response.

    Returns dict with keys: text, provider, latency_ms, strategy.
    """
    providers_ordered = _ordered_providers(task_type)[:max_parallel]
    if not providers_ordered:
        raise RuntimeError("No LLM providers available")

    result: dict[str, Any] = {}
    t0 = time.monotonic()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as pool:
        future_to_name: dict[concurrent.futures.Future, str] = {}
        for name in providers_ordered:
            provider = get_provider(name)
            future = pool.submit(
                provider.call,
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            future_to_name[future] = name

        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            try:
                text = future.result()
                if text:
                    latency = (time.monotonic() - t0) * 1000
                    result = {
                        "text": text,
                        "provider": name,
                        "latency_ms": round(latency, 1),
                        "strategy": "fastest",
                    }
                    # Cancel remaining futures
                    for f in future_to_name:
                        if f is not future:
                            f.cancel()
                    return result
            except Exception:
                continue

    raise RuntimeError("All parallel LLM calls failed")


def strategy_smartest(
    messages: Sequence[dict[str, str]],
    *,
    task_type: str = "general",
    max_tokens: int = 200,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Route to the single best provider for this task type, with fallback.

    Returns dict with keys: text, provider, latency_ms, strategy.
    """
    providers_ordered = _ordered_providers(task_type)
    if not providers_ordered:
        raise RuntimeError("No LLM providers available")

    errors: list[str] = []
    for name in providers_ordered:
        provider = get_provider(name)
        t0 = time.monotonic()
        try:
            text = provider.call(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            latency = (time.monotonic() - t0) * 1000
            return {
                "text": text,
                "provider": name,
                "latency_ms": round(latency, 1),
                "strategy": "smartest",
                "task_type": task_type,
            }
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    raise RuntimeError(f"All providers failed: {'; '.join(errors)}")


def strategy_consensus(
    messages: Sequence[dict[str, str]],
    *,
    task_type: str = "general",
    max_tokens: int = 200,
    temperature: float = 0.7,
    num_providers: int = 2,
) -> dict[str, Any]:
    """Query multiple LLMs and merge into the best response.

    Uses a fast local LLM to synthesise the best answer from multiple providers.
    Falls back to the longest response if synthesis fails.
    """
    providers_ordered = _ordered_providers(task_type)[:num_providers]
    if not providers_ordered:
        raise RuntimeError("No LLM providers available")

    # Collect responses in parallel
    responses: list[tuple[str, str]] = []  # (provider_name, text)
    t0 = time.monotonic()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_providers) as pool:
        future_to_name: dict[concurrent.futures.Future, str] = {}
        for name in providers_ordered:
            provider = get_provider(name)
            future = pool.submit(
                provider.call,
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            future_to_name[future] = name

        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            try:
                text = future.result()
                if text:
                    responses.append((name, text))
            except Exception:
                continue

    if not responses:
        raise RuntimeError("No LLM responses for consensus")

    if len(responses) == 1:
        latency = (time.monotonic() - t0) * 1000
        return {
            "text": responses[0][1],
            "provider": responses[0][0],
            "latency_ms": round(latency, 1),
            "strategy": "consensus_single",
        }

    # Synthesise using Ollama (fast local model)
    synthesis_prompt = (
        "You are merging AI responses for a blind user. "
        "Pick the BEST parts of each response and combine them into ONE reply. "
        "Keep it to 2-3 sentences, natural and conversational. "
        "Never mention that you're merging responses.\n\n"
    )
    for name, text in responses:
        synthesis_prompt += f"Response from {name}:\n{text}\n\n"
    synthesis_prompt += (
        "Your merged response (2-3 sentences, spoken conversational style):"
    )

    synthesis_messages = [{"role": "user", "content": synthesis_prompt}]

    try:
        ollama = get_provider("ollama")
        merged = ollama.call(
            synthesis_messages,
            model="llama3.2:3b",
            max_tokens=150,
            temperature=0.5,
        )
    except Exception:
        # Fall back to the longest response
        merged = max(responses, key=lambda r: len(r[1]))[1]

    latency = (time.monotonic() - t0) * 1000
    return {
        "text": merged,
        "providers": [r[0] for r in responses],
        "provider": "consensus",
        "latency_ms": round(latency, 1),
        "strategy": "consensus",
        "individual_responses": {name: text for name, text in responses},
    }


def strategy_fallback(
    messages: Sequence[dict[str, str]],
    *,
    task_type: str = "general",
    max_tokens: int = 200,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Simple fallback chain — try each provider in order.

    Identical to strategy_smartest but named for clarity in config.
    """
    return strategy_smartest(
        messages,
        task_type=task_type,
        max_tokens=max_tokens,
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

STRATEGIES = {
    "fastest": strategy_fastest,
    "smartest": strategy_smartest,
    "consensus": strategy_consensus,
    "fallback": strategy_fallback,
}


def query_llm(
    messages: Sequence[dict[str, str]],
    *,
    strategy: str = "smartest",
    task_type: str | None = None,
    max_tokens: int = 200,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Main entry point: route a query through the multi-LLM engine.

    Args:
        messages: Chat messages (system + history + user).
        strategy: One of 'fastest', 'smartest', 'consensus', 'fallback'.
        task_type: Override auto-detected task type.
        max_tokens: Max response tokens.
        temperature: LLM temperature.

    Returns:
        dict with 'text', 'provider', 'latency_ms', 'strategy' keys.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}. Use: {list(STRATEGIES)}")

    # Auto-detect task type from the last user message
    if task_type is None:
        user_msgs = [m for m in messages if m["role"] == "user"]
        last_user = user_msgs[-1]["content"] if user_msgs else ""
        task_type = detect_task_type(last_user)

    fn = STRATEGIES[strategy]
    return fn(
        messages,
        task_type=task_type,
        max_tokens=max_tokens,
        temperature=temperature,
    )
