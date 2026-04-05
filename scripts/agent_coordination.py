#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Simple Redis-based coordination helpers for LLM agents performing git work.

This script provides a **very small, explicit contract** for agents so they
stop trampling each other during git operations.

Redis primitives used
---------------------
- Key ``llm:git:lock``          – global mutex for git operations
- Key ``llm:agents:status``     – last status update from any agent
- Channel ``llm:coordination``  – coordination events (lock / status)
- Channel ``llm:meeting``       – higher-level "meeting" style updates

How agents SHOULD coordinate
----------------------------
1. Before **any** git operation (add / commit / push / rebase):

   >>> from scripts.agent_coordination import acquire_git_lock
   >>> lock = acquire_git_lock(agent_id="cli-agent", ttl=300)
   >>> if not lock.acquired:
   ...     # respect other agents – do NOT continue
   ...     raise SystemExit("Another agent holds the git lock")

2. Perform git operations only while you hold the lock.

3. After work is complete (success or failure):

   >>> from scripts.agent_coordination import release_git_lock
   >>> release_git_lock(agent_id="cli-agent")

4. On conflict / busy lock:
   - ``acquire_git_lock`` will wait (with backoff) until the lock becomes free
     or until ``wait_timeout`` is exceeded.
   - While waiting it publishes ``lock_waiting`` events so other tools can
     surface the blockage to the user.

All events are JSON and safe for other agents to subscribe to:

.. code-block:: json

   {
     "event": "lock_acquired",
     "agent_id": "cli-agent",
     "lock_key": "llm:git:lock",
     "timestamp": "2026-03-25T10:00:00Z",
     "ttl": 300
   }

This script is intentionally dependency-light so it can be imported from any
agent (Python module, CLI helper, or notebook).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

try:  # Local helper, do not enforce redis during import in non-Redis envs
    import redis  # type: ignore[import]
except Exception:  # pragma: no cover - handled at runtime in get_redis_client
    redis = None  # type: ignore[assignment]


COORDINATION_CHANNEL = "llm:coordination"
MEETING_CHANNEL = "llm:meeting"
GIT_LOCK_KEY = "llm:git:lock"
AGENT_STATUS_KEY = "llm:agents:status"


@dataclass
class LockResult:
    """Result of a lock acquisition attempt.

    Attributes:
        acquired: Whether the lock was successfully acquired.
        owner: Current owner of the lock (may be ``None`` if no lock).
        expires_at: Epoch timestamp when the lock will expire, if known.
        details: Raw lock payload (decoded JSON) if available.
    """

    acquired: bool
    owner: Optional[str]
    expires_at: Optional[float]
    details: Dict[str, Any]


def _utc_now() -> datetime:
    return datetime.utcnow()


def _get_redis_client() -> redis.Redis:
    """Create a Redis client using standard Agentic Brain environment.

    This mirrors the defaults used elsewhere in the project:
    - REDIS_HOST (default: ``localhost``)
    - REDIS_PORT (default: ``6379``)
    - REDIS_PASSWORD (default: ``brain_secure_2024``)
    - REDIS_DB (default: ``0``)
    """

    if redis is None:  # pragma: no cover - guarded import above
        raise RuntimeError("redis-py not installed. Install with: pip install redis")

    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    password = os.getenv("REDIS_PASSWORD", "brain_secure_2024")
    db = int(os.getenv("REDIS_DB", "0"))

    return redis.Redis(
        host=host,
        port=port,
        password=password,
        db=db,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
    )


def _publish(client: redis.Redis, event: str, agent_id: str, **extra: Any) -> None:
    """Publish a small JSON event to both coordination channels."""

    payload = {
        "event": event,
        "agent_id": agent_id,
        "lock_key": GIT_LOCK_KEY,
        "timestamp": _utc_now().isoformat() + "Z",
    }
    payload.update(extra)
    data = json.dumps(payload, separators=(",", ":"))

    # Fire-and-forget – subscribers are optional
    client.publish(COORDINATION_CHANNEL, data)
    client.publish(MEETING_CHANNEL, data)


def _update_status(
    client: redis.Redis, agent_id: str, status: str, **extra: Any
) -> None:
    """Write a compact status document for quick inspection.

    Stored at ``llm:agents:status`` so users can inspect via redis-cli:

        redis-cli -a brain_secure_2024 GET llm:agents:status
    """

    doc: Dict[str, Any] = {
        "agent_id": agent_id,
        "status": status,
        "lock_key": GIT_LOCK_KEY,
        "updated_at": _utc_now().isoformat() + "Z",
    }
    doc.update(extra)
    client.set(AGENT_STATUS_KEY, json.dumps(doc, separators=(",", ":")))


def _parse_lock(
    raw: Optional[str],
) -> Tuple[Optional[str], Optional[float], Dict[str, Any]]:
    """Decode the current lock value from Redis.

    Returns (owner, expires_at, details_dict).
    """

    if not raw:
        return None, None, {}

    try:
        data = json.loads(raw)
        owner = data.get("agent_id")
        expires_at = data.get("expires_at")
        return owner, expires_at, data
    except Exception:
        # Fallback – unknown format but still surface it
        return None, None, {"raw": raw}


def acquire_git_lock(
    agent_id: str,
    *,
    ttl: int = 300,
    wait_timeout: int = 900,
    poll_interval: float = 2.0,
) -> LockResult:
    """Acquire the global git lock, waiting politely if needed.

    Args:
        agent_id: Logical name for this agent (e.g. ``"cli-agent"``).
        ttl: Lock TTL in seconds (prevents dead locks if an agent crashes).
        wait_timeout: Max seconds to wait for the lock before giving up.
        poll_interval: Seconds between retry attempts while waiting.

    Returns:
        :class:`LockResult` describing whether the lock was acquired and who
        currently owns it.

    Behaviour:
        - Uses ``SET llm:git:lock NX EX ttl`` for atomic acquire.
        - If the lock is held, waits up to ``wait_timeout``.
        - Publishes ``lock_acquired`` / ``lock_waiting`` events.
        - Updates ``llm:agents:status`` on each state change.
    """

    client = _get_redis_client()
    start = time.time()

    while True:
        now = time.time()
        acquired_at = now
        payload = {
            "agent_id": agent_id,
            "acquired_at": acquired_at,
            "acquired_at_iso": datetime.utcfromtimestamp(acquired_at).isoformat() + "Z",
            "ttl": ttl,
            "expires_at": acquired_at + ttl,
        }

        # Try atomic acquire
        try:
            did_set = client.set(GIT_LOCK_KEY, json.dumps(payload), nx=True, ex=ttl)
        except Exception as e:  # pragma: no cover - runtime connection issues
            raise RuntimeError(f"Redis error while acquiring lock: {e}") from e

        if did_set:
            _update_status(client, agent_id, "locked", ttl=ttl)
            _publish(client, "lock_acquired", agent_id, ttl=ttl)
            return LockResult(True, agent_id, payload["expires_at"], payload)

        # Someone else holds the lock – inspect and optionally wait
        raw = client.get(GIT_LOCK_KEY)
        owner, expires_at, details = _parse_lock(raw)

        _update_status(
            client,
            agent_id,
            "waiting",
            owner=owner,
            expires_at=expires_at,
        )
        _publish(
            client,
            "lock_waiting",
            agent_id,
            owner=owner,
            expires_at=expires_at,
        )

        if now - start >= wait_timeout:
            return LockResult(False, owner, expires_at, details)

        time.sleep(poll_interval)


def release_git_lock(agent_id: str) -> bool:
    """Release the global git lock if held by ``agent_id``.

    Returns ``True`` if the lock was removed, ``False`` otherwise.

    This is intentionally forgiving: if another agent has already released the
    lock we simply report ``False`` and publish a ``lock_missing`` event.
    """

    client = _get_redis_client()

    raw = client.get(GIT_LOCK_KEY)
    owner, expires_at, details = _parse_lock(raw)

    if not raw:
        _update_status(client, agent_id, "idle", note="no_lock_present")
        _publish(client, "lock_missing", agent_id)
        return False

    if owner and owner != agent_id:
        # Do NOT steal another agent's lock
        _update_status(
            client,
            agent_id,
            "not_owner",
            current_owner=owner,
            expires_at=expires_at,
        )
        _publish(
            client,
            "lock_release_denied",
            agent_id,
            current_owner=owner,
            expires_at=expires_at,
        )
        return False

    # Safe to delete – best-effort, no Lua needed for this use case
    client.delete(GIT_LOCK_KEY)
    _update_status(client, agent_id, "idle")
    _publish(client, "lock_released", agent_id, previous=details)
    return True


def get_lock_status() -> LockResult:
    """Return current lock holder information without modifying anything."""

    client = _get_redis_client()
    raw = client.get(GIT_LOCK_KEY)
    owner, expires_at, details = _parse_lock(raw)
    return LockResult(False, owner, expires_at, details)


def _cli_acquire(args: argparse.Namespace) -> int:
    result = acquire_git_lock(
        agent_id=args.agent_id,
        ttl=args.ttl,
        wait_timeout=args.wait_timeout,
        poll_interval=args.poll_interval,
    )

    if args.json:
        print(json.dumps(result.__dict__, indent=2, default=str))
    else:
        if result.acquired:
            print(
                f"LOCK ACQUIRED by {args.agent_id} (expires at "
                f"{datetime.utcfromtimestamp(result.expires_at).isoformat() if result.expires_at else 'unknown'})"
            )
        else:
            print(
                f"LOCK BUSY – held by {result.owner or 'unknown'}; "
                f"expires_at={result.expires_at}"
            )
    return 0 if result.acquired else 1


def _cli_release(args: argparse.Namespace) -> int:
    ok = release_git_lock(agent_id=args.agent_id)
    if args.json:
        print(json.dumps({"released": ok}, indent=2))
    else:
        if ok:
            print(f"LOCK RELEASED by {args.agent_id}")
        else:
            print("NO LOCK RELEASED (either missing or owned by someone else)")
    return 0 if ok else 1


def _cli_status(args: argparse.Namespace) -> int:
    result = get_lock_status()
    client = _get_redis_client()
    status_raw = client.get(AGENT_STATUS_KEY)

    payload: Dict[str, Any] = {
        "lock": result.__dict__,
        "agent_status_raw": status_raw,
    }

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        owner = result.owner or "<none>"
        print(f"Current lock owner: {owner}")
        if result.expires_at:
            print(
                "Expires at:",
                datetime.utcfromtimestamp(result.expires_at).isoformat() + "Z",
            )
        else:
            print("Expires at: <unknown>")
        if status_raw:
            print("Agent status:", status_raw)
        else:
            print("Agent status: <none>")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Redis-based coordination helper for LLM agents performing git "
            "operations.\n\n"
            "Typical workflow:\n"
            "  1) agent_coordination.py acquire --agent my-agent && git commit ...\n"
            "  2) agent_coordination.py release --agent my-agent\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # acquire
    p_acq = sub.add_parser("acquire", help="Acquire the global git lock")
    p_acq.add_argument("--agent", "--agent-id", dest="agent_id", required=True)
    p_acq.add_argument("--ttl", type=int, default=300, help="Lock TTL in seconds")
    p_acq.add_argument(
        "--wait-timeout",
        type=int,
        default=900,
        help="Max seconds to wait for lock before failing",
    )
    p_acq.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between lock acquisition attempts",
    )
    p_acq.add_argument("--json", action="store_true", help="JSON output")
    p_acq.set_defaults(func=_cli_acquire)

    # release
    p_rel = sub.add_parser("release", help="Release the global git lock")
    p_rel.add_argument("--agent", "--agent-id", dest="agent_id", required=True)
    p_rel.add_argument("--json", action="store_true", help="JSON output")
    p_rel.set_defaults(func=_cli_release)

    # status
    p_stat = sub.add_parser("status", help="Show lock + agent status")
    p_stat.add_argument("--json", action="store_true", help="JSON output")
    p_stat.set_defaults(func=_cli_status)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)  # type: ignore[attr-defined]
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
