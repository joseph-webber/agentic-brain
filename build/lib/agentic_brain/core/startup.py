# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""Startup greeting helpers backed by recent Neo4j memory."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from agentic_brain.core.neo4j_pool import get_session

logger = logging.getLogger(__name__)

RECENT_CONTEXT_CYPHER = """
MATCH (m:Memory)
WHERE m.scope IN $scopes
RETURN
    m.id AS id,
    m.content AS content,
    m.scope AS scope,
    m.timestamp AS timestamp,
    m.metadata AS metadata
ORDER BY m.timestamp DESC
LIMIT $limit
"""

PENDING_CONTEXT_CYPHER = """
MATCH (m:Memory)
WHERE m.scope IN $scopes
  AND m.timestamp >= datetime() - duration($window)
  AND (
    toLower(coalesce(m.content, "")) CONTAINS "pending"
    OR toLower(coalesce(m.content, "")) CONTAINS "todo"
    OR toLower(coalesce(m.content, "")) CONTAINS "follow up"
    OR toLower(coalesce(m.content, "")) CONTAINS "next step"
    OR toLower(coalesce(m.content, "")) CONTAINS "action item"
  )
RETURN count(m) AS pending_count
"""


@dataclass(frozen=True)
class StartupSnapshot:
    """Structured startup context used by CLI and voice output."""

    greeting: str
    proof_lines: tuple[str, ...]
    last_session_topic: str
    last_session_time: str
    pending_count: int
    recent_summary: str


def _to_datetime(value: Any) -> datetime:
    """Normalize Neo4j or Python datetime values."""
    if value is None:
        return datetime.now(UTC)
    if hasattr(value, "to_native"):
        value = value.to_native()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            logger.debug("Could not parse timestamp: %s", value)
    return datetime.now(UTC)


def _parse_metadata(raw_metadata: Any) -> dict[str, Any]:
    """Best-effort parsing for stored metadata strings."""
    if isinstance(raw_metadata, dict):
        return raw_metadata
    if not raw_metadata or not isinstance(raw_metadata, str):
        return {}
    try:
        parsed = ast.literal_eval(raw_metadata)
    except (SyntaxError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _clean_text(text: str | None, *, max_length: int = 96) -> str:
    """Collapse whitespace and trim for user-facing output."""
    if not text:
        return "No stored details"
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"


def _format_time(value: Any) -> str:
    """Format timestamps in the local timezone."""
    timestamp = _to_datetime(value).astimezone()
    now = datetime.now(timestamp.tzinfo)
    if timestamp.date() == now.date():
        return timestamp.strftime("today at %-I:%M %p")
    if timestamp.year == now.year:
        return timestamp.strftime("%b %-d at %-I:%M %p")
    return timestamp.strftime("%Y-%m-%d %-I:%M %p")


def _extract_topic(row: Mapping[str, Any]) -> str:
    """Infer a human-friendly topic from metadata or content."""
    metadata = _parse_metadata(row.get("metadata"))
    for key in ("topic", "session_topic", "title", "category", "summary"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return _clean_text(value, max_length=72)
    return _clean_text(str(row.get("content", "")), max_length=72)


def _build_recent_summary(rows: Sequence[Mapping[str, Any]]) -> str:
    """Build a short summary from the most recent context entries."""
    if not rows:
        return "No recent context stored yet."
    snippets: list[str] = []
    for row in rows[:3]:
        snippet = _clean_text(str(row.get("content", "")), max_length=52)
        if snippet not in snippets:
            snippets.append(snippet)
    return "; ".join(snippets) if snippets else "No recent context stored yet."


def _build_proof_lines(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """Build proof lines showing the memories behind the greeting."""
    proof: list[str] = []
    for row in rows[:3]:
        proof.append(f"- {_format_time(row.get('timestamp'))}: {_clean_text(str(row.get('content', '')))}")
    return tuple(proof)


def build_startup_snapshot(
    rows: Sequence[Mapping[str, Any]], pending_count: int = 0
) -> StartupSnapshot:
    """Convert recent memory rows into a greeting snapshot."""
    last_row = rows[0] if rows else {}
    last_session_topic = _extract_topic(last_row) if last_row else "No recent context found"
    last_session_time = _format_time(last_row.get("timestamp")) if last_row else "just now"
    recent_summary = _build_recent_summary(rows)
    greeting = "\n".join(
        [
            "Welcome back! Here's what I remember:",
            f"- Last session: {last_session_topic} at {last_session_time}",
            f"- Pending: {pending_count} items",
            f"- Recent: {recent_summary}",
            "Ready to continue?",
        ]
    )
    return StartupSnapshot(
        greeting=greeting,
        proof_lines=_build_proof_lines(rows),
        last_session_topic=last_session_topic,
        last_session_time=last_session_time,
        pending_count=max(pending_count, 0),
        recent_summary=recent_summary,
    )


def _fetch_recent_context(
    *, limit: int = 5, scopes: Sequence[str] = ("private", "public")
) -> list[dict[str, Any]]:
    """Fetch recent memories from Neo4j."""
    with get_session() as session:
        result = session.run(RECENT_CONTEXT_CYPHER, scopes=list(scopes), limit=limit)
        return [dict(record) for record in result]


def _count_pending_items(
    *, scopes: Sequence[str] = ("private", "public"), window_days: int = 7
) -> int:
    """Estimate pending items from recent memory content."""
    with get_session() as session:
        result = session.run(
            PENDING_CONTEXT_CYPHER,
            scopes=list(scopes),
            window=f"P{max(window_days, 1)}D",
        )
        record = result.single()
    if not record:
        return 0
    return int(record.get("pending_count", 0))


def get_startup_snapshot(
    *, limit: int = 5, scopes: Sequence[str] = ("private", "public")
) -> StartupSnapshot:
    """Load recent context from Neo4j and build a startup snapshot."""
    try:
        rows = _fetch_recent_context(limit=limit, scopes=scopes)
        pending_count = _count_pending_items(scopes=scopes)
        return build_startup_snapshot(rows, pending_count=pending_count)
    except Exception as exc:  # pragma: no cover - exercised via CLI fallback tests
        logger.info("Startup context unavailable: %s", exc)
        return build_startup_snapshot([], pending_count=0)


def startup_greeting(*, limit: int = 5, scopes: Sequence[str] = ("private", "public")) -> str:
    """Return a friendly startup greeting with context from Neo4j."""
    return get_startup_snapshot(limit=limit, scopes=scopes).greeting


__all__ = [
    "StartupSnapshot",
    "build_startup_snapshot",
    "get_startup_snapshot",
    "startup_greeting",
]
