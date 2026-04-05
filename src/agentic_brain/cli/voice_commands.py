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
    ab voice list --female         List female voices only
    ab voice list --male           List male voices only
    ab voice list --primary        List primary voice assistants
    ab voice test Karen            Test the Karen voice
    ab voice test --all            Test all English voices (short sample)
    ab voice speak "Hello world"   Speak text with default voice
    ab voice speak "Hi" -v Moira   Speak with specific voice

CRITICAL for accessibility - voice output is required for users with visual impairments!
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


def voice_clone_command(args: argparse.Namespace) -> int:
    """Manage local zero-shot voice clones."""
    try:
        from agentic_brain.voice.voice_cloning import VoiceCloner
        from agentic_brain.voice.voice_library import VoiceLibrary
    except ImportError as exc:
        print(f"Error: Could not import voice cloning module: {exc}")
        return 1

    library = VoiceLibrary()
    cloner = VoiceCloner(library=library)

    if getattr(args, "list", False):
        voices = library.list_voices()
        print("\n🧬 Cloned Voices")
        print(f"   Found {len(voices)} voice clone(s)\n")
        if not voices:
            print("   No cloned voices yet.")
            print("   Create one with: ab voice clone sample.wav --name custom_karen")
            return 0

        print(f"   {'Voice ID':<26} {'Name':<24} {'Lady':<12} {'Backend':<16}")
        print(f"   {'-'*26} {'-'*24} {'-'*12} {'-'*16}")
        for profile in voices:
            lady = profile.assigned_lady or "-"
            print(
                f"   {profile.voice_id:<26} {profile.name[:24]:<24} {lady:<12} {profile.backend:<16}"
            )
        return 0

    if getattr(args, "delete", None):
        deleted = library.delete_voice(args.delete)
        if deleted:
            print(f"✅ Deleted cloned voice: {args.delete}")
            return 0
        print(f"❌ Voice not found: {args.delete}")
        return 1

    if getattr(args, "assign", None):
        if not getattr(args, "lady", None):
            print("❌ --lady is required with --assign")
            return 1
        try:
            profile = library.assign_voice(args.assign, args.lady)
        except KeyError:
            print(f"❌ Voice not found: {args.assign}")
            return 1
        except ValueError as exc:
            print(f"❌ {exc}")
            return 1

        print(f"✅ Assigned {profile.voice_id} to lady: {profile.assigned_lady}")
        return 0

    audio_file = getattr(args, "audio_file", None)
    if not audio_file:
        print("Usage: ab voice clone <audio_file> --name custom_karen")
        print("       ab voice clone --list")
        print("       ab voice clone --delete <voice_id>")
        print("       ab voice clone --assign <voice_id> --lady karen")
        return 1

    try:
        voice_id = cloner.clone_voice(
            audio_file,
            name=getattr(args, "name", None),
            reference_text=getattr(args, "reference_text", ""),
            assigned_lady=getattr(args, "lady", None),
        )
    except Exception as exc:
        print(f"❌ Failed to clone voice: {exc}")
        return 1

    profile = library.get_voice(voice_id)
    warnings = profile.validation.get("warnings", []) if profile else []
    print(f"✅ Voice clone created: {voice_id}")
    if profile:
        print(f"   Name: {profile.name}")
        print(f"   Reference: {profile.reference_audio}")
        print(f"   Backend: {profile.backend}")
        if profile.assigned_lady:
            print(f"   Assigned lady: {profile.assigned_lady}")
    if warnings:
        print("   Warnings:")
        for warning in warnings:
            print(f"   - {warning}")
    return 0


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

    voice = args.voice if hasattr(args, "voice") and args.voice else "Samantha"
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
            speak(regionalized, voice="Samantha", rate=160)
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
        print("Usage: agentic voice llm 'Hello'")
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
    - slow/normal/fast/rapid → set content-aware tier
    - up              → move one tier faster
    - down            → move one tier slower
    """
    from agentic_brain.voice.speed_profiles import (
        CONTENT_SPEED_TIERS,
        PROFILE_DESCRIPTIONS,
        PROFILE_RATES,
        TIER_DESCRIPTIONS,
        SpeedProfile,
        get_preference_manager,
        get_speed_manager,
    )

    mgr = get_speed_manager()
    pref_mgr = get_preference_manager()
    action = getattr(args, "profile_or_action", None)
    max_speed = getattr(args, "max_speed", None)
    auto_classify = getattr(args, "auto_classify", False)

    # Handle --max flag
    if max_speed is not None:
        pref_mgr.set_max_speed(max_speed)
        print(f"⚡ Max speed set to {max_speed} WPM")
        return 0

    # Handle --auto flag
    if auto_classify:
        prefs = pref_mgr.preferences
        new_state = not prefs.auto_classify
        pref_mgr.set_auto_classify(new_state)
        state_str = "ENABLED" if new_state else "DISABLED"
        print(f"⚡ Auto-classification {state_str}")
        if new_state:
            print("  Content will be analysed for optimal speed:")
            for _tier, desc in TIER_DESCRIPTIONS.items():
                print(f"    {desc}")
        return 0

    if not action:
        # Show current state
        prefs = pref_mgr.preferences
        print(f"\n⚡ Speech Speed Profile: {mgr.current_profile.value.upper()}")
        print(f"   Rate: {mgr.current_rate} WPM")
        print(f"   Max speed: {prefs.max_speed} WPM")
        print(f"   Auto-classify: {'ON' if prefs.auto_classify else 'OFF'}")
        print()
        for profile in SpeedProfile:
            marker = " ▶ " if profile == mgr.current_profile else "   "
            print(f"{marker}{PROFILE_DESCRIPTIONS[profile]}")
        print()
        print("Content-aware tiers:")
        for _tier, desc in TIER_DESCRIPTIONS.items():
            print(f"   {desc}")
        print()
        print("Change with:  ab voice speed <profile|up|down>")
        print("              ab voice speed --max 300")
        print("              ab voice speed --auto")
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

    # Try content-aware tier name (slow/normal/fast/rapid)
    if action in CONTENT_SPEED_TIERS:
        low, high = CONTENT_SPEED_TIERS[action]
        midpoint = (low + high) // 2
        print(f"⚡ Content speed tier: {action} ({low}-{high} WPM, default {midpoint})")
        print(f"   {TIER_DESCRIPTIONS[action]}")
        return 0

    # Try direct profile name
    try:
        profile = SpeedProfile(action)
    except ValueError:
        print(f"Unknown speed profile: '{action}'")
        print("Valid profiles: relaxed, working, focused, power, up, down")
        print("Valid tiers: slow, normal, fast, rapid")
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
    print("  ab voice speed slow        Show slow tier info (130-150)")
    print("  ab voice speed --max 300   Set maximum WPM")
    print("  ab voice speed --auto      Toggle auto-classification")
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
    print("  ab voice speak 'Hello world' -v Karen")
    print("  ab voice conversation --demo")
    print("  ab voice mode work")
    print("  ab voice speed focused")
    print("  ab voice location adelaide")
    print("  ab voice regionalize 'That is very great!'")
    print()
    print("🔧 Phase 2 Commands:")
    print("  ab voice watchdog          Show worker thread watchdog status")
    print("  ab voice live              Show live voice session status")
    print("  ab voice live start        Start live voice mode (streaming)")
    print("  ab voice live stop         Stop live voice mode")
    print("  ab voice live status       Show live mode status")
    print("  ab voice live --stop       Stop (flag shortcut)")
    print("  ab voice live --status     Status (flag shortcut)")
    print("  ab voice live start --wake-word 'Hey Karen'")
    print("  ab voice live start --timeout 60")
    print("  ab voice live start --transcriber whisper")
    print("  ab voice live start --daemon   Run as background daemon")
    print("  ab voice live install      Install launchd auto-start")
    print("  ab voice live uninstall    Remove launchd auto-start")
    print("  ab voice stream            Show Redpanda stream consumer status")
    print("  ab voice health            Full unified voice system health")
    print()
    print("🧬 Voice Cloning Commands:")
    print("  ab voice clone sample.wav --name custom_karen")
    print("  ab voice clone --list")
    print("  ab voice clone --delete <voice_id>")
    print("  ab voice clone --assign <voice_id> --lady karen")
    print()
    print("📝 Conversation Memory Commands:")
    print("  ab voice history           Show recent utterances")
    print("  ab voice history --lady karen  Filter by lady")
    print("  ab voice repeat            Show last spoken utterance")
    print("  ab voice repeat --speak    Re-speak the last utterance")
    print("  ab voice search 'JIRA'     Search voice history")
    return 0


def voice_watchdog_command(args: argparse.Namespace) -> int:
    """Show voice worker watchdog status."""
    try:
        from agentic_brain.voice.unified import get_unified

        uv = get_unified()
        status = uv.watchdog_status()

        print("\n🐕 Voice Worker Watchdog")
        print("=" * 50)

        if not status.get("available"):
            print(f"   Status: UNAVAILABLE ({status.get('reason', 'unknown')})")
            return 0

        running = status.get("running", False)
        alive = status.get("worker_alive", False)
        restarts = status.get("total_restarts", 0)
        hb_age = status.get("last_heartbeat_age_s", -1)

        icon = "✅" if running and alive else "⚠️"
        print(f"   {icon} Running: {running}")
        print(f"   Worker alive: {alive}")
        print(f"   Total restarts: {restarts}")
        print(f"   Last heartbeat: {hb_age}s ago")

        if restarts > 0:
            print(f"\n   ⚠️  Worker has been restarted {restarts} time(s)")

        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def voice_live_command(args: argparse.Namespace) -> int:
    """Start/stop/status for live voice conversation (Project Aria).

    This connects to the bidirectional live session (listen + respond)
    powered by whisper.cpp for local offline transcription.

    Supports both in-process sessions and daemon mode (background
    listening with PID file management).
    """
    action = getattr(args, "action", "status").lower()
    use_daemon = getattr(args, "daemon", False)

    # ── --stop flag shortcut ─────────────────────────────────────
    if getattr(args, "stop", False):
        action = "stop"

    # ── --status flag shortcut ───────────────────────────────────
    if getattr(args, "status_flag", False):
        action = "status"

    # ── Collect options from flags ───────────────────────────────
    wake_word = getattr(args, "wake_word", None)
    timeout_val = getattr(args, "timeout", None)
    transcriber = getattr(args, "transcriber", None)
    voice = getattr(args, "voice", "Samantha") or "Samantha"
    rate = getattr(args, "rate", 160) or 160

    # Build wake-words tuple
    default_wake_words = ("hey karen", "hey brain")
    if wake_word:
        wake_words = tuple(w.strip().lower() for w in wake_word.split(","))
    else:
        wake_words = default_wake_words

    session_timeout = float(timeout_val) if timeout_val else 30.0
    use_whisper = (
        transcriber != "macos"
    )  # default to whisper unless --transcriber macos

    try:
        if use_daemon and action in ("start", "stop", "status"):
            return _live_daemon_command(
                action=action,
                voice=voice,
                rate=rate,
                wake_words=wake_words,
                session_timeout=session_timeout,
                use_whisper=use_whisper,
            )

        # Non-daemon: in-process session
        from agentic_brain.voice.live_session import (
            live_session_status,
            start_live_session,
            stop_live_session,
        )

        if action == "start":
            result = start_live_session(
                voice=voice,
                rate=rate,
                require_wake_word=True,
                session_timeout=session_timeout,
            )
            if "error" in result:
                print(f"❌ {result['error']}")
                return 1
            state = result.get("state", "unknown")
            print(
                f"✅ Live voice session started "
                f"(state={state}, voice={voice}, rate={rate})"
            )
            print(f"   Wake words: {', '.join(wake_words)}")
            print(f"   Timeout: {session_timeout:.0f}s of silence")
            print(
                f"   Transcriber: {'whisper.cpp' if use_whisper else 'macOS dictation'}"
            )
            return 0

        elif action == "stop":
            result = stop_live_session()
            state = result.get("state", "idle")
            metrics = result.get("metrics", {})
            print("✅ Live voice session stopped")
            print(f"   Utterances: {metrics.get('utterances_heard', 0)}")
            print(f"   Responses: {metrics.get('responses_given', 0)}")
            print(f"   Interrupts: {metrics.get('interrupts', 0)}")
            latency = metrics.get("avg_response_latency_ms", 0)
            if latency:
                print(f"   Avg latency: {latency:.0f}ms")
            return 0

        elif action == "install":
            return _live_launchd_install()

        elif action == "uninstall":
            return _live_launchd_uninstall()

        else:
            # status (default)
            result = live_session_status()
            _print_live_status(result)
            return 0

    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("   Install: pip install pyaudio pywhispercpp")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def _live_daemon_command(
    action: str,
    voice: str,
    rate: int,
    wake_words: tuple[str, ...],
    session_timeout: float,
    use_whisper: bool,
) -> int:
    """Handle daemon-mode live voice commands."""
    from agentic_brain.voice.live_daemon import (
        DaemonConfig,
        daemon_status,
        start_daemon,
        stop_daemon,
    )

    if action == "start":
        cfg = DaemonConfig(
            wake_words=wake_words,
            session_timeout=session_timeout,
            voice=voice,
            rate=rate,
            use_whisper=use_whisper,
        )
        result = start_daemon(cfg)
        if not result.get("ok"):
            print(f"❌ {result.get('error', 'Failed to start daemon')}")
            return 1
        print(f"✅ Live voice daemon started (PID {result.get('pid', '?')})")
        print(f"   Wake words: {', '.join(wake_words)}")
        print(f"   Timeout: {session_timeout:.0f}s")
        print(f"   Transcriber: {'whisper.cpp' if use_whisper else 'macOS dictation'}")
        return 0

    elif action == "stop":
        result = stop_daemon()
        print("✅ Live voice daemon stopped")
        return 0

    else:
        result = daemon_status()
        _print_daemon_status(result)
        return 0


def _print_live_status(result: dict) -> None:
    """Pretty-print live session status."""
    print("\n🎙️  Live Voice Session (Project Aria)")
    print("=" * 50)
    state = result.get("state", "idle")
    icon = "🟢" if state not in ("idle", "error") else "⚪"
    print(f"   {icon} State: {state}")

    config = result.get("config", {})
    if config:
        print(f"   Voice: {config.get('voice', 'Samantha')}")
        print(f"   Rate: {config.get('rate', 155)}")
        wake = config.get("wake_words", [])
        print(f"   Wake words: {', '.join(wake)}")
        print(f"   Timeout: {config.get('session_timeout_secs', 30)}s")
        print(
            f"   Transcriber: "
            f"{'whisper.cpp' if config.get('use_whisper', True) else 'macOS dictation'}"
        )

    metrics = result.get("metrics", {})
    if metrics and metrics.get("utterances_heard", 0) > 0:
        print(f"\n   Utterances: {metrics.get('utterances_heard', 0)}")
        print(f"   Responses: {metrics.get('responses_given', 0)}")
        latency = metrics.get("avg_response_latency_ms", 0)
        print(f"   Avg latency: {latency:.0f}ms")


def _print_daemon_status(result: dict) -> None:
    """Pretty-print daemon status."""
    print("\n🎙️  Live Voice Daemon (Project Aria)")
    print("=" * 50)
    running = result.get("daemon_running", False)
    icon = "🟢" if running else "⚪"
    print(f"   {icon} Running: {running}")
    if running:
        print(f"   PID: {result.get('pid', '?')}")
        print(f"   Uptime: {result.get('uptime_s', 0)}s")
    session = result.get("session", {})
    if session:
        print(f"   Session state: {session.get('state', 'unknown')}")


def _live_launchd_install() -> int:
    """Install the launchd plist for auto-start."""
    from agentic_brain.voice.live_daemon import install_launchd_plist

    result = install_launchd_plist()
    if not result.get("ok"):
        print(f"❌ {result.get('error', 'Failed')}")
        return 1
    print(f"✅ Launchd plist installed: {result['path']}")
    print(f"   Load:   {result['load_command']}")
    print(f"   Unload: {result['unload_command']}")
    return 0


def _live_launchd_uninstall() -> int:
    """Uninstall the launchd plist."""
    from agentic_brain.voice.live_daemon import uninstall_launchd_plist

    result = uninstall_launchd_plist()
    if not result.get("ok"):
        print(f"❌ {result.get('error', 'Failed')}")
        return 1
    print("✅ Launchd plist removed")
    return 0


def voice_stream_command(args: argparse.Namespace) -> int:
    """Show Redpanka voice stream consumer status."""
    try:
        from agentic_brain.voice.unified import get_unified

        uv = get_unified()
        status = uv.stream_status()

        print("\n📡 Voice Stream Consumer (Redpanda)")
        print("=" * 50)

        if not status.get("available"):
            print(f"   Status: UNAVAILABLE ({status.get('reason', 'unknown')})")
            print("   Install aiokafka: pip install aiokafka")
            return 0

        running = status.get("running", False)
        icon = "🟢" if running else "⚪"
        print(f"   {icon} Running: {running}")
        print(f"   Topic: {status.get('topic', 'N/A')}")
        print(f"   Bootstrap: {status.get('bootstrap', 'N/A')}")
        print(f"   Messages received: {status.get('messages_received', 0)}")
        print(f"   Messages spoken: {status.get('messages_spoken', 0)}")
        print(f"   Messages failed: {status.get('messages_failed', 0)}")
        print(f"   Uptime: {status.get('uptime_s', 0)}s")

        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def voice_health_command(args: argparse.Namespace) -> int:
    """Show unified voice system health."""
    try:
        from agentic_brain.voice.unified import get_unified

        uv = get_unified()
        report = uv.status()

        print()
        print(report["summary"])
        print()

        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


# ── Conversation memory CLI commands ─────────────────────────────────


def voice_history_command(args: argparse.Namespace) -> int:
    """Show recent voice utterance history."""
    from agentic_brain.voice.conversation_memory import get_conversation_memory

    mem = get_conversation_memory()
    lady = getattr(args, "lady", None)
    count = getattr(args, "count", 20)

    recent = mem.get_recent(lady=lady, count=count)

    if not recent:
        if lady:
            print(f"No voice history for {lady}.")
        else:
            print("No voice history yet.")
        return 0

    title = f"Voice History ({lady})" if lady else "Voice History (all)"
    print(f"\n🎙️  {title}")
    print(f"   Showing {len(recent)} utterance(s)\n")
    print(f"   {'Time':<12} {'Lady':<12} {'Text'}")
    print(f"   {'-'*12} {'-'*12} {'-'*50}")

    import time as _time

    for utt in recent:
        age = utt.age_seconds()
        if age < 60:
            age_str = f"{age:.0f}s ago"
        elif age < 3600:
            age_str = f"{age / 60:.0f}m ago"
        else:
            age_str = _time.strftime("%H:%M:%S", _time.localtime(utt.timestamp))
        text_preview = utt.text[:60] + ("…" if len(utt.text) > 60 else "")
        print(f"   {age_str:<12} {utt.lady:<12} {text_preview}")

    print()
    health = mem.health()
    print(
        f"   Total: {health['in_memory_count']} | Redis: {'✓' if health['redis_available'] else '✗'}"
    )
    return 0


def voice_repeat_command(args: argparse.Namespace) -> int:
    """Repeat the last spoken utterance or a specific lady's last utterance."""
    from agentic_brain.voice.conversation_memory import get_conversation_memory

    mem = get_conversation_memory()
    lady = getattr(args, "lady", None)
    last = mem.get_last(lady=lady)

    if last is None:
        print("Nothing to repeat – no voice history.")
        return 1

    print(f"🔁 Last ({last.lady}): {last.text}")

    # Optionally re-speak it
    if getattr(args, "speak", False):
        try:
            from agentic_brain.voice import speak_safe

            speak_safe(last.text, voice=last.voice or "Samantha", rate=last.rate or 155)
        except Exception as e:
            print(f"   (Could not speak: {e})")
    return 0


def voice_search_command(args: argparse.Namespace) -> int:
    """Search voice history for a keyword."""
    from agentic_brain.voice.conversation_memory import get_conversation_memory

    query = getattr(args, "query", None)
    if not query:
        print("Error: Please specify a search query")
        print("Usage: ab voice search 'JIRA'")
        return 1

    mem = get_conversation_memory()
    limit = getattr(args, "limit", 20)
    results = mem.search(query, limit=limit)

    if not results:
        print(f"No voice history matching '{query}'.")
        return 0

    print(f"\n🔍 Voice Search: '{query}'")
    print(f"   Found {len(results)} match(es)\n")

    import time as _time

    for utt in results:
        ts_str = _time.strftime("%H:%M:%S", _time.localtime(utt.timestamp))
        text_preview = utt.text[:60] + ("…" if len(utt.text) > 60 else "")
        print(f"   [{ts_str}] {utt.lady}: {text_preview}")

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
        default="Samantha",
        help="Voice to use (default: Samantha)",
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
            "Content tiers: slow (130-150), normal (155-180), fast (200-250), rapid (300-400). "
            "Use 'up'/'down' to shift one tier."
        ),
    )
    speed_parser.add_argument(
        "profile_or_action",
        nargs="?",
        type=str,
        help="Profile (relaxed/working/focused/power), tier (slow/normal/fast/rapid), or action (up/down)",
    )
    speed_parser.add_argument(
        "--max",
        dest="max_speed",
        type=int,
        default=None,
        metavar="WPM",
        help="Set maximum speech speed in WPM (e.g. --max 300)",
    )
    speed_parser.add_argument(
        "--auto",
        dest="auto_classify",
        action="store_true",
        default=False,
        help="Toggle auto-classification (content-aware speed)",
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

    # voice clone
    clone_parser = voice_subparsers.add_parser(
        "clone",
        help="Manage local F5-TTS voice clones",
        description=(
            "Create and manage local voice clones. "
            "F5-TTS is optional and used when installed; otherwise clones are stored "
            "locally for later use with graceful fallback synthesis."
        ),
    )
    clone_parser.add_argument(
        "audio_file",
        nargs="?",
        type=str,
        help="Reference audio file to clone",
    )
    clone_parser.add_argument(
        "--name",
        type=str,
        help="Human-friendly clone name (e.g. custom_karen)",
    )
    clone_parser.add_argument(
        "--reference-text",
        type=str,
        default="",
        help="Optional transcription of the reference audio",
    )
    clone_parser.add_argument(
        "--list",
        action="store_true",
        help="List available cloned voices",
    )
    clone_parser.add_argument(
        "--delete",
        type=str,
        metavar="VOICE_ID",
        help="Delete a cloned voice",
    )
    clone_parser.add_argument(
        "--assign",
        type=str,
        metavar="VOICE_ID",
        help="Assign a cloned voice to a lady",
    )
    clone_parser.add_argument(
        "--lady",
        type=str,
        help="Lady name for --assign or initial clone association",
    )
    clone_parser.set_defaults(func=voice_clone_command)

    # Default for bare 'ab voice'
    voice_parser.set_defaults(func=voice_command)

    # ── Phase 2 CLI Commands ─────────────────────────────────────────

    # voice watchdog
    watchdog_parser = voice_subparsers.add_parser(
        "watchdog",
        help="Show voice worker watchdog status",
    )
    watchdog_parser.set_defaults(func=voice_watchdog_command)

    # voice live
    live_parser = voice_subparsers.add_parser(
        "live",
        help="Start/stop live voice mode (Project Aria)",
        description=(
            "Live voice conversation powered by whisper.cpp (offline) "
            "or macOS dictation (fallback). Listens for wake words, "
            "transcribes speech, and responds via the voice serializer."
        ),
    )
    live_parser.add_argument(
        "action",
        nargs="?",
        type=str,
        default="status",
        choices=["start", "stop", "status", "install", "uninstall"],
        help="Action: start, stop, status, install, uninstall (default: status)",
    )
    live_parser.add_argument(
        "-v",
        "--voice",
        type=str,
        default="Samantha",
        help="Voice for live mode (default: Samantha)",
    )
    live_parser.add_argument(
        "-r",
        "--rate",
        type=int,
        default=160,
        help="Speech rate for live mode (default: 160)",
    )
    live_parser.add_argument(
        "-w",
        "--wake-word",
        type=str,
        default=None,
        help="Wake word(s), comma-separated (default: 'hey karen,hey brain')",
    )
    live_parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=None,
        help="Session timeout in seconds of silence (default: 30)",
    )
    live_parser.add_argument(
        "--transcriber",
        type=str,
        choices=["whisper", "macos"],
        default=None,
        help="Transcription backend: whisper (offline) or macos (dictation)",
    )
    live_parser.add_argument(
        "--daemon",
        action="store_true",
        default=False,
        help="Run as background daemon with PID file management",
    )
    live_parser.add_argument(
        "--stop",
        action="store_true",
        default=False,
        help="Stop the live session (shortcut for 'ab voice live stop')",
    )
    live_parser.add_argument(
        "--status",
        action="store_true",
        default=False,
        dest="status_flag",
        help="Show status (shortcut for 'ab voice live status')",
    )
    live_parser.set_defaults(func=voice_live_command)

    # voice stream
    stream_parser = voice_subparsers.add_parser(
        "stream",
        help="Show Redpanda voice stream consumer status",
    )
    stream_parser.set_defaults(func=voice_stream_command)

    # voice health
    health_parser = voice_subparsers.add_parser(
        "health",
        help="Show unified voice system health",
    )
    health_parser.set_defaults(func=voice_health_command)

    # voice history
    history_parser = voice_subparsers.add_parser(
        "history",
        help="Show recent voice utterance history",
    )
    history_parser.add_argument(
        "--lady",
        type=str,
        default=None,
        help="Filter by lady name (e.g., karen, moira)",
    )
    history_parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=20,
        help="Number of utterances to show (default: 20)",
    )
    history_parser.set_defaults(func=voice_history_command)

    # voice repeat
    repeat_parser = voice_subparsers.add_parser(
        "repeat",
        help="Repeat the last spoken utterance",
    )
    repeat_parser.add_argument(
        "--lady",
        type=str,
        default=None,
        help="Repeat last utterance from a specific lady",
    )
    repeat_parser.add_argument(
        "--speak",
        action="store_true",
        default=False,
        help="Re-speak the utterance aloud",
    )
    repeat_parser.set_defaults(func=voice_repeat_command)

    # voice search
    search_parser = voice_subparsers.add_parser(
        "search",
        help="Search voice history for a keyword",
    )
    search_parser.add_argument(
        "query",
        type=str,
        help="Search term (e.g., 'JIRA', 'morning')",
    )
    search_parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=20,
        help="Max results (default: 20)",
    )
    search_parser.set_defaults(func=voice_search_command)
