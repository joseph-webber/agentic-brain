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

"""
Clock MCP Server - Provides reliable date/time tools for AI agents.

This server exposes clock/time tools that ensure AI agents ALWAYS get correct dates.
Uses the thread-safe Clock singleton to prevent stale date issues.

Tools provided:
- clock_now: Get current datetime in various formats
- clock_adelaide: Get Adelaide time (Joseph's timezone)
- clock_utc: Get UTC time
- clock_year: Get current year (NEVER stale!)
- clock_date: Get current date in ISO format
- clock_greeting: Get appropriate greeting based on Adelaide time
- clock_is_business_hours: Check if Adelaide business hours
- clock_convert: Convert between timezones
- clock_format: Format current time with custom format string
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from agentic_brain.utils.clock import get_clock

logger = logging.getLogger(__name__)

# Get the singleton clock instance
_clock = None


def _get_clock():
    """Lazy-load the clock instance."""
    global _clock
    if _clock is None:
        _clock = get_clock()
    return _clock


# =============================================================================
# Clock Tools
# =============================================================================


def clock_now(format_type: str = "iso") -> str:
    """
    Get current Adelaide datetime in various formats.

    Args:
        format_type: Output format - "iso", "human", "timestamp", "full"

    Returns:
        Current Adelaide time in requested format

    Examples:
        clock_now("iso") -> "2026-03-22T15:30:45.123456+10:30"
        clock_now("human") -> "3:30 PM"
        clock_now("full") -> "Friday, March 22, 2026 at 3:30 PM"
    """
    clock = _get_clock()
    current = clock.now_adelaide()

    if format_type == "iso":
        return current.isoformat()
    elif format_type == "human":
        return clock.human_time()
    elif format_type == "timestamp":
        return str(int(current.timestamp()))
    elif format_type == "full":
        return f"{clock.human_date()} at {clock.human_time()}"
    else:
        return current.isoformat()


def clock_adelaide() -> str:
    """
    Get current Adelaide time (Joseph's timezone).

    Adelaide is UTC+10:30 (ACDT) or UTC+9:30 (ACST).

    Returns:
        JSON with Adelaide time details

    Example:
        {
            "datetime": "2026-03-22T15:30:45.123456+10:30",
            "date": "2026-03-22",
            "time": "3:30 PM",
            "timezone": "Australia/Adelaide",
            "offset": "+10:30",
            "year": 2026,
            "greeting": "Good afternoon"
        }
    """
    clock = _get_clock()
    current = clock.now_adelaide()

    result = {
        "datetime": current.isoformat(),
        "date": current.date().isoformat(),
        "time": clock.human_time(),
        "timezone": "Australia/Adelaide",
        "offset": current.strftime("%z"),
        "year": current.year,
        "day": current.strftime("%A"),
        "greeting": clock.greeting(),
        "is_business_hours": clock.is_business_hours(),
        "is_weekend": clock.is_weekend(),
    }

    return json.dumps(result, indent=2)


def clock_utc() -> str:
    """
    Get current UTC time.

    Returns:
        JSON with UTC time details

    Example:
        {
            "datetime": "2026-03-22T05:00:45.123456+00:00",
            "date": "2026-03-22",
            "time": "05:00:45",
            "timezone": "UTC"
        }
    """
    clock = _get_clock()
    current = clock.now_utc()

    result = {
        "datetime": current.isoformat(),
        "date": current.date().isoformat(),
        "time": current.strftime("%H:%M:%S"),
        "timezone": "UTC",
        "timestamp": int(current.timestamp()),
    }

    return json.dumps(result, indent=2)


def clock_year() -> str:
    """
    Get the current year in Adelaide timezone.

    CRITICAL: This ensures AI agents never use stale year data.
    The year 2026 should NEVER be confused with 2024 or 2023.

    Returns:
        Current year as string

    Example:
        "2026"
    """
    clock = _get_clock()
    year = clock.year()

    # Return comprehensive info
    result = {
        "year": year,
        "message": f"The current year is {year}",
        "warning": "AI training data is ~2 years stale. Use web search for current info.",
    }

    return json.dumps(result, indent=2)


def clock_date() -> str:
    """
    Get current date in Adelaide timezone (ISO format).

    Returns:
        Current date as YYYY-MM-DD

    Example:
        "2026-03-22"
    """
    clock = _get_clock()
    return clock.iso_date()


def clock_greeting() -> str:
    """
    Get appropriate greeting based on Adelaide time of day.

    Returns:
        JSON with greeting and time context

    Example:
        {
            "greeting": "Good afternoon",
            "time": "3:30 PM",
            "hour": 15,
            "reason": "Between 12:00 and 18:00"
        }
    """
    clock = _get_clock()
    current = clock.now_adelaide()
    hour = current.hour
    greeting = clock.greeting()

    # Determine reason
    if 5 <= hour < 12:
        reason = "Between 05:00 and 12:00"
    elif 12 <= hour < 18:
        reason = "Between 12:00 and 18:00"
    else:
        reason = "Between 18:00 and 05:00"

    result = {
        "greeting": greeting,
        "time": clock.human_time(),
        "hour": hour,
        "reason": reason,
    }

    return json.dumps(result, indent=2)


def clock_is_business_hours() -> str:
    """
    Check if it's currently business hours in Adelaide.

    Business hours are Monday-Friday, 9 AM - 5 PM.

    Returns:
        JSON with business hours status

    Example:
        {
            "is_business_hours": true,
            "is_weekend": false,
            "time": "3:30 PM",
            "day": "Friday"
        }
    """
    clock = _get_clock()
    current = clock.now_adelaide()

    result = {
        "is_business_hours": clock.is_business_hours(),
        "is_weekend": clock.is_weekend(),
        "time": clock.human_time(),
        "day": current.strftime("%A"),
        "hour": current.hour,
    }

    return json.dumps(result, indent=2)


def clock_convert(
    from_tz: str = "UTC",
    to_tz: str = "Australia/Adelaide",
    iso_datetime: str | None = None,
) -> str:
    """
    Convert time between timezones.

    Args:
        from_tz: Source timezone (e.g., "UTC", "America/New_York")
        to_tz: Target timezone (e.g., "Australia/Adelaide", "Europe/London")
        iso_datetime: ISO datetime string to convert (uses current time if None)

    Returns:
        JSON with conversion details

    Example:
        clock_convert("UTC", "Australia/Adelaide", "2026-03-22T05:00:00Z")
        ->
        {
            "from": {
                "datetime": "2026-03-22T05:00:00+00:00",
                "timezone": "UTC"
            },
            "to": {
                "datetime": "2026-03-22T15:30:00+10:30",
                "timezone": "Australia/Adelaide"
            }
        }
    """
    clock = _get_clock()

    # Parse or use current time
    if iso_datetime:
        dt = datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
    else:
        dt = datetime.now(ZoneInfo(from_tz))

    # Ensure timezone aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(from_tz))

    # Convert to target timezone
    to_dt = dt.astimezone(ZoneInfo(to_tz))

    result = {
        "from": {
            "datetime": dt.isoformat(),
            "timezone": from_tz,
        },
        "to": {
            "datetime": to_dt.isoformat(),
            "timezone": to_tz,
        },
        "offset_hours": (
            to_dt.utcoffset().total_seconds() - dt.utcoffset().total_seconds()
        )
        / 3600,
    }

    return json.dumps(result, indent=2)


def clock_format(format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format current Adelaide time with custom strftime format.

    Args:
        format_string: Python strftime format string

    Returns:
        Formatted time string

    Common formats:
        "%Y-%m-%d" -> "2026-03-22"
        "%I:%M %p" -> "03:30 PM"
        "%A, %B %d, %Y" -> "Friday, March 22, 2026"
        "%Y-%m-%d %H:%M:%S" -> "2026-03-22 15:30:45"

    Example:
        clock_format("%A, %B %d, %Y") -> "Friday, March 22, 2026"
    """
    clock = _get_clock()
    return clock.format(format_string)


# =============================================================================
# Tool Registration
# =============================================================================

# Tools registry for auto-discovery
CLOCK_TOOLS = {
    "clock_now": {
        "function": clock_now,
        "description": "Get current Adelaide datetime in various formats (iso, human, timestamp, full)",
    },
    "clock_adelaide": {
        "function": clock_adelaide,
        "description": "Get comprehensive Adelaide time information (Joseph's timezone)",
    },
    "clock_utc": {
        "function": clock_utc,
        "description": "Get current UTC time",
    },
    "clock_year": {
        "function": clock_year,
        "description": "Get current year (NEVER stale!) - critical for preventing date confusion",
    },
    "clock_date": {
        "function": clock_date,
        "description": "Get current date in ISO format (YYYY-MM-DD)",
    },
    "clock_greeting": {
        "function": clock_greeting,
        "description": "Get appropriate greeting based on Adelaide time of day",
    },
    "clock_is_business_hours": {
        "function": clock_is_business_hours,
        "description": "Check if currently business hours in Adelaide (Mon-Fri 9AM-5PM)",
    },
    "clock_convert": {
        "function": clock_convert,
        "description": "Convert time between timezones",
    },
    "clock_format": {
        "function": clock_format,
        "description": "Format current Adelaide time with custom strftime format",
    },
}


def get_clock_tools() -> dict[str, dict[str, Any]]:
    """
    Get all clock tools for registration.

    Returns:
        Dictionary of tool name -> tool info
    """
    return CLOCK_TOOLS


__all__ = [
    "clock_now",
    "clock_adelaide",
    "clock_utc",
    "clock_year",
    "clock_date",
    "clock_greeting",
    "clock_is_business_hours",
    "clock_convert",
    "clock_format",
    "get_clock_tools",
    "CLOCK_TOOLS",
]
