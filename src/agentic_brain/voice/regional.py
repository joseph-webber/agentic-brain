# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Regional Voice Intelligence

Learns user's location and adapts voice to regional expressions.
Example: Adelaide uses "heaps good", Queensland uses "sweet as"
"""

import json
import os
import random
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RegionalProfile:
    """Profile of a region's language characteristics"""

    country: str
    state: str
    city: str
    timezone: str
    expressions: Dict[str, str] = field(default_factory=dict)
    greetings: List[str] = field(default_factory=list)
    farewells: List[str] = field(default_factory=list)
    local_knowledge: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RegionalProfile":
        """Create from dictionary"""
        return cls(**data)


from .australian_regions import (
    AUSTRALIAN_CITIES,
    convert_australian_cities_to_profiles,
)

# Convert Australian cities to RegionalProfile objects
_AUSTRALIAN_PROFILES = convert_australian_cities_to_profiles()

# Alias for backward compatibility - now contains RegionalProfile objects
AUSTRALIAN_REGIONS = _AUSTRALIAN_PROFILES

__all__ = [
    "RegionalProfile",
    "RegionalVoice",
    "AUSTRALIAN_REGIONS",
    "INTERNATIONAL_REGIONS",
    "detect_location",
    "get_available_regions",
    "get_regional_voice",
    "list_regions",
]

# International regions
INTERNATIONAL_REGIONS = {
    "uk_london": RegionalProfile(
        country="United Kingdom",
        state="England",
        city="London",
        timezone="Europe/London",
        expressions={
            "great": "brilliant",
            "very": "quite",
            "good": "lovely",
            "thank you": "cheers",
            "thanks": "ta",
            "hello": "hiya",
            "excellent": "smashing",
            "garbage": "rubbish",
            "apartment": "flat",
            "elevator": "lift",
        },
        greetings=["Hiya!", "Alright?", "How do you do?"],
        farewells=["Cheers!", "Ta-ra!", "Cheerio!"],
        local_knowledge={
            "tea": "Tea is sacred - milk, no sugar debate is serious",
            "weather": "Always bring an umbrella",
        },
    ),
    "us_california": RegionalProfile(
        country="United States",
        state="California",
        city="San Francisco",
        timezone="America/Los_Angeles",
        expressions={
            "great": "awesome",
            "very": "super",
            "good": "cool",
            "hello": "hey",
            "excellent": "rad",
            "friend": "dude",
        },
        greetings=["Hey!", "What's up?", "Yo!"],
        farewells=["Later!", "Peace!", "Catch you later!"],
        local_knowledge={
            "tech": "Silicon Valley - tech capital of the world",
            "weather": "Perfect year-round",
        },
    ),
    "ireland": RegionalProfile(
        country="Ireland",
        state="",
        city="Dublin",
        timezone="Europe/Dublin",
        expressions={
            "great": "grand",
            "very": "fierce",
            "good": "lovely",
            "hello": "howya",
            "friend": "lad",
            "thank you": "cheers",
        },
        greetings=["Howya!", "How's the craic?", "Alright?"],
        farewells=["Sláinte!", "Cheers!", "See ya!"],
        local_knowledge={
            "culture": "Friendly, love a good chat and a pint",
            "weather": "Rainy - always bring a jacket",
        },
    ),
}


class RegionalVoice:
    """Voice that adapts to user's region"""

    def __init__(self, config_dir: Optional[str] = None):
        self._config_dir = config_dir or os.path.expanduser("~/.agentic-brain")
        self._config_path = os.path.join(self._config_dir, "location.json")
        self._profile: Optional[RegionalProfile] = None
        self._load_location()

    def _load_location(self):
        """Load location from config or detect"""
        os.makedirs(self._config_dir, exist_ok=True)

        if os.path.exists(self._config_path):
            try:
                with open(self._config_path) as f:
                    data = json.load(f)
                    region_key = data.get("region", "adelaide")

                    # Check for custom profile
                    if "custom_profile" in data:
                        self._profile = RegionalProfile.from_dict(
                            data["custom_profile"]
                        )
                    else:
                        # Load from predefined regions
                        if region_key in _AUSTRALIAN_PROFILES:
                            self._profile = _AUSTRALIAN_PROFILES[region_key]
                        else:
                            self._profile = INTERNATIONAL_REGIONS.get(region_key)
            except Exception as e:
                print(f"Error loading location config: {e}")

        if not self._profile:
            # Default to Adelaide (Joseph's location)
            self._profile = _AUSTRALIAN_PROFILES["adelaide"]
            self.save_location("adelaide")

    def save_location(self, region_key: str):
        """Save location to config"""
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump({"region": region_key}, f, indent=2)

    def save_custom_profile(self, profile: RegionalProfile):
        """Save a custom regional profile"""
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump(
                {"region": "custom", "custom_profile": profile.to_dict()}, f, indent=2
            )
        self._profile = profile

    def regionalize(self, text: str, apply_expressions: bool = True) -> str:
        """Apply regional expressions to text"""
        if not self._profile or not apply_expressions:
            return text

        # Case-insensitive replacement
        result = text
        for standard, regional in self._profile.expressions.items():
            # Replace whole words only
            import re

            pattern = r"\b" + re.escape(standard) + r"\b"
            result = re.sub(pattern, regional, result, flags=re.IGNORECASE)

        return result

    def get_greeting(self) -> str:
        """Get a regional greeting"""
        if self._profile and self._profile.greetings:
            return random.choice(self._profile.greetings)
        return "Hello!"

    def get_farewell(self) -> str:
        """Get a regional farewell"""
        if self._profile and self._profile.farewells:
            return random.choice(self._profile.farewells)
        return "Goodbye!"

    def get_local_knowledge(self, topic: str) -> Optional[str]:
        """Get local knowledge about a topic"""
        if self._profile:
            return self._profile.local_knowledge.get(topic)
        return None

    def get_all_local_knowledge(self) -> Dict[str, str]:
        """Get all local knowledge"""
        if self._profile:
            return self._profile.local_knowledge.copy()
        return {}

    def add_expression(self, standard: str, regional: str):
        """Learn a new regional expression"""
        if self._profile:
            self._profile.expressions[standard.lower()] = regional
            # Save to config
            self.save_custom_profile(self._profile)

    def add_local_knowledge(self, topic: str, info: str):
        """Add local knowledge"""
        if self._profile:
            self._profile.local_knowledge[topic] = info
            self.save_custom_profile(self._profile)

    @property
    def profile(self) -> Optional[RegionalProfile]:
        """Get current profile"""
        return self._profile

    @property
    def region_name(self) -> str:
        """Get region name"""
        if self._profile:
            return (
                f"{self._profile.city}, {self._profile.state}, {self._profile.country}"
            )
        return "Unknown"

    @property
    def timezone(self) -> str:
        """Get timezone"""
        if self._profile:
            return self._profile.timezone
        return "UTC"


def detect_location() -> str:
    """Detect user's location from system settings"""
    try:
        # Try macOS timezone detection
        result = subprocess.run(
            ["readlink", "/etc/localtime"], capture_output=True, text=True, timeout=5
        )
        tz_path = result.stdout.strip()

        # Parse timezone
        if "Adelaide" in tz_path:
            return "adelaide"
        elif "Brisbane" in tz_path:
            return "queensland"
        elif "Melbourne" in tz_path:
            return "melbourne"
        elif "Sydney" in tz_path:
            return "sydney"
        elif "Perth" in tz_path:
            return "perth"
        elif "London" in tz_path:
            return "uk_london"
        elif "Los_Angeles" in tz_path:
            return "us_california"
        elif "Dublin" in tz_path:
            return "ireland"
    except Exception:
        pass

    # Try macOS defaults
    try:
        result = subprocess.run(
            [
                "defaults",
                "read",
                "/Library/Preferences/.GlobalPreferences",
                "AppleLocale",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        locale = result.stdout.strip()
        if "en_AU" in locale:
            # Default to Adelaide for Australian locale
            return "adelaide"
        elif "en_GB" in locale:
            return "uk_london"
        elif "en_US" in locale:
            return "us_california"
        elif "en_IE" in locale:
            return "ireland"
    except Exception:
        pass

    return "adelaide"  # Default to Joseph's location


def get_available_regions() -> Dict[str, Any]:
    """Get all available regions"""
    return {**AUSTRALIAN_CITIES, **INTERNATIONAL_REGIONS}


def list_regions() -> List[str]:
    """List all region keys"""
    return list(get_available_regions().keys())


# Global instance
_regional_voice_instance: Optional[RegionalVoice] = None


def get_regional_voice() -> RegionalVoice:
    """Get the global regional voice instance"""
    global _regional_voice_instance
    if _regional_voice_instance is None:
        _regional_voice_instance = RegionalVoice()
    return _regional_voice_instance


if __name__ == "__main__":
    # Demo
    rv = RegionalVoice()
    print(f"Region: {rv.region_name}")
    print(f"Greeting: {rv.get_greeting()}")
    print(f"Farewell: {rv.get_farewell()}")
    print("\nRegionalized text:")
    print("  Before: That's very great! Thank you!")
    print(f"  After:  {rv.regionalize('That is very great! Thank you!')}")
    print("\nLocal knowledge:")
    for topic, info in rv.get_all_local_knowledge().items():
        print(f"  {topic}: {info}")
