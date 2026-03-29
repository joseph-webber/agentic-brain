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
