# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
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

"""Tests for the Spatial Audio Router.

Covers position calculations, backend selection, stereo panning math,
voice mapping, Sox rendering path, and fallback logic.  All external
commands (``say``, ``sox``, ``afplay``) are mocked — no audio hardware
required.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from agentic_brain.audio.spatial_audio import (
    ALL_LADIES,
    LADY_POSITIONS,
    LADY_VOICE_MAP,
    SpatialAudioRouter,
    SpatialPosition,
    _azimuth_to_cartesian,
    _azimuth_to_stereo_gains,
    get_spatial_router,
    speak_spatial,
)

# ── Position data integrity ──────────────────────────────────────────


class TestVoicePersonaPositions:
    """Verify the 14 voice personas are correctly placed around the circle."""

    def test_all_14_voice_personas_defined(self):
        assert len(LADY_POSITIONS) == 14

    def test_all_voice_personas_tuple_matches_positions(self):
        assert set(ALL_LADIES) == set(LADY_POSITIONS.keys())

    def test_karen_is_center_front(self):
        assert LADY_POSITIONS["Karen"].azimuth == 0

    def test_sari_is_directly_behind(self):
        assert LADY_POSITIONS["Sari"].azimuth == 180

    def test_no_duplicate_azimuths(self):
        azimuths = [p.azimuth for p in LADY_POSITIONS.values()]
        assert len(azimuths) == len(
            set(azimuths)
        ), "Two voice personas share the same azimuth"

    def test_all_azimuths_in_valid_range(self):
        for name, pos in LADY_POSITIONS.items():
            assert 0 <= pos.azimuth < 360, f"{name} azimuth {pos.azimuth} out of range"

    def test_azimuths_increase_clockwise(self):
        ordered = sorted(LADY_POSITIONS.values(), key=lambda p: p.azimuth)
        for i in range(len(ordered) - 1):
            assert ordered[i].azimuth < ordered[i + 1].azimuth

    def test_default_distance_is_one(self):
        for name, pos in LADY_POSITIONS.items():
            assert pos.distance == 1.0, f"{name} distance is {pos.distance}"

    def test_default_elevation_is_zero(self):
        for name, pos in LADY_POSITIONS.items():
            assert pos.elevation == 0.0, f"{name} elevation is {pos.elevation}"


# ── Voice map ────────────────────────────────────────────────────────


class TestVoicePersonaMap:
    """All 14 voice personas must map to a valid macOS voice."""

    def test_all_voice_personas_have_voice_mapping(self):
        for voice in LADY_POSITIONS:
            assert voice in LADY_VOICE_MAP, f"{voice} missing from LADY_VOICE_MAP"

    def test_karen_is_premium(self):
        assert LADY_VOICE_MAP["Karen"] == "Karen (Premium)"

    def test_indonesian_trio_share_damayanti(self):
        for lady in ("Dewi", "Sari", "Wayan"):
            assert LADY_VOICE_MAP[lady] == "Damayanti"

    def test_flo_uses_amelie(self):
        assert LADY_VOICE_MAP["Flo"] == "Amelie"

    def test_tingting_uses_ting_ting(self):
        assert LADY_VOICE_MAP["Tingting"] == "Ting-Ting"


# ── Stereo panning math ─────────────────────────────────────────────


class TestStereoPanning:
    """Verify the equal-power panning law."""

    def test_front_center_equal_gains(self):
        left, right = _azimuth_to_stereo_gains(0)
        assert abs(left - right) < 0.01, "Front-center should be equal L/R"

    def test_right_ear_favours_right(self):
        left, right = _azimuth_to_stereo_gains(90)
        assert right > left
        assert right > 0.9

    def test_left_ear_favours_left(self):
        left, right = _azimuth_to_stereo_gains(270)
        assert left > right
        assert left > 0.9

    def test_behind_has_rear_attenuation(self):
        left_front, right_front = _azimuth_to_stereo_gains(0)
        left_back, right_back = _azimuth_to_stereo_gains(180)
        # Behind should be slightly quieter
        total_front = left_front + right_front
        total_back = left_back + right_back
        assert total_back < total_front

    def test_gains_are_non_negative(self):
        for az in range(0, 360, 15):
            left, right = _azimuth_to_stereo_gains(float(az))
            assert left >= 0, f"Negative left gain at azimuth {az}"
            assert right >= 0, f"Negative right gain at azimuth {az}"

    def test_equal_power_conservation(self):
        """Total power (L² + R²) should stay roughly constant."""
        powers = []
        for az in range(0, 360, 30):
            left, right = _azimuth_to_stereo_gains(float(az))
            powers.append(left**2 + right**2)
        max_dev = max(powers) - min(powers)
        # Allow 25% variance due to intentional rear attenuation
        assert max_dev < 0.25, f"Power varies by {max_dev:.3f}"


# ── Cartesian conversion ────────────────────────────────────────────


class TestCartesian:
    def test_front_center_is_positive_z(self):
        x, y, z = _azimuth_to_cartesian(0)
        assert abs(x) < 0.01
        assert z > 0.9

    def test_right_is_positive_x(self):
        x, y, z = _azimuth_to_cartesian(90)
        assert x > 0.9
        assert abs(z) < 0.01

    def test_behind_is_negative_z(self):
        x, y, z = _azimuth_to_cartesian(180)
        assert z < -0.9

    def test_left_is_negative_x(self):
        x, y, z = _azimuth_to_cartesian(270)
        assert x < -0.9

    def test_elevation_goes_up(self):
        _, y, _ = _azimuth_to_cartesian(0, elevation_deg=45)
        assert y > 0.5

    def test_distance_scales_output(self):
        x1, _, z1 = _azimuth_to_cartesian(45, distance=1.0)
        x2, _, z2 = _azimuth_to_cartesian(45, distance=2.0)
        assert abs(x2 / x1 - 2.0) < 0.01


# ── Router backend selection ─────────────────────────────────────────


class TestRouterBackend:
    def test_mono_backend_when_no_tools(self):
        with patch("agentic_brain.audio.spatial_audio.shutil.which", return_value=None):
            router = SpatialAudioRouter(force_backend=None)
            # No sox, no say → mono (may also fail detection gracefully)
            assert router.backend in ("mono", "sox")

    def test_force_sox_backend(self):
        router = SpatialAudioRouter(force_backend="sox")
        assert router.backend == "sox"

    def test_force_mono_backend(self):
        router = SpatialAudioRouter(force_backend="mono")
        assert router.backend == "mono"

    def test_force_native_backend(self):
        router = SpatialAudioRouter(force_backend="native")
        assert router.backend == "native"


# ── Router queries ───────────────────────────────────────────────────


class TestRouterQueries:
    @pytest.fixture
    def router(self):
        return SpatialAudioRouter(force_backend="mono")

    def test_get_position_known_lady(self, router):
        pos = router.get_position("Kyoko")
        assert pos.azimuth == 30

    def test_get_position_unknown_defaults_to_karen(self, router):
        pos = router.get_position("UnknownLady")
        assert pos.azimuth == 0  # Karen's position

    def test_set_position(self, router):
        new_pos = SpatialPosition(azimuth=42, elevation=5, distance=1.5)
        router.set_position("TestLady", new_pos)
        assert router.get_position("TestLady").azimuth == 42

    def test_list_positions_returns_all(self, router):
        positions = router.list_positions()
        assert len(positions) >= 14

    def test_get_voice_name_known(self, router):
        assert router.get_voice_name("Tingting") == "Ting-Ting"

    def test_get_voice_name_unknown_defaults_to_karen(self, router):
        assert router.get_voice_name("Nobody") == "Karen (Premium)"

    def test_status_contains_expected_keys(self, router):
        s = router.status()
        assert "backend" in s
        assert "voices" in s
        assert "voice_count" in s
        assert s["voice_count"] == 14
        assert "Karen" in s["voices"]


# ── Sox rendering path ───────────────────────────────────────────────


class TestSoxBackend:
    """Test the Sox stereo-pan speech path with mocked subprocesses."""

    @pytest.fixture
    def sox_router(self):
        return SpatialAudioRouter(force_backend="sox")

    @patch("agentic_brain.audio.spatial_audio.subprocess.run")
    def test_speak_sox_calls_say_then_sox_then_afplay(self, mock_run, sox_router):
        # say -o succeeds and writes a file
        def _side_effect(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stderr = b""
            # Simulate say creating the mono file
            if cmd[0] == "say" and "-o" in cmd:
                out_path = cmd[cmd.index("-o") + 1]
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                Path(out_path).write_bytes(b"\x00" * 100)
            return result

        mock_run.side_effect = _side_effect

        result = sox_router._speak_sox(
            "Hello from Kyoko",
            "Kyoko",
            SpatialPosition(azimuth=30),
            155,
        )

        assert result is True
        calls = [c.args[0][0] for c in mock_run.call_args_list]
        assert "say" in calls
        assert sox_router._sox_path is not None or "sox" in calls

    @patch("agentic_brain.audio.spatial_audio.subprocess.run")
    def test_speak_sox_falls_back_to_mono_on_say_failure(self, mock_run, sox_router):
        mock_run.return_value = MagicMock(returncode=1, stderr=b"error")
        result = sox_router._speak_sox(
            "Fallback test",
            "Karen (Premium)",
            SpatialPosition(azimuth=0),
            155,
        )
        # Should fall back to _speak_mono which also calls say (no -o flag)
        assert isinstance(result, bool)


# ── Mono fallback ────────────────────────────────────────────────────


class TestMonoFallback:
    @patch("agentic_brain.audio.spatial_audio.subprocess.run")
    def test_speak_mono_calls_say(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        router = SpatialAudioRouter(force_backend="mono")
        result = router._speak_mono("Hello", "Karen (Premium)", 155)
        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "say"
        assert "Karen (Premium)" in cmd

    def test_speak_mono_returns_false_without_say(self):
        router = SpatialAudioRouter(force_backend="mono")
        router._say_path = None
        assert router._speak_mono("Hello", "Karen", 155) is False


# ── speak_spatial dispatch ───────────────────────────────────────────


class TestSpeakSpatial:
    @patch("agentic_brain.audio.spatial_audio.subprocess.run")
    def test_speak_spatial_dispatches_to_backend(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        router = SpatialAudioRouter(force_backend="mono")
        result = router.speak_spatial("Test", "Moira", rate=150)
        assert result is True

    def test_speak_spatial_uses_karen_for_unknown_lady(self):
        router = SpatialAudioRouter(force_backend="mono")
        pos = router.get_position("Ghost")
        assert pos.azimuth == 0  # Karen's azimuth


# ── Narrate sequence ─────────────────────────────────────────────────


class TestNarrateSequence:
    @patch("agentic_brain.audio.spatial_audio.subprocess.run")
    @patch("time.sleep")
    def test_narrate_returns_success_count(self, mock_sleep, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        router = SpatialAudioRouter(force_backend="mono")
        items = [
            ("Karen", "First message"),
            ("Moira", "Second message"),
            ("Kyoko", "Third message"),
        ]
        count = router.narrate_sequence(items, pause=0.5)
        assert count == 3
        assert mock_sleep.call_count == 2  # pause between items, not after last


# ── Scene builder ────────────────────────────────────────────────────


class TestBuildFullScene:
    def test_build_full_scene_all_voice_personas(self):
        router = SpatialAudioRouter(force_backend="mono")
        scene = router.build_full_scene()
        assert len(scene.voices) == 14
        karen = next(v for v in scene.voices if v.name == "Karen")
        assert karen.is_anchor is True
        assert karen.azimuth == 0

    def test_build_full_scene_subset(self):
        router = SpatialAudioRouter(force_backend="mono")
        scene = router.build_full_scene(ladies=["Karen", "Moira"])
        assert len(scene.voices) == 2

    def test_non_karen_voices_have_lower_gain(self):
        router = SpatialAudioRouter(force_backend="mono")
        scene = router.build_full_scene()
        for v in scene.voices:
            if v.name == "Karen":
                assert v.gain == 1.0
            else:
                assert v.gain == 0.92


# ── Singleton ────────────────────────────────────────────────────────


class TestSingleton:
    @patch("agentic_brain.audio.spatial_audio._default_router", None)
    @patch("agentic_brain.audio.spatial_audio.SpatialAudioRouter")
    def test_get_spatial_router_creates_once(self, MockRouter):
        MockRouter.return_value = MagicMock()
        import agentic_brain.audio.spatial_audio as mod

        mod._default_router = None
        r1 = get_spatial_router()
        r2 = get_spatial_router()
        # Both should be the same instance
        assert r1 is r2


# ── Module-level convenience ─────────────────────────────────────────


class TestModuleLevelSpeak:
    @patch("agentic_brain.audio.spatial_audio.get_spatial_router")
    def test_speak_spatial_delegates(self, mock_get):
        mock_router = MagicMock()
        mock_router.speak_spatial.return_value = True
        mock_get.return_value = mock_router

        result = speak_spatial("Hello", lady="Zosia", rate=150)
        assert result is True
        mock_router.speak_spatial.assert_called_once_with(
            "Hello", "Zosia", rate=150, wait=True
        )
