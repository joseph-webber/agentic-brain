# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Linux Voice Support

Provides speech synthesis on Linux using:
1. pyttsx3 (preferred, uses espeak backend)
2. espeak/espeak-ng (direct command)
3. speech-dispatcher (spd-say)
4. festival (older TTS engine)
"""

import asyncio
import logging
import shutil
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def speak_linux_pyttsx3(
    text: str, voice: Optional[str] = None, rate: int = 150
) -> bool:
    """
    Speak using pyttsx3 (uses espeak backend on Linux).

    Args:
        text: Text to speak
        voice: Voice name (optional)
        rate: Speech rate in words per minute

    Returns:
        True if successful
    """
    try:
        import pyttsx3

        loop = asyncio.get_event_loop()

        def _speak():
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", rate)

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

        return await loop.run_in_executor(None, _speak)

    except ImportError:
        logger.debug("pyttsx3 not installed")
        return False
    except Exception as e:
        logger.error(f"pyttsx3 speak error: {e}")
        return False


async def speak_linux_espeak(
    text: str, voice: Optional[str] = None, rate: int = 150
) -> bool:
    """
    Speak using espeak/espeak-ng command.

    espeak is a compact open source software speech synthesizer.

    Args:
        text: Text to speak
        voice: Voice variant (e.g., 'en', 'en-us', 'en-gb')
        rate: Speech rate in words per minute (80-450, default 175)

    Returns:
        True if successful
    """
    # Check for espeak or espeak-ng
    espeak_cmd = None
    if shutil.which("espeak-ng"):
        espeak_cmd = "espeak-ng"
    elif shutil.which("espeak"):
        espeak_cmd = "espeak"
    else:
        logger.debug("espeak not found")
        return False

    try:
        cmd = [espeak_cmd, "-s", str(rate)]

        if voice:
            cmd.extend(["-v", voice])

        cmd.append(text)

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        await proc.wait()
        return proc.returncode == 0

    except Exception as e:
        logger.error(f"espeak error: {e}")
        return False


async def speak_linux_spd_say(
    text: str, voice: Optional[str] = None, rate: int = 150
) -> bool:
    """
    Speak using speech-dispatcher (spd-say).

    speech-dispatcher is a common interface to speech synthesis.

    Args:
        text: Text to speak
        voice: Voice type (optional)
        rate: Speech rate (-100 to 100, 0 is normal)

    Returns:
        True if successful
    """
    if not shutil.which("spd-say"):
        logger.debug("spd-say not found")
        return False

    try:
        # Convert rate to spd-say scale (-100 to 100)
        spd_rate = max(-100, min(100, (rate - 150) // 2))

        cmd = ["spd-say", "-r", str(spd_rate)]

        if voice:
            cmd.extend(["-t", voice])

        cmd.append(text)

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        await proc.wait()
        return proc.returncode == 0

    except Exception as e:
        logger.error(f"spd-say error: {e}")
        return False


async def speak_linux_festival(
    text: str, voice: Optional[str] = None, rate: int = 150
) -> bool:
    """
    Speak using festival TTS engine.

    Festival is an older but still widely available TTS system.

    Args:
        text: Text to speak
        voice: Voice (optional, festival has limited voice options)
        rate: Speech rate (not fully supported by festival)

    Returns:
        True if successful
    """
    if not shutil.which("festival"):
        logger.debug("festival not found")
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            "festival",
            "--tts",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await proc.communicate(input=text.encode())
        return proc.returncode == 0

    except Exception as e:
        logger.error(f"festival error: {e}")
        return False


async def speak_linux(text: str, voice: Optional[str] = None, rate: int = 150) -> bool:
    """
    Speak on Linux using best available method.

    WARNING: This function does NOT acquire the voice serializer lock.
    It must only be called from within the serializer's executor (e.g.
    via ``ResilientVoice._linux_voice``).  Calling it directly from
    application code will bypass overlap protection.

    Tries methods in order:
    1. pyttsx3 (preferred)
    2. espeak/espeak-ng
    3. speech-dispatcher (spd-say)
    4. festival

    Args:
        text: Text to speak
        voice: Voice name/variant
        rate: Speech rate in words per minute

    Returns:
        True if any method succeeded
    """
    # Try pyttsx3 first (most features)
    if await speak_linux_pyttsx3(text, voice, rate):
        return True

    # Try espeak (most common on Linux)
    if await speak_linux_espeak(text, voice, rate):
        return True

    # Try speech-dispatcher
    if await speak_linux_spd_say(text, voice, rate):
        return True

    # Fallback to festival
    if await speak_linux_festival(text, voice, rate):
        return True

    logger.error("All Linux voice methods failed")
    return False


async def list_linux_voices() -> List[Dict[str, str]]:
    """
    List available Linux voices.

    Returns:
        List of available voices
    """
    voices = []

    # Try pyttsx3 first
    try:
        import pyttsx3

        engine = pyttsx3.init()

        for voice in engine.getProperty("voices"):
            voices.append(
                {
                    "name": voice.name,
                    "id": voice.id,
                    "languages": voice.languages,
                }
            )

        engine.stop()
        return voices
    except Exception:
        pass

    # Try espeak voice list
    espeak_cmd = None
    if shutil.which("espeak-ng"):
        espeak_cmd = "espeak-ng"
    elif shutil.which("espeak"):
        espeak_cmd = "espeak"

    if espeak_cmd:
        try:
            proc = await asyncio.create_subprocess_exec(
                espeak_cmd,
                "--voices",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await proc.communicate()

            # Parse espeak voice list
            for line in stdout.decode().split("\n")[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        voices.append(
                            {
                                "name": parts[3] if len(parts) > 3 else parts[1],
                                "id": parts[1],
                                "language": parts[1],
                            }
                        )
        except Exception as e:
            logger.error(f"Error listing espeak voices: {e}")

    return voices


if __name__ == "__main__":
    # Test Linux voice
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("Linux Voice Test")
        print("=" * 60)

        # List available voices
        print("\nAvailable Voices:")
        voices = await list_linux_voices()
        for voice in voices[:10]:  # Limit to first 10
            print(f"  - {voice.get('name', voice.get('id'))}")

        if len(voices) > 10:
            print(f"  ... and {len(voices) - 10} more")

        # Test speech
        print("\nTesting speech...")
        text = "Hello! This is the Linux voice system working on your computer."
        success = await speak_linux(text)

        if success:
            print("✓ Speech test successful!")
        else:
            print("✗ Speech test failed!")

        # Test different rates
        print("\nTesting different rates...")
        await speak_linux("Slow speech", rate=100)
        await asyncio.sleep(0.5)
        await speak_linux("Normal speech", rate=150)
        await asyncio.sleep(0.5)
        await speak_linux("Fast speech", rate=200)

    asyncio.run(test())
