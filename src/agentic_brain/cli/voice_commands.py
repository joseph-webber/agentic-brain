# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
    ab voice list --female         List female voices only
    ab voice list --male           List male voices only
    ab voice list --primary        List primary voice assistants
    ab voice test Karen            Test the Karen voice
    ab voice test --all            Test all English voices (short sample)
    ab voice speak "Hello world"   Speak text with default voice
    ab voice speak "Hi" -v Moira   Speak with specific voice

CRITICAL for accessibility - Joseph needs voice output!
"""

import argparse
import platform
import sys

from agentic_brain.voice import LANGUAGE_PACKS, VoiceConfig
from agentic_brain.voice import speak as quick_speak
from agentic_brain.voice.llm_voice import smart_voice_response
from agentic_brain.voice.regional import (
    detect_location,
    get_available_regions,
    get_regional_voice,
    list_regions,
)
from agentic_brain.voice.registry import (
    get_english_voices,
    get_female_voices,
    get_male_voices,
    get_novelty_voices,
    get_primary_voices,
    list_all_voices,
)
from agentic_brain.voice.registry import (
    get_voice as get_voice_metadata,
)


def voice_region_command(args: argparse.Namespace) -> int:
    """Set or show regional voice settings."""
    rv = get_regional_voice()

    if args.city:
        city = args.city.lower()
        available = get_available_regions()

        if city in available:
            rv.save_location(city)
            print(f"✅ Region set to: {city.capitalize()}")
            # Reload to confirm
            rv._load_location()
            print(f"Greeting: {rv.get_greeting()}")
        else:
            print(f"❌ Unknown region: {city}")
            print("Available regions:")
            for region in list_regions():
                print(f"  - {region}")
            return 1
    else:
        # Show current
        print(f"Current Region: {rv.region_name}")
        print(f"Greeting: {rv.get_greeting()}")
        print(f"Farewell: {rv.get_farewell()}")
        print(f"Timezone: {rv.timezone}")

    return 0


def voice_list_command(args: argparse.Namespace) -> int:
    """List available voices."""
    # Filter based on flags
    if getattr(args, "primary", False):
        voices = get_primary_voices()
        title = "🎙️  Primary Voice Assistants"
    elif getattr(args, "female", False):
        voices = get_female_voices()
        title = "🎙️  Female Voices"
    elif getattr(args, "male", False):
        voices = get_male_voices()
        title = "🎙️  Male Voices"
    elif getattr(args, "english", False):
        voices = get_english_voices()
        title = "🎙️  English Voices"
    elif getattr(args, "novelty", False):
        voices = get_novelty_voices()
        title = "🎭  Novelty/Fun Voices"
    elif getattr(args, "search", None):
        search = args.search.lower()
        all_voices = list_all_voices()
        voices = [
            v
            for v in all_voices
            if search in v.name.lower() or search in v.description.lower()
        ]
        title = f"🔍  Voices matching '{args.search}'"
    else:
        voices = list_all_voices()
        title = "🎙️  All Available Voices"

    # Display
    print(f"\n{title}")
    print(f"   Found {len(voices)} voices\n")

    if not voices:
        print("   No voices found matching criteria.")
        return 0

    # Table format
    print(f"   {'Voice Name':<30} {'Language':<15} {'Description':<40}")
    print(f"   {'-'*30} {'-'*15} {'-'*40}")

    for v in voices:
        name = getattr(v, "name", "Unknown")
        lang = getattr(v, "language", "")
        desc = getattr(v, "description", "")[:40]

        # Add flag
        flag = ""
        if lang in LANGUAGE_PACKS:
            flag = LANGUAGE_PACKS[lang].flag + " "

        print(f"   {name:<30} {flag + lang:<15} {desc:<40}")

    print()
    print("   Tip: Use 'ab voice test <name>' to hear a voice")
    print("   Tip: Use 'ab voice list --primary' for curated primary voices")
    return 0


def voice_test_command(args: argparse.Namespace) -> int:
    """Test a voice."""
    if platform.system() != "Darwin":
        print("⚠️  Voice testing requires macOS.")
        print(f"   Current platform: {platform.system()}")
        return 1

    from agentic_brain.voice.registry import get_english_voices

    # Test all English voices
    if hasattr(args, "all") and args.all:
        print("\n🎙️  Testing all English voices...\n")
        english_voices = get_english_voices()
        for v in english_voices[:10]:  # Limit to 10 for sanity
            name = v.name
            print(f"   Testing: {name}")
            quick_speak(f"Hello, I am {name}", voice=v.full_name)
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

    voice_meta = get_voice_metadata(voice_name)
    if not voice_meta:
        print(f"❌  Voice not found: {voice_name}")
        print("\n   Available voices (sample):")
        for v in list_all_voices()[:10]:
            print(f"   - {v.name}")
        print("\n   Use 'ab voice list' to see all voices")
        return 1

    # Custom text or default sample
    text = args.text if hasattr(args, "text") and args.text else None

    print(f"\n🎙️  Testing voice: {voice_meta.name}")
    print(f"   Language: {voice_meta.language}")
    if voice_meta.sample_text:
        print(f"   Sample: {voice_meta.sample_text}")
    print()

    sample = text or voice_meta.sample_text or f"Hello, I am {voice_meta.name}"
    if quick_speak(sample, voice=voice_meta.full_name):
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


def voice_set_command(args: argparse.Namespace) -> int:
    """Set default voice."""
    voice = args.voice
    print(f"\n🎙️  Setting default voice to: {voice}")
    print("   To make this permanent, add this to your environment:")
    print(f"   export AGENTIC_BRAIN_VOICE='{voice}'")
    print("\n   Or in your .env file:")
    print(f"   AGENTIC_BRAIN_VOICE={voice}")
    return 0


def voice_conversation_command(args: argparse.Namespace) -> int:
    """Run a conversation demo or custom conversation."""
    try:
        from agentic_brain.voice.conversation import ConversationalVoice, VoiceMode
    except ImportError as e:
        print(f"Error: Could not import conversation module: {e}")
        return 1

    conv = ConversationalVoice()

    if hasattr(args, "demo") and args.demo:
        print("\n🎙️  Running Conversation Demo")
        print("=" * 50)
        conv.demo()
        return 0

    # Custom conversation
    print("Usage: ab voice conversation --demo")
    print("       (custom conversations not yet implemented in CLI)")
    return 1


def voice_voiceover_command(args: argparse.Namespace) -> int:
    """Test VoiceOver integration."""
    try:
        from agentic_brain.voice.voiceover import test_voiceover_integration
    except ImportError as e:
        print(f"Error: Could not import VoiceOver module: {e}")
        return 1

    test_voiceover_integration()
    return 0


def voice_mode_command(args: argparse.Namespace) -> int:
    """Get or set voice mode."""
    try:
        from agentic_brain.voice.conversation import ConversationalVoice, VoiceMode
    except ImportError as e:
        print(f"Error: Could not import conversation module: {e}")
        return 1

    conv = ConversationalVoice()

    if hasattr(args, "mode") and args.mode:
        # Set mode
        mode_str = args.mode.lower()
        if mode_str in ["work", "boss"]:
            conv.set_mode(VoiceMode.WORK)
            print("✅ Voice mode set to WORK (Karen only)")
        elif mode_str in ["life", "private"]:
            conv.set_mode(VoiceMode.LIFE)
            print("✅ Voice mode set to LIFE (all primary voices)")
        elif mode_str == "quiet":
            conv.set_mode(VoiceMode.QUIET)
            print("✅ Voice mode set to QUIET (minimal output)")
        else:
            print(f"❌ Unknown mode: {mode_str}")
            print("   Valid modes: work, life, quiet")
            return 1
    else:
        # Show current mode
        print(f"\n🎙️  Current voice mode: {conv.config.mode.value.upper()}")
        print(f"   Available voices: {', '.join(conv.get_available_voices())}")

    return 0


def voice_location_command(args: argparse.Namespace) -> int:
    """Show or set location for regional voice."""
    regional = get_regional_voice()

    if hasattr(args, "region") and args.region:
        # Set location
        region_key = args.region.lower()
        available = list_regions()

        if region_key not in available:
            print(f"❌ Unknown region: {region_key}")
            print("\n   Available regions:")
            for r in available:
                print(f"   - {r}")
            return 1

        regional.save_location(region_key)
        regional._load_location()
        print(f"✅ Location set to: {regional.region_name}")
        print(f"   Timezone: {regional.timezone}")
        print(f"\n   Sample greeting: {regional.get_greeting()}")
        return 0

    # Show current location
    print(f"\n📍 Current Location: {regional.region_name}")
    print(f"   Timezone: {regional.timezone}")
    print(f"\n   Greeting: {regional.get_greeting()}")
    print(f"   Farewell: {regional.get_farewell()}")

    # Show some expressions
    if regional.profile and regional.profile.expressions:
        print("\n   Regional Expressions (sample):")
        for standard, regional_expr in list(regional.profile.expressions.items())[:5]:
            print(f"   - '{standard}' → '{regional_expr}'")

    print("\n   Use 'ab voice location <region>' to change location")
    print("   Use 'ab voice expressions' to see all expressions")
    return 0


def voice_expressions_command(args: argparse.Namespace) -> int:
    """List all regional expressions."""
    regional = get_regional_voice()

    if not regional.profile:
        print("❌ No regional profile loaded")
        return 1

    print(f"\n📍 Regional Expressions for {regional.region_name}")
    print("=" * 60)

    if regional.profile.expressions:
        print("\n   Standard → Regional")
        print(f"   {'-'*25}   {'-'*25}")
        for standard, regional_expr in sorted(regional.profile.expressions.items()):
            print(f"   {standard:<25} → {regional_expr}")
    else:
        print("   No expressions defined")

    # Show example
    if regional.profile.expressions:
        print("\n   Example:")
        text = "That is very great! Thank you!"
        regionalized = regional.regionalize(text)
        print(f"   Before: {text}")
        print(f"   After:  {regionalized}")

    return 0


def voice_knowledge_command(args: argparse.Namespace) -> int:
    """Show local knowledge for current region."""
    regional = get_regional_voice()

    if not regional.profile:
        print("❌ No regional profile loaded")
        return 1

    print(f"\n📍 Local Knowledge: {regional.region_name}")
    print("=" * 60)

    knowledge = regional.get_all_local_knowledge()
    if knowledge:
        for topic, info in sorted(knowledge.items()):
            print(f"\n   {topic.replace('_', ' ').title()}:")
            print(f"   {info}")
    else:
        print("   No local knowledge defined")

    return 0


def voice_regions_command(args: argparse.Namespace) -> int:
    """List all available regions."""
    regions = get_available_regions()

    print("\n🌏 Available Regions")
    print("=" * 60)

    # Group by country
    by_country = {}
    for key, profile in regions.items():
        country = profile.country
        if country not in by_country:
            by_country[country] = []
        by_country[country].append((key, profile))

    for country, profiles in sorted(by_country.items()):
        print(f"\n   {country}")
        print(f"   {'-'*40}")
        for key, profile in sorted(profiles, key=lambda x: x[1].city):
            print(f"   {key:<20} - {profile.city}, {profile.state}")

    print("\n   Use 'ab voice location <region>' to select a region")
    return 0


def voice_detect_command(args: argparse.Namespace) -> int:
    """Auto-detect location from system settings."""
    print("\n🔍 Detecting location from system...")

    detected = detect_location()
    print(f"   Detected: {detected}")

    regional = get_regional_voice()
    regional.save_location(detected)
    regional._load_location()

    print(f"\n✅ Location set to: {regional.region_name}")
    print(f"   Greeting: {regional.get_greeting()}")
    return 0


def voice_regionalize_command(args: argparse.Namespace) -> int:
    """Regionalize text."""
    if not hasattr(args, "text") or not args.text:
        print("Error: Please specify text to regionalize")
        print("Usage: ab voice regionalize 'Hello, that is very great!'")
        return 1

    regional = get_regional_voice()
    text = args.text
    regionalized = regional.regionalize(text)

    print(f"\n📍 Regionalized for {regional.region_name}")
    print(f"   Before: {text}")
    print(f"   After:  {regionalized}")

    # Optionally speak it
    if hasattr(args, "speak") and args.speak:
        try:
            from agentic_brain.audio import speak

            print("\n🎙️ Speaking regionalized text...")
            speak(regionalized, voice="Karen (Premium)", rate=160)
        except Exception as e:
            print(f"   (Could not speak: {e})")

    return 0


def voice_llm_command(args: argparse.Namespace) -> int:
    """Generate a short voice-style response using the local LLM.

    This prints text that the main voice system can then speak. Keeping all
    audio output going through a single queue avoids overlapping voices.
    """

    prompt = getattr(args, "prompt", None)
    if not prompt:
        print("Error: Please provide a prompt for the LLM")
        print("Usage: agentic voice llm 'Hello Joseph'")
        return 1

    personality = getattr(args, "personality", "karen")

    try:
        import asyncio

        result = asyncio.run(smart_voice_response(prompt, personality=personality))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            smart_voice_response(prompt, personality=personality)
        )

    print(result)
    return 0


def voice_speed_command(args: argparse.Namespace) -> int:
    """Show or change the adaptive speech rate profile.

    Subargument *profile_or_action* may be:
    - (empty)         → show current profile
    - relaxed/working/focused/power → jump to that tier
    - up              → move one tier faster
    - down            → move one tier slower
    """
    from agentic_brain.voice.speed_profiles import (
        PROFILE_DESCRIPTIONS,
        PROFILE_RATES,
        SpeedProfile,
        get_speed_manager,
    )

    mgr = get_speed_manager()
    action = getattr(args, "profile_or_action", None)

    if not action:
        # Show current state
        print(f"\n⚡ Speech Speed Profile: {mgr.current_profile.value.upper()}")
        print(f"   Rate: {mgr.current_rate} WPM")
        print()
        for profile in SpeedProfile:
            marker = " ▶ " if profile == mgr.current_profile else "   "
            print(f"{marker}{PROFILE_DESCRIPTIONS[profile]}")
        print()
        print("Change with:  ab voice speed <profile|up|down>")
        return 0

    action = action.strip().lower()

    if action == "up":
        if not mgr.can_speed_up():
            print("Already at maximum speed (power, 400 WPM)")
            return 0
        mgr.speed_up()
        print(f"⚡ Speed UP → {mgr.current_profile.value} ({mgr.current_rate} WPM)")
        return 0

    if action == "down":
        if not mgr.can_slow_down():
            print("Already at minimum speed (relaxed, 155 WPM)")
            return 0
        mgr.slow_down()
        print(f"⚡ Speed DOWN → {mgr.current_profile.value} ({mgr.current_rate} WPM)")
        return 0

    # Try direct profile name
    try:
        profile = SpeedProfile(action)
    except ValueError:
        print(f"Unknown speed profile: '{action}'")
        print("Valid: relaxed, working, focused, power, up, down")
        return 1

    mgr.set_profile(profile)
    print(f"⚡ Speed set to {profile.value} ({PROFILE_RATES[profile]} WPM)")
    return 0


def voice_command(args: argparse.Namespace) -> int:
    """Main voice command (shows help if no subcommand)."""
    print("\n🎙️  Agentic Brain Voice System")
    print("=" * 50)
    print("\nCommands:")
    print("  ab voice list              List all voices")
    print("  ab voice list --primary    List primary voice assistants")
    print("  ab voice list --english    List English voices")
    print("  ab voice list -s <term>    Search voices")
    print()
    print("  ab voice test <name>       Test a specific voice")
    print("  ab voice test --all        Test all English voices")
    print()
    print("  ab voice speak 'text'      Speak with default voice")
    print("  ab voice speak 'text' -v Moira  Speak with Moira")
    print()
    print("  ab voice conversation --demo    Demo multi-voice conversation")
    print("  ab voice voiceover         Test VoiceOver integration")
    print("  ab voice mode              Show current voice mode")
    print("  ab voice mode work         Set work mode (Karen only)")
    print("  ab voice mode life         Set life mode (all primary voices)")
    print()
    print("⚡ Speed Profile Commands:")
    print("  ab voice speed             Show current speed profile")
    print("  ab voice speed relaxed     Set relaxed (155 WPM)")
    print("  ab voice speed working     Set working (200 WPM)")
    print("  ab voice speed focused     Set focused (280 WPM)")
    print("  ab voice speed power       Set power   (400 WPM)")
    print("  ab voice speed up          Move up one tier")
    print("  ab voice speed down        Move down one tier")
    print()
    print("📍 Regional Voice Commands:")
    print("  ab voice location          Show current location")
    print("  ab voice location adelaide Set location to Adelaide")
    print("  ab voice regions           List all regions")
    print("  ab voice expressions       Show regional expressions")
    print("  ab voice knowledge         Show local knowledge")
    print("  ab voice detect            Auto-detect location")
    print("  ab voice regionalize 'text' Convert text to regional")
    print()
    print("Examples:")
    print("  ab voice test 'Karen (Premium)'")
    print("  ab voice speak 'Hello Joseph' -v Karen")
    print("  ab voice conversation --demo")
    print("  ab voice mode work")
    print("  ab voice speed focused")
    print("  ab voice location adelaide")
    print("  ab voice regionalize 'That is very great!'")
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
        "--primary",
        action="store_true",
        help="Show only primary voice assistants",
    )
    list_parser.add_argument(
        "--female",
        action="store_true",
        help="Show only female voices",
    )
    list_parser.add_argument(
        "--male",
        action="store_true",
        help="Show only male voices",
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
        "-s",
        "--search",
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
        "-t",
        "--text",
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
        "-v",
        "--voice",
        type=str,
        default="Karen (Premium)",
        help="Voice to use (default: Karen Premium)",
    )
    speak_parser.add_argument(
        "-r",
        "--rate",
        type=int,
        default=160,
        help="Speech rate (default: 160)",
    )
    speak_parser.set_defaults(func=voice_speak_command)

    # voice set
    set_parser = voice_subparsers.add_parser(
        "set",
        help="Set default voice",
    )
    set_parser.add_argument(
        "voice",
        type=str,
        help="Voice name to set (e.g., Karen)",
    )
    set_parser.set_defaults(func=voice_set_command)

    # voice conversation
    conversation_parser = voice_subparsers.add_parser(
        "conversation",
        help="Multi-voice conversation demo",
    )
    conversation_parser.add_argument(
        "--demo",
        action="store_true",
        help="Run conversation demo",
    )
    conversation_parser.set_defaults(func=voice_conversation_command)

    # voice voiceover
    voiceover_parser = voice_subparsers.add_parser(
        "voiceover",
        help="Test VoiceOver integration",
    )
    voiceover_parser.set_defaults(func=voice_voiceover_command)

    # voice mode
    mode_parser = voice_subparsers.add_parser(
        "mode",
        help="Get/set voice mode (work/life/quiet)",
    )
    mode_parser.add_argument(
        "mode",
        nargs="?",
        type=str,
        help="Mode to set: work, life, or quiet",
    )
    mode_parser.set_defaults(func=voice_mode_command)

    # voice speed
    speed_parser = voice_subparsers.add_parser(
        "speed",
        help="Show/set adaptive speech rate profile",
        description=(
            "Adaptive speech rate profiles. "
            "Profiles: relaxed (155 WPM), working (200), focused (280), power (400). "
            "Use 'up'/'down' to shift one tier."
        ),
    )
    speed_parser.add_argument(
        "profile_or_action",
        nargs="?",
        type=str,
        help="Profile name (relaxed/working/focused/power) or action (up/down)",
    )
    speed_parser.set_defaults(func=voice_speed_command)

    # voice location
    location_parser = voice_subparsers.add_parser(
        "location",
        help="Show/set location for regional voice",
    )
    location_parser.add_argument(
        "region",
        nargs="?",
        type=str,
        help="Region to set (e.g., adelaide, melbourne, queensland)",
    )
    location_parser.set_defaults(func=voice_location_command)

    # voice regions
    regions_parser = voice_subparsers.add_parser(
        "regions",
        help="List all available regions",
    )
    regions_parser.set_defaults(func=voice_regions_command)

    # voice expressions
    expressions_parser = voice_subparsers.add_parser(
        "expressions",
        help="Show regional expressions",
    )
    expressions_parser.set_defaults(func=voice_expressions_command)

    # voice knowledge
    knowledge_parser = voice_subparsers.add_parser(
        "knowledge",
        help="Show local knowledge for region",
    )
    knowledge_parser.set_defaults(func=voice_knowledge_command)

    # voice detect
    detect_parser = voice_subparsers.add_parser(
        "detect",
        help="Auto-detect location from system",
    )
    detect_parser.set_defaults(func=voice_detect_command)

    # voice regionalize
    regionalize_parser = voice_subparsers.add_parser(
        "regionalize",
        help="Convert text to regional expressions",
    )
    regionalize_parser.add_argument(
        "text",
        type=str,
        help="Text to regionalize",
    )
    regionalize_parser.add_argument(
        "-s",
        "--speak",
        action="store_true",
        help="Speak the regionalized text",
    )
    regionalize_parser.set_defaults(func=voice_regionalize_command)

    # voice llm
    llm_parser = voice_subparsers.add_parser(
        "llm",
        help="Generate voice-style text using local LLM",
    )
    llm_parser.add_argument(
        "prompt",
        type=str,
        help="Prompt to send to local LLM",
    )
    llm_parser.add_argument(
        "-p",
        "--personality",
        type=str,
        default="karen",
        help="Voice personality to use (karen, daniel, moira)",
    )
    llm_parser.set_defaults(func=voice_llm_command)

    # Default for bare 'ab voice'
    voice_parser.set_defaults(func=voice_command)
