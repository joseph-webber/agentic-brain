#!/usr/bin/env python3
"""Voice complexity classifier — determines query routing.

Single source of truth for complexity classification across all voice components.
Replaces duplicated classifiers in talk_to_karen.py, voice_reasoning.py, and
voice_orchestrator.py.
"""

from __future__ import annotations

# Complexity levels
SIMPLE = "simple"
MEDIUM = "medium"
COMPLEX = "complex"

# Word count thresholds
SIMPLE_MAX_WORDS = 8
COMPLEX_MIN_WORDS = 18

# Greeting / short command signals
SIMPLE_SIGNALS = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "yes",
        "no",
        "yep",
        "nope",
        "what time",
        "what's the time",
        "how are you",
        "what day",
        "stop",
        "bye",
        "goodbye",
        "good morning",
        "good afternoon",
        "good evening",
        "cheers",
        "ta",
        "alright",
        "cool",
        "nice",
        "great",
    }
)

# Signals that indicate a complex, multi-step query
COMPLEX_SIGNALS = frozenset(
    {
        "explain",
        "how does",
        "why does",
        "compare",
        "difference between",
        "pros and cons",
        "step by step",
        "walk me through",
        "in detail",
        "summarise",
        "summarize",
        "what would happen",
        "analyse",
        "analyze",
        "history of",
        "background on",
        "what are all",
        "list every",
        "write code",
        "implement",
        "build",
        "create a",
        "design",
        "write a",
        "generate",
        "refactor",
        "debug",
        "script",
    }
)

# GPT-preferred signals (coding tasks)
GPT_SIGNALS = frozenset(
    {
        "use gpt",
        "use openai",
        "openai",
        "gpt",
        "write code",
        "python",
        "javascript",
        "typescript",
        "json",
        "regex",
        "refactor",
        "debug",
    }
)


def classify_complexity(text: str) -> str:
    """Return 'simple', 'medium', or 'complex' based on heuristics.

    This is the canonical classifier used by all voice components.
    """
    lower = text.lower().strip()
    words = lower.split()
    word_count = len(words)

    if not words:
        return SIMPLE

    # Short greetings and commands
    if word_count <= SIMPLE_MAX_WORDS:
        for sig in SIMPLE_SIGNALS:
            if lower == sig or lower.startswith(sig):
                return SIMPLE

    # Explicit complex signals
    for sig in COMPLEX_SIGNALS:
        if sig in lower:
            return COMPLEX

    # Word count heuristic
    if word_count <= SIMPLE_MAX_WORDS:
        return SIMPLE
    if word_count >= COMPLEX_MIN_WORDS:
        return COMPLEX

    return MEDIUM


def wants_gpt(text: str) -> bool:
    """Check if user explicitly requested GPT/coding mode."""
    lower = text.lower().strip()
    return any(sig in lower for sig in GPT_SIGNALS)


def classify_for_strategy(text: str) -> dict[str, str]:
    """Return both complexity and recommended strategy.

    Returns:
        dict with keys 'complexity' and 'strategy'.
    """
    complexity = classify_complexity(text)
    if complexity == SIMPLE:
        strategy = "fallback"  # fast local model, simple fallback chain
    elif complexity == COMPLEX:
        strategy = "smartest"  # route to best provider for task type
    else:
        strategy = "smartest"  # medium also benefits from smart routing

    return {"complexity": complexity, "strategy": strategy}
