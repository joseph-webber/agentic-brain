# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain contributors

"""Thread-safe clocks backed only by system time."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timezone, tzinfo
from threading import Lock
from zoneinfo import ZoneInfo

_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$")


class Clock:
    """Production-grade singleton clock for Adelaide-aware time handling."""

    _instance: Clock | None = None
    _instance_lock = Lock()
    _initialized = False

    def __new__(cls) -> Clock:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        with self.__class__._instance_lock:
            if self.__class__._initialized:
                return
            self._adelaide_tz = ZoneInfo("Australia/Adelaide")
            self._utc_tz = UTC
            self.__class__._initialized = True

    @staticmethod
    def _system_timezone() -> timezone:
        """Return the current system timezone."""
        tzinfo = datetime.now().astimezone().tzinfo
        if tzinfo is None:
            return UTC
        return tzinfo

    def _normalize_datetime(self, dt: datetime) -> datetime:
        """Ensure datetimes are timezone-aware before conversion."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self._system_timezone())
        return dt

    def now(self) -> datetime:
        """Return the current Adelaide datetime from system time."""
        return self.now_adelaide()

    def now_utc(self) -> datetime:
        """Return the current UTC datetime from system time."""
        return datetime.now(self._utc_tz)

    def now_adelaide(self) -> datetime:
        """Return the current Adelaide datetime from system time."""
        return datetime.now(self._adelaide_tz)

    def today(self) -> date:
        """Return today's date in Adelaide."""
        return self.now_adelaide().date()

    def year(self) -> int:
        """Return the current Adelaide year from system time."""
        return self.today().year

    def iso_date(self) -> str:
        """Return the current Adelaide date in ISO format."""
        return self.today().isoformat()

    def iso_datetime(self) -> str:
        """Return the current Adelaide datetime in ISO format."""
        return self.now_adelaide().isoformat()

    def to_adelaide(self, dt: datetime) -> datetime:
        """Convert any datetime to Adelaide time."""
        return self._normalize_datetime(dt).astimezone(self._adelaide_tz)

    def to_utc(self, dt: datetime) -> datetime:
        """Convert any datetime to UTC."""
        return self._normalize_datetime(dt).astimezone(self._utc_tz)

    def format(self, fmt: str) -> str:
        """Format the current Adelaide datetime with strftime."""
        return self.now_adelaide().strftime(fmt)

    def human_time(self) -> str:
        """Return a human-friendly Adelaide time string."""
        return self.now_adelaide().strftime("%I:%M %p").lstrip("0")

    def human_date(self) -> str:
        """Return a human-friendly Adelaide date string."""
        current = self.now_adelaide()
        return f"{current.strftime('%A, %B')} {current.day}, {current.year}"

    def is_business_hours(self) -> bool:
        """Return True during weekday business hours in Adelaide."""
        current = self.now_adelaide()
        return current.weekday() < 5 and 9 <= current.hour < 17

    def is_weekend(self) -> bool:
        """Return True on Saturday or Sunday in Adelaide."""
        return self.now_adelaide().weekday() >= 5

    def greeting(self) -> str:
        """Return an Adelaide-aware greeting."""
        hour = self.now_adelaide().hour
        if 5 <= hour < 12:
            return "Good morning"
        if 12 <= hour < 18:
            return "Good afternoon"
        return "Good evening"


class AgentClock:
    """Generic UTC-first timestamp utilities for agents."""

    def __init__(self, local_timezone: tzinfo | None = None) -> None:
        self._boot_time = datetime.now(UTC)
        self._local_tz = local_timezone or UTC

    def set_local_timezone(self, timezone_info: tzinfo) -> None:
        self._local_tz = timezone_info

    def now(self) -> str:
        return self.now_dt().isoformat().replace("+00:00", "Z")

    def now_dt(self) -> datetime:
        return datetime.now(UTC)

    def local_now(self) -> str:
        return datetime.now(self._local_tz).strftime("%I:%M %p, %A %d %B")

    def stamp(
        self, data: dict[str, object], field: str = "timestamp"
    ) -> dict[str, object]:
        data[field] = self.now()
        return data

    def stamp_sync(self, data: dict[str, object]) -> dict[str, object]:
        return self.stamp(data, field="synced_at")

    def stamp_created(self, data: dict[str, object]) -> dict[str, object]:
        return self.stamp(data, field="created_at")

    def validate(self, timestamp: str | None) -> bool:
        if not timestamp or not isinstance(timestamp, str):
            return False
        return bool(_UTC_PATTERN.match(timestamp.strip()))

    def is_valid(self, timestamp: str | None) -> bool:
        return self.validate(timestamp)

    def fix(self, timestamp: str | None) -> str:
        if not timestamp:
            return self.now()

        normalized = str(timestamp).strip()
        if self.validate(normalized):
            return normalized.replace("+00:00", "Z")

        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            else:
                parsed = parsed.astimezone(UTC)
            return parsed.isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError):
            return self.now()

    def fix_dict(
        self,
        data: dict[str, object],
        fields: list[str] | None = None,
    ) -> dict[str, object]:
        timestamp_fields = fields or [
            "timestamp",
            "created_at",
            "updated_at",
            "synced_at",
            "scraped_at",
        ]
        for field in timestamp_fields:
            value = data.get(field)
            if value:
                data[field] = self.fix(str(value))
        return data

    def age_minutes(self, timestamp: str | None) -> float:
        if not timestamp:
            return float("inf")

        try:
            parsed = datetime.fromisoformat(self.fix(timestamp).replace("Z", "+00:00"))
        except ValueError:
            return float("inf")

        age = (self.now_dt() - parsed).total_seconds() / 60
        return max(0.0, age)

    def age_hours(self, timestamp: str | None) -> float:
        return self.age_minutes(timestamp) / 60

    def is_fresh(self, timestamp: str | None, max_minutes: int = 30) -> bool:
        return self.age_minutes(timestamp) < max_minutes

    def is_stale(self, timestamp: str | None, threshold_minutes: int = 60) -> bool:
        return self.age_minutes(timestamp) >= threshold_minutes

    def age_human(self, timestamp: str | None) -> str:
        minutes = self.age_minutes(timestamp)
        if minutes == float("inf"):
            return "unknown"
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{int(minutes)} minutes ago"
        if minutes < 1440:
            hours = int(minutes / 60)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = int(minutes / 1440)
        return f"{days} day{'s' if days != 1 else ''} ago"

    def status(self) -> dict[str, object]:
        return {
            "utc": self.now(),
            "local": self.local_now(),
            "uptime_minutes": self.age_minutes(self._boot_time.isoformat()),
            "timezone": str(self._local_tz),
        }


def get_clock() -> Clock:
    """Return the one global clock instance."""
    return Clock()


clock = get_clock()
agent_clock = AgentClock()


__all__ = ["AgentClock", "Clock", "agent_clock", "clock", "get_clock"]
