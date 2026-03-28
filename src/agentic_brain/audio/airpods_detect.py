# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
AirPods Pro Max detection and audio routing helpers.

This module provides a lightweight compatibility layer for quickly checking
whether Joseph's AirPods are connected, switching audio output, and issuing
low-battery voice warnings. It intentionally reuses the richer AirPods manager
already present in :mod:`agentic_brain.audio.airpods`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .airpods import AirPodsManager


@dataclass(slots=True)
class AirPodsStatus:
    """Simplified AirPods status for quick checks and routing."""

    connected: bool
    name: str
    battery_left: Optional[int] = None
    battery_right: Optional[int] = None
    battery_case: Optional[int] = None
    spatial_audio_available: bool = False
    head_tracking_available: bool = False


class AirPodsDetector:
    """Detect and manage AirPods Pro Max connection."""

    def __init__(self, manager: AirPodsManager | None = None):
        self._manager = manager or AirPodsManager()
        self._last_status: Optional[AirPodsStatus] = None

    def _map_status(self) -> AirPodsStatus:
        rich_status = self._manager.status()
        device = rich_status.device
        battery_single = rich_status.battery.single
        battery_left = rich_status.battery.left
        battery_right = rich_status.battery.right

        if battery_single is not None and battery_left is None and battery_right is None:
            battery_left = battery_single
            battery_right = battery_single

        name = device.name if device else ""
        spatial_audio_available = rich_status.spatial_audio_enabled or self._supports_spatial(name)
        head_tracking_available = (
            rich_status.head_tracking_available or spatial_audio_available
        )

        return AirPodsStatus(
            connected=rich_status.connected,
            name=name,
            battery_left=battery_left,
            battery_right=battery_right,
            battery_case=rich_status.battery.case,
            spatial_audio_available=spatial_audio_available,
            head_tracking_available=head_tracking_available,
        )

    @staticmethod
    def _supports_spatial(name: str) -> bool:
        lowered = name.lower()
        return "airpods max" in lowered or "airpods pro" in lowered

    def get_status(self) -> AirPodsStatus:
        """Get current AirPods status."""
        status = self._map_status()
        self._last_status = status
        return status

    def is_connected(self) -> bool:
        """Quick check if AirPods are connected."""
        return self.get_status().connected

    def get_battery(self) -> dict[str, Optional[int]]:
        """Get battery levels for left, right, and case."""
        status = self.get_status()
        return {
            "left": status.battery_left,
            "right": status.battery_right,
            "case": status.battery_case,
        }

    def supports_spatial_audio(self) -> bool:
        """Check if connected AirPods support spatial audio."""
        status = self.get_status()
        return status.spatial_audio_available

    def supports_head_tracking(self) -> bool:
        """Check if head tracking is available."""
        status = self.get_status()
        return status.head_tracking_available

    def handle_connection_change(
        self,
        *,
        route_audio: bool = True,
        route_to_speakers_on_disconnect: bool = False,
        router: AudioRouter | None = None,
    ) -> AirPodsStatus:
        """Handle connection and disconnection events."""
        previous = self._last_status
        status = self._map_status()

        if route_audio:
            active_router = router or get_audio_router()
            if status.connected and (previous is None or not previous.connected):
                active_router.route_to_airpods(status.name)
            elif (
                route_to_speakers_on_disconnect
                and previous is not None
                and previous.connected
                and not status.connected
            ):
                active_router.route_to_speakers()

        self._last_status = status
        return status


class AudioRouter:
    """Route audio to appropriate output device."""

    def __init__(self, switchaudio_path: Path | None = None):
        self._detector = AirPodsDetector()
        self._switchaudio_path = switchaudio_path or self._find_switchaudio()

    def _find_switchaudio(self) -> Optional[Path]:
        """Find SwitchAudioSource binary."""
        paths = [
            Path("/opt/homebrew/bin/SwitchAudioSource"),
            Path("/usr/local/bin/SwitchAudioSource"),
        ]
        for path in paths:
            if path.exists():
                return path
        return None

    def _run(self, *args: str) -> subprocess.CompletedProcess[str] | None:
        if not self._switchaudio_path:
            return None
        return subprocess.run(
            [str(self._switchaudio_path), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def list_outputs(self) -> list[str]:
        """List available audio output devices."""
        result = self._run("-a", "-t", "output")
        if result is None or result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def get_current_output(self) -> str:
        """Get current audio output device."""
        result = self._run("-c")
        if result is None or result.returncode != 0:
            return "Unknown"
        return result.stdout.strip() or "Unknown"

    def set_output(self, device: str) -> bool:
        """Set audio output device."""
        result = self._run("-s", device)
        return bool(result and result.returncode == 0)

    def route_to_airpods(self, preferred_name: str | None = None) -> bool:
        """Route audio to AirPods if connected."""
        outputs = self.list_outputs()
        if preferred_name:
            for output in outputs:
                if output == preferred_name:
                    return self.set_output(output)

        for output in outputs:
            if "AirPods" in output:
                return self.set_output(output)
        return False

    def route_to_speakers(self) -> bool:
        """Route audio back to MacBook speakers."""
        outputs = self.list_outputs()
        preferred = (
            "MacBook Pro Speakers",
            "MacBook Air Speakers",
            "MacBook Speakers",
        )
        for device in preferred:
            if device in outputs:
                return self.set_output(device)

        for output in outputs:
            lowered = output.lower()
            if "macbook" in lowered and "speaker" in lowered:
                return self.set_output(output)
        return False


_detector: Optional[AirPodsDetector] = None
_router: Optional[AudioRouter] = None
_last_battery_warning: dict[str, int] = {}


def get_airpods_detector() -> AirPodsDetector:
    global _detector
    if _detector is None:
        _detector = AirPodsDetector()
    return _detector


def get_audio_router() -> AudioRouter:
    global _router
    if _router is None:
        _router = AudioRouter()
    return _router


def airpods_connected() -> bool:
    """Quick check if AirPods are connected."""
    return get_airpods_detector().is_connected()


def _default_speaker(message: str) -> None:
    from agentic_brain.voice import speak_safe

    speak_safe(message, voice="Karen", rate=155)


def _warning_message(component: str, level: int, urgent: bool, shared: bool) -> str:
    if shared:
        if urgent:
            return f"Warning! AirPods battery at {level} percent!"
        return f"Heads up, AirPods battery at {level} percent."

    label = {
        "left": "left AirPod",
        "right": "right AirPod",
        "case": "charging case",
    }.get(component, "AirPods")
    if urgent:
        return f"Warning! {label.capitalize()} battery at {level} percent!"
    return f"Heads up, {label} battery at {level} percent."


def check_battery_and_warn(
    *,
    detector: AirPodsDetector | None = None,
    speaker: Callable[[str], None] | None = None,
) -> list[str]:
    """Check battery and speak warnings when thresholds are crossed."""
    detector = detector or get_airpods_detector()
    speaker = speaker or _default_speaker
    battery = detector.get_battery()
    warnings: list[str] = []
    shared_level = (
        battery["left"]
        if battery["left"] is not None and battery["left"] == battery["right"]
        else None
    )

    for component in ("left", "right", "case"):
        level = battery.get(component)
        if level is None:
            continue

        threshold = 10 if level <= 10 else 20 if level <= 20 else None
        if threshold is None:
            _last_battery_warning.pop(component, None)
            continue
        if _last_battery_warning.get(component) == threshold:
            continue

        message = _warning_message(
            component=component,
            level=level,
            urgent=threshold == 10,
            shared=shared_level is not None and component in {"left", "right"},
        )

        if shared_level is not None and component == "right":
            _last_battery_warning[component] = threshold
            continue

        speaker(message)
        warnings.append(message)
        _last_battery_warning[component] = threshold

    return warnings


__all__ = [
    "AirPodsDetector",
    "AirPodsStatus",
    "AudioRouter",
    "airpods_connected",
    "check_battery_and_warn",
    "get_airpods_detector",
    "get_audio_router",
]
