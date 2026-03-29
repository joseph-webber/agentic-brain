# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
NeuralVoiceRouter – Intelligent routing between Apple say and Kokoro.

Rules:
- System/navigation speech (timers, alerts, quick confirmations) →
  Apple ``say`` for instant response.
- Ladies' conversational speech → Kokoro neural TTS for warmth and
  personality.
- Karen **always** uses Apple ``say`` for system messages (she is the
  lead and must be fast/reliable) but uses Kokoro for longer
  conversational turns.

All output is serialized through :class:`VoiceSerializer` so Joseph
never hears overlapping voices.

Usage::

    from agentic_brain.voice.neural_router import NeuralVoiceRouter

    router = NeuralVoiceRouter()
    router.speak("Deployment complete!", category="system")
    router.speak("Good morning Joseph", lady="Karen")
    router.speak("おはよう", lady="Kyoko")
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Messages shorter than this use Apple say even for ladies (faster)
_SHORT_MESSAGE_THRESHOLD = 12

# Speech categories that always use Apple say
_SYSTEM_CATEGORIES = frozenset(
    {
        "system",
        "navigation",
        "alert",
        "timer",
        "notification",
        "error",
        "progress",
    }
)


class NeuralVoiceRouter:
    """Routes speech to the optimal TTS engine per context.

    Lazy-initializes KokoroVoice on first neural request.
    Integrates with :class:`VoiceSerializer` for overlap prevention.
    Caches generated audio for repeated phrases.
    """

    def __init__(
        self,
        *,
        cache_dir: Optional[Path] = None,
        enable_cache: bool = True,
        short_message_threshold: int = _SHORT_MESSAGE_THRESHOLD,
    ) -> None:
        self._cache_dir = cache_dir or Path.home() / ".cache" / "neural-voice-router"
        self._enable_cache = enable_cache
        self._short_threshold = short_message_threshold
        self._kokoro: Any = None
        self._kokoro_attempted = False
        self._phrase_cache: Dict[str, bytes] = {}
        self._stats: Dict[str, int] = {
            "apple_say_count": 0,
            "kokoro_count": 0,
            "cache_hits": 0,
            "fallback_count": 0,
        }

    @property
    def stats(self) -> Dict[str, int]:
        """Return routing statistics."""
        return dict(self._stats)

    @property
    def kokoro_available(self) -> bool:
        """Check if Kokoro backend is usable."""
        self._ensure_kokoro()
        return self._kokoro is not None and self._kokoro.backend not in (
            None,
            "apple-say",
        )

    def _ensure_kokoro(self) -> None:
        """Lazy-load KokoroVoice, only once."""
        if self._kokoro_attempted:
            return
        self._kokoro_attempted = True
        try:
            from agentic_brain.voice.kokoro_tts import KokoroVoice

            self._kokoro = KokoroVoice(
                cache_dir=self._cache_dir / "kokoro",
                enable_cache=self._enable_cache,
            )
        except Exception as exc:
            logger.warning("KokoroVoice init failed: %s", exc)
            self._kokoro = None

    def speak(
        self,
        text: str,
        *,
        lady: str = "Karen",
        rate: int = 155,
        category: str = "conversation",
        wait: bool = True,
    ) -> bool:
        """Speak text, routing to the best engine.

        Args:
            text: What to say.
            lady: Lady name (Karen, Kyoko, …).
            rate: Words per minute for Apple say.
            category: Speech category (system, conversation, …).
            wait: Block until speech finishes.

        Returns:
            True if speech was delivered.
        """
        if not text or not text.strip():
            return False

        engine = self._route(text, lady=lady, category=category)

        if engine == "apple-say":
            return self._speak_apple(text, lady=lady, rate=rate, wait=wait)

        return self._speak_kokoro(text, lady=lady, rate=rate, wait=wait)

    def speak_system(self, text: str, *, rate: int = 160, wait: bool = True) -> bool:
        """Shortcut for system/navigation messages (always Apple say)."""
        return self.speak(text, lady="Karen", rate=rate, category="system", wait=wait)

    def speak_lady(
        self,
        text: str,
        lady: str,
        *,
        rate: int = 155,
        wait: bool = True,
    ) -> bool:
        """Shortcut for lady conversational speech (prefers Kokoro)."""
        return self.speak(
            text, lady=lady, rate=rate, category="conversation", wait=wait
        )

    def _route(self, text: str, *, lady: str, category: str) -> str:
        """Decide which engine to use.

        Returns ``"apple-say"`` or ``"kokoro"``.
        """
        if category in _SYSTEM_CATEGORIES:
            return "apple-say"

        if len(text.strip()) < self._short_threshold:
            return "apple-say"

        if lady == "Karen" and category == "system":
            return "apple-say"

        self._ensure_kokoro()
        if self._kokoro is not None and self._kokoro.backend not in (None, "apple-say"):
            return "kokoro"

        return "apple-say"

    def _speak_apple(
        self,
        text: str,
        *,
        lady: str,
        rate: int,
        wait: bool,
    ) -> bool:
        """Speak via the VoiceSerializer (Apple say pathway)."""
        self._stats["apple_say_count"] += 1
        try:
            from agentic_brain.voice.serializer import get_voice_serializer

            serializer = get_voice_serializer()
            return serializer.speak(text, voice=lady, rate=rate, wait=wait)
        except Exception:
            return self._speak_apple_direct(text, lady=lady, rate=rate)

    def _speak_apple_direct(
        self,
        text: str,
        *,
        lady: str,
        rate: int,
    ) -> bool:
        """Direct Apple say (last resort if serializer unavailable)."""
        from agentic_brain.voice.kokoro_tts import _APPLE_FALLBACKS

        if shutil.which("say") is None:
            return False
        voice = _APPLE_FALLBACKS.get(lady, "Samantha")
        try:
            result = subprocess.run(
                ["say", "-v", voice, "-r", str(rate), text],
                check=False,
                capture_output=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _speak_kokoro(
        self,
        text: str,
        *,
        lady: str,
        rate: int,
        wait: bool,
    ) -> bool:
        """Synthesize with Kokoro, then play via serializer or afplay."""
        if self._kokoro is None:
            self._stats["fallback_count"] += 1
            return self._speak_apple(text, lady=lady, rate=rate, wait=wait)

        cache_key = self._phrase_cache_key(text, lady, rate)
        audio_bytes = self._phrase_cache.get(cache_key)

        if audio_bytes is not None:
            self._stats["cache_hits"] += 1
        else:
            try:
                speed = max(0.75, min(1.35, rate / 155.0))
                audio_bytes = self._kokoro.synthesize(text, lady, speed=speed)
                if self._enable_cache and audio_bytes:
                    self._phrase_cache[cache_key] = audio_bytes
            except Exception as exc:
                logger.warning("Kokoro synthesis failed for %s: %s", lady, exc)
                self._stats["fallback_count"] += 1
                return self._speak_apple(text, lady=lady, rate=rate, wait=wait)

        if audio_bytes is None:
            self._stats["fallback_count"] += 1
            return self._speak_apple(text, lady=lady, rate=rate, wait=wait)

        self._stats["kokoro_count"] += 1
        return self._play_audio_bytes(audio_bytes, wait=wait)

    def _play_audio_bytes(self, audio_bytes: bytes, *, wait: bool = True) -> bool:
        """Play WAV/AIFF audio bytes by writing to a temp file and using afplay."""
        play_dir = self._cache_dir / "playback"
        play_dir.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256(audio_bytes[:256]).hexdigest()[:12]
        audio_path = play_dir / f"play_{digest}.wav"

        try:
            audio_path.write_bytes(audio_bytes)

            if shutil.which("afplay") is None:
                logger.warning("afplay not available")
                return False

            if wait:
                result = subprocess.run(
                    ["afplay", str(audio_path)],
                    check=False,
                    capture_output=True,
                    timeout=60,
                )
                return result.returncode == 0
            else:
                subprocess.Popen(
                    ["afplay", str(audio_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
        except Exception as exc:
            logger.warning("Audio playback failed: %s", exc)
            return False
        finally:
            try:
                if audio_path.exists():
                    audio_path.unlink()
            except OSError:
                pass

    @staticmethod
    def _phrase_cache_key(text: str, lady: str, rate: int) -> str:
        raw = f"{lady}|{rate}|{text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def clear_cache(self) -> int:
        """Clear the in-memory phrase cache. Returns items cleared."""
        count = len(self._phrase_cache)
        self._phrase_cache.clear()
        if self._kokoro is not None:
            count += self._kokoro.clear_cache()
        return count

    def get_routing_info(self, text: str, lady: str, category: str) -> Dict[str, str]:
        """Return routing decision details without speaking."""
        engine = self._route(text, lady=lady, category=category)
        info: Dict[str, str] = {
            "engine": engine,
            "lady": lady,
            "category": category,
            "reason": "",
        }
        if category in _SYSTEM_CATEGORIES:
            info["reason"] = "system category always uses Apple say"
        elif len(text.strip()) < self._short_threshold:
            info["reason"] = "short message, Apple say is faster"
        elif engine == "kokoro":
            info["reason"] = "conversational speech routed to Kokoro neural TTS"
        else:
            info["reason"] = "Kokoro unavailable, using Apple say fallback"
        return info
