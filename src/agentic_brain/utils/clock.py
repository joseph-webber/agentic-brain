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

"""Thread-safe clock singleton backed only by system time."""

from __future__ import annotations

from datetime import date, datetime, timezone
from threading import Lock
from zoneinfo import ZoneInfo


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
            self._utc_tz = timezone.utc
            self.__class__._initialized = True

    @staticmethod
    def _system_timezone() -> timezone:
        """Return the current system timezone."""
        tzinfo = datetime.now().astimezone().tzinfo
        if tzinfo is None:
            return timezone.utc
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


def get_clock() -> Clock:
    """Return the one global clock instance."""
    return Clock()


clock = get_clock()


__all__ = ["Clock", "clock", "get_clock"]
