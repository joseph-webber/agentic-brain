# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Windows Voice Support

Provides speech synthesis on Windows using:
1. pyttsx3 (SAPI wrapper) - preferred
2. PowerShell SAPI commands - fallback
3. Direct SAPI COM automation - advanced
"""

import asyncio
import logging
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def speak_windows_pyttsx3(
    text: str, voice: Optional[str] = None, rate: int = 150
) -> bool:
    """
    Speak using pyttsx3 library (SAPI wrapper).

    This is the preferred method as it's pure Python and cross-platform.

    Args:
        text: Text to speak
        voice: Voice name (optional, uses default if not specified)
        rate: Speech rate in words per minute (default 150)

    Returns:
        True if successful, False otherwise
    """
    try:
        import pyttsx3

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()

        def _speak():
            try:
                engine = pyttsx3.init()

                # Set rate (pyttsx3 uses words per minute)
                engine.setProperty("rate", rate)

                # Set voice if specified
                if voice:
                    voices = engine.getProperty("voices")
                    voice_lower = voice.lower()
                    for v in voices:
                        if voice_lower in v.name.lower():
                            engine.setProperty("voice", v.id)
                            break

                engine.say(text)
                engine.runAndWait()
                return True
            except Exception as e:
                logger.error(f"pyttsx3 error: {e}")
                return False

        success = await loop.run_in_executor(None, _speak)
        return success

    except ImportError:
        logger.debug("pyttsx3 not installed")
        return False
    except Exception as e:
        logger.error(f"pyttsx3 speak error: {e}")
        return False


async def speak_windows_powershell(
    text: str, voice: Optional[str] = None, rate: int = 150
) -> bool:
    """
    Speak using PowerShell SAPI commands.

    Fallback method when pyttsx3 is not available.

    Args:
        text: Text to speak
        voice: Voice name (optional)
        rate: Speech rate (default 150, converted to SAPI scale -10 to 10)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Escape text for PowerShell
        safe_text = text.replace('"', '`"').replace("'", "''")

        # Convert rate from words/min to SAPI rate (-10 to 10)
        # 150 WPM = 0 (normal), 200 WPM = +5, 100 WPM = -5
        sapi_rate = max(-10, min(10, (rate - 150) // 10))

        # Build PowerShell script
        script_lines = [
            "Add-Type -AssemblyName System.Speech",
            "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer",
            f"$speak.Rate = {sapi_rate}",
        ]

        # Set voice if specified
        if voice:
            script_lines.append(f'$speak.SelectVoice("{voice}")')

        script_lines.append(f'$speak.Speak("{safe_text}")')

        script = "; ".join(script_lines)

        # Execute PowerShell
        proc = await asyncio.create_subprocess_exec(
            "powershell",
            "-NoProfile",
            "-Command",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await proc.wait()
        return proc.returncode == 0

    except Exception as e:
        logger.error(f"PowerShell speak error: {e}")
        return False


async def speak_windows(
    text: str, voice: Optional[str] = None, rate: int = 150
) -> bool:
    """
    Speak on Windows using best available method.

    Tries methods in order:
    1. pyttsx3 (preferred)
    2. PowerShell SAPI

    Args:
        text: Text to speak
        voice: Voice name (optional)
        rate: Speech rate in words per minute

    Returns:
        True if any method succeeded
    """
    # Try pyttsx3 first (fastest and most reliable)
    if await speak_windows_pyttsx3(text, voice, rate):
        return True

    # Fallback to PowerShell
    if await speak_windows_powershell(text, voice, rate):
        return True

    logger.error("All Windows voice methods failed")
    return False


async def list_windows_voices() -> List[Dict[str, str]]:
    """
    List available Windows SAPI voices.

    Returns:
        List of dicts with voice information (id, name, language)
    """
    voices = []

    try:
        import pyttsx3

        engine = pyttsx3.init()

        for voice in engine.getProperty("voices"):
            voices.append(
                {
                    "id": voice.id,
                    "name": voice.name,
                    "languages": voice.languages,
                    "gender": getattr(voice, "gender", "unknown"),
                    "age": getattr(voice, "age", "unknown"),
                }
            )

        engine.stop()

    except Exception as e:
        logger.error(f"Error listing voices: {e}")

    return voices


def get_default_windows_voice() -> Optional[str]:
    """
    Get the default Windows voice name.

    Returns:
        Voice name or None if cannot determine
    """
    try:
        import pyttsx3

        engine = pyttsx3.init()
        voice_id = engine.getProperty("voice")

        # Find voice name from ID
        for voice in engine.getProperty("voices"):
            if voice.id == voice_id:
                engine.stop()
                return voice.name

        engine.stop()
    except Exception as e:
        logger.error(f"Error getting default voice: {e}")

    return None


if __name__ == "__main__":
    # Test Windows voice
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("Windows Voice Test")
        print("=" * 60)

        # List available voices
        print("\nAvailable Voices:")
        voices = await list_windows_voices()
        for voice in voices:
            print(f"  - {voice['name']}")

        # Test speech
        print("\nTesting speech...")
        text = "Hello! This is the Windows voice system working on your computer."
        success = await speak_windows(text)

        if success:
            print("✓ Speech test successful!")
        else:
            print("✗ Speech test failed!")

        # Test with rate variation
        print("\nTesting different rates...")
        await speak_windows("Slow speech", rate=100)
        await asyncio.sleep(0.5)
        await speak_windows("Normal speech", rate=150)
        await asyncio.sleep(0.5)
        await speak_windows("Fast speech", rate=200)

    asyncio.run(test())
