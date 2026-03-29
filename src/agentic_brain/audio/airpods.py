# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""AirPods and spatial-audio integration for agentic-brain.

The implementation is intentionally layered:

1. Pure-Python discovery and routing fallbacks using ``system_profiler`` and the
   optional ``SwitchAudioSource`` command-line utility.
2. A Swift bridge for advanced spatial audio and head-tracking on Apple
   platforms when the Swift toolchain is available.
3. A monitoring loop for auto-routing, adaptive transparency, and battery alerts.

The Python layer is fully testable without Apple hardware by injecting a custom
command runner and bridge.
"""

from __future__ import annotations

import json
import logging
import platform
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

logger = logging.getLogger(__name__)


class NoiseControlMode(StrEnum):
    """Supported headphone noise-control modes."""

    OFF = "off"
    NOISE_CANCELLATION = "noise_cancellation"
    TRANSPARENCY = "transparency"
    ADAPTIVE = "adaptive"


class HeadTrackingMode(StrEnum):
    """How the 3D scene should behave relative to head movement."""

    OFF = "off"
    FIXED = "fixed"
    FOLLOW_HEAD = "follow_head"


@dataclass(slots=True)
class BatteryLevels:
    """Battery levels reported by AirPods accessories."""

    single: int | None = None
    left: int | None = None
    right: int | None = None
    case: int | None = None

    def minimum_level(self) -> int | None:
        levels = [
            value
            for value in (self.single, self.left, self.right, self.case)
            if value is not None
        ]
        if not levels:
            return None
        return min(levels)

    def as_dict(self) -> dict[str, int | None]:
        return {
            "single": self.single,
            "left": self.left,
            "right": self.right,
            "case": self.case,
        }


@dataclass(slots=True)
class HeadTrackingPose:
    """Current head-tracking pose in degrees."""

    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    timestamp: float = field(default_factory=time.time)
    source: str = "unavailable"


@dataclass(slots=True)
class SpatialVoicePosition:
    """3D placement for a single voice in the spatial scene."""

    name: str
    azimuth: float
    elevation: float = 0.0
    distance: float = 1.0
    gain: float = 1.0
    is_anchor: bool = False

    def to_native_payload(self) -> dict[str, float | str | bool]:
        return {
            "name": self.name,
            "azimuth": self.azimuth,
            "elevation": self.elevation,
            "distance": self.distance,
            "gain": self.gain,
            "isAnchor": self.is_anchor,
        }


@dataclass(slots=True)
class SpatialAudioScene:
    """Desired spatial layout for the ladies around the listener."""

    mode: HeadTrackingMode = HeadTrackingMode.FIXED
    fixed_listener_space: bool = True
    voices: list[SpatialVoicePosition] = field(default_factory=list)

    def to_native_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "fixedListenerSpace": self.fixed_listener_space,
            "voices": [voice.to_native_payload() for voice in self.voices],
        }


@dataclass(slots=True)
class AirPodsDevice:
    """Detected AirPods device."""

    name: str
    address: str | None = None
    connected: bool = False
    battery: BatteryLevels = field(default_factory=BatteryLevels)


@dataclass(slots=True)
class AirPodsStatus:
    """Full AirPods integration status."""

    device: AirPodsDevice | None = None
    output_selected: bool = False
    current_output_device: str | None = None
    spatial_audio_enabled: bool = False
    head_tracking_available: bool = False
    head_tracking_enabled: bool = False
    head_tracking_mode: HeadTrackingMode = HeadTrackingMode.FIXED
    head_pose: HeadTrackingPose | None = None
    noise_control_mode: NoiseControlMode | None = None
    scene: SpatialAudioScene | None = None
    last_updated: float = field(default_factory=time.time)

    @property
    def connected(self) -> bool:
        return bool(self.device and self.device.connected)

    @property
    def battery(self) -> BatteryLevels:
        return self.device.battery if self.device else BatteryLevels()


class NativeBridgeError(RuntimeError):
    """Raised when a native bridge cannot fulfill a request."""


class SwiftAirPodsBridge:
    """Thin wrapper around the Swift native bridge script."""

    def __init__(
        self,
        bridge_path: Path | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ):
        self.bridge_path = bridge_path or (
            Path(__file__).resolve().parent / "native" / "airpods_bridge.swift"
        )
        self.runner = runner

    def is_available(self) -> bool:
        if platform.system() != "Darwin":
            return False
        if not self.bridge_path.exists():
            return False
        return shutil.which("xcrun") is not None or shutil.which("swift") is not None

    def invoke(
        self, command: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not self.is_available():
            raise NativeBridgeError("Swift AirPods bridge is unavailable")

        launcher = ["xcrun", "swift"] if shutil.which("xcrun") else ["swift"]
        cmd = [*launcher, str(self.bridge_path), command]
        if payload is not None:
            cmd.append(json.dumps(payload))
        result = self.runner(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise NativeBridgeError(result.stderr.strip() or result.stdout.strip())
        output = result.stdout.strip()
        if not output:
            return {}
        return json.loads(output)


class AirPodsManager:
    """High-level AirPods support for routing, monitoring, and spatial voice."""

    def __init__(
        self,
        *,
        command_runner: Callable[
            ..., subprocess.CompletedProcess[str]
        ] = subprocess.run,
        native_bridge: SwiftAirPodsBridge | None = None,
        target_name_patterns: Sequence[str] = (
            "AirPods Max",
            "AirPods Pro Max",
            "AirPods Pro",
            "AirPods",
        ),
        low_battery_threshold: int = 20,
        adaptive_transparency: bool = False,
        head_tracking_mode: HeadTrackingMode = HeadTrackingMode.FIXED,
        fixed_listener_space: bool = True,
        voice_alert: Callable[[str], None] | None = None,
    ):
        self.command_runner = command_runner
        self.native_bridge = native_bridge or SwiftAirPodsBridge(runner=command_runner)
        self.target_name_patterns = tuple(target_name_patterns)
        self.low_battery_threshold = low_battery_threshold
        self.adaptive_transparency = adaptive_transparency
        self.head_tracking_mode = head_tracking_mode
        self.fixed_listener_space = fixed_listener_space
        self.voice_alert = voice_alert
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_status: AirPodsStatus | None = None
        self._battery_alerted = False
        self._speech_restore_mode: NoiseControlMode | None = None
        self._scene = self.default_spatial_scene()
        self._fallback_output_device: str | None = None

    def detect_airpods_pro_max(self) -> AirPodsDevice | None:
        return self._find_airpods_device()

    def connected_device(self) -> AirPodsDevice | None:
        device = self._find_airpods_device()
        if device and device.connected:
            return device
        return None

    def is_connected(self) -> bool:
        return self.connected_device() is not None

    def get_battery_levels(self) -> BatteryLevels:
        device = self._find_airpods_device()
        return device.battery if device else BatteryLevels()

    def get_head_tracking_data(self) -> HeadTrackingPose | None:
        if self.native_bridge.is_available():
            try:
                response = self.native_bridge.invoke("head-tracking")
                return HeadTrackingPose(
                    yaw=float(response.get("yaw", 0.0)),
                    pitch=float(response.get("pitch", 0.0)),
                    roll=float(response.get("roll", 0.0)),
                    timestamp=float(response.get("timestamp", time.time())),
                    source=response.get("source", "swift"),
                )
            except Exception as exc:  # pragma: no cover - best effort bridge path
                logger.debug("Swift head-tracking bridge failed: %s", exc)
        return None

    def get_spatial_audio_status(self) -> dict[str, Any]:
        status = self.status()
        return {
            "enabled": status.spatial_audio_enabled,
            "headTrackingAvailable": status.head_tracking_available,
            "headTrackingEnabled": status.head_tracking_enabled,
            "headTrackingMode": status.head_tracking_mode.value,
            "fixedListenerSpace": (
                status.scene.fixed_listener_space
                if status.scene
                else self.fixed_listener_space
            ),
        }

    def current_output_device(self) -> str | None:
        if shutil.which("SwitchAudioSource"):
            result = self._run_command(["SwitchAudioSource", "-c"])
            if result.returncode == 0:
                name = result.stdout.strip()
                if name:
                    return name

        if self.native_bridge.is_available():
            try:
                response = self.native_bridge.invoke("status")
                current_output = response.get("currentOutputDevice")
                if isinstance(current_output, str) and current_output:
                    return current_output
            except Exception as exc:  # pragma: no cover - best effort bridge path
                logger.debug("Swift status bridge failed: %s", exc)

        audio_data = self._system_profiler_json("SPAudioDataType")
        for item in self._walk_dicts(audio_data):
            if self._to_bool(
                item.get("coreaudio_default_audio_output_device")
                or item.get("default_output_device")
            ):
                return self._first_string(
                    item,
                    "_name",
                    "device_name",
                    "name",
                    "coreaudio_default_audio_output_device",
                )
        return None

    def route_audio(self, device_name: str | None = None) -> bool:
        target = device_name
        if not target:
            device = self.connected_device()
            if not device:
                return False
            target = device.name

        current = self.current_output_device()
        if current and current != target and self._fallback_output_device is None:
            self._fallback_output_device = current

        if shutil.which("SwitchAudioSource"):
            result = self._run_command(["SwitchAudioSource", "-s", target])
            return result.returncode == 0

        if self.native_bridge.is_available():
            try:
                response = self.native_bridge.invoke("route", {"deviceName": target})
                return bool(response.get("routed", False))
            except Exception as exc:  # pragma: no cover - best effort bridge path
                logger.debug("Swift route bridge failed: %s", exc)
        return False

    def restore_fallback_output(self) -> bool:
        if not self._fallback_output_device:
            return False
        return self.route_audio(self._fallback_output_device)

    def handoff_audio(self, target_device: str | None = None) -> bool:
        if target_device:
            return self.route_audio(target_device)
        if self.is_connected():
            return self.route_audio()
        return self.restore_fallback_output()

    def control_noise_cancellation(self, mode: NoiseControlMode | str) -> bool:
        resolved = NoiseControlMode(mode)
        if self.native_bridge.is_available():
            try:
                response = self.native_bridge.invoke(
                    "noise-control", {"mode": resolved.value}
                )
                if response.get("success"):
                    return True
            except Exception as exc:  # pragma: no cover - best effort bridge path
                logger.debug("Noise-control bridge failed: %s", exc)
        return False

    def set_head_tracking_mode(self, mode: HeadTrackingMode | str) -> bool:
        resolved = HeadTrackingMode(mode)
        self.head_tracking_mode = resolved
        if self.native_bridge.is_available():
            try:
                response = self.native_bridge.invoke(
                    "head-tracking-mode", {"mode": resolved.value}
                )
                return bool(response.get("success", False))
            except Exception as exc:  # pragma: no cover - best effort bridge path
                logger.debug("Head-tracking bridge failed: %s", exc)
        return True

    def configure_spatial_audio(
        self,
        scene: SpatialAudioScene | None = None,
        voice_names: Sequence[str] | None = None,
    ) -> bool:
        if scene is None:
            scene = self.default_spatial_scene(voice_names)
        self._scene = scene
        if self.native_bridge.is_available():
            try:
                response = self.native_bridge.invoke(
                    "spatial-layout", scene.to_native_payload()
                )
                return bool(response.get("success", False))
            except Exception as exc:  # pragma: no cover - best effort bridge path
                logger.debug("Spatial-audio bridge failed: %s", exc)
        return True

    def prepare_for_speech(self, text: str | None = None) -> bool:
        if not self.adaptive_transparency or not self.is_connected():
            return False
        status = self.status()
        self._speech_restore_mode = status.noise_control_mode
        return self.control_noise_cancellation(NoiseControlMode.TRANSPARENCY)

    def finish_speech(self) -> bool:
        if not self.adaptive_transparency or self._speech_restore_mode is None:
            return False
        restore_mode = self._speech_restore_mode
        self._speech_restore_mode = None
        return self.control_noise_cancellation(restore_mode)

    def ensure_brain_audio_ready(self, text: str | None = None) -> bool:
        routed = self.route_audio()
        self.configure_spatial_audio(self._scene)
        self.prepare_for_speech(text)
        return routed

    def status(self) -> AirPodsStatus:
        device = self._find_airpods_device()
        current_output = self.current_output_device()
        output_selected = bool(
            device and current_output and current_output == device.name
        )
        head_pose = self.get_head_tracking_data()
        native_status: dict[str, Any] = {}
        if self.native_bridge.is_available():
            try:
                native_status = self.native_bridge.invoke("status")
            except Exception as exc:  # pragma: no cover - best effort bridge path
                logger.debug("Swift status bridge failed: %s", exc)

        status = AirPodsStatus(
            device=device,
            output_selected=output_selected,
            current_output_device=current_output,
            spatial_audio_enabled=bool(native_status.get("spatialAudioEnabled", False)),
            head_tracking_available=bool(
                native_status.get("headTrackingAvailable", head_pose is not None)
            ),
            head_tracking_enabled=bool(native_status.get("headTrackingEnabled", False)),
            head_tracking_mode=self.head_tracking_mode,
            head_pose=head_pose,
            noise_control_mode=self._parse_noise_mode(
                native_status.get("noiseControlMode")
            ),
            scene=self._scene,
        )
        status.last_updated = time.time()
        return status

    def start_monitoring(
        self,
        callback: Callable[[AirPodsStatus], None] | None = None,
        *,
        interval: float = 5.0,
        route_on_connect: bool = True,
    ) -> None:
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.is_set():
                try:
                    status = self.status()
                    self._handle_status_update(status, callback, route_on_connect)
                except Exception as exc:  # pragma: no cover - monitor resilience path
                    logger.warning("AirPods monitor iteration failed: %s", exc)
                self._stop_event.wait(interval)

        self._monitor_thread = threading.Thread(
            target=_loop,
            name="agentic-brain-airpods-monitor",
            daemon=True,
        )
        self._monitor_thread.start()

    def stop_monitoring(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=timeout)

    def default_spatial_scene(
        self,
        voice_names: Sequence[str] | None = None,
    ) -> SpatialAudioScene:
        if not voice_names:
            voice_names = (
                "Karen",
                "Moira",
                "Tingting",
                "Zosia",
                "Shelley",
                "Linh",
                "Damayanti",
            )

        names = list(voice_names)
        voices: list[SpatialVoicePosition] = []
        if names:
            voices.append(
                SpatialVoicePosition(
                    name=names[0],
                    azimuth=0.0,
                    elevation=0.0,
                    distance=1.0,
                    gain=1.1,
                    is_anchor=True,
                )
            )
        orbit = [-45.0, 45.0, -100.0, 100.0, -150.0, 150.0, 180.0]
        for index, name in enumerate(names[1:]):
            azimuth = orbit[index % len(orbit)]
            elevation = 10.0 if index % 2 == 0 else -8.0
            distance = 1.2 + (0.15 * (index % 3))
            voices.append(
                SpatialVoicePosition(
                    name=name,
                    azimuth=azimuth,
                    elevation=elevation,
                    distance=distance,
                    gain=0.92,
                )
            )
        return SpatialAudioScene(
            mode=self.head_tracking_mode,
            fixed_listener_space=self.fixed_listener_space,
            voices=voices,
        )

    def _handle_status_update(
        self,
        status: AirPodsStatus,
        callback: Callable[[AirPodsStatus], None] | None,
        route_on_connect: bool,
    ) -> None:
        previous = self._last_status
        if route_on_connect and status.connected and not status.output_selected:
            if (
                previous is None
                or not previous.connected
                or previous.current_output_device != status.current_output_device
            ):
                self.route_audio(status.device.name if status.device else None)
                self.configure_spatial_audio(self._scene)

        if callback:
            callback(status)

        min_battery = status.battery.minimum_level()
        if min_battery is not None and min_battery <= self.low_battery_threshold:
            if not self._battery_alerted and self.voice_alert:
                self.voice_alert(
                    f"AirPods battery is low at {min_battery} percent. Consider charging soon."
                )
                self._battery_alerted = True
        else:
            self._battery_alerted = False

        self._last_status = status

    def _find_airpods_device(self) -> AirPodsDevice | None:
        bluetooth_data = self._system_profiler_json("SPBluetoothDataType")
        matches: list[AirPodsDevice] = []
        for item in self._walk_dicts(bluetooth_data):
            name = self._first_string(
                item, "device_title", "name", "_name", "device_name"
            )
            if not name or not self._matches_target(name):
                continue
            device = AirPodsDevice(
                name=name,
                address=self._first_string(
                    item, "device_address", "address", "bd_addr"
                ),
                connected=self._to_bool(
                    self._first_non_none(
                        item, "device_connected", "connected", "is_connected"
                    )
                ),
                battery=self._parse_battery_levels(item),
            )
            matches.append(device)

        if not matches:
            return None
        matches.sort(
            key=lambda device: (device.connected, device.battery.minimum_level() or -1),
            reverse=True,
        )
        return matches[0]

    def _system_profiler_json(self, data_type: str) -> dict[str, Any]:
        result = self._run_command(["system_profiler", "-json", data_type])
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.debug("Failed to parse system_profiler output for %s", data_type)
            return {}

    def _run_command(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return self.command_runner(command, capture_output=True, text=True, check=False)

    def _matches_target(self, name: str) -> bool:
        lowered = name.lower()
        return any(pattern.lower() in lowered for pattern in self.target_name_patterns)

    @staticmethod
    def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
        if isinstance(value, dict):
            yield value
            for nested in value.values():
                yield from AirPodsManager._walk_dicts(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from AirPodsManager._walk_dicts(nested)

    @staticmethod
    def _first_non_none(mapping: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in mapping and mapping[key] not in (None, ""):
                return mapping[key]
        return None

    @staticmethod
    def _first_string(mapping: dict[str, Any], *keys: str) -> str | None:
        value = AirPodsManager._first_non_none(mapping, *keys)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"yes", "true", "connected", "1"}
        if isinstance(value, (int, float)):
            return value != 0
        return False

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            digits = "".join(ch for ch in value if ch.isdigit())
            if digits:
                return int(digits)
        return None

    @classmethod
    def _parse_battery_levels(cls, data: dict[str, Any]) -> BatteryLevels:
        lookup = {str(key).lower(): value for key, value in data.items()}
        return BatteryLevels(
            single=cls._parse_int(
                lookup.get("batterypercent")
                or lookup.get("batterypercentcombined")
                or lookup.get("battery_level")
                or lookup.get("battery")
            ),
            left=cls._parse_int(
                lookup.get("batterypercentleft")
                or lookup.get("left_battery")
                or lookup.get("battery_left")
            ),
            right=cls._parse_int(
                lookup.get("batterypercentright")
                or lookup.get("right_battery")
                or lookup.get("battery_right")
            ),
            case=cls._parse_int(
                lookup.get("batterypercentcase")
                or lookup.get("case_battery")
                or lookup.get("battery_case")
            ),
        )

    @staticmethod
    def _parse_noise_mode(value: Any) -> NoiseControlMode | None:
        if value is None:
            return None
        try:
            return NoiseControlMode(str(value))
        except ValueError:
            return None


_default_airpods_manager: AirPodsManager | None = None


def get_airpods_manager() -> AirPodsManager:
    global _default_airpods_manager
    if _default_airpods_manager is None:
        _default_airpods_manager = AirPodsManager()
    return _default_airpods_manager
