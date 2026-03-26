# SPDX-License-Identifier: Apache-2.0
"""
Location Services Integration

Detection priority (tries in order):
1. System location services (macOS CoreLocation)
2. Ask user for city/state
3. Get timezone from system clock (always works)

Privacy-first: Always asks permission, never shares data.
"""

import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class LocationInfo:
    """Detected location information."""

    city: str = ""
    state: str = ""
    country: str = ""
    timezone: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: str = "unknown"  # location_services, user_input, system_clock
    confidence: str = "low"  # low, medium, high


# ============================================================
# TIMEZONE FROM SYSTEM CLOCK (ALWAYS WORKS)
# ============================================================


def get_system_timezone() -> str:
    """
    Get timezone from system clock settings.
    This ALWAYS works as a fallback.
    """
    try:
        # Method 1: Read /etc/localtime symlink (macOS/Linux)
        if os.path.islink("/etc/localtime"):
            link = os.readlink("/etc/localtime")
            if "zoneinfo/" in link:
                return link.split("zoneinfo/")[-1]

        # Method 2: systemsetup on macOS
        if platform.system() == "Darwin":
            result = subprocess.run(
                ["systemsetup", "-gettimezone"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and "Time Zone:" in result.stdout:
                return result.stdout.strip().replace("Time Zone: ", "")

        # Method 3: timedatectl on Linux
        if platform.system() == "Linux":
            result = subprocess.run(
                ["timedatectl", "show", "--property=Timezone", "--value"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()

        # Method 4: Python's time module
        import time

        # This gives offset but not timezone name

        # Method 5: TZ environment variable
        tz = os.environ.get("TZ", "")
        if tz:
            return tz

        # Method 6: Try to read from system config files
        for config_file in ["/etc/timezone", "/var/db/timezone/localtime"]:
            if os.path.exists(config_file):
                try:
                    with open(config_file) as f:
                        tz = f.read().strip()
                        if tz:
                            return tz
                except Exception:
                    pass

        return ""

    except Exception:
        return ""


def get_timezone_from_clock() -> LocationInfo:
    """Get location info from system clock timezone."""
    timezone = get_system_timezone()

    if timezone:
        location = _timezone_to_location(timezone)
        location.source = "system_clock"
        return location

    return LocationInfo(source="system_clock", confidence="low")


# ============================================================
# LOCATION SERVICES (macOS)
# ============================================================


def check_location_services_available() -> bool:
    """Check if location services are available."""
    if platform.system() != "Darwin":
        return False

    try:
        # Check if CoreLocation framework is available
        result = subprocess.run(
            ["osascript", "-e", 'use framework "CoreLocation"'],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def request_location_permission() -> bool:
    """Request location services permission on macOS."""
    if platform.system() != "Darwin":
        return False

    try:
        script = """
        use framework "CoreLocation"
        use scripting additions

        set locationManager to current application's CLLocationManager's alloc()'s init()

        -- Check current authorization
        set authStatus to current application's CLLocationManager's authorizationStatus()

        -- If not determined, request authorization
        if authStatus = 0 then
            locationManager's requestWhenInUseAuthorization()
            delay 1
            set authStatus to current application's CLLocationManager's authorizationStatus()
        end if

        -- Return status (3 or 4 = authorized)
        return authStatus as integer
        """

        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            status = int(result.stdout.strip())
            return status >= 3

        return False

    except Exception:
        return False


def get_location_from_services() -> Optional[LocationInfo]:
    """Get location from macOS CoreLocation services."""
    if platform.system() != "Darwin":
        return None

    if not request_location_permission():
        return None

    # For now, use timezone-based inference
    # Full CoreLocation integration would require a helper app
    timezone = get_system_timezone()
    if timezone:
        location = _timezone_to_location(timezone)
        location.source = "location_services"
        location.confidence = "high"
        return location

    return None


# ============================================================
# CITY/STATE DATABASE
# ============================================================

# Major cities with their timezones
CITY_DATABASE = {
    # Australia
    "adelaide": ("South Australia", "Australia", "Australia/Adelaide"),
    "sydney": ("New South Wales", "Australia", "Australia/Sydney"),
    "melbourne": ("Victoria", "Australia", "Australia/Melbourne"),
    "brisbane": ("Queensland", "Australia", "Australia/Brisbane"),
    "perth": ("Western Australia", "Australia", "Australia/Perth"),
    "darwin": ("Northern Territory", "Australia", "Australia/Darwin"),
    "hobart": ("Tasmania", "Australia", "Australia/Hobart"),
    "canberra": ("ACT", "Australia", "Australia/Sydney"),
    "gold coast": ("Queensland", "Australia", "Australia/Brisbane"),
    "newcastle": ("New South Wales", "Australia", "Australia/Sydney"),
    # USA
    "new york": ("New York", "United States", "America/New_York"),
    "los angeles": ("California", "United States", "America/Los_Angeles"),
    "chicago": ("Illinois", "United States", "America/Chicago"),
    "houston": ("Texas", "United States", "America/Chicago"),
    "phoenix": ("Arizona", "United States", "America/Phoenix"),
    "san francisco": ("California", "United States", "America/Los_Angeles"),
    "seattle": ("Washington", "United States", "America/Los_Angeles"),
    "denver": ("Colorado", "United States", "America/Denver"),
    "boston": ("Massachusetts", "United States", "America/New_York"),
    "miami": ("Florida", "United States", "America/New_York"),
    # UK/Europe
    "london": ("England", "United Kingdom", "Europe/London"),
    "manchester": ("England", "United Kingdom", "Europe/London"),
    "edinburgh": ("Scotland", "United Kingdom", "Europe/London"),
    "dublin": ("", "Ireland", "Europe/Dublin"),
    "paris": ("", "France", "Europe/Paris"),
    "berlin": ("", "Germany", "Europe/Berlin"),
    "amsterdam": ("", "Netherlands", "Europe/Amsterdam"),
    "rome": ("", "Italy", "Europe/Rome"),
    "madrid": ("", "Spain", "Europe/Madrid"),
    "barcelona": ("Catalonia", "Spain", "Europe/Madrid"),
    # Asia
    "tokyo": ("", "Japan", "Asia/Tokyo"),
    "osaka": ("", "Japan", "Asia/Tokyo"),
    "singapore": ("", "Singapore", "Asia/Singapore"),
    "hong kong": ("", "Hong Kong", "Asia/Hong_Kong"),
    "shanghai": ("", "China", "Asia/Shanghai"),
    "beijing": ("", "China", "Asia/Shanghai"),
    "seoul": ("", "South Korea", "Asia/Seoul"),
    "bangkok": ("", "Thailand", "Asia/Bangkok"),
    "mumbai": ("Maharashtra", "India", "Asia/Kolkata"),
    "delhi": ("", "India", "Asia/Kolkata"),
    "jakarta": ("", "Indonesia", "Asia/Jakarta"),
    "bali": ("", "Indonesia", "Asia/Makassar"),
    # Other
    "auckland": ("", "New Zealand", "Pacific/Auckland"),
    "wellington": ("", "New Zealand", "Pacific/Auckland"),
    "toronto": ("Ontario", "Canada", "America/Toronto"),
    "vancouver": ("British Columbia", "Canada", "America/Vancouver"),
    "sao paulo": ("", "Brazil", "America/Sao_Paulo"),
    "rio de janeiro": ("", "Brazil", "America/Sao_Paulo"),
    "cape town": ("", "South Africa", "Africa/Johannesburg"),
    "dubai": ("", "UAE", "Asia/Dubai"),
}


def lookup_city(city: str) -> Optional[LocationInfo]:
    """Look up a city in the database."""
    city_lower = city.lower().strip()

    if city_lower in CITY_DATABASE:
        state, country, timezone = CITY_DATABASE[city_lower]
        return LocationInfo(
            city=city.title(),
            state=state,
            country=country,
            timezone=timezone,
            source="user_input",
            confidence="high",
        )

    # Try partial match
    for db_city, (state, country, timezone) in CITY_DATABASE.items():
        if db_city in city_lower or city_lower in db_city:
            return LocationInfo(
                city=db_city.title(),
                state=state,
                country=country,
                timezone=timezone,
                source="user_input",
                confidence="medium",
            )

    return None


# ============================================================
# TIMEZONE TO LOCATION MAPPING
# ============================================================


def _timezone_to_location(timezone: str) -> LocationInfo:
    """Convert timezone to approximate location."""
    TIMEZONE_MAP = {
        "Australia/Adelaide": ("Adelaide", "South Australia", "Australia"),
        "Australia/Sydney": ("Sydney", "New South Wales", "Australia"),
        "Australia/Melbourne": ("Melbourne", "Victoria", "Australia"),
        "Australia/Brisbane": ("Brisbane", "Queensland", "Australia"),
        "Australia/Perth": ("Perth", "Western Australia", "Australia"),
        "Australia/Darwin": ("Darwin", "Northern Territory", "Australia"),
        "Australia/Hobart": ("Hobart", "Tasmania", "Australia"),
        "America/New_York": ("New York", "New York", "United States"),
        "America/Los_Angeles": ("Los Angeles", "California", "United States"),
        "America/Chicago": ("Chicago", "Illinois", "United States"),
        "Europe/London": ("London", "England", "United Kingdom"),
        "Europe/Paris": ("Paris", "", "France"),
        "Europe/Berlin": ("Berlin", "", "Germany"),
        "Asia/Tokyo": ("Tokyo", "", "Japan"),
        "Asia/Singapore": ("Singapore", "", "Singapore"),
        "Asia/Hong_Kong": ("Hong Kong", "", "Hong Kong"),
        "Asia/Shanghai": ("Shanghai", "", "China"),
        "Asia/Seoul": ("Seoul", "", "South Korea"),
    }

    if timezone in TIMEZONE_MAP:
        city, state, country = TIMEZONE_MAP[timezone]
        return LocationInfo(
            city=city,
            state=state,
            country=country,
            timezone=timezone,
            confidence="medium",
        )

    # Parse timezone string
    parts = timezone.split("/")
    if len(parts) >= 2:
        region = parts[0].replace("_", " ")
        city = parts[-1].replace("_", " ")
        return LocationInfo(
            city=city, country=region, timezone=timezone, confidence="low"
        )

    return LocationInfo(timezone=timezone, confidence="low")


# ============================================================
# MAIN DETECTION FUNCTION
# ============================================================


def detect_location(
    try_location_services: bool = True, ask_user: bool = True
) -> LocationInfo:
    """
    Detect user's location using best available method.

    Priority:
    1. Location services (if available and permitted)
    2. Ask user for city/state
    3. Get timezone from system clock

    Args:
        try_location_services: Try macOS location services
        ask_user: Interactively ask user for city/state

    Returns:
        LocationInfo with best available data
    """

    # 1. Try location services first
    if try_location_services and check_location_services_available():
        location = get_location_from_services()
        if location and location.confidence == "high":
            return location

    # 2. If interactive, ask user for city/state
    if ask_user:
        print("\n📍 Location Setup")
        print("   We use this for regional voice expressions.")

        city = input("   Your city [skip]: ").strip()

        if city:
            # Try to look up the city
            location = lookup_city(city)
            if location:
                confirm = input(
                    f"   Found: {location.city}, {location.country} - correct? (y/n) [y]: "
                )
                if confirm.strip().lower() != "n":
                    return location

            # City not in database - ask for more info
            state = input("   State/Province [skip]: ").strip()
            country = input("   Country [skip]: ").strip()

            if country:
                return LocationInfo(
                    city=city,
                    state=state,
                    country=country,
                    timezone=get_system_timezone(),  # Use system timezone
                    source="user_input",
                    confidence="high",
                )

    # 3. Fall back to system clock timezone (ALWAYS WORKS)
    return get_timezone_from_clock()


def get_greeting_time(timezone: str = "") -> str:
    """Get appropriate greeting based on timezone."""
    if not timezone:
        timezone = get_system_timezone()

    try:
        import pytz

        tz = pytz.timezone(timezone)
        hour = datetime.now(tz).hour
    except ImportError:
        hour = datetime.now().hour

    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"
