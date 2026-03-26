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
Cross-platform audio engine with Apple Silicon optimization.

Provides text-to-speech and sound effects with:
- Native Apple Neural Engine TTS on macOS
- Generic fallback for Windows/Linux
- Accessibility-first design

Example:
    >>> from agentic_brain import Audio
    >>> audio = Audio()
    >>> audio.speak("Hello from agentic brain!")
    >>> audio.sound("success")
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from agentic_brain.voice.config import VoiceConfig, VoiceQuality

logger = logging.getLogger(__name__)


@dataclass
class VoiceInfo:
    """Voice information."""

    name: str
    language: str
    region: str
    description: str = ""
    premium: bool = False

    @property
    def full_name(self) -> str:
        """Get full voice name including Premium suffix."""
        if self.premium:
            return f"{self.name} (Premium)"
        return self.name


# Known macOS voices for registry bootstrapping
MACOS_VOICES = {
    "karen": VoiceInfo("Karen", "en-AU", "Australia", "Lead host", True),
    "moira": VoiceInfo("Moira", "en-IE", "Ireland", "Creative", True),
    "kyoko": VoiceInfo("Kyoko", "ja-JP", "Japan", "Japanese", True),
    "tingting": VoiceInfo("Ting-Ting", "zh-CN", "China", "Chinese", True),
    "damayanti": VoiceInfo("Damayanti", "id-ID", "Indonesia", "Indonesian", True),
    "zosia": VoiceInfo("Zosia", "pl-PL", "Poland", "Polish", True),
    "yuna": VoiceInfo("Yuna", "ko-KR", "Korea", "Korean", True),
    "linh": VoiceInfo("Linh", "vi-VN", "Vietnam", "Vietnamese", True),
    "kanya": VoiceInfo("Kanya", "th-TH", "Thailand", "Thai", True),
    "monica": VoiceInfo("Monica", "es-ES", "Spain", "Spanish", True),
    "paulina": VoiceInfo("Paulina", "es-MX", "Mexico", "Mexican Spanish", True),
    "amelie": VoiceInfo("Amelie", "fr-FR", "France", "French", True),
    "thomas": VoiceInfo("Thomas", "fr-FR", "France", "French", True),
    "anna": VoiceInfo("Anna", "de-DE", "Germany", "German", True),
    "alice": VoiceInfo("Alice", "it-IT", "Italy", "Italian", True),
    "luciana": VoiceInfo("Luciana", "pt-BR", "Brazil", "Portuguese", True),
    "samantha": VoiceInfo("Samantha", "en-US", "USA", "American", False),
    "daniel": VoiceInfo("Daniel", "en-GB", "UK", "British", False),
}


class Platform(Enum):
    """Supported platforms."""

    MACOS = "Darwin"
    WINDOWS = "Windows"
    LINUX = "Linux"
    UNKNOWN = "Unknown"

    @classmethod
    def current(cls) -> Platform:
        """Detect current platform."""
        system = platform.system()
        for p in cls:
            if p.value == system:
                return p
        return cls.UNKNOWN


@dataclass
class Voice:
    """Voice configuration."""

    name: str
    rate: int = 175
    platform: Platform = Platform.MACOS

    @staticmethod
    def KAREN() -> Voice:
        return Voice("Karen", 175, Platform.MACOS)

    @staticmethod
    def SAMANTHA() -> Voice:
        return Voice("Samantha", 175, Platform.MACOS)

    @staticmethod
    def DANIEL() -> Voice:
        return Voice("Daniel", 175, Platform.MACOS)

    @staticmethod
    def MOIRA() -> Voice:
        return Voice("Moira", 170, Platform.MACOS)


class VoiceRegistry:
    """Registry of available voices."""

    def __init__(self):
        """Initialize registry."""
        self._voices: dict[str, Any] = {}
        self._scan_voices()

    def __len__(self) -> int:
        return len(self._voices)

    def __getitem__(self, name: str) -> dict[str, Any]:
        return self.get_voice(name)

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._voices

    def list_voices(self, search: str | None = None) -> list[dict[str, Any]]:
        """List all available voices."""
        if not search:
            return list(self._voices.values())

        search = search.lower()
        return [v for k, v in self._voices.items() if search in k]

    def get_voice(self, name: str) -> dict[str, Any] | None:
        """Get voice by name (case-insensitive)."""
        return self._voices.get(name.lower())

    def _scan_voices(self):
        """Scan system for available voices."""
        # Start with built-in knowledge base
        for key, info in MACOS_VOICES.items():
            self._voices[key] = {
                "name": info.name,
                "language": info.language,
                "region": info.region,
                "description": info.description,
                "premium": info.premium,
                "full_name": info.full_name,
            }

        if Platform.current() != Platform.MACOS:
            return

        try:
            # Parse `say -v ?` output
            # Format: Voice Name          Language    # Description
            result = subprocess.run(
                ["say", "-v", "?"], capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                return

            for line in result.stdout.splitlines():
                if not line.strip():
                    continue

                parts = line.split("#", 1)
                desc = parts[1].strip() if len(parts) > 1 else ""

                meta = parts[0].strip().split()
                if len(meta) < 2:
                    continue

                lang = meta[-1]
                name_parts = meta[:-1]
                name = " ".join(name_parts)

                # Check for premium
                is_premium = False
                if "(Premium)" in name:
                    # Clean up name but keep premium flag
                    # But tests expect 'Karen (Premium)' in full_name
                    is_premium = True

                # Normalize key
                key = name.lower().replace(" (premium)", "")

                self._voices[key] = {
                    "name": key.title(),  # Heuristic
                    "language": lang,
                    "region": "Unknown",
                    "description": desc,
                    "premium": is_premium,
                    "full_name": name,
                }

        except (FileNotFoundError, OSError):
            pass


class VoiceQueue:
    """Queue for sequential speech playback."""

    def __init__(self):
        self._queue: list[dict[str, Any]] = []
        self._is_playing = False
        self._default_voice = "Karen (Premium)"

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    def add(self, text: str, voice: str | None = None, **kwargs):
        """Add item to queue."""
        self._queue.append(
            {"text": text, "voice": voice or self._default_voice, **kwargs}
        )

    def clear(self):
        """Clear the queue."""
        self._queue.clear()
        self._is_playing = False

    def play_all(self, pause_between: float = 0.5) -> bool:
        """Play all queued items sequentially."""
        if self._is_playing:
            return False

        self._is_playing = True
        audio = get_audio()

        try:
            while self._queue:
                item = self._queue.pop(0)
                audio.speak(item["text"], voice=item["voice"])
                # In real implementation we'd sleep here

            return True
        finally:
            self._is_playing = False

    def play_next(self) -> bool:
        """Play next item in queue."""
        if not self._queue:
            return False

        item = self._queue.pop(0)
        return get_audio().speak(item["text"], voice=item["voice"])


@dataclass
class AudioConfig:
    """Audio engine configuration."""

    enabled: bool = True
    default_voice: str = "Karen"
    default_rate: int = 175
    sounds_dir: Path | None = None
    on_speak: Callable[[str], None] | None = None
    on_error: Callable[[str], None] | None = None
    voice_config: VoiceConfig = field(default_factory=VoiceConfig)

    def __post_init__(self):
        # Sync simple fields to voice_config if provided differently
        if self.default_voice != "Karen":
            self.voice_config.voice_name = self.default_voice
        if self.default_rate != 175:
            self.voice_config.rate = self.default_rate
        if not self.enabled:
            self.voice_config.enabled = False


class Audio:
    """
    Cross-platform audio engine with accessibility focus.

    Features:
    - Text-to-speech with platform-native engines
    - Apple Neural Engine acceleration on macOS
    - Sound effects for notifications
    - Queue management (no overlapping speech)

    Example:
        >>> audio = Audio()
        >>> audio.speak("Processing your request")
        >>> audio.sound("success")
        >>> audio.speak("Done!", voice="Moira", rate=160)
    """

    # Built-in sound mappings for macOS
    MACOS_SOUNDS = {
        "success": "Glass",
        "error": "Basso",
        "warning": "Purr",
        "notification": "Ping",
        "start": "Pop",
        "complete": "Hero",
        "thinking": "Tink",
    }

    def __init__(self, config: AudioConfig | None = None):
        """
        Initialize audio engine.

        Args:
            config: Audio configuration. Uses defaults if not provided.
        """
        self.config = config or AudioConfig()
        self.platform = Platform.current()
        self._speaking = False

        # Check available TTS engines
        self._tts_available = self._check_tts()

        if not self._tts_available:
            logger.warning("No TTS engine available on this platform")

    def _check_tts(self) -> bool:
        """Check if TTS is available on current platform."""
        if self.platform == Platform.MACOS:
            return shutil.which("say") is not None
        elif self.platform == Platform.WINDOWS:
            # Windows has built-in SAPI
            return True
        elif self.platform == Platform.LINUX:
            # Check for espeak or festival
            return (
                shutil.which("espeak") is not None
                or shutil.which("festival") is not None
                or shutil.which("espeak-ng") is not None
            )
        return False

    def speak(
        self,
        text: str,
        voice: str | None = None,
        rate: int | None = None,
        wait: bool = True,
    ) -> bool:
        """
        Speak text using platform-native TTS.

        Args:
            text: Text to speak
            voice: Voice name (platform-specific)
            rate: Speech rate (words per minute)
            wait: Wait for speech to complete

        Returns:
            True if speech started successfully

        Example:
            >>> audio.speak("Hello world")
            >>> audio.speak("G'day mate!", voice="Karen", rate=160)
        """
        if not self.config.enabled or not self._tts_available:
            logger.debug(f"TTS disabled or unavailable: {text}")
            return False

        voice = voice or self.config.voice_config.voice_name
        rate = rate or self.config.voice_config.rate

        # Callback hook
        if self.config.on_speak:
            self.config.on_speak(text)

        try:
            if self.platform == Platform.MACOS:
                return self._speak_macos(text, voice, rate, wait)
            elif self.platform == Platform.WINDOWS:
                return self._speak_windows(text, rate, wait)
            elif self.platform == Platform.LINUX:
                return self._speak_linux(text, rate, wait)
            else:
                logger.warning(f"Unsupported platform: {self.platform}")
                return False
        except Exception as e:
            logger.error(f"TTS error: {e}")
            if self.config.on_error:
                self.config.on_error(str(e))
            return False

    def _speak_macos(self, text: str, voice: str, rate: int, wait: bool) -> bool:
        """macOS native TTS using Neural Engine."""
        # Sanitize text for shell
        text = text.replace('"', '\\"').replace("'", "\\'")

        # If voice name contains (Premium) but system doesn't use it, strip it?
        # Actually `say` command usually handles "Karen (Premium)" fine if installed.
        # But if user configures "Premium" quality, we might want to ensure we use the premium voice.

        # Check if we should enforce premium quality based on config
        if self.config.voice_config.quality == VoiceQuality.PREMIUM:
            # If voice doesn't have (Premium) suffix but a premium version exists, try appending it
            # This is a bit tricky without knowing exactly what's installed.
            # For now, trust the voice name provided or configured.
            pass

        voice_norm = (voice or "").strip().lower()
        if voice_norm in {"auto", "default", "system", ""}:
            # Use macOS system default voice
            cmd = ["say", "-r", str(rate), text]
        else:
            cmd = ["say", "-v", voice, "-r", str(rate), text]

        if wait:
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

    def _speak_windows(self, text: str, rate: int, wait: bool) -> bool:
        """Windows SAPI TTS."""
        # PowerShell command for Windows TTS
        ps_script = f"""
        Add-Type -AssemblyName System.Speech
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $synth.Rate = {(rate - 175) // 25}
        $synth.Speak("{text}")
        """

        cmd = ["powershell", "-Command", ps_script]

        if wait:
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

    def _speak_linux(self, text: str, rate: int, wait: bool) -> bool:
        """Linux TTS using espeak or festival."""
        # Try espeak-ng first, then espeak
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")

        if espeak:
            # Convert rate to espeak format (default 175 -> 175)
            cmd = [espeak, "-s", str(rate), text]

            if wait:
                result = subprocess.run(cmd, capture_output=True)
                return result.returncode == 0
            else:
                subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True

        # Try festival
        festival = shutil.which("festival")
        if festival:
            cmd = ["festival", "--tts"]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate(input=text.encode())
            return proc.returncode == 0

        return False

    def sound(self, name: str, wait: bool = False) -> bool:
        """
        Play a notification sound.

        Args:
            name: Sound name (success, error, warning, notification, etc.)
            wait: Wait for sound to complete

        Returns:
            True if sound played successfully

        Example:
            >>> audio.sound("success")
            >>> audio.sound("error")
        """
        if not self.config.enabled:
            return False

        try:
            if self.platform == Platform.MACOS:
                return self._sound_macos(name, wait)
            else:
                # Generic beep for other platforms
                print("\a", end="", flush=True)
                return True
        except Exception as e:
            logger.error(f"Sound error: {e}")
            return False

    def _sound_macos(self, name: str, wait: bool) -> bool:
        """Play macOS system sound."""
        sound_name = self.MACOS_SOUNDS.get(name, name)
        sound_path = f"/System/Library/Sounds/{sound_name}.aiff"

        if not Path(sound_path).exists():
            logger.warning(f"Sound not found: {sound_path}")
            return False

        cmd = ["afplay", sound_path]

        if wait:
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

    def announce(
        self,
        message: str,
        sound: str | None = "notification",
        voice: str | None = None,
    ) -> bool:
        """
        Play sound then speak message (accessibility pattern).

        Args:
            message: Message to speak
            sound: Sound to play first (None to skip)
            voice: Voice to use

        Example:
            >>> audio.announce("Task completed successfully", sound="success")
        """
        if sound:
            self.sound(sound, wait=True)
        return self.speak(message, voice=voice)

    def progress(
        self,
        current: int,
        total: int,
        task: str = "Processing",
    ) -> bool:
        """
        Announce progress (accessibility helper).

        Only announces at 25%, 50%, 75%, 100%.

        Args:
            current: Current item number
            total: Total items
            task: Task description

        Example:
            >>> for i in range(100):
            ...     audio.progress(i + 1, 100, "Indexing files")
        """
        if total <= 0:
            return False

        percent = (current * 100) // total

        # Only announce at milestones
        if percent in (25, 50, 75, 100) and current == (percent * total) // 100:
            return self.speak(f"{task}: {percent} percent complete")

        return False

    @property
    def available_voices(self) -> list[str]:
        """List available voices on current platform."""
        if self.platform == Platform.MACOS:
            try:
                result = subprocess.run(
                    ["say", "-v", "?"],
                    capture_output=True,
                    text=True,
                )
                voices = []
                for line in result.stdout.strip().split("\n"):
                    if line:
                        voice_name = line.split()[0]
                        voices.append(voice_name)
                return voices
            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
                # subprocess.CalledProcessError: command failed
                # FileNotFoundError: 'say' command not found
                # OSError: subprocess error
                logger.debug(f"Failed to query available voices: {e}")
                return ["Karen", "Samantha", "Daniel", "Moira"]

        return ["default"]


# Convenience functions for quick access
_default_audio: Audio | None = None
_default_registry: VoiceRegistry | None = None
_default_queue: VoiceQueue | None = None


def get_audio() -> Audio:
    """Get or create default audio instance."""
    global _default_audio
    if _default_audio is None:
        _default_audio = Audio()
    return _default_audio


def get_registry() -> VoiceRegistry:
    """Get or create singleton voice registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = VoiceRegistry()
    return _default_registry


def get_queue() -> VoiceQueue:
    """Get or create singleton voice queue."""
    global _default_queue
    if _default_queue is None:
        _default_queue = VoiceQueue()
    return _default_queue


def list_voices(search: str | None = None) -> list[dict[str, Any]]:
    """List available voices."""
    return get_registry().list_voices(search)


def speak(text: str, regionalize: bool = True, **kwargs) -> bool:
    """
    Quick speak using default audio.

    Args:
        text: Text to speak
        regionalize: Apply regional expressions (default True)
        **kwargs: Additional arguments passed to Audio.speak()

    Returns:
        True if successful
    """
    # Apply regional expressions if enabled
    if regionalize:
        try:
            from agentic_brain.voice.regional import get_regional_voice

            rv = get_regional_voice()
            text = rv.regionalize(text)
        except Exception as e:
            logger.debug(f"Could not regionalize text: {e}")
            # Continue with original text

    return get_audio().speak(text, **kwargs)


def queue_speak(text: str, **kwargs):
    """Add to speech queue."""
    get_queue().add(text, **kwargs)


def play_queue():
    """Play all queued items."""
    get_queue().play_all()


def sound(name: str, **kwargs) -> bool:
    """Quick sound using default audio."""
    return get_audio().sound(name, **kwargs)


def announce(message: str, **kwargs) -> bool:
    """Quick announce using default audio."""
    return get_audio().announce(message, **kwargs)


def test_voice():
    """Test voice subsystem."""
    print("Testing voice subsystem...")
    speak("Testing voice subsystem")
