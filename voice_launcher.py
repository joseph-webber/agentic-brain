#!/usr/bin/env python3
"""Unified launcher for standalone voice and GitHub Copilot voice bridge."""

from __future__ import annotations

import argparse
import os
import time
from typing import Optional

from voice_copilot_bridge import CopilotVoiceBridge
from voice_standalone import (
    RedisStateStore,
    StandaloneVoiceAgent,
    VoiceIO,
    VoiceSettings,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch Joseph's voice stack in standalone Claude mode or Copilot bridge mode."
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["standalone", "copilot"],
        help="Which voice mode to launch.",
    )
    parser.add_argument("--once", action="store_true", help="Run one turn only.")
    parser.add_argument("--text", help="Use text input instead of recording audio.")
    parser.add_argument("--voice", default=os.getenv("VOICE_TTS_VOICE", "Karen (Premium)"))
    parser.add_argument("--rate", type=int, default=int(os.getenv("VOICE_TTS_RATE", "160")))
    parser.add_argument("--record-seconds", type=int, default=int(os.getenv("VOICE_RECORD_SECONDS", "6")))
    parser.add_argument("--no-speak", action="store_true", help="Disable macOS say output.")
    parser.add_argument("--repo-path", default=os.getenv("VOICE_COPILOT_REPO", os.getcwd()))
    parser.add_argument(
        "--copilot-arg",
        action="append",
        default=[],
        help="Extra argument to pass through to gh copilot in copilot mode.",
    )
    parser.add_argument(
        "--transcribe-model",
        default=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
    )
    parser.add_argument(
        "--claude-model",
        default=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    integrator_state = RedisStateStore("voice:integrator")
    integrator_state.write(
        "last_launch",
        {
            "mode": args.mode,
            "timestamp": time.time(),
            "voice": args.voice,
            "record_seconds": args.record_seconds,
            "repo_path": args.repo_path,
        },
    )

    shared_settings = VoiceSettings(
        voice=args.voice,
        rate=args.rate,
        record_seconds=args.record_seconds,
        transcribe_model=args.transcribe_model,
        claude_model=args.claude_model,
        say_enabled=not args.no_speak,
    )
    announcer = VoiceIO(shared_settings)
    announcer.speak(f"Launching {args.mode} voice mode now.")

    if args.mode == "standalone":
        agent = StandaloneVoiceAgent(settings=shared_settings)
        exit_code = agent.run(once=args.once, text_override=args.text)
    else:
        bridge_settings = VoiceSettings(
            voice=args.voice,
            rate=args.rate,
            record_seconds=args.record_seconds,
            transcribe_model=args.transcribe_model,
            namespace="voice:bridge",
            say_enabled=not args.no_speak,
        )
        agent = CopilotVoiceBridge(
            settings=bridge_settings,
            repo_path=args.repo_path,
            extra_args=args.copilot_arg,
        )
        exit_code = agent.run(once=args.once, text_override=args.text)

    integrator_state.write(
        "last_result",
        {
            "mode": args.mode,
            "timestamp": time.time(),
            "exit_code": exit_code,
        },
    )
    if exit_code == 0:
        announcer.speak(f"{args.mode.capitalize()} voice mode finished successfully.")
    else:
        announcer.speak(f"{args.mode.capitalize()} voice mode ended with an error.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
