#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
"""Voice Reasoning Layer – Redis-coordinated intelligence for talk_to_karen.py.

Architecture
------------
                  ┌──────────────────────────────────────┐
  talk_to_karen ──► voice:current_input  (Redis key/pub)  │
                  │         │                             │
                  │  VoiceReasoningLayer                  │
                  │         │                             │
                  │   analyse complexity                  │
                  │   select best LLM                     │
                  │   build context from history          │
                  │         │                             │
                  │  voice:llm_recommendation (pub)       │
                  └──────────────────────────────────────┘

Redis keys used
---------------
  voice:current_input          STRING  – latest user utterance (set by Karen)
  voice:llm_recommendation     STRING  – JSON recommendation for Karen to consume
  voice:history                LIST    – last N (user/assistant) exchange pairs as JSON
  voice:claude_progress        STRING  – this agent's status string
  voice:gpt_progress           STRING  – GPT agent's status (read-only)
  voice:reasoning_complete     STRING  – set to "true" once initialised

Usage
-----
  # Run as a standalone daemon alongside talk_to_karen.py
  python tools/voice_reasoning.py daemon

  # Analyse a single query and print the recommendation
  python tools/voice_reasoning.py analyse "what's the weather like?"

  # Show the last 5 history entries
  python tools/voice_reasoning.py history
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

try:
    from tools.voice_event_bus import (
        VOICE_INPUT_TOPIC,
        VOICE_REASONING_TOPIC,
        VOICE_RESPONSE_TOPIC,
        create_voice_consumer,
        ensure_voice_topics,
        mark_redpanda_ready,
        publish_progress,
        publish_voice_event,
        set_voice_state,
    )
except ModuleNotFoundError:
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from voice_event_bus import (
        VOICE_INPUT_TOPIC,
        VOICE_REASONING_TOPIC,
        VOICE_RESPONSE_TOPIC,
        create_voice_consumer,
        ensure_voice_topics,
        mark_redpanda_ready,
        publish_progress,
        publish_voice_event,
        set_voice_state,
    )

# ---------------------------------------------------------------------------
# Redis connection (lazy import)
# ---------------------------------------------------------------------------
REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"

def _get_redis():
    import redis  # type: ignore
    return redis.from_url(REDIS_URL, decode_responses=True)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HISTORY_KEY = "voice:history"
INPUT_KEY = "voice:current_input"
RECOMMENDATION_KEY = "voice:llm_recommendation"
CLAUDE_PROGRESS_KEY = "voice:claude_progress"
GPT_PROGRESS_KEY = "voice:gpt_progress"
COMPLETE_KEY = "voice:reasoning_complete"
REASONING_KEY = "voice:current_reasoning"
RESPONSE_KEY = "voice:current_response"

HISTORY_MAX_PAIRS = 10          # store up to 10 user/assistant pairs
HISTORY_CONTEXT_PAIRS = 5       # use last 5 pairs when building context
DAEMON_POLL_SECONDS = 0.4       # how often to check for new input
RECOMMENDATION_TTL = 30         # seconds before recommendation expires
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

# Complexity thresholds (heuristic token count estimates)
SIMPLE_MAX_WORDS = 8
COMPLEX_MIN_WORDS = 25

# Model routing table
LLM_MODELS = {
    "simple": {
        "model": "llama3.2:3b",
        "reason": "Short factual query; fast local model is sufficient.",
        "max_tokens": 80,
        "temperature": 0.6,
    },
    "medium": {
        "model": "llama3.1:8b",
        "reason": "Moderate query; local 8-billion-param model handles it well.",
        "max_tokens": 120,
        "temperature": 0.7,
    },
    "complex": {
        "model": "llama3.1:8b",
        "reason": "Complex/multi-step query; use the larger local model.",
        "max_tokens": 200,
        "temperature": 0.75,
    },
}

# Karen's personality system prompt
KAREN_SYSTEM_PROMPT = (
    "You are Karen, a warm and witty Australian voice companion. "
    "The user relies entirely on audio – every response will be spoken aloud. "
    "Rules:\n"
    "1. ALWAYS reply in 2–3 short, punchy sentences – never more.\n"
    "2. Sound natural and conversational, like a mate having a chat.\n"
    "3. Occasionally use relaxed Australian expressions (no worries, heaps good, "
    "she'll be right, fair dinkum) but don't overdo it.\n"
    "4. If you don't know something, say so briefly and offer a practical suggestion.\n"
    "5. Never use bullet points, markdown, or lists – plain spoken sentences only.\n"
    "6. Be warm and caring; the user's independence and confidence matter to you."
)


# ---------------------------------------------------------------------------
# Complexity analysis
# ---------------------------------------------------------------------------

# Keywords that signal a complex, multi-step query
_COMPLEX_SIGNALS = frozenset({
    "explain", "how does", "why does", "compare", "difference between",
    "pros and cons", "step by step", "walk me through", "in detail",
    "summarise", "summarize", "what would happen", "analyse", "analyze",
    "history of", "background on", "what are all", "list every",
})

# Keywords that signal a simple greeting / status check
_SIMPLE_SIGNALS = frozenset({
    "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
    "yes", "no", "yep", "nope", "what time", "what's the time",
    "how are you", "what day", "stop", "bye", "goodbye",
})


def classify_complexity(text: str) -> str:
    """Return 'simple', 'medium', or 'complex' based on heuristics."""
    lower = text.lower().strip()
    words = lower.split()
    word_count = len(words)

    # Check explicit simple signals first
    if word_count <= SIMPLE_MAX_WORDS:
        for sig in _SIMPLE_SIGNALS:
            if lower.startswith(sig) or lower == sig:
                return "simple"

    # Check explicit complex signals
    for sig in _COMPLEX_SIGNALS:
        if sig in lower:
            return "complex"

    # Fall back to word-count heuristic
    if word_count <= SIMPLE_MAX_WORDS:
        return "simple"
    if word_count >= COMPLEX_MIN_WORDS:
        return "complex"
    return "medium"


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def push_history(r: Any, role: str, content: str) -> None:
    """Append a single role/content entry to the Redis history list."""
    entry = json.dumps({"role": role, "content": content, "ts": time.time()})
    r.lpush(HISTORY_KEY, entry)
    # Keep the list bounded
    r.ltrim(HISTORY_KEY, 0, HISTORY_MAX_PAIRS * 2 - 1)


def get_context_messages(r: Any) -> list[dict[str, str]]:
    """Return the last HISTORY_CONTEXT_PAIRS pairs in chronological order."""
    raw = r.lrange(HISTORY_KEY, 0, HISTORY_CONTEXT_PAIRS * 2 - 1)
    messages: list[dict[str, str]] = []
    for item in reversed(raw):  # lpush stores newest first; reverse = oldest first
        try:
            entry = json.loads(item)
            messages.append({"role": entry["role"], "content": entry["content"]})
        except (json.JSONDecodeError, KeyError):
            continue
    return messages


# ---------------------------------------------------------------------------
# Core recommendation builder
# ---------------------------------------------------------------------------

def build_recommendation(text: str, r: Any) -> dict[str, Any]:
    """Analyse *text* and return a full LLM recommendation dict."""
    complexity = classify_complexity(text)
    llm_cfg = LLM_MODELS[complexity]
    context_messages = get_context_messages(r)

    # Check what the GPT agent is up to (informational only)
    gpt_status = r.get(GPT_PROGRESS_KEY) or "unknown"

    recommendation: dict[str, Any] = {
        "query": text,
        "complexity": complexity,
        "model": llm_cfg["model"],
        "reason": llm_cfg["reason"],
        "max_tokens": llm_cfg["max_tokens"],
        "temperature": llm_cfg["temperature"],
        "system_prompt": KAREN_SYSTEM_PROMPT,
        "context_messages": context_messages,
        "context_length": len(context_messages),
        "gpt_agent_status": gpt_status,
        "timestamp": time.time(),
    }
    return recommendation


def analyse_and_publish(text: str, r: Any) -> dict[str, Any]:
    """Full pipeline: classify → build recommendation → publish to Redis."""
    rec = build_recommendation(text, r)

    r.set(RECOMMENDATION_KEY, json.dumps(rec), ex=RECOMMENDATION_TTL)
    r.publish(RECOMMENDATION_KEY, json.dumps(rec))

    # Record in history as a user turn
    push_history(r, "user", text)

    return rec


def generate_reply(text: str, recommendation: dict[str, Any]) -> str:
    messages = [{"role": "system", "content": recommendation["system_prompt"]}]
    messages.extend(recommendation["context_messages"])
    messages.append({"role": "user", "content": text})

    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": recommendation["model"],
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": recommendation["temperature"],
                "num_predict": recommendation["max_tokens"],
            },
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    reply = payload.get("message", {}).get("content", "").strip()
    if not reply:
        reply = "Sorry, I didn't get a proper reply from Ollama."
    return reply


def process_voice_input_event(event: dict[str, Any], r: Any) -> dict[str, Any]:
    text = str(event.get("text") or "").strip()
    if not text:
        raise ValueError("voice input event must include text")

    request_id = str(event.get("request_id") or f"voice-{int(time.time() * 1000)}")
    session_id = str(event.get("session_id") or "voice-session")

    set_voice_state(INPUT_KEY, text)
    publish_progress(
        "voice-reasoning-started",
        {
            "request_id": request_id,
            "session_id": session_id,
            "source": "voice_reasoning",
        },
    )

    recommendation = build_recommendation(text, r)
    reasoning_payload = {
        **recommendation,
        "request_id": request_id,
        "session_id": session_id,
        "source": "voice_reasoning",
    }
    r.set(RECOMMENDATION_KEY, json.dumps(reasoning_payload), ex=RECOMMENDATION_TTL)
    r.set(REASONING_KEY, json.dumps(reasoning_payload), ex=RECOMMENDATION_TTL)
    publish_voice_event(VOICE_REASONING_TOPIC, reasoning_payload)
    push_history(r, "user", text)

    reply = generate_reply(text, recommendation)
    response_payload = {
        "request_id": request_id,
        "session_id": session_id,
        "text": reply,
        "model": recommendation["model"],
        "complexity": recommendation["complexity"],
        "source": "voice_reasoning",
        "timestamp": time.time(),
    }
    r.set(RESPONSE_KEY, json.dumps(response_payload), ex=RECOMMENDATION_TTL)
    publish_voice_event(VOICE_RESPONSE_TOPIC, response_payload)
    push_history(r, "assistant", reply)
    publish_progress(
        "voice-response-published",
        {
            "request_id": request_id,
            "session_id": session_id,
            "model": recommendation["model"],
            "complexity": recommendation["complexity"],
        },
    )
    return response_payload


# ---------------------------------------------------------------------------
# Daemon loop
# ---------------------------------------------------------------------------

def _set_progress(r: Any, status: str) -> None:
    r.set(CLAUDE_PROGRESS_KEY, status)


def run_daemon() -> None:
    """Consume brain.voice.input and publish reasoning + response events."""
    r = _get_redis()
    ensure_voice_topics()
    _set_progress(r, "starting")
    print("[reasoning] Daemon starting up…", flush=True)
    publish_progress("voice-reasoning-daemon-starting", {"source": "voice_reasoning"})
    _set_progress(r, "ready")

    # Signal initialisation complete
    r.set(COMPLETE_KEY, "true")
    mark_redpanda_ready("true")
    print(f"[reasoning] Daemon ready. Watching {VOICE_INPUT_TOPIC}…", flush=True)

    consumer = create_voice_consumer(
        VOICE_INPUT_TOPIC,
        group_id="voice-reasoning",
        auto_offset_reset="latest",
        consumer_timeout_ms=1000,
    )

    try:
        while True:
            records = consumer.poll(timeout_ms=1000, max_records=10)
            for batch in records.values():
                for message in batch:
                    event = getattr(message, "value", message)
                    text = str(event.get("text") or "").strip()
                    if not text:
                        continue

                    _set_progress(r, f"analysing: {text[:40]}")
                    print(f"[reasoning] New input → '{text}'", flush=True)
                    response_payload = process_voice_input_event(event, r)
                    print(
                        f"[reasoning] → reply queued via {VOICE_RESPONSE_TOPIC} "
                        f"for request={response_payload['request_id']}",
                        flush=True,
                    )
                    _set_progress(r, f"done: {response_payload['request_id']}")
            time.sleep(DAEMON_POLL_SECONDS)

    except KeyboardInterrupt:
        _set_progress(r, "stopped")
        print("\n[reasoning] Daemon stopped.", flush=True)
    finally:
        consumer.close()


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def cmd_analyse(text: str) -> None:
    r = _get_redis()
    rec = analyse_and_publish(text, r)
    print(json.dumps(rec, indent=2))


def cmd_history() -> None:
    r = _get_redis()
    msgs = get_context_messages(r)
    if not msgs:
        print("(no history)")
        return
    for m in msgs:
        role = m["role"].upper().ljust(9)
        print(f"{role} {m['content']}")


def cmd_status() -> None:
    r = _get_redis()
    print("voice:claude_progress   :", r.get(CLAUDE_PROGRESS_KEY) or "(not set)")
    print("voice:gpt_progress      :", r.get(GPT_PROGRESS_KEY) or "(not set)")
    print("voice:reasoning_complete:", r.get(COMPLETE_KEY) or "(not set)")
    print("voice:history length    :", r.llen(HISTORY_KEY))
    rec_raw = r.get(RECOMMENDATION_KEY)
    if rec_raw:
        try:
            rec = json.loads(rec_raw)
            print(
                f"last recommendation     : complexity={rec.get('complexity')}, "
                f"model={rec.get('model')}"
            )
        except json.JSONDecodeError:
            print("last recommendation     : (parse error)")
    else:
        print("last recommendation     : (none)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

USAGE = """\
Usage:
  python tools/voice_reasoning.py daemon              # run as background service
  python tools/voice_reasoning.py analyse "<query>"   # one-shot analysis
  python tools/voice_reasoning.py history             # show conversation history
  python tools/voice_reasoning.py status              # show Redis coordination keys
"""


def main(argv: list[str] | None = None) -> int:
    args = (argv or sys.argv)[1:]
    if not args:
        print(USAGE)
        return 0

    cmd = args[0].lower()

    if cmd == "daemon":
        run_daemon()
    elif cmd == "analyse" and len(args) >= 2:
        cmd_analyse(" ".join(args[1:]))
    elif cmd == "history":
        cmd_history()
    elif cmd == "status":
        cmd_status()
    else:
        print(USAGE)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
