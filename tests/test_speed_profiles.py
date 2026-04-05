# SPDX-License-Identifier: Apache-2.0
#
# Tests for Adaptive Speech Rate Profiles, Content Classifier,
# User Preferences, and Content-Aware Speed Resolution.
#
# Users should be able to gradually increase listening speed as he
# gains proficiency.  These tests verify the profile manager, voice
# command matching, tier navigation, persistence, adaptive tracker,
# content classification, user preferences, and speed resolution.

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.content_classifier import (
    CONTENT_TYPE_TO_TIER,
    ClassificationContext,
    ClassificationResult,
    ContentClassifier,
    ContentType,
    get_content_classifier,
)
from agentic_brain.voice.speed_profiles import (
    CONTENT_SPEED_TIERS,
    PROFILE_RATES,
    TIER_DESCRIPTIONS,
    AdaptiveSpeedTracker,
    ContentSpeedResult,
    SpeedProfile,
    SpeedProfileManager,
    UserPreferenceManager,
    UserSpeedPreferences,
    get_adaptive_tracker,
    get_current_rate,
    get_preference_manager,
    get_speed_for_content,
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
        "agentic_brain.voice.speed_profiles._STATE_FILE",
        fake,
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
            "agentic_brain.voice.speed_profiles._manager",
            None,
        )
        m1 = get_speed_manager()
        m2 = get_speed_manager()
        assert m1 is m2

    def test_get_current_rate(self, state_file, monkeypatch):
        monkeypatch.setattr(
            "agentic_brain.voice.speed_profiles._manager",
            None,
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


# ---------------------------------------------------------------------------
# Content Speed Tiers
# ---------------------------------------------------------------------------


class TestContentSpeedTiers:
    def test_all_tiers_exist(self):
        for tier in ("slow", "normal", "fast", "rapid"):
            assert tier in CONTENT_SPEED_TIERS

    def test_tiers_are_ascending(self):
        tiers = ["slow", "normal", "fast", "rapid"]
        midpoints = [
            (CONTENT_SPEED_TIERS[t][0] + CONTENT_SPEED_TIERS[t][1]) // 2 for t in tiers
        ]
        assert midpoints == sorted(midpoints), "Tier midpoints must ascend"

    def test_slow_tier_range(self):
        low, high = CONTENT_SPEED_TIERS["slow"]
        assert low == 130
        assert high == 150

    def test_rapid_tier_range(self):
        low, high = CONTENT_SPEED_TIERS["rapid"]
        assert low == 300
        assert high == 400

    def test_tier_descriptions_exist(self):
        for tier in CONTENT_SPEED_TIERS:
            assert tier in TIER_DESCRIPTIONS


# ---------------------------------------------------------------------------
# Content Classifier
# ---------------------------------------------------------------------------


class TestContentClassifier:

    @pytest.fixture
    def classifier(self):
        c = ContentClassifier()
        yield c
        c.clear_cache()

    def test_error_classification(self, classifier):
        result = classifier.classify("Error: connection refused, timeout after 30s")
        assert result.content_type == ContentType.ERROR
        assert result.tier == "slow"

    def test_warning_classification(self, classifier):
        result = classifier.classify("Warning: deprecated API used, will be removed")
        assert result.content_type == ContentType.WARNING
        assert result.tier == "slow"

    def test_status_classification(self, classifier):
        result = classifier.classify("All systems go, everything is fine")
        assert result.content_type == ContentType.STATUS
        assert result.tier == "rapid"

    def test_progress_classification(self, classifier):
        result = classifier.classify("Processing 5 of 10 items")
        assert result.content_type == ContentType.PROGRESS
        assert result.tier == "rapid"

    def test_progress_percentage(self, classifier):
        result = classifier.classify("Upload 75% complete")
        assert result.content_type == ContentType.PROGRESS
        assert result.tier == "rapid"

    def test_list_classification(self, classifier):
        text = "- First item\n- Second item\n- Third item\n- Fourth item"
        result = classifier.classify(text)
        assert result.content_type == ContentType.LIST
        assert result.tier == "fast"

    def test_question_classification(self, classifier):
        result = classifier.classify("Should we proceed with the deployment?")
        assert result.content_type == ContentType.QUESTION
        assert result.tier == "normal"

    def test_complex_code_classification(self, classifier):
        result = classifier.classify(
            "def calculate_hash(data): return hashlib.sha256(data)"
        )
        assert result.content_type == ContentType.COMPLEX
        assert result.tier == "slow"

    def test_default_to_update(self, classifier):
        result = classifier.classify("The meeting is at three pm today")
        assert result.content_type == ContentType.UPDATE
        assert result.tier == "normal"

    def test_context_repeated(self, classifier):
        ctx = ClassificationContext(is_repeated=True)
        result = classifier.classify("Some random text here", ctx)
        assert result.content_type == ContentType.FAMILIAR
        assert result.tier == "fast"

    def test_context_critical(self, classifier):
        ctx = ClassificationContext(urgency="critical")
        result = classifier.classify("Something happened", ctx)
        assert result.content_type == ContentType.ERROR
        assert result.tier == "slow"

    def test_context_first_time(self, classifier):
        ctx = ClassificationContext(is_first_time=True)
        result = classifier.classify("Introducing the new dashboard feature", ctx)
        assert result.content_type == ContentType.NEW_INFO

    def test_cache_returns_same_result(self, classifier):
        text = "Critical error: database connection lost"
        r1 = classifier.classify(text)
        r2 = classifier.classify(text)
        assert r1.content_type == r2.content_type
        assert r1.tier == r2.tier

    def test_familiar_on_third_call(self, classifier):
        text = "Build succeeded, all tests passed"
        # First call → classify (status)
        r1 = classifier.classify(text)
        # Second call → cached, marks as seen
        r2 = classifier.classify(text)
        # Third call → promoted to familiar
        r3 = classifier.classify(text)
        assert r3.content_type == ContentType.FAMILIAR
        assert r3.tier == "fast"

    def test_mark_familiar(self, classifier):
        text = "Custom phrase to remember"
        classifier.mark_familiar(text)
        # After marking, next classify from cache + familiar set won't find it
        # because we need it in the cache too.  So classify once first:
        classifier.classify(text)
        # Now it's in cache AND marked familiar → next hit returns familiar
        result = classifier.classify(text)
        assert result.content_type == ContentType.FAMILIAR

    def test_clear_cache(self, classifier):
        classifier.classify("test text")
        assert classifier.cache_size > 0
        classifier.clear_cache()
        assert classifier.cache_size == 0

    def test_classification_result_confidence(self, classifier):
        result = classifier.classify("Error: fatal crash, exception thrown, failed")
        assert result.is_high_confidence

    def test_all_content_types_have_tier_mapping(self):
        for ct in ContentType:
            assert ct in CONTENT_TYPE_TO_TIER

    def test_singleton_classifier(self):
        c1 = get_content_classifier()
        c2 = get_content_classifier()
        assert c1 is c2


# ---------------------------------------------------------------------------
# User Speed Preferences
# ---------------------------------------------------------------------------


class TestUserSpeedPreferences:
    def test_defaults(self):
        prefs = UserSpeedPreferences()
        assert prefs.default_speed == 155
        assert prefs.max_speed == 400
        assert prefs.auto_classify is False

    def test_clamp_within_range(self):
        prefs = UserSpeedPreferences(default_speed=150, max_speed=300)
        assert prefs.clamp(200) == 200

    def test_clamp_above_max(self):
        prefs = UserSpeedPreferences(default_speed=150, max_speed=300)
        assert prefs.clamp(500) == 300

    def test_clamp_below_default(self):
        prefs = UserSpeedPreferences(default_speed=150, max_speed=300)
        assert prefs.clamp(100) == 150

    def test_round_trip_dict(self):
        prefs = UserSpeedPreferences(
            default_speed=180,
            max_speed=350,
            auto_classify=True,
            feedback_history=[
                {"direction": "faster", "wpm_at_feedback": 155, "timestamp": 1.0}
            ],
        )
        d = prefs.to_dict()
        restored = UserSpeedPreferences.from_dict(d)
        assert restored.default_speed == 180
        assert restored.max_speed == 350
        assert restored.auto_classify is True
        assert len(restored.feedback_history) == 1


# ---------------------------------------------------------------------------
# User Preference Manager
# ---------------------------------------------------------------------------


class TestUserPreferenceManager:
    @pytest.fixture
    def pref_mgr(self, state_file):
        return UserPreferenceManager()

    def test_default_preferences(self, pref_mgr):
        prefs = pref_mgr.preferences
        assert prefs.default_speed == 155
        assert prefs.max_speed == 400

    def test_set_max_speed(self, pref_mgr):
        pref_mgr.set_max_speed(300)
        assert pref_mgr.preferences.max_speed == 300

    def test_set_max_speed_clamped(self, pref_mgr):
        pref_mgr.set_max_speed(9999)
        assert pref_mgr.preferences.max_speed == 900

    def test_set_auto_classify(self, pref_mgr):
        pref_mgr.set_auto_classify(True)
        assert pref_mgr.preferences.auto_classify is True

    def test_record_feedback(self, pref_mgr):
        pref_mgr.record_feedback("faster", 155)
        pref_mgr.record_feedback("faster", 200)
        assert len(pref_mgr.preferences.feedback_history) == 2

    def test_feedback_direction_faster(self, pref_mgr):
        for _ in range(6):
            pref_mgr.record_feedback("faster", 155)
        assert pref_mgr.get_preferred_direction() == "faster"

    def test_feedback_direction_slower(self, pref_mgr):
        for _ in range(6):
            pref_mgr.record_feedback("slower", 300)
        assert pref_mgr.get_preferred_direction() == "slower"

    def test_feedback_no_trend(self, pref_mgr):
        pref_mgr.record_feedback("faster", 155)
        pref_mgr.record_feedback("slower", 200)
        assert pref_mgr.get_preferred_direction() is None

    def test_preferences_persist(self, state_file):
        m1 = UserPreferenceManager()
        m1.set_max_speed(250)
        m1.set_auto_classify(True)

        m2 = UserPreferenceManager()
        assert m2.preferences.max_speed == 250
        assert m2.preferences.auto_classify is True


# ---------------------------------------------------------------------------
# Content-Aware Speed Resolution
# ---------------------------------------------------------------------------


class TestGetSpeedForContent:
    @pytest.fixture(autouse=True)
    def _reset_classifier(self):
        """Ensure a fresh classifier for each test."""
        import agentic_brain.voice.content_classifier as cc

        cc._classifier = None
        yield
        cc._classifier = None

    def test_error_returns_slow(self, state_file):
        result = get_speed_for_content("Fatal error: database crashed")
        assert result.tier == "slow"
        assert 130 <= result.wpm <= 150

    def test_status_returns_rapid(self, state_file):
        result = get_speed_for_content("All systems go, no issues found")
        assert result.tier == "rapid"
        assert 300 <= result.wpm <= 400

    def test_progress_returns_rapid(self, state_file):
        result = get_speed_for_content("Step 3 of 10 complete")
        assert result.tier == "rapid"

    def test_normal_text_returns_normal(self, state_file):
        result = get_speed_for_content("The weather is nice today")
        assert result.tier == "normal"
        assert 155 <= result.wpm <= 180

    def test_max_speed_clamping(self, state_file):
        prefs = UserSpeedPreferences(max_speed=200)
        result = get_speed_for_content(
            "All good, healthy, running, no issues",
            preferences=prefs,
        )
        # Rapid would normally be 300-400, but clamped to 200
        assert result.wpm <= 200
        assert result.clamped is True

    def test_auto_classified_flag(self, state_file):
        result = get_speed_for_content("Error: something broke")
        assert result.auto_classified is True

    def test_context_dict(self, state_file):
        result = get_speed_for_content(
            "Hello world",
            context={"urgency": "critical"},
        )
        assert result.tier == "slow"

    def test_returns_content_speed_result(self, state_file):
        result = get_speed_for_content("Testing the output type")
        assert isinstance(result, ContentSpeedResult)
