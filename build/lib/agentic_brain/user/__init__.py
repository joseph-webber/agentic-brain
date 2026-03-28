# SPDX-License-Identifier: Apache-2.0
"""User profile management - personalization without sharing to git."""

from .location_service import (
    LocationInfo,
    detect_location,
    get_greeting_time,
    get_system_timezone,
    request_location_permission,
)
from .profile import (
    UserProfile,
    get_user_email,
    get_user_location,
    get_user_name,
    get_user_profile,
    get_user_timezone,
    save_user_profile,
    setup_user_profile,
)

__all__ = [
    # Profile
    "UserProfile",
    "get_user_profile",
    "save_user_profile",
    "setup_user_profile",
    "get_user_name",
    "get_user_email",
    "get_user_timezone",
    "get_user_location",
    # Location
    "LocationInfo",
    "detect_location",
    "get_system_timezone",
    "request_location_permission",
    "get_greeting_time",
]
