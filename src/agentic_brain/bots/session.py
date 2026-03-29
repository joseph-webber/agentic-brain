"""Session helpers for agent lifecycle tracking."""

from __future__ import annotations

import secrets
import string
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any

_ALLOWED_PREFIX_CHARS = set(string.ascii_letters + string.digits + "_-")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso8601(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _from_iso8601(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def generate_session_id(prefix: str = "session") -> str:
    """Generate a collision-resistant, readable session ID."""
    cleaned_prefix = prefix.strip().lower()
    if not cleaned_prefix or any(char not in _ALLOWED_PREFIX_CHARS for char in cleaned_prefix):
        raise ValueError("prefix must contain only letters, numbers, hyphens, or underscores")

    timestamp = _utc_now().strftime("%Y%m%dT%H%M%S")
    entropy = secrets.token_hex(6)
    return f"{cleaned_prefix}_{timestamp}_{entropy}"


def get_session_key(agent_id: str, session_id: str) -> str:
    """Build a stable composite key for session storage."""
    return f"{agent_id}:{session_id}"


@dataclass
class AgentSession:
    """Track a single agent execution session."""

    agent_id: str
    session_id: str = field(default_factory=generate_session_id)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    status: str = "running"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def session_key(self) -> str:
        return get_session_key(self.agent_id, self.session_id)

    def start(self) -> None:
        self.started_at = _utc_now()
        self.status = "running"

    def end(self, status: str = "completed") -> None:
        self.ended_at = _utc_now()
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["started_at"] = _to_iso8601(self.started_at)
        data["ended_at"] = _to_iso8601(self.ended_at)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSession:
        payload = data.copy()
        payload["started_at"] = _from_iso8601(payload.get("started_at"))
        payload["ended_at"] = _from_iso8601(payload.get("ended_at"))
        return cls(**payload)

    def __str__(self) -> str:
        return f"AgentSession({self.session_key}, status={self.status})"


BotSession = AgentSession


__all__ = [
    "AgentSession",
    "BotSession",
    "generate_session_id",
    "get_session_key",
]
