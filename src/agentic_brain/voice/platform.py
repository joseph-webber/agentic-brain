# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Platform Detection for Cross-Platform Voice Support

Detects the operating system and available voice systems to enable
voice output on Windows, Linux, and macOS with automatic fallback.
"""

import logging
import platform
import shutil
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class VoicePlatform(Enum):
    """Supported platforms for voice output"""

    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"
    UNKNOWN = "unknown"


def detect_platform() -> VoicePlatform:
    """
    Detect the current operating system.

    Returns:
        VoicePlatform enum value
    """
    system = platform.system()

    platform_map = {
        "Darwin": VoicePlatform.MACOS,
        "Windows": VoicePlatform.WINDOWS,
        "Linux": VoicePlatform.LINUX,
    }
    if system in platform_map:
        return platform_map[system]

    logger.warning(f"Unknown platform: {system}")
    return VoicePlatform.UNKNOWN


def _check_pyttsx3() -> bool:
    """Check if pyttsx3 is available"""
    try:
        import pyttsx3

        # Try to initialize to verify it works
        engine = pyttsx3.init()
        engine.stop()
        return True
    except (ImportError, Exception) as e:
        logger.debug(f"pyttsx3 not available: {e}")
        return False


def _check_gtts() -> bool:
    """Check if gTTS (Google Text-to-Speech) is available"""
    try:
        from gtts import gTTS

        return True
    except ImportError:
        return False


def _check_audio_player() -> Optional[str]:
    """Check for available audio player"""
    players = {
        "afplay": "macOS",
        "mpg123": "Linux",
        "mpg321": "Linux",
        "ffplay": "Cross-platform",
        "vlc": "Cross-platform",
    }

    for player, _platform_name in players.items():
        if shutil.which(player):
            return player

    return None


def check_voice_available() -> Dict[str, bool]:
    """
    Check what voice systems are available on this platform.

    Returns:
        Dict with availability of each voice system:
        - macos_say: macOS native 'say' command
        - windows_sapi: Windows Speech API
        - windows_powershell: Windows PowerShell TTS
        - linux_espeak: Linux espeak TTS
        - linux_festival: Linux festival TTS
        - linux_spd_say: Linux speech-dispatcher
        - pyttsx3: Cross-platform pyttsx3 library
        - gtts: Google Text-to-Speech (cloud, requires internet)
        - audio_player: Audio player for playing MP3/WAV files
    """
    current_platform = detect_platform()

    availability = {
        # Platform-specific native commands
        "macos_say": False,
        "windows_sapi": False,
        "windows_powershell": False,
        "linux_espeak": False,
        "linux_festival": False,
        "linux_spd_say": False,
        # Cross-platform libraries
        "pyttsx3": _check_pyttsx3(),
        "gtts": _check_gtts(),
        # Audio player for MP3 playback (needed for gTTS)
        "audio_player": _check_audio_player(),
    }

    # Platform-specific checks
    if current_platform == VoicePlatform.MACOS:
        availability["macos_say"] = shutil.which("say") is not None

    elif current_platform == VoicePlatform.WINDOWS:
        # Windows always has SAPI available
        availability["windows_sapi"] = True
        # PowerShell is available on Windows 7+
        availability["windows_powershell"] = shutil.which("powershell") is not None

    elif current_platform == VoicePlatform.LINUX:
        availability["linux_espeak"] = (
            shutil.which("espeak") is not None or shutil.which("espeak-ng") is not None
        )
        availability["linux_festival"] = shutil.which("festival") is not None
        availability["linux_spd_say"] = shutil.which("spd-say") is not None

    return availability


def get_recommended_voice_method() -> Optional[str]:
    """
    Get the recommended voice method for this platform.

    Returns:
        String name of recommended method, or None if none available
    """
    current_platform = detect_platform()
    availability = check_voice_available()

    # Platform-specific recommendations (in order of preference)
    if current_platform == VoicePlatform.MACOS:
        if availability["macos_say"]:
            return "macos_say"

    elif current_platform == VoicePlatform.WINDOWS:
        if availability["pyttsx3"]:
            return "pyttsx3"
        if availability["windows_powershell"]:
            return "windows_powershell"
        if availability["windows_sapi"]:
            return "windows_sapi"

    elif current_platform == VoicePlatform.LINUX:
        if availability["pyttsx3"]:
            return "pyttsx3"
        if availability["linux_espeak"]:
            return "linux_espeak"
        if availability["linux_spd_say"]:
            return "linux_spd_say"
        if availability["linux_festival"]:
            return "linux_festival"

    # Cross-platform fallbacks
    if availability["pyttsx3"]:
        return "pyttsx3"
    if availability["gtts"] and availability["audio_player"]:
        return "gtts"

    logger.error("No voice system available on this platform!")
    return None


def get_platform_info() -> Dict[str, str]:
    """
    Get detailed platform information.

    Returns:
        Dict with platform details
    """
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "detected_platform": detect_platform().value,
        "recommended_voice": get_recommended_voice_method(),
    }


if __name__ == "__main__":
    # Test platform detection
    logging.basicConfig(level=logging.INFO)

    print("Platform Detection Test")
    print("=" * 60)

    platform_info = get_platform_info()
    print("\nPlatform Information:")
    for key, value in platform_info.items():
        print(f"  {key}: {value}")

    print("\nVoice System Availability:")
    availability = check_voice_available()
    for system, available in availability.items():
        status = "✓ AVAILABLE" if available else "✗ Not available"
        print(f"  {system:20s}: {status}")

    recommended = get_recommended_voice_method()
    if recommended:
        print(f"\n✓ Recommended voice method: {recommended}")
    else:
        print("\n✗ No voice system available!")
