# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from agentic_brain.audio.stereo_pan import get_stereo_panner
from agentic_brain.cache.voice_cache import VoiceCache, VoiceState
from agentic_brain.voice._speech_lock import get_global_lock as _get_global_lock
from agentic_brain.voice.config import VoiceConfig as EmotionalVoiceConfig
from agentic_brain.voice.config import stereo_pan_enabled, use_redpanda_voice
from agentic_brain.voice.emotions import VoiceEmotion
from agentic_brain.voice.expression import ExpressionEngine
from agentic_brain.voice.redis_queue import RedisVoiceQueue, VoiceJob
from agentic_brain.voice.watchdog import VoiceWatchdog

logger = logging.getLogger(__name__)
DEFAULT_STARTUP_SILENCE_SECONDS = 0.5

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


async def audit_no_concurrent_say_async() -> None:
    """Async variant of :func:`audit_no_concurrent_say`.

    Uses ``asyncio.create_subprocess_exec`` so async callers can perform the
    overlap audit without blocking the event loop.
    """
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            "pgrep",
            "-x",
            "say",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=2)
        pids: List[str] = [
            p for p in stdout.decode(errors="ignore").strip().splitlines() if p
        ]
        if len(pids) > 1:
            raise RuntimeError(
                f"CRITICAL: {len(pids)} concurrent 'say' processes detected "
                f"(pids: {', '.join(pids)}).  Voice overlap is occurring!"
            )
    except FileNotFoundError:
        logger.debug("audit_no_concurrent_say_async: pgrep unavailable, skipping")
    except TimeoutError:
        logger.debug("audit_no_concurrent_say_async: pgrep timed out, skipping")
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
    except ValueError:
        logger.debug("audit_no_concurrent_say_async: subprocess mocked, skipping")


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
    voice: str = "Samantha"
    rate: int = 155
    pitch: float = 1.0
    volume: float = 0.8
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    pause_after: Optional[float] = None
    persona: Optional[str] = None  # When set, route through spatial audio
    sequence: int = 0

    # Backwards compatibility: alias lady -> persona
    @property
    def lady(self) -> Optional[str]:
        return self.persona

    def __post_init__(self) -> None:
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("Voice message text cannot be empty")

    def render_for_say(self) -> str:
        """Render text with inline macOS speech prosody controls."""

        commands: list[str] = []
        pitch_steps = int(round((self.pitch - 1.0) * 25))
        volume_percent = int(round(self.volume * 100))

        if pitch_steps:
            commands.append(f"[[pbas {pitch_steps:+d}]]")
        if volume_percent != 80:
            commands.append(f"[[volm {volume_percent}]]")

        if not commands:
            return self.text

        return "".join(commands) + self.text


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
        self._speech_lock_timeout = float(
            os.environ.get("VOICE_LOCK_TIMEOUT_SECONDS", "30")
        )
        self._state_lock = threading.Lock()
        self._queue_lock = threading.Lock()
        self._queue_ready = threading.Condition(self._queue_lock)
        self._mode_switch_lock = threading.Lock()
        self._queue: list[_SpeechJob] = []
        self._pending_jobs: dict[str, _SpeechJob] = {}
        self._submission_sequence = 0
        self._current_message: Optional[VoiceMessage] = None
        self._current_process: Optional[subprocess.Popen] = None
        self._job_pending = False
        self._pause_between = 0.3
        self._startup_silence_seconds = max(
            0.0,
            float(
                os.environ.get(
                    "VOICE_STARTUP_SILENCE_SECONDS",
                    str(DEFAULT_STARTUP_SILENCE_SECONDS),
                )
            ),
        )
        self._worker_ready = threading.Event()
        self._daemon_ready = threading.Event()
        self._mode_switch_ready = threading.Event()
        self._daemon_ready.set()
        self._mode_switch_ready.set()
        self._audit_enabled = os.environ.get(
            "VOICE_AUDIT_DISABLED", ""
        ).lower() not in ("1", "true", "yes")
        self._redis_queue = self._create_redis_queue()
        self._voice_cache = self._create_voice_cache()

        # Worker thread watchdog – auto-restart on stall
        self._watchdog = VoiceWatchdog(
            worker_factory=self._create_worker,
            stall_timeout=15.0,
            check_interval=5.0,
            max_restarts=3,
            alert_callback=self._on_watchdog_alert,
        )
        self._worker = self._create_worker()
        self._watchdog.start(worker=self._worker)
        self._sync_voice_cache_state()

    def _create_worker(self) -> threading.Thread:
        """Create and start a new worker thread for the speech queue."""
        worker = threading.Thread(
            target=self._worker_loop,
            name="voice-serializer",
            daemon=True,
        )
        worker.start()
        return worker

    def _on_watchdog_alert(self, restart_count: int, reason: Optional[str]) -> None:
        """Called when the watchdog hits max consecutive restarts."""
        logger.error(
            "Voice worker alert: %d consecutive restart failures (reason=%s). "
            "Voice may be degraded.",
            restart_count,
            reason,
        )

    @property
    def pause_between(self) -> float:
        return self._pause_between

    @property
    def startup_silence_seconds(self) -> float:
        return self._startup_silence_seconds

    @property
    def watchdog(self) -> VoiceWatchdog:
        """Access the worker thread watchdog."""
        return self._watchdog

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

    def is_busy(self) -> bool:
        with self._state_lock:
            return self._current_message is not None or self._job_pending

    def is_worker_ready(self) -> bool:
        return self._worker_ready.is_set()

    def is_daemon_ready(self) -> bool:
        return self._daemon_ready.is_set()

    def wait_until_worker_ready(self, timeout: float = 5.0) -> bool:
        return self._worker_ready.wait(timeout)

    def wait_until_ready(self, timeout: Optional[float] = 5.0) -> bool:
        deadline = None if timeout is None else time.monotonic() + timeout
        for event in (self._worker_ready, self._daemon_ready, self._mode_switch_ready):
            remaining = (
                None if deadline is None else max(0.0, deadline - time.monotonic())
            )
            if not event.wait(remaining):
                return False
        return True

    def mark_daemon_starting(self) -> None:
        self._daemon_ready.clear()

    def mark_daemon_ready(self) -> None:
        self._daemon_ready.set()

    @contextmanager
    def mode_switch(self, timeout: float = 10.0):
        self._mode_switch_lock.acquire()
        self._mode_switch_ready.clear()
        try:
            deadline = time.monotonic() + timeout
            while self.is_speaking():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Timed out waiting for active speech to finish")
                time.sleep(0.01)
            yield
        finally:
            self._mode_switch_ready.set()
            self._mode_switch_lock.release()

    @asynccontextmanager
    async def mode_switch_async(self, timeout: float = 10.0):
        await asyncio.to_thread(self._mode_switch_lock.acquire)
        self._mode_switch_ready.clear()
        try:
            deadline = time.monotonic() + timeout
            while self.is_speaking():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Timed out waiting for active speech to finish")
                await asyncio.sleep(0.01)
            yield
        finally:
            self._mode_switch_ready.set()
            self._mode_switch_lock.release()

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
            self._submission_sequence = 0

        if self._redis_queue is not None:
            try:
                self._redis_queue.clear()
            except Exception:
                logger.debug(
                    "Unable to clear Redis voice queue during reset", exc_info=True
                )

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
            self._job_pending = False
        self._daemon_ready.set()
        self._mode_switch_ready.set()
        self._sync_voice_cache_state()

    def wait_until_idle(self, timeout: float = 5.0) -> bool:
        """Wait until no message is queued or speaking."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.queue_size() == 0 and not self.is_busy():
                return True
            time.sleep(0.01)
        return self.queue_size() == 0 and not self.is_busy()

    async def wait_until_idle_async(self, timeout: float = 5.0) -> bool:
        """Async variant of :meth:`wait_until_idle`."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.queue_size() == 0 and not self.is_busy():
                return True
            await asyncio.sleep(0.01)
        return self.queue_size() == 0 and not self.is_busy()

    def speak(
        self,
        text: str,
        voice: str = "Samantha",
        rate: int = 155,
        emotion: VoiceEmotion | str | None = None,
        pause_after: Optional[float] = None,
        wait: bool = True,
        persona: Optional[str] = None,
    ) -> bool:
        """Queue text for speech through the centralized serializer.

        This is the **only** sanctioned way to produce voice output.
        The message is placed on the worker-thread queue and executed
        sequentially, guaranteeing zero overlap.

        When *persona* is provided and stereo panning is enabled, the
        serializer will pan the generated speech using Sox before
        playback.

        Repeat detection: if the env var ``AGENTIC_BRAIN_VOICE_NO_REPEATS``
        is set to ``true``, near-duplicate utterances are silently dropped.
        """
        # ── Repeat detection ─────────────────────────────────────────
        try:
            from agentic_brain.voice.repeat_detector import get_repeat_detector

            detector = get_repeat_detector()
            result = detector.check(text)
            if result.should_block:
                logger.debug(
                    "Blocked repeat utterance (similarity=%.2f): %s",
                    result.similarity,
                    text[:60],
                )
                return True  # pretend success – caller doesn't need to retry
            if result.is_repeat:
                logger.debug(
                    "Near-repeat detected (similarity=%.2f): %s",
                    result.similarity,
                    text[:60],
                )
        except Exception:
            pass  # repeat detection must never break speech

        return speak_serialized(
            text,
            voice=voice,
            persona=persona,
            rate=rate,
            emotion=emotion,
            pause_after=pause_after,
            wait=wait,
        )

    async def speak_async(
        self,
        text: str,
        voice: str = "Samantha",
        rate: int = 155,
        emotion: VoiceEmotion | str | None = None,
        pause_after: Optional[float] = None,
        wait: bool = True,
        persona: Optional[str] = None,
    ) -> bool:
        """Async wrapper for serialized speech."""
        if use_redpanda_voice():
            from agentic_brain.voice.events import VoicePriorityLane
            from agentic_brain.voice.stream import speak_async as publish_voice_request

            return await publish_voice_request(
                text,
                persona=persona or voice,
                priority=VoicePriorityLane.NORMAL,
                source="agentic_brain.voice.serializer",
                fallback=lambda: self.speak(
                    text,
                    voice=voice,
                    rate=rate,
                    emotion=emotion,
                    pause_after=pause_after,
                    wait=wait,
                    persona=persona,
                ),
            )

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.speak(
                text,
                voice=voice,
                rate=rate,
                emotion=emotion,
                pause_after=pause_after,
                wait=wait,
                persona=persona,
            ),
        )

    def run_serialized(
        self,
        message: VoiceMessage,
        executor: Optional[SpeechExecutor] = None,
        wait: bool = True,
    ) -> bool:
        """Run a speech job through the singleton queue."""
        if message.sequence <= 0:
            message.sequence = self._reserve_sequence()
        job = _SpeechJob(message=message, executor=executor or self._speak_with_say)
        with self._queue_ready:
            if self._redis_queue is None:
                self._queue.append(job)
                self._queue.sort(key=lambda queued_job: queued_job.message.sequence)
            else:
                try:
                    queued_job = VoiceJob(
                        text=message.text,
                        voice=message.voice,
                        rate=message.rate,
                        pitch=message.pitch,
                        volume=message.volume,
                        emotion=message.emotion.value,
                        priority="normal",
                        pause_after=message.pause_after,
                        sequence=message.sequence,
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
        if message.sequence <= 0:
            message.sequence = self._reserve_sequence()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.run_serialized(message, executor=executor, wait=wait),
        )

    def _reserve_sequence(self) -> int:
        """Allocate the next FIFO sequence number for a speech request."""
        with self._queue_ready:
            self._submission_sequence += 1
            return self._submission_sequence

    def _worker_loop(self) -> None:
        if self._startup_silence_seconds > 0:
            time.sleep(self._startup_silence_seconds)
        self._worker_ready.set()

        while True:
            # Signal the watchdog that the worker is alive
            if hasattr(self, "_watchdog"):
                self._watchdog.heartbeat()

            job = self._next_job()
            with self._state_lock:
                self._job_pending = True
            self.wait_until_ready(timeout=None)

            # Heartbeat after waking from queue wait
            if hasattr(self, "_watchdog"):
                self._watchdog.heartbeat()

            if not self._speech_lock.acquire(timeout=self._speech_lock_timeout):
                job.error = TimeoutError(
                    "Could not acquire the global voice lock before speech execution"
                )
                job.result = False
                job.done.set()
                continue

            try:
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
                    # Record to conversation memory + repeat detector
                    if job.result:
                        self._record_utterance(job.message)

                    with self._state_lock:
                        self._current_message = None
                        self._current_process = None
                        self._job_pending = False
                    self._sync_voice_cache_state()

                    pause_after = (
                        self._pause_between
                        if job.message.pause_after is None
                        else max(0.0, job.message.pause_after)
                    )
                    if pause_after > 0:
                        time.sleep(pause_after)

                    job.done.set()
            finally:
                self._speech_lock.release()

            # Heartbeat after completing a job
            if hasattr(self, "_watchdog"):
                self._watchdog.heartbeat()

    @staticmethod
    def _record_utterance(message: VoiceMessage) -> None:
        """Record a successfully spoken utterance to memory + repeat detector."""
        try:
            from agentic_brain.voice.conversation_memory import get_conversation_memory

            mem = get_conversation_memory()
            mem.record(
                lady=message.lady or message.voice,
                text=message.text,
                voice=message.voice,
                rate=message.rate,
            )
        except Exception:
            logger.debug(
                "Failed to record utterance to conversation memory", exc_info=True
            )

        try:
            from agentic_brain.voice.repeat_detector import get_repeat_detector

            get_repeat_detector().record(message.text)
        except Exception:
            logger.debug("Failed to record utterance to repeat detector", exc_info=True)

    def _next_job(self) -> _SpeechJob:
        while True:
            if self._redis_queue is not None:
                try:
                    redis_job = self._redis_queue.dequeue()
                except Exception:
                    logger.debug(
                        "Unable to dequeue from Redis voice queue", exc_info=True
                    )
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
                            pitch=redis_job.pitch,
                            volume=redis_job.volume,
                            emotion=VoiceEmotion(redis_job.emotion),
                            pause_after=redis_job.pause_after,
                            sequence=redis_job.sequence,
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
                    logger.exception(
                        "Stereo panning failed - falling back to direct say"
                    )
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

        cmd = [
            "say",
            "-v",
            message.voice,
            "-r",
            str(message.rate),
            message.render_for_say(),
        ]
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
                persona=persona,
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
            logger.debug(
                "Voice cache unavailable - continuing without Redis", exc_info=True
            )
            return None

    def _create_redis_queue(self) -> Optional[RedisVoiceQueue]:
        try:
            return RedisVoiceQueue()
        except Exception:
            logger.debug(
                "Redis voice queue unavailable - falling back to memory", exc_info=True
            )
            return None

    def _sync_voice_cache_state(
        self, queue_depth_override: Optional[int] = None
    ) -> None:
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
                    current_voice=current_message.voice if current_message else "Samantha",
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
    voice: str = "Samantha",
    persona: Optional[str] = None,
    rate: int = 155,
    emotion: VoiceEmotion | str | None = None,
    pause_after: Optional[float] = None,
    wait: bool = True,
    speed_profile: Optional[str] = None,
) -> bool:
    """Thread-safe speech that never overlaps.

    **This is the recommended module-level entry-point.**
    All voice output should flow through here or through
    ``get_voice_serializer().speak()``.

    When *speed_profile* is provided (``"slow"``, ``"normal"``,
    ``"fast"``, ``"rapid"``), the *rate* is overridden with the
    midpoint WPM for that tier.  If *speed_profile* is ``"auto"``
    and auto-classification is enabled, the content classifier
    determines the tier from the text itself.

    When *lady* is provided, speech is routed through the spatial audio
    system so the sound comes from that lady's position in 3D space
    around Joseph's head (requires AirPods + Sox or native bridge).
    """
    effective_rate = rate

    if speed_profile == "auto":
        try:
            from agentic_brain.voice.speed_profiles import (
                get_preference_manager,
                get_speed_for_content,
            )

            prefs = get_preference_manager().preferences
            if prefs.auto_classify:
                result = get_speed_for_content(text)
                effective_rate = result.wpm
        except Exception:
            logger.debug("Auto-classify failed, using default rate", exc_info=True)

    elif speed_profile and speed_profile != "auto":
        from agentic_brain.voice.speed_profiles import CONTENT_SPEED_TIERS

        tier_range = CONTENT_SPEED_TIERS.get(speed_profile)
        if tier_range:
            effective_rate = (tier_range[0] + tier_range[1]) // 2

    explicit_emotion = emotion is not None
    base_config = EmotionalVoiceConfig(voice_name=voice, rate=effective_rate)
    styled_config = base_config
    resolved_emotion = VoiceEmotion.NEUTRAL

    if explicit_emotion:
        expression_engine = ExpressionEngine()
        resolved_emotion = (
            emotion if isinstance(emotion, VoiceEmotion) else VoiceEmotion(emotion)
        )
        _, styled_config = expression_engine.style_config(
            base_config,
            text,
            persona=persona or voice,
            emotion=resolved_emotion,
        )
    else:
        expression_engine = ExpressionEngine()
        auto_emotion = expression_engine.detect_emotion(text, persona=persona or voice)
        if auto_emotion in {
            VoiceEmotion.EXCITED,
            VoiceEmotion.CALM,
            VoiceEmotion.URGENT,
            VoiceEmotion.CONCERNED,
        }:
            resolved_emotion = auto_emotion
            _, styled_config = expression_engine.style_config(
                base_config,
                text,
                persona=persona or voice,
                emotion=resolved_emotion,
            )
    message = VoiceMessage(
        text=text,
        voice=voice,
        rate=styled_config.rate,
        pitch=styled_config.pitch,
        volume=styled_config.volume,
        emotion=resolved_emotion,
        pause_after=pause_after,
        persona=persona,
    )
    return _serializer.run_serialized(message, wait=wait)


# ── Legacy / bypass detection ────────────────────────────────────────


def _legacy_speak(text: str, voice: str = "Samantha", rate: int = 155) -> bool:
    """Deprecated shim that routes through the serializer.

    Emits a ``DeprecationWarning`` so callers that bypass the canonical
    ``speak_serialized`` path are surfaced in logs / CI.
    """
    _warn_direct_say(caller="_legacy_speak")
    return speak_serialized(text, voice=voice, rate=rate)
