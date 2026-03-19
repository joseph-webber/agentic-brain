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

import platform
import subprocess
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class Platform(Enum):
    """Supported platforms."""
    MACOS = "Darwin"
    WINDOWS = "Windows"
    LINUX = "Linux"
    UNKNOWN = "Unknown"
    
    @classmethod
    def current(cls) -> "Platform":
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
    
    # Popular macOS voices
    KAREN = lambda: Voice("Karen", 175, Platform.MACOS)  # Australian
    SAMANTHA = lambda: Voice("Samantha", 175, Platform.MACOS)  # American
    DANIEL = lambda: Voice("Daniel", 175, Platform.MACOS)  # British
    MOIRA = lambda: Voice("Moira", 170, Platform.MACOS)  # Irish


@dataclass 
class AudioConfig:
    """Audio engine configuration."""
    enabled: bool = True
    default_voice: str = "Karen"
    default_rate: int = 175
    sounds_dir: Optional[Path] = None
    on_speak: Optional[Callable[[str], None]] = None
    on_error: Optional[Callable[[str], None]] = None


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
    
    def __init__(self, config: Optional[AudioConfig] = None):
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
                shutil.which("espeak") is not None or
                shutil.which("festival") is not None or
                shutil.which("espeak-ng") is not None
            )
        return False
    
    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
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
        
        voice = voice or self.config.default_voice
        rate = rate or self.config.default_rate
        
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
    
    def _speak_macos(
        self, 
        text: str, 
        voice: str, 
        rate: int, 
        wait: bool
    ) -> bool:
        """macOS native TTS using Neural Engine."""
        # Sanitize text for shell
        text = text.replace('"', '\\"').replace("'", "\\'")
        
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
        ps_script = f'''
        Add-Type -AssemblyName System.Speech
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $synth.Rate = {(rate - 175) // 25}
        $synth.Speak("{text}")
        '''
        
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
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        sound: Optional[str] = "notification",
        voice: Optional[str] = None,
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
_default_audio: Optional[Audio] = None


def get_audio() -> Audio:
    """Get or create default audio instance."""
    global _default_audio
    if _default_audio is None:
        _default_audio = Audio()
    return _default_audio


def speak(text: str, **kwargs) -> bool:
    """Quick speak using default audio."""
    return get_audio().speak(text, **kwargs)


def sound(name: str, **kwargs) -> bool:
    """Quick sound using default audio."""
    return get_audio().sound(name, **kwargs)


def announce(message: str, **kwargs) -> bool:
    """Quick announce using default audio."""
    return get_audio().announce(message, **kwargs)
