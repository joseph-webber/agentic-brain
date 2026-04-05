#!/usr/bin/env python3
"""
voice.py — Unified voice launcher.

Usage:
    python voice.py              → standalone mode (Claude API)
    python voice.py --copilot    → GitHub Copilot mode
    python voice.py --once       → single turn then exit
    python voice.py --text "hi"  → skip mic, use text directly

Auto-detects AirPods Max. Uses energy gate + hallucination filter.
No setup needed beyond .env with API keys.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import uuid
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
BRAIN_ROOT = SCRIPT_DIR.parent
RUNTIME_DIR = SCRIPT_DIR / ".voice-runtime"
RECORDINGS_DIR = RUNTIME_DIR / "recordings"

# .env files searched in order (brain root first, then local)
_ENV_FILES = (BRAIN_ROOT / ".env", SCRIPT_DIR / ".env")


def _load_env() -> None:
    """Load .env without requiring python-dotenv (graceful fallback)."""
    for env_file in _ENV_FILES:
        if not env_file.exists():
            continue
        try:
            with env_file.open() as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    os.environ.setdefault(key, val)
        except OSError:
            pass


_load_env()

# ── Constants ──────────────────────────────────────────────────────────────────

AIRPODS_NATIVE_RATE = 24_000   # CoreAudio reports 24 kHz for AirPods Max
WHISPER_TARGET_RATE = 16_000   # Whisper expects 16 kHz
ENERGY_THRESHOLD = 0.001       # RMS below this = silence (skip transcription)
NO_SPEECH_THRESHOLD = 0.6      # Whisper no_speech_prob above this = discard
AVG_LOGPROB_THRESHOLD = -1.0   # Log-prob below this = likely hallucination
POST_TTS_DELAY = 0.7           # Seconds to wait after TTS before mic opens

HALLUCINATIONS = {
    "you", "thank you", "thanks", "thank you.", "thanks.",
    "thanks for watching", "thanks for watching.", "thank you for watching",
    "bye", "bye bye", ".", "...",
}

STOP_PHRASES = {
    "stop", "stop listening", "goodbye", "exit", "quit",
    "thanks goodbye", "stop voice", "turn off",
}

# macOS system sounds used for state announcements
_SOUNDS = {
    "ready":    "/System/Library/Sounds/Tink.aiff",
    "thinking": "/System/Library/Sounds/Pop.aiff",
    "done":     "/System/Library/Sounds/Glass.aiff",
    "error":    "/System/Library/Sounds/Basso.aiff",
    "start":    "/System/Library/Sounds/Hero.aiff",
    "bye":      "/System/Library/Sounds/Funk.aiff",
}


# ── Config ─────────────────────────────────────────────────────────────────────

@dataclass
class Config:
    """Runtime configuration — sensible defaults, all overridable via env/flags."""

    mode: str = "standalone"           # "standalone" | "copilot"
    voice: str = field(
        default_factory=lambda: os.getenv("VOICE_TTS_VOICE", "Karen (Premium)")
    )
    rate: int = field(
        default_factory=lambda: int(os.getenv("VOICE_TTS_RATE", "160"))
    )
    record_seconds: int = field(
        default_factory=lambda: int(os.getenv("VOICE_RECORD_SECONDS", "6"))
    )
    whisper_model: str = field(
        default_factory=lambda: os.getenv("WHISPER_MODEL", "tiny.en")
    )
    claude_model: str = field(
        default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("VOICE_MAX_TOKENS", "220"))
    )
    repo_path: Path = field(
        default_factory=lambda: Path(os.getenv("VOICE_COPILOT_REPO", str(SCRIPT_DIR)))
    )
    once: bool = False
    say_enabled: bool = True
    keep_recordings: bool = False


# ── Audio helpers ──────────────────────────────────────────────────────────────

def _play_sound(name: str) -> None:
    path = _SOUNDS.get(name)
    if path:
        subprocess.run(["afplay", path], check=False, capture_output=True)


def speak(text: str, voice: str = "Karen (Premium)", rate: int = 160) -> None:
    """Speak *text* via macOS say, then pause so mic doesn't catch TTS bleed."""
    if not text.strip():
        return
    subprocess.run(
        ["say", "-v", voice, "-r", str(rate), text],
        check=False,
        capture_output=True,
    )
    time.sleep(POST_TTS_DELAY)


def detect_airpods() -> bool:
    """Return True if AirPods Max are the default input device."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPAudioDataType"],
            capture_output=True, text=True, timeout=8,
        )
        lines = result.stdout.splitlines()
        airpods_section = False
        for line in lines:
            if "AirPods" in line:
                airpods_section = True
            if airpods_section and "Default Input Device: Yes" in line:
                return True
        return False
    except Exception:
        return False


def _record_native(path: Path, duration: float) -> None:
    """Capture at AirPods Max native 24 kHz (avoids CoreAudio resampling noise)."""
    cmd = [
        "sox", "-q",
        "-d",                          # default input device
        "-r", str(AIRPODS_NATIVE_RATE),
        "-c", "1",
        "-b", "32",                    # 32-bit float PCM as CoreAudio delivers
        str(path),
        "trim", "0", str(duration),
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"sox record failed: {r.stderr.decode(errors='replace').strip()}"
        )


def _record_generic(path: Path, duration: float) -> None:
    """Fallback recording for non-AirPods devices (direct 16 kHz capture)."""
    cmd = [
        "sox", "-q", "-d",
        "-r", "16000", "-c", "1", "-b", "16",
        str(path),
        "trim", "0", str(duration),
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"sox record failed: {r.stderr.decode(errors='replace').strip()}"
        )


def _resample(src: Path, dst: Path) -> None:
    """Convert native capture to 16 kHz 16-bit mono for Whisper."""
    cmd = [
        "sox", "-q", str(src),
        "-r", str(WHISPER_TARGET_RATE), "-b", "16", "-e", "signed-integer",
        str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"sox resample failed: {r.stderr.decode(errors='replace').strip()}"
        )


def record_audio(duration: float, *, airpods: bool = False) -> Path:
    """
    Record microphone input, returning a 16 kHz WAV path for Whisper.

    AirPods Max path: capture at 24 kHz → resample to 16 kHz (two-step).
    Other devices: capture directly at 16 kHz (one-step).
    """
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:6]
    out = RECORDINGS_DIR / f"{ts}-{uid}.wav"

    if airpods:
        native = out.with_suffix(".native.wav")
        try:
            _record_native(native, duration)
            _resample(native, out)
        finally:
            native.unlink(missing_ok=True)
    else:
        _record_generic(out, duration)

    return out


def check_energy(wav_path: Path) -> float:
    """Return RMS energy; raise RuntimeError if below silence threshold."""
    import numpy as np
    with wave.open(str(wav_path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        sw = wf.getsampwidth()
    dtype = {1: "int8", 2: "int16", 4: "int32"}.get(sw, "int16")
    samples = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if samples.size == 0:
        raise RuntimeError("Empty WAV file.")
    peak = float(np.iinfo(np.dtype(dtype)).max)
    rms = float(np.sqrt(np.mean((samples / peak) ** 2)))
    if rms < ENERGY_THRESHOLD:
        raise RuntimeError(
            f"Silence detected (RMS {rms:.6f} < {ENERGY_THRESHOLD}). "
            "Nothing was spoken."
        )
    return rms


def transcribe_local(wav_path: Path, model_name: str = "tiny.en") -> str:
    """
    Transcribe with faster-whisper (local, free, offline).
    Applies no_speech / logprob guards and strips hallucinations.
    """
    from faster_whisper import WhisperModel  # lazy — heavy import

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(wav_path),
        no_speech_threshold=NO_SPEECH_THRESHOLD,
        log_prob_threshold=AVG_LOGPROB_THRESHOLD,
        condition_on_previous_text=False,
    )
    parts: list[str] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        if text.lower().rstrip(".!?,") in HALLUCINATIONS:
            continue
        if seg.avg_logprob < AVG_LOGPROB_THRESHOLD:
            continue
        if seg.no_speech_prob > NO_SPEECH_THRESHOLD:
            continue
        parts.append(text)
    return " ".join(parts).strip()


def transcribe_openai(wav_path: Path) -> str:
    """Fallback: transcribe via OpenAI Whisper API."""
    import requests
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set and faster-whisper unavailable.")
    with wav_path.open("rb") as fh:
        r = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": "gpt-4o-mini-transcribe"},
            files={"file": (wav_path.name, fh, "audio/wav")},
            timeout=60,
        )
    r.raise_for_status()
    return str(r.json().get("text", "")).strip()


def transcribe(wav_path: Path, model_name: str = "tiny.en") -> str:
    """
    Transcribe *wav_path*: energy-gate → faster-whisper → OpenAI fallback.
    Returns empty string when nothing was spoken (not an error).
    """
    try:
        check_energy(wav_path)
    except RuntimeError:
        return ""  # silence — caller will loop

    try:
        return transcribe_local(wav_path, model_name)
    except Exception:
        # faster-whisper not loaded or failed — try OpenAI
        return transcribe_openai(wav_path)


# ── LLM backends ──────────────────────────────────────────────────────────────

_CLAUDE_HISTORY: list[dict] = []   # module-level so it persists across turns

_CLAUDE_SYSTEM = (
    "You are Karen, a warm, concise voice assistant for a user with visual impairments. "
    "Respond in plain spoken English, normally one to four short sentences. "
    "No markdown, no bullet points, no emoji. Be direct and helpful."
)


def generate_claude(text: str, cfg: Config) -> str:
    """Call Anthropic Claude and return plain-text response."""
    import requests as _req

    api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "CLAUDE_API_KEY not set. Add it to ~/brain/.env to use standalone mode."
        )

    _CLAUDE_HISTORY.append({"role": "user", "content": text})
    messages = _CLAUDE_HISTORY[-10:]   # keep last 5 turns (10 messages)

    r = _req.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": cfg.claude_model,
            "max_tokens": cfg.max_tokens,
            "system": _CLAUDE_SYSTEM,
            "messages": messages,
        },
        timeout=90,
    )
    r.raise_for_status()
    payload = r.json()

    parts = [
        item.get("text", "").strip()
        for item in payload.get("content", [])
        if item.get("type") == "text"
    ]
    answer = "\n".join(p for p in parts if p).strip()
    if not answer:
        raise RuntimeError("Claude returned an empty response.")

    _CLAUDE_HISTORY.append({"role": "assistant", "content": answer})
    return answer


def generate_copilot(text: str, cfg: Config) -> str:
    """Send text to GitHub Copilot CLI and return its response."""
    prompt = (
        f"{text}\n\n"
        "Respond in plain text suitable for speech output to a blind user. "
        "Keep formatting minimal — no markdown tables, no bullet points, "
        "no emoji. Speak naturally."
    )
    cmd = [
        "gh", "copilot", "-p", prompt,
        "-s", "--screen-reader", "--allow-all-tools",
        "--no-ask-user",
        "--add-dir", str(cfg.repo_path),
    ]
    result = subprocess.run(
        cmd, cwd=cfg.repo_path,
        capture_output=True, text=True, check=False,
    )
    output = (result.stdout or "").strip()
    if result.returncode != 0 and not output:
        raise RuntimeError(
            (result.stderr or "Copilot CLI failed with no output.").strip()
        )
    if not output:
        raise RuntimeError("Copilot returned no output.")
    return output


def generate_response(text: str, cfg: Config) -> str:
    """Route to the correct LLM based on mode."""
    if cfg.mode == "copilot":
        return generate_copilot(text, cfg)
    return generate_claude(text, cfg)


# ── Main loop ──────────────────────────────────────────────────────────────────

class VoiceLauncher:
    """
    Single-turn and continuous voice loop.

    States announced verbally and via sound:
        ready     → Tink tone  → "Listening…"
        thinking  → Pop tone
        speaking  → response played back
        error     → Basso tone → error message spoken
        stopping  → Funk tone  → goodbye message
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.airpods = detect_airpods()
        self.session_id = uuid.uuid4().hex[:8]
        self._running = True

    # ── Accessibility helpers ─────────────────────────────────────────────────

    def say(self, text: str) -> None:
        if self.cfg.say_enabled:
            speak(text, voice=self.cfg.voice, rate=self.cfg.rate)

    def announce(self, state: str, detail: str = "") -> None:
        """Print state to stdout and speak it if verbose."""
        label = f"[{state.upper()}]"
        line = f"{label} {detail}".strip() if detail else label
        print(line, flush=True)

    # ── One listen-transcribe-respond turn ────────────────────────────────────

    def _listen(self, text_override: Optional[str] = None) -> str:
        """Record mic (or use override) and return transcribed text."""
        if text_override is not None:
            return text_override.strip()

        self.announce("listening")
        _play_sound("ready")

        wav = record_audio(self.cfg.record_seconds, airpods=self.airpods)
        try:
            return transcribe(wav, self.cfg.whisper_model)
        finally:
            if not self.cfg.keep_recordings:
                wav.unlink(missing_ok=True)

    def _think(self, text: str) -> str:
        """Generate LLM response for *text*."""
        self.announce("thinking", f"You said: {text}")
        _play_sound("thinking")
        return generate_response(text, self.cfg)

    def _respond(self, reply: str) -> None:
        """Print and speak *reply*."""
        self.announce("speaking")
        print(f"Response: {reply}", flush=True)
        self.say(reply)
        _play_sound("done")

    def _is_stop(self, text: str) -> bool:
        return " ".join(text.lower().split()) in STOP_PHRASES

    # ── Single turn ───────────────────────────────────────────────────────────

    def run_once(self, text_override: Optional[str] = None) -> bool:
        """
        Process one listen → think → speak cycle.
        Returns True if the loop should continue, False if stopping.
        """
        try:
            heard = self._listen(text_override)
            if not heard:
                self.announce("idle", "Nothing heard — staying ready.")
                return True

            if self._is_stop(heard):
                self.announce("stopping", f"Stop phrase: '{heard}'")
                _play_sound("bye")
                self.say("Goodbye. Talk soon.")
                return False

            reply = self._think(heard)
            self._respond(reply)
            return True

        except KeyboardInterrupt:
            raise
        except Exception as exc:
            msg = str(exc).strip() or exc.__class__.__name__
            self.announce("error", msg)
            _play_sound("error")
            self.say(f"I hit a problem. {msg}. I'll keep listening.")
            return True

    # ── Startup ───────────────────────────────────────────────────────────────

    def _startup_announcement(self) -> None:
        mode_label = "GitHub Copilot" if self.cfg.mode == "copilot" else "Claude"
        device_label = "AirPods Max" if self.airpods else "default microphone"
        msg = (
            f"Voice ready. {mode_label} mode. Using {device_label}. "
            "Speak after the tone. Say stop to exit."
        )
        print(f"\n{'─'*55}", flush=True)
        print(f"  Voice Launcher — {mode_label} mode", flush=True)
        print(f"  Device  : {device_label}", flush=True)
        print(f"  Model   : {self.cfg.claude_model if self.cfg.mode == 'standalone' else 'gh copilot'}", flush=True)
        print(f"  Whisper : {self.cfg.whisper_model} (local)", flush=True)
        print(f"  Session : {self.session_id}", flush=True)
        print(f"{'─'*55}\n", flush=True)
        _play_sound("start")
        self.say(msg)

    # ── Main entry ────────────────────────────────────────────────────────────

    def run(self, text_override: Optional[str] = None) -> int:
        """
        Run the voice loop until a stop phrase or Ctrl-C.
        Returns exit code (0 = clean stop, 1 = fatal error).
        """
        # Graceful Ctrl-C
        def _sigint(sig, frame):  # noqa: ANN001
            self._running = False
            print("\nCtrl-C received — shutting down.", flush=True)

        signal.signal(signal.SIGINT, _sigint)

        self._startup_announcement()

        try:
            if self.cfg.once:
                ok = self.run_once(text_override)
                return 0 if ok else 0

            first = True
            while self._running:
                override = text_override if first else None
                first = False
                should_continue = self.run_once(override)
                if not should_continue:
                    break

        except KeyboardInterrupt:
            pass
        except Exception as exc:
            msg = str(exc).strip() or exc.__class__.__name__
            self.announce("fatal", msg)
            _play_sound("error")
            self.say(f"Fatal error: {msg}. Shutting down.")
            return 1

        _play_sound("bye")
        self.say("Voice launcher closed. Goodbye.")
        return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="voice.py",
        description=(
            "Unified voice launcher.\n"
            "  python voice.py           → standalone (Claude)\n"
            "  python voice.py --copilot → GitHub Copilot mode"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--copilot", action="store_true",
        help="Use GitHub Copilot CLI as the LLM backend.",
    )
    p.add_argument(
        "--mode", choices=["standalone", "copilot"],
        help="Explicit mode (alternative to --copilot flag).",
    )
    p.add_argument(
        "--once", action="store_true",
        help="Process one turn then exit.",
    )
    p.add_argument(
        "--text", metavar="TEXT",
        help="Skip microphone; use TEXT as input.",
    )
    p.add_argument(
        "--voice", default=None,
        help="macOS say voice (default: Karen (Premium)).",
    )
    p.add_argument(
        "--rate", type=int, default=None,
        help="TTS speaking rate (default: 160).",
    )
    p.add_argument(
        "--record-seconds", type=int, default=None,
        help="Mic recording duration per turn in seconds (default: 6).",
    )
    p.add_argument(
        "--whisper-model", default=None,
        help="faster-whisper model name (default: tiny.en).",
    )
    p.add_argument(
        "--claude-model", default=None,
        help="Anthropic model ID for standalone mode.",
    )
    p.add_argument(
        "--no-speak", action="store_true",
        help="Disable all speech output (text only).",
    )
    p.add_argument(
        "--repo-path", default=None,
        help="Working directory passed to gh copilot (default: agentic-brain/).",
    )
    p.add_argument(
        "--keep-recordings", action="store_true",
        help="Keep WAV files after transcription (debugging).",
    )
    p.add_argument(
        "--diagnose", action="store_true",
        help="Print audio diagnostics and exit.",
    )
    return p


def _run_diagnose() -> int:
    """Print audio environment diagnostics."""
    import shutil

    airpods = detect_airpods()
    info = {
        "airpods_max_detected": airpods,
        "airpods_native_rate_hz": AIRPODS_NATIVE_RATE if airpods else "n/a",
        "whisper_target_rate_hz": WHISPER_TARGET_RATE,
        "energy_threshold": ENERGY_THRESHOLD,
        "no_speech_threshold": NO_SPEECH_THRESHOLD,
        "post_tts_delay_s": POST_TTS_DELAY,
        "sox": bool(shutil.which("sox")),
        "gh": bool(shutil.which("gh")),
        "CLAUDE_API_KEY": bool(os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
    }
    try:
        import faster_whisper
        info["faster_whisper"] = faster_whisper.__version__
    except ImportError:
        info["faster_whisper"] = "not installed"

    print(json.dumps(info, indent=2))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.diagnose:
        return _run_diagnose()

    # ── Build config ──────────────────────────────────────────────────────────
    cfg = Config()

    # Resolve mode: --copilot flag, --mode flag, or default standalone
    if args.copilot or (args.mode == "copilot"):
        cfg.mode = "copilot"
    elif args.mode == "standalone":
        cfg.mode = "standalone"
    # else: default "standalone" from Config

    if args.voice:
        cfg.voice = args.voice
    if args.rate:
        cfg.rate = args.rate
    if args.record_seconds:
        cfg.record_seconds = args.record_seconds
    if args.whisper_model:
        cfg.whisper_model = args.whisper_model
    if args.claude_model:
        cfg.claude_model = args.claude_model
    if args.no_speak:
        cfg.say_enabled = False
    if args.repo_path:
        cfg.repo_path = Path(args.repo_path)
    if args.keep_recordings:
        cfg.keep_recordings = True

    cfg.once = args.once

    # ── Go ─────────────────────────────────────────────────────────────────────
    launcher = VoiceLauncher(cfg)
    return launcher.run(text_override=args.text)


if __name__ == "__main__":
    raise SystemExit(main())
