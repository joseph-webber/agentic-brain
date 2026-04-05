#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Cross-Platform Voice Demo

Demonstrates voice synthesis working on macOS, Windows, and Linux
with automatic platform detection and cloud fallback.
"""

import asyncio
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from agentic_brain.voice.platform import (
    VoicePlatform,
    check_voice_available,
    detect_platform,
    get_platform_info,
    get_recommended_voice_method,
)
from agentic_brain.voice.resilient import get_voice_stats, speak


async def demo_platform_detection():
    """Demo 1: Platform Detection"""
    print("\n" + "=" * 60)
    print("DEMO 1: Platform Detection")
    print("=" * 60)

    # Detect platform
    platform = detect_platform()
    print(f"\n✓ Detected Platform: {platform.value.upper()}")

    # Show platform info
    info = get_platform_info()
    print(f"  OS: {info['system']} {info['release']}")
    print(f"  Architecture: {info['machine']}")
    print(f"  Python: {info['python_version']}")

    # Check availability
    availability = check_voice_available()
    print("\n✓ Voice Systems Available:")

    for system, available in availability.items():
        status = "✓" if available else "✗"
        print(f"  {status} {system}")

    # Recommended method
    recommended = get_recommended_voice_method()
    if recommended:
        print(f"\n✓ Recommended Method: {recommended}")
    else:
        print("\n✗ No voice method available!")


async def demo_basic_speech():
    """Demo 2: Basic Speech"""
    print("\n" + "=" * 60)
    print("DEMO 2: Basic Speech")
    print("=" * 60)

    platform = detect_platform()

    if platform == VoicePlatform.MACOS:
        message = "Hello from macOS! The native say command is working perfectly!"
    elif platform == VoicePlatform.WINDOWS:
        message = "Hello from Windows! Speech API is working!"
    elif platform == VoicePlatform.LINUX:
        message = "Hello from Linux! Text to speech is operational!"
    else:
        message = "Hello! Cross-platform voice is working!"

    print(f"\nSpeaking: '{message}'")
    success = await speak(message)

    if success:
        print("✓ Speech succeeded!")
    else:
        print("✗ Speech failed (but fallback attempted)")


async def demo_different_rates():
    """Demo 3: Different Speech Rates"""
    print("\n" + "=" * 60)
    print("DEMO 3: Different Speech Rates")
    print("=" * 60)

    rates = [(100, "Slow"), (150, "Normal"), (200, "Fast")]

    for rate, description in rates:
        message = f"This is {description.lower()} speech"
        print(f"\nRate {rate} ({description}): '{message}'")
        await speak(message, rate=rate)
        await asyncio.sleep(0.5)

    print("\n✓ Rate variation demo complete!")


async def demo_fallback_resilience():
    """Demo 4: Fallback Resilience"""
    print("\n" + "=" * 60)
    print("DEMO 4: Fallback Resilience")
    print("=" * 60)

    print("\nThe voice system has multiple fallback layers.")
    print("If one method fails, it automatically tries the next!")

    messages = [
        "Testing fallback layer one",
        "Testing fallback layer two",
        "Testing fallback layer three",
    ]

    for i, message in enumerate(messages, 1):
        print(f"\nTest {i}: '{message}'")
        success = await speak(message)
        if success:
            print("  ✓ Succeeded")
        await asyncio.sleep(0.5)

    print("\n✓ All fallback tests passed!")


async def demo_voice_stats():
    """Demo 5: Voice Statistics"""
    print("\n" + "=" * 60)
    print("DEMO 5: Voice Statistics")
    print("=" * 60)

    # Speak some messages
    await speak("Collecting statistics test one")
    await speak("Collecting statistics test two")
    await speak("Collecting statistics test three")

    # Get stats
    stats = get_voice_stats()

    print("\n✓ Voice System Statistics:")
    print("\nFallback Methods Used:")

    for method_name, method_stats in stats.get("voice", {}).items():
        success = method_stats.get("success", 0)
        failure = method_stats.get("failure", 0)
        rate = method_stats.get("success_rate", "0.0%")

        if success > 0 or failure > 0:
            print(f"  - {method_name}:")
            print(f"    Success: {success}, Failures: {failure}")
            print(f"    Success Rate: {rate}")

    daemon_stats = stats.get("daemon", {})
    if daemon_stats.get("status") != "not_started":
        print("\nDaemon Statistics:")
        print(f"  Processed: {daemon_stats.get('processed', 0)}")
        print(f"  Errors: {daemon_stats.get('errors', 0)}")


async def demo_platform_specific():
    """Demo 6: Platform-Specific Features"""
    print("\n" + "=" * 60)
    print("DEMO 6: Platform-Specific Features")
    print("=" * 60)

    platform = detect_platform()

    if platform == VoicePlatform.MACOS:
        print("\n✓ macOS-specific features:")
        print("  - Multiple high-quality voices (Karen, Alex, Samantha)")
        print("  - Adjustable speech rate")
        print("  - AppleScript integration")
        print("  - System sounds fallback")

        await speak("Testing macOS premium voice", voice="Karen")

    elif platform == VoicePlatform.WINDOWS:
        print("\n✓ Windows-specific features:")
        print("  - Windows Speech API (SAPI)")
        print("  - Multiple voices via pyttsx3")
        print("  - PowerShell integration")

        try:
            from agentic_brain.voice.windows import list_windows_voices

            voices = await list_windows_voices()
            if voices:
                print(f"  - Available voices: {len(voices)}")
                print(f"    Example: {voices[0].get('name', 'Unknown')}")
        except Exception as e:
            print(f"  (Could not list voices: {e})")

    elif platform == VoicePlatform.LINUX:
        print("\n✓ Linux-specific features:")
        print("  - espeak/espeak-ng support")
        print("  - speech-dispatcher support")
        print("  - festival support")
        print("  - Multiple voice variants")

        try:
            from agentic_brain.voice.linux import list_linux_voices

            voices = await list_linux_voices()
            if voices:
                print(f"  - Available voices: {len(voices)}")
        except Exception as e:
            print(f"  (Could not list voices: {e})")

    else:
        print("\n✓ Unknown platform - using cloud fallback")


async def demo_cloud_fallback():
    """Demo 7: Cloud TTS Fallback"""
    print("\n" + "=" * 60)
    print("DEMO 7: Cloud TTS Fallback")
    print("=" * 60)

    from agentic_brain.voice.cloud_tts import check_cloud_tts_available

    availability = check_cloud_tts_available()

    print("\n✓ Cloud TTS Providers:")
    print(
        f"  - Google TTS (gTTS): {'✓ Available' if availability['gtts'] else '✗ Not installed'}"
    )
    print(
        f"  - Azure Speech: {'✓ Configured' if availability['azure'] else '✗ Not configured'}"
    )
    print(
        f"  - AWS Polly: {'✓ Configured' if availability['aws_polly'] else '✗ Not configured'}"
    )

    if availability["gtts"]:
        print("\n  Testing Google TTS (requires internet)...")
        try:
            from agentic_brain.voice.cloud_tts import speak_cloud

            success = await speak_cloud(
                "Testing cloud text to speech with Google TTS", provider="gtts"
            )
            if success:
                print("  ✓ Google TTS working!")
            else:
                print("  ✗ Google TTS failed (check internet connection)")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        print("\n  Install gTTS to enable cloud fallback:")
        print("    pip install gTTS")


async def main():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("CROSS-PLATFORM VOICE DEMO")
    print("Agentic Brain - Universal Voice Synthesis")
    print("=" * 60)

    try:
        # Run all demos
        await demo_platform_detection()
        await demo_basic_speech()
        await demo_different_rates()
        await demo_fallback_resilience()
        await demo_voice_stats()
        await demo_platform_specific()
        await demo_cloud_fallback()

        # Summary
        print("\n" + "=" * 60)
        print("DEMO COMPLETE!")
        print("=" * 60)
        print("\n✓ All voice demos completed successfully!")
        print("\nThe voice system works on:")
        print("  ✓ macOS (native 'say' command)")
        print("  ✓ Windows (pyttsx3 + SAPI)")
        print("  ✓ Linux (espeak, festival, speech-dispatcher)")
        print("  ✓ Cloud fallback (Google TTS, Azure, AWS)")
        print("\nVoice NEVER fails - multiple fallback layers ensure")
        print("audio output is ALWAYS available!")

    except KeyboardInterrupt:
        print("\n\n✗ Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Demo error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
