#!/usr/bin/env python3
"""Voice health monitor — real-time system status for all voice components.

Exposes a single `health_check()` function that returns the status of every
component in the voice pipeline. Can also be run as a CLI or polled by Redis.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

REDIS_URL = os.getenv("VOICE_REDIS_URL", "redis://:BrainRedis2026@localhost:6379/0")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
PANDAPROXY_URL = os.getenv("PANDAPROXY_URL", "http://localhost:8082")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")


def _check_url(url: str, timeout: int = 3) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def _check_redis() -> dict[str, Any]:
    try:
        import redis

        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        history_len = r.llen("voice:history")
        return {"status": "healthy", "history_messages": history_len}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def _check_neo4j() -> dict[str, Any]:
    try:
        from neo4j import GraphDatabase

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        driver = GraphDatabase.driver(
            uri,
            auth=(
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "Brain2026"),
            ),
        )
        with driver.session() as session:
            result = session.run("MATCH (m:VoiceMessage) RETURN count(m) AS cnt")
            count = result.single()["cnt"]
        driver.close()
        return {"status": "healthy", "voice_messages": count}
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _check_ollama() -> dict[str, Any]:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
        return {"status": "healthy", "models": models}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def _check_redpanda() -> dict[str, Any]:
    try:
        req = urllib.request.Request(
            f"{PANDAPROXY_URL}/topics",
            headers={"Accept": "application/vnd.kafka.v2+json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            topics = json.loads(resp.read())
        voice_topics = [t for t in topics if "voice" in t]
        return {"status": "healthy", "voice_topics": voice_topics}
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _check_cartesia() -> dict[str, Any]:
    if not CARTESIA_API_KEY:
        return {"status": "not_configured", "error": "CARTESIA_API_KEY not set"}
    return {"status": "configured"}


def _check_circuit_breakers() -> list[dict[str, Any]]:
    try:
        from tools.voice.circuit_breaker import CircuitBreakerRegistry

        return CircuitBreakerRegistry.get().all_stats()
    except Exception:
        return []


def health_check() -> dict[str, Any]:
    """Run a full health check on all voice components.

    Returns a dict with status of every component.
    """
    t0 = time.monotonic()

    result = {
        "timestamp": time.time(),
        "components": {
            "redis": _check_redis(),
            "neo4j": _check_neo4j(),
            "ollama": _check_ollama(),
            "redpanda": _check_redpanda(),
            "cartesia": _check_cartesia(),
        },
        "circuit_breakers": _check_circuit_breakers(),
    }

    # Overall status
    statuses = [c.get("status") for c in result["components"].values()]
    critical = ["redis", "ollama"]
    critical_ok = all(
        result["components"][c].get("status") == "healthy" for c in critical
    )
    result["overall"] = "healthy" if critical_ok else "degraded"
    result["check_duration_ms"] = round((time.monotonic() - t0) * 1000, 1)

    return result


def publish_health_to_redis() -> None:
    """Run health check and publish to Redis for monitoring."""
    try:
        import redis

        r = redis.from_url(REDIS_URL, decode_responses=True)
        status = health_check()
        r.set("voice:health", json.dumps(status), ex=60)
        r.set("voice:health_status", status["overall"])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import sys

    status = health_check()
    print(json.dumps(status, indent=2))
    # Exit code 0 if healthy, 1 if degraded
    sys.exit(0 if status["overall"] == "healthy" else 1)


if __name__ == "__main__":
    main()
