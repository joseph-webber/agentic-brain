# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Unified Voice System - Single entry point for ALL voice operations.

Phase 2 integration layer that combines:
1. VoiceSerializer (core serialized speech)
2. VoiceWatchdog (worker thread monitoring)
3. DaemonGate (overlap prevention across processes)
4. LiveVoiceMode (real-time streaming speech, Project Aria)
5. VoiceStreamConsumer (Redpanda event-driven speech)
6. RedpandaVoiceQueue (durable priority queue)

All features are lazy-loaded and optional.  If a dependency is missing
the system degrades gracefully — the serializer always works.

Usage::

    from agentic_brain.voice.unified import UnifiedVoiceSystem, get_unified

    uv = get_unified()
    uv.speak("Hello Joseph", voice="Karen")     # basic speak
    uv.start_live(voice="Karen")                 # start live mode
    uv.feed_live("streaming text")               # feed LLM tokens
    uv.stop_live()                               # stop live mode
    uv.health()                                  # full health check
    uv.status()                                  # status report
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class UnifiedVoiceSystem:
    """Unified facade combining all Phase 2 voice components.

    Every subsystem is lazily initialized on first use.  If a subsystem's
    dependencies are missing, it is simply marked as unavailable and the
    rest of the system continues to function.
    """

    def __init__(self) -> None:
        self._init_time = time.time()
        self._speak_count = 0
        self._error_count = 0
        self._lock = threading.Lock()

        # Lazy subsystem references
        self._serializer = None
        self._watchdog = None
        self._daemon_gate = None
        self._live_mode = None
        self._stream_consumer = None

    # ── Core Speak ───────────────────────────────────────────────────

    def speak(
        self,
        text: str,
        voice: str = "Karen",
        rate: int = 155,
        *,
        pause_after: Optional[float] = None,
        wait: bool = True,
        lady: Optional[str] = None,
    ) -> bool:
        """Speak text through the voice serializer (never overlaps).

        This is the primary entry point for all voice output.
        """
        serializer = self._get_serializer()
        try:
            result = serializer.speak(
                text,
                voice=voice,
                rate=rate,
                pause_after=pause_after,
                wait=wait,
                lady=lady,
            )
            with self._lock:
                self._speak_count += 1
            return result
        except Exception:
            with self._lock:
                self._error_count += 1
            logger.exception("UnifiedVoiceSystem.speak failed")
            return False

    # ── Watchdog ─────────────────────────────────────────────────────

    def start_watchdog(self) -> bool:
        """Start the worker thread watchdog.

        Returns True if the watchdog is now running.
        """
        try:
            wd = self._get_watchdog()
            if wd is None:
                return False
            if not wd.is_running:
                serializer = self._get_serializer()
                worker = getattr(serializer, "_worker", None)
                wd.start(worker=worker)
            return wd.is_running
        except Exception:
            logger.debug("Failed to start watchdog", exc_info=True)
            return False

    def stop_watchdog(self) -> None:
        """Stop the watchdog."""
        if self._watchdog is not None:
            try:
                self._watchdog.stop()
            except Exception:
                logger.debug("Failed to stop watchdog", exc_info=True)

    def watchdog_status(self) -> Dict:
        """Return watchdog diagnostics."""
        wd = self._get_watchdog()
        if wd is None:
            return {"available": False, "reason": "watchdog module not loaded"}
        return {
            "available": True,
            "running": wd.is_running,
            "total_restarts": wd.total_restarts,
            "consecutive_failures": wd.consecutive_failures,
            "worker_alive": wd.worker_alive,
            "last_heartbeat_age_s": round(wd.last_heartbeat_age, 1),
        }

    # ── Daemon Gate ──────────────────────────────────────────────────

    def acquire_daemon_gate(self) -> bool:
        """Acquire the daemon gate (prevents overlapping daemons).

        Returns True if this process now owns the audio output.
        """
        gate = self._get_daemon_gate()
        if gate is None:
            return True  # graceful — assume we own it
        return gate.acquire()

    def release_daemon_gate(self) -> None:
        """Release the daemon gate."""
        if self._daemon_gate is not None:
            self._daemon_gate.release()

    def daemon_gate_status(self) -> Dict:
        """Return daemon gate diagnostics."""
        gate = self._get_daemon_gate()
        if gate is None:
            return {"available": False, "reason": "daemon_gate module not loaded"}
        return {"available": True, **gate.status()}

    # ── Live Voice Mode (Project Aria) ───────────────────────────────

    def start_live(
        self,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
    ) -> bool:
        """Start live (streaming) voice mode."""
        lm = self._get_live_mode()
        if lm is None:
            return False
        lm.start(voice=voice, rate=rate)
        return lm.is_active

    def feed_live(self, text: str) -> int:
        """Feed text tokens to live mode. Returns sentences spoken."""
        lm = self._get_live_mode()
        if lm is None or not lm.is_active:
            return 0
        return lm.feed(text)

    def flush_live(self) -> bool:
        """Flush remaining live mode buffer."""
        lm = self._get_live_mode()
        if lm is None:
            return False
        return lm.flush()

    def stop_live(self) -> None:
        """Stop live voice mode."""
        if self._live_mode is not None:
            self._live_mode.stop()

    def interrupt_live(self) -> None:
        """Interrupt live mode (discard buffer, stop speaking)."""
        if self._live_mode is not None:
            self._live_mode.interrupt()

    def live_status(self) -> Dict:
        """Return live mode diagnostics."""
        lm = self._get_live_mode()
        if lm is None:
            return {"available": False, "reason": "live_mode module not loaded"}
        return {"available": True, **lm.status()}

    # ── Stream Consumer (Redpanda) ───────────────────────────────────

    async def start_stream(self) -> bool:
        """Start the Redpanda voice stream consumer."""
        sc = self._get_stream_consumer()
        if sc is None:
            return False
        return await sc.start()

    async def stop_stream(self) -> None:
        """Stop the stream consumer."""
        if self._stream_consumer is not None:
            await self._stream_consumer.stop()

    def stream_status(self) -> Dict:
        """Return stream consumer diagnostics."""
        sc = self._get_stream_consumer()
        if sc is None:
            return {"available": False, "reason": "stream_consumer module not loaded"}
        return {"available": True, **sc.status()}

    # ── Health / Status ──────────────────────────────────────────────

    def health(self) -> Dict:
        """Comprehensive health check across all subsystems."""
        uptime = time.time() - self._init_time
        serializer = self._get_serializer()

        subsystems = {}

        # Serializer (always available)
        subsystems["serializer"] = {
            "ok": True,
            "speaking": serializer.is_speaking(),
            "queue_size": serializer.queue_size(),
        }

        # Watchdog
        wd = self._get_watchdog()
        if wd is not None:
            subsystems["watchdog"] = {
                "ok": wd.is_running and wd.worker_alive,
                "running": wd.is_running,
                "worker_alive": wd.worker_alive,
                "restarts": wd.total_restarts,
            }
        else:
            subsystems["watchdog"] = {"ok": False, "loaded": False}

        # Daemon gate
        gate = self._get_daemon_gate()
        if gate is not None:
            subsystems["daemon_gate"] = {
                "ok": True,
                "is_owner": gate.is_owner,
                "is_held": gate.is_held,
            }
        else:
            subsystems["daemon_gate"] = {"ok": False, "loaded": False}

        # Live mode
        lm = self._get_live_mode()
        if lm is not None:
            subsystems["live_mode"] = {
                "ok": True,
                "active": lm.is_active,
                "sentences_spoken": lm.status().get("sentences_spoken", 0),
            }
        else:
            subsystems["live_mode"] = {"ok": False, "loaded": False}

        # Stream consumer
        sc = self._get_stream_consumer()
        if sc is not None:
            subsystems["stream_consumer"] = {
                "ok": sc.is_available,
                "running": sc.is_running,
                "messages": sc.status().get("messages_spoken", 0),
            }
        else:
            subsystems["stream_consumer"] = {"ok": False, "loaded": False}

        all_ok = all(s.get("ok", False) for s in subsystems.values())
        # Core is OK if serializer works
        core_ok = subsystems["serializer"]["ok"]

        return {
            "healthy": core_ok,
            "all_subsystems_ok": all_ok,
            "uptime_s": round(uptime, 1),
            "speak_count": self._speak_count,
            "error_count": self._error_count,
            "subsystems": subsystems,
        }

    def status(self) -> Dict:
        """Human-friendly status report."""
        h = self.health()
        lines = []
        lines.append(f"Voice System: {'HEALTHY' if h['healthy'] else 'DEGRADED'}")
        lines.append(f"Uptime: {h['uptime_s']}s | Speaks: {h['speak_count']} | Errors: {h['error_count']}")

        for name, info in h["subsystems"].items():
            ok_str = "OK" if info.get("ok") else "DOWN"
            detail = " | ".join(
                f"{k}={v}" for k, v in info.items() if k != "ok"
            )
            lines.append(f"  {name}: [{ok_str}] {detail}")

        return {
            "summary": "\n".join(lines),
            "health": h,
        }

    # ── Lazy initializers ────────────────────────────────────────────

    def _get_serializer(self):
        if self._serializer is None:
            from agentic_brain.voice.serializer import get_voice_serializer
            self._serializer = get_voice_serializer()
        return self._serializer

    def _get_watchdog(self):
        if self._watchdog is None:
            try:
                from agentic_brain.voice.watchdog import VoiceWatchdog

                serializer = self._get_serializer()

                def _worker_factory():
                    t = threading.Thread(
                        target=serializer._worker_loop,
                        name="voice-serializer",
                        daemon=True,
                    )
                    t.start()
                    return t

                self._watchdog = VoiceWatchdog(worker_factory=_worker_factory)
            except Exception:
                logger.debug("Watchdog not available", exc_info=True)
                return None
        return self._watchdog

    def _get_daemon_gate(self):
        if self._daemon_gate is None:
            try:
                from agentic_brain.voice.daemon_gate import get_daemon_gate
                self._daemon_gate = get_daemon_gate()
            except Exception:
                logger.debug("DaemonGate not available", exc_info=True)
                return None
        return self._daemon_gate

    def _get_live_mode(self):
        if self._live_mode is None:
            try:
                from agentic_brain.voice.live_mode import get_live_mode
                self._live_mode = get_live_mode()
            except Exception:
                logger.debug("LiveVoiceMode not available", exc_info=True)
                return None
        return self._live_mode

    def _get_stream_consumer(self):
        if self._stream_consumer is None:
            try:
                from agentic_brain.voice.stream_consumer import VoiceStreamConsumer
                self._stream_consumer = VoiceStreamConsumer()
            except Exception:
                logger.debug("VoiceStreamConsumer not available", exc_info=True)
                return None
        return self._stream_consumer


# ── Singleton ────────────────────────────────────────────────────────

_unified: Optional[UnifiedVoiceSystem] = None
_unified_lock = threading.Lock()


def get_unified() -> UnifiedVoiceSystem:
    """Return the process-wide unified voice system singleton."""
    global _unified
    if _unified is None:
        with _unified_lock:
            if _unified is None:
                _unified = UnifiedVoiceSystem()
    return _unified


def _set_unified_for_testing(uv: Optional[UnifiedVoiceSystem]) -> None:
    """Replace the global unified system (tests only)."""
    global _unified
    _unified = uv
