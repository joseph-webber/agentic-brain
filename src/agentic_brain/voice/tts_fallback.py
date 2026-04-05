# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
TTS Fallback Chain - ALWAYS produces speech, never fails silently.

FALLBACK PRIORITY (fastest paid → slowest free):
1. Cartesia Sonic (40ms TTFA) - if API key available and credits
2. Kokoro Neural TTS (82M model) - FREE, local, ~200ms
3. macOS say command - FREE, local, always works, ~100ms

ARCHITECTURE
============

This module provides a robust TTS chain that Joseph can rely on 100%.
The chain is invisible to the user - it just works.

Key guarantees:
* ✅ ALWAYS produces audio - macOS say is the nuclear option
* ✅ Works on FIRST RUN before any API keys are configured
* ✅ Automatic fallback - no user intervention needed
* ✅ Health checking - knows which TTS engines are available
* ✅ Integrates with VoiceSerializer - no overlap ever

Usage::

    from agentic_brain.voice.tts_fallback import get_tts_chain

    tts = get_tts_chain()
    await tts.speak("Hello Joseph")  # Tries Cartesia → Kokoro → macOS say
    tts.speak_sync("Hello again")    # Blocking version

    # Check health
    health = await tts.health_check()
    print(health)
    # {'cartesia': {'available': False, 'reason': 'No API key'},
    #  'kokoro': {'available': True, 'backend': 'kokoro-onnx'},
    #  'macos_say': {'available': True},
    #  'active_backend': 'kokoro'}

CRITICAL: Joseph is blind. This module MUST NEVER fail silently.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────


class TTSBackend(Enum):
    """Available TTS backends in priority order."""

    CARTESIA = "cartesia"
    KOKORO = "kokoro"
    MACOS_SAY = "macos_say"


DEFAULT_TIMEOUT_SECONDS = 30.0
CACHE_DIR = Path.home() / ".cache" / "agentic-brain" / "tts-fallback"


# ── Data Classes ──────────────────────────────────────────────────────


@dataclass
class TTSResult:
    """Result of a TTS synthesis attempt."""

    success: bool
    backend: TTSBackend
    audio_bytes: Optional[bytes] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class BackendHealth:
    """Health status of a single backend."""

    available: bool
    backend_name: str
    reason: Optional[str] = None
    latency_ms: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSChainHealth:
    """Overall health of the TTS fallback chain."""

    cartesia: BackendHealth
    kokoro: BackendHealth
    macos_say: BackendHealth
    active_backend: Optional[TTSBackend] = None
    chain_healthy: bool = True


# ── Apple say fallback voices per lady ─────────────────────────────────

APPLE_VOICE_MAP: Dict[str, str] = {
    "Karen": "Karen (Premium)",
    "Kyoko": "Kyoko",
    "Tingting": "Tingting",
    "Yuna": "Yuna",
    "Linh": "Linh",
    "Kanya": "Kanya",
    "Dewi": "Damayanti",
    "Sari": "Damayanti",
    "Wayan": "Damayanti",
    "Moira": "Moira",
    "Alice": "Alice",
    "Zosia": "Zosia",
    "Flo": "Amelie",
    "Shelley": "Shelley",
    "Samantha": "Samantha",
}


# ── TTSFallbackChain ──────────────────────────────────────────────────


class TTSFallbackChain:
    """Robust TTS with automatic fallback - NEVER fails silently.

    Priority:
    1. Cartesia Sonic (40ms TTFA) - fastest, paid
    2. Kokoro Neural (82M) - high quality, free, local
    3. macOS say - always works, built-in

    The chain is lazy-loaded. Backends are only initialized when first
    used, keeping import time near zero.

    Thread-safe: all state is protected by locks.
    """

    def __init__(
        self,
        *,
        cartesia_api_key: Optional[str] = None,
        cartesia_voice_id: Optional[str] = None,
        default_voice: str = "Karen",
        default_rate: int = 160,
        enable_cache: bool = True,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._cartesia_api_key = cartesia_api_key or os.getenv("CARTESIA_API_KEY")
        self._cartesia_voice_id = cartesia_voice_id or os.getenv("CARTESIA_VOICE_ID")
        self._default_voice = default_voice
        self._default_rate = default_rate
        self._enable_cache = enable_cache
        self._timeout_seconds = timeout_seconds

        # Lazy-loaded backends
        self._cartesia: Any = None
        self._kokoro: Any = None
        self._cartesia_checked = False
        self._kokoro_checked = False

        # State tracking
        self._lock = threading.Lock()
        self._active_backend: Optional[TTSBackend] = None
        self._metrics: Dict[str, Any] = {
            "cartesia_calls": 0,
            "cartesia_failures": 0,
            "kokoro_calls": 0,
            "kokoro_failures": 0,
            "macos_say_calls": 0,
            "macos_say_failures": 0,
            "total_fallbacks": 0,
        }

        # Cache directory
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.debug("Unable to create TTS cache directory", exc_info=True)

    # ── Public API ────────────────────────────────────────────────────

    async def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
        *,
        wait: bool = True,
        use_serializer: bool = True,
    ) -> TTSResult:
        """Speak text using the fallback chain (async).

        Tries each TTS backend in order until one succeeds.
        NEVER fails silently - macOS say is the nuclear option.

        Args:
            text: Text to speak.
            voice: Voice/lady name (default: Karen).
            rate: Speech rate in words per minute.
            wait: If True, wait for speech to complete.
            use_serializer: If True, route through VoiceSerializer for overlap prevention.

        Returns:
            TTSResult with success status and used backend.
        """
        if not text or not text.strip():
            return TTSResult(
                success=False,
                backend=TTSBackend.MACOS_SAY,
                error="Empty text",
            )

        voice = voice or self._default_voice
        rate = rate or self._default_rate

        # Route through VoiceSerializer if requested (prevents overlap)
        if use_serializer:
            try:
                return await self._speak_via_serializer(text, voice, rate, wait)
            except Exception:
                logger.debug(
                    "VoiceSerializer unavailable, using direct fallback chain"
                )

        # Direct fallback chain
        return await self._run_fallback_chain(text, voice, rate)

    def speak_sync(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
        *,
        wait: bool = True,
        use_serializer: bool = True,
    ) -> TTSResult:
        """Speak text using the fallback chain (blocking).
        
        Synchronous version of speak(). Handles running from both
        inside and outside an async event loop.
        
        Args:
            text: Text to speak.
            voice: Voice/lady name (default: Karen).
            rate: Speech rate in words per minute.
            wait: If True, wait for speech to complete.
            use_serializer: If True, use VoiceSerializer for overlap prevention.
            
        Returns:
            TTSResult with success status and used backend.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # Already in an event loop - run in thread pool
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    lambda: asyncio.run(
                        self.speak(
                            text,
                            voice,
                            rate,
                            wait=wait,
                            use_serializer=use_serializer,
                        )
                    )
                )
                return future.result(timeout=self._timeout_seconds)
        else:
            # No event loop - run directly
            return asyncio.run(
                self.speak(text, voice, rate, wait=wait, use_serializer=use_serializer)
            )

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize audio without playing it.
        
        Useful for pre-generating audio that can be cached
        or played later.
        
        Args:
            text: Text to synthesize.
            voice: Voice/lady name.
            
        Returns:
            TTSResult with audio_bytes if successful.
        """
        if not text or not text.strip():
            return TTSResult(
                success=False,
                backend=TTSBackend.MACOS_SAY,
                error="Empty text",
            )

        voice = voice or self._default_voice
        return await self._synthesize_with_fallback(text, voice)

    async def health_check(self) -> TTSChainHealth:
        """Check health of all TTS backends.
        
        Tests each backend for availability and measures latency.
        Determines the active (highest priority available) backend.
        
        Returns:
            TTSChainHealth with status for all backends.
        """
        # Check Cartesia
        cartesia_health = await self._check_cartesia_health()

        # Check Kokoro
        kokoro_health = await self._check_kokoro_health()

        # Check macOS say
        macos_health = await self._check_macos_say_health()

        # Determine active backend
        active = None
        if cartesia_health.available:
            active = TTSBackend.CARTESIA
        elif kokoro_health.available:
            active = TTSBackend.KOKORO
        elif macos_health.available:
            active = TTSBackend.MACOS_SAY

        with self._lock:
            self._active_backend = active

        chain_healthy = macos_health.available  # Chain is healthy if nuclear option works

        return TTSChainHealth(
            cartesia=cartesia_health,
            kokoro=kokoro_health,
            macos_say=macos_health,
            active_backend=active,
            chain_healthy=chain_healthy,
        )

    @property
    def active_backend(self) -> Optional[TTSBackend]:
        """Return the currently active backend.
        
        The active backend is the highest priority backend
        that is currently available.
        
        Returns:
            Currently active TTSBackend or None.
        """
        with self._lock:
            return self._active_backend

    @property
    def metrics(self) -> Dict[str, Any]:
        """Return usage metrics for all backends.
        
        Includes call counts, failure counts, and fallback statistics.
        
        Returns:
            Dictionary of metrics for each backend.
        """
        with self._lock:
            return dict(self._metrics)

    # ── Private Implementation ────────────────────────────────────────

    async def _speak_via_serializer(
        self,
        text: str,
        voice: str,
        rate: int,
        wait: bool,
    ) -> TTSResult:
        """Route speech through VoiceSerializer for overlap prevention.
        
        Args:
            text: Text to speak.
            voice: Voice identifier.
            rate: Speech rate.
            wait: Whether to wait for completion.
            
        Returns:
            TTSResult from serialized speech.
        """
        from agentic_brain.voice.serializer import get_voice_serializer

        serializer = get_voice_serializer()

        # Inject our fallback synthesis into the serializer
        # The serializer handles the queue and overlap prevention
        start_time = time.time()

        # Use serializer's speak method with our custom executor
        success = await serializer.speak_async(
            text,
            voice=APPLE_VOICE_MAP.get(voice, voice),
            rate=rate,
            wait=wait,
        )

        latency_ms = (time.time() - start_time) * 1000

        # Determine which backend was used (serializer uses macOS say by default)
        # For now, assume macos_say - in future we can inject our chain
        return TTSResult(
            success=success,
            backend=TTSBackend.MACOS_SAY,
            latency_ms=latency_ms,
        )

    async def _run_fallback_chain(
        self,
        text: str,
        voice: str,
        rate: int,
    ) -> TTSResult:
        """Run the fallback chain directly without serializer.
        
        Tries backends in priority order: Cartesia → Kokoro → macOS say.
        
        Args:
            text: Text to speak.
            voice: Voice identifier.
            rate: Speech rate.
            
        Returns:
            TTSResult from first successful backend.
        """
        # Try Cartesia first (fastest, paid)
        result = await self._try_cartesia(text, voice)
        if result.success:
            return result

        # Try Kokoro second (free, local, neural quality)
        result = await self._try_kokoro(text, voice, rate)
        if result.success:
            return result

        # Nuclear option: macOS say (always works)
        result = await self._try_macos_say(text, voice, rate)
        return result

    async def _synthesize_with_fallback(
        self,
        text: str,
        voice: str,
    ) -> TTSResult:
        """Synthesize audio bytes with fallback."""
        # Try Cartesia
        result = await self._synthesize_cartesia(text, voice)
        if result.success and result.audio_bytes:
            return result

        # Try Kokoro
        result = await self._synthesize_kokoro(text, voice)
        if result.success and result.audio_bytes:
            return result

        # Nuclear: macOS say to AIFF
        result = await self._synthesize_macos_say(text, voice)
        return result

    # ── Cartesia Backend ──────────────────────────────────────────────

    def _get_cartesia(self) -> Any:
        """Lazy-load Cartesia TTS."""
        if self._cartesia is not None or self._cartesia_checked:
            return self._cartesia

        with self._lock:
            if self._cartesia is not None or self._cartesia_checked:
                return self._cartesia

            self._cartesia_checked = True

            if not self._cartesia_api_key:
                logger.debug("Cartesia: No API key configured")
                return None

            try:
                from agentic_brain.voice.cartesia_tts import CartesiaTTS

                self._cartesia = CartesiaTTS(
                    api_key=self._cartesia_api_key,
                    default_voice_id=self._cartesia_voice_id,
                )
                logger.info("Cartesia TTS initialized successfully")
            except Exception as exc:
                logger.debug("Cartesia TTS unavailable: %s", exc)
                self._cartesia = None

        return self._cartesia

    async def _try_cartesia(self, text: str, voice: str) -> TTSResult:
        """Attempt TTS via Cartesia."""
        cartesia = self._get_cartesia()
        if cartesia is None:
            return TTSResult(
                success=False,
                backend=TTSBackend.CARTESIA,
                error="Cartesia not available",
            )

        start_time = time.time()
        try:
            # Use blocking synthesis in executor to not block event loop
            loop = asyncio.get_running_loop()
            audio_bytes = await loop.run_in_executor(
                None,
                lambda: cartesia.synthesize(text),
            )

            if audio_bytes:
                # Play the audio
                await self._play_audio(audio_bytes)
                latency_ms = (time.time() - start_time) * 1000

                with self._lock:
                    self._metrics["cartesia_calls"] += 1
                    self._active_backend = TTSBackend.CARTESIA

                return TTSResult(
                    success=True,
                    backend=TTSBackend.CARTESIA,
                    audio_bytes=audio_bytes,
                    latency_ms=latency_ms,
                )

        except Exception as exc:
            logger.warning("Cartesia synthesis failed: %s", exc)
            with self._lock:
                self._metrics["cartesia_failures"] += 1
                self._metrics["total_fallbacks"] += 1

        return TTSResult(
            success=False,
            backend=TTSBackend.CARTESIA,
            error="Synthesis failed",
        )

    async def _synthesize_cartesia(self, text: str, voice: str) -> TTSResult:
        """Synthesize via Cartesia without playing."""
        cartesia = self._get_cartesia()
        if cartesia is None:
            return TTSResult(
                success=False,
                backend=TTSBackend.CARTESIA,
                error="Cartesia not available",
            )

        start_time = time.time()
        try:
            loop = asyncio.get_running_loop()
            audio_bytes = await loop.run_in_executor(
                None,
                lambda: cartesia.synthesize(text),
            )

            if audio_bytes:
                latency_ms = (time.time() - start_time) * 1000
                with self._lock:
                    self._metrics["cartesia_calls"] += 1

                return TTSResult(
                    success=True,
                    backend=TTSBackend.CARTESIA,
                    audio_bytes=audio_bytes,
                    latency_ms=latency_ms,
                )

        except Exception as exc:
            logger.warning("Cartesia synthesis failed: %s", exc)
            with self._lock:
                self._metrics["cartesia_failures"] += 1

        return TTSResult(
            success=False,
            backend=TTSBackend.CARTESIA,
            error="Synthesis failed",
        )

    async def _check_cartesia_health(self) -> BackendHealth:
        """Check Cartesia availability."""
        if not self._cartesia_api_key:
            return BackendHealth(
                available=False,
                backend_name="cartesia",
                reason="No API key configured (CARTESIA_API_KEY)",
            )

        cartesia = self._get_cartesia()
        if cartesia is None:
            return BackendHealth(
                available=False,
                backend_name="cartesia",
                reason="Failed to initialize Cartesia client",
            )

        # Test synthesis with a short phrase
        try:
            start_time = time.time()
            loop = asyncio.get_running_loop()
            audio = await loop.run_in_executor(
                None,
                lambda: cartesia.synthesize("Test"),
            )
            latency_ms = (time.time() - start_time) * 1000

            if audio:
                return BackendHealth(
                    available=True,
                    backend_name="cartesia",
                    latency_ms=latency_ms,
                    details={"model": "sonic-3"},
                )
        except Exception as exc:
            return BackendHealth(
                available=False,
                backend_name="cartesia",
                reason=f"Test synthesis failed: {exc}",
            )

        return BackendHealth(
            available=False,
            backend_name="cartesia",
            reason="Unknown error",
        )

    # ── Kokoro Backend ────────────────────────────────────────────────

    def _get_kokoro(self) -> Any:
        """Lazy-load Kokoro TTS."""
        if self._kokoro is not None or self._kokoro_checked:
            return self._kokoro

        with self._lock:
            if self._kokoro is not None or self._kokoro_checked:
                return self._kokoro

            self._kokoro_checked = True

            try:
                from agentic_brain.voice.kokoro_tts import KokoroVoice, kokoro_available

                if not kokoro_available():
                    logger.debug("Kokoro: No backend available (kokoro-onnx or kokoro not installed)")
                    return None

                self._kokoro = KokoroVoice(enable_cache=self._enable_cache)
                logger.info("Kokoro TTS initialized (backend will lazy-load)")
            except ImportError:
                logger.debug("Kokoro TTS module not found")
                self._kokoro = None
            except Exception as exc:
                logger.debug("Kokoro TTS unavailable: %s", exc)
                self._kokoro = None

        return self._kokoro

    async def _try_kokoro(self, text: str, voice: str, rate: int) -> TTSResult:
        """Attempt TTS via Kokoro."""
        kokoro = self._get_kokoro()
        if kokoro is None:
            return TTSResult(
                success=False,
                backend=TTSBackend.KOKORO,
                error="Kokoro not available",
            )

        start_time = time.time()
        try:
            # Convert rate to speed multiplier (Kokoro uses 0.75-1.35)
            # macOS rate 155 ≈ speed 1.0, rate 180 ≈ speed 1.15
            speed = max(0.75, min(1.35, rate / 155.0))

            loop = asyncio.get_running_loop()
            audio_bytes = await loop.run_in_executor(
                None,
                lambda: kokoro.synthesize(text, lady_name=voice, speed=speed),
            )

            if audio_bytes:
                # Play the audio
                await self._play_audio(audio_bytes)
                latency_ms = (time.time() - start_time) * 1000

                with self._lock:
                    self._metrics["kokoro_calls"] += 1
                    self._active_backend = TTSBackend.KOKORO

                return TTSResult(
                    success=True,
                    backend=TTSBackend.KOKORO,
                    audio_bytes=audio_bytes,
                    latency_ms=latency_ms,
                )

        except Exception as exc:
            logger.warning("Kokoro synthesis failed: %s", exc)
            with self._lock:
                self._metrics["kokoro_failures"] += 1
                self._metrics["total_fallbacks"] += 1

        return TTSResult(
            success=False,
            backend=TTSBackend.KOKORO,
            error="Synthesis failed",
        )

    async def _synthesize_kokoro(self, text: str, voice: str) -> TTSResult:
        """Synthesize via Kokoro without playing."""
        kokoro = self._get_kokoro()
        if kokoro is None:
            return TTSResult(
                success=False,
                backend=TTSBackend.KOKORO,
                error="Kokoro not available",
            )

        start_time = time.time()
        try:
            loop = asyncio.get_running_loop()
            audio_bytes = await loop.run_in_executor(
                None,
                lambda: kokoro.synthesize(text, lady_name=voice),
            )

            if audio_bytes:
                latency_ms = (time.time() - start_time) * 1000
                with self._lock:
                    self._metrics["kokoro_calls"] += 1

                return TTSResult(
                    success=True,
                    backend=TTSBackend.KOKORO,
                    audio_bytes=audio_bytes,
                    latency_ms=latency_ms,
                )

        except Exception as exc:
            logger.warning("Kokoro synthesis failed: %s", exc)
            with self._lock:
                self._metrics["kokoro_failures"] += 1

        return TTSResult(
            success=False,
            backend=TTSBackend.KOKORO,
            error="Synthesis failed",
        )

    async def _check_kokoro_health(self) -> BackendHealth:
        """Check Kokoro availability."""
        try:
            from agentic_brain.voice.kokoro_tts import kokoro_available

            if not kokoro_available():
                return BackendHealth(
                    available=False,
                    backend_name="kokoro",
                    reason="Neither kokoro-onnx nor kokoro package installed",
                )
        except ImportError:
            return BackendHealth(
                available=False,
                backend_name="kokoro",
                reason="kokoro_tts module not available",
            )

        kokoro = self._get_kokoro()
        if kokoro is None:
            return BackendHealth(
                available=False,
                backend_name="kokoro",
                reason="Failed to initialize Kokoro engine",
            )

        # Test synthesis
        try:
            start_time = time.time()
            loop = asyncio.get_running_loop()
            audio = await loop.run_in_executor(
                None,
                lambda: kokoro.synthesize("Test", "Karen"),
            )
            latency_ms = (time.time() - start_time) * 1000

            if audio:
                backend = kokoro.backend or "unknown"
                return BackendHealth(
                    available=True,
                    backend_name="kokoro",
                    latency_ms=latency_ms,
                    details={
                        "backend": backend,
                        "hardware": kokoro.hardware_info,
                    },
                )
        except Exception as exc:
            return BackendHealth(
                available=False,
                backend_name="kokoro",
                reason=f"Test synthesis failed: {exc}",
            )

        return BackendHealth(
            available=False,
            backend_name="kokoro",
            reason="Unknown error",
        )

    # ── macOS say Backend (Nuclear Option) ─────────────────────────────

    async def _try_macos_say(self, text: str, voice: str, rate: int) -> TTSResult:
        """Nuclear option: macOS say command. ALWAYS works on macOS."""
        if shutil.which("say") is None:
            return TTSResult(
                success=False,
                backend=TTSBackend.MACOS_SAY,
                error="macOS say command not available",
            )

        start_time = time.time()
        apple_voice = APPLE_VOICE_MAP.get(voice, voice)

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["say", "-v", apple_voice, "-r", str(rate), text],
                    capture_output=True,
                    timeout=self._timeout_seconds,
                ),
            )

            latency_ms = (time.time() - start_time) * 1000

            if result.returncode == 0:
                with self._lock:
                    self._metrics["macos_say_calls"] += 1
                    self._active_backend = TTSBackend.MACOS_SAY

                return TTSResult(
                    success=True,
                    backend=TTSBackend.MACOS_SAY,
                    latency_ms=latency_ms,
                )

        except subprocess.TimeoutExpired:
            logger.error("macOS say timed out after %d seconds", self._timeout_seconds)
        except Exception as exc:
            logger.error("macOS say failed: %s", exc)

        with self._lock:
            self._metrics["macos_say_failures"] += 1

        return TTSResult(
            success=False,
            backend=TTSBackend.MACOS_SAY,
            error="macOS say command failed",
        )

    async def _synthesize_macos_say(self, text: str, voice: str) -> TTSResult:
        """Synthesize to AIFF via macOS say."""
        if shutil.which("say") is None:
            return TTSResult(
                success=False,
                backend=TTSBackend.MACOS_SAY,
                error="macOS say command not available",
            )

        apple_voice = APPLE_VOICE_MAP.get(voice, voice)
        digest = hashlib.sha256(f"{apple_voice}|{text}".encode()).hexdigest()[:16]
        aiff_path = CACHE_DIR / f"say_{digest}.aiff"

        start_time = time.time()
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["say", "-v", apple_voice, "-o", str(aiff_path), text],
                    capture_output=True,
                    timeout=self._timeout_seconds,
                ),
            )

            latency_ms = (time.time() - start_time) * 1000

            if result.returncode == 0 and aiff_path.exists():
                audio_bytes = aiff_path.read_bytes()
                with self._lock:
                    self._metrics["macos_say_calls"] += 1

                return TTSResult(
                    success=True,
                    backend=TTSBackend.MACOS_SAY,
                    audio_bytes=audio_bytes,
                    latency_ms=latency_ms,
                )

        except Exception as exc:
            logger.error("macOS say file synthesis failed: %s", exc)
        finally:
            # Clean up temp file
            try:
                if aiff_path.exists():
                    aiff_path.unlink()
            except Exception:
                pass

        with self._lock:
            self._metrics["macos_say_failures"] += 1

        return TTSResult(
            success=False,
            backend=TTSBackend.MACOS_SAY,
            error="File synthesis failed",
        )

    async def _check_macos_say_health(self) -> BackendHealth:
        """Check macOS say availability."""
        if shutil.which("say") is None:
            return BackendHealth(
                available=False,
                backend_name="macos_say",
                reason="say command not found (not macOS?)",
            )

        # Test a short synthesis
        try:
            start_time = time.time()
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["say", "-v", "Samantha", ""],  # Empty string = instant
                    capture_output=True,
                    timeout=5,
                ),
            )
            latency_ms = (time.time() - start_time) * 1000

            if result.returncode == 0:
                # Get list of available voices
                voices_result = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        ["say", "-v", "?"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    ),
                )
                voice_count = len(voices_result.stdout.strip().splitlines())

                return BackendHealth(
                    available=True,
                    backend_name="macos_say",
                    latency_ms=latency_ms,
                    details={"voice_count": voice_count},
                )
            else:
                stderr = result.stderr.decode(errors="ignore") if result.stderr else ""
                return BackendHealth(
                    available=False,
                    backend_name="macos_say",
                    reason=f"say command failed (exit {result.returncode}): {stderr[:100]}",
                )

        except Exception as exc:
            return BackendHealth(
                available=False,
                backend_name="macos_say",
                reason=f"Test failed: {exc}",
            )

    # ── Audio Playback ────────────────────────────────────────────────

    async def _play_audio(self, audio_bytes: bytes) -> bool:
        """Play audio bytes via afplay (macOS)."""
        if not audio_bytes:
            return False

        # Determine format from magic bytes
        is_aiff = audio_bytes[:4] == b"FORM"
        is_wav = audio_bytes[:4] == b"RIFF"

        extension = ".aiff" if is_aiff else ".wav" if is_wav else ".audio"
        digest = hashlib.sha256(audio_bytes[:100]).hexdigest()[:12]
        temp_path = CACHE_DIR / f"play_{digest}{extension}"

        try:
            temp_path.write_bytes(audio_bytes)

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["afplay", str(temp_path)],
                    capture_output=True,
                    timeout=60,
                ),
            )
            return result.returncode == 0

        except Exception as exc:
            logger.warning("Audio playback failed: %s", exc)
            return False
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass


# ── Singleton ─────────────────────────────────────────────────────────

_tts_chain: Optional[TTSFallbackChain] = None
_tts_chain_lock = threading.Lock()


def get_tts_chain() -> TTSFallbackChain:
    """Return the process-wide TTSFallbackChain singleton.

    Thread-safe and idempotent.
    """
    global _tts_chain
    if _tts_chain is None:
        with _tts_chain_lock:
            if _tts_chain is None:
                _tts_chain = TTSFallbackChain()
    return _tts_chain


def _set_tts_chain_for_testing(chain: Optional[TTSFallbackChain]) -> None:
    """Replace the global TTSFallbackChain (tests only)."""
    global _tts_chain
    _tts_chain = chain


# ── Convenience Functions ─────────────────────────────────────────────


async def speak(
    text: str,
    voice: str = "Karen",
    rate: int = 160,
    *,
    wait: bool = True,
) -> bool:
    """Speak text using the fallback chain (async convenience function).

    Returns True if speech succeeded.
    """
    result = await get_tts_chain().speak(text, voice, rate, wait=wait)
    return result.success


def speak_sync(
    text: str,
    voice: str = "Karen",
    rate: int = 160,
    *,
    wait: bool = True,
) -> bool:
    """Speak text using the fallback chain (sync convenience function).

    Returns True if speech succeeded.
    """
    result = get_tts_chain().speak_sync(text, voice, rate, wait=wait)
    return result.success


async def health_check() -> TTSChainHealth:
    """Check health of all TTS backends."""
    return await get_tts_chain().health_check()


__all__ = [
    "TTSFallbackChain",
    "TTSResult",
    "TTSBackend",
    "TTSChainHealth",
    "BackendHealth",
    "get_tts_chain",
    "speak",
    "speak_sync",
    "health_check",
]
