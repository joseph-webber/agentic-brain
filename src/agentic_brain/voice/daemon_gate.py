# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Daemon Startup Gate - Prevents overlapping voice daemons.

If two brain processes start simultaneously, they can each launch a
``VoiceDaemon`` that calls ``say`` in parallel → Joseph hears two voices
at once.  This module provides a PID-file gate that ensures only ONE
daemon owns the audio output at any time.

Usage::

    from agentic_brain.voice.daemon_gate import DaemonGate, get_daemon_gate

    gate = get_daemon_gate()
    if gate.acquire():
        # We own the audio output
        daemon.start()
    else:
        print(f"Another daemon owns audio (pid={gate.owner_pid})")

On process exit the gate is released automatically via ``atexit``.
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_PID_PATH = os.path.expanduser("~/.brain-voice-daemon.pid")
_STALE_THRESHOLD = 120  # seconds - consider PID file stale after this


class DaemonGate:
    """PID-file based gate ensuring only one voice daemon runs at a time.

    Acquire the gate before starting any voice daemon.  If another
    process already holds the gate, ``acquire()`` returns ``False``.

    Stale PID files (from crashed processes) are automatically cleaned.
    """

    def __init__(self, pid_path: str = _DEFAULT_PID_PATH) -> None:
        self._pid_path = pid_path
        self._owned = False
        self._lock = threading.Lock()

    # ── Public API ───────────────────────────────────────────────────

    def acquire(self) -> bool:
        """Try to become the active voice daemon.

        Returns True if we now own the gate, False if another live
        process already holds it.
        """
        with self._lock:
            if self._owned:
                return True

            existing_pid = self._read_pid()
            if existing_pid is not None:
                if self._is_alive(existing_pid):
                    logger.debug(
                        "Daemon gate held by pid=%d, cannot acquire", existing_pid
                    )
                    return False
                else:
                    logger.info(
                        "Stale daemon gate (pid=%d not alive), reclaiming",
                        existing_pid,
                    )
                    self._remove_pid_file()

            self._write_pid()
            self._owned = True
            atexit.register(self.release)
            logger.info("Daemon gate acquired (pid=%d)", os.getpid())
            return True

    def release(self) -> None:
        """Release the gate (idempotent)."""
        with self._lock:
            if not self._owned:
                return
            self._remove_pid_file()
            self._owned = False
            logger.info("Daemon gate released (pid=%d)", os.getpid())

    @property
    def is_held(self) -> bool:
        """True if *any* process holds the gate."""
        pid = self._read_pid()
        if pid is None:
            return False
        return self._is_alive(pid)

    @property
    def is_owner(self) -> bool:
        """True if *this* process holds the gate."""
        return self._owned

    @property
    def owner_pid(self) -> Optional[int]:
        """PID of the process currently holding the gate, or None."""
        pid = self._read_pid()
        if pid is not None and self._is_alive(pid):
            return pid
        return None

    def status(self) -> Dict:
        """Diagnostic status dict."""
        pid = self._read_pid()
        alive = pid is not None and self._is_alive(pid)
        return {
            "pid_path": self._pid_path,
            "is_owner": self._owned,
            "holder_pid": pid if alive else None,
            "is_held": alive,
            "stale": pid is not None and not alive,
        }

    # ── Internal ─────────────────────────────────────────────────────

    def _read_pid(self) -> Optional[int]:
        try:
            with open(self._pid_path) as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return None

    def _write_pid(self) -> None:
        os.makedirs(os.path.dirname(self._pid_path) or ".", exist_ok=True)
        with open(self._pid_path, "w") as f:
            f.write(str(os.getpid()))

    def _remove_pid_file(self) -> None:
        try:
            os.unlink(self._pid_path)
        except FileNotFoundError:
            pass

    @staticmethod
    def _is_alive(pid: int) -> bool:
        """Check if a process with the given PID is alive."""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we lack permission to signal it
            return True


# ── Singleton ────────────────────────────────────────────────────────

_gate: Optional[DaemonGate] = None
_gate_lock = threading.Lock()


def get_daemon_gate(pid_path: str = _DEFAULT_PID_PATH) -> DaemonGate:
    """Return the process-wide daemon gate singleton."""
    global _gate
    if _gate is None:
        with _gate_lock:
            if _gate is None:
                _gate = DaemonGate(pid_path)
    return _gate


def _set_daemon_gate_for_testing(gate: Optional[DaemonGate]) -> None:
    """Replace the global daemon gate (tests only)."""
    global _gate
    _gate = gate
