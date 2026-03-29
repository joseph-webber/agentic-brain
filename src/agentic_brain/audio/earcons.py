# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Earcons - non-speech audio cues for blind accessibility.

Earcons are intentionally short (< 0.5s), quieter than speech, and routed
through the same global speech lock so they never overlap with spoken output.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.io import wavfile

from agentic_brain.audio.sound_themes import DEFAULT_SOUND_THEME, get_sound_theme
from agentic_brain.voice._speech_lock import get_global_lock

SAMPLE_RATE = 44_100
MAX_DURATION_SECONDS = 0.5
DEFAULT_SPEECH_VOLUME = 1.0
DEFAULT_EARCON_VOLUME = 0.22
DEFAULT_BLOCKING_LOCK_TIMEOUT = 1.0
DEFAULT_ASYNC_LOCK_TIMEOUT = 0.05
SOUND_DIR = Path(__file__).parent / "sounds"
EARCON_DIR = SOUND_DIR  # Backward-compatible alias


def _seconds_to_samples(duration: float) -> int:
    return max(1, int(SAMPLE_RATE * duration))


def _time_axis(duration: float) -> np.ndarray:
    return np.linspace(0.0, duration, _seconds_to_samples(duration), endpoint=False)


def _silence(duration: float) -> np.ndarray:
    return np.zeros(_seconds_to_samples(duration), dtype=np.float32)


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


def _harmonic(
    frequencies: tuple[float, ...],
    duration: float,
    weights: tuple[float, ...] | None = None,
) -> np.ndarray:
    if not frequencies:
        return _silence(duration)

    weights = weights or tuple(1.0 for _ in frequencies)
    signal = np.zeros(_seconds_to_samples(duration), dtype=np.float32)
    for frequency, weight in zip(frequencies, weights, strict=False):
        signal += np.float32(weight) * _sine(frequency, duration)
    return signal


def _mix(*signals: np.ndarray) -> np.ndarray:
    if not signals:
        return np.zeros(1, dtype=np.float32)

    max_len = max(signal.size for signal in signals)
    mixed = np.zeros(max_len, dtype=np.float32)
    for signal in signals:
        mixed[: signal.size] += signal.astype(np.float32)
    return mixed


def _sequence(*signals: np.ndarray) -> np.ndarray:
    if not signals:
        return np.zeros(1, dtype=np.float32)
    return np.concatenate([signal.astype(np.float32) for signal in signals]).astype(
        np.float32
    )


def _normalise(signal: np.ndarray, peak: float = 0.92) -> np.ndarray:
    if signal.size == 0:
        return signal.astype(np.float32)

    max_amplitude = float(np.max(np.abs(signal)))
    if max_amplitude == 0:
        return signal.astype(np.float32)
    return (signal / max_amplitude * peak).astype(np.float32)


def _apply_envelope(
    signal: np.ndarray,
    *,
    attack: float = 0.004,
    release: float = 0.05,
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


def _with_decay(signal: np.ndarray, duration: float, rate: float) -> np.ndarray:
    return (signal * np.exp(-rate * _time_axis(duration))).astype(np.float32)


def generate_success() -> np.ndarray:
    first = _with_decay(_harmonic((880.0, 1320.0), 0.09, (1.0, 0.35)), 0.09, 10.0)
    second = _with_decay(_harmonic((1174.66, 1568.0), 0.12, (1.0, 0.28)), 0.12, 8.5)
    return _normalise(
        _sequence(
            _apply_envelope(first, release=0.03),
            _silence(0.025),
            _apply_envelope(second, release=0.05),
        )
    )


def generate_error() -> np.ndarray:
    duration = 0.24
    tone = _mix(
        _sweep(310.0, 190.0, duration),
        0.45 * _sine(155.0, duration),
        0.15 * np.sign(_sine(24.0, duration)),
    )
    return _normalise(_apply_envelope(tone, attack=0.003, release=0.04))


def generate_waiting() -> np.ndarray:
    pulse = _apply_envelope(_harmonic((660.0, 990.0), 0.045, (1.0, 0.18)), release=0.02)
    return _normalise(
        _sequence(
            pulse * 0.95,
            _silence(0.045),
            pulse * 0.82,
            _silence(0.055),
            pulse * 0.7,
        )
    )


def generate_mode_switch() -> np.ndarray:
    duration = 0.21
    signal = _mix(
        0.75 * _sweep(520.0, 980.0, duration),
        0.45 * _sweep(980.0, 620.0, duration),
    )
    return _normalise(_apply_envelope(signal, attack=0.004, release=0.05))


def generate_attention_needed() -> np.ndarray:
    ping = _with_decay(_harmonic((1046.5, 1567.98), 0.07, (1.0, 0.22)), 0.07, 12.0)
    return _normalise(
        _sequence(
            _apply_envelope(ping, release=0.03),
            _silence(0.045),
            _apply_envelope(ping * 0.85, release=0.03),
        )
    )


def generate_speech_start() -> np.ndarray:
    return _normalise(
        _apply_envelope(_sweep(900.0, 1350.0, 0.075), attack=0.002, release=0.025)
    )


def generate_speech_end() -> np.ndarray:
    return _normalise(
        _apply_envelope(_sweep(1350.0, 720.0, 0.085), attack=0.002, release=0.03)
    )


def generate_agent_deployed() -> np.ndarray:
    duration = 0.23
    t = _time_axis(duration)
    rng = np.random.default_rng(7)
    noise = rng.normal(0.0, 1.0, t.size).astype(np.float32)
    noise *= np.linspace(0.1, 1.0, t.size, dtype=np.float32)
    signal = _mix(0.55 * noise, 0.3 * _sweep(240.0, 1800.0, duration))
    return _normalise(_apply_envelope(signal, attack=0.006, release=0.05))


def generate_agent_completed() -> np.ndarray:
    arrival = _with_decay(
        _harmonic((783.99, 1174.66), 0.08, (1.0, 0.2)),
        0.08,
        10.0,
    )
    landing = _with_decay(
        _harmonic((523.25, 783.99), 0.13, (1.0, 0.18)),
        0.13,
        8.0,
    )
    return _normalise(
        _sequence(
            _apply_envelope(arrival, release=0.02),
            _silence(0.02),
            _apply_envelope(landing, release=0.05),
        )
    )


def generate_system_ready() -> np.ndarray:
    notes = [
        _with_decay(_harmonic((523.25, 784.0), 0.075, (1.0, 0.2)), 0.075, 11.0),
        _with_decay(_harmonic((659.25, 988.88), 0.075, (1.0, 0.18)), 0.075, 10.0),
        _with_decay(_harmonic((783.99, 1174.66), 0.12, (1.0, 0.18)), 0.12, 8.5),
    ]
    return _normalise(
        _sequence(
            _apply_envelope(notes[0], release=0.02),
            _silence(0.02),
            _apply_envelope(notes[1], release=0.02),
            _silence(0.02),
            _apply_envelope(notes[2], release=0.05),
        )
    )


@dataclass(frozen=True)
class EarconConfig:
    name: str
    filename: str
    description: str
    duration_seconds: float
    gain: float
    generator: Callable[[], np.ndarray]
    aliases: tuple[str, ...] = ()


EARCONS: dict[str, EarconConfig] = {
    "success": EarconConfig(
        name="success",
        filename="success.wav",
        description="Pleasant completion chime",
        duration_seconds=0.235,
        gain=1.0,
        generator=generate_success,
        aliases=("task_done", "complete"),
    ),
    "error": EarconConfig(
        name="error",
        filename="error.wav",
        description="Distinct warning tone",
        duration_seconds=0.24,
        gain=1.0,
        generator=generate_error,
    ),
    "waiting": EarconConfig(
        name="waiting",
        filename="waiting.wav",
        description="Subtle thinking pulse",
        duration_seconds=0.235,
        gain=0.8,
        generator=generate_waiting,
        aliases=("thinking",),
    ),
    "mode_switch": EarconConfig(
        name="mode_switch",
        filename="mode_switch.wav",
        description="Transition cue between work and life modes",
        duration_seconds=0.21,
        gain=0.9,
        generator=generate_mode_switch,
        aliases=("mode_change",),
    ),
    "attention_needed": EarconConfig(
        name="attention_needed",
        filename="attention_needed.wav",
        description="Notification ping that needs attention",
        duration_seconds=0.185,
        gain=0.92,
        generator=generate_attention_needed,
        aliases=("new_message", "notification"),
    ),
    "speech_start": EarconConfig(
        name="speech_start",
        filename="speech_start.wav",
        description="Subtle onset cue before speech",
        duration_seconds=0.075,
        gain=0.7,
        generator=generate_speech_start,
        aliases=("utterance_start", "task_started"),
    ),
    "speech_end": EarconConfig(
        name="speech_end",
        filename="speech_end.wav",
        description="Subtle offset cue after speech",
        duration_seconds=0.085,
        gain=0.68,
        generator=generate_speech_end,
        aliases=("utterance_done",),
    ),
    "agent_deployed": EarconConfig(
        name="agent_deployed",
        filename="agent_deployed.wav",
        description="Launch whoosh for deployed agents",
        duration_seconds=0.23,
        gain=0.85,
        generator=generate_agent_deployed,
        aliases=("queue_start",),
    ),
    "agent_completed": EarconConfig(
        name="agent_completed",
        filename="agent_completed.wav",
        description="Arrival cue for completed agents",
        duration_seconds=0.23,
        gain=0.9,
        generator=generate_agent_completed,
        aliases=("queue_empty",),
    ),
    "system_ready": EarconConfig(
        name="system_ready",
        filename="system_ready.wav",
        description="Boot complete / ready cue",
        duration_seconds=0.33,
        gain=0.95,
        generator=generate_system_ready,
        aliases=("ready",),
    ),
}

EARCON_ALIASES = {
    alias: config.name for config in EARCONS.values() for alias in config.aliases
}
EARCON_GENERATORS = {name: config.generator for name, config in EARCONS.items()}


def canonical_earcon_name(name: str) -> str:
    normalized = name.strip().lower().replace("-", "_")
    resolved = EARCON_ALIASES.get(normalized, normalized)
    if resolved not in EARCONS:
        valid = ", ".join(sorted(EARCONS))
        raise ValueError(f"Unknown earcon '{name}'. Expected one of: {valid}")
    return resolved


def get_earcon_config(name: str) -> EarconConfig:
    return EARCONS[canonical_earcon_name(name)]


def _write_wav(path: Path, signal: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.int16(np.clip(signal, -1.0, 1.0) * 32767)
    wavfile.write(path, SAMPLE_RATE, pcm)


def _write_with_sox(path: Path, signal: np.ndarray) -> bool:
    sox = shutil.which("sox")
    if not sox:
        return False

    command = [
        sox,
        "-V0",
        "-t",
        "f32",
        "-r",
        str(SAMPLE_RATE),
        "-c",
        "1",
        "-",
        "-t",
        "wav",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            input=signal.astype(np.float32).tobytes(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return False
    return completed.returncode == 0


def _render_audio_file(path: Path, signal: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    signal = np.asarray(signal, dtype=np.float32)
    if not _write_with_sox(path, signal):
        _write_wav(path, signal)


def ensure_earcons_exist(
    directory: Path | None = None,
    *,
    force: bool = False,
) -> dict[str, Path]:
    target_dir = Path(directory) if directory else SOUND_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    generated: dict[str, Path] = {}
    for name, config in EARCONS.items():
        path = target_dir / config.filename
        if force or not path.exists():
            _render_audio_file(path, config.generator())
        generated[name] = path
    return generated


def list_earcons(directory: Path | None = None) -> list[Path]:
    return list(ensure_earcons_exist(directory).values())


@dataclass
class Earcon:
    name: str
    player: EarconPlayer

    @property
    def config(self) -> EarconConfig:
        return get_earcon_config(self.name)

    def play(self, *, blocking: bool = True) -> bool:
        return self.player.play(self.name, blocking=blocking)

    def play_async(self) -> threading.Thread | None:
        return self.player.play_async(self.name)


class EarconPlayer:
    """Play earcons quietly and without overlapping speech."""

    def __init__(
        self,
        volume: float = DEFAULT_EARCON_VOLUME,
        *,
        enabled: bool = True,
        sound_dir: Path | None = None,
        theme: str = DEFAULT_SOUND_THEME,
        blocking_lock_timeout: float = DEFAULT_BLOCKING_LOCK_TIMEOUT,
        async_lock_timeout: float = DEFAULT_ASYNC_LOCK_TIMEOUT,
    ) -> None:
        self.base_volume = max(0.0, min(1.0, volume))
        self.enabled = enabled
        self.sound_dir = Path(sound_dir) if sound_dir else SOUND_DIR
        self.theme = get_sound_theme(theme)
        self.blocking_lock_timeout = max(0.0, blocking_lock_timeout)
        self.async_lock_timeout = max(0.0, async_lock_timeout)
        self._playback_lock = threading.Lock()
        ensure_earcons_exist(self.sound_dir)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def enable(self) -> None:
        self.set_enabled(True)

    def disable(self) -> None:
        self.set_enabled(False)

    def set_theme(self, theme: str) -> None:
        self.theme = get_sound_theme(theme)

    def earcon(self, name: str) -> Earcon:
        return Earcon(name=canonical_earcon_name(name), player=self)

    def path_for(self, name: str) -> Path:
        config = get_earcon_config(name)
        return self.sound_dir / config.filename

    def effective_volume_for(self, name: str) -> float:
        config = get_earcon_config(name)
        return self.theme.apply(self.base_volume * config.gain)

    def play(self, name: str, blocking: bool = False) -> bool:
        if not self.enabled or not self.theme.enabled:
            return False

        canonical_name = canonical_earcon_name(name)
        path = self.path_for(canonical_name)
        if not path.exists():
            ensure_earcons_exist(self.sound_dir, force=True)

        if blocking:
            return self._play_file(
                path,
                volume=self.effective_volume_for(canonical_name),
                wait_for_turn=True,
            )

        return self.play_async(canonical_name) is not None

    def play_async(self, name: str) -> threading.Thread | None:
        if not self.enabled or not self.theme.enabled:
            return None

        canonical_name = canonical_earcon_name(name)
        path = self.path_for(canonical_name)
        if not path.exists():
            ensure_earcons_exist(self.sound_dir, force=True)

        thread = threading.Thread(
            target=self._play_file,
            kwargs={
                "sound_path": path,
                "volume": self.effective_volume_for(canonical_name),
                "wait_for_turn": False,
            },
            name=f"earcon-{canonical_name}",
            daemon=True,
        )
        thread.start()
        return thread

    def _play_file(
        self, sound_path: Path, *, volume: float, wait_for_turn: bool
    ) -> bool:
        command = self._build_command(sound_path, volume)
        if command is None:
            return False

        lock = get_global_lock()
        timeout = (
            self.blocking_lock_timeout if wait_for_turn else self.async_lock_timeout
        )
        if not lock.acquire(timeout=timeout):
            return False

        try:
            with self._playback_lock:
                completed = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return completed.returncode == 0
        except (FileNotFoundError, OSError):
            return False
        finally:
            lock.release()

    def _build_command(self, sound_path: Path, volume: float) -> list[str] | None:
        clamped_volume = max(0.0, min(1.0, volume))
        if shutil.which("afplay"):
            return ["afplay", "-v", f"{clamped_volume:.2f}", str(sound_path)]
        if shutil.which("play"):
            return ["play", "-q", "-v", f"{clamped_volume:.2f}", str(sound_path)]
        if shutil.which("ffplay"):
            return [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "quiet",
                "-af",
                f"volume={clamped_volume:.2f}",
                str(sound_path),
            ]
        return None
