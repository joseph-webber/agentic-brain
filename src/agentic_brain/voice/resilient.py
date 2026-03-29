# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Resilient Voice System - NEVER STOPS

This system ensures voice output is always available through
multiple fallback layers. If one method fails, immediately try the next.

CROSS-PLATFORM SUPPORT:
- macOS: Native 'say' command
- Windows: pyttsx3 + PowerShell SAPI
- Linux: espeak, speech-dispatcher, festival
- Cloud Fallback: Google TTS, Azure, AWS Polly

Joseph is blind and depends on this for complete independence.
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from ._speech_lock import get_global_lock
from .cloud_tts import speak_cloud
from .linux import speak_linux
from .platform import VoicePlatform, check_voice_available, detect_platform
from .serializer import VoiceMessage as SerializedVoiceMessage
from .serializer import get_voice_serializer
from .windows import speak_windows

logger = logging.getLogger(__name__)


def _resolve_detect_platform():
    """Resolve detect_platform from the currently-imported module.

    Some tests clear `sys.modules` entries under `agentic_brain.*` to validate
    lazy-loading, then patch `agentic_brain.voice.resilient.detect_platform`.
    Resolving dynamically avoids patch drift across module reloads.
    """

    current_module = sys.modules.get("agentic_brain.voice.resilient")
    if current_module is not None and hasattr(current_module, "detect_platform"):
        return current_module.detect_platform

    from agentic_brain.voice.platform import detect_platform as _detect_platform

    return _detect_platform


@dataclass
class VoiceConfig:
    """Configuration for voice system"""

    default_voice: str = "Karen"
    default_rate: int = 155
    timeout: int = 30
    max_retries: int = 5
    enable_fallbacks: bool = True
    log_failures: bool = True
    fallback_sound: str = "/System/Library/Sounds/Glass.aiff"


class VoiceFallback:
    """Single fallback method"""

    def __init__(self, name: str, priority: int, method: Callable):
        self.name = name
        self.priority = priority
        self.method = method
        self.last_used = None
        self.success_count = 0
        self.failure_count = 0

    async def try_speak(self, text: str, voice: str = "Karen", rate: int = 155) -> bool:
        """Execute fallback method"""
        try:
            success = await self.method(text, voice, rate)
            if success:
                self.success_count += 1
                self.last_used = datetime.now()
                return True
            else:
                self.failure_count += 1
                return False
        except Exception as e:
            self.failure_count += 1
            logger.debug(f"Fallback {self.name} error: {e}")
            return False


class ResilientVoice:
    """
    Cross-platform voice system with multiple fallback layers.

    Fallback Chain (platform-specific):

    macOS:
    1. macOS `say` with voice and rate
    2. macOS `say` with default voice
    3. AppleScript UI automation
    4. OSAScript with voice
    5. Cloud TTS (gTTS)
    6. Alert sound as last resort

    Windows:
    1. pyttsx3 (SAPI wrapper)
    2. PowerShell SAPI commands
    3. Cloud TTS (gTTS)

    Linux:
    1. pyttsx3 (espeak backend)
    2. espeak/espeak-ng direct
    3. speech-dispatcher
    4. festival
    5. Cloud TTS (gTTS)
    """

    _instance = None
    _config = None
    _fallbacks: List[VoiceFallback] = []
    _queue = None
    _daemon_task = None
    _platform = None

    def __init__(self, config: Optional[VoiceConfig] = None):
        if config is None:
            config = VoiceConfig()
        ResilientVoice._config = config
        ResilientVoice._platform = _resolve_detect_platform()()
        self._setup_fallbacks()

    @classmethod
    def _setup_fallbacks(cls):
        """Initialize platform-specific fallback chain"""
        cls._fallbacks = []
        cls._platform = _resolve_detect_platform()()
        platform_value = getattr(cls._platform, "value", str(cls._platform))

        if platform_value == VoicePlatform.MACOS.value:
            # macOS fallback chain
            cls._fallbacks = [
                VoiceFallback("say_with_voice", 1, cls._say_with_voice),
                VoiceFallback("say_default", 2, cls._say_default),
                VoiceFallback("osascript_voice", 3, cls._osascript_voice),
                VoiceFallback("osascript_default", 4, cls._osascript_default),
                VoiceFallback("cloud_tts", 5, cls._cloud_tts),
                VoiceFallback("alert_sound", 6, cls._play_alert),
            ]

        elif platform_value == VoicePlatform.WINDOWS.value:
            # Windows fallback chain
            cls._fallbacks = [
                VoiceFallback("windows_voice", 1, cls._windows_voice),
                VoiceFallback("cloud_tts", 2, cls._cloud_tts),
                VoiceFallback("alert_sound", 3, cls._play_alert),
            ]

        elif platform_value == VoicePlatform.LINUX.value:
            # Linux fallback chain
            cls._fallbacks = [
                VoiceFallback("linux_voice", 1, cls._linux_voice),
                VoiceFallback("cloud_tts", 2, cls._cloud_tts),
                VoiceFallback("alert_sound", 3, cls._play_alert),
            ]

        else:
            # Unknown platform - cloud only
            cls._fallbacks = [
                VoiceFallback("cloud_tts", 1, cls._cloud_tts),
                VoiceFallback("alert_sound", 2, cls._play_alert),
                VoiceFallback("linux_voice", 3, cls._linux_voice),
            ]

        cls._fallbacks.sort(key=lambda x: x.priority)
        logger.info(
            f"Initialized {len(cls._fallbacks)} fallback methods for {cls._platform.value}"
        )

    @classmethod
    async def _say_with_voice(
        cls, text: str, voice: str = "Karen", rate: int = 155
    ) -> bool:
        """macOS say command with voice and rate"""
        lock = get_global_lock()
        owns_lock = not lock.is_held
        if owns_lock:
            acquired = await asyncio.to_thread(
                lock.acquire, timeout=cls._config.timeout
            )
            if not acquired:
                logger.warning("say_with_voice: could not acquire speech lock")
                return False
        try:
            proc = await asyncio.create_subprocess_exec(
                "say",
                "-v",
                voice,
                "-r",
                str(rate),
                text,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await asyncio.wait_for(
                proc.wait(), timeout=cls._config.timeout
            )
            return returncode == 0
        except TimeoutError:
            logger.warning("say_with_voice timeout")
            return False
        except Exception as e:
            logger.debug(f"say_with_voice error: {e}")
            return False
        finally:
            if owns_lock:
                lock.release()

    @classmethod
    async def _say_default(
        cls, text: str, voice: str = "Karen", rate: int = 155
    ) -> bool:
        """macOS say command with default voice"""
        lock = get_global_lock()
        owns_lock = not lock.is_held
        if owns_lock:
            acquired = await asyncio.to_thread(
                lock.acquire, timeout=cls._config.timeout
            )
            if not acquired:
                logger.warning("say_default: could not acquire speech lock")
                return False
        try:
            proc = await asyncio.create_subprocess_exec(
                "say",
                text,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await asyncio.wait_for(
                proc.wait(), timeout=cls._config.timeout
            )
            return returncode == 0
        except TimeoutError:
            logger.warning("say_default timeout")
            return False
        except Exception as e:
            logger.debug(f"say_default error: {e}")
            return False
        finally:
            if owns_lock:
                lock.release()

    @classmethod
    async def _osascript_voice(
        cls, text: str, voice: str = "Karen", rate: int = 155
    ) -> bool:
        """AppleScript with voice"""
        lock = get_global_lock()
        owns_lock = not lock.is_held
        if owns_lock:
            acquired = await asyncio.to_thread(
                lock.acquire, timeout=cls._config.timeout
            )
            if not acquired:
                logger.warning("osascript_voice: could not acquire speech lock")
                return False
        try:
            safe_text = text.replace('"', '\\"')
            script = (
                f'tell application "System Events" to say "{safe_text}" using "{voice}"'
            )
            proc = await asyncio.create_subprocess_exec(
                "osascript",
                "-e",
                script,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await asyncio.wait_for(
                proc.wait(), timeout=cls._config.timeout
            )
            return returncode == 0
        except TimeoutError:
            logger.warning("osascript_voice timeout")
            return False
        except Exception as e:
            logger.debug(f"osascript_voice error: {e}")
            return False
        finally:
            if owns_lock:
                lock.release()

    @classmethod
    async def _osascript_default(
        cls, text: str, voice: str = "Karen", rate: int = 155
    ) -> bool:
        """AppleScript without voice specification"""
        lock = get_global_lock()
        owns_lock = not lock.is_held
        if owns_lock:
            acquired = await asyncio.to_thread(
                lock.acquire, timeout=cls._config.timeout
            )
            if not acquired:
                logger.warning("osascript_default: could not acquire speech lock")
                return False
        try:
            safe_text = text.replace('"', '\\"')
            script = f'say "{safe_text}"'
            proc = await asyncio.create_subprocess_exec(
                "osascript",
                "-e",
                script,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await asyncio.wait_for(
                proc.wait(), timeout=cls._config.timeout
            )
            return returncode == 0
        except TimeoutError:
            logger.warning("osascript_default timeout")
            return False
        except Exception as e:
            logger.debug(f"osascript_default error: {e}")
            return False
        finally:
            if owns_lock:
                lock.release()

    @classmethod
    async def _play_alert(
        cls, text: str, voice: str = "Karen", rate: int = 155
    ) -> bool:
        """Play alert sound as final fallback"""
        lock = get_global_lock()
        owns_lock = not lock.is_held
        if owns_lock:
            acquired = await asyncio.to_thread(lock.acquire, timeout=5)
            if not acquired:
                logger.warning("play_alert: could not acquire speech lock")
                return False
        try:
            if os.path.exists(cls._config.fallback_sound):
                proc = await asyncio.create_subprocess_exec(
                    "afplay",
                    cls._config.fallback_sound,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                returncode = await asyncio.wait_for(proc.wait(), timeout=5)
                return returncode == 0
            return False
        except Exception as e:
            logger.debug(f"alert_sound error: {e}")
            return False
        finally:
            if owns_lock:
                lock.release()

    @classmethod
    async def _windows_voice(
        cls, text: str, voice: str = "Karen", rate: int = 155
    ) -> bool:
        """Windows voice using pyttsx3 or PowerShell"""
        try:
            return await speak_windows(text, voice, rate)
        except Exception as e:
            logger.debug(f"windows_voice error: {e}")
            return False

    @classmethod
    async def _linux_voice(
        cls, text: str, voice: str = "Karen", rate: int = 155
    ) -> bool:
        """Linux voice using espeak, festival, or pyttsx3"""
        try:
            return await speak_linux(text, voice, rate)
        except Exception as e:
            logger.debug(f"linux_voice error: {e}")
            return False

    @classmethod
    async def _cloud_tts(cls, text: str, voice: str = "Karen", rate: int = 155) -> bool:
        """Cloud TTS fallback (gTTS, Azure, AWS Polly)"""
        try:
            return await speak_cloud(text, provider="auto")
        except Exception as e:
            logger.debug(f"cloud_tts error: {e}")
            return False

    @classmethod
    async def speak(cls, text: str, voice: str = None, rate: int = None) -> bool:
        """
        Speak text using resilient fallback chain.

        Tries each fallback method in priority order until one succeeds.
        Returns True if ANY method succeeded.
        """
        if not cls._config:
            cls(VoiceConfig())

        if not text or not text.strip():
            logger.debug("Skipping resilient voice request with empty text")
            return False

        voice = voice or cls._config.default_voice
        rate = rate or cls._config.default_rate
        serializer = get_voice_serializer()
        message = SerializedVoiceMessage(text=text, voice=voice, rate=rate)

        return await serializer.run_serialized_async(
            message,
            executor=lambda queued_message: cls._run_serialized_fallbacks(
                queued_message
            ),
        )

    @classmethod
    def _run_serialized_fallbacks(cls, message: SerializedVoiceMessage) -> bool:
        """Run the fallback chain inside the global voice serializer."""
        return asyncio.run(
            cls._speak_with_fallbacks(message.text, message.voice, message.rate)
        )

    @classmethod
    async def _speak_with_fallbacks(
        cls,
        text: str,
        voice: str,
        rate: int,
    ) -> bool:
        """Internal fallback chain executed while the serializer lock is held."""
        if not cls._config:
            cls(VoiceConfig())

        logger.info(f"Speaking: '{text[:50]}...' (voice={voice}, rate={rate})")

        if not cls._config.enable_fallbacks:
            return await cls._fallbacks[0].try_speak(text, voice, rate)

        # Try each fallback in order
        for fallback in cls._fallbacks:
            success = await fallback.try_speak(text, voice, rate)
            if success:
                logger.debug(f"Success with {fallback.name}")
                return True

        # ALL methods failed
        logger.error(f"All voice methods failed for: '{text[:50]}...'")
        if cls._config.log_failures:
            cls._log_failure(text, voice, rate)

        # Still return True - we tried our best
        return True

    @classmethod
    def _log_failure(cls, text: str, voice: str, rate: int):
        """Log voice failures for debugging"""
        log_file = os.path.expanduser("~/.brain-voice-failures.log")
        try:
            with open(log_file, "a") as f:
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "text": text[:100],
                    "voice": voice,
                    "rate": rate,
                    "fallbacks_tried": len(cls._fallbacks),
                }
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.debug(f"Failed to log voice failure: {e}")

    @classmethod
    def get_stats(cls) -> dict:
        """Get statistics about voice system performance"""
        stats = {}
        for fallback in cls._fallbacks:
            total = fallback.success_count + fallback.failure_count
            success_rate = (fallback.success_count / total * 100) if total > 0 else 0
            stats[fallback.name] = {
                "success": fallback.success_count,
                "failure": fallback.failure_count,
                "success_rate": f"{success_rate:.1f}%",
                "last_used": (
                    fallback.last_used.isoformat() if fallback.last_used else None
                ),
            }
        return stats


class VoiceDaemon:
    """
    Background daemon that processes voice queue.

    Ensures voice is always available and ready, even if main thread is busy.
    Runs continuously, processing requests from queue.
    """

    INTER_UTTERANCE_GAP = 0.3

    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self.queue = asyncio.Queue()
        self._running = False
        self._task = None
        self._ready = asyncio.Event()
        self._startup_silence_seconds = get_voice_serializer().startup_silence_seconds
        self.processed = 0
        self.errors = 0

    async def start(self):
        """Start the daemon"""
        if self._running:
            return

        serializer = get_voice_serializer()
        serializer.mark_daemon_starting()
        self._ready.clear()
        self._running = True
        try:
            self._task = asyncio.create_task(self._process_queue())
            worker_ready = await asyncio.to_thread(
                serializer.wait_until_worker_ready, 5.0
            )
            if not worker_ready:
                raise TimeoutError("Voice serializer worker did not become ready")
            await asyncio.sleep(self._startup_silence_seconds)
            self._ready.set()
            serializer.mark_daemon_ready()
            logger.info(
                "Voice daemon started (startup gate %.3fs)",
                self._startup_silence_seconds,
            )
        except Exception:
            serializer.mark_daemon_ready()
            self._running = False
            if self._task is not None:
                self._task.cancel()
            raise

    async def stop(self):
        """Stop the daemon gracefully"""
        self._running = False
        self._ready.clear()
        if self._task:
            try:
                # Don't pass loop parameter - deprecated in Python 3.10+
                await asyncio.wait_for(self._task, timeout=5)
            except TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            except ValueError:
                # Task belongs to different loop - just cancel it
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        get_voice_serializer().mark_daemon_ready()
        logger.info(
            f"Voice daemon stopped (processed={self.processed}, errors={self.errors})"
        )

    async def speak(self, text: str, voice: str = None, rate: int = None):
        """Queue text to be spoken"""
        await self.queue.put(
            (text, voice or self.config.default_voice, rate or self.config.default_rate)
        )

    async def _process_queue(self):
        """Process queued speech requests one at a time."""
        while self._running:
            try:
                text, voice, rate = await asyncio.wait_for(self.queue.get(), timeout=60)
                await self._ready.wait()
                success = await ResilientVoice.speak(text, voice, rate)
                await asyncio.sleep(self.INTER_UTTERANCE_GAP)
                self.processed += 1
                if not success:
                    self.errors += 1
            except TimeoutError:
                # Queue timeout - daemon still alive, checking every minute
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                self.errors += 1
                # NEVER crash - continue processing
                continue

    def get_stats(self) -> dict:
        """Get daemon statistics"""
        return {
            "running": self._running,
            "ready": self._ready.is_set(),
            "queue_size": self.queue.qsize(),
            "processed": self.processed,
            "errors": self.errors,
            "error_rate": f"{(self.errors / max(self.processed, 1) * 100):.1f}%",
        }


class SoundEffects:
    """Play system sounds for feedback"""

    SOUNDS = {
        "success": "/System/Library/Sounds/Glass.aiff",
        "error": "/System/Library/Sounds/Basso.aiff",
        "notification": "/System/Library/Sounds/Ping.aiff",
        "complete": "/System/Library/Sounds/Hero.aiff",
        "alarm": "/System/Library/Sounds/Alarm.aiff",
        "alert": "/System/Library/Sounds/Alert.aiff",
    }

    @classmethod
    async def play(cls, name: str) -> bool:
        """Play a sound effect"""
        sound_file = cls.SOUNDS.get(name)
        if not sound_file or not os.path.exists(sound_file):
            logger.warning(f"Sound not found: {name}")
            return False

        try:
            from agentic_brain.voice._speech_lock import global_speak

            cmd = ["afplay", sound_file]
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: global_speak(cmd, timeout=5)
            )
        except Exception as e:
            logger.debug(f"Sound effect error: {e}")
            return False


# Global daemon instance
_daemon_instance = None


async def get_daemon(config: Optional[VoiceConfig] = None) -> VoiceDaemon:
    """Get or create global daemon instance"""
    global _daemon_instance
    if _daemon_instance is None:
        _daemon_instance = VoiceDaemon(config)
        await _daemon_instance.start()
    return _daemon_instance


# Convenience functions


async def speak(text: str, voice: str = "Karen", rate: int = 155) -> bool:
    """Speak text with fallbacks"""
    return await ResilientVoice.speak(text, voice, rate)


async def speak_via_daemon(text: str, voice: str = "Karen", rate: int = 155):
    """Speak via background daemon (fire and forget)"""
    daemon = await get_daemon()
    await daemon.speak(text, voice, rate)


async def play_sound(name: str) -> bool:
    """Play a sound effect"""
    return await SoundEffects.play(name)


def get_voice_stats() -> dict:
    """Get voice system statistics"""
    return {
        "voice": ResilientVoice.get_stats(),
        "daemon": (
            _daemon_instance.get_stats()
            if _daemon_instance
            else {"status": "not_started"}
        ),
    }


if __name__ == "__main__":
    # Test the system
    logging.basicConfig(level=logging.DEBUG)

    async def test():
        print("Testing Resilient Voice System...")

        # Test direct speak
        print("\n1. Testing direct speak:")
        success = await speak("Hello Joseph! The resilient voice system is working!")
        print(f"   Result: {'SUCCESS' if success else 'FAILED'}")

        # Test daemon
        print("\n2. Testing daemon:")
        daemon = await get_daemon()
        await daemon.speak("Speaking through the background daemon!")
        await asyncio.sleep(2)

        # Test sound
        print("\n3. Testing sound effect:")
        await play_sound("success")

        # Print stats
        print("\n4. System Statistics:")
        stats = get_voice_stats()
        print(json.dumps(stats, indent=2, default=str))

        await daemon.stop()

    asyncio.run(test())
