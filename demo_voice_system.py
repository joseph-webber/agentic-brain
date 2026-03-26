#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Voice System Demo and Test Script

Demonstrates all features of the world-class voice system:
- 145+ macOS voices
- Joseph's primary voice assistants
- Conversational multi-voice
- VoiceOver integration
- Work/Life/Quiet modes
"""

import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentic_brain.voice.registry import (
    get_voice_stats,
    get_primary_voices,
    get_english_voices,
    get_premium_voices,
    get_voice,
)

from agentic_brain.voice.conversation import ConversationalVoice, VoiceMode

from agentic_brain.voice.voiceover import VoiceOverCoordinator, format_for_voiceover


def print_banner(title: str):
    """Print a fancy banner."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_registry():
    """Demo the voice registry."""
    print_banner("🎙️  VOICE REGISTRY - All 145+ macOS Voices")

    stats = get_voice_stats()
    print(f"\n📊 Statistics:")
    print(f"   Total voices: {stats['total']}")
    print(f"   Primary voices: {stats['primary']}")
    print(f"   English voices: {stats['english']}")
    print(f"   Premium voices: {stats['premium']}")
    print(f"   Novelty voices: {stats['novelty']}")
    print(f"   Languages: {stats['languages']}")

    print(f"\n🎙️ Primary Voice Assistants:")
    for voice in get_primary_voices():
        print(f"   • {voice.name:15} - {voice.language_name:25} - {voice.description}")

    print(f"\n🎖️  Premium English Voices (sample):")
    premium_english = [v for v in get_english_voices() if v.quality.value == "premium"][
        :5
    ]
    for voice in premium_english:
        print(f"   • {voice.full_name:25} - {voice.region}")

    print("\n✅ Registry loaded successfully!")


def demo_conversation():
    """Demo conversational voice."""
    print_banner("💬 CONVERSATIONAL VOICE - Multi-Voice Conversations")

    conv = ConversationalVoice()

    print(f"\n🎭 Current mode: {conv.config.mode.value.upper()}")
    print(f"   Available voices: {', '.join(conv.get_available_voices())}")

    print("\n🎙️  Running conversation demo...")
    print("   (This will speak aloud - make sure speakers are on!)\n")

    time.sleep(1)

    # Demo conversation
    if conv.config.mode == VoiceMode.WORK:
        conv.conversation(
            [
                ("Karen", "This is work mode - professional and focused."),
                ("Karen", "Only Karen speaks in work mode, perfect for client calls."),
            ]
        )
    else:
        conv.conversation(
            [
                ("Karen", "Welcome! Let me introduce the team."),
                ("Moira", "Hello! I'm Moira from Ireland, your creative assistant."),
                (
                    "Tingting",
                    "Hi! Tingting here from China, code reviews are my specialty.",
                ),
                ("Damayanti", "Greetings from Bali! I handle project management."),
                ("Karen", "Together, we make the brain conversational and alive!"),
            ]
        )

    print("\n✅ Conversation demo complete!")


def demo_voiceover():
    """Demo VoiceOver integration."""
    print_banner("♿ VOICEOVER INTEGRATION - Accessibility First")

    coord = VoiceOverCoordinator()

    print(f"\n📡 VoiceOver Status:")
    print(f"   Running: {coord.is_voiceover_running()}")
    print(f"   Speaking: {coord.is_voiceover_speaking()}")

    if coord.is_voiceover_running():
        print("\n✅ VoiceOver detected! Testing coordination...")
        coord.speak_coordinated("This speech is coordinated with VoiceOver!")
    else:
        print("\n⚠️  VoiceOver not detected (that's okay for testing)")
        print("   Enable VoiceOver in System Settings > Accessibility")

    print(f"\n🎯 VoiceOver Text Formatting:")
    test_text = "Hello 🎉 **bold** and *italic* text!"
    formatted = format_for_voiceover(test_text)
    print(f"   Original: {test_text}")
    print(f"   Formatted: {formatted}")

    print("\n✅ VoiceOver integration ready!")


def demo_modes():
    """Demo voice modes."""
    print_banner("🎭 VOICE MODES - Work / Life / Quiet")

    conv = ConversationalVoice()

    print("\n🔧 WORK MODE (Professional, Karen only)")
    conv.set_mode(VoiceMode.WORK)
    print(f"   Voices: {conv.get_available_voices()}")
    conv.speak("Work mode active. Professional and focused.", voice="Karen")
    time.sleep(1)

    print("\n💜 LIFE MODE (All primary voices, fun and learning)")
    conv.set_mode(VoiceMode.LIFE)
    print(f"   Voices: {', '.join(conv.get_available_voices())}")
    conv.speak("Life mode active! All primary voices ready!", voice="Karen")
    time.sleep(1)

    print("\n🔇 QUIET MODE (Minimal output)")
    conv.set_mode(VoiceMode.QUIET)
    print(f"   Voices: {conv.get_available_voices()}")
    print("   [Quiet mode - no speech]")

    # Restore to life mode
    conv.set_mode(VoiceMode.LIFE)

    print("\n✅ Mode switching works perfectly!")


def demo_cli():
    """Show CLI commands."""
    print_banner("⌨️  CLI COMMANDS - How to Use")

    print("\n📋 Available Commands:")
    print("\n   Voice Registry:")
    print("   $ ab voice list              # All voices")
    print("   $ ab voice list --primary    # Primary voice assistants")
    print("   $ ab voice list --english    # English voices only")
    print("   $ ab voice test Karen        # Test a voice")

    print("\n   Conversation:")
    print("   $ ab voice conversation --demo   # Multi-voice demo")
    print("   $ ab voice speak 'Hello!'        # Speak with Karen")
    print("   $ ab voice speak 'Hi!' -v Moira  # Speak with Moira")

    print("\n   Modes:")
    print("   $ ab voice mode              # Show current mode")
    print("   $ ab voice mode work         # Set work mode")
    print("   $ ab voice mode life         # Set life mode")

    print("\n   VoiceOver:")
    print("   $ ab voice voiceover         # Test VoiceOver integration")

    print("\n✅ Full CLI ready!")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("  🎙️  AGENTIC BRAIN - WORLD CLASS VOICE SYSTEM")
    print("  Built for Joseph's Accessibility")
    print("=" * 70)

    try:
        demo_registry()
        time.sleep(2)

        demo_conversation()
        time.sleep(2)

        demo_voiceover()
        time.sleep(2)

        demo_modes()
        time.sleep(2)

        demo_cli()

        print("\n" + "=" * 70)
        print("  ✅ ALL DEMOS COMPLETE!")
        print("  🎉 Voice system is WORLD CLASS!")
        print("=" * 70)

        # Final announcement
        from agentic_brain.voice.conversation import speak

        speak(
            "Voice system demo complete! World class accessibility achieved!",
            voice="Karen",
        )

    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
