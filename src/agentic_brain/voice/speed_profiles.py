# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Adaptive Speech Rate Profiles - Grow with Joseph's proficiency.

Blind power users process 350-900 WPM.  As Joseph gains proficiency
the brain should let him listen faster.

4 Speed Profiles
================
- **relaxed** : 155 WPM  (current default, gentle pace)
- **working** : 200 WPM  (light productivity)
- **focused** : 280 WPM  (deep work)
- **power**   : 400 WPM  (expert mode)

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
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

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

# ── Voice command triggers ────────────────────────────────────────────

SPEED_UP_TRIGGERS = frozenset({
    "speed up", "faster", "go faster", "talk faster",
    "quicker", "hurry up",
})

SLOW_DOWN_TRIGGERS = frozenset({
    "slow down", "slower", "go slower", "talk slower",
    "ease up",
})

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
            logger.info("Speed profile raised to %s (%d WPM)",
                        self._profile.value, self.current_rate)
        return self._profile

    def slow_down(self) -> SpeedProfile:
        """Move down one tier.  Returns the new profile."""
        idx = _ORDERED_PROFILES.index(self._profile)
        if idx > 0:
            self._profile = _ORDERED_PROFILES[idx - 1]
            self._persist()
            logger.info("Speed profile lowered to %s (%d WPM)",
                        self._profile.value, self.current_rate)
        return self._profile

    def set_profile(self, profile: SpeedProfile) -> None:
        """Jump directly to *profile*."""
        self._profile = profile
        self._persist()
        logger.info("Speed profile set to %s (%d WPM)",
                    self._profile.value, self.current_rate)

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
                return (f"Switched to {profile.value} mode - "
                        f"{PROFILE_RATES[profile]} words per minute")

        # Relative triggers
        if normalised in SPEED_UP_TRIGGERS:
            if not self.can_speed_up():
                return "Already at maximum speed - power mode, 400 words per minute"
            new = self.speed_up()
            return (f"Speed up! Now {new.value} mode - "
                    f"{PROFILE_RATES[new]} words per minute")

        if normalised in SLOW_DOWN_TRIGGERS:
            if not self.can_slow_down():
                return "Already at minimum speed - relaxed mode, 155 words per minute"
            new = self.slow_down()
            return (f"Slowing down. Now {new.value} mode - "
                    f"{PROFILE_RATES[new]} words per minute")

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
    kind: str          # "interrupt" | "replay"
    timestamp: float = field(default_factory=time.time)


class AdaptiveSpeedTracker:
    """Auto-adjust speed based on Joseph's usage patterns.

    * **interrupt** → Joseph cut off speech (probably too slow)
    * **replay**    → Joseph asked to repeat (probably too fast)

    When enough signal accumulates the tracker suggests a tier change.
    Suggestions are soft - the manager decides whether to apply them.
    """

    WINDOW_SECONDS = 300       # 5-minute rolling window
    INTERRUPT_THRESHOLD = 5    # interrupts in window → suggest speed up
    REPLAY_THRESHOLD = 3       # replays in window    → suggest slow down

    def __init__(self, manager: SpeedProfileManager) -> None:
        self._manager = manager
        self._events: List[_AdaptiveEvent] = []
        self._last_suggestion_time: float = 0.0
        self._suggestion_cooldown = 120.0  # seconds between suggestions

    def record_interrupt(self) -> None:
        """Speech was interrupted - signal that pace may be too slow."""
        self._events.append(_AdaptiveEvent(kind="interrupt"))
        self._trim_window()
        logger.debug("Adaptive: recorded interrupt (%d in window)",
                      self._count("interrupt"))

    def record_replay(self) -> None:
        """User requested a replay - signal that pace may be too fast."""
        self._events.append(_AdaptiveEvent(kind="replay"))
        self._trim_window()
        logger.debug("Adaptive: recorded replay (%d in window)",
                      self._count("replay"))

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

        direction = "faster" if suggested.value != old.value and \
            _ORDERED_PROFILES.index(suggested) > _ORDERED_PROFILES.index(old) \
            else "slower"
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
