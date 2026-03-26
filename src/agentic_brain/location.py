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
Location services for agentic-brain chatbots.

Provides timezone awareness, geolocation, and local service discovery.
Essential for helping users find services in their area.

Features:
- Timezone detection and conversion
- IP-based geolocation (privacy-respecting)
- Postcode/suburb lookup (Australia)
- Distance calculations
- Local service filtering
- Opening hours in local time
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# AUSTRALIAN TIMEZONE DATA
# =============================================================================


class AustralianTimezone(Enum):
    """Australian timezone identifiers."""

    # Eastern
    AEST = "Australia/Sydney"  # NSW, VIC, TAS, QLD (standard)
    AEDT = "Australia/Sydney"  # NSW, VIC, TAS (daylight saving)

    # Central
    ACST = "Australia/Adelaide"  # SA, NT (standard)
    ACDT = "Australia/Adelaide"  # SA (daylight saving)

    # Western
    AWST = "Australia/Perth"  # WA

    # Special
    LHST = "Australia/Lord_Howe"  # Lord Howe Island
    NFT = "Pacific/Norfolk"  # Norfolk Island
    CXT = "Indian/Christmas"  # Christmas Island
    CCT = "Indian/Cocos"  # Cocos Islands


# State to timezone mapping
STATE_TIMEZONES: Dict[str, str] = {
    "NSW": "Australia/Sydney",
    "VIC": "Australia/Melbourne",
    "QLD": "Australia/Brisbane",
    "SA": "Australia/Adelaide",
    "WA": "Australia/Perth",
    "TAS": "Australia/Hobart",
    "NT": "Australia/Darwin",
    "ACT": "Australia/Sydney",
}

# UTC offsets (standard time)
TIMEZONE_OFFSETS: Dict[str, float] = {
    "Australia/Sydney": 10.0,  # AEST +10, AEDT +11
    "Australia/Melbourne": 10.0,
    "Australia/Brisbane": 10.0,  # No DST
    "Australia/Adelaide": 9.5,  # ACST +9:30, ACDT +10:30
    "Australia/Perth": 8.0,  # AWST +8, no DST
    "Australia/Hobart": 10.0,
    "Australia/Darwin": 9.5,  # No DST
    "Australia/Lord_Howe": 10.5,  # +10:30, DST +11
}

# States that observe daylight saving
DST_STATES = {"NSW", "VIC", "SA", "TAS", "ACT"}


# =============================================================================
# LOCATION DATA STRUCTURES
# =============================================================================


@dataclass
class Coordinates:
    """Geographic coordinates."""

    latitude: float
    longitude: float
    accuracy_meters: Optional[float] = None
    source: str = "unknown"  # gps, ip, postcode, manual

    def to_tuple(self) -> Tuple[float, float]:
        """Return as (lat, lon) tuple."""
        return (self.latitude, self.longitude)


@dataclass
class Address:
    """Australian address."""

    street: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: str = "Australia"

    def format_short(self) -> str:
        """Format as 'Suburb STATE Postcode'."""
        parts = []
        if self.suburb:
            parts.append(self.suburb)
        if self.state:
            parts.append(self.state)
        if self.postcode:
            parts.append(self.postcode)
        return " ".join(parts)

    def format_full(self) -> str:
        """Format complete address."""
        parts = []
        if self.street:
            parts.append(self.street)
        if self.suburb:
            parts.append(self.suburb)
        if self.state and self.postcode:
            parts.append(f"{self.state} {self.postcode}")
        elif self.state:
            parts.append(self.state)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass
class UserLocation:
    """Complete user location context."""

    # Geographic
    coordinates: Optional[Coordinates] = None
    address: Optional[Address] = None

    # Timezone
    timezone_id: str = "Australia/Sydney"  # IANA timezone
    utc_offset_hours: float = 10.0
    is_dst: bool = False

    # Derived
    state: Optional[str] = None
    region: Optional[str] = None  # Metro, Regional, Remote

    # Consent
    location_consent: bool = False
    consent_timestamp: Optional[datetime] = None

    # Metadata
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    detection_method: str = "unknown"  # ip, gps, postcode, manual

    def get_local_time(self) -> datetime:
        """Get current time in user's timezone."""
        utc_now = datetime.now(UTC)
        offset = timedelta(hours=self.utc_offset_hours)
        if self.is_dst:
            offset += timedelta(hours=1)
        return utc_now + offset

    def format_local_time(self, fmt: str = "%I:%M %p") -> str:
        """Format current local time."""
        return self.get_local_time().strftime(fmt)

    def get_timezone_abbrev(self) -> str:
        """Get timezone abbreviation (e.g., AEDT, ACST)."""
        if "Adelaide" in self.timezone_id or "Darwin" in self.timezone_id:
            return "ACDT" if self.is_dst else "ACST"
        elif "Perth" in self.timezone_id:
            return "AWST"
        elif "Brisbane" in self.timezone_id:
            return "AEST"  # QLD doesn't do DST
        else:
            return "AEDT" if self.is_dst else "AEST"


# =============================================================================
# AUSTRALIAN POSTCODE DATABASE (Major areas)
# =============================================================================

# Postcode ranges to state mapping
POSTCODE_STATES: Dict[Tuple[int, int], str] = {
    (200, 299): "ACT",
    (800, 899): "NT",
    (900, 999): "QLD",  # Delivery areas
    (1000, 1999): "NSW",  # LVR and PO Boxes
    (2000, 2599): "NSW",
    (2600, 2618): "ACT",
    (2619, 2899): "NSW",
    (2900, 2920): "ACT",
    (2921, 2999): "NSW",
    (3000, 3999): "VIC",
    (4000, 4999): "QLD",
    (5000, 5799): "SA",
    (5800, 5999): "SA",  # Delivery
    (6000, 6797): "WA",
    (6800, 6999): "WA",  # Delivery
    (7000, 7799): "TAS",
    (7800, 7999): "TAS",  # Delivery
}

# Major city postcodes with coordinates
MAJOR_POSTCODES: Dict[str, Dict[str, Any]] = {
    # NSW
    "2000": {"suburb": "Sydney", "state": "NSW", "lat": -33.8688, "lon": 151.2093},
    "2150": {"suburb": "Parramatta", "state": "NSW", "lat": -33.8151, "lon": 151.0011},
    "2500": {"suburb": "Wollongong", "state": "NSW", "lat": -34.4278, "lon": 150.8931},
    "2300": {"suburb": "Newcastle", "state": "NSW", "lat": -32.9283, "lon": 151.7817},
    # VIC
    "3000": {"suburb": "Melbourne", "state": "VIC", "lat": -37.8136, "lon": 144.9631},
    "3220": {"suburb": "Geelong", "state": "VIC", "lat": -38.1499, "lon": 144.3617},
    "3500": {"suburb": "Mildura", "state": "VIC", "lat": -34.2087, "lon": 142.1393},
    # QLD
    "4000": {"suburb": "Brisbane", "state": "QLD", "lat": -27.4698, "lon": 153.0251},
    "4217": {"suburb": "Gold Coast", "state": "QLD", "lat": -28.0167, "lon": 153.4000},
    "4870": {"suburb": "Cairns", "state": "QLD", "lat": -16.9186, "lon": 145.7781},
    "4810": {"suburb": "Townsville", "state": "QLD", "lat": -19.2590, "lon": 146.8169},
    # SA
    "5000": {"suburb": "Adelaide", "state": "SA", "lat": -34.9285, "lon": 138.6007},
    "5045": {"suburb": "Glenelg", "state": "SA", "lat": -34.9833, "lon": 138.5167},
    "5108": {"suburb": "Salisbury", "state": "SA", "lat": -34.7667, "lon": 138.6333},
    # WA
    "6000": {"suburb": "Perth", "state": "WA", "lat": -31.9505, "lon": 115.8605},
    "6230": {"suburb": "Bunbury", "state": "WA", "lat": -33.3271, "lon": 115.6414},
    # TAS
    "7000": {"suburb": "Hobart", "state": "TAS", "lat": -42.8821, "lon": 147.3272},
    "7250": {"suburb": "Launceston", "state": "TAS", "lat": -41.4332, "lon": 147.1441},
    # NT
    "0800": {"suburb": "Darwin", "state": "NT", "lat": -12.4634, "lon": 130.8456},
    "0870": {
        "suburb": "Alice Springs",
        "state": "NT",
        "lat": -23.6980,
        "lon": 133.8807,
    },
    # ACT
    "2600": {"suburb": "Canberra", "state": "ACT", "lat": -35.2809, "lon": 149.1300},
    "2617": {"suburb": "Belconnen", "state": "ACT", "lat": -35.2394, "lon": 149.0653},
}


# =============================================================================
# LOCATION SERVICE
# =============================================================================


class LocationService:
    """
    Location services for agentic-brain chatbots.

    Provides:
    - Timezone detection from state/postcode
    - Distance calculations
    - Local time formatting
    - Service filtering by proximity

    Privacy-respecting: No external API calls by default.
    All geolocation is done locally using postcode database.
    """

    def __init__(self):
        self.postcode_data = MAJOR_POSTCODES
        self.state_timezones = STATE_TIMEZONES
        self._current_location: Optional[UserLocation] = None

    @property
    def current_location(self) -> Optional[UserLocation]:
        """Get current user location if set."""
        return self._current_location

    def set_location_from_state(self, state: str) -> UserLocation:
        """
        Set user location from Australian state.

        Args:
            state: Australian state code (NSW, VIC, QLD, SA, WA, TAS, NT, ACT)

        Returns:
            UserLocation with timezone set
        """
        state = state.upper()

        if state not in STATE_TIMEZONES:
            raise ValueError(
                f"Unknown state: {state}. Use NSW, VIC, QLD, SA, WA, TAS, NT, or ACT"
            )

        tz_id = STATE_TIMEZONES[state]
        offset = TIMEZONE_OFFSETS.get(tz_id, 10.0)
        is_dst = self._is_dst_active(state)

        location = UserLocation(
            timezone_id=tz_id,
            utc_offset_hours=offset,
            is_dst=is_dst,
            state=state,
            address=Address(state=state),
            detection_method="state",
        )

        self._current_location = location
        logger.info(f"Location set to {state}, timezone {tz_id}")

        return location

    def set_location_from_postcode(self, postcode: str) -> UserLocation:
        """
        Set user location from Australian postcode.

        Args:
            postcode: Australian postcode (4 digits)

        Returns:
            UserLocation with timezone and coordinates if known
        """
        postcode = postcode.strip().zfill(4)

        # Get state from postcode
        state = self._postcode_to_state(postcode)
        if not state:
            raise ValueError(f"Invalid postcode: {postcode}")

        tz_id = STATE_TIMEZONES[state]
        offset = TIMEZONE_OFFSETS.get(tz_id, 10.0)
        is_dst = self._is_dst_active(state)

        # Try to get coordinates from known postcodes
        coords = None
        suburb = None
        if postcode in self.postcode_data:
            data = self.postcode_data[postcode]
            coords = Coordinates(
                latitude=data["lat"],
                longitude=data["lon"],
                source="postcode",
            )
            suburb = data.get("suburb")

        location = UserLocation(
            coordinates=coords,
            timezone_id=tz_id,
            utc_offset_hours=offset,
            is_dst=is_dst,
            state=state,
            address=Address(
                suburb=suburb,
                state=state,
                postcode=postcode,
            ),
            detection_method="postcode",
        )

        self._current_location = location
        logger.info(f"Location set to {postcode} ({state})")

        return location

    def set_location_from_coordinates(
        self,
        latitude: float,
        longitude: float,
        accuracy_meters: Optional[float] = None,
    ) -> UserLocation:
        """
        Set user location from GPS coordinates.

        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            accuracy_meters: GPS accuracy

        Returns:
            UserLocation with nearest state/timezone
        """
        coords = Coordinates(
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            source="gps",
        )

        # Determine state from coordinates (simplified - uses nearest capital)
        state = self._coords_to_state(latitude, longitude)
        tz_id = STATE_TIMEZONES.get(state, "Australia/Sydney")
        offset = TIMEZONE_OFFSETS.get(tz_id, 10.0)
        is_dst = self._is_dst_active(state)

        location = UserLocation(
            coordinates=coords,
            timezone_id=tz_id,
            utc_offset_hours=offset,
            is_dst=is_dst,
            state=state,
            detection_method="gps",
        )

        self._current_location = location
        logger.info(f"Location set to ({latitude}, {longitude}) -> {state}")

        return location

    def get_local_time(self, location: Optional[UserLocation] = None) -> datetime:
        """
        Get current time in user's local timezone.

        Args:
            location: UserLocation or None to use current

        Returns:
            Current datetime in local timezone
        """
        loc = location or self._current_location
        if not loc:
            # Default to Sydney
            loc = UserLocation()

        return loc.get_local_time()

    def format_time_for_user(
        self,
        utc_time: datetime,
        location: Optional[UserLocation] = None,
        include_timezone: bool = True,
    ) -> str:
        """
        Format a UTC time for display in user's timezone.

        Args:
            utc_time: Time in UTC
            location: UserLocation or None to use current
            include_timezone: Whether to append timezone abbreviation

        Returns:
            Formatted time string like "2:30 PM AEDT"
        """
        loc = location or self._current_location
        if not loc:
            loc = UserLocation()

        offset = timedelta(hours=loc.utc_offset_hours)
        if loc.is_dst:
            offset += timedelta(hours=1)

        local_time = utc_time + offset
        formatted = local_time.strftime("%I:%M %p")

        if include_timezone:
            formatted += f" {loc.get_timezone_abbrev()}"

        return formatted

    def calculate_distance_km(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Calculate distance between two points using Haversine formula.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in km

        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)

        a = (
            sin(delta_lat / 2) ** 2
            + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        )
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    def filter_services_by_distance(
        self,
        services: List[Dict[str, Any]],
        max_distance_km: float = 50,
        location: Optional[UserLocation] = None,
    ) -> List[Dict[str, Any]]:
        """
        Filter services by distance from user location.

        Args:
            services: List of services with 'latitude' and 'longitude' keys
            max_distance_km: Maximum distance in kilometers
            location: UserLocation or None to use current

        Returns:
            Services within max_distance_km, sorted by distance
        """
        loc = location or self._current_location
        if not loc or not loc.coordinates:
            logger.warning("No location set, returning all services")
            return services

        user_lat = loc.coordinates.latitude
        user_lon = loc.coordinates.longitude

        results = []
        for service in services:
            if "latitude" in service and "longitude" in service:
                distance = self.calculate_distance_km(
                    user_lat, user_lon, service["latitude"], service["longitude"]
                )
                if distance <= max_distance_km:
                    service_copy = service.copy()
                    service_copy["distance_km"] = round(distance, 1)
                    results.append(service_copy)

        # Sort by distance
        results.sort(key=lambda x: x.get("distance_km", float("inf")))

        return results

    def filter_services_by_state(
        self,
        services: List[Dict[str, Any]],
        location: Optional[UserLocation] = None,
        include_national: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Filter services by user's state.

        Args:
            services: List of services with 'states' or 'national' keys
            location: UserLocation or None to use current
            include_national: Include services marked as national

        Returns:
            Services available in user's state
        """
        loc = location or self._current_location
        if not loc or not loc.state:
            logger.warning("No state set, returning all services")
            return services

        user_state = loc.state.upper()
        results = []

        for service in services:
            # Check if national
            if include_national and service.get("national", False):
                results.append(service)
                continue

            # Check state list
            states = service.get("states", [])
            if isinstance(states, str):
                states = [states]

            if user_state in [s.upper() for s in states]:
                results.append(service)

        return results

    def is_business_hours(
        self,
        location: Optional[UserLocation] = None,
        start_hour: int = 9,
        end_hour: int = 17,
    ) -> bool:
        """
        Check if current time is within business hours.

        Args:
            location: UserLocation or None to use current
            start_hour: Business start hour (default 9am)
            end_hour: Business end hour (default 5pm)

        Returns:
            True if within business hours
        """
        local_time = self.get_local_time(location)
        hour = local_time.hour
        weekday = local_time.weekday()  # 0=Monday, 6=Sunday

        # Weekend check
        if weekday >= 5:
            return False

        return start_hour <= hour < end_hour

    def get_greeting(self, location: Optional[UserLocation] = None) -> str:
        """
        Get time-appropriate greeting.

        Args:
            location: UserLocation or None to use current

        Returns:
            "Good morning", "Good afternoon", or "Good evening"
        """
        local_time = self.get_local_time(location)
        hour = local_time.hour

        if 5 <= hour < 12:
            return "Good morning"
        elif 12 <= hour < 17:
            return "Good afternoon"
        else:
            return "Good evening"

    def format_location_context(
        self,
        location: Optional[UserLocation] = None,
    ) -> str:
        """
        Format location context for display.

        Returns something like:
        "📍 Adelaide, SA | 🕐 2:30 PM ACDT | Business hours"
        """
        loc = location or self._current_location
        if not loc:
            return "📍 Location not set"

        parts = []

        # Location
        if loc.address and loc.address.suburb:
            parts.append(f"📍 {loc.address.format_short()}")
        elif loc.state:
            parts.append(f"📍 {loc.state}")

        # Time
        parts.append(f"🕐 {loc.format_local_time()} {loc.get_timezone_abbrev()}")

        # Business hours status
        if self.is_business_hours(loc):
            parts.append("✅ Business hours")
        else:
            parts.append("🌙 After hours")

        return " | ".join(parts)

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _postcode_to_state(self, postcode: str) -> Optional[str]:
        """Convert postcode to state code."""
        try:
            pc = int(postcode)
        except ValueError:
            return None

        for (start, end), state in POSTCODE_STATES.items():
            if start <= pc <= end:
                return state

        return None

    def _coords_to_state(self, lat: float, lon: float) -> str:
        """Determine state from coordinates (simplified)."""
        # Simple bounding box check for Australian states
        if lat > -20:
            # North - QLD or NT
            if lon < 130:
                return "NT"
            else:
                return "QLD"
        elif lat < -35:
            # South - VIC, TAS, or SA
            if lon < 140:
                return "SA"
            elif lat < -40:
                return "TAS"
            else:
                return "VIC"
        else:
            # Middle band
            if lon < 130:
                return "WA"
            elif lon < 140:
                return "SA"
            elif lon < 149:
                return "NSW"
            else:
                return "NSW"  # East coast

    def _is_dst_active(self, state: str) -> bool:
        """
        Check if daylight saving is currently active.

        DST in Australia:
        - Starts: First Sunday in October at 2am
        - Ends: First Sunday in April at 3am
        - States: NSW, VIC, SA, TAS, ACT (not QLD, NT, WA)
        """
        if state not in DST_STATES:
            return False

        now = datetime.now(UTC)
        month = now.month

        # Simple check: DST is October-March inclusive
        # (More precise would check exact Sunday transitions)
        return month >= 10 or month <= 3


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global location service instance (lazy initialized)
_location_service: Optional[LocationService] = None


def get_location_service() -> LocationService:
    """Get or create the global location service instance."""
    global _location_service
    if _location_service is None:
        _location_service = LocationService()
    return _location_service


def detect_timezone_from_state(state: str) -> str:
    """Quick function to get timezone ID from state."""
    return STATE_TIMEZONES.get(state.upper(), "Australia/Sydney")


def format_phone_for_state(phone: str, state: str) -> str:
    """
    Format a phone number appropriately for the user's state.

    For interstate calls, may need to add area code.
    """
    # Most Australian services use national numbers (13xx, 1800, 1300)
    # which work from any state
    phone = phone.replace(" ", "").replace("-", "")

    # Format nicely
    if phone.startswith("1800") or phone.startswith("1300"):
        return f"{phone[:4]} {phone[4:7]} {phone[7:]}"
    elif phone.startswith("13") and len(phone) == 6:
        return f"{phone[:2]} {phone[2:4]} {phone[4:]}"
    elif phone.startswith("04"):
        return f"{phone[:4]} {phone[4:7]} {phone[7:]}"
    elif phone.startswith("0"):
        return f"({phone[:2]}) {phone[2:6]} {phone[6:]}"

    return phone


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Main classes
    "LocationService",
    "UserLocation",
    "Address",
    "Coordinates",
    # Enums
    "AustralianTimezone",
    # Data
    "STATE_TIMEZONES",
    "TIMEZONE_OFFSETS",
    "MAJOR_POSTCODES",
    # Functions
    "get_location_service",
    "detect_timezone_from_state",
    "format_phone_for_state",
]
