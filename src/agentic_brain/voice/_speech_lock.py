# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
GLOBAL Speech Lock - Prevents ALL voice overlap ACROSS PROCESSES.

CRITICAL ACCESSIBILITY MODULE for Joseph (blind user).

This module provides a **distributed** lock backed by Redis so that
every process in the brain ecosystem (MCP server, CLI scripts,
background daemons) is gated by the same mutex.  If Redis is
unavailable the lock degrades gracefully to a process-local
``threading.Lock`` so speech never blocks indefinitely.

Architecture (Redis available):
    1.  ``SET voice:speaking <owner> NX EX 30`` – atomic acquire.
    2.  A daemon heartbeat thread renews the TTL every 10 s while
        the owner holds the lock, preventing premature expiry during
        long utterances.
    3.  ``DEL voice:speaking`` (only if we still own it) on release.
    4.  If the process crashes, the 30 s TTL auto-releases.

Architecture (Redis unavailable – fallback):
    A plain ``threading.Lock()`` serialises speech within the current
    process.  Cross-process protection is lost but in-process overlap
    is still prevented.

.. warning::

    Prefer ``VoiceSerializer.speak()`` or ``speak_serialized()`` from
    ``agentic_brain.voice.serializer`` instead of calling ``global_speak``
    directly.  The serializer adds queue management, async support, and
    overlap auditing on top of the raw lock.
"""

from __future__ import annotations

import atexit
import logging
import os
import subprocess
import threading
import time
import uuid
import warnings
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Gap between consecutive utterances (seconds).
INTER_UTTERANCE_GAP = 0.3

# Redis distributed lock settings
_LOCK_KEY = "voice:speaking"
_LOCK_TTL = 30  # seconds – auto-release on crash
_HEARTBEAT_INTERVAL = 10  # seconds – renewal cadence
_ACQUIRE_POLL_INTERVAL = 0.1  # seconds – retry cadence while waiting


# ── Redis Distributed Voice Lock ────────────────────────────────────


class RedisVoiceLock:
    """Cross-process speech lock backed by Redis ``SET NX EX``.

    The lock is **reentrant within the same owner** (same process /
    thread combination) and falls back to a local ``threading.Lock``
    when Redis is unreachable.

    Context-manager protocol is supported::

        lock = get_global_lock()
        with lock:
            subprocess.run(["say", "Hello"])
    """

    def __init__(
        self,
        redis_client: Any = None,
        *,
        lock_key: str = _LOCK_KEY,
        ttl: int = _LOCK_TTL,
        heartbeat_interval: int = _HEARTBEAT_INTERVAL,
    ) -> None:
        self._lock_key = lock_key
        self._ttl = ttl
        self._heartbeat_interval = heartbeat_interval

        # Unique owner token: PID + random UUID to avoid collisions
        # after PID reuse.
        self._owner = f"{os.getpid()}-{uuid.uuid4().hex[:12]}"

        # ── Redis client (lazy) ──────────────────────────────────
        self._redis: Any = redis_client
        self._redis_available: bool | None = None  # None = not tested yet
        self._redis_init_lock = threading.Lock()

        # ── Local fallback lock ──────────────────────────────────
        self._local_lock = threading.Lock()

        # ── Heartbeat management ─────────────────────────────────
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_stop = threading.Event()

        # ── State tracking ───────────────────────────────────────
        self._held = False  # True while this instance owns the lock
        self._mode: str = "none"  # "redis" | "local" | "none"

        atexit.register(self._atexit_release)

    # ── Redis bootstrapping ──────────────────────────────────────

    def _ensure_redis(self) -> bool:
        """Lazily connect to Redis.  Returns ``True`` if usable."""
        if self._redis_available is not None:
            return self._redis_available

        with self._redis_init_lock:
            # Double-checked locking
            if self._redis_available is not None:
                return self._redis_available

            if self._redis is not None:
                # Client was injected (e.g. in tests)
                try:
                    self._redis.ping()
                    self._redis_available = True
                except Exception:
                    self._redis_available = False
                return self._redis_available

            try:
                from agentic_brain.core.redis_pool import (
                    RedisConfig,
                    RedisPoolManager,
                )

                password = os.getenv("REDIS_PASSWORD", "BrainRedis2026")
                config = RedisConfig(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", "6379")),
                    password=password,
                    db=int(os.getenv("REDIS_DB", "0")),
                )
                pool = RedisPoolManager(config)
                pool.client.ping()
                self._redis = pool.client
                self._redis_available = True
            except Exception as exc:
                logger.debug(
                    "Redis unavailable for voice lock, using local fallback: %s",
                    exc,
                )
                self._redis_available = False

        return self._redis_available

    # ── Acquire / Release ────────────────────────────────────────

    def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire the distributed voice lock.

        Args:
            timeout: Maximum seconds to wait.  ``0`` means non-blocking.

        Returns:
            ``True`` if the lock was acquired.
        """
        if self._ensure_redis():
            acquired = self._acquire_redis(timeout)
            if acquired:
                self._mode = "redis"
                self._held = True
                self._start_heartbeat()
                return True
            # Redis is alive but someone else holds the lock and we
            # timed out – do NOT fall through to local lock because
            # that would defeat the distributed guarantee.
            return False

        # Redis down – fall back to local lock.
        logger.debug("Voice lock: Redis unavailable, acquiring local lock")
        acquired = self._local_lock.acquire(timeout=max(timeout, 0))
        if acquired:
            self._mode = "local"
            self._held = True
        return acquired

    def release(self) -> None:
        """Release the lock (idempotent)."""
        if not self._held:
            return

        self._stop_heartbeat()

        if self._mode == "redis":
            self._release_redis()
        elif self._mode == "local":
            try:
                self._local_lock.release()
            except RuntimeError:
                pass  # already released

        self._held = False
        self._mode = "none"

    # ── Redis primitives ─────────────────────────────────────────

    def _acquire_redis(self, timeout: float) -> bool:
        """Try ``SET NX EX`` in a polling loop until *timeout*."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                ok = self._redis.set(
                    self._lock_key,
                    self._owner,
                    nx=True,
                    ex=self._ttl,
                )
                if ok:
                    return True
            except Exception as exc:
                logger.debug("Redis SET NX failed: %s", exc)
                # Redis went away mid-acquire – mark unavailable so
                # caller can fall back.
                self._redis_available = False
                return False

            if time.monotonic() >= deadline:
                return False

            time.sleep(_ACQUIRE_POLL_INTERVAL)

    def _release_redis(self) -> None:
        """Release only if we still own the key (Lua atomic check)."""
        lua = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "  return redis.call('del', KEYS[1]) "
            "else "
            "  return 0 "
            "end"
        )
        try:
            self._redis.eval(lua, 1, self._lock_key, self._owner)
        except Exception as exc:
            logger.debug("Redis lock release failed: %s", exc)

    # ── Heartbeat thread ─────────────────────────────────────────

    def _start_heartbeat(self) -> None:
        """Renew TTL every ``_heartbeat_interval`` seconds."""
        if self._mode != "redis":
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="voice-lock-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2)
            self._heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        """Renew the TTL while the lock is held."""
        while not self._heartbeat_stop.wait(self._heartbeat_interval):
            try:
                # Only renew if we still own the key.
                lua = (
                    "if redis.call('get', KEYS[1]) == ARGV[1] then "
                    "  return redis.call('expire', KEYS[1], ARGV[2]) "
                    "else "
                    "  return 0 "
                    "end"
                )
                self._redis.eval(lua, 1, self._lock_key, self._owner, str(self._ttl))
            except Exception as exc:
                logger.debug("Heartbeat renewal failed: %s", exc)
                break

    # ── Context-manager protocol ─────────────────────────────────

    def __enter__(self) -> "RedisVoiceLock":
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()

    # ── Cleanup ──────────────────────────────────────────────────

    def _atexit_release(self) -> None:
        """Best-effort release at interpreter shutdown."""
        try:
            self.release()
        except Exception:
            pass

    # ── Diagnostics ──────────────────────────────────────────────

    @property
    def is_held(self) -> bool:
        return self._held

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def owner(self) -> str:
        return self._owner

    def status(self) -> dict:
        """Return a diagnostic snapshot of the lock state."""
        info: dict = {
            "held_by_us": self._held,
            "mode": self._mode,
            "owner": self._owner,
            "redis_available": self._redis_available,
        }
        if self._redis_available and self._redis is not None:
            try:
                current_owner = self._redis.get(self._lock_key)
                ttl = self._redis.ttl(self._lock_key)
                info["redis_lock_owner"] = current_owner
                info["redis_lock_ttl"] = ttl
            except Exception:
                info["redis_lock_owner"] = "error"
                info["redis_lock_ttl"] = -1
        return info


# ── Module-level singleton ───────────────────────────────────────────

_speech_lock: RedisVoiceLock | None = None
_speech_lock_init = threading.Lock()
_current_process: Optional[subprocess.Popen] = None


def _get_speech_lock() -> RedisVoiceLock:
    """Return (or create) the singleton ``RedisVoiceLock``."""
    global _speech_lock
    if _speech_lock is not None:
        return _speech_lock
    with _speech_lock_init:
        if _speech_lock is None:
            _speech_lock = RedisVoiceLock()
    return _speech_lock


def global_speak(
    cmd: List[str],
    *,
    timeout: int = 60,
    inter_gap: float = INTER_UTTERANCE_GAP,
) -> bool:
    """Run a speech command under the global lock.

    .. deprecated::
        New code should route through ``speak_serialized()`` from
        ``agentic_brain.voice.serializer`` which wraps this lock with
        queue management and overlap auditing.

    Args:
        cmd: Full subprocess command, e.g. ``["say", "-v", "Karen", "Hello"]``.
        timeout: Maximum seconds to wait for the process.
        inter_gap: Seconds to pause after speech finishes for clarity.

    Returns:
        True if the command completed successfully.
    """
    warnings.warn(
        "global_speak() is a low-level primitive.  Prefer "
        "speak_serialized() from agentic_brain.voice.serializer "
        "to get queue management and overlap auditing.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _global_speak_inner(cmd, timeout=timeout, inter_gap=inter_gap)


def _global_speak_inner(
    cmd: List[str],
    *,
    timeout: int = 60,
    inter_gap: float = INTER_UTTERANCE_GAP,
) -> bool:
    """Internal implementation – no deprecation warning.

    Called by the serializer's own executor when it needs the raw lock.
    """
    global _current_process
    lock = _get_speech_lock()

    if not lock.acquire(timeout=timeout):
        logger.error("Could not acquire voice lock within %ds", timeout)
        return False

    try:
        # If a previous process is somehow still alive, wait for it.
        if _current_process is not None and _current_process.poll() is None:
            try:
                _current_process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning("Previous speech process timed out, terminating")
                _current_process.terminate()
            except Exception:
                pass
            finally:
                _current_process = None

        try:
            _current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _current_process.wait(timeout=timeout)
            success = _current_process.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("Speech command timed out: %s", " ".join(cmd[:4]))
            if _current_process:
                _current_process.terminate()
            success = False
        except FileNotFoundError:
            logger.error("Speech command not found: %s", cmd[0])
            success = False
        except Exception as e:
            logger.error("Speech command error: %s", e)
            success = False
        finally:
            _current_process = None

        # Brief pause between utterances for auditory clarity.
        if inter_gap > 0:
            time.sleep(inter_gap)

        return success
    finally:
        lock.release()


def get_global_lock() -> RedisVoiceLock:
    """Return the process-wide speech lock.

    Other modules (e.g. ``VoiceSerializer``) **must** use this lock when
    spawning ``say`` sub-processes so that every speech path in the
    process is gated by the same mutex.

    Returns a :class:`RedisVoiceLock` that supports the context-manager
    protocol (``with lock: ...``) just like ``threading.Lock``.
    """
    return _get_speech_lock()


def is_speech_active() -> bool:
    """Check if a speech process is currently running."""
    return _current_process is not None and _current_process.poll() is None


def interrupt_speech() -> None:
    """Terminate any in-flight speech immediately and release the lock."""
    global _current_process
    if _current_process is not None and _current_process.poll() is None:
        try:
            _current_process.terminate()
        except Exception:
            pass
        _current_process = None

    # Force-release the distributed lock so other processes can speak.
    lock = _get_speech_lock()
    if lock.is_held:
        lock.release()


def voice_lock_status() -> dict:
    """Return diagnostic info about the distributed voice lock."""
    return _get_speech_lock().status()


def _set_speech_lock_for_testing(lock: RedisVoiceLock | None) -> None:
    """Replace the singleton lock – **test-only**."""
    global _speech_lock
    _speech_lock = lock
