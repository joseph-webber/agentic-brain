# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Sound themes for earcons."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SOUND_THEME = "minimal"


@dataclass(frozen=True)
class SoundTheme:
    name: str
    description: str
    volume_multiplier: float
    enabled: bool = True

    def apply(self, base_volume: float) -> float:
        if not self.enabled:
            return 0.0
        return max(0.0, min(1.0, base_volume * self.volume_multiplier))


SOUND_THEMES: dict[str, SoundTheme] = {
    "minimal": SoundTheme(
        name="minimal",
        description="Very subtle earcons that sit under speech comfortably",
        volume_multiplier=0.65,
        enabled=True,
    ),
    "expressive": SoundTheme(
        name="expressive",
        description="More noticeable earcons for busy or noisy environments",
        volume_multiplier=1.0,
        enabled=True,
    ),
    "silent": SoundTheme(
        name="silent",
        description="Disable earcons entirely",
        volume_multiplier=0.0,
        enabled=False,
    ),
}


def get_sound_theme(name: str | None = None) -> SoundTheme:
    normalized = (name or DEFAULT_SOUND_THEME).strip().lower()
    if normalized not in SOUND_THEMES:
        valid = ", ".join(sorted(SOUND_THEMES))
        raise ValueError(f"Unknown sound theme '{name}'. Expected one of: {valid}")
    return SOUND_THEMES[normalized]


def list_sound_themes() -> tuple[str, ...]:
    return tuple(sorted(SOUND_THEMES))
