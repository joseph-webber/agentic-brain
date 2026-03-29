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

"""Tests for the global Adelaide-aware clock singleton."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo

from agentic_brain.utils import Clock, clock, get_clock

ADELAIDE = ZoneInfo("Australia/Adelaide")


def test_get_clock_returns_singleton_instance():
    """The exported clock access points should all return the same instance."""
    assert get_clock() is get_clock()
    assert get_clock() is clock
    assert Clock() is clock


def test_singleton_is_thread_safe():
    """Concurrent access should still return one instance."""
    with ThreadPoolExecutor(max_workers=16) as executor:
        instances = list(executor.map(lambda _: get_clock(), range(64)))

    assert {id(instance) for instance in instances} == {id(clock)}


def test_core_methods_return_adelaide_aware_values(monkeypatch):
    """Core methods should use Adelaide time and real system-derived values."""
    current_adelaide = datetime(2026, 3, 29, 15, 45, 12, tzinfo=ADELAIDE)
    current_utc = current_adelaide.astimezone(UTC)

    monkeypatch.setattr(Clock, "now_adelaide", lambda self: current_adelaide)
    monkeypatch.setattr(Clock, "now_utc", lambda self: current_utc)

    current = clock.now()

    assert current.tzinfo == ADELAIDE
    assert current_adelaide.tzinfo == ADELAIDE
    assert current_utc.tzinfo == UTC
    assert clock.today() == current_adelaide.date()
    assert clock.year() == clock.today().year
    assert clock.iso_date() == clock.today().isoformat()
    assert clock.iso_datetime() == current_adelaide.isoformat()


def test_timezone_conversion_handles_aware_and_naive_datetimes():
    """Timezone conversion should normalize both aware and naive values."""
    utc_dt = datetime(2026, 3, 29, 1, 0, tzinfo=UTC)
    naive_dt = datetime(2026, 3, 29, 11, 30)

    adelaide_from_utc = clock.to_adelaide(utc_dt)
    utc_from_adelaide = clock.to_utc(adelaide_from_utc)
    adelaide_from_naive = clock.to_adelaide(naive_dt)

    assert adelaide_from_utc.tzinfo == ADELAIDE
    assert utc_from_adelaide.tzinfo == UTC
    assert utc_from_adelaide == utc_dt
    assert adelaide_from_naive.tzinfo == ADELAIDE


def test_formatting_and_validation_helpers(monkeypatch):
    """Formatting, greeting, and business rules should use Adelaide time."""
    morning = datetime(2026, 3, 30, 9, 45, tzinfo=ADELAIDE)
    afternoon = datetime(2026, 3, 30, 15, 45, tzinfo=ADELAIDE)
    evening_weekend = datetime(2026, 3, 29, 19, 30, tzinfo=ADELAIDE)

    monkeypatch.setattr(Clock, "now_adelaide", lambda self: morning)
    assert clock.format("%Y-%m-%d %H:%M") == "2026-03-30 09:45"
    assert clock.human_time() == "9:45 AM"
    assert clock.human_date() == "Monday, March 30, 2026"
    assert clock.is_business_hours() is True
    assert clock.is_weekend() is False
    assert clock.greeting() == "Good morning"

    monkeypatch.setattr(Clock, "now_adelaide", lambda self: afternoon)
    assert clock.greeting() == "Good afternoon"

    monkeypatch.setattr(Clock, "now_adelaide", lambda self: evening_weekend)
    assert clock.is_business_hours() is False
    assert clock.is_weekend() is True
    assert clock.greeting() == "Good evening"
