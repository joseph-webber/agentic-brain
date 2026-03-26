# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Tests for Regional Voice Intelligence.

Tests location detection, regional expressions, and local knowledge.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from agentic_brain.voice.regional import (
    AUSTRALIAN_REGIONS,
    INTERNATIONAL_REGIONS,
    RegionalProfile,
    RegionalVoice,
    detect_location,
    get_available_regions,
    get_regional_voice,
    list_regions,
)


class TestRegionalProfile:
    """Test RegionalProfile dataclass."""

    def test_create_profile(self):
        """Test creating a regional profile."""
        profile = RegionalProfile(
            country="Australia",
            state="South Australia",
            city="Adelaide",
            timezone="Australia/Adelaide",
            expressions={"great": "heaps good"},
            greetings=["G'day!"],
            farewells=["See ya!"],
            local_knowledge={"coffee": "Flat whites are popular"},
        )

        assert profile.country == "Australia"
        assert profile.city == "Adelaide"
        assert profile.expressions["great"] == "heaps good"
        assert "G'day!" in profile.greetings

    def test_to_dict(self):
        """Test converting profile to dictionary."""
        profile = AUSTRALIAN_REGIONS["adelaide"]
        data = profile.to_dict()

        assert isinstance(data, dict)
        assert data["country"] == "Australia"
        assert data["city"] == "Adelaide"
        assert "expressions" in data

    def test_from_dict(self):
        """Test creating profile from dictionary."""
        data = {
            "country": "Australia",
            "state": "Victoria",
            "city": "Melbourne",
            "timezone": "Australia/Melbourne",
            "expressions": {"great": "ripper"},
            "greetings": ["G'day!"],
            "farewells": ["See ya!"],
            "local_knowledge": {},
        }

        profile = RegionalProfile.from_dict(data)
        assert profile.city == "Melbourne"
        assert profile.expressions["great"] == "ripper"


class TestRegionalVoice:
    """Test RegionalVoice class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_init_default(self, temp_config_dir):
        """Test initialization with default Adelaide."""
        rv = RegionalVoice(config_dir=temp_config_dir)
        assert rv.profile is not None
        assert rv.profile.city == "Adelaide"

    def test_regionalize_adelaide(self, temp_config_dir):
        """Test Adelaide-specific regionalizations."""
        rv = RegionalVoice(config_dir=temp_config_dir)

        # Test expressions
        text = "That is very great! Thank you!"
        result = rv.regionalize(text)

        # Should contain Adelaide expressions
        assert "heaps" in result.lower()
        assert "cheers" in result.lower()

    def test_regionalize_case_insensitive(self, temp_config_dir):
        """Test case-insensitive regionalization."""
        rv = RegionalVoice(config_dir=temp_config_dir)

        # Mixed case
        text = "That is VERY great! THANK YOU!"
        result = rv.regionalize(text)

        assert "heaps" in result.lower() or "HEAPS" in result

    def test_regionalize_whole_words(self, temp_config_dir):
        """Test whole word matching only."""
        rv = RegionalVoice(config_dir=temp_config_dir)

        # Should not replace "very" in "everything"
        text = "everything is great"
        result = rv.regionalize(text)

        # "very" in "everything" should not be replaced
        assert "everything" in result or "eheapsything" not in result

    def test_get_greeting(self, temp_config_dir):
        """Test getting regional greetings."""
        rv = RegionalVoice(config_dir=temp_config_dir)
        greeting = rv.get_greeting()

        assert greeting in AUSTRALIAN_REGIONS["adelaide"].greetings

    def test_get_farewell(self, temp_config_dir):
        """Test getting regional farewells."""
        rv = RegionalVoice(config_dir=temp_config_dir)
        farewell = rv.get_farewell()

        assert farewell in AUSTRALIAN_REGIONS["adelaide"].farewells

    def test_get_local_knowledge(self, temp_config_dir):
        """Test getting local knowledge."""
        rv = RegionalVoice(config_dir=temp_config_dir)

        coffee = rv.get_local_knowledge("coffee_order")
        assert coffee is not None
        assert "flat white" in coffee.lower()

        football = rv.get_local_knowledge("football")
        assert football is not None
        assert "AFL" in football or "Crows" in football or "Power" in football

    def test_save_and_load_location(self, temp_config_dir):
        """Test saving and loading location."""
        rv = RegionalVoice(config_dir=temp_config_dir)

        # Save Melbourne
        rv.save_location("melbourne")

        # Create new instance - should load Melbourne
        rv2 = RegionalVoice(config_dir=temp_config_dir)
        assert rv2.profile.city == "Melbourne"

    def test_save_custom_profile(self, temp_config_dir):
        """Test saving custom profile."""
        rv = RegionalVoice(config_dir=temp_config_dir)

        custom = RegionalProfile(
            country="Test",
            state="Test State",
            city="Test City",
            timezone="UTC",
            expressions={"hello": "howdy"},
            greetings=["Howdy!"],
            farewells=["Bye!"],
            local_knowledge={"test": "data"},
        )

        rv.save_custom_profile(custom)

        # Load should get custom profile
        rv2 = RegionalVoice(config_dir=temp_config_dir)
        assert rv2.profile.city == "Test City"
        assert rv2.profile.expressions["hello"] == "howdy"

    def test_add_expression(self, temp_config_dir):
        """Test adding new expressions."""
        rv = RegionalVoice(config_dir=temp_config_dir)

        rv.add_expression("awesome", "grouse")
        assert rv.profile.expressions["awesome"] == "grouse"

        # Should persist
        rv2 = RegionalVoice(config_dir=temp_config_dir)
        assert rv2.profile.expressions.get("awesome") == "grouse"

    def test_add_local_knowledge(self, temp_config_dir):
        """Test adding local knowledge."""
        rv = RegionalVoice(config_dir=temp_config_dir)

        rv.add_local_knowledge("test_topic", "test info")
        assert rv.get_local_knowledge("test_topic") == "test info"

        # Should persist
        rv2 = RegionalVoice(config_dir=temp_config_dir)
        assert rv2.get_local_knowledge("test_topic") == "test info"

    def test_region_name(self, temp_config_dir):
        """Test region name property."""
        rv = RegionalVoice(config_dir=temp_config_dir)
        name = rv.region_name

        assert "Adelaide" in name
        assert "Australia" in name

    def test_timezone(self, temp_config_dir):
        """Test timezone property."""
        rv = RegionalVoice(config_dir=temp_config_dir)
        tz = rv.timezone

        assert "Adelaide" in tz or "Australia" in tz


class TestAustralianRegions:
    """Test Australian regional profiles."""

    def test_adelaide_profile(self):
        """Test Adelaide profile completeness."""
        profile = AUSTRALIAN_REGIONS["adelaide"]

        assert profile.country == "Australia"
        assert profile.state == "South Australia"
        assert profile.city == "Adelaide"
        assert profile.timezone == "Australia/Adelaide"

        # Check expressions
        assert "great" in profile.expressions
        assert profile.expressions["great"] == "heaps good"
        assert "bottle shop" in profile.expressions
        assert profile.expressions["bottle shop"] == "bottle-o"

        # Check greetings/farewells
        assert len(profile.greetings) > 0
        assert len(profile.farewells) > 0

        # Check local knowledge
        assert "football" in profile.local_knowledge
        assert "wine_region" in profile.local_knowledge
        assert "beach" in profile.local_knowledge

    def test_melbourne_profile(self):
        """Test Melbourne profile."""
        profile = AUSTRALIAN_REGIONS["melbourne"]

        assert profile.city == "Melbourne"
        assert profile.state == "Victoria"
        assert "coffee" in profile.local_knowledge
        assert "Four seasons" in profile.local_knowledge["weather"]

    def test_all_australian_regions(self):
        """Test all Australian regions are valid."""
        for _key, profile in AUSTRALIAN_REGIONS.items():
            assert profile.country == "Australia"
            assert profile.timezone.startswith("Australia/")
            assert len(profile.greetings) > 0
            assert len(profile.farewells) > 0


class TestInternationalRegions:
    """Test international regional profiles."""

    def test_uk_london_profile(self):
        """Test UK London profile."""
        profile = INTERNATIONAL_REGIONS["uk_london"]

        assert profile.country == "United Kingdom"
        assert profile.city == "London"
        assert profile.timezone == "Europe/London"

        # British expressions
        assert profile.expressions["great"] == "brilliant"
        assert profile.expressions["thank you"] == "cheers"

    def test_us_california_profile(self):
        """Test US California profile."""
        profile = INTERNATIONAL_REGIONS["us_california"]

        assert profile.country == "United States"
        assert profile.state == "California"
        assert profile.expressions["great"] == "awesome"

    def test_ireland_profile(self):
        """Test Ireland profile."""
        profile = INTERNATIONAL_REGIONS["ireland"]

        assert profile.country == "Ireland"
        assert profile.expressions["great"] == "grand"
        assert "craic" in str(profile.greetings)


class TestHelperFunctions:
    """Test helper functions."""

    def test_get_available_regions(self):
        """Test getting all regions."""
        regions = get_available_regions()

        assert "adelaide" in regions
        assert "melbourne" in regions
        assert "uk_london" in regions

        # Should include both Australian and international
        assert len(regions) >= 7  # adelaide, melbourne, sydney, etc.

    def test_list_regions(self):
        """Test listing region keys."""
        keys = list_regions()

        assert "adelaide" in keys
        assert isinstance(keys, list)

    def test_detect_location(self):
        """Test location detection."""
        # Should return something valid
        location = detect_location()
        assert location in list_regions()

    def test_get_regional_voice_singleton(self):
        """Test global singleton instance."""
        rv1 = get_regional_voice()
        rv2 = get_regional_voice()

        # Should be same instance
        assert rv1 is rv2


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_joseph_in_adelaide(self, tmp_path):
        """Test Joseph's actual usage in Adelaide."""
        rv = RegionalVoice(config_dir=str(tmp_path))

        # Joseph says something
        text = "That's very great! Thank you! Let's go to the bottle shop."
        regionalized = rv.regionalize(text)

        # Should sound like Adelaide
        assert "heaps" in regionalized.lower()
        assert "cheers" in regionalized.lower()
        assert "bottle-o" in regionalized.lower()

        # Get greeting - should be one from the Adelaide profile
        greeting = rv.get_greeting()
        assert greeting in AUSTRALIAN_REGIONS["adelaide"].greetings

    def test_traveling_to_melbourne(self, tmp_path):
        """Test switching regions when traveling."""
        rv = RegionalVoice(config_dir=str(tmp_path))

        # Start in Adelaide
        assert rv.profile.city == "Adelaide"
        rv.get_greeting()

        # Travel to Melbourne
        rv.save_location("melbourne")
        rv._load_location()

        assert rv.profile.city == "Melbourne"

        # Different expressions
        text = "That's very great!"
        result = rv.regionalize(text)
        # Melbourne uses "bloody" for very
        assert "bloody" in result.lower() or "top notch" in result.lower()

    def test_explaining_adelaide_to_visitors(self, tmp_path):
        """Test using local knowledge for visitors."""
        rv = RegionalVoice(config_dir=str(tmp_path))

        # What to see in Adelaide?
        beaches = rv.get_local_knowledge("beach")
        assert "Glenelg" in beaches

        wine = rv.get_local_knowledge("wine_region")
        assert "Barossa" in wine

        events = rv.get_local_knowledge("events")
        assert "Fringe" in events

    def test_learning_new_expressions(self, tmp_path):
        """Test learning new regional slang."""
        rv = RegionalVoice(config_dir=str(tmp_path))

        # Learn new slang
        rv.add_expression("friend", "mate")
        rv.add_expression("going", "goin'")

        # Should use it
        text = "How is your friend going?"
        result = rv.regionalize(text)
        assert "mate" in result
        assert "goin'" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
