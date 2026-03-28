from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from agentic_brain.audio import Audio, AudioConfig
from agentic_brain.audio.airpods import (
    AirPodsDevice,
    AirPodsManager,
    AirPodsStatus,
    BatteryLevels,
    HeadTrackingMode,
    NoiseControlMode,
)


class Completed:
    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def make_runner(outputs: dict[tuple[str, ...], Completed]):
    def _runner(command, capture_output=True, text=True, check=False):
        key = tuple(command)
        if key in outputs:
            return outputs[key]
        raise AssertionError(f"Unexpected command: {command}")

    return _runner


def test_detect_airpods_max_and_battery_levels():
    bluetooth_json = {
        "SPBluetoothDataType": [
            {
                "device_title": "AirPods Max",
                "device_connected": "Yes",
                "device_address": "AA-BB",
                "batteryPercent": 74,
            }
        ]
    }
    audio_json = {"SPAudioDataType": []}
    manager = AirPodsManager(
        command_runner=make_runner(
            {
                ("system_profiler", "-json", "SPBluetoothDataType"): Completed(
                    json.dumps(bluetooth_json)
                ),
                ("system_profiler", "-json", "SPAudioDataType"): Completed(
                    json.dumps(audio_json)
                ),
            }
        )
    )
    device = manager.detect_airpods_pro_max()

    assert device is not None
    assert device.name == "AirPods Max"
    assert device.connected is True
    assert device.battery.single == 74


@patch("agentic_brain.audio.airpods.shutil.which")
def test_route_audio_uses_switchaudiosource(mock_which):
    mock_which.side_effect = (
        lambda name: "/usr/local/bin/SwitchAudioSource"
        if name == "SwitchAudioSource"
        else None
    )
    manager = AirPodsManager(
        command_runner=make_runner(
            {
                ("SwitchAudioSource", "-c"): Completed("MacBook Pro Speakers\n"),
                ("SwitchAudioSource", "-s", "AirPods Max"): Completed(),
                ("system_profiler", "-json", "SPBluetoothDataType"): Completed(
                    json.dumps(
                        {
                            "SPBluetoothDataType": [
                                {
                                    "name": "AirPods Max",
                                    "connected": True,
                                    "batteryPercent": 80,
                                }
                            ]
                        }
                    )
                ),
            }
        )
    )

    assert manager.route_audio() is True


def test_default_spatial_scene_places_karen_center():
    manager = AirPodsManager(command_runner=make_runner({}))
    scene = manager.default_spatial_scene(["Karen", "Moira", "Tingting"])

    assert scene.mode == HeadTrackingMode.FIXED
    assert scene.voices[0].name == "Karen"
    assert scene.voices[0].azimuth == 0.0
    assert scene.voices[0].is_anchor is True
    assert {scene.voices[1].azimuth, scene.voices[2].azimuth} == {-45.0, 45.0}


@patch("agentic_brain.audio.airpods.shutil.which", return_value=None)
def test_prepare_and_finish_speech_toggle_transparency(mock_which):
    runner = make_runner(
        {
            ("system_profiler", "-json", "SPBluetoothDataType"): Completed(
                json.dumps(
                    {
                        "SPBluetoothDataType": [
                            {
                                "name": "AirPods Max",
                                "connected": True,
                                "batteryPercent": 63,
                            }
                        ]
                    }
                )
            ),
            ("system_profiler", "-json", "SPAudioDataType"): Completed(
                json.dumps({"SPAudioDataType": []})
            ),
        }
    )
    native_bridge = MagicMock()
    native_bridge.is_available.return_value = True
    native_bridge.invoke.side_effect = [
        {
            "connected": True,
            "currentOutputDevice": "AirPods Max",
            "noiseControlMode": "noise_cancellation",
            "spatialAudioEnabled": True,
            "headTrackingAvailable": True,
            "headTrackingEnabled": True,
        },
        {
            "source": "coremotion",
            "yaw": 0.0,
            "pitch": 0.0,
            "roll": 0.0,
            "timestamp": 1.0,
        },
        {
            "connected": True,
            "currentOutputDevice": "AirPods Max",
            "noiseControlMode": "noise_cancellation",
            "spatialAudioEnabled": True,
            "headTrackingAvailable": True,
            "headTrackingEnabled": True,
        },
        {"success": True},
        {"success": True},
    ]
    manager = AirPodsManager(
        command_runner=runner,
        native_bridge=native_bridge,
        adaptive_transparency=True,
    )

    assert manager.prepare_for_speech("Hello") is True
    assert manager.finish_speech() is True
    noise_calls = [
        call for call in native_bridge.invoke.call_args_list if call.args[0] == "noise-control"
    ]
    assert len(noise_calls) == 2
    assert noise_calls[0].args[1]["mode"] == NoiseControlMode.TRANSPARENCY.value
    assert noise_calls[1].args[1]["mode"] == NoiseControlMode.NOISE_CANCELLATION.value


def test_monitoring_alerts_on_low_battery():
    alerts: list[str] = []
    manager = AirPodsManager(command_runner=make_runner({}), voice_alert=alerts.append)
    low_status = AirPodsStatus(
        device=AirPodsDevice(
            name="AirPods Max",
            connected=True,
            battery=BatteryLevels(single=12),
        )
    )

    manager._handle_status_update(low_status, callback=None, route_on_connect=False)

    assert alerts == ["AirPods battery is low at 12 percent. Consider charging soon."]


def test_audio_speak_integrates_airpods_hooks():
    manager = MagicMock()
    manager.ensure_brain_audio_ready.return_value = True
    manager.finish_speech.return_value = True

    audio = Audio(AudioConfig(auto_route_to_airpods=True, adaptive_transparency=True))
    with patch.object(audio, "_get_airpods_manager", return_value=manager), patch.object(
        audio, "_speak_macos", return_value=True
    ):
        audio.platform = audio.platform.MACOS
        audio._tts_available = True
        assert audio.speak("Testing AirPods") is True

    manager.ensure_brain_audio_ready.assert_called_once_with("Testing AirPods")
    manager.finish_speech.assert_called_once()
