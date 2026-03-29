# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Adaptive Speech Rate Profiles - Grow with Joseph's proficiency.

Blind power users process 350-900 WPM.  As Joseph gains proficiency
the brain should let him listen faster.

4 Speed Profiles (base tier)
============================
- **relaxed** : 155 WPM  (current default, gentle pace)
- **working** : 200 WPM  (light productivity)
- **focused** : 280 WPM  (deep work)
- **power**   : 400 WPM  (expert mode)

Content-Aware Speed Tiers
=========================
Overlaid on top of the base profile, content analysis can shift the
effective rate up or down:

- **slow**   : 130–150 WPM  (errors, warnings, new/complex content)
- **normal** : 155–180 WPM  (regular conversation, updates)
- **fast**   : 200–250 WPM  (familiar content, confirmations, lists)
- **rapid**  : 300–400 WPM  (status updates, progress, repeated phrases)

Voice Commands
==============
- "speed up" / "faster"   → move up one tier
- "slow down" / "slower"  → move down one tier
- "relaxed mode" / "working mode" / "focused mode" / "power mode"
  → jump directly to that tier

Auto-Adaptation
===============
``AdaptiveSpeedTracker`` records interrupts (too slow) and replay
requests (too fast) and nudges the profile over time.

Content-Aware Auto-Classification
=================================
``get_speed_for_content()`` uses the ``ContentClassifier`` to pick
the right speed tier for a piece of text, respecting both the user's
base profile and their max-speed preference.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Speed profiles ────────────────────────────────────────────────────


class SpeedProfile(Enum):
    """Ordered tiers from slowest to fastest."""

    RELAXED = "relaxed"
    WORKING = "working"
    FOCUSED = "focused"
    POWER = "power"


PROFILE_RATES: Dict[SpeedProfile, int] = {
    SpeedProfile.RELAXED: 155,
    SpeedProfile.WORKING: 200,
    SpeedProfile.FOCUSED: 280,
    SpeedProfile.POWER: 400,
}

PROFILE_DESCRIPTIONS: Dict[SpeedProfile, str] = {
    SpeedProfile.RELAXED: "Relaxed - 155 WPM, gentle listening pace",
    SpeedProfile.WORKING: "Working - 200 WPM, light productivity",
    SpeedProfile.FOCUSED: "Focused - 280 WPM, deep work speed",
    SpeedProfile.POWER: "Power - 400 WPM, expert listener mode",
}

# Ordered list for tier navigation
_ORDERED_PROFILES: List[SpeedProfile] = list(SpeedProfile)

# ── Content-aware speed tiers ─────────────────────────────────────────

CONTENT_SPEED_TIERS: Dict[str, Tuple[int, int]] = {
    "slow": (130, 150),  # errors, warnings, new info, complex
    "normal": (155, 180),  # regular conversation, updates
    "fast": (200, 250),  # familiar, confirmations, lists
    "rapid": (300, 400),  # status, progress, repeated phrases
}

TIER_DESCRIPTIONS: Dict[str, str] = {
    "slow": "Slow (130-150 WPM) - errors, warnings, new information",
    "normal": "Normal (155-180 WPM) - conversation, updates",
    "fast": "Fast (200-250 WPM) - familiar content, lists",
    "rapid": "Rapid (300-400 WPM) - status updates, progress",
}

# ── Voice command triggers ────────────────────────────────────────────

SPEED_UP_TRIGGERS = frozenset(
    {
        "speed up",
        "faster",
        "go faster",
        "talk faster",
        "quicker",
        "hurry up",
    }
)

SLOW_DOWN_TRIGGERS = frozenset(
    {
        "slow down",
        "slower",
        "go slower",
        "talk slower",
        "ease up",
    }
)

PROFILE_TRIGGERS: Dict[str, SpeedProfile] = {
    "relaxed mode": SpeedProfile.RELAXED,
    "relaxed": SpeedProfile.RELAXED,
    "working mode": SpeedProfile.WORKING,
    "working": SpeedProfile.WORKING,
    "focused mode": SpeedProfile.FOCUSED,
    "focused": SpeedProfile.FOCUSED,
    "focus mode": SpeedProfile.FOCUSED,
    "power mode": SpeedProfile.POWER,
    "power": SpeedProfile.POWER,
    "turbo": SpeedProfile.POWER,
}


# ── Persistence ───────────────────────────────────────────────────────

_STATE_FILE = Path.home() / ".brain-speech-profile"


def _load_state() -> dict:
    """Read persisted profile state from disk."""
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("Could not load speed profile state: %s", exc)
    return {}


def _save_state(data: dict) -> None:
    """Persist profile state to disk."""
    try:
        _STATE_FILE.write_text(json.dumps(data, indent=2))
    except OSError as exc:
        logger.warning("Could not save speed profile state: %s", exc)


# ── SpeedProfileManager ──────────────────────────────────────────────


class SpeedProfileManager:
    """Manages the active speech rate profile.

    Persists the selected tier to ``~/.brain-speech-profile`` so the
    preference survives across sessions.
    """

    def __init__(self) -> None:
        state = _load_state()
        try:
            self._profile = SpeedProfile(state.get("profile", "relaxed"))
        except ValueError:
            self._profile = SpeedProfile.RELAXED

    # ── Properties ────────────────────────────────────────────────

    @property
    def current_profile(self) -> SpeedProfile:
        return self._profile

    @property
    def current_rate(self) -> int:
        """Speech rate (WPM) for the active profile."""
        return PROFILE_RATES[self._profile]

    @property
    def description(self) -> str:
        return PROFILE_DESCRIPTIONS[self._profile]

    # ── Tier navigation ───────────────────────────────────────────

    def speed_up(self) -> SpeedProfile:
        """Move up one tier.  Returns the new profile."""
        idx = _ORDERED_PROFILES.index(self._profile)
        if idx < len(_ORDERED_PROFILES) - 1:
            self._profile = _ORDERED_PROFILES[idx + 1]
            self._persist()
            logger.info(
                "Speed profile raised to %s (%d WPM)",
                self._profile.value,
                self.current_rate,
            )
        return self._profile

    def slow_down(self) -> SpeedProfile:
        """Move down one tier.  Returns the new profile."""
        idx = _ORDERED_PROFILES.index(self._profile)
        if idx > 0:
            self._profile = _ORDERED_PROFILES[idx - 1]
            self._persist()
            logger.info(
                "Speed profile lowered to %s (%d WPM)",
                self._profile.value,
                self.current_rate,
            )
        return self._profile

    def set_profile(self, profile: SpeedProfile) -> None:
        """Jump directly to *profile*."""
        self._profile = profile
        self._persist()
        logger.info(
            "Speed profile set to %s (%d WPM)", self._profile.value, self.current_rate
        )

    def can_speed_up(self) -> bool:
        return _ORDERED_PROFILES.index(self._profile) < len(_ORDERED_PROFILES) - 1

    def can_slow_down(self) -> bool:
        return _ORDERED_PROFILES.index(self._profile) > 0

    # ── Voice command matching ────────────────────────────────────

    def match_command(self, text: str) -> Optional[str]:
        """Try to match *text* against known voice commands.

        Returns a human-readable result string on match, or ``None``
        if no command was recognised.
        """
        normalised = text.strip().lower()

        # Direct profile triggers
        for trigger, profile in PROFILE_TRIGGERS.items():
            if normalised == trigger:
                self.set_profile(profile)
                return (
                    f"Switched to {profile.value} mode - "
                    f"{PROFILE_RATES[profile]} words per minute"
                )

        # Relative triggers
        if normalised in SPEED_UP_TRIGGERS:
            if not self.can_speed_up():
                return "Already at maximum speed - power mode, 400 words per minute"
            new = self.speed_up()
            return (
                f"Speed up! Now {new.value} mode - "
                f"{PROFILE_RATES[new]} words per minute"
            )

        if normalised in SLOW_DOWN_TRIGGERS:
            if not self.can_slow_down():
                return "Already at minimum speed - relaxed mode, 155 words per minute"
            new = self.slow_down()
            return (
                f"Slowing down. Now {new.value} mode - "
                f"{PROFILE_RATES[new]} words per minute"
            )

        return None

    # ── Internals ─────────────────────────────────────────────────

    def _persist(self) -> None:
        state = _load_state()
        state["profile"] = self._profile.value
        state["rate"] = self.current_rate
        state["updated"] = time.time()
        _save_state(state)


# ── Adaptive Speed Tracker ────────────────────────────────────────────


@dataclass
class _AdaptiveEvent:
    kind: str  # "interrupt" | "replay"
    timestamp: float = field(default_factory=time.time)


class AdaptiveSpeedTracker:
    """Auto-adjust speed based on Joseph's usage patterns.

    * **interrupt** → Joseph cut off speech (probably too slow)
    * **replay**    → Joseph asked to repeat (probably too fast)

    When enough signal accumulates the tracker suggests a tier change.
    Suggestions are soft - the manager decides whether to apply them.
    """

    WINDOW_SECONDS = 300  # 5-minute rolling window
    INTERRUPT_THRESHOLD = 5  # interrupts in window → suggest speed up
    REPLAY_THRESHOLD = 3  # replays in window    → suggest slow down

    def __init__(self, manager: SpeedProfileManager) -> None:
        self._manager = manager
        self._events: List[_AdaptiveEvent] = []
        self._last_suggestion_time: float = 0.0
        self._suggestion_cooldown = 120.0  # seconds between suggestions

    def record_interrupt(self) -> None:
        """Speech was interrupted - signal that pace may be too slow."""
        self._events.append(_AdaptiveEvent(kind="interrupt"))
        self._trim_window()
        logger.debug(
            "Adaptive: recorded interrupt (%d in window)", self._count("interrupt")
        )

    def record_replay(self) -> None:
        """User requested a replay - signal that pace may be too fast."""
        self._events.append(_AdaptiveEvent(kind="replay"))
        self._trim_window()
        logger.debug("Adaptive: recorded replay (%d in window)", self._count("replay"))

    def get_suggested_profile(self) -> Optional[SpeedProfile]:
        """Suggest optimal profile based on recent history.

        Returns ``None`` if no change is recommended.
        """
        self._trim_window()

        now = time.time()
        if now - self._last_suggestion_time < self._suggestion_cooldown:
            return None

        interrupts = self._count("interrupt")
        replays = self._count("replay")

        if interrupts >= self.INTERRUPT_THRESHOLD and self._manager.can_speed_up():
            self._last_suggestion_time = now
            idx = _ORDERED_PROFILES.index(self._manager.current_profile) + 1
            return _ORDERED_PROFILES[idx]

        if replays >= self.REPLAY_THRESHOLD and self._manager.can_slow_down():
            self._last_suggestion_time = now
            idx = _ORDERED_PROFILES.index(self._manager.current_profile) - 1
            return _ORDERED_PROFILES[idx]

        return None

    def apply_suggestion(self) -> Optional[str]:
        """Check for and apply an adaptive suggestion.

        Returns a description of what changed, or ``None``.
        """
        suggested = self.get_suggested_profile()
        if suggested is None:
            return None

        old = self._manager.current_profile
        self._manager.set_profile(suggested)
        self._events.clear()

        direction = (
            "faster"
            if suggested.value != old.value
            and _ORDERED_PROFILES.index(suggested) > _ORDERED_PROFILES.index(old)
            else "slower"
        )
        return (
            f"Auto-adjusted {direction}: {old.value} to {suggested.value} "
            f"({PROFILE_RATES[old]} to {PROFILE_RATES[suggested]} WPM)"
        )

    @property
    def stats(self) -> Dict[str, int]:
        """Current window statistics."""
        self._trim_window()
        return {
            "interrupts": self._count("interrupt"),
            "replays": self._count("replay"),
            "window_seconds": self.WINDOW_SECONDS,
        }

    # ── Internals ─────────────────────────────────────────────────

    def _trim_window(self) -> None:
        cutoff = time.time() - self.WINDOW_SECONDS
        self._events = [e for e in self._events if e.timestamp >= cutoff]

    def _count(self, kind: str) -> int:
        return sum(1 for e in self._events if e.kind == kind)


# ── Module-level singleton access ─────────────────────────────────────

_manager: Optional[SpeedProfileManager] = None
_tracker: Optional[AdaptiveSpeedTracker] = None


def get_speed_manager() -> SpeedProfileManager:
    """Return (or create) the process-wide speed profile manager."""
    global _manager
    if _manager is None:
        _manager = SpeedProfileManager()
    return _manager


def get_adaptive_tracker() -> AdaptiveSpeedTracker:
    """Return (or create) the process-wide adaptive speed tracker."""
    global _tracker
    if _tracker is None:
        _tracker = AdaptiveSpeedTracker(get_speed_manager())
    return _tracker


def get_current_rate() -> int:
    """Convenience: current speech rate in WPM from the active profile."""
    return get_speed_manager().current_rate


# ── User Preferences ─────────────────────────────────────────────────


@dataclass
class UserSpeedPreferences:
    """Persisted user preferences for speech speed.

    Stored alongside the profile state in ``~/.brain-speech-profile``.
    """

    default_speed: int = 155  # Base WPM
    max_speed: int = 400  # Hard ceiling
    auto_classify: bool = False  # Content-aware speed
    feedback_history: List[dict] = field(default_factory=list)

    def clamp(self, wpm: int) -> int:
        """Ensure *wpm* is within [default_speed, max_speed]."""
        return max(self.default_speed, min(wpm, self.max_speed))

    def to_dict(self) -> dict:
        return {
            "default_speed": self.default_speed,
            "max_speed": self.max_speed,
            "auto_classify": self.auto_classify,
            "feedback_history": self.feedback_history[-50:],  # keep last 50
        }

    @classmethod
    def from_dict(cls, data: dict) -> UserSpeedPreferences:
        return cls(
            default_speed=data.get("default_speed", 155),
            max_speed=data.get("max_speed", 400),
            auto_classify=data.get("auto_classify", False),
            feedback_history=data.get("feedback_history", []),
        )


class UserPreferenceManager:
    """Load/save user speed preferences alongside profile state."""

    def __init__(self) -> None:
        state = _load_state()
        prefs_data = state.get("user_preferences", {})
        self._prefs = UserSpeedPreferences.from_dict(prefs_data)

    @property
    def preferences(self) -> UserSpeedPreferences:
        return self._prefs

    def set_default_speed(self, wpm: int) -> None:
        """Set the user's preferred default speed."""
        self._prefs.default_speed = max(100, min(wpm, 900))
        self._persist()
        logger.info("Default speed set to %d WPM", self._prefs.default_speed)

    def set_max_speed(self, wpm: int) -> None:
        """Set the hard maximum speed ceiling."""
        self._prefs.max_speed = max(100, min(wpm, 900))
        self._persist()
        logger.info("Max speed set to %d WPM", self._prefs.max_speed)

    def set_auto_classify(self, enabled: bool) -> None:
        """Enable or disable content-aware speed classification."""
        self._prefs.auto_classify = enabled
        self._persist()
        logger.info("Auto-classify %s", "enabled" if enabled else "disabled")

    def record_feedback(self, direction: str, current_wpm: int) -> None:
        """Record user feedback ('slower' or 'faster') for learning.

        Over time this builds a profile of how Joseph responds to
        different speeds, helping the adaptive system tune itself.
        """
        entry = {
            "direction": direction,
            "wpm_at_feedback": current_wpm,
            "timestamp": time.time(),
        }
        self._prefs.feedback_history.append(entry)
        # Keep bounded
        if len(self._prefs.feedback_history) > 50:
            self._prefs.feedback_history = self._prefs.feedback_history[-50:]
        self._persist()
        logger.info("Feedback recorded: %s at %d WPM", direction, current_wpm)

    def get_preferred_direction(self) -> Optional[str]:
        """Analyse recent feedback to detect a trend.

        Returns ``'faster'``, ``'slower'``, or ``None`` if no clear trend.
        """
        recent = self._prefs.feedback_history[-10:]
        if len(recent) < 3:
            return None
        faster = sum(1 for f in recent if f["direction"] == "faster")
        slower = sum(1 for f in recent if f["direction"] == "slower")
        if faster >= 2 * max(slower, 1):
            return "faster"
        if slower >= 2 * max(faster, 1):
            return "slower"
        return None

    def _persist(self) -> None:
        state = _load_state()
        state["user_preferences"] = self._prefs.to_dict()
        _save_state(state)


# ── Content-aware speed resolver ──────────────────────────────────────


@dataclass
class ContentSpeedResult:
    """The resolved speech rate for a piece of content."""

    wpm: int
    tier: str
    content_type: str
    auto_classified: bool = False
    clamped: bool = False


def get_speed_for_content(
    text: str,
    context: Optional[dict] = None,
    *,
    preferences: Optional[UserSpeedPreferences] = None,
) -> ContentSpeedResult:
    """Determine the optimal speech rate for *text*.

    Uses the ``ContentClassifier`` to categorise the text, then maps
    the resulting tier to a concrete WPM value.  The result is clamped
    to the user's ``max_speed`` preference.

    Args:
        text: The content to be spoken.
        context: Optional dict with keys matching
                 ``ClassificationContext`` fields.
        preferences: Override preferences (uses stored prefs if None).

    Returns:
        A ``ContentSpeedResult`` with the chosen WPM and metadata.
    """
    from agentic_brain.voice.content_classifier import (
        ClassificationContext,
        get_content_classifier,
    )

    prefs = preferences or get_preference_manager().preferences
    classifier = get_content_classifier()

    # Build context
    ctx = ClassificationContext()
    if context:
        ctx.source = context.get("source", "")
        ctx.is_repeated = context.get("is_repeated", False)
        ctx.is_first_time = context.get("is_first_time", False)
        ctx.urgency = context.get("urgency", "normal")

    result = classifier.classify(text, ctx)
    tier = result.tier

    # Map tier to WPM
    low, high = CONTENT_SPEED_TIERS.get(tier, (155, 180))
    wpm = (low + high) // 2

    # Clamp to user preference
    clamped = False
    if wpm > prefs.max_speed:
        wpm = prefs.max_speed
        clamped = True
    if wpm < 100:
        wpm = 100

    return ContentSpeedResult(
        wpm=wpm,
        tier=tier,
        content_type=result.content_type.value,
        auto_classified=True,
        clamped=clamped,
    )


# ── Module-level singleton for preferences ────────────────────────────

_pref_manager: Optional[UserPreferenceManager] = None


def get_preference_manager() -> UserPreferenceManager:
    """Return (or create) the process-wide user preference manager."""
    global _pref_manager
    if _pref_manager is None:
        _pref_manager = UserPreferenceManager()
    return _pref_manager
