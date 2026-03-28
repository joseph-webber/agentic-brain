# SPDX-License-Identifier: Apache-2.0
#
# Tests for Adaptive Speech Rate Profiles.
#
# Joseph should be able to gradually increase listening speed as he
# gains proficiency.  These tests verify the profile manager, voice
# command matching, tier navigation, persistence, and adaptive tracker.

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.speed_profiles import (
    PROFILE_RATES,
    AdaptiveSpeedTracker,
    SpeedProfile,
    SpeedProfileManager,
    get_adaptive_tracker,
    get_current_rate,
    get_speed_manager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state_file(tmp_path, monkeypatch):
    """Redirect the persistent state file to a temp location."""
    fake = tmp_path / ".brain-speech-profile"
    monkeypatch.setattr(
        "agentic_brain.voice.speed_profiles._STATE_FILE", fake,
    )
    return fake


@pytest.fixture
def manager(state_file):
    """Fresh SpeedProfileManager with temp persistence."""
    return SpeedProfileManager()


@pytest.fixture
def tracker(manager):
    return AdaptiveSpeedTracker(manager)


# ---------------------------------------------------------------------------
# SpeedProfile enum
# ---------------------------------------------------------------------------

class TestSpeedProfile:
    def test_all_profiles_have_rates(self):
        for p in SpeedProfile:
            assert p in PROFILE_RATES, f"Missing rate for {p}"

    def test_rates_are_ascending(self):
        rates = [PROFILE_RATES[p] for p in SpeedProfile]
        assert rates == sorted(rates), "Rates must increase across tiers"

    def test_relaxed_is_155(self):
        assert PROFILE_RATES[SpeedProfile.RELAXED] == 155

    def test_power_is_400(self):
        assert PROFILE_RATES[SpeedProfile.POWER] == 400


# ---------------------------------------------------------------------------
# SpeedProfileManager
# ---------------------------------------------------------------------------

class TestSpeedProfileManager:
    def test_defaults_to_relaxed(self, manager):
        assert manager.current_profile == SpeedProfile.RELAXED
        assert manager.current_rate == 155

    def test_speed_up(self, manager):
        manager.speed_up()
        assert manager.current_profile == SpeedProfile.WORKING
        assert manager.current_rate == 200

    def test_speed_up_twice(self, manager):
        manager.speed_up()
        manager.speed_up()
        assert manager.current_profile == SpeedProfile.FOCUSED
        assert manager.current_rate == 280

    def test_speed_up_to_max(self, manager):
        for _ in range(10):
            manager.speed_up()
        assert manager.current_profile == SpeedProfile.POWER
        assert manager.current_rate == 400

    def test_slow_down(self, manager):
        manager.set_profile(SpeedProfile.FOCUSED)
        manager.slow_down()
        assert manager.current_profile == SpeedProfile.WORKING

    def test_slow_down_at_min(self, manager):
        assert manager.current_profile == SpeedProfile.RELAXED
        manager.slow_down()
        assert manager.current_profile == SpeedProfile.RELAXED

    def test_set_profile(self, manager):
        manager.set_profile(SpeedProfile.POWER)
        assert manager.current_profile == SpeedProfile.POWER
        assert manager.current_rate == 400

    def test_can_speed_up(self, manager):
        assert manager.can_speed_up() is True
        manager.set_profile(SpeedProfile.POWER)
        assert manager.can_speed_up() is False

    def test_can_slow_down(self, manager):
        assert manager.can_slow_down() is False
        manager.set_profile(SpeedProfile.WORKING)
        assert manager.can_slow_down() is True

    def test_description(self, manager):
        desc = manager.description
        assert "155" in desc
        assert "Relaxed" in desc


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_saves_and_loads(self, state_file):
        m1 = SpeedProfileManager()
        m1.set_profile(SpeedProfile.FOCUSED)
        assert state_file.exists()

        m2 = SpeedProfileManager()
        assert m2.current_profile == SpeedProfile.FOCUSED

    def test_corrupt_state_falls_back_to_relaxed(self, state_file):
        state_file.write_text("not json at all {{{")
        m = SpeedProfileManager()
        assert m.current_profile == SpeedProfile.RELAXED

    def test_unknown_profile_falls_back_to_relaxed(self, state_file):
        state_file.write_text(json.dumps({"profile": "ludicrous"}))
        m = SpeedProfileManager()
        assert m.current_profile == SpeedProfile.RELAXED


# ---------------------------------------------------------------------------
# Voice command matching
# ---------------------------------------------------------------------------

class TestVoiceCommands:
    def test_speed_up_command(self, manager):
        result = manager.match_command("speed up")
        assert result is not None
        assert "working" in result.lower()
        assert manager.current_profile == SpeedProfile.WORKING

    def test_slower_command(self, manager):
        manager.set_profile(SpeedProfile.FOCUSED)
        result = manager.match_command("slower")
        assert result is not None
        assert "working" in result.lower()

    def test_direct_profile_command(self, manager):
        result = manager.match_command("power mode")
        assert result is not None
        assert "400" in result
        assert manager.current_profile == SpeedProfile.POWER

    def test_relaxed_mode_command(self, manager):
        manager.set_profile(SpeedProfile.POWER)
        result = manager.match_command("relaxed mode")
        assert result is not None
        assert manager.current_profile == SpeedProfile.RELAXED

    def test_unrecognised_returns_none(self, manager):
        result = manager.match_command("do a backflip")
        assert result is None
        assert manager.current_profile == SpeedProfile.RELAXED

    def test_at_max_speed(self, manager):
        manager.set_profile(SpeedProfile.POWER)
        result = manager.match_command("faster")
        assert result is not None
        assert "maximum" in result.lower()

    def test_at_min_speed(self, manager):
        result = manager.match_command("slow down")
        assert result is not None
        assert "minimum" in result.lower()

    def test_case_insensitive(self, manager):
        result = manager.match_command("SPEED UP")
        assert result is not None
        assert manager.current_profile == SpeedProfile.WORKING

    def test_whitespace_tolerance(self, manager):
        result = manager.match_command("  focused mode  ")
        assert result is not None
        assert manager.current_profile == SpeedProfile.FOCUSED

    def test_turbo_alias(self, manager):
        result = manager.match_command("turbo")
        assert result is not None
        assert manager.current_profile == SpeedProfile.POWER


# ---------------------------------------------------------------------------
# AdaptiveSpeedTracker
# ---------------------------------------------------------------------------

class TestAdaptiveTracker:
    def test_starts_with_no_suggestion(self, tracker):
        assert tracker.get_suggested_profile() is None

    def test_interrupts_suggest_speed_up(self, tracker, manager):
        assert manager.current_profile == SpeedProfile.RELAXED
        for _ in range(5):
            tracker.record_interrupt()
        suggested = tracker.get_suggested_profile()
        assert suggested == SpeedProfile.WORKING

    def test_replays_suggest_slow_down(self, tracker, manager):
        manager.set_profile(SpeedProfile.FOCUSED)
        for _ in range(3):
            tracker.record_replay()
        suggested = tracker.get_suggested_profile()
        assert suggested == SpeedProfile.WORKING

    def test_cooldown_prevents_rapid_suggestions(self, tracker, manager):
        for _ in range(5):
            tracker.record_interrupt()
        first = tracker.get_suggested_profile()
        assert first is not None

        # Second suggestion within cooldown should be suppressed
        for _ in range(5):
            tracker.record_interrupt()
        second = tracker.get_suggested_profile()
        assert second is None

    def test_window_expiry(self, tracker, manager):
        tracker.record_interrupt()
        # Manually expire the event
        tracker._events[0].timestamp = time.time() - 600
        tracker._trim_window()
        assert tracker.stats["interrupts"] == 0

    def test_apply_suggestion_changes_profile(self, tracker, manager):
        for _ in range(5):
            tracker.record_interrupt()
        result = tracker.apply_suggestion()
        assert result is not None
        assert "faster" in result.lower()
        assert manager.current_profile == SpeedProfile.WORKING

    def test_apply_suggestion_clears_events(self, tracker, manager):
        for _ in range(5):
            tracker.record_interrupt()
        tracker.apply_suggestion()
        assert tracker.stats["interrupts"] == 0
        assert tracker.stats["replays"] == 0

    def test_no_suggestion_when_at_max(self, tracker, manager):
        manager.set_profile(SpeedProfile.POWER)
        for _ in range(10):
            tracker.record_interrupt()
        assert tracker.get_suggested_profile() is None

    def test_no_suggestion_when_at_min(self, tracker, manager):
        for _ in range(10):
            tracker.record_replay()
        assert tracker.get_suggested_profile() is None

    def test_stats(self, tracker):
        tracker.record_interrupt()
        tracker.record_interrupt()
        tracker.record_replay()
        s = tracker.stats
        assert s["interrupts"] == 2
        assert s["replays"] == 1
        assert s["window_seconds"] == 300


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

class TestSingletons:
    def test_get_speed_manager_returns_same_instance(self, state_file, monkeypatch):
        monkeypatch.setattr(
            "agentic_brain.voice.speed_profiles._manager", None,
        )
        m1 = get_speed_manager()
        m2 = get_speed_manager()
        assert m1 is m2

    def test_get_current_rate(self, state_file, monkeypatch):
        monkeypatch.setattr(
            "agentic_brain.voice.speed_profiles._manager", None,
        )
        rate = get_current_rate()
        assert rate == 155  # default relaxed


# ---------------------------------------------------------------------------
# Integration: all profiles round-trip through persistence
# ---------------------------------------------------------------------------

class TestAllProfilesPersist:
    @pytest.mark.parametrize("profile", list(SpeedProfile))
    def test_round_trip(self, state_file, profile):
        m1 = SpeedProfileManager()
        m1.set_profile(profile)

        m2 = SpeedProfileManager()
        assert m2.current_profile == profile
        assert m2.current_rate == PROFILE_RATES[profile]
