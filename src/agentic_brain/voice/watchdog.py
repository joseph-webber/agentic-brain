# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Voice Worker Thread Watchdog
============================

Monitors the voice serializer's worker thread and automatically restarts
it if it stalls.  Joseph is blind – if the worker dies, voice stops and
he sits in silence.  That can **never** happen.

Architecture::

    VoiceWatchdog (monitor thread)
        │
        ├─ checks heartbeat every ``check_interval`` seconds
        ├─ if no heartbeat for ``stall_timeout`` seconds → kill & restart
        ├─ exponential backoff on repeated failures
        ├─ optional Redis publish for monitoring dashboards
        └─ fires alert callback after ``max_restarts`` consecutive failures

Usage::

    from agentic_brain.voice.watchdog import VoiceWatchdog

    watchdog = VoiceWatchdog(
        worker_factory=my_start_worker_fn,
        stall_timeout=15.0,
        max_restarts=3,
    )
    watchdog.start()

    # In the worker loop:
    watchdog.heartbeat()

Thread safety: all public methods are safe to call from any thread.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Sentinel that means "worker has never sent a heartbeat"
_NEVER = 0.0


class VoiceWatchdog:
    """Monitors a voice worker thread and restarts it on stall.

    Parameters
    ----------
    worker_factory:
        Callable that starts a **new** worker thread and returns the
        ``threading.Thread`` object.  The watchdog calls this whenever
        it needs to revive the worker.
    stall_timeout:
        Seconds of silence before the worker is considered stalled.
        Default ``15.0`` (three missed heartbeats at the default 5 s
        interval).
    check_interval:
        How often the monitor thread checks the heartbeat. Default
        ``5.0`` seconds.
    max_restarts:
        Consecutive restart attempts before firing the *alert_callback*.
        After the alert the counter resets so the watchdog keeps trying.
        Default ``3``.
    backoff_base:
        Base delay (seconds) for exponential backoff between restarts.
        Actual delay = ``backoff_base * 2 ** (consecutive_failures - 1)``.
        Default ``1.0``.
    backoff_max:
        Cap on the backoff delay.  Default ``30.0``.
    alert_callback:
        Called with ``(restart_count, last_error)`` when
        ``max_restarts`` consecutive failures are reached.
    redis_client:
        Optional Redis client.  When provided, publishes restart events
        to ``brain.voice.watchdog`` for monitoring dashboards.
    """

    def __init__(
        self,
        worker_factory: Callable[[], threading.Thread],
        *,
        stall_timeout: float = 15.0,
        check_interval: float = 5.0,
        max_restarts: int = 3,
        backoff_base: float = 1.0,
        backoff_max: float = 30.0,
        alert_callback: Optional[Callable[[int, Optional[str]], None]] = None,
        redis_client: Any = None,
    ) -> None:
        if stall_timeout <= 0:
            raise ValueError("stall_timeout must be positive")
        if check_interval <= 0:
            raise ValueError("check_interval must be positive")
        if max_restarts < 1:
            raise ValueError("max_restarts must be >= 1")

        self._worker_factory = worker_factory
        self._stall_timeout = stall_timeout
        self._check_interval = check_interval
        self._max_restarts = max_restarts
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._alert_callback = alert_callback
        self._redis = redis_client

        # Protected state
        self._lock = threading.Lock()
        self._last_heartbeat: float = _NEVER
        self._worker: Optional[threading.Thread] = None
        self._monitor: Optional[threading.Thread] = None
        self._running = False
        self._consecutive_failures = 0
        self._total_restarts = 0
        self._restart_log: list[dict[str, Any]] = []
        self._stop_event = threading.Event()

    # ── Public API ───────────────────────────────────────────────────

    def heartbeat(self) -> None:
        """Called by the worker thread to signal it is alive."""
        with self._lock:
            self._last_heartbeat = time.monotonic()

    def start(self, worker: Optional[threading.Thread] = None) -> None:
        """Begin monitoring.

        Parameters
        ----------
        worker:
            The *currently running* worker thread.  If ``None`` the
            watchdog will call ``worker_factory`` to create one.
        """
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._last_heartbeat = time.monotonic()

            if worker is not None:
                self._worker = worker
            else:
                self._worker = self._worker_factory()

        self._monitor = threading.Thread(
            target=self._monitor_loop,
            name="voice-watchdog",
            daemon=True,
        )
        self._monitor.start()
        logger.info("Voice watchdog started (stall_timeout=%.1fs)", self._stall_timeout)

    def stop(self) -> None:
        """Shut down the watchdog monitor (does NOT stop the worker)."""
        with self._lock:
            if not self._running:
                return
            self._running = False
        self._stop_event.set()
        if self._monitor is not None:
            self._monitor.join(timeout=self._check_interval + 2)
            self._monitor = None
        logger.info("Voice watchdog stopped")

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._consecutive_failures

    @property
    def total_restarts(self) -> int:
        with self._lock:
            return self._total_restarts

    @property
    def restart_log(self) -> list[dict[str, Any]]:
        """Return a copy of the restart history."""
        with self._lock:
            return list(self._restart_log)

    @property
    def last_heartbeat_age(self) -> float:
        """Seconds since the last heartbeat (or since start if none)."""
        with self._lock:
            if self._last_heartbeat == _NEVER:
                return float("inf")
            return time.monotonic() - self._last_heartbeat

    @property
    def worker_alive(self) -> bool:
        """True if the registered worker thread is alive."""
        with self._lock:
            return self._worker is not None and self._worker.is_alive()

    def register_worker(self, worker: threading.Thread) -> None:
        """Replace the tracked worker thread (e.g. after manual restart)."""
        with self._lock:
            self._worker = worker
            self._last_heartbeat = time.monotonic()
            self._consecutive_failures = 0
        logger.debug("Watchdog: new worker registered (%s)", worker.name)

    # ── Internals ────────────────────────────────────────────────────

    def _monitor_loop(self) -> None:
        """Periodic check – runs on the watchdog daemon thread."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._check_interval)
            if self._stop_event.is_set():
                break
            self._check_worker()

    def _check_worker(self) -> None:
        with self._lock:
            if not self._running:
                return
            elapsed = time.monotonic() - self._last_heartbeat
            worker_dead = self._worker is None or not self._worker.is_alive()
            stalled = elapsed > self._stall_timeout

        if worker_dead or stalled:
            reason = "thread_dead" if worker_dead else "heartbeat_timeout"
            logger.warning(
                "Voice watchdog: worker %s (elapsed=%.1fs, alive=%s)",
                reason,
                elapsed,
                not worker_dead,
            )
            self._restart_worker(reason)

    def _restart_worker(self, reason: str) -> None:
        with self._lock:
            self._consecutive_failures += 1
            self._total_restarts += 1
            failures = self._consecutive_failures

            entry = {
                "timestamp": time.time(),
                "reason": reason,
                "consecutive": failures,
                "total": self._total_restarts,
            }
            self._restart_log.append(entry)

        # Exponential backoff
        if failures > 1:
            delay = min(
                self._backoff_base * (2 ** (failures - 2)),
                self._backoff_max,
            )
            logger.info(
                "Watchdog: backoff %.1fs before restart attempt %d",
                delay,
                failures,
            )
            self._stop_event.wait(timeout=delay)
            if self._stop_event.is_set():
                return

        # Fire alert on max_restarts threshold
        if failures >= self._max_restarts:
            logger.error(
                "Voice watchdog: %d consecutive failures – firing alert",
                failures,
            )
            if self._alert_callback is not None:
                try:
                    self._alert_callback(failures, reason)
                except Exception:
                    logger.exception("Watchdog alert callback failed")
            with self._lock:
                self._consecutive_failures = 0

        # Attempt restart
        try:
            new_worker = self._worker_factory()
            with self._lock:
                self._worker = new_worker
                self._last_heartbeat = time.monotonic()
            logger.info(
                "Voice watchdog: worker restarted (reason=%s, attempt=%d)",
                reason,
                failures,
            )
        except Exception as exc:
            logger.exception("Voice watchdog: failed to restart worker")
            entry["error"] = str(exc)

        # Publish to Redis for monitoring
        self._publish_restart_event(reason, failures)

    def _publish_restart_event(self, reason: str, attempt: int) -> None:
        if self._redis is None:
            return
        try:
            import json

            payload = json.dumps(
                {
                    "event": "worker_restart",
                    "reason": reason,
                    "attempt": attempt,
                    "timestamp": time.time(),
                }
            )
            self._redis.publish("brain.voice.watchdog", payload)
        except Exception:
            logger.debug("Watchdog: Redis publish failed (non-fatal)", exc_info=True)
