from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from agentic_brain import audio
from agentic_brain.audio.airpods import (
    AirPodsDevice,
    BatteryLevels,
)
from agentic_brain.audio.airpods import (
    AirPodsStatus as ManagerAirPodsStatus,
)
from agentic_brain.audio.airpods_detect import (
    AirPodsDetector,
    AudioRouter,
    airpods_connected,
    check_battery_and_warn,
)


class Completed:
    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def test_detector_maps_airpods_pro_max_status():
    manager = MagicMock()
    manager.status.return_value = ManagerAirPodsStatus(
        device=AirPodsDevice(
            name="Joseph's AirPods Pro Max",
            connected=True,
            battery=BatteryLevels(single=74),
        ),
        spatial_audio_enabled=False,
        head_tracking_available=False,
    )
    detector = AirPodsDetector(manager=manager)

    status = detector.get_status()

    assert status.connected is True
    assert status.name == "Joseph's AirPods Pro Max"
    assert status.battery_left == 74
    assert status.battery_right == 74
    assert status.battery_case is None
    assert status.spatial_audio_available is True
    assert status.head_tracking_available is True


def test_handle_connection_change_routes_on_connect_and_disconnect():
    manager = MagicMock()
    manager.status.side_effect = [
        ManagerAirPodsStatus(
            device=AirPodsDevice(name="AirPods Pro Max", connected=True),
        ),
        ManagerAirPodsStatus(
            device=None,
        ),
    ]
    router = MagicMock()
    detector = AirPodsDetector(manager=manager)

    connected = detector.handle_connection_change(
        router=router,
        route_to_speakers_on_disconnect=True,
    )
    disconnected = detector.handle_connection_change(
        router=router,
        route_to_speakers_on_disconnect=True,
    )

    assert connected.connected is True
    assert disconnected.connected is False
    router.route_to_airpods.assert_called_once_with("AirPods Pro Max")
    router.route_to_speakers.assert_called_once_with()


def test_audio_router_lists_and_switches_outputs():
    commands = {
        ("/opt/homebrew/bin/SwitchAudioSource", "-a", "-t", "output"): Completed(
            "MacBook Pro Speakers\nAirPods Pro Max\nStudio Display\n"
        ),
        ("/opt/homebrew/bin/SwitchAudioSource", "-c"): Completed(
            "MacBook Pro Speakers\n"
        ),
        ("/opt/homebrew/bin/SwitchAudioSource", "-s", "AirPods Pro Max"): Completed(),
        (
            "/opt/homebrew/bin/SwitchAudioSource",
            "-s",
            "MacBook Pro Speakers",
        ): Completed(),
    }

    def fake_run(command, capture_output=True, text=True, check=False):
        return commands[tuple(command)]

    router = AudioRouter(switchaudio_path=Path("/opt/homebrew/bin/SwitchAudioSource"))
    with patch(
        "agentic_brain.audio.airpods_detect.subprocess.run", side_effect=fake_run
    ):
        assert router.list_outputs() == [
            "MacBook Pro Speakers",
            "AirPods Pro Max",
            "Studio Display",
        ]
        assert router.get_current_output() == "MacBook Pro Speakers"
        assert router.route_to_airpods("AirPods Pro Max") is True
        assert router.route_to_speakers() is True


def test_check_battery_and_warn_announces_shared_thresholds_once():
    from agentic_brain.audio import airpods_detect

    airpods_detect._last_battery_warning.clear()
    detector = MagicMock()
    detector.get_battery.side_effect = [
        {"left": 20, "right": 20, "case": None},
        {"left": 20, "right": 20, "case": None},
        {"left": 10, "right": 10, "case": None},
    ]
    speaker = MagicMock()

    first = check_battery_and_warn(detector=detector, speaker=speaker)
    second = check_battery_and_warn(detector=detector, speaker=speaker)
    third = check_battery_and_warn(detector=detector, speaker=speaker)

    assert first == ["Heads up, AirPods battery at 20 percent."]
    assert second == []
    assert third == ["Warning! AirPods battery at 10 percent!"]
    assert speaker.call_count == 2


def test_module_exports_and_singleton_helpers():
    detector = MagicMock()
    detector.is_connected.return_value = True

    with patch(
        "agentic_brain.audio.airpods_detect.get_airpods_detector", return_value=detector
    ):
        assert airpods_connected() is True

    assert audio.AirPodsDetector is AirPodsDetector
    assert audio.AudioRouter is AudioRouter
    assert callable(audio.get_airpods_detector)
    assert callable(audio.get_audio_router)
