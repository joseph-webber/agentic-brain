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
- Optional AirPods-aware routing and spatial voice control

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

from agentic_brain.voice.config import VoiceConfig

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


MACOS_VOICES = {
    "karen": VoiceInfo("Karen", "en-AU", "Australia", "Lead host", True),
    "moira": VoiceInfo("Moira", "en-IE", "Ireland", "Creative", True),
    "kyoko": VoiceInfo("Kyoko", "ja-JP", "Japan", "Japanese", True),
    "tingting": VoiceInfo("Ting-Ting", "zh-CN", "China", "Chinese", True),
    "damayanti": VoiceInfo(
        "Damayanti", "id-ID", "Indonesia", "Indonesian", True
    ),
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
        for candidate in cls:
            if candidate.value == system:
                return candidate
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
        self._voices: dict[str, Any] = {}
        self._scan_voices()

    def __len__(self) -> int:
        return len(self._voices)

    def __getitem__(self, name: str) -> dict[str, Any] | None:
        return self.get_voice(name)

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._voices

    def list_voices(self, search: str | None = None) -> list[dict[str, Any]]:
        if not search:
            return list(self._voices.values())

        search = search.lower()
        return [voice for key, voice in self._voices.items() if search in key]

    def get_voice(self, name: str) -> dict[str, Any] | None:
        return self._voices.get(name.lower())

    def _scan_voices(self):
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
                name = " ".join(meta[:-1])
                is_premium = "(Premium)" in name
                key = name.lower().replace(" (premium)", "")
                self._voices[key] = {
                    "name": key.title(),
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
        self._queue.append({"text": text, "voice": voice or self._default_voice, **kwargs})

    def clear(self):
        self._queue.clear()
        self._is_playing = False

    def play_all(self, pause_between: float = 0.5) -> bool:
        if self._is_playing:
            return False

        self._is_playing = True
        audio = get_audio()
        try:
            while self._queue:
                item = self._queue.pop(0)
                audio.speak(item["text"], voice=item["voice"])
            return True
        finally:
            self._is_playing = False

    def play_next(self) -> bool:
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
    auto_route_to_airpods: bool = False
    adaptive_transparency: bool = False
    preferred_output_device: str | None = None
    airpods_name_patterns: tuple[str, ...] = (
        "AirPods Max",
        "AirPods Pro Max",
        "AirPods Pro",
        "AirPods",
    )
    head_tracking_mode: str = "fixed"
    fixed_listener_space: bool = True
    low_battery_threshold: int = 20

    def __post_init__(self):
        if self.default_voice != "Karen":
            self.voice_config.voice_name = self.default_voice
        if self.default_rate != 175:
            self.voice_config.rate = self.default_rate
        if not self.enabled:
            self.voice_config.enabled = False


class Audio:
    """Cross-platform audio engine with accessibility focus."""

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
        self.config = config or AudioConfig()
        self.platform = Platform.current()
        self._speaking = False
        self._airpods_manager = None
        self._tts_available = self._check_tts()
        if not self._tts_available:
            logger.warning("No TTS engine available on this platform")

    def _check_tts(self) -> bool:
        if self.platform == Platform.MACOS:
            return shutil.which("say") is not None
        if self.platform == Platform.WINDOWS:
            return True
        if self.platform == Platform.LINUX:
            return any(
                shutil.which(cmd) is not None
                for cmd in ("espeak", "festival", "espeak-ng")
            )
        return False

    def _get_airpods_manager(self):
        if self.platform != Platform.MACOS:
            return None
        if self._airpods_manager is None:
            from .airpods import AirPodsManager, HeadTrackingMode

            try:
                head_tracking_mode = HeadTrackingMode(self.config.head_tracking_mode)
            except ValueError:
                head_tracking_mode = HeadTrackingMode.FIXED

            self._airpods_manager = AirPodsManager(
                target_name_patterns=self.config.airpods_name_patterns,
                low_battery_threshold=self.config.low_battery_threshold,
                adaptive_transparency=self.config.adaptive_transparency,
                head_tracking_mode=head_tracking_mode,
                fixed_listener_space=self.config.fixed_listener_space,
            )
        return self._airpods_manager

    def _prepare_airpods_for_speech(self, text: str):
        manager = self._get_airpods_manager()
        if not manager:
            return
        preferred_device = self.config.preferred_output_device
        if preferred_device:
            manager.route_audio(device_name=preferred_device)
            return
        if self.config.auto_route_to_airpods:
            manager.ensure_brain_audio_ready(text)

    def _restore_airpods_after_speech(self):
        manager = self._get_airpods_manager()
        if manager:
            manager.finish_speech()

    def speak(
        self,
        text: str,
        voice: str | None = None,
        rate: int | None = None,
        wait: bool = True,
    ) -> bool:
        if not self.config.enabled or not self._tts_available:
            logger.debug("TTS disabled or unavailable: %s", text)
            return False

        voice = voice or self.config.voice_config.voice_name
        rate = rate or self.config.voice_config.rate

        if self.config.on_speak:
            self.config.on_speak(text)

        self._prepare_airpods_for_speech(text)
        try:
            if self.platform == Platform.MACOS:
                return self._speak_macos(text, voice, rate, wait)
            if self.platform == Platform.WINDOWS:
                return self._speak_windows(text, rate, wait)
            if self.platform == Platform.LINUX:
                return self._speak_linux(text, rate, wait)
            logger.warning("Unsupported platform: %s", self.platform)
            return False
        except Exception as exc:  # pragma: no cover - defensive callback path
            logger.error("TTS error: %s", exc)
            if self.config.on_error:
                self.config.on_error(str(exc))
            return False
        finally:
            self._restore_airpods_after_speech()

    def _speak_macos(self, text: str, voice: str, rate: int, wait: bool) -> bool:
        from agentic_brain.voice._speech_lock import global_speak

        voice_norm = (voice or "").strip().lower()
        if voice_norm in {"auto", "default", "system", ""}:
            cmd = ["say", "-r", str(rate), text]
        else:
            cmd = ["say", "-v", voice, "-r", str(rate), text]
        return global_speak(cmd, timeout=60)

    def _speak_windows(self, text: str, rate: int, wait: bool) -> bool:
        from agentic_brain.voice._speech_lock import global_speak

        ps_script = f'''
        Add-Type -AssemblyName System.Speech
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $synth.Rate = {(rate - 175) // 25}
        $synth.Speak("{text}")
        '''
        return global_speak(["powershell", "-Command", ps_script], timeout=60)

    def _speak_linux(self, text: str, rate: int, wait: bool) -> bool:
        from agentic_brain.voice._speech_lock import global_speak

        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if espeak:
            return global_speak([espeak, "-s", str(rate), text], timeout=60)

        festival = shutil.which("festival")
        if festival:

            def _festival_speak(msg: object) -> bool:
                proc = subprocess.Popen(
                    ["festival", "--tts"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                proc.communicate(input=text.encode(), timeout=60)
                return proc.returncode == 0

            from agentic_brain.voice.serializer import (
                VoiceMessage,
                get_voice_serializer,
            )

            return get_voice_serializer().run_serialized(
                VoiceMessage(text=text, voice="festival", rate=rate),
                executor=_festival_speak,
            )
        return False

    def sound(self, name: str, wait: bool = False) -> bool:
        if not self.config.enabled:
            return False

        try:
            if self.platform == Platform.MACOS:
                return self._sound_macos(name, wait)
            print("\a", end="", flush=True)
            return True
        except Exception as exc:  # pragma: no cover - defensive callback path
            logger.error("Sound error: %s", exc)
            return False

    def _sound_macos(self, name: str, wait: bool) -> bool:
        from agentic_brain.voice._speech_lock import global_speak

        sound_name = self.MACOS_SOUNDS.get(name, name)
        sound_path = f"/System/Library/Sounds/{sound_name}.aiff"
        if not Path(sound_path).exists():
            logger.warning("Sound not found: %s", sound_path)
            return False
        return global_speak(["afplay", sound_path], timeout=10)

    def announce(
        self,
        message: str,
        sound: str | None = "notification",
        voice: str | None = None,
    ) -> bool:
        if sound:
            self.sound(sound, wait=True)
        return self.speak(message, voice=voice)

    def progress(self, current: int, total: int, task: str = "Processing") -> bool:
        if total <= 0:
            return False
        percent = (current * 100) // total
        if percent in (25, 50, 75, 100) and current == (percent * total) // 100:
            return self.speak(f"{task}: {percent} percent complete")
        return False

    @property
    def available_voices(self) -> list[str]:
        if self.platform == Platform.MACOS:
            try:
                result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
                voices = []
                for line in result.stdout.strip().split("\n"):
                    if line:
                        voices.append(line.split()[0])
                return voices
            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
                logger.debug("Failed to query available voices: %s", exc)
                return ["Karen", "Samantha", "Daniel", "Moira"]
        return ["default"]


_default_audio: Audio | None = None
_default_registry: VoiceRegistry | None = None
_default_queue: VoiceQueue | None = None
_default_airpods: AirPodsManager | None = None


def get_audio() -> Audio:
    global _default_audio
    if _default_audio is None:
        _default_audio = Audio()
    return _default_audio


def get_registry() -> VoiceRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = VoiceRegistry()
    return _default_registry


def get_queue() -> VoiceQueue:
    global _default_queue
    if _default_queue is None:
        _default_queue = VoiceQueue()
    return _default_queue


def get_airpods() -> AirPodsManager:
    global _default_airpods
    if _default_airpods is None:
        _default_airpods = AirPodsManager()
    return _default_airpods


def list_voices(search: str | None = None) -> list[dict[str, Any]]:
    return get_registry().list_voices(search)


def speak(text: str, regionalize: bool = True, **kwargs) -> bool:
    if regionalize:
        try:
            from agentic_brain.voice.regional import get_regional_voice

            text = get_regional_voice().regionalize(text)
        except Exception as exc:  # pragma: no cover - defensive fallback path
            logger.debug("Could not regionalize text: %s", exc)
    return get_audio().speak(text, **kwargs)


def queue_speak(text: str, **kwargs):
    get_queue().add(text, **kwargs)


def play_queue():
    get_queue().play_all()


def sound(name: str, **kwargs) -> bool:
    return get_audio().sound(name, **kwargs)


def announce(message: str, **kwargs) -> bool:
    return get_audio().announce(message, **kwargs)


def test_voice():
    print("Testing voice subsystem...")
    speak("Testing voice subsystem")


from .airpods import (
    AirPodsDevice,
    AirPodsManager,
    AirPodsStatus,
    BatteryLevels,
    HeadTrackingMode,
    HeadTrackingPose,
    NoiseControlMode,
    SpatialAudioScene,
    SpatialVoicePosition,
)
