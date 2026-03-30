#!/usr/bin/env python3
"""
Robust audio utilities for voice capture with AirPods Max.

Root-cause analysis (2026-03-30):
  - AirPods Max native sample rate: 24000 Hz
  - sox captures at 24000 Hz and resamples to 16000 Hz for Whisper (this works)
  - "You" / silence transcription = Whisper tiny.en hallucinating on low-energy audio
  - Fix: energy gate + no_speech_threshold + post-TTS delay + hallucination filter

Working sox command:
  sox -q -d -r 24000 -c 1 -b 32 native.wav trim 0 5
  sox native.wav -r 16000 -b 16 final.wav

Whisper fix:
  model.transcribe(path, no_speech_threshold=0.6, avg_logprob_threshold=-1.0)
"""

from __future__ import annotations

import subprocess
import time
import wave
from pathlib import Path

import numpy as np

# ── Constants ─────────────────────────────────────────────────────────────────

# AirPods Max native sample rate (CoreAudio reports 24000 Hz)
AIRPODS_NATIVE_RATE = 24000

# Whisper expects 16000 Hz
WHISPER_TARGET_RATE = 16000

# Minimum RMS amplitude to consider audio as "real speech" (not silence/noise).
# 0.001 = about -60 dBFS.  Silence from AirPods idles around 0.000015 RMS.
ENERGY_THRESHOLD = 0.001

# Whisper no-speech probability threshold.  Segments above this are skipped.
NO_SPEECH_THRESHOLD = 0.6

# Average log-probability below this are likely hallucinations.
AVG_LOGPROB_THRESHOLD = -1.0

# Whisper tiny.en common hallucinations on silence/noise
HALLUCINATION_PHRASES = {
    "you",
    "thank you",
    "thanks",
    "thank you.",
    "thanks.",
    "thanks for watching",
    "thanks for watching.",
    "thank you for watching",
    "bye",
    "bye bye",
    ".",
    "...",
}

# How long to wait after TTS finishes before starting mic capture.
# Bluetooth audio has ~200-400 ms propagation; adding margin avoids Karen's
# voice bleeding into the mic.
POST_TTS_DELAY_S = 0.7


# ── Recording ─────────────────────────────────────────────────────────────────


def record_audio(
    duration: float = 5.0,
    output_path: Path | str | None = None,
    *,
    post_tts_delay: float = POST_TTS_DELAY_S,
) -> Path:
    """
    Record microphone input and return a 16 kHz mono WAV path suitable for
    Whisper.

    Strategy
    --------
    1. Capture at 24000 Hz (AirPods Max native) to avoid CoreAudio resampling
       artefacts during live capture.
    2. Pipe immediately through sox to convert to 16000 Hz, 16-bit signed PCM.
    3. Validate energy; raise ``AudioTooQuietError`` if no real speech detected.

    The two-step capture → resample ensures the live recording stays at the
    device's native clock while Whisper still gets the expected 16 kHz file.
    """

    if post_tts_delay > 0:
        time.sleep(post_tts_delay)

    if output_path is None:
        ts = int(time.time() * 1000)
        output_path = Path.home() / "brain" / "agentic-brain" / f".voice_{ts}.wav"

    output_path = Path(output_path)
    native_path = output_path.with_suffix(".native.wav")

    try:
        # Step 1: capture at native 24 kHz
        _record_native(native_path, duration)

        # Step 2: resample to 16 kHz for Whisper
        _resample_to_whisper(native_path, output_path)
    finally:
        native_path.unlink(missing_ok=True)

    return output_path


def _record_native(path: Path, duration: float) -> None:
    """sox capture at 24000 Hz (AirPods Max native rate)."""
    cmd = [
        "sox",
        "-q",          # suppress progress meter
        "-d",          # default input device
        "-r", str(AIRPODS_NATIVE_RATE),
        "-c", "1",     # mono
        "-b", "32",    # 32-bit capture (CoreAudio float PCM)
        str(path),
        "trim", "0", str(duration),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"sox recording failed: {result.stderr.decode(errors='replace').strip()}"
        )


def _resample_to_whisper(src: Path, dst: Path) -> None:
    """Convert native capture to 16 kHz 16-bit mono WAV."""
    cmd = [
        "sox",
        "-q",
        str(src),
        "-r", str(WHISPER_TARGET_RATE),
        "-b", "16",
        "-e", "signed-integer",
        str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"sox resample failed: {result.stderr.decode(errors='replace').strip()}"
        )


# ── Energy validation ─────────────────────────────────────────────────────────


class AudioTooQuietError(ValueError):
    """Raised when recorded audio contains no detectable speech energy."""


def check_audio_energy(wav_path: Path | str, threshold: float = ENERGY_THRESHOLD) -> float:
    """
    Return RMS amplitude of the WAV file.

    Raises ``AudioTooQuietError`` if the RMS is below *threshold*.
    """
    wav_path = Path(wav_path)
    with wave.open(str(wav_path), "rb") as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        sampwidth = wf.getsampwidth()

    dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(sampwidth, np.int16)
    samples = np.frombuffer(raw, dtype=dtype).astype(np.float32)

    if samples.size == 0:
        raise AudioTooQuietError("WAV file contains no samples.")

    # Normalise to [-1, 1]
    peak = float(np.iinfo(dtype).max)
    samples /= peak

    rms = float(np.sqrt(np.mean(samples ** 2)))

    if rms < threshold:
        raise AudioTooQuietError(
            f"Audio RMS {rms:.6f} is below threshold {threshold:.6f}. "
            "No real speech detected (silence or noise only)."
        )

    return rms


# ── Transcription ─────────────────────────────────────────────────────────────


def transcribe_audio(
    wav_path: Path | str,
    model_name: str = "tiny.en",
    *,
    validate_energy: bool = True,
    energy_threshold: float = ENERGY_THRESHOLD,
) -> str:
    """
    Transcribe *wav_path* using faster-whisper with hallucination guards.

    Guards applied:
    - Energy check before transcription (skip silent recordings)
    - ``no_speech_threshold=0.6`` (discard segments whisper is unsure about)
    - ``avg_logprob`` check per segment (drop likely hallucinations)
    - Phrase blocklist for common Whisper hallucinations

    Returns the transcribed text, or an empty string when no real speech
    is found.
    """
    wav_path = Path(wav_path)

    # Fast-fail on silent recordings
    if validate_energy:
        try:
            check_audio_energy(wav_path, threshold=energy_threshold)
        except AudioTooQuietError:
            return ""

    from faster_whisper import WhisperModel  # lazy import – heavy dependency

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(wav_path),
        no_speech_threshold=NO_SPEECH_THRESHOLD,
        log_prob_threshold=AVG_LOGPROB_THRESHOLD,
        condition_on_previous_text=False,  # avoids context bleeding between turns
    )

    parts: list[str] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        # Drop known hallucinations
        if text.lower().rstrip(".!?,") in HALLUCINATION_PHRASES:
            continue
        # Drop very low-confidence segments
        if seg.avg_logprob < AVG_LOGPROB_THRESHOLD:
            continue
        if seg.no_speech_prob > NO_SPEECH_THRESHOLD:
            continue
        parts.append(text)

    return " ".join(parts).strip()


# ── TTS helpers ───────────────────────────────────────────────────────────────


def speak(text: str, voice: str = "Karen (Premium)", rate: int = 160) -> None:
    """
    Speak *text* via macOS ``say`` and then wait POST_TTS_DELAY_S to let
    Bluetooth audio fully flush before any subsequent mic recording starts.
    """
    subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=True)
    # Brief pause so the Bluetooth audio path is clear before we open the mic.
    time.sleep(POST_TTS_DELAY_S)


# ── Diagnostics ───────────────────────────────────────────────────────────────


def diagnostics() -> dict:
    """
    Return a dict summarising the audio environment.  Handy for Redis reporting.
    """
    import shutil

    info: dict = {
        "sox_available": bool(shutil.which("sox")),
        "ffmpeg_available": bool(shutil.which("ffmpeg")),
        "airpods_native_rate": AIRPODS_NATIVE_RATE,
        "whisper_target_rate": WHISPER_TARGET_RATE,
        "energy_threshold": ENERGY_THRESHOLD,
        "no_speech_threshold": NO_SPEECH_THRESHOLD,
        "post_tts_delay_s": POST_TTS_DELAY_S,
    }

    # Probe default input via system_profiler
    try:
        result = subprocess.run(
            ["system_profiler", "SPAudioDataType"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = result.stdout.splitlines()
        for i, line in enumerate(lines):
            if "Default Input Device: Yes" in line:
                # Device name is usually a few lines before this
                for back in range(1, 6):
                    candidate = lines[i - back].strip()
                    if candidate and not candidate.startswith("Default"):
                        info["default_input_device"] = candidate.rstrip(":")
                        break
                break
        for line in lines:
            if "Current SampleRate" in line and "default_input_sample_rate" not in info:
                info["default_input_sample_rate"] = int(
                    line.split(":")[-1].strip()
                )
    except Exception as exc:
        info["system_profiler_error"] = str(exc)

    return info


if __name__ == "__main__":
    import json

    print("=== Audio diagnostics ===")
    d = diagnostics()
    print(json.dumps(d, indent=2))

    print("\n=== Working sox commands ===")
    print(
        f"  Capture: sox -q -d -r {AIRPODS_NATIVE_RATE} -c 1 -b 32 native.wav trim 0 5"
    )
    print(
        f"  Resample: sox native.wav -r {WHISPER_TARGET_RATE} -b 16 -e signed-integer final.wav"
    )
    print(
        f"  One-shot (good enough): sox -q -d -r 16000 -c 1 -b 16 final.wav trim 0 5"
    )
