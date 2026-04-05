#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
"""Copilot Voice Bridge – connects voice input to GitHub Copilot CLI.

Architecture
------------
  brain.voice.input  (Redpanda via HTTP REST proxy)
         ↓
  [CopilotVoiceBridge]  ← voice:history (Redis, conversation memory)
         ↓ route
  Copilot CLI (-p/--prompt)  →  fallback: Ollama (llama3.2:3b)
         ↓
  brain.voice.response  (Redpanda via HTTP REST proxy)
         ↓
  Cartesia TTS → Karen speaks

Transport
---------
  Uses Redpanda Pandaproxy HTTP REST API (port 8082) for produce/consume.
  This bypasses kafka-python TCP issues with Docker-advertised broker addresses.

Copilot Integration
-------------------
  Uses `copilot -p <prompt> --output-format text` for non-interactive queries.
  The Copilot CLI binary lives at ~/.local/bin/copilot (arm64 Mach-O).
  Subprocess timeout: 90s (complex queries may take time).

Fallback
--------
  When Copilot CLI is unavailable or times out, falls back to local Ollama
  (llama3.2:3b at localhost:11434) for zero-downtime voice responses.

Usage
-----
  python tools/copilot_voice_bridge.py daemon    # run as background service
  python tools/copilot_voice_bridge.py test      # send a test query
  python tools/copilot_voice_bridge.py status    # show bridge health
  python tools/copilot_voice_bridge.py health    # check Copilot + Ollama
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT = "[%(asctime)s] %(levelname)-7s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")
log = logging.getLogger("copilot-bridge")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PANDAPROXY = os.getenv("PANDAPROXY_URL", "http://localhost:8082")
REDIS_URL = os.getenv("VOICE_REDIS_URL", "redis://:BrainRedis2026@localhost:6379/0")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
POLL_INTERVAL = float(os.getenv("BRIDGE_POLL_INTERVAL", "0.5"))

COPILOT_BIN = os.getenv(
    "COPILOT_BIN",
    shutil.which("copilot") or str(Path.home() / ".local" / "bin" / "copilot"),
)
COPILOT_TIMEOUT = int(os.getenv("COPILOT_TIMEOUT", "30"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))

# Topics
TOPIC_INPUT = "brain.voice.input"
TOPIC_RESPONSE = "brain.voice.response"
TOPIC_COORDINATION = "brain.voice.coordination"

# Redis keys
REDIS_PROGRESS_KEY = "voice:copilot_bridge_progress"
REDIS_READY_KEY = "voice:copilot_bridge_ready"
REDIS_HISTORY_KEY = "voice:copilot_bridge_history"

# Conversation memory
HISTORY_MAX_ENTRIES = 10
HISTORY_CONTEXT_ENTRIES = 6

# Consumer group
CONSUMER_GROUP = "copilot-voice-bridge"
CONSUMER_ID = "bridge-1"

# System prompt for Ollama fallback (matches Karen's voice)
SYSTEM_PROMPT = (
    "You are Karen, a warm and friendly Australian AI assistant. "
    "The user relies on audio, so every response you give will be spoken aloud. "
    "Keep responses to 2-3 sentences — clear, conversational, and easy to listen to. "
    "You have a sense of humour and a caring nature. "
    "If the question is about code, give a concise practical answer. "
    "Never use bullet points, markdown, or long lists — just natural spoken sentences."
)


# ---------------------------------------------------------------------------
# Lazy Redis singleton
# ---------------------------------------------------------------------------
_redis_client: Any = None


def _redis() -> Any:
    global _redis_client
    if _redis_client is None:
        import redis as _r  # type: ignore[import]

        _redis_client = _r.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _set_progress(status: str) -> None:
    try:
        _redis().set(REDIS_PROGRESS_KEY, status)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Conversation history (Redis-backed)
# ---------------------------------------------------------------------------


def push_history(role: str, content: str) -> None:
    try:
        r = _redis()
        entry = json.dumps({"role": role, "content": content, "ts": time.time()})
        r.lpush(REDIS_HISTORY_KEY, entry)
        r.ltrim(REDIS_HISTORY_KEY, 0, HISTORY_MAX_ENTRIES - 1)
    except Exception as exc:
        log.debug("History push failed: %s", exc)


def get_context_messages() -> list[dict[str, str]]:
    try:
        r = _redis()
        raw = r.lrange(REDIS_HISTORY_KEY, 0, HISTORY_CONTEXT_ENTRIES - 1)
        messages: list[dict[str, str]] = []
        for item in reversed(raw):
            try:
                e = json.loads(item)
                messages.append({"role": e["role"], "content": e["content"]})
            except (json.JSONDecodeError, KeyError):
                continue
        return messages
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Redpanda REST transport (Pandaproxy on port 8082)
# ---------------------------------------------------------------------------


def _rest_post(
    path: str,
    body: Any,
    content_type: str = "application/vnd.kafka.json.v2+json",
) -> Any:
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


def _rest_get(path: str, accept: str = "application/vnd.kafka.v2+json") -> Any:
    url = f"{PANDAPROXY}{path}"
    req = urllib.request.Request(url, headers={"Accept": accept})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _rest_delete(path: str) -> None:
    url = f"{PANDAPROXY}{path}"
    req = urllib.request.Request(
        url,
        method="DELETE",
        headers={"Accept": "application/vnd.kafka.v2+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise


def rest_produce(topic: str, value: dict, key: str | None = None) -> None:
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
        offset_reset: str = "latest",
    ):
        self._group = group
        self._instance = instance
        self._base = f"/consumers/{group}/instances/{instance}"
        self._topics = topics
        # Create consumer instance
        try:
            _rest_post(
                f"/consumers/{group}",
                {
                    "name": instance,
                    "format": "json",
                    "auto.offset.reset": offset_reset,
                    "auto.commit.enable": "true",
                },
                content_type="application/vnd.kafka.v2+json",
            )
        except urllib.error.HTTPError as e:
            if e.code != 409:  # 409 = already exists
                raise
        # Subscribe to topics
        _rest_post(
            f"{self._base}/subscription",
            {"topics": topics},
            content_type="application/vnd.kafka.v2+json",
        )

    def poll(self, max_bytes: int = 65536, timeout_ms: int = 1000) -> list[dict]:
        try:
            url = f"{self._base}/records" f"?max_bytes={max_bytes}&timeout={timeout_ms}"
            return _rest_get(url)
        except Exception:
            return []

    def delete(self) -> None:
        try:
            _rest_delete(self._base)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Copilot CLI integration
# ---------------------------------------------------------------------------


def _copilot_available() -> bool:
    """Check if the Copilot CLI binary exists and is executable."""
    p = Path(COPILOT_BIN)
    return p.is_file() and os.access(p, os.X_OK)


def _call_copilot(query: str) -> str | None:
    """Send a prompt to the Copilot CLI in non-interactive mode.

    Uses `copilot -p <prompt> --output-format text` which runs a single
    prompt and exits. Returns the response text or None on failure.
    """
    if not _copilot_available():
        log.warning("Copilot CLI not found at %s", COPILOT_BIN)
        return None

    # Build context from conversation history
    context = get_context_messages()
    context_block = ""
    if context:
        recent = context[-4:]  # last 2 exchanges max for prompt size
        lines = []
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Karen"
            lines.append(f"{role}: {msg['content']}")
        context_block = "Recent conversation:\n" + "\n".join(lines) + "\n\n"

    full_prompt = (
        f"{context_block}"
        f"The user (who relies on VoiceOver for accessibility) asks: {query}\n\n"
        "Respond in 2-3 spoken sentences. No markdown, no bullet points. "
        "Be warm and conversational like an Australian friend."
    )

    cmd = [
        COPILOT_BIN,
        "-p",
        full_prompt,
        "--output-format",
        "text",
    ]

    try:
        log.info("Calling Copilot CLI (timeout=%ds)...", COPILOT_TIMEOUT)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=COPILOT_TIMEOUT,
            cwd=str(Path.home() / "brain"),
            env={**os.environ, "NO_COLOR": "1"},
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0 and result.stdout.strip():
            response = result.stdout.strip()
            # Truncate very long responses for voice
            if len(response) > 1000:
                response = response[:1000].rsplit(".", 1)[0] + "."
            log.info("Copilot responded (%d chars)", len(response))
            return response
        else:
            stderr = result.stderr.strip()[:200] if result.stderr else ""
            log.warning("Copilot exit=%d stderr=%s", result.returncode, stderr)
            return None
    except subprocess.TimeoutExpired:
        log.warning("Copilot CLI timed out after %ds", COPILOT_TIMEOUT)
        return None
    except FileNotFoundError:
        log.error("Copilot CLI binary not found: %s", COPILOT_BIN)
        return None
    except Exception as exc:
        log.error("Copilot CLI error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Ollama fallback
# ---------------------------------------------------------------------------


def _ollama_available() -> bool:
    """Quick health check against Ollama /api/tags endpoint."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _call_ollama(query: str) -> str | None:
    """Call local Ollama as fallback. Returns text or None on failure."""
    try:
        context = get_context_messages()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(context[-4:])
        messages.append({"role": "user", "content": query})

        payload = json.dumps(
            {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 250},
            }
        ).encode()

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        log.info("Calling Ollama (%s, timeout=%ds)...", OLLAMA_MODEL, OLLAMA_TIMEOUT)
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read())
            text = data.get("message", {}).get("content", "").strip()
            if text:
                log.info("Ollama responded (%d chars)", len(text))
            return text or None
    except Exception as exc:
        log.error("Ollama error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Complexity classifier (matches voice_orchestrator.py patterns)
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
    if len(words) <= 5 and set(words).issubset(_SIMPLE_WORDS):
        return "simple"
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
        "create",
        "build",
        "implement",
        "generate",
        "refactor",
        "debug",
        "fix",
        "review",
        "deploy",
    ]
    for sig in complex_signals:
        if sig in lower:
            return "complex"
    if len(words) <= 12:
        return "medium"
    return "complex"


# Routing table: complexity → provider preference order
# Simple/medium queries go to Ollama first (faster for voice latency).
# Complex queries try Copilot first (more capable for code tasks).
_ROUTING: dict[str, list[str]] = {
    "simple": ["ollama", "copilot"],
    "medium": ["ollama", "copilot"],
    "complex": ["copilot", "ollama"],
}


# ---------------------------------------------------------------------------
# Routing: Copilot ↔ Ollama with complexity-based preference
# ---------------------------------------------------------------------------

_CALLERS: dict[str, Any] = {}


def _get_callers() -> dict[str, Any]:
    if not _CALLERS:
        _CALLERS["copilot"] = _call_copilot
        _CALLERS["ollama"] = _call_ollama
    return _CALLERS


def route_query(query: str) -> tuple[str, str]:
    """Route query through providers based on complexity.

    Simple/medium → Ollama first (fast), Copilot fallback.
    Complex       → Copilot first (powerful), Ollama fallback.

    Returns (response_text, provider_used).
    """
    complexity = classify_complexity(query)
    providers = _ROUTING[complexity]
    callers = _get_callers()

    for provider in providers:
        _set_progress(f"calling_{provider}: {query[:40]}")
        response = callers[provider](query)
        if response:
            return response, provider

    # Hard fallback
    return (
        "Sorry, I'm having a bit of trouble connecting right now. "
        "Give me a moment and try again!",
        "fallback",
    )


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

    log.info("← '%s'", query)
    _set_progress(f"routing: {query[:40]}")

    complexity = classify_complexity(query)
    log.info("complexity=%s", complexity)

    # Store user turn
    push_history("user", query)

    # Route to best provider
    t0 = time.time()
    response_text, provider = route_query(query)
    latency_ms = int((time.time() - t0) * 1000)

    # Store assistant turn
    push_history("assistant", response_text)

    log.info("→ [%s] %dms: %s", provider, latency_ms, response_text[:80])
    _set_progress(f"done: {provider}/{complexity}/{latency_ms}ms")

    # Publish to brain.voice.response
    response_envelope = {
        "text": response_text,
        "provider": provider,
        "complexity": complexity,
        "latency_ms": latency_ms,
        "session_id": session_id,
        "request_id": request_id,
        "source": "copilot_voice_bridge",
        "ts": time.time(),
    }
    try:
        rest_produce(TOPIC_RESPONSE, response_envelope, key=session_id)
    except Exception as exc:
        log.error("Failed to publish response: %s", exc)

    # Broadcast coordination event
    try:
        rest_produce(
            TOPIC_COORDINATION,
            {
                "type": "copilot_bridge_response",
                "provider": provider,
                "latency_ms": latency_ms,
                "ts": time.time(),
            },
            key="bridge_event",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Coordination listener (background thread)
# ---------------------------------------------------------------------------


def _coordination_listener() -> None:
    """Listen to brain.voice.coordination for peer agent messages."""
    try:
        consumer = RestConsumer(
            group=f"{CONSUMER_GROUP}-coord",
            instance="bridge-coord-1",
            topics=[TOPIC_COORDINATION],
            offset_reset="latest",
        )
        log.info("Coordination listener active.")
        while True:
            records = consumer.poll()
            for rec in records:
                evt = rec.get("value", {})
                etype = evt.get("type", "")
                if etype in ("peer_status", "orchestrator_ready"):
                    log.info("Peer event: %s", etype)
            time.sleep(POLL_INTERVAL)
    except Exception as exc:
        log.error("Coordination listener error: %s", exc)


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------


def check_health() -> dict[str, Any]:
    """Return health status of all bridge dependencies."""
    health: dict[str, Any] = {
        "copilot_cli": {
            "binary": COPILOT_BIN,
            "available": _copilot_available(),
        },
        "ollama": {
            "url": OLLAMA_URL,
            "model": OLLAMA_MODEL,
            "available": _ollama_available(),
        },
        "pandaproxy": {"url": PANDAPROXY, "available": False},
        "redis": {"url": REDIS_URL.split("@")[-1], "available": False},
    }

    # Pandaproxy check
    try:
        topics = _rest_get("/topics")
        health["pandaproxy"]["available"] = True
        health["pandaproxy"]["voice_topics"] = [t for t in topics if "voice" in t]
    except Exception as exc:
        health["pandaproxy"]["error"] = str(exc)

    # Redis check
    try:
        r = _redis()
        r.ping()
        health["redis"]["available"] = True
        progress = r.get(REDIS_PROGRESS_KEY) or "unknown"
        health["redis"]["bridge_progress"] = progress
    except Exception as exc:
        health["redis"]["error"] = str(exc)

    # Overall
    health["ready"] = health["pandaproxy"]["available"] and (
        health["copilot_cli"]["available"] or health["ollama"]["available"]
    )
    return health


# ---------------------------------------------------------------------------
# Main daemon
# ---------------------------------------------------------------------------


def run_daemon() -> None:
    """Main event loop: consume voice input, route to Copilot, publish responses."""
    log.info("Starting Copilot Voice Bridge...")
    _set_progress("starting")

    # Verify Pandaproxy connectivity
    try:
        topics = _rest_get("/topics")
        voice_topics = [t for t in topics if "voice" in t]
        log.info("Pandaproxy OK — voice topics: %s", voice_topics)
    except Exception as exc:
        log.error("Pandaproxy probe failed: %s", exc)
        log.error("Is Redpanda running? (docker-compose up -d redpanda)")
        sys.exit(1)

    # Log provider availability
    if _copilot_available():
        log.info("Copilot CLI: ✓ (%s)", COPILOT_BIN)
    else:
        log.warning("Copilot CLI: ✗ — will use Ollama fallback exclusively")

    if _ollama_available():
        log.info("Ollama: ✓ (%s @ %s)", OLLAMA_MODEL, OLLAMA_URL)
    else:
        log.warning("Ollama: ✗ — no fallback available")

    # Start coordination listener
    coord_thread = threading.Thread(target=_coordination_listener, daemon=True)
    coord_thread.start()

    # Mark bridge ready
    try:
        r = _redis()
        r.set(REDIS_READY_KEY, "true")
    except Exception:
        pass
    _set_progress("ready")

    # Announce readiness
    try:
        rest_produce(
            TOPIC_COORDINATION,
            {
                "type": "copilot_bridge_ready",
                "copilot_available": _copilot_available(),
                "ollama_available": _ollama_available(),
                "ts": time.time(),
            },
            key="bridge_event",
        )
    except Exception:
        pass

    log.info("Ready. Subscribing to %s...", TOPIC_INPUT)

    # Main consumer loop
    consumer = RestConsumer(
        group=CONSUMER_GROUP,
        instance=CONSUMER_ID,
        topics=[TOPIC_INPUT],
        offset_reset="latest",
    )

    try:
        while True:
            records = consumer.poll(timeout_ms=1000)
            for rec in records:
                try:
                    process_input_message(rec.get("value", {}))
                except Exception as exc:
                    log.error("Error processing message: %s", exc)
                    _set_progress(f"error: {str(exc)[:60]}")
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        _set_progress("stopped")
        try:
            _redis().set(REDIS_READY_KEY, "false")
        except Exception:
            pass
        consumer.delete()
        log.info("Stopped.")


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def cmd_test() -> None:
    """Send a test query through the full pipeline."""
    import uuid

    rid = uuid.uuid4().hex[:8]
    test_query = {
        "text": "Hey Karen, what's the weather like in Adelaide today?",
        "session_id": "test-copilot-bridge",
        "request_id": rid,
        "ts": time.time(),
    }

    log.info("Publishing test query (request_id=%s)...", rid)
    rest_produce(TOPIC_INPUT, test_query)

    # Poll for response
    consumer = RestConsumer(
        group=f"test-{rid}",
        instance="t1",
        topics=[TOPIC_RESPONSE],
        offset_reset="latest",
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        for rec in consumer.poll(timeout_ms=3000):
            inner = rec.get("value", {})
            if inner.get("request_id") == rid:
                log.info("Response received!")
                print(json.dumps(inner, indent=2))
                consumer.delete()
                return
        time.sleep(0.5)

    consumer.delete()
    log.warning("No response within 30s. Is the daemon running?")


def cmd_status() -> None:
    """Show bridge status from Redis."""
    try:
        r = _redis()
        ready = r.get(REDIS_READY_KEY) or "unknown"
        progress = r.get(REDIS_PROGRESS_KEY) or "unknown"
        history_len = r.llen(REDIS_HISTORY_KEY)
        print(f"Bridge ready:    {ready}")
        print(f"Last progress:   {progress}")
        print(f"History entries: {history_len}")
    except Exception as exc:
        print(f"Redis unavailable: {exc}")


def cmd_health() -> None:
    """Run full health check and display results."""
    health = check_health()
    print(json.dumps(health, indent=2, default=str))
    if health["ready"]:
        print("\n✓ Bridge is ready to process voice input.")
    else:
        print("\n✗ Bridge has issues — check errors above.")


def cmd_direct(query: str) -> None:
    """Send a query directly (bypass Redpanda) for quick testing."""
    log.info("Direct query: %s", query)
    t0 = time.time()
    response_text, provider = route_query(query)
    latency_ms = int((time.time() - t0) * 1000)
    print(f"\n[{provider}] ({latency_ms}ms):")
    print(response_text)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

USAGE = """\
Copilot Voice Bridge – connects voice input to GitHub Copilot CLI

Usage:
  python copilot_voice_bridge.py daemon          Run as background service
  python copilot_voice_bridge.py test            Send a test query via Redpanda
  python copilot_voice_bridge.py status          Show Redis state
  python copilot_voice_bridge.py health          Check all dependencies
  python copilot_voice_bridge.py direct "query"  Query directly (bypass Redpanda)
"""


def main() -> None:
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "daemon":
        run_daemon()
    elif cmd == "test":
        cmd_test()
    elif cmd == "status":
        cmd_status()
    elif cmd == "health":
        cmd_health()
    elif cmd == "direct":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Hello Karen!"
        cmd_direct(query)
    else:
        print(f"Unknown command: {cmd}")
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
