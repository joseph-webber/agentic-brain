"""
Stereo panning for lady voices.

Uses Sox to pan voices left/right based on lady position.
Works with any headphones and does not require spatial audio support.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Lady pan positions: -1.0 (full left) to +1.0 (full right)
LADY_PAN_POSITIONS = {
    # Center - main voice
    "Karen": 0.0,
    # Front-right quadrant (Asian ladies for travel)
    "Kyoko": 0.25,
    "Tingting": 0.40,
    "Yuna": 0.55,
    "Linh": 0.70,
    "Kanya": 0.80,
    # Back (Indonesian ladies)
    "Dewi": 0.90,
    "Sari": -0.90,
    "Wayan": -0.80,
    # Left quadrant (European ladies)
    "Moira": -0.45,
    "Alice": -0.60,
    "Zosia": -0.75,
    "Flo": -0.30,
    "Shelley": -0.15,
}

_LADY_ALIASES = {
    "karen": "Karen",
    "kyoko": "Kyoko",
    "tingting": "Tingting",
    "ting-ting": "Tingting",
    "yuna": "Yuna",
    "linh": "Linh",
    "kanya": "Kanya",
    "dewi": "Dewi",
    "sari": "Sari",
    "wayan": "Wayan",
    "moira": "Moira",
    "alice": "Alice",
    "zosia": "Zosia",
    "flo": "Flo",
    "amelie": "Flo",
    "shelley": "Shelley",
}


def resolve_lady_name(lady_or_voice: str) -> str:
    """Resolve a lady/voice name to the canonical pan identity."""
    normalized = (lady_or_voice or "").strip()
    normalized = normalized.replace(" (Premium)", "")
    normalized = normalized.replace("_", " ")
    key = normalized.lower()
    return _LADY_ALIASES.get(key, normalized or "Karen")


def get_pan_position(lady_or_voice: str) -> float:
    """Return the configured pan position for a lady or voice."""
    return LADY_PAN_POSITIONS.get(resolve_lady_name(lady_or_voice), 0.0)


@dataclass(frozen=True)
class PannedAudio:
    path: Path
    lady: str
    pan: float


class StereoPanner:
    """Apply stereo panning to speech audio."""

    def __init__(
        self,
        sox_path: Optional[Path] = None,
        temp_dir: Optional[Path] = None,
    ) -> None:
        self._sox_path = sox_path or self._find_sox()
        self._temp_dir = temp_dir or self._default_temp_dir()
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    def _default_temp_dir(self) -> Path:
        configured = os.getenv("AGENTIC_BRAIN_STEREO_PAN_DIR", "").strip()
        if configured:
            return Path(configured).expanduser()
        repo_root = Path(__file__).resolve().parents[3]
        return repo_root / ".cache" / "stereo_pan"

    def _find_sox(self) -> Optional[Path]:
        """Find the sox binary."""
        which_path = shutil.which("sox")
        if which_path:
            return Path(which_path)

        paths = (
            Path("/opt/homebrew/bin/sox"),
            Path("/usr/local/bin/sox"),
            Path("/usr/bin/sox"),
        )
        for path in paths:
            if path.exists():
                return path
        return None

    @property
    def temp_dir(self) -> Path:
        return self._temp_dir

    def is_available(self) -> bool:
        """Check if sox is available."""
        return self._sox_path is not None

    def pan_audio(self, input_path: Path, lady: str) -> Path:
        """Apply stereo pan to a mono audio file."""
        if not self._sox_path:
            return input_path

        pan = get_pan_position(lady)
        left_vol = (1 - pan) / 2
        right_vol = (1 + pan) / 2
        output_path = self._temp_dir / (
            f"panned_{resolve_lady_name(lady)}_{input_path.stem}_{uuid.uuid4().hex}.aiff"
        )

        subprocess.run(
            [
                str(self._sox_path),
                str(input_path),
                str(output_path),
                "remix",
                f"1v{left_vol:.2f}",
                f"1v{right_vol:.2f}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return output_path

    def render_panned_speech(
        self,
        text: str,
        lady: str,
        voice: str,
        rate: int = 155,
    ) -> PannedAudio:
        """Generate speech audio, then pan it for the target lady."""
        lady_name = resolve_lady_name(lady or voice)
        mono_path = self._temp_dir / f"mono_{lady_name}_{uuid.uuid4().hex}.aiff"

        say_cmd = ["say", "-r", str(rate), "-o", str(mono_path)]
        normalized_voice = (voice or "").strip().lower()
        if normalized_voice not in {"", "auto", "default", "system"}:
            say_cmd[1:1] = ["-v", voice]
        say_cmd.append(text)

        subprocess.run(
            say_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            panned_path = self.pan_audio(mono_path, lady_name)
            return PannedAudio(
                path=panned_path,
                lady=lady_name,
                pan=get_pan_position(lady_name),
            )
        finally:
            mono_path.unlink(missing_ok=True)

    def cleanup_audio(self, path: Path) -> None:
        """Delete generated audio if it lives in the configured pan cache."""
        try:
            resolved = path.resolve()
            if self._temp_dir.resolve() in resolved.parents:
                path.unlink(missing_ok=True)
        except FileNotFoundError:
            return

    def speak_panned(self, text: str, lady: str, voice: str, rate: int = 155) -> bool:
        """Speak text with stereo panning for the lady."""
        panned_audio = self.render_panned_speech(
            text=text, lady=lady, voice=voice, rate=rate
        )
        try:
            completed = subprocess.run(
                ["afplay", str(panned_audio.path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return completed.returncode == 0
        finally:
            self.cleanup_audio(panned_audio.path)


_panner: Optional[StereoPanner] = None


def get_stereo_panner() -> StereoPanner:
    global _panner
    if _panner is None:
        _panner = StereoPanner()
    return _panner


def speak_with_pan(text: str, lady: str, voice: str, rate: int = 155) -> bool:
    """Speak text with the lady's stereo position."""
    return get_stereo_panner().speak_panned(text, lady, voice, rate)
