# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

# Copyright 2026 Joseph Webber
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
Mode Manager - Hot-swappable mode switching under 100ms.

The ModeManager is the central controller for switching between
the 42 operational modes of Agentic Brain. It handles:
- Hot-swap mode switching without restart
- Mode state persistence
- Event callbacks for mode changes
- Voice announcements
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agentic_brain.voice.serializer import speak_serialized

from .base import Mode, ModeCategory
from .registry import (
    CODE_TO_NAME,
    MODE_REGISTRY,
    MODES_BY_CATEGORY,
    get_mode,
    get_mode_count,
    list_modes,
)

logger = logging.getLogger(__name__)


@dataclass
class ModeTransition:
    """Record of a mode transition."""

    from_mode: Optional[str]
    to_mode: str
    timestamp: float
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class ModeManagerState:
    """Persistent state for the mode manager."""

    current_mode: str = "developer"
    history: List[Dict[str, Any]] = field(default_factory=list)
    total_switches: int = 0
    avg_switch_time_ms: float = 0.0


class ModeManager:
    """
    Central manager for Agentic Brain operational modes.

    Provides hot-swap mode switching under 100ms, with voice
    announcements and event callbacks.

    Example:
        manager = ModeManager()
        manager.switch("D")  # Switch to Developer mode
        manager.switch("turbo")  # Switch to Turbo mode
        print(manager.current())  # Get current mode
    """

    # Short code reference
    SHORT_CODES = {
        # USER modes
        "F": "free",
        "H": "home",
        "D": "developer",
        "B": "business",
        "E": "enterprise",
        "ST": "startup",
        "R": "research",
        "CR": "creator",
        # INDUSTRY modes
        "MED": "medical",
        "LAW": "legal",
        "BANK": "banking",
        "MIL": "military",
        "EDU": "education",
        "RET": "retail",
        "MFG": "manufacturing",
        "INS": "insurance",
        "RE": "realestate",
        "HOSP": "hospitality",
        "LOG": "logistics",
        "TEL": "telecom",
        "NRG": "energy",
        "MEDIA": "media",
        "GOV": "government",
        "PHARMA": "pharma",
        "AGRI": "agriculture",
        "CON": "construction",
        "AUTO": "automotive",
        "NPO": "nonprofit",
        # ARCHITECTURE modes
        "MONO": "monolith",
        "MICRO": "microservices",
        "CLU": "cluster",
        "SWM": "swarm",
        "AIR": "airlock",
        "EDGE": "edge",
        "HYB": "hybrid",
        "SRVL": "serverless",
        # COMPLIANCE modes
        "HIPAA": "hipaa",
        "GDPR": "gdpr",
        "SOX": "sox",
        "APRA": "apra",
        # POWER modes
        "L": "turbo",
        "P": "plaid",
    }

    def __init__(
        self,
        default_mode: str = "developer",
        state_file: Optional[Path] = None,
        voice_enabled: bool = True,
        on_mode_change: Optional[Callable[[Mode, Mode], None]] = None,
    ):
        """
        Initialize the Mode Manager.

        Args:
            default_mode: Initial mode to activate
            state_file: Path to persist state (optional)
            voice_enabled: Whether to announce mode changes
            on_mode_change: Callback for mode changes (old_mode, new_mode)
        """
        self._current_mode: Optional[Mode] = None
        self._state_file = state_file or Path.home() / ".brain-mode-state.json"
        self._voice_enabled = voice_enabled
        self._on_mode_change = on_mode_change
        self._transitions: List[ModeTransition] = []
        self._switch_times: List[float] = []

        # Load state or use default
        self._load_state()
        if self._current_mode is None:
            self.switch(default_mode, announce=False)

    def switch(
        self,
        name_or_code: str,
        announce: bool = True,
        save_state: bool = True,
    ) -> ModeTransition:
        """
        Switch to a new mode with hot-swap (target: <100ms).

        Args:
            name_or_code: Mode name or short code (e.g., "D", "developer", "turbo")
            announce: Whether to voice announce the change
            save_state: Whether to persist the state change

        Returns:
            ModeTransition record

        Raises:
            KeyError: If mode not found
        """
        start_time = time.perf_counter()
        old_mode = self._current_mode
        old_mode_name = old_mode.name if old_mode else None
        error = None

        try:
            # Resolve mode
            new_mode = get_mode(name_or_code)

            # Deactivate old mode
            if old_mode:
                old_mode.deactivate()

            # Activate new mode
            new_mode.activate(previous_mode=old_mode_name)
            self._current_mode = new_mode

            # Calculate switch time
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            self._switch_times.append(duration_ms)

            # Log the switch
            logger.info(
                f"Mode switched: {old_mode_name or 'None'} -> {new_mode.name} "
                f"in {duration_ms:.2f}ms"
            )

            # Voice announcement
            if (
                announce
                and self._voice_enabled
                and new_mode.config.voice.announce_mode_changes
            ):
                self._announce_mode_change(new_mode)

            # Callback
            if self._on_mode_change and old_mode:
                try:
                    self._on_mode_change(old_mode, new_mode)
                except Exception as e:
                    logger.warning(f"Mode change callback error: {e}")

            # Persist state
            if save_state:
                self._save_state()

            success = True

        except Exception as e:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            error = str(e)
            success = False
            logger.error(f"Mode switch failed: {e}")
            raise

        finally:
            # Record transition
            transition = ModeTransition(
                from_mode=old_mode_name,
                to_mode=name_or_code,
                timestamp=time.time(),
                duration_ms=duration_ms,
                success=success,
                error=error,
            )
            self._transitions.append(transition)

        return transition

    def current(self) -> Optional[Mode]:
        """Get the current active mode."""
        return self._current_mode

    def list(self, category: Optional[ModeCategory] = None) -> List[Mode]:
        """
        List all available modes.

        Args:
            category: Optional filter by category

        Returns:
            List of Mode objects
        """
        return list_modes(category)

    def list_by_category(self) -> Dict[str, List[Mode]]:
        """Get modes organized by category."""
        return {
            cat.value: [MODE_REGISTRY[name] for name in names]
            for cat, names in MODES_BY_CATEGORY.items()
        }

    def get(self, name_or_code: str) -> Mode:
        """Get a mode by name or code without switching."""
        return get_mode(name_or_code)

    def exists(self, name_or_code: str) -> bool:
        """Check if a mode exists."""
        try:
            get_mode(name_or_code)
            return True
        except KeyError:
            return False

    def stats(self) -> Dict[str, Any]:
        """Get mode manager statistics."""
        avg_switch_time = (
            sum(self._switch_times) / len(self._switch_times)
            if self._switch_times
            else 0.0
        )

        return {
            "current_mode": self._current_mode.name if self._current_mode else None,
            "total_modes": len(MODE_REGISTRY),
            "mode_counts": get_mode_count(),
            "total_switches": len(self._transitions),
            "avg_switch_time_ms": round(avg_switch_time, 2),
            "min_switch_time_ms": (
                round(min(self._switch_times), 2) if self._switch_times else 0
            ),
            "max_switch_time_ms": (
                round(max(self._switch_times), 2) if self._switch_times else 0
            ),
            "recent_transitions": [
                {
                    "from": t.from_mode,
                    "to": t.to_mode,
                    "duration_ms": round(t.duration_ms, 2),
                    "success": t.success,
                }
                for t in self._transitions[-5:]
            ],
        }

    def history(self, limit: int = 10) -> List[ModeTransition]:
        """Get recent mode transition history."""
        return self._transitions[-limit:]

    def search(self, query: str) -> List[Mode]:
        """
        Search modes by name, code, or description.

        Args:
            query: Search term

        Returns:
            Matching modes
        """
        query_lower = query.lower()
        results = []

        for mode in MODE_REGISTRY.values():
            if (
                query_lower in mode.name.lower()
                or query_lower in mode.code.lower()
                or query_lower in mode.description.lower()
            ):
                results.append(mode)

        return results

    def quick_codes(self) -> Dict[str, str]:
        """Get the short code reference table."""
        return self.SHORT_CODES.copy()

    def _announce_mode_change(self, mode: Mode) -> None:
        """Announce mode change via voice (non-blocking)."""
        try:
            voice = mode.config.voice.primary_voice
            rate = mode.config.voice.speech_rate
            message = f"Switched to {mode.name} mode"

            speak_serialized(message, voice=voice, rate=rate, wait=False)
        except Exception as e:
            logger.debug(f"Voice announcement failed: {e}")

    def _save_state(self) -> None:
        """Persist current state to file."""
        try:
            state = {
                "current_mode": (
                    self._current_mode.name if self._current_mode else "developer"
                ),
                "timestamp": time.time(),
                "total_switches": len(self._transitions),
            }

            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(state, indent=2))

        except Exception as e:
            logger.debug(f"State save failed: {e}")

    def _load_state(self) -> None:
        """Load state from file."""
        try:
            if self._state_file.exists():
                state = json.loads(self._state_file.read_text())
                mode_name = state.get("current_mode", "developer")

                # Restore the mode without announcement
                mode = get_mode(mode_name)
                mode.activate()
                self._current_mode = mode

                logger.debug(f"Restored mode state: {mode_name}")

        except Exception as e:
            logger.debug(f"State load failed: {e}")

    def reset(self, default_mode: str = "developer") -> None:
        """Reset to default mode and clear history."""
        self._transitions.clear()
        self._switch_times.clear()
        self.switch(default_mode, announce=True)

    def __str__(self) -> str:
        if self._current_mode:
            return f"ModeManager(current={self._current_mode.name}, total_modes={len(MODE_REGISTRY)})"
        return f"ModeManager(current=None, total_modes={len(MODE_REGISTRY)})"

    def __repr__(self) -> str:
        return self.__str__()


# Global singleton instance
_manager: Optional[ModeManager] = None


def get_manager() -> ModeManager:
    """Get the global ModeManager singleton."""
    global _manager
    if _manager is None:
        _manager = ModeManager()
    return _manager


def set_mode(name_or_code: str) -> ModeTransition:
    """
    Convenience function to switch modes.

    Args:
        name_or_code: Mode name or short code

    Returns:
        ModeTransition record
    """
    return get_manager().switch(name_or_code)


def current_mode() -> Optional[Mode]:
    """Get the current active mode."""
    return get_manager().current()


# Quick access functions
def switch(name_or_code: str) -> ModeTransition:
    """Switch to a mode by name or code."""
    return get_manager().switch(name_or_code)


def status() -> Dict[str, Any]:
    """Get mode manager status."""
    return get_manager().stats()
