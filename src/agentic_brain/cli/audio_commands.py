# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""CLI audio commands."""

from __future__ import annotations

import argparse

from agentic_brain.audio.earcons import EARCONS, EarconPlayer, get_earcon_config
from agentic_brain.audio.sound_themes import list_sound_themes


def audio_earcon_command(args: argparse.Namespace) -> int:
    """Play or list earcons."""
    if getattr(args, "list", False) or not getattr(args, "name", None):
        print("Available earcons:")
        for name in sorted(EARCONS):
            config = EARCONS[name]
            print(f"  - {name:<16} {config.description}")
        print()
        print(f"Themes: {', '.join(list_sound_themes())}")
        return 0

    try:
        config = get_earcon_config(args.name)
        player = EarconPlayer(
            volume=args.volume,
            enabled=not args.disable,
            theme=args.theme,
        )
        if args.async_play:
            ok = player.play_async(config.name) is not None
        else:
            ok = player.play(config.name, blocking=True)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    if not ok:
        print(f"Could not play earcon '{config.name}'")
        return 1

    print(
        f"Played earcon '{config.name}' "
        f"(theme={args.theme}, volume={player.effective_volume_for(config.name):.2f})"
    )
    return 0


def register_audio_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register audio commands with the CLI parser."""
    audio_parser = subparsers.add_parser(
        "audio",
        help="Audio playback utilities",
        description="Accessibility-focused audio utilities including earcons.",
    )
    audio_subparsers = audio_parser.add_subparsers(dest="audio_subcommand")

    earcon_parser = audio_subparsers.add_parser(
        "earcon",
        help="Play or list earcons",
        description="Play short non-speech audio cues for accessibility feedback.",
    )
    earcon_parser.add_argument(
        "name",
        nargs="?",
        help="Earcon name (for example: success, error, waiting)",
    )
    earcon_parser.add_argument(
        "--theme",
        default="minimal",
        choices=list_sound_themes(),
        help="Sound theme to use",
    )
    earcon_parser.add_argument(
        "--volume",
        type=float,
        default=0.22,
        help="Base earcon volume before theme adjustment (0.0-1.0)",
    )
    earcon_parser.add_argument(
        "--async",
        dest="async_play",
        action="store_true",
        help="Return immediately after scheduling playback",
    )
    earcon_parser.add_argument(
        "--disable",
        action="store_true",
        help="Disable playback and validate the command path only",
    )
    earcon_parser.add_argument(
        "--list",
        action="store_true",
        help="List all available earcons",
    )
    earcon_parser.set_defaults(func=audio_earcon_command)
