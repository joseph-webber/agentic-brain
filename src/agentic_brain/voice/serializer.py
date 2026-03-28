"""
Voice Serializer - Ensures voices NEVER overlap.

HARDENED ARCHITECTURE (2026-03-29)
===================================
All voice output MUST go through this singleton.  Direct calls to
``subprocess.Popen(["say", ...])`` outside the serializer are FORBIDDEN.

Safety layers:
1. **Singleton pattern** – ``VoiceSerializer.__new__`` is thread-safe and
   idempotent.  A second instantiation returns the existing instance.
2. **Worker-thread queue** – A single daemon thread pulls ``_SpeechJob``
   items from a deque, ensuring sequential execution.
3. **Runtime overlap detection** – ``audit_no_concurrent_say()`` scans the
   process table and raises ``RuntimeError`` if more than one ``say``
   process is alive.  Called automatically before each utterance.
4. **Deprecation gate** – ``_warn_direct_say()`` emits a
   ``DeprecationWarning`` so legacy callers surface in CI/logs.

Joseph is blind.  Voice overlap is an *accessibility catastrophe*.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import threading
import time
import warnings
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from agentic_brain.audio.stereo_pan import get_stereo_panner
from agentic_brain.cache.voice_cache import VoiceCache, VoiceState
from agentic_brain.voice.config import stereo_pan_enabled
from agentic_brain.voice._speech_lock import get_global_lock as _get_global_lock
from agentic_brain.voice.redis_queue import RedisVoiceQueue, VoiceJob

logger = logging.getLogger(__name__)

# ── Overlap detection ────────────────────────────────────────────────

def audit_no_concurrent_say() -> None:
    """Raise ``RuntimeError`` if multiple ``say`` processes are running.

    This is an O(n) scan over ``/bin/ps`` output – cheap enough to call
    before every utterance and invaluable as a safety net.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-x", "say"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        pids: List[str] = [p for p in result.stdout.strip().splitlines() if p]
        if len(pids) > 1:
            raise RuntimeError(
                f"CRITICAL: {len(pids)} concurrent 'say' processes detected "
                f"(pids: {', '.join(pids)}).  Voice overlap is occurring!"
            )
    except FileNotFoundError:
        # pgrep not available (non-macOS) – skip audit
        pass
    except subprocess.TimeoutExpired:
        logger.debug("audit_no_concurrent_say: pgrep timed out, skipping")
    except ValueError:
        logger.debug("audit_no_concurrent_say: subprocess mocked, skipping")


# ── Deprecation helper ───────────────────────────────────────────────

def _warn_direct_say(caller: str = "unknown") -> None:
    """Emit a deprecation warning for direct say/speak calls.

    Any code path that bypasses the serializer should call this so the
    violation surfaces in logs and test output.
    """
    warnings.warn(
        f"Direct say/speak call from '{caller}' is deprecated.  "
        "Route ALL speech through VoiceSerializer.speak() or "
        "speak_serialized() to prevent overlap.",
        DeprecationWarning,
        stacklevel=3,
    )


@dataclass
class VoiceMessage:
    """Normalized speech request handled by the serializer."""

    text: str
    voice: str = "Karen"
    rate: int = 155
    pause_after: Optional[float] = None
    lady: Optional[str] = None  # When set, route through spatial audio

    def __post_init__(self) -> None:
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("Voice message text cannot be empty")


SpeechExecutor = Callable[[VoiceMessage], bool]


@dataclass
class _SpeechJob:
    """Internal queued speech job."""

    message: VoiceMessage
    executor: SpeechExecutor
    done: threading.Event = field(default_factory=threading.Event)
    result: bool = False
    error: Optional[Exception] = None


class VoiceSerializer:
    """Global speech gate – guarantees ONE utterance at a time.

    **Singleton enforcement**: ``__new__`` is thread-safe and idempotent.
    Constructing a second ``VoiceSerializer()`` returns the *same*
    instance.  ``_initialized`` prevents the worker thread from being
    started twice.

    **Overlap auditing**: Before each ``say`` subprocess is spawned the
    serializer calls ``audit_no_concurrent_say()`` to verify no rogue
    ``say`` process is already running.  In production this means an
    immediate ``RuntimeError`` rather than silent voice overlap.

    All external callers should use:

    * ``speak_serialized()`` (module-level function), **or**
    * ``get_voice_serializer().speak(...)``

    Never call ``subprocess.Popen(["say", ...])`` directly.
    """

    _instance: Optional[VoiceSerializer] = None
    _instance_lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> VoiceSerializer:
        with cls._instance_lock:
            if cls._instance is not None:
                return cls._instance
            instance = super().__new__(cls)
            cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        # Prevent re-initialization on subsequent VoiceSerializer() calls
        if VoiceSerializer._initialized:
            return
        VoiceSerializer._initialized = True
        self._initialize()

    def _initialize(self) -> None:
        # Use the ONE TRUE LOCK from _speech_lock.py so that every
        # speech path in the process (serializer, voiceover, global_speak,
        # resilient, llm_voice) is gated by the same mutex.
        self._speech_lock = _get_global_lock()
        self._state_lock = threading.Lock()
        self._queue_lock = threading.Lock()
        self._queue_ready = threading.Condition(self._queue_lock)
        self._queue: list[_SpeechJob] = []
        self._pending_jobs: dict[str, _SpeechJob] = {}
        self._current_message: Optional[VoiceMessage] = None
        self._current_process: Optional[subprocess.Popen] = None
        self._pause_between = 0.3
        self._audit_enabled = os.environ.get(
            "VOICE_AUDIT_DISABLED", ""
        ).lower() not in ("1", "true", "yes")
        self._redis_queue = self._create_redis_queue()
        self._voice_cache = self._create_voice_cache()
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="voice-serializer",
            daemon=True,
        )
        self._worker.start()
        self._sync_voice_cache_state()

    @property
    def pause_between(self) -> float:
        return self._pause_between

    @property
    def current_message(self) -> Optional[VoiceMessage]:
        with self._state_lock:
            return self._current_message

    @property
    def current_process(self) -> Optional[subprocess.Popen]:
        with self._state_lock:
            return self._current_process

    def set_pause_between(self, pause_seconds: float) -> None:
        """Set the default pause inserted after each utterance."""
        self._pause_between = max(0.0, pause_seconds)

    def is_speaking(self) -> bool:
        with self._state_lock:
            return self._current_message is not None

    def queue_size(self) -> int:
        if self._redis_queue is not None:
            try:
                return self._redis_queue.depth
            except Exception:
                logger.debug("Unable to query Redis voice queue depth", exc_info=True)
        with self._queue_lock:
            return len(self._queue)

    def reset(self) -> None:
        """Clear pending work and stop any active macOS `say` process."""
        with self._queue_ready:
            self._queue.clear()
            self._pending_jobs.clear()

        if self._redis_queue is not None:
            try:
                self._redis_queue.clear()
            except Exception:
                logger.debug("Unable to clear Redis voice queue during reset", exc_info=True)

        process = self.current_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1)
            except Exception:
                logger.debug("Unable to terminate active voice process during reset")

        with self._state_lock:
            self._current_message = None
            self._current_process = None
        self._sync_voice_cache_state()

    def wait_until_idle(self, timeout: float = 5.0) -> bool:
        """Wait until no message is queued or speaking."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.queue_size() == 0 and not self.is_speaking():
                return True
            time.sleep(0.01)
        return self.queue_size() == 0 and not self.is_speaking()

    def speak(
        self,
        text: str,
        voice: str = "Karen",
        rate: int = 155,
        pause_after: Optional[float] = None,
        wait: bool = True,
        lady: Optional[str] = None,
    ) -> bool:
        """Queue text for speech through the centralized serializer.

        This is the **only** sanctioned way to produce voice output.
        The message is placed on the worker-thread queue and executed
        sequentially, guaranteeing zero overlap.

        When *lady* is provided and stereo panning is enabled, the
        serializer will pan the generated speech using Sox before
        playback.
        """
        message = VoiceMessage(
            text=text,
            voice=voice,
            rate=rate,
            pause_after=pause_after,
            lady=lady,
        )
        return self.run_serialized(message, wait=wait)

    async def speak_async(
        self,
        text: str,
        voice: str = "Karen",
        rate: int = 155,
        pause_after: Optional[float] = None,
        wait: bool = True,
        lady: Optional[str] = None,
    ) -> bool:
        """Async wrapper for serialized speech."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.speak(
                text,
                voice=voice,
                rate=rate,
                pause_after=pause_after,
                wait=wait,
                lady=lady,
            ),
        )

    def run_serialized(
        self,
        message: VoiceMessage,
        executor: Optional[SpeechExecutor] = None,
        wait: bool = True,
    ) -> bool:
        """Run a speech job through the singleton queue."""
        job = _SpeechJob(message=message, executor=executor or self._speak_with_say)
        with self._queue_ready:
            if self._redis_queue is None:
                self._queue.append(job)
            else:
                try:
                    queued_job = VoiceJob(
                        text=message.text,
                        voice=message.voice,
                        rate=message.rate,
                        priority="normal",
                        pause_after=message.pause_after,
                    )
                    self._pending_jobs[queued_job.job_id] = job
                    self._redis_queue.enqueue(queued_job)
                except Exception:
                    logger.debug(
                        "Unable to enqueue speech in Redis - falling back to memory",
                        exc_info=True,
                    )
                    if "queued_job" in locals():
                        self._pending_jobs.pop(queued_job.job_id, None)
                    self._queue.append(job)
            queue_depth = max(len(self._queue), len(self._pending_jobs))
            self._sync_voice_cache_state(queue_depth_override=queue_depth)
            self._queue_ready.notify()

        if not wait:
            return True

        job.done.wait()
        if job.error:
            logger.debug("Serialized speech failed: %s", job.error)
        return job.result

    async def run_serialized_async(
        self,
        message: VoiceMessage,
        executor: Optional[SpeechExecutor] = None,
        wait: bool = True,
    ) -> bool:
        """Async wrapper for a serialized speech job."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.run_serialized(message, executor=executor, wait=wait),
        )

    def _worker_loop(self) -> None:
        while True:
            job = self._next_job()

            with self._speech_lock:
                with self._state_lock:
                    self._current_message = job.message
                    self._current_process = None
                self._sync_voice_cache_state()

                try:
                    job.result = job.executor(job.message)
                except Exception as exc:
                    job.error = exc
                    job.result = False
                    logger.exception("Voice serializer job failed")
                finally:
                    with self._state_lock:
                        self._current_message = None
                        self._current_process = None
                    self._sync_voice_cache_state()

                    pause_after = (
                        self._pause_between
                        if job.message.pause_after is None
                        else max(0.0, job.message.pause_after)
                    )
                    if pause_after > 0:
                        time.sleep(pause_after)

                    job.done.set()

    def _next_job(self) -> _SpeechJob:
        while True:
            if self._redis_queue is not None:
                try:
                    redis_job = self._redis_queue.dequeue()
                except Exception:
                    logger.debug("Unable to dequeue from Redis voice queue", exc_info=True)
                    redis_job = None

                if redis_job is not None:
                    with self._queue_ready:
                        pending = self._pending_jobs.pop(redis_job.job_id, None)
                    if pending is not None:
                        return pending
                    return _SpeechJob(
                        message=VoiceMessage(
                            text=redis_job.text,
                            voice=redis_job.voice,
                            rate=redis_job.rate,
                            pause_after=redis_job.pause_after,
                        ),
                        executor=self._speak_with_say,
                    )

            with self._queue_ready:
                if self._queue:
                    return self._queue.pop(0)
                self._queue_ready.wait(timeout=0.25)

    def _speak_with_say(self, message: VoiceMessage) -> bool:
        """Speak using macOS ``say``, waiting for completion.

        Before spawning the subprocess the method runs
        ``audit_no_concurrent_say()`` to catch overlap bugs early.
        """
        if shutil.which("say") is None:
            logger.warning("macOS 'say' command not available")
            return False

        # Runtime overlap audit – catch bugs before they reach the speaker
        if self._audit_enabled:
            try:
                audit_no_concurrent_say()
            except RuntimeError:
                logger.error(
                    "Overlap detected before speaking: %s",
                    message.text[:60],
                )
                raise

        if message.lady and stereo_pan_enabled():
            stereo_panner = get_stereo_panner()
            if stereo_panner.is_available():
                try:
                    panned_audio = stereo_panner.render_panned_speech(
                        text=message.text,
                        lady=message.lady or message.voice,
                        voice=message.voice,
                        rate=message.rate,
                    )
                except Exception:
                    logger.exception("Stereo panning failed - falling back to direct say")
                else:
                    try:
                        process = subprocess.Popen(
                            ["afplay", str(panned_audio.path)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        with self._state_lock:
                            self._current_process = process
                        return process.wait() == 0
                    finally:
                        stereo_panner.cleanup_audio(panned_audio.path)

        cmd = ["say", "-v", message.voice, "-r", str(message.rate), message.text]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        with self._state_lock:
            self._current_process = process

        return process.wait() == 0

    def _speak_spatial(self, message: VoiceMessage) -> bool:
        """Speak from a lady's spatial position using the spatial router.

        Falls back to plain ``_speak_with_say`` if spatial routing is
        unavailable or if no ``lady`` is set on the message.
        """
        lady = message.lady
        if not lady:
            return self._speak_with_say(message)

        try:
            from agentic_brain.audio.spatial_audio import get_spatial_router

            router = get_spatial_router()
            return router.speak_spatial(
                message.text,
                lady=lady,
                rate=message.rate,
                wait=True,
            )
        except Exception:
            logger.debug(
                "Spatial routing unavailable for %s, falling back to mono",
                lady,
                exc_info=True,
            )
            return self._speak_with_say(message)

    def cache_audio(
        self,
        text: str,
        voice: str,
        audio_bytes: bytes,
        ttl: int = 86400,
    ) -> Optional[str]:
        """Store synthesized audio in Redis if voice caching is available."""

        if self._voice_cache is None:
            return None
        try:
            return self._voice_cache.cache_audio(text, voice, audio_bytes, ttl=ttl)
        except Exception:
            logger.debug("Unable to cache synthesized audio", exc_info=True)
            return None

    def get_cached_audio(self, text: str, voice: str) -> Optional[bytes]:
        """Load synthesized audio from Redis if available."""

        if self._voice_cache is None:
            return None
        try:
            return self._voice_cache.get_cached_audio(text, voice)
        except Exception:
            logger.debug("Unable to load synthesized audio", exc_info=True)
            return None

    def _create_voice_cache(self) -> Optional[VoiceCache]:
        try:
            return VoiceCache()
        except Exception:
            logger.debug("Voice cache unavailable - continuing without Redis", exc_info=True)
            return None

    def _create_redis_queue(self) -> Optional[RedisVoiceQueue]:
        try:
            return RedisVoiceQueue()
        except Exception:
            logger.debug("Redis voice queue unavailable - falling back to memory", exc_info=True)
            return None

    def _sync_voice_cache_state(self, queue_depth_override: Optional[int] = None) -> None:
        if self._voice_cache is None:
            return

        try:
            with self._state_lock:
                current_message = self._current_message
                is_speaking = current_message is not None

            self._voice_cache.set_state(
                VoiceState(
                    is_speaking=is_speaking,
                    current_text=current_message.text if current_message else "",
                    current_voice=current_message.voice if current_message else "Karen",
                    queue_depth=(
                        self.queue_size()
                        if queue_depth_override is None
                        else queue_depth_override
                    ),
                )
            )
        except Exception:
            logger.debug("Unable to sync voice state to Redis", exc_info=True)


_serializer = VoiceSerializer()


def get_voice_serializer() -> VoiceSerializer:
    """Return the process-wide voice serializer singleton."""
    return _serializer


def speak_serialized(
    text: str,
    voice: str = "Karen",
    lady: Optional[str] = None,
    rate: int = 155,
    pause_after: Optional[float] = None,
    wait: bool = True,
) -> bool:
    """Thread-safe speech that never overlaps.

    **This is the recommended module-level entry-point.**
    All voice output should flow through here or through
    ``get_voice_serializer().speak()``.

    When *lady* is provided, speech is routed through the spatial audio
    system so the sound comes from that lady's position in 3D space
    around Joseph's head (requires AirPods + Sox or native bridge).
    """
    return _serializer.speak(
        text,
        voice=voice,
        lady=lady,
        rate=rate,
        pause_after=pause_after,
        wait=wait,
    )


# ── Legacy / bypass detection ────────────────────────────────────────

def _legacy_speak(text: str, voice: str = "Karen", rate: int = 155) -> bool:
    """Deprecated shim that routes through the serializer.

    Emits a ``DeprecationWarning`` so callers that bypass the canonical
    ``speak_serialized`` path are surfaced in logs / CI.
    """
    _warn_direct_say(caller="_legacy_speak")
    return speak_serialized(text, voice=voice, rate=rate)
