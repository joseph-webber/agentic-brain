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

"""Startup greeting command for the public Agentic Brain CLI."""

from __future__ import annotations

import argparse
import os

from agentic_brain.audio import speak
from agentic_brain.core.startup import get_startup_snapshot


def greet_command(args: argparse.Namespace) -> int:
    """Speak and print a startup greeting with context proof."""
    snapshot = get_startup_snapshot(limit=args.limit)

    print(snapshot.greeting)
    if snapshot.proof_lines:
        print("\nContext proof:")
        for line in snapshot.proof_lines:
            print(line)

    if not args.no_speak:
        speak(snapshot.greeting, voice=args.voice, rate=args.rate)

    return 0


def register_greet_command(subparsers: argparse._SubParsersAction) -> None:
    """Register the greet command on the main CLI parser."""
    greet_parser = subparsers.add_parser(
        "greet",
        help="Speak a startup greeting using recent memory context",
        description=(
            "Show what Agentic Brain remembers from recent Neo4j context and "
            "speak a friendly startup greeting."
        ),
    )
    greet_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="How many recent memory items to inspect (default: 5)",
    )
    greet_parser.add_argument(
        "--voice",
        type=str,
        default=os.environ.get("AGENTIC_BRAIN_VOICE", "Samantha"),
        help="Voice to use for spoken greeting (default: Samantha)",
    )
    greet_parser.add_argument(
        "--rate",
        type=int,
        default=int(os.environ.get("AGENTIC_BRAIN_VOICE_RATE", "165")),
        help="Speech rate for spoken greeting (default: 165)",
    )
    greet_parser.add_argument(
        "--no-speak",
        action="store_true",
        help="Print the greeting without speaking it",
    )
    greet_parser.set_defaults(func=greet_command)


__all__ = ["greet_command", "register_greet_command"]
