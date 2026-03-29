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
Voice CLI commands for Agentic Brain.

Commands:
    ab voice list                  List all available voices
    ab voice list --english        List English voices only
    ab voice list --ladies         List Joseph's ladies voices
    ab voice test Karen            Test the Karen voice
    ab voice test --all            Test all English voices (short sample)
    ab voice speak "Hello world"   Speak text with default voice
    ab voice speak "Hi" -v Moira   Speak with specific voice

CRITICAL for accessibility - Joseph needs voice output!
"""

import argparse
import platform
import sys


def voice_list_command(args: argparse.Namespace) -> int:
    """List available voices."""
    # Check platform first
    if platform.system() != "Darwin":
        print("⚠️  Voice system is macOS only.")
        print(f"   Current platform: {platform.system()}")
        print("   On Windows/Linux, only basic TTS (espeak) is available.")
        return 1

    try:
        from agentic_brain.audio import VoiceRegistry
    except ImportError as e:
        print(f"Error: Could not import voice module: {e}")
        return 1

    registry = VoiceRegistry()

    # Filter based on flags
    if hasattr(args, "ladies") and args.ladies:
        voices = registry.get_ladies()
        title = "🎙️  Joseph's Ladies Voices"
    elif hasattr(args, "english") and args.english:
        voices = registry.get_english_voices()
        title = "🎙️  English Voices"
    elif hasattr(args, "novelty") and args.novelty:
        voices = registry.get_novelty_voices()
        title = "🎭  Novelty/Fun Voices"
    elif hasattr(args, "search") and args.search:
        voices = registry.list_voices(search=args.search)
        title = f"🔍  Voices matching '{args.search}'"
    else:
        voices = registry.list_voices()
        title = "🎙️  All Available Voices"

    # Display
    print(f"\n{title}")
    print(f"   Found {len(voices)} voices\n")

    if not voices:
        print("   No voices found matching criteria.")
        return 0

    # Table format
    print(f"   {'Voice Name':<30} {'Language':<10} {'Description':<40}")
    print(f"   {'-'*30} {'-'*10} {'-'*40}")

    for v in voices:
        name = v.get("name", "Unknown")
        lang = v.get("language", "")
        desc = v.get("sample", "")[:40]
        print(f"   {name:<30} {lang:<10} {desc:<40}")

    print()
    print("   Tip: Use 'ab voice test <name>' to hear a voice")
    print("   Tip: Use 'ab voice list --ladies' for Joseph's primary voices")
    return 0


def voice_test_command(args: argparse.Namespace) -> int:
    """Test a voice."""
    if platform.system() != "Darwin":
        print("⚠️  Voice testing requires macOS.")
        print(f"   Current platform: {platform.system()}")
        return 1

    try:
        from agentic_brain.audio import VoiceRegistry
    except ImportError as e:
        print(f"Error: Could not import voice module: {e}")
        return 1

    registry = VoiceRegistry()

    # Test all English voices
    if hasattr(args, "all") and args.all:
        print("\n🎙️  Testing all English voices...\n")
        english_voices = registry.get_english_voices()
        for v in english_voices[:10]:  # Limit to 10 for sanity
            name = v.get("name", "Unknown")
            print(f"   Testing: {name}")
            registry.test_voice(name, f"Hello, I am {name}")
        print("\n   Done! Tested 10 voices.")
        return 0

    # Test specific voice
    voice_name = args.voice if hasattr(args, "voice") else None
    if not voice_name:
        print("Error: Please specify a voice name")
        print("Usage: ab voice test <voice_name>")
        print("       ab voice test Karen")
        print("       ab voice test 'Karen (Premium)'")
        return 1

    voice_info = registry.get_voice(voice_name)
    if not voice_info:
        print(f"❌  Voice not found: {voice_name}")
        print("\n   Available voices (sample):")
        for v in registry.list_voices()[:10]:
            print(f"   - {v['name']}")
        print("\n   Use 'ab voice list' to see all voices")
        return 1

    # Custom text or default sample
    text = args.text if hasattr(args, "text") and args.text else None

    print(f"\n🎙️  Testing voice: {voice_info['name']}")
    print(f"   Language: {voice_info.get('language', 'Unknown')}")
    if voice_info.get("sample"):
        print(f"   Sample: {voice_info['sample']}")
    print()

    if registry.test_voice(voice_info["name"], text):
        print("   ✓ Voice test successful!")
        return 0
    else:
        print("   ✗ Voice test failed")
        return 1


def voice_speak_command(args: argparse.Namespace) -> int:
    """Speak text with specified voice."""
    if platform.system() != "Darwin":
        print("⚠️  Voice speaking requires macOS.")
        print(f"   Current platform: {platform.system()}")
        return 1

    try:
        from agentic_brain.audio import speak
    except ImportError as e:
        print(f"Error: Could not import voice module: {e}")
        return 1

    text = args.text if hasattr(args, "text") else None
    if not text:
        print("Error: Please specify text to speak")
        print("Usage: ab voice speak 'Hello world'")
        return 1

    voice = args.voice if hasattr(args, "voice") and args.voice else "Karen (Premium)"
    rate = args.rate if hasattr(args, "rate") and args.rate else 160

    print(f"🎙️  Speaking with {voice}...")
    if speak(text, voice=voice, rate=rate):
        print("   ✓ Done")
        return 0
    else:
        print("   ✗ Speech failed")
        return 1


def voice_command(args: argparse.Namespace) -> int:
    """Main voice command (shows help if no subcommand)."""
    print("\n🎙️  Agentic Brain Voice System")
    print("=" * 40)
    print("\nCommands:")
    print("  ab voice list              List all voices")
    print("  ab voice list --ladies     List Joseph's ladies")
    print("  ab voice list --english    List English voices")
    print("  ab voice list -s <term>    Search voices")
    print()
    print("  ab voice test <name>       Test a specific voice")
    print("  ab voice test --all        Test all English voices")
    print()
    print("  ab voice speak 'text'      Speak with default voice")
    print("  ab voice speak 'text' -v Moira  Speak with Moira")
    print()
    print("Examples:")
    print("  ab voice test 'Karen (Premium)'")
    print("  ab voice speak 'Hello Joseph' -v Karen")
    print("  ab voice list --ladies")
    return 0


def register_voice_commands(subparsers: argparse._SubParsersAction) -> None:
    """
    Register voice commands with the CLI parser.

    Call this from cli/__init__.py to add voice commands.
    """
    # Main voice command
    voice_parser = subparsers.add_parser(
        "voice",
        help="Voice/TTS commands (145+ macOS voices)",
        description="Text-to-speech commands for accessibility. CRITICAL for blind users!",
    )
    voice_subparsers = voice_parser.add_subparsers(
        dest="voice_subcommand",
        help="Voice command",
    )

    # voice list
    list_parser = voice_subparsers.add_parser(
        "list",
        help="List available voices",
    )
    list_parser.add_argument(
        "--ladies",
        action="store_true",
        help="Show only Joseph's ladies voices",
    )
    list_parser.add_argument(
        "--english",
        action="store_true",
        help="Show only English voices",
    )
    list_parser.add_argument(
        "--novelty",
        action="store_true",
        help="Show fun/novelty voices",
    )
    list_parser.add_argument(
        "-s", "--search",
        type=str,
        help="Search voices by name/description",
    )
    list_parser.set_defaults(func=voice_list_command)

    # voice test
    test_parser = voice_subparsers.add_parser(
        "test",
        help="Test a voice",
    )
    test_parser.add_argument(
        "voice",
        nargs="?",
        type=str,
        help="Voice name to test (e.g., Karen, Moira)",
    )
    test_parser.add_argument(
        "--all",
        action="store_true",
        help="Test all English voices",
    )
    test_parser.add_argument(
        "-t", "--text",
        type=str,
        help="Custom text to speak",
    )
    test_parser.set_defaults(func=voice_test_command)

    # voice speak
    speak_parser = voice_subparsers.add_parser(
        "speak",
        help="Speak text",
    )
    speak_parser.add_argument(
        "text",
        type=str,
        help="Text to speak",
    )
    speak_parser.add_argument(
        "-v", "--voice",
        type=str,
        default="Karen (Premium)",
        help="Voice to use (default: Karen Premium)",
    )
    speak_parser.add_argument(
        "-r", "--rate",
        type=int,
        default=160,
        help="Speech rate (default: 160)",
    )
    speak_parser.set_defaults(func=voice_speak_command)

    # Default for bare 'ab voice'
    voice_parser.set_defaults(func=voice_command)
