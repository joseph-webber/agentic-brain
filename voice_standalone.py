#!/usr/bin/env python3
"""Standalone voice chat agent backed by OpenAI transcription and Claude."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv

try:
    import redis
except ImportError:  # pragma: no cover - optional runtime dependency
    redis = None  # type: ignore[assignment]


SCRIPT_DIR = Path(__file__).resolve().parent
BRAIN_ROOT = SCRIPT_DIR.parent
ENV_FILES = (BRAIN_ROOT / ".env", SCRIPT_DIR / ".env")
RUNTIME_DIR = SCRIPT_DIR / ".voice-runtime"
RECORDINGS_DIR = RUNTIME_DIR / "recordings"
STOP_PHRASES = {
    "stop",
    "stop listening",
    "goodbye",
    "exit",
    "quit",
    "thanks goodbye",
}


def load_environment() -> None:
    """Load .env files from the brain root and local project if present."""
    for env_file in ENV_FILES:
        if env_file.exists():
            load_dotenv(env_file, override=False)


load_environment()


@dataclass
class VoiceSettings:
    """Runtime configuration for the standalone voice loop."""

    voice: str = field(default_factory=lambda: os.getenv("VOICE_TTS_VOICE", "Karen (Premium)"))
    rate: int = field(default_factory=lambda: int(os.getenv("VOICE_TTS_RATE", "160")))
    record_seconds: int = field(default_factory=lambda: int(os.getenv("VOICE_RECORD_SECONDS", "6")))
    transcribe_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
    )
    claude_model: str = field(
        default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    )
    anthropic_version: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_VERSION", "2023-06-01")
    )
    max_tokens: int = field(default_factory=lambda: int(os.getenv("VOICE_MAX_TOKENS", "220")))
    namespace: str = "voice:standalone"
    say_enabled: bool = True
    keep_recordings: bool = False


class RedisStateStore:
    """Tiny Redis wrapper that stores JSON-friendly state by namespace."""

    def __init__(self, namespace: str, client: Any = None) -> None:
        self.namespace = namespace
        self.client = client if client is not None else self._build_client()

    def _build_client(self) -> Any:
        if redis is None:
            return None
        try:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                return redis.Redis.from_url(redis_url, decode_responses=True)
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            password = os.getenv("REDIS_PASSWORD")
            return redis.Redis(host=host, port=port, password=password, decode_responses=True)
        except Exception:
            return None

    def _key(self, suffix: str) -> str:
        return f"{self.namespace}:{suffix}"

    def write(self, suffix: str, value: Any) -> None:
        if self.client is None:
            return
        try:
            if isinstance(value, str):
                payload = value
            else:
                payload = json.dumps(value, ensure_ascii=False)
            self.client.set(self._key(suffix), payload)
        except Exception:
            return

    def status(self, state: str, **details: Any) -> None:
        payload = {"status": state, "timestamp": time.time(), **details}
        self.write("status", payload)


class VoiceIO:
    """Shared audio helpers for recording, transcription, and speech."""

    def __init__(self, settings: VoiceSettings, runtime_dir: Path = RUNTIME_DIR) -> None:
        self.settings = settings
        self.runtime_dir = runtime_dir
        self.recordings_dir = runtime_dir / "recordings"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

    def speak(self, text: str) -> None:
        if not self.settings.say_enabled or not text.strip():
            return
        subprocess.run(
            ["say", "-v", self.settings.voice, "-r", str(self.settings.rate), text],
            check=False,
            capture_output=True,
        )

    def play_ready_tone(self) -> None:
        subprocess.run(["afplay", "/System/Library/Sounds/Tink.aiff"], check=False, capture_output=True)

    def record_audio(self, duration: Optional[int] = None) -> Path:
        seconds = duration or self.settings.record_seconds
        output_path = self.recordings_dir / f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}.wav"
        cmd = [
            "sox",
            "-q",
            "-d",
            "-r",
            "16000",
            "-c",
            "1",
            "-b",
            "16",
            str(output_path),
            "trim",
            "0",
            str(seconds),
        ]
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(f"sox recording failed: {completed.stderr.strip() or completed.stdout.strip()}")
        return output_path

    def transcribe(self, audio_path: Path) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        with audio_path.open("rb") as audio_file:
            response = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": self.settings.transcribe_model},
                files={"file": (audio_path.name, audio_file, "audio/wav")},
                timeout=60,
            )
        response.raise_for_status()
        payload = response.json()
        text = str(payload.get("text", "")).strip()
        return text

    def cleanup_recording(self, audio_path: Path) -> None:
        if self.settings.keep_recordings:
            return
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            return


class StandaloneVoiceAgent:
    """Conversation loop using OpenAI transcription and Claude responses."""

    def __init__(
        self,
        settings: Optional[VoiceSettings] = None,
        io: Optional[VoiceIO] = None,
        state_store: Optional[RedisStateStore] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.settings = settings or VoiceSettings()
        self.io = io or VoiceIO(self.settings)
        self.state = state_store or RedisStateStore(self.settings.namespace)
        self.session = session or requests.Session()
        self.session_id = uuid.uuid4().hex
        self.history: list[dict[str, str]] = []

    def _stop_requested(self, text: str) -> bool:
        normalized = " ".join(text.lower().split())
        return normalized in STOP_PHRASES

    def _extract_claude_text(self, payload: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in payload.get("content", []):
            if item.get("type") == "text":
                parts.append(str(item.get("text", "")).strip())
        return "\n".join(part for part in parts if part).strip()

    def generate_response(self, text: str) -> str:
        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key:
            raise RuntimeError("CLAUDE_API_KEY is not set.")

        system_prompt = (
            "You are a warm, concise voice assistant for Joseph, who is blind. "
            "Respond in plain spoken English, normally 1 to 4 short sentences, "
            "without markdown, bullet points, or emoji."
        )
        messages = self.history[-8:] + [{"role": "user", "content": text}]
        response = self.session.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": self.settings.anthropic_version,
                "content-type": "application/json",
            },
            json={
                "model": self.settings.claude_model,
                "max_tokens": self.settings.max_tokens,
                "system": system_prompt,
                "messages": messages,
            },
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        answer = self._extract_claude_text(payload)
        if not answer:
            raise RuntimeError("Claude returned an empty response.")
        self.history.extend(
            [
                {"role": "user", "content": text},
                {"role": "assistant", "content": answer},
            ]
        )
        return answer

    def listen_once(self, text_override: Optional[str] = None) -> str:
        if text_override is not None:
            text = text_override.strip()
            if not text:
                raise RuntimeError("Text override was empty.")
            return text

        self.state.status("listening", session_id=self.session_id)
        self.io.play_ready_tone()
        audio_path = self.io.record_audio()
        try:
            transcript = self.io.transcribe(audio_path)
            return transcript.strip()
        finally:
            self.io.cleanup_recording(audio_path)

    def process_turn(self, text: str) -> str:
        heard = text.strip()
        if not heard:
            raise RuntimeError("No speech was transcribed.")
        self.state.write("last_heard", {"text": heard, "timestamp": time.time()})
        if self._stop_requested(heard):
            goodbye = "Stopping voice mode now. Talk soon, Joseph."
            self.state.status("stopping", reason="voice_stop_phrase", session_id=self.session_id)
            self.state.write("last_response", {"text": goodbye, "timestamp": time.time()})
            self.io.speak(goodbye)
            return goodbye

        self.state.status("processing", session_id=self.session_id, heard=heard)
        reply = self.generate_response(heard)
        self.state.write(
            "last_response",
            {"text": reply, "timestamp": time.time(), "session_id": self.session_id},
        )
        self.state.status("speaking", session_id=self.session_id)
        self.io.speak(reply)
        return reply

    def run(self, *, once: bool = False, text_override: Optional[str] = None) -> int:
        self.state.write(
            "config",
            {
                "session_id": self.session_id,
                "voice": self.settings.voice,
                "rate": self.settings.rate,
                "record_seconds": self.settings.record_seconds,
                "transcribe_model": self.settings.transcribe_model,
                "claude_model": self.settings.claude_model,
                "pid": os.getpid(),
            },
        )
        self.state.status("ready", session_id=self.session_id)
        if text_override is None:
            self.io.speak("Standalone voice agent ready. Speak after the tone.")

        first_iteration = True
        while True:
            try:
                spoken_text = self.listen_once(text_override if first_iteration else None)
                first_iteration = False
                if not spoken_text:
                    self.state.status("idle", session_id=self.session_id, note="empty_transcript")
                    if once:
                        return 1
                    continue
                response = self.process_turn(spoken_text)
                print(f"You: {spoken_text}")
                print(f"Claude: {response}")
                sys.stdout.flush()
                if once or self._stop_requested(spoken_text):
                    self.state.status("stopped", session_id=self.session_id)
                    return 0
            except KeyboardInterrupt:
                self.state.status("stopped", session_id=self.session_id, reason="keyboard_interrupt")
                self.io.speak("Stopping standalone voice agent.")
                return 0
            except Exception as exc:
                message = str(exc).strip() or exc.__class__.__name__
                self.state.write(
                    "last_error",
                    {"message": message, "timestamp": time.time(), "session_id": self.session_id},
                )
                self.state.status("error", session_id=self.session_id, error=message)
                print(f"Error: {message}", file=sys.stderr)
                sys.stderr.flush()
                if once:
                    return 1
                self.io.speak("I hit a problem. I will keep listening.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone voice agent using sox, OpenAI transcription, and Claude."
    )
    parser.add_argument("--once", action="store_true", help="Process a single turn then exit.")
    parser.add_argument("--text", help="Skip recording and use this text as the transcribed input.")
    parser.add_argument("--voice", default=os.getenv("VOICE_TTS_VOICE", "Karen (Premium)"))
    parser.add_argument("--rate", type=int, default=int(os.getenv("VOICE_TTS_RATE", "160")))
    parser.add_argument(
        "--record-seconds",
        type=int,
        default=int(os.getenv("VOICE_RECORD_SECONDS", "6")),
        help="How long sox records for each utterance.",
    )
    parser.add_argument(
        "--transcribe-model",
        default=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
        help="OpenAI transcription model.",
    )
    parser.add_argument(
        "--claude-model",
        default=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        help="Anthropic Claude model alias.",
    )
    parser.add_argument("--no-speak", action="store_true", help="Do not speak responses aloud.")
    parser.add_argument(
        "--keep-recordings",
        action="store_true",
        help="Keep captured wav files in .voice-runtime/recordings.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    settings = VoiceSettings(
        voice=args.voice,
        rate=args.rate,
        record_seconds=args.record_seconds,
        transcribe_model=args.transcribe_model,
        claude_model=args.claude_model,
        say_enabled=not args.no_speak,
        keep_recordings=args.keep_recordings,
    )
    agent = StandaloneVoiceAgent(settings=settings)
    return agent.run(once=args.once, text_override=args.text)


if __name__ == "__main__":
    raise SystemExit(main())
