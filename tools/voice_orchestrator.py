#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
"""Voice Orchestrator – Redpanda-driven smart LLM routing for Karen.

Architecture
------------
  brain.voice.input  (Redpanda via HTTP REST proxy)
         ↓
  [VoiceOrchestrator]  ← voice:history (Redis, last 3 exchanges)
         ↓ route by complexity
  Ollama / Claude / GPT  (fallback chain)
         ↓
  brain.voice.response  (Redpanda via HTTP REST proxy)
         ↓
  Cartesia TTS → Karen speaks

Coordination
------------
  brain.voice.coordination (Redpanda) – peer agent messages
  voice:claude_orchestrator_progress  (Redis) – this agent's status
  voice:orchestrator_ready            (Redis) – "true" once initialised
  voice:history                       (Redis LIST) – conversation memory

Transport
---------
  Uses Redpanda Pandaproxy HTTP REST API (port 8082) for produce/consume.
  This bypasses kafka-python TCP issues with Docker-advertised broker addresses.
  Topic admin via rpk (docker exec agentic-brain-redpanda).

Usage
-----
  python tools/voice_orchestrator.py daemon    # run as background service
  python tools/voice_orchestrator.py test      # send a test query
  python tools/voice_orchestrator.py status    # show Redis/Redpanda state
  python tools/voice_orchestrator.py topics    # list voice topics
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PANDAPROXY = "http://localhost:8082"  # Redpanda HTTP REST proxy
REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
OLLAMA_URL = "http://localhost:11434"
POLL_INTERVAL = 0.5  # seconds between consume polls


# Load Claude API key from env / .env file
def _load_claude_key() -> str:
    key = os.environ.get("CLAUDE_API_KEY", "")
    if not key:
        env_path = Path(__file__).parents[2] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("CLAUDE_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    return key


CLAUDE_API_KEY = _load_claude_key()

# Topics
TOPIC_INPUT = "brain.voice.input"
TOPIC_RESPONSE = "brain.voice.response"
TOPIC_COORDINATION = "brain.voice.coordination"

# Redis keys
REDIS_PROGRESS_KEY = "voice:claude_orchestrator_progress"
REDIS_READY_KEY = "voice:orchestrator_ready"
REDIS_HISTORY_KEY = "voice:history"
REDIS_GPT_KEY = "voice:gpt_redpanda_progress"

# Memory
HISTORY_MAX_PAIRS = 6  # store up to 6 role/content entries (3 exchanges)
HISTORY_CONTEXT_PAIRS = 3  # include last 3 exchanges in LLM context

# Consumer group
CONSUMER_GROUP = "voice-orchestrator"
CONSUMER_ID = "orchestrator-1"

# ---------------------------------------------------------------------------
# Karen's personality prompt
# ---------------------------------------------------------------------------
KAREN_SYSTEM = (
    "You are Karen, a warm and friendly Australian AI assistant. "
    "The user relies on audio, so every response you give will be spoken aloud by a text-to-speech engine. "
    "Keep responses to 2-3 sentences — clear, conversational, and easy to listen to. "
    "You have a sense of humour and a caring nature. "
    "You remember the conversation context and refer back to it naturally. "
    "Never use bullet points, markdown, or long lists — just natural spoken sentences."
)

# ---------------------------------------------------------------------------
# Complexity classifier (mirrors voice_reasoning.py so recommendations align)
# ---------------------------------------------------------------------------
_SIMPLE_WORDS = {
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank",
    "you",
    "bye",
    "goodbye",
    "yes",
    "no",
    "ok",
    "okay",
    "sure",
    "great",
    "cool",
    "nice",
    "good",
    "cheers",
    "ta",
    "yep",
    "nope",
    "alright",
    "right",
    "got",
    "it",
}


def classify_complexity(text: str) -> str:
    """Return 'simple', 'medium', or 'complex'."""
    lower = text.lower().strip()
    words = lower.split()
    if not words:
        return "simple"
    # Short greetings / acknowledgements → simple
    if len(words) <= 5 and set(words).issubset(_SIMPLE_WORDS):
        return "simple"
    # Explicit complexity signals
    complex_signals = [
        "write",
        "code",
        "script",
        "explain",
        "how does",
        "why does",
        "analyse",
        "analyze",
        "compare",
        "difference",
        "create",
        "build",
        "implement",
        "generate",
        "summarise",
        "summarize",
        "design",
    ]
    for sig in complex_signals:
        if sig in lower:
            return "complex"
    if len(words) <= 12:
        return "medium"
    return "complex"


# LLM routing table: complexity → preferred provider
_ROUTING: dict[str, list[str]] = {
    "simple": ["ollama", "claude", "gpt"],
    "medium": ["claude", "ollama", "gpt"],
    "complex": ["claude", "gpt", "ollama"],
}

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------
_redis_client: Any = None


def _redis() -> Any:
    global _redis_client
    if _redis_client is None:
        import redis as _r

        _redis_client = _r.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


# ---------------------------------------------------------------------------
# Redpanda REST transport (Pandaproxy on port 8082)
# ---------------------------------------------------------------------------


def _rest_post(
    path: str, body: Any, content_type: str = "application/vnd.kafka.json.v2+json"
) -> Any:
    """POST to Pandaproxy and return parsed JSON response."""
    url = f"{PANDAPROXY}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": content_type,
            "Accept": "application/vnd.kafka.v2+json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _rest_get(path: str, accept: str = "application/vnd.kafka.json.v2+json") -> Any:
    """GET from Pandaproxy and return parsed JSON."""
    url = f"{PANDAPROXY}{path}"
    req = urllib.request.Request(url, headers={"Accept": accept})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def rest_produce(topic: str, value: dict, key: str | None = None) -> None:
    """Produce one JSON message to a Redpanda topic via HTTP REST."""
    record: dict[str, Any] = {"value": value}
    if key:
        record["key"] = key
    _rest_post(f"/topics/{topic}", {"records": [record]})


class RestConsumer:
    """Long-poll consumer via Pandaproxy REST API."""

    def __init__(
        self,
        group: str,
        instance: str,
        topics: list[str],
        offset_reset: str = "earliest",
    ):
        self._group = group
        self._instance = instance
        self._base = f"/consumers/{group}/instances/{instance}"
        self._topics = topics
        # Create consumer instance (Pandaproxy only supports "earliest")
        try:
            _rest_post(
                f"/consumers/{group}",
                {"name": instance, "format": "json", "auto.offset.reset": "earliest"},
                content_type="application/vnd.kafka.v2+json",
            )
        except urllib.error.HTTPError as e:
            if e.code != 409:  # 409 = already exists, fine
                raise
        # Subscribe – response body may be empty (204/200)
        try:
            req_url = f"{PANDAPROXY}{self._base}/subscription"
            data = json.dumps({"topics": topics}).encode()
            req = urllib.request.Request(
                req_url,
                data=data,
                method="POST",
                headers={
                    "Content-Type": "application/vnd.kafka.v2+json",
                    "Accept": "application/vnd.kafka.v2+json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass  # 200/204, body may be empty
        except urllib.error.HTTPError as e:
            if e.code not in (200, 204):
                raise

    def poll(self, max_bytes: int = 65536, timeout_ms: int = 500) -> list[dict]:
        """Return list of records (may be empty)."""
        try:
            url = f"{PANDAPROXY}{self._base}/records?max_bytes={max_bytes}&timeout={timeout_ms}"
            req = urllib.request.Request(
                url, headers={"Accept": "application/vnd.kafka.json.v2+json"}
            )
            with urllib.request.urlopen(req, timeout=timeout_ms // 1000 + 5) as resp:
                body = resp.read()
                if not body:
                    return []
                records = json.loads(body)
                return records if isinstance(records, list) else []
        except Exception:
            return []

    def delete(self) -> None:
        url = f"{PANDAPROXY}{self._base}"
        req = urllib.request.Request(
            url,
            method="DELETE",
            headers={"Content-Type": "application/vnd.kafka.v2+json"},
        )
        try:
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Redis history helpers
# ---------------------------------------------------------------------------


def push_history(role: str, content: str) -> None:
    r = _redis()
    entry = json.dumps({"role": role, "content": content, "ts": time.time()})
    r.lpush(REDIS_HISTORY_KEY, entry)
    r.ltrim(REDIS_HISTORY_KEY, 0, HISTORY_MAX_PAIRS - 1)


def get_context_messages() -> list[dict[str, str]]:
    r = _redis()
    raw = r.lrange(REDIS_HISTORY_KEY, 0, HISTORY_CONTEXT_PAIRS * 2 - 1)
    messages: list[dict[str, str]] = []
    for item in reversed(raw):  # lpush = newest first; reverse = chronological
        try:
            e = json.loads(item)
            messages.append({"role": e["role"], "content": e["content"]})
        except (json.JSONDecodeError, KeyError):
            continue
    return messages


# ---------------------------------------------------------------------------
# LLM callers
# ---------------------------------------------------------------------------


def _call_ollama(query: str, context: list[dict]) -> str | None:
    """Call local Ollama. Returns text or None on failure."""
    try:
        import urllib.request

        messages = [{"role": "system", "content": KAREN_SYSTEM}]
        messages.extend(context)
        messages.append({"role": "user", "content": query})
        payload = json.dumps(
            {
                "model": "llama3.2:3b",
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 200},
            }
        ).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("message", {}).get("content", "").strip()
    except Exception as exc:
        print(f"[orchestrator] Ollama error: {exc}", flush=True)
        return None


def _call_claude(query: str, context: list[dict]) -> str | None:
    """Call Claude API. Returns text or None on failure."""
    if not CLAUDE_API_KEY:
        return None
    try:
        import urllib.request

        messages = list(context)
        messages.append({"role": "user", "content": query})
        payload = json.dumps(
            {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 300,
                "system": KAREN_SYSTEM,
                "messages": messages,
            }
        ).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            blocks = data.get("content", [])
            text = " ".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            )
            return text.strip() or None
    except Exception as exc:
        print(f"[orchestrator] Claude error: {exc}", flush=True)
        return None


def _call_gpt(query: str, context: list[dict]) -> str | None:
    """GPT stub – checks Redis for a live GPT agent to delegate."""
    try:
        gpt_status = _redis().get(REDIS_GPT_KEY) or ""
        if "ready" in gpt_status.lower():
            rest_produce(
                TOPIC_COORDINATION,
                {
                    "type": "gpt_request",
                    "query": query,
                    "context": context,
                    "ts": time.time(),
                },
                key="gpt_request",
            )
            # Give GPT agent 10s to respond via Redis
            for _ in range(20):
                time.sleep(0.5)
                reply = _redis().get("voice:gpt_response")
                if reply:
                    _redis().delete("voice:gpt_response")
                    return reply
        return None
    except Exception as exc:
        print(f"[orchestrator] GPT delegation error: {exc}", flush=True)
        return None


def route_and_respond(query: str, complexity: str) -> tuple[str, str]:
    """Try providers in preference order. Returns (response_text, provider_used)."""
    context = get_context_messages()
    providers = _ROUTING[complexity]

    caller_map = {
        "ollama": _call_ollama,
        "claude": _call_claude,
        "gpt": _call_gpt,
    }

    for provider in providers:
        _set_progress(f"calling_{provider}: {query[:40]}")
        result = caller_map[provider](query, context)
        if result:
            return result, provider

    # Hard fallback: honest minimal answer
    return (
        "Sorry, I'm having a bit of trouble connecting right now. Give me a moment and try again!",
        "fallback",
    )


# ---------------------------------------------------------------------------
# Progress helper
# ---------------------------------------------------------------------------


def _set_progress(status: str) -> None:
    try:
        _redis().set(REDIS_PROGRESS_KEY, status)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Message processor
# ---------------------------------------------------------------------------


def process_input_message(msg_value: dict) -> None:
    """Handle one brain.voice.input message end-to-end."""
    query: str = msg_value.get("text", "").strip()
    session_id: str = msg_value.get("session_id", "default")
    request_id: str = msg_value.get("request_id", str(time.time()))

    if not query:
        return

    print(f"[orchestrator] ← '{query}'", flush=True)
    _set_progress(f"routing: {query[:40]}")

    complexity = classify_complexity(query)
    print(f"[orchestrator] complexity={complexity}", flush=True)

    # Push user turn into history
    push_history("user", query)

    # Route to best LLM
    t0 = time.time()
    response_text, provider = route_and_respond(query, complexity)
    latency_ms = int((time.time() - t0) * 1000)

    # Push assistant turn into history
    push_history("assistant", response_text)

    print(
        f"[orchestrator] → [{provider}] {latency_ms}ms: {response_text[:80]}",
        flush=True,
    )
    _set_progress(f"done: {provider}/{complexity}/{latency_ms}ms")

    # Publish to brain.voice.response
    response_envelope = {
        "text": response_text,
        "provider": provider,
        "complexity": complexity,
        "latency_ms": latency_ms,
        "session_id": session_id,
        "request_id": request_id,
        "ts": time.time(),
    }
    try:
        rest_produce(TOPIC_RESPONSE, response_envelope, key=session_id)
    except Exception as exc:
        print(f"[orchestrator] Failed to publish response: {exc}", flush=True)

    # Broadcast coordination event so peer agents stay informed
    try:
        rest_produce(
            TOPIC_COORDINATION,
            {
                "type": "response_generated",
                "provider": provider,
                "complexity": complexity,
                "latency_ms": latency_ms,
                "ts": time.time(),
            },
            key="orchestrator_event",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Coordination message handler (runs in background thread)
# ---------------------------------------------------------------------------


def _coordination_listener() -> None:
    """Listen to brain.voice.coordination and act on peer agent messages."""
    try:
        consumer = RestConsumer(
            group=f"{CONSUMER_GROUP}-coord",
            instance="coord-1",
            topics=[TOPIC_COORDINATION],
            offset_reset="latest",
        )
        print("[orchestrator] Coordination listener active.", flush=True)
        while True:
            records = consumer.poll()
            for rec in records:
                evt = rec.get("value", {})
                etype = evt.get("type", "")
                if etype == "gpt_agent_ready":
                    print(
                        f"[orchestrator] GPT agent signalled ready: {evt}", flush=True
                    )
                    _redis().set(REDIS_GPT_KEY, "ready")
                elif etype == "peer_status":
                    print(
                        f"[orchestrator] Peer status: {evt.get('agent')} → {evt.get('status')}",
                        flush=True,
                    )
            time.sleep(POLL_INTERVAL)
    except Exception as exc:
        print(f"[orchestrator] Coordination listener error: {exc}", flush=True)


# ---------------------------------------------------------------------------
# Main daemon
# ---------------------------------------------------------------------------


def run_daemon() -> None:
    r = _redis()
    _set_progress("starting")
    print("[orchestrator] Starting up…", flush=True)

    # Verify Pandaproxy connectivity
    try:
        topics = _rest_get("/topics", accept="application/vnd.kafka.v2+json")
        voice_topics = [t for t in topics if "voice" in t]
        print(
            f"[orchestrator] Pandaproxy OK — voice topics: {voice_topics}", flush=True
        )
    except Exception as exc:
        print(f"[orchestrator] WARNING: Pandaproxy probe failed: {exc}", flush=True)

    # Start coordination listener in background thread
    coord_thread = threading.Thread(target=_coordination_listener, daemon=True)
    coord_thread.start()

    # Mark orchestrator ready
    r.set(REDIS_READY_KEY, "true")
    _set_progress("ready")
    print(f"[orchestrator] Ready. Subscribing to {TOPIC_INPUT}…", flush=True)

    # Announce readiness to coordination topic
    try:
        rest_produce(
            TOPIC_COORDINATION,
            {"type": "orchestrator_ready", "ts": time.time()},
            key="orchestrator_event",
        )
    except Exception:
        pass

    # Main consumer loop (REST long-poll)
    consumer = RestConsumer(
        group=CONSUMER_GROUP,
        instance=CONSUMER_ID,
        topics=[TOPIC_INPUT],
        offset_reset="earliest",
    )

    print("[orchestrator] Consumer loop running. Ctrl+C to stop.", flush=True)
    try:
        while True:
            records = consumer.poll(timeout_ms=1000)
            for rec in records:
                try:
                    process_input_message(rec.get("value", {}))
                except Exception as exc:
                    print(f"[orchestrator] Error processing message: {exc}", flush=True)
                    _set_progress(f"error: {str(exc)[:60]}")
    except KeyboardInterrupt:
        _set_progress("stopped")
        r.set(REDIS_READY_KEY, "false")
        consumer.delete()
        print("\n[orchestrator] Stopped.", flush=True)


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def cmd_test() -> None:
    """Send a test query through the full pipeline."""
    import uuid, subprocess

    rid = str(uuid.uuid4())[:8]
    test_query = {
        "text": "G'day Karen! What's happening today?",
        "session_id": "test-session",
        "request_id": rid,
        "ts": time.time(),
    }

    rest_produce(TOPIC_INPUT, test_query)
    print(
        f"[test] Published (request_id={rid}). Waiting for daemon to process…",
        flush=True,
    )

    # Poll Pandaproxy consumer for new responses
    c = RestConsumer(group=f"test-{rid}", instance="t1", topics=[TOPIC_RESPONSE])
    deadline = time.time() + 20
    while time.time() < deadline:
        for rec in c.poll(max_bytes=65536, timeout_ms=3000):
            inner = rec.get("value", {})
            if inner.get("request_id") == rid:
                print(
                    f"[test] ✓ Response from [{inner.get('provider','?')}] in {inner.get('latency_ms','?')}ms:"
                )
                print(f"       {inner.get('text','')}")
                c.delete()
                return
        time.sleep(0.3)
    print("[test] No matching response in 20s — is the daemon running?", flush=True)
    c.delete()


def cmd_status() -> None:
    r = _redis()
    print(
        "voice:claude_orchestrator_progress:", r.get(REDIS_PROGRESS_KEY) or "(not set)"
    )
    print("voice:orchestrator_ready          :", r.get(REDIS_READY_KEY) or "(not set)")
    print("voice:gpt_redpanda_progress       :", r.get(REDIS_GPT_KEY) or "(not set)")
    print("voice:history length              :", r.llen(REDIS_HISTORY_KEY))
    print("CLAUDE_API_KEY present            :", bool(CLAUDE_API_KEY))
    print("Ollama URL                        :", OLLAMA_URL)
    print("Pandaproxy URL                    :", PANDAPROXY)

    # Check Ollama reachable
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3)
        print("Ollama reachable                  : yes")
    except Exception:
        print("Ollama reachable                  : no")

    # Check Pandaproxy reachable
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                f"{PANDAPROXY}/topics",
                headers={"Accept": "application/vnd.kafka.v2+json"},
            ),
            timeout=3,
        )
        print("Pandaproxy reachable              : yes")
    except Exception:
        print("Pandaproxy reachable              : no")


def cmd_topics() -> None:
    import subprocess

    result = subprocess.run(
        ["docker", "exec", "agentic-brain-redpanda", "rpk", "topic", "list"],
        capture_output=True,
        text=True,
    )
    lines = [
        l
        for l in result.stdout.splitlines()
        if "voice" in l or "brain" in l or "NAME" in l
    ]
    print("Voice / brain topics:")
    for line in lines:
        print(f"  {line}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

USAGE = """\
Usage:
  python tools/voice_orchestrator.py daemon   # run as background service
  python tools/voice_orchestrator.py test     # send a test query end-to-end
  python tools/voice_orchestrator.py status   # show Redis/Redpanda state
  python tools/voice_orchestrator.py topics   # list voice/brain topics
"""


def main(argv: list[str] | None = None) -> int:
    args = (argv or sys.argv)[1:]
    if not args:
        print(USAGE)
        return 0

    cmd = args[0].lower()
    if cmd == "daemon":
        run_daemon()
    elif cmd == "test":
        cmd_test()
    elif cmd == "status":
        cmd_status()
    elif cmd == "topics":
        cmd_topics()
    else:
        print(USAGE)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
