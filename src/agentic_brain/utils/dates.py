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
Date utilities - ALWAYS use system time, NEVER hardcode dates.

AI models have stale training data (typically 2 years old).
This module ensures we always get the REAL current date from the system.
"""

from datetime import datetime, date, timezone
from typing import Optional


def now() -> datetime:
    """Get current datetime from system. NEVER use AI-generated dates."""
    return datetime.now()


def today() -> date:
    """Get current date from system. NEVER use AI-generated dates."""
    return date.today()


def now_utc() -> datetime:
    """Get current UTC datetime from system."""
    return datetime.now(timezone.utc)


def current_year() -> int:
    """Get current year from system. AI training data is ALWAYS stale."""
    return date.today().year


def current_month() -> int:
    """Get current month from system."""
    return date.today().month


def current_day() -> int:
    """Get current day from system."""
    return date.today().day


def iso_date() -> str:
    """Get current date in ISO format (YYYY-MM-DD) from system."""
    return date.today().isoformat()


def iso_datetime() -> str:
    """Get current datetime in ISO format from system."""
    return datetime.now().isoformat()


def format_date(fmt: str = "%Y-%m-%d") -> str:
    """Get formatted current date from system."""
    return date.today().strftime(fmt)


def format_datetime(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Get formatted current datetime from system."""
    return datetime.now().strftime(fmt)


# Convenience constants that update at import time
# (for quick checks, but prefer functions for accuracy)
CURRENT_YEAR = current_year()
CURRENT_DATE = iso_date()


if __name__ == "__main__":
    print(f"Current year: {current_year()}")
    print(f"Current date: {iso_date()}")
    print(f"Current datetime: {iso_datetime()}")
