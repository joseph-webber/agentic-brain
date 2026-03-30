#!/usr/bin/env python3
"""Voice bridge that sends spoken prompts to GitHub Copilot CLI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from voice_standalone import STOP_PHRASES, RedisStateStore, VoiceIO, VoiceSettings

SCRIPT_DIR = Path(__file__).resolve().parent


class CopilotVoiceBridge:
    """Routes transcribed speech into GitHub Copilot CLI and speaks the result."""

    def __init__(
        self,
        settings: Optional[VoiceSettings] = None,
        io: Optional[VoiceIO] = None,
        state_store: Optional[RedisStateStore] = None,
        repo_path: Optional[Path] = None,
        extra_args: Optional[list[str]] = None,
    ) -> None:
        self.settings = settings or VoiceSettings(namespace="voice:bridge")
        self.settings.namespace = "voice:bridge"
        self.io = io or VoiceIO(self.settings)
        self.state = state_store or RedisStateStore(self.settings.namespace)
        self.repo_path = repo_path or SCRIPT_DIR
        self.extra_args = extra_args or []
        self.session_id = uuid.uuid4().hex

    def _stop_requested(self, text: str) -> bool:
        normalized = " ".join(text.lower().split())
        return normalized in STOP_PHRASES

    def _build_prompt(self, user_text: str) -> str:
        return (
            f"{user_text}\n\n"
            "Respond in plain text suitable for speech output to a blind user. "
            "Keep formatting minimal and avoid markdown tables unless essential."
        )

    def run_copilot(self, text: str) -> str:
        prompt = self._build_prompt(text)
        command = [
            "gh",
            "copilot",
            "-p",
            prompt,
            "-s",
            "--screen-reader",
            "--allow-all-tools",
            "--no-ask-user",
            "--add-dir",
            str(self.repo_path),
        ]
        command.extend(self.extra_args)
        completed = subprocess.run(
            command,
            cwd=self.repo_path,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Copilot CLI failed.")
        response = completed.stdout.strip()
        if not response:
            raise RuntimeError("Copilot CLI returned no output.")
        return response

    def listen_once(self, text_override: Optional[str] = None) -> str:
        if text_override is not None:
            return text_override.strip()
        self.state.status("listening", session_id=self.session_id)
        self.io.play_ready_tone()
        audio_path = self.io.record_audio()
        try:
            return self.io.transcribe(audio_path).strip()
        finally:
            self.io.cleanup_recording(audio_path)

    def process_turn(self, text: str) -> str:
        heard = text.strip()
        if not heard:
            raise RuntimeError("No speech was transcribed.")
        self.state.write("last_heard", {"text": heard, "timestamp": time.time()})
        if self._stop_requested(heard):
            goodbye = "Stopping Copilot voice bridge now."
            self.state.status("stopping", session_id=self.session_id)
            self.state.write("last_response", {"text": goodbye, "timestamp": time.time()})
            self.io.speak(goodbye)
            return goodbye

        self.state.status("processing", session_id=self.session_id, heard=heard)
        answer = self.run_copilot(heard)
        self.state.write(
            "last_response",
            {"text": answer, "timestamp": time.time(), "session_id": self.session_id},
        )
        self.state.status("speaking", session_id=self.session_id)
        self.io.speak(answer)
        return answer

    def run(self, *, once: bool = False, text_override: Optional[str] = None) -> int:
        self.state.write(
            "config",
            {
                "session_id": self.session_id,
                "voice": self.settings.voice,
                "rate": self.settings.rate,
                "repo_path": str(self.repo_path),
                "pid": os.getpid(),
            },
        )
        self.state.status("ready", session_id=self.session_id)
        if text_override is None:
            self.io.speak("Copilot voice bridge ready. Speak after the tone.")

        first_iteration = True
        while True:
            try:
                spoken_text = self.listen_once(text_override if first_iteration else None)
                first_iteration = False
                answer = self.process_turn(spoken_text)
                print(f"You: {spoken_text}")
                print(f"Copilot: {answer}")
                sys.stdout.flush()
                if once or self._stop_requested(spoken_text):
                    self.state.status("stopped", session_id=self.session_id)
                    return 0
            except KeyboardInterrupt:
                self.state.status("stopped", session_id=self.session_id, reason="keyboard_interrupt")
                self.io.speak("Stopping Copilot voice bridge.")
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
                self.io.speak("Copilot hit a problem. I will keep listening.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Voice bridge that transcribes speech and forwards it to GitHub Copilot CLI."
    )
    parser.add_argument("--once", action="store_true", help="Process one turn and exit.")
    parser.add_argument("--text", help="Skip audio recording and use this text instead.")
    parser.add_argument("--voice", default=os.getenv("VOICE_TTS_VOICE", "Karen (Premium)"))
    parser.add_argument("--rate", type=int, default=int(os.getenv("VOICE_TTS_RATE", "160")))
    parser.add_argument("--record-seconds", type=int, default=int(os.getenv("VOICE_RECORD_SECONDS", "6")))
    parser.add_argument("--no-speak", action="store_true", help="Do not speak the response aloud.")
    parser.add_argument(
        "--repo-path",
        default=str(SCRIPT_DIR),
        help="Directory Copilot is allowed to access.",
    )
    parser.add_argument(
        "--copilot-arg",
        action="append",
        default=[],
        help="Extra argument to append to gh copilot. Can be used multiple times.",
    )
    parser.add_argument(
        "--transcribe-model",
        default=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    settings = VoiceSettings(
        voice=args.voice,
        rate=args.rate,
        record_seconds=args.record_seconds,
        transcribe_model=args.transcribe_model,
        namespace="voice:bridge",
        say_enabled=not args.no_speak,
    )
    bridge = CopilotVoiceBridge(
        settings=settings,
        repo_path=Path(args.repo_path).expanduser().resolve(),
        extra_args=args.copilot_arg,
    )
    return bridge.run(once=args.once, text_override=args.text)


if __name__ == "__main__":
    raise SystemExit(main())
