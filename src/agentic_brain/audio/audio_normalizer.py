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

"""
Audio Normalizer — Ensure consistent, accessible voice output.

Uses sox for audio processing: volume normalization, silence removal,
and edge trimming so every utterance the user hears is clean and clear.

Usage:
    >>> from agentic_brain.audio.audio_normalizer import AudioNormalizer
    >>> normalizer = AudioNormalizer()
    >>> normalizer.normalize_volume("raw.wav", target_db=-16)
    PosixPath('raw.normalized.wav')
"""

from __future__ import annotations

import logging
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TARGET_DB = -16.0
DEFAULT_SILENCE_THRESHOLD_DB = -40.0
DEFAULT_SILENCE_DURATION = 0.3  # seconds


class AudioNormalizer:
    """Normalizes audio for consistent, accessible playback.

    All heavy lifting is delegated to sox when available; a pure-Python
    fallback handles simple WAV normalization when sox is not installed.

    Parameters:
        sox_path: Explicit path to sox binary (auto-detected if None).
    """

    def __init__(self, sox_path: str | None = None) -> None:
        self.sox_path = sox_path or shutil.which("sox")

    @property
    def sox_available(self) -> bool:
        return self.sox_path is not None and Path(self.sox_path).exists()

    # ── Public API ────────────────────────────────────────────────

    def normalize_volume(
        self,
        audio_path: str | Path,
        target_db: float = DEFAULT_TARGET_DB,
        output_path: str | Path | None = None,
    ) -> Path:
        """Normalize audio volume to *target_db* dBFS.

        Returns the path to the normalized file.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        out = (
            Path(output_path)
            if output_path
            else self._output_path(audio_path, "normalized")
        )

        if self.sox_available:
            self._sox_normalize(audio_path, out, target_db)
        else:
            self._python_normalize(audio_path, out, target_db)

        return out

    def remove_silence(
        self,
        audio_path: str | Path,
        threshold_db: float = DEFAULT_SILENCE_THRESHOLD_DB,
        min_duration: float = DEFAULT_SILENCE_DURATION,
        output_path: str | Path | None = None,
    ) -> Path:
        """Remove silence from audio, keeping speech segments.

        Requires sox. Falls back to trim_edges if sox is unavailable.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        out = (
            Path(output_path)
            if output_path
            else self._output_path(audio_path, "desilenced")
        )

        if not self.sox_available:
            logger.warning("sox not available — falling back to edge trimming")
            return self.trim_edges(audio_path, output_path=out)

        # sox silence: remove leading + trailing silence, then internal gaps
        threshold_pct = f"{self._db_to_percent(threshold_db):.1f}%"
        cmd = [
            self.sox_path,
            str(audio_path),
            str(out),
            # Remove leading silence
            "silence",
            "1",
            str(min_duration),
            threshold_pct,
            # Remove trailing silence
            "reverse",
            "silence",
            "1",
            str(min_duration),
            threshold_pct,
            "reverse",
        ]

        self._run_sox(cmd)
        return out

    def trim_edges(
        self,
        audio_path: str | Path,
        output_path: str | Path | None = None,
    ) -> Path:
        """Trim leading and trailing silence from audio edges.

        Uses sox if available, otherwise a pure-Python WAV fallback.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        out = (
            Path(output_path)
            if output_path
            else self._output_path(audio_path, "trimmed")
        )

        if self.sox_available:
            threshold_pct = f"{self._db_to_percent(DEFAULT_SILENCE_THRESHOLD_DB):.1f}%"
            cmd = [
                self.sox_path,
                str(audio_path),
                str(out),
                "silence",
                "1",
                "0.1",
                threshold_pct,
                "reverse",
                "silence",
                "1",
                "0.1",
                threshold_pct,
                "reverse",
            ]
            self._run_sox(cmd)
        else:
            self._python_trim(audio_path, out)

        return out

    def process_for_playback(
        self,
        audio_path: str | Path,
        target_db: float = DEFAULT_TARGET_DB,
        output_path: str | Path | None = None,
    ) -> Path:
        """Full pipeline: trim → remove silence → normalize.

        Returns the path to the final processed file.
        """
        audio_path = Path(audio_path)
        out = (
            Path(output_path)
            if output_path
            else self._output_path(audio_path, "processed")
        )

        # Chain through intermediate steps
        trimmed = self.trim_edges(audio_path)
        try:
            desilenced = self.remove_silence(trimmed)
            try:
                result = self.normalize_volume(
                    desilenced, target_db=target_db, output_path=out
                )
            finally:
                if desilenced != out and desilenced.exists():
                    desilenced.unlink(missing_ok=True)
        finally:
            if trimmed.exists():
                trimmed.unlink(missing_ok=True)

        return result

    # ── Sox helpers ───────────────────────────────────────────────

    def _sox_normalize(self, src: Path, dst: Path, target_db: float) -> None:
        """Normalize using sox --norm."""
        # sox --norm=target_db input output
        cmd = [
            self.sox_path,
            "--norm=" + str(target_db),
            str(src),
            str(dst),
        ]
        self._run_sox(cmd)

    def _run_sox(self, cmd: list[str]) -> subprocess.CompletedProcess:
        """Run a sox command with error handling."""
        logger.debug("Running: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"sox failed (exit {result.returncode}): {result.stderr.strip()}"
                )
            return result
        except FileNotFoundError:
            raise RuntimeError("sox binary not found. Install with: brew install sox")
        except subprocess.TimeoutExpired:
            raise RuntimeError("sox timed out after 60 seconds")

    # ── Pure-Python fallbacks ─────────────────────────────────────

    def _python_normalize(self, src: Path, dst: Path, target_db: float) -> None:
        """Normalize a WAV file without sox — pure Python."""
        with wave.open(str(src), "rb") as wf:
            params = wf.getparams()
            raw = wf.readframes(params.nframes)

        sampwidth = params.sampwidth
        fmt_map = {1: "b", 2: "h", 4: "i"}
        fmt_char = fmt_map.get(sampwidth)
        if fmt_char is None:
            raise ValueError(f"Unsupported sample width: {sampwidth}")

        n_samples = len(raw) // sampwidth
        samples = list(struct.unpack(f"<{n_samples}{fmt_char}", raw))

        if not samples:
            # Empty file — just copy
            shutil.copy2(src, dst)
            return

        max_val = float(2 ** (sampwidth * 8 - 1))
        peak = max(abs(s) for s in samples) / max_val
        if peak <= 0:
            shutil.copy2(src, dst)
            return

        current_db = 20.0 * math.log10(peak)
        gain_db = target_db - current_db
        gain_linear = 10.0 ** (gain_db / 20.0)

        max_int = int(max_val) - 1
        min_int = -int(max_val)
        normalized = [max(min_int, min(max_int, int(s * gain_linear))) for s in samples]

        out_raw = struct.pack(f"<{n_samples}{fmt_char}", *normalized)
        with wave.open(str(dst), "wb") as wf:
            wf.setparams(params)
            wf.writeframes(out_raw)

    def _python_trim(self, src: Path, dst: Path) -> None:
        """Trim silence edges from a WAV file — pure Python."""
        with wave.open(str(src), "rb") as wf:
            params = wf.getparams()
            raw = wf.readframes(params.nframes)

        sampwidth = params.sampwidth
        n_channels = params.nchannels
        fmt_map = {1: "b", 2: "h", 4: "i"}
        fmt_char = fmt_map.get(sampwidth)
        if fmt_char is None:
            shutil.copy2(src, dst)
            return

        n_samples = len(raw) // sampwidth
        samples = list(struct.unpack(f"<{n_samples}{fmt_char}", raw))

        max_val = float(2 ** (sampwidth * 8 - 1))
        threshold = self._db_to_linear(DEFAULT_SILENCE_THRESHOLD_DB) * max_val

        frame_size = n_channels
        n_frames = n_samples // frame_size

        # Find first non-silent frame
        start = 0
        for i in range(n_frames):
            frame_start = i * frame_size
            frame_vals = samples[frame_start : frame_start + frame_size]
            if any(abs(v) > threshold for v in frame_vals):
                start = i
                break

        # Find last non-silent frame
        end = n_frames
        for i in range(n_frames - 1, -1, -1):
            frame_start = i * frame_size
            frame_vals = samples[frame_start : frame_start + frame_size]
            if any(abs(v) > threshold for v in frame_vals):
                end = i + 1
                break

        trimmed = samples[start * frame_size : end * frame_size]
        if not trimmed:
            trimmed = samples  # Don't produce empty file

        out_raw = struct.pack(f"<{len(trimmed)}{fmt_char}", *trimmed)
        with wave.open(str(dst), "wb") as wf:
            wf.setparams(params._replace(nframes=len(trimmed) // frame_size))
            wf.writeframes(out_raw)

    # ── Utilities ─────────────────────────────────────────────────

    @staticmethod
    def _output_path(src: Path, suffix: str) -> Path:
        """Generate an output path like 'file.normalized.wav'."""
        return src.with_suffix(f".{suffix}{src.suffix}")

    @staticmethod
    def _db_to_percent(db: float) -> float:
        """Convert dBFS to a percentage for sox threshold arguments."""
        return 10.0 ** (db / 20.0) * 100.0

    @staticmethod
    def _db_to_linear(db: float) -> float:
        """Convert dBFS to linear amplitude."""
        return 10.0 ** (db / 20.0)
