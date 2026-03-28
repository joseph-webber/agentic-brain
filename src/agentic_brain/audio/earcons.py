# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Earcon Sound System - Non-speech audio cues for accessibility.

7 earcons provide instant ambient awareness without interrupting speech:
- task_started: Rising ping
- task_done: Falling chime
- error: Low buzz
- new_message: Soft ding
- thinking: Subtle pulse
- agent_deployed: Whoosh
- attention_needed: Double tap
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.io import wavfile

SAMPLE_RATE = 44_100
MAX_DURATION_SECONDS = 0.5
DEFAULT_EARCON_VOLUME = 0.3
EARCON_DIR = Path(__file__).parent / "earcons"


def _seconds_to_samples(duration: float) -> int:
    return max(1, int(SAMPLE_RATE * duration))


def _time_axis(duration: float) -> np.ndarray:
    return np.linspace(0.0, duration, _seconds_to_samples(duration), endpoint=False)


def _normalise(signal: np.ndarray, peak: float = 0.95) -> np.ndarray:
    if signal.size == 0:
        return signal.astype(np.float32)
    max_amplitude = float(np.max(np.abs(signal)))
    if max_amplitude == 0:
        return signal.astype(np.float32)
    return (signal / max_amplitude * peak).astype(np.float32)


def _apply_envelope(
    signal: np.ndarray,
    *,
    attack: float = 0.01,
    release: float = 0.04,
) -> np.ndarray:
    if signal.size == 0:
        return signal.astype(np.float32)

    envelope = np.ones(signal.size, dtype=np.float32)
    attack_samples = min(signal.size, _seconds_to_samples(attack))
    release_samples = min(signal.size, _seconds_to_samples(release))

    if attack_samples > 1:
        envelope[:attack_samples] = np.linspace(0.0, 1.0, attack_samples)
    if release_samples > 1:
        envelope[-release_samples:] *= np.linspace(1.0, 0.0, release_samples)

    return (signal * envelope).astype(np.float32)


def _sine(frequency: float, duration: float, *, phase: float = 0.0) -> np.ndarray:
    t = _time_axis(duration)
    return np.sin((2.0 * np.pi * frequency * t) + phase).astype(np.float32)


def _sweep(start_hz: float, end_hz: float, duration: float) -> np.ndarray:
    frequencies = np.linspace(
        start_hz,
        end_hz,
        _seconds_to_samples(duration),
        endpoint=False,
    )
    phase = 2.0 * np.pi * np.cumsum(frequencies) / SAMPLE_RATE
    return np.sin(phase).astype(np.float32)


def _silence(duration: float) -> np.ndarray:
    return np.zeros(_seconds_to_samples(duration), dtype=np.float32)


def _write_wav(path: Path, signal: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.int16(np.clip(signal, -1.0, 1.0) * 32767)
    wavfile.write(path, SAMPLE_RATE, pcm)


def generate_rising_ping() -> np.ndarray:
    """Rising frequency ping for task_started."""
    duration = 0.2
    tone = (0.82 * _sweep(440.0, 880.0, duration)) + (
        0.18 * _sweep(660.0, 1320.0, duration)
    )
    return _normalise(_apply_envelope(tone, attack=0.005, release=0.06))


def generate_falling_chime() -> np.ndarray:
    """Falling frequency chime for task_done."""
    duration = 0.3
    t = _time_axis(duration)
    base = _sweep(880.0, 440.0, duration)
    shimmer = 0.35 * _sweep(1320.0, 660.0, duration)
    decay = np.exp(-4.2 * t)
    return _normalise(_apply_envelope((base + shimmer) * decay, release=0.08))


def generate_error_buzz() -> np.ndarray:
    """Low buzz for error conditions."""
    duration = 0.3
    t = _time_axis(duration)
    fundamental = _sine(150.0, duration)
    grit = 0.35 * _sine(300.0, duration) + 0.18 * _sine(75.0, duration)
    tremolo = 0.7 + (0.3 * np.sign(np.sin(2.0 * np.pi * 18.0 * t)))
    return _normalise(_apply_envelope((fundamental + grit) * tremolo, release=0.05))


def generate_new_message_ding() -> np.ndarray:
    """Soft ding for inbound messages."""
    duration = 0.15
    t = _time_axis(duration)
    bell = _sine(1000.0, duration) + (0.25 * _sine(2000.0, duration, phase=np.pi / 6))
    decay = np.exp(-9.0 * t)
    return _normalise(_apply_envelope(bell * decay, attack=0.002, release=0.05))


def generate_thinking_pulse() -> np.ndarray:
    """Subtle pulse for background thinking activity."""
    pulse = _apply_envelope(_sine(600.0, 0.08), attack=0.004, release=0.03)
    pulse *= 0.75
    return _normalise(
        np.concatenate(
            [
                pulse,
                _silence(0.05),
                pulse * 0.85,
                _silence(0.05),
                pulse * 0.7,
                _silence(0.09),
            ]
        )
    )


def generate_agent_deployed_whoosh() -> np.ndarray:
    """Whoosh of filtered noise for agent deployment."""
    duration = 0.25
    t = _time_axis(duration)
    rng = np.random.default_rng(7)
    noise = rng.normal(0.0, 1.0, t.size).astype(np.float32)
    sweep_mask = np.linspace(0.15, 1.0, t.size, dtype=np.float32)
    airy = np.sin(2.0 * np.pi * np.cumsum(np.linspace(300.0, 2400.0, t.size)) / SAMPLE_RATE)
    signal = (noise * sweep_mask * 0.65) + (0.25 * airy)
    return _normalise(_apply_envelope(signal, attack=0.01, release=0.08))


def generate_attention_needed_double_tap() -> np.ndarray:
    """Double tap cue for action-required moments."""
    tap = _apply_envelope(_sine(800.0, 0.09), attack=0.003, release=0.035)
    return _normalise(np.concatenate([tap, _silence(0.05), tap * 0.9, _silence(0.07)]))


EARCON_GENERATORS: dict[str, Callable[[], np.ndarray]] = {
    "task_started": generate_rising_ping,
    "task_done": generate_falling_chime,
    "error": generate_error_buzz,
    "new_message": generate_new_message_ding,
    "thinking": generate_thinking_pulse,
    "agent_deployed": generate_agent_deployed_whoosh,
    "attention_needed": generate_attention_needed_double_tap,
}


class EarconPlayer:
    """Play earcon sounds at 30% of speech volume."""

    def __init__(
        self,
        volume: float = DEFAULT_EARCON_VOLUME,
        earcon_dir: Path | None = None,
    ):
        self.volume = max(0.0, min(1.0, volume))
        self.earcon_dir = Path(earcon_dir) if earcon_dir else EARCON_DIR
        self._playing = threading.Lock()
        ensure_earcons_exist(self.earcon_dir)

    def path_for(self, earcon: str) -> Path:
        if earcon not in EARCON_GENERATORS:
            valid = ", ".join(sorted(EARCON_GENERATORS))
            raise ValueError(f"Unknown earcon '{earcon}'. Expected one of: {valid}")
        return self.earcon_dir / f"{earcon}.wav"

    def play(self, earcon: str, blocking: bool = False) -> bool:
        """Play an earcon sound."""
        sound_path = self.path_for(earcon)
        if not sound_path.exists():
            ensure_earcons_exist(self.earcon_dir, force=True)

        if blocking:
            return self._play_file(sound_path)

        thread = threading.Thread(
            target=self._play_file,
            args=(sound_path,),
            name=f"earcon-{earcon}",
            daemon=True,
        )
        thread.start()
        return True

    def _play_file(self, sound_path: Path) -> bool:
        command = self._build_command(sound_path)
        if command is None:
            print("\a", end="", flush=True)
            return True

        try:
            with self._playing:
                completed = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return completed.returncode == 0
        except (FileNotFoundError, OSError):
            return False

    def _build_command(self, sound_path: Path) -> list[str] | None:
        system = platform.system()
        if system == "Darwin" and shutil.which("afplay"):
            return ["afplay", "-v", f"{self.volume:.2f}", str(sound_path)]
        if shutil.which("ffplay"):
            return [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "quiet",
                str(sound_path),
            ]
        if shutil.which("aplay"):
            return ["aplay", "-q", str(sound_path)]
        if shutil.which("paplay"):
            return ["paplay", str(sound_path)]
        return None

    def task_started(self):
        return self.play("task_started")

    def task_done(self):
        return self.play("task_done")

    def error(self):
        return self.play("error")

    def new_message(self):
        return self.play("new_message")

    def thinking(self):
        return self.play("thinking")

    def agent_deployed(self):
        return self.play("agent_deployed")

    def attention_needed(self):
        return self.play("attention_needed")


def ensure_earcons_exist(
    directory: Path | None = None,
    *,
    force: bool = False,
) -> dict[str, Path]:
    """Generate all earcon files if they are missing."""
    target_dir = Path(directory) if directory else EARCON_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    generated: dict[str, Path] = {}
    for name, generator in EARCON_GENERATORS.items():
        path = target_dir / f"{name}.wav"
        if force or not path.exists():
            signal = generator()
            _write_wav(path, signal)
        generated[name] = path
    return generated


def list_earcons(directory: Path | None = None) -> list[Path]:
    """Return the available earcon files."""
    return [
        path
        for _, path in ensure_earcons_exist(directory).items()
    ]
