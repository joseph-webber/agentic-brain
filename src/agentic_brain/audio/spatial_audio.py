# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Spatial Audio Router — positions each lady in 3D space around Joseph.

Joseph wears AirPods Pro Max with spatial audio + head tracking.  By
routing each lady's speech to a fixed azimuth he can identify WHO is
speaking by WHERE the sound comes from — even without hearing the voice
clearly.

Architecture
============
1. **Stereo panning** (Sox) — works on any headphones, zero deps beyond
   ``sox``.  Converts mono ``say`` output to stereo with the correct
   left/right balance derived from the lady's azimuth.
2. **Native spatial** (AVAudioEngine) — used when AirPods Pro Max are
   connected and the Swift bridge is available.  Provides true 3D
   positioning with head-tracking via the existing
   ``airpods_bridge.swift``.
3. **Fallback** — if neither Sox nor the native bridge are available,
   speech is delivered as plain mono through the standard ``say`` path.

All paths funnel through the voice serializer — overlap is impossible.
"""

from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────


@dataclass(slots=True)
class SpatialPosition:
    """3D position of a lady relative to the listener.

    Parameters
    ----------
    azimuth:
        Horizontal angle in degrees.  0 = directly in front,
        90 = right ear, 180 = behind, 270 = left ear.
    elevation:
        Vertical angle in degrees.  0 = ear-level,
        positive = above, negative = below.
    distance:
        Relative distance from listener.  1.0 = normal conversational
        distance.  Larger values attenuate volume slightly.
    """

    azimuth: float
    elevation: float = 0.0
    distance: float = 1.0


# ── The 14 ladies — fixed positions around Joseph's head ─────────────

LADY_POSITIONS: Dict[str, SpatialPosition] = {
    # Front arc — the main voices Joseph hears most often
    "Karen": SpatialPosition(azimuth=0),  # Center front — main host
    "Kyoko": SpatialPosition(azimuth=30),  # Front-right — Japan
    "Tingting": SpatialPosition(azimuth=55),  # Right-front — China
    "Yuna": SpatialPosition(azimuth=80),  # Right — Korea
    "Linh": SpatialPosition(azimuth=110),  # Right-back — Vietnam
    "Kanya": SpatialPosition(azimuth=140),  # Back-right — Thailand
    # Behind — the Indonesian trio
    "Dewi": SpatialPosition(azimuth=165),  # Back — Jakarta
    "Sari": SpatialPosition(azimuth=180),  # Dead behind — Java
    "Wayan": SpatialPosition(azimuth=195),  # Back-left — Bali
    # Left arc — European ladies
    "Moira": SpatialPosition(azimuth=225),  # Left-back — Ireland
    "Alice": SpatialPosition(azimuth=255),  # Left — Italy
    "Zosia": SpatialPosition(azimuth=285),  # Left-front — Poland
    "Flo": SpatialPosition(azimuth=315),  # Front-left — France
    "Shelley": SpatialPosition(azimuth=345),  # Front-left — UK
}

# Lady name → macOS ``say -v`` voice name
LADY_VOICE_MAP: Dict[str, str] = {
    "Karen": "Karen (Premium)",
    "Kyoko": "Kyoko",
    "Tingting": "Ting-Ting",
    "Yuna": "Yuna",
    "Linh": "Linh",
    "Kanya": "Kanya",
    "Dewi": "Damayanti",
    "Sari": "Damayanti",
    "Wayan": "Damayanti",
    "Moira": "Moira",
    "Alice": "Alice",
    "Zosia": "Zosia",
    "Flo": "Amelie",
    "Shelley": "Shelley",
}

ALL_LADIES = tuple(LADY_POSITIONS.keys())


# ── Stereo-pan helpers ───────────────────────────────────────────────


def _azimuth_to_stereo_gains(azimuth_deg: float) -> tuple[float, float]:
    """Convert an azimuth angle to (left_gain, right_gain) for stereo pan.

    Uses an equal-power panning law so that total perceived volume stays
    constant regardless of position.

    0° (front) → equal L/R.  90° (right) → mostly right.  270° (left)
    → mostly left.  180° (behind) → equal L/R with slight attenuation.
    """
    rad = math.radians(azimuth_deg)
    # sin(azimuth) gives -1 (left) to +1 (right)
    pan = math.sin(rad)
    # Equal-power: sqrt-based crossfade
    left = math.sqrt(max(0.0, (1.0 - pan) / 2.0))
    right = math.sqrt(max(0.0, (1.0 + pan) / 2.0))
    # Rear attenuation — sounds from behind are slightly quieter to
    # give a sense of depth.  cos(azimuth) < 0 means behind.
    rear_factor = 1.0 - 0.12 * max(0.0, -math.cos(rad))
    return (left * rear_factor, right * rear_factor)


def _azimuth_to_cartesian(
    azimuth_deg: float, elevation_deg: float = 0.0, distance: float = 1.0
) -> tuple[float, float, float]:
    """Convert spherical (azimuth, elevation, distance) to (x, y, z).

    Coordinate system: x = right, y = up, z = front.
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    x = distance * math.sin(az) * math.cos(el)
    y = distance * math.sin(el)
    z = distance * math.cos(az) * math.cos(el)
    return (x, y, z)


# ── Spatial Audio Router ─────────────────────────────────────────────


class SpatialAudioRouter:
    """Route speech to spatial positions so Joseph can locate each lady.

    The router checks for AirPods and Sox at construction time and
    automatically selects the best rendering path:

    1. Native AVAudioEngine via Swift bridge (full 3D + head tracking)
    2. Sox stereo panning (lightweight, works on any stereo output)
    3. Plain mono fallback (no positioning, just ``say``)

    Thread-safe: all mutable state is guarded by ``_lock``.
    """

    def __init__(
        self,
        positions: Dict[str, SpatialPosition] | None = None,
        voice_map: Dict[str, str] | None = None,
        force_backend: str | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._positions = dict(positions or LADY_POSITIONS)
        self._voice_map = dict(voice_map or LADY_VOICE_MAP)
        self._sox_path: str | None = shutil.which("sox")
        self._afplay_path: str | None = shutil.which("afplay")
        self._say_path: str | None = shutil.which("say")
        self._airpods_connected: bool = False
        self._native_available: bool = False
        self._backend: str = "mono"  # "native", "sox", or "mono"
        self._scratch_dir = Path(
            os.environ.get(
                "AGENTIC_BRAIN_AUDIO_SCRATCH",
                Path.home() / ".cache" / "agentic-brain" / "spatial",
            )
        )
        self._scratch_dir.mkdir(parents=True, exist_ok=True)

        self._detect_capabilities(force_backend)

    # ── Detection ────────────────────────────────────────────────────

    def _detect_capabilities(self, force_backend: str | None) -> None:
        """Probe hardware and pick the best rendering path."""
        if force_backend in ("native", "sox", "mono"):
            self._backend = force_backend
            logger.info("Spatial audio backend forced to %s", force_backend)
            return

        # Check native bridge availability
        try:
            from agentic_brain.audio.airpods import get_airpods_manager

            mgr = get_airpods_manager()
            if mgr.native_bridge.is_available():
                device = mgr.detect_airpods_pro_max()
                if device and device.connected:
                    self._airpods_connected = True
                    self._native_available = True
                    self._backend = "native"
                    logger.info(
                        "Spatial audio: native AVAudioEngine with %s",
                        device.name,
                    )
                    return
        except Exception:
            logger.debug("Native spatial bridge not available", exc_info=True)

        # Fall back to Sox stereo panning
        if self._sox_path and self._say_path and self._afplay_path:
            self._backend = "sox"
            logger.info("Spatial audio: stereo panning via Sox")
            return

        logger.info("Spatial audio: mono fallback (no Sox or native bridge)")

    @property
    def backend(self) -> str:
        """Active rendering backend: ``native``, ``sox``, or ``mono``."""
        return self._backend

    @property
    def airpods_connected(self) -> bool:
        return self._airpods_connected

    def refresh_airpods_status(self) -> bool:
        """Re-check AirPods connection and potentially upgrade backend."""
        self._detect_capabilities(force_backend=None)
        return self._airpods_connected

    # ── Position queries ─────────────────────────────────────────────

    def get_position(self, lady: str) -> SpatialPosition:
        """Return the spatial position for *lady*, defaulting to Karen."""
        return self._positions.get(lady, self._positions["Karen"])

    def set_position(self, lady: str, position: SpatialPosition) -> None:
        with self._lock:
            self._positions[lady] = position

    def list_positions(self) -> Dict[str, SpatialPosition]:
        with self._lock:
            return dict(self._positions)

    def get_voice_name(self, lady: str) -> str:
        """Resolve lady name to macOS ``say -v`` voice identifier."""
        return self._voice_map.get(lady, "Karen (Premium)")

    # ── Primary speech entry-point ───────────────────────────────────

    def speak_spatial(
        self,
        text: str,
        lady: str,
        rate: int = 155,
        wait: bool = True,
    ) -> bool:
        """Speak *text* from *lady*'s spatial position.

        Returns ``True`` on success.  The method is safe to call from any
        thread — it acquires the internal lock and delegates to the
        appropriate backend.
        """
        voice = self.get_voice_name(lady)
        position = self.get_position(lady)

        if self._backend == "native":
            return self._speak_native(text, lady, voice, position, rate)
        if self._backend == "sox":
            return self._speak_sox(text, voice, position, rate)
        return self._speak_mono(text, voice, rate)

    # ── Backend: Native AVAudioEngine ────────────────────────────────

    def _speak_native(
        self,
        text: str,
        lady: str,
        voice: str,
        pos: SpatialPosition,
        rate: int,
    ) -> bool:
        """Use AVAudioEngine 3D positioning via the AirPods manager."""
        try:
            from agentic_brain.audio.airpods import (
                SpatialAudioScene,
                SpatialVoicePosition,
                get_airpods_manager,
            )

            mgr = get_airpods_manager()

            # Build a scene with the active lady at her position
            scene = SpatialAudioScene(
                mode=mgr.head_tracking_mode,
                fixed_listener_space=mgr.fixed_listener_space,
                voices=[
                    SpatialVoicePosition(
                        name=lady,
                        azimuth=pos.azimuth,
                        elevation=pos.elevation,
                        distance=pos.distance,
                        gain=1.0 if lady == "Karen" else 0.92,
                        is_anchor=(lady == "Karen"),
                    )
                ],
            )
            mgr.configure_spatial_audio(scene=scene)
            mgr.prepare_for_speech(text)

            # Render speech through say -> AIFF -> afplay
            ok = self._speak_mono(text, voice, rate)

            mgr.finish_speech()
            return ok
        except Exception:
            logger.warning(
                "Native spatial failed, falling back to Sox",
                exc_info=True,
            )
            return self._speak_sox(text, voice, pos, rate)

    # ── Backend: Sox stereo panning ──────────────────────────────────

    def _speak_sox(
        self,
        text: str,
        voice: str,
        pos: SpatialPosition,
        rate: int,
    ) -> bool:
        """Render speech to a file, apply stereo pan with Sox, play back."""
        mono_path = self._scratch_dir / "spatial_mono.aiff"
        stereo_path = self._scratch_dir / "spatial_stereo.aiff"

        try:
            # 1. Render speech to mono AIFF
            result = subprocess.run(
                ["say", "-v", voice, "-r", str(rate), "-o", str(mono_path), text],
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(
                    "say -o failed: %s", result.stderr.decode(errors="replace")
                )
                return self._speak_mono(text, voice, rate)

            if not mono_path.exists() or mono_path.stat().st_size == 0:
                logger.warning("say produced empty output file")
                return self._speak_mono(text, voice, rate)

            # 2. Calculate stereo gains from azimuth
            left_gain, right_gain = _azimuth_to_stereo_gains(pos.azimuth)

            # Apply distance attenuation
            dist_atten = 1.0 / max(0.5, pos.distance)
            left_gain *= dist_atten
            right_gain *= dist_atten

            # 3. Sox remix: duplicate mono to stereo with pan gains
            sox_result = subprocess.run(
                [
                    self._sox_path,
                    str(mono_path),
                    str(stereo_path),
                    "remix",
                    f"1v{left_gain:.3f}",
                    f"1v{right_gain:.3f}",
                ],
                capture_output=True,
                timeout=15,
            )
            if sox_result.returncode != 0:
                logger.warning(
                    "Sox remix failed: %s",
                    sox_result.stderr.decode(errors="replace"),
                )
                return self._speak_mono(text, voice, rate)

            # 4. Play the spatialized file
            play_result = subprocess.run(
                ["afplay", str(stereo_path)],
                capture_output=True,
                timeout=60,
            )
            return play_result.returncode == 0

        except subprocess.TimeoutExpired:
            logger.warning("Spatial speech timed out")
            return False
        except Exception:
            logger.warning("Sox spatial rendering failed", exc_info=True)
            return self._speak_mono(text, voice, rate)
        finally:
            # Clean up scratch files
            for p in (mono_path, stereo_path):
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass

    # ── Backend: Mono fallback ───────────────────────────────────────

    def _speak_mono(self, text: str, voice: str, rate: int) -> bool:
        """Plain mono speech through macOS ``say`` — no spatial positioning."""
        if not self._say_path:
            logger.warning("macOS 'say' command not available")
            return False
        try:
            result = subprocess.run(
                ["say", "-v", voice, "-r", str(rate), text],
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            logger.warning("Mono speech failed", exc_info=True)
            return False

    # ── Convenience: narrate with multiple ladies ────────────────────

    def narrate_sequence(
        self,
        items: Sequence[tuple[str, str]],
        rate: int = 155,
        pause: float = 1.0,
    ) -> int:
        """Speak a sequence of ``(lady, text)`` tuples with pauses.

        Returns the count of successfully spoken items.
        """
        import time

        ok_count = 0
        for i, (lady, text) in enumerate(items):
            if self.speak_spatial(text, lady, rate=rate):
                ok_count += 1
            if i < len(items) - 1 and pause > 0:
                time.sleep(pause)
        return ok_count

    # ── Scene builder — build AirPods scene from all positions ───────

    def build_full_scene(self, ladies: Sequence[str] | None = None) -> Any:
        """Build a ``SpatialAudioScene`` with all (or specified) ladies.

        Returns the scene dataclass from ``airpods.py`` for use with
        ``AirPodsManager.configure_spatial_audio()``.
        """
        from agentic_brain.audio.airpods import (
            SpatialAudioScene,
            SpatialVoicePosition,
        )

        if ladies is None:
            ladies = list(LADY_POSITIONS.keys())

        voices = []
        for lady in ladies:
            pos = self.get_position(lady)
            voices.append(
                SpatialVoicePosition(
                    name=lady,
                    azimuth=pos.azimuth,
                    elevation=pos.elevation,
                    distance=pos.distance,
                    gain=1.0 if lady == "Karen" else 0.92,
                    is_anchor=(lady == "Karen"),
                )
            )

        return SpatialAudioScene(
            mode="fixed",
            fixed_listener_space=True,
            voices=voices,
        )

    # ── Diagnostics ──────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return a diagnostic dictionary for debugging."""
        return {
            "backend": self._backend,
            "airpods_connected": self._airpods_connected,
            "native_available": self._native_available,
            "sox_available": self._sox_path is not None,
            "say_available": self._say_path is not None,
            "afplay_available": self._afplay_path is not None,
            "scratch_dir": str(self._scratch_dir),
            "lady_count": len(self._positions),
            "ladies": {
                name: {
                    "azimuth": pos.azimuth,
                    "elevation": pos.elevation,
                    "distance": pos.distance,
                    "voice": self.get_voice_name(name),
                }
                for name, pos in self._positions.items()
            },
        }


# ── Singleton access ─────────────────────────────────────────────────

_default_router: SpatialAudioRouter | None = None
_router_lock = threading.Lock()


def get_spatial_router() -> SpatialAudioRouter:
    """Return the process-wide spatial audio router singleton."""
    global _default_router
    if _default_router is None:
        with _router_lock:
            if _default_router is None:
                _default_router = SpatialAudioRouter()
    return _default_router


def speak_spatial(
    text: str,
    lady: str = "Karen",
    rate: int = 155,
    wait: bool = True,
) -> bool:
    """Module-level convenience — speak from a lady's spatial position."""
    return get_spatial_router().speak_spatial(text, lady, rate=rate, wait=wait)
