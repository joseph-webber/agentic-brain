#!/usr/bin/env python3
"""Voice chat using sox/afrecord for microphone capture to bypass TCC issues."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import redis
import requests

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR / ".cache" / "voice-recordings"
REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_WHISPER_MODEL = "tiny.en"
DEFAULT_VOICE = "Karen (Premium)"
DEFAULT_RATE = 160
DEFAULT_DURATION = 5
DEFAULT_SAMPLE_RATE = 16000
EXIT_WORDS = {"stop", "goodbye", "exit", "quit", "bye karen", "thanks karen"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Voice chat with Karen using sox/afrecord to avoid terminal TCC mic issues."
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "sox", "afrecord"),
        default="auto",
        help="Recorder backend to use. auto prefers sox, then afrecord.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION,
        help="Recording length in seconds for each turn.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
        help="Capture sample rate in Hz.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Ollama model name.",
    )
    parser.add_argument(
        "--whisper-model",
        default=DEFAULT_WHISPER_MODEL,
        help="faster-whisper model name.",
    )
    parser.add_argument(
        "--redis-url",
        default=REDIS_URL,
        help="Redis URL used for status reporting.",
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        help="macOS say voice name.",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=DEFAULT_RATE,
        help="macOS say speech rate.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single record/transcribe/respond cycle.",
    )
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="Do not speak responses. Useful for non-interactive testing.",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip the Ollama request and just echo the transcript.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate dependencies and connectivity without recording.",
    )
    return parser


def get_redis_client(redis_url: str) -> redis.Redis:
    return redis.from_url(redis_url, decode_responses=True)


def report_status(client: redis.Redis | None, event: str, **payload: Any) -> None:
    if client is None:
        return
    record = {"event": event, "timestamp": time.time(), **payload}
    serialized = json.dumps(record, ensure_ascii=False)
    try:
        client.set("voice:sox:last_status", serialized)
        client.publish("voice:sox:status", serialized)
        client.lpush("voice:sox:history", serialized)
        client.ltrim("voice:sox:history", 0, 49)
    except Exception:
        pass


def resolve_backend(preferred: str) -> str:
    if preferred != "auto":
        if shutil.which(preferred):
            return preferred
        raise RuntimeError(f"Recorder backend '{preferred}' is not installed.")

    if shutil.which("sox"):
        return "sox"
    if shutil.which("afrecord"):
        return "afrecord"
    raise RuntimeError("Neither sox nor afrecord is installed.")


def build_audio_path() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"talk_to_karen_sox_{int(time.time())}_{uuid4().hex}.wav"


def record_with_sox(output_path: Path, duration: float, sample_rate: int) -> None:
    # Import from audio_utils for consistent AirPods-aware recording
    import sys
    sys.path.insert(0, str(SCRIPT_DIR))
    from audio_utils import record_audio as _au_record
    # audio_utils handles native-rate capture + resample; ignore sample_rate arg here
    _au_record(duration=duration, output_path=output_path)


def record_with_afrecord(output_path: Path, duration: float, sample_rate: int) -> None:
    cmd = [
        "afrecord",
        "-d",
        str(duration),
        "-f",
        "WAVE",
        "-r",
        str(sample_rate),
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def record_audio(duration: float = DEFAULT_DURATION, sample_rate: int = DEFAULT_SAMPLE_RATE, backend: str = "auto") -> tuple[Path, str]:
    selected = resolve_backend(backend)
    output_path = build_audio_path()

    if selected == "sox":
        record_with_sox(output_path, duration, sample_rate)
    else:
        record_with_afrecord(output_path, duration, sample_rate)

    return output_path, selected


def transcribe_audio(audio_path: Path, model_name: str = DEFAULT_WHISPER_MODEL) -> str:
    # Use audio_utils transcription which includes energy gate + hallucination guards
    import sys
    sys.path.insert(0, str(SCRIPT_DIR))
    from audio_utils import transcribe_audio as _au_transcribe
    return _au_transcribe(audio_path, model_name=model_name)


def get_llm_response(text: str, model: str = DEFAULT_MODEL) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": (
                "You are Karen, an Australian assistant speaking to Joseph, who is blind. "
                "Reply conversationally in no more than three short sentences.\n"
                f"User said: {text}"
            ),
            "stream": False,
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("response", "")
    if not isinstance(result, str):
        raise RuntimeError("Ollama returned a non-text response.")
    return result.strip()


def speak(text: str, voice: str = DEFAULT_VOICE, rate: int = DEFAULT_RATE) -> None:
    # Use audio_utils.speak which adds a post-TTS delay to clear Bluetooth buffer
    import sys
    sys.path.insert(0, str(SCRIPT_DIR))
    from audio_utils import speak as _au_speak
    _au_speak(text, voice=voice, rate=rate)


def run_self_test(args: argparse.Namespace) -> int:
    failures: list[str] = []
    backend = None

    try:
        backend = resolve_backend(args.backend)
    except Exception as exc:
        failures.append(str(exc))

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        failures.append(f"Cannot create cache directory: {exc}")

    try:
        import faster_whisper  # noqa: F401
    except Exception as exc:
        failures.append(f"faster_whisper unavailable: {exc}")

    try:
        requests.get("http://localhost:11434/api/tags", timeout=5).raise_for_status()
    except Exception as exc:
        failures.append(f"Ollama unavailable: {exc}")

    try:
        get_redis_client(args.redis_url).ping()
    except Exception as exc:
        failures.append(f"Redis unavailable: {exc}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print(f"PASS: backend={backend}")
    print(f"PASS: cache_dir={CACHE_DIR}")
    print("PASS: faster_whisper import")
    print("PASS: Ollama reachable")
    print("PASS: Redis reachable")
    return 0


def run_chat(args: argparse.Namespace) -> int:
    redis_client: redis.Redis | None
    try:
        redis_client = get_redis_client(args.redis_url)
        redis_client.ping()
    except Exception:
        redis_client = None

    print("🎙️ Voice Chat with Karen (sox/afrecord)")
    print("Press Ctrl+C to stop.\n")
    report_status(redis_client, "session_started", backend_preference=args.backend)

    if not args.skip_tts:
        speak("Hello Joseph! I'm ready to chat. Go ahead and speak!", voice=args.voice, rate=args.rate)

    try:
        while True:
            print(f"🎤 Recording for {args.duration:g} seconds...")
            audio_path, selected_backend = record_audio(
                duration=args.duration,
                sample_rate=args.sample_rate,
                backend=args.backend,
            )
            report_status(
                redis_client,
                "recording_complete",
                backend=selected_backend,
                audio_path=str(audio_path),
            )

            try:
                print("🔄 Transcribing...")
                text = transcribe_audio(audio_path, model_name=args.whisper_model)
                print(f"You said: {text or '[silence]'}")
                report_status(redis_client, "transcription_complete", transcript=text, backend=selected_backend)

                if not text.strip():
                    if args.once:
                        return 0
                    print("…No speech detected, trying again.\n")
                    continue

                if text.strip().lower() in EXIT_WORDS:
                    goodbye = "No worries, Joseph. Talk soon."
                    print(f"Karen: {goodbye}")
                    report_status(redis_client, "session_finished", transcript=text, response=goodbye)
                    if not args.skip_tts:
                        speak(goodbye, voice=args.voice, rate=args.rate)
                    return 0

                print("🤔 Thinking...")
                if args.skip_llm:
                    response = f"I heard you say: {text}"
                else:
                    response = get_llm_response(text, model=args.model)

                print(f"Karen: {response}")
                report_status(redis_client, "response_complete", transcript=text, response=response, backend=selected_backend)
                if not args.skip_tts:
                    speak(response, voice=args.voice, rate=args.rate)

                if args.once:
                    return 0
            finally:
                try:
                    audio_path.unlink(missing_ok=True)
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("\nStopping voice chat.")
        report_status(redis_client, "session_interrupted")
        return 0
    except Exception as exc:
        report_status(redis_client, "session_error", error=str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.self_test:
        return run_self_test(args)
    return run_chat(args)


if __name__ == "__main__":
    raise SystemExit(main())
