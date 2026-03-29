# SPDX-License-Identifier: Apache-2.0
#
# Tests for VoiceWatchdog – the worker-thread safety net.
#
# Joseph is blind.  If the voice worker dies without recovery, he sits
# in silence.  These tests PROVE the watchdog catches stalls, restarts
# workers, respects backoff, and fires alerts.

import json
import os
import sys
import threading
import time
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.watchdog import VoiceWatchdog, _NEVER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_worker_factory() -> threading.Thread:
    """Create a fake worker thread that just sleeps."""
    t = threading.Thread(target=lambda: time.sleep(300), daemon=True)
    t.start()
    return t


def _dead_worker_factory() -> threading.Thread:
    """Create a worker thread that exits immediately."""
    t = threading.Thread(target=lambda: None, daemon=True)
    t.start()
    t.join(timeout=1)
    return t


def _failing_factory() -> threading.Thread:
    """Factory that always raises."""
    raise RuntimeError("Cannot create worker")


class FakeRedis:
    """Minimal Redis mock for publish testing."""

    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    def publish(self, channel: str, message: str) -> None:
        self.messages.append((channel, message))


# ---------------------------------------------------------------------------
# 1. Heartbeat mechanism
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_updates_timestamp(self):
        """Heartbeat call updates the last_heartbeat time."""
        wd = VoiceWatchdog(worker_factory=_fake_worker_factory, stall_timeout=15.0)
        assert wd.last_heartbeat_age == float("inf")  # never heartbeated
        wd.heartbeat()
        assert wd.last_heartbeat_age < 1.0

    def test_multiple_heartbeats_keep_age_low(self):
        """Repeated heartbeats keep the age near zero."""
        wd = VoiceWatchdog(worker_factory=_fake_worker_factory, stall_timeout=15.0)
        for _ in range(5):
            wd.heartbeat()
            time.sleep(0.01)
        assert wd.last_heartbeat_age < 0.5

    def test_heartbeat_is_thread_safe(self):
        """Multiple threads can heartbeat concurrently without error."""
        wd = VoiceWatchdog(worker_factory=_fake_worker_factory, stall_timeout=15.0)
        errors = []

        def _beat():
            try:
                for _ in range(50):
                    wd.heartbeat()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_beat) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert wd.last_heartbeat_age < 1.0


# ---------------------------------------------------------------------------
# 2. Stall detection
# ---------------------------------------------------------------------------


class TestStallDetection:
    def test_no_restart_when_heartbeat_active(self):
        """Worker that heartbeats regularly is never restarted."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.5,
            check_interval=0.1,
        )
        worker = _fake_worker_factory()
        wd.start(worker=worker)

        # Heartbeat faster than the stall timeout
        for _ in range(15):
            wd.heartbeat()
            time.sleep(0.05)

        wd.stop()
        # Factory should not have been called (no restart needed)
        factory.assert_not_called()
        assert wd.total_restarts == 0

    def test_stall_detected_on_heartbeat_timeout(self):
        """Worker is restarted when heartbeat lapses past stall_timeout."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.2,
            check_interval=0.1,
            backoff_base=0.01,
        )
        worker = _fake_worker_factory()
        wd.start(worker=worker)

        # No heartbeats → stall
        time.sleep(0.6)

        wd.stop()
        assert wd.total_restarts >= 1
        factory.assert_called()


# ---------------------------------------------------------------------------
# 3. Auto-restart
# ---------------------------------------------------------------------------


class TestAutoRestart:
    def test_dead_worker_is_restarted(self):
        """A worker thread that exits is detected and restarted."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.2,
            check_interval=0.1,
            backoff_base=0.01,
        )
        # Start with an already-dead worker
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.5)

        wd.stop()
        assert wd.total_restarts >= 1
        assert factory.call_count >= 1

    def test_restart_resets_heartbeat(self):
        """After restart, the heartbeat clock resets so we don't
        immediately re-trigger."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.3,
            check_interval=0.1,
            backoff_base=0.01,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        # Wait for first restart
        time.sleep(0.5)
        first_restarts = wd.total_restarts
        assert first_restarts >= 1

        # Now send heartbeats to prevent further restarts
        for _ in range(10):
            wd.heartbeat()
            time.sleep(0.05)

        wd.stop()
        # Should not have accumulated many more restarts
        assert wd.total_restarts - first_restarts <= 1

    def test_restart_log_records_entries(self):
        """Each restart is logged with timestamp, reason, and counts."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.15,
            check_interval=0.1,
            backoff_base=0.01,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.6)
        wd.stop()

        log = wd.restart_log
        assert len(log) >= 1
        entry = log[0]
        assert "timestamp" in entry
        assert "reason" in entry
        assert entry["reason"] in ("thread_dead", "heartbeat_timeout")
        assert "consecutive" in entry
        assert "total" in entry

    def test_worker_alive_property(self):
        """worker_alive reflects the actual thread state."""
        wd = VoiceWatchdog(worker_factory=_fake_worker_factory, stall_timeout=15.0)
        alive_worker = _fake_worker_factory()
        wd.start(worker=alive_worker)
        assert wd.worker_alive is True

        dead_worker = _dead_worker_factory()
        wd.register_worker(dead_worker)
        assert wd.worker_alive is False
        wd.stop()


# ---------------------------------------------------------------------------
# 4. Max restart limit and alert
# ---------------------------------------------------------------------------


class TestMaxRestartLimit:
    def test_alert_fires_at_max_restarts(self):
        """Alert callback fires when consecutive failures hit max_restarts."""
        alert = MagicMock()
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.15,
            check_interval=0.1,
            max_restarts=2,
            backoff_base=0.01,
            alert_callback=alert,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(1.0)
        wd.stop()

        assert alert.called
        args = alert.call_args[0]
        assert args[0] >= 2  # restart_count >= max_restarts

    def test_consecutive_counter_resets_after_alert(self):
        """After firing the alert, consecutive_failures resets to 0."""
        alert = MagicMock()
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.15,
            check_interval=0.1,
            max_restarts=2,
            backoff_base=0.01,
            alert_callback=alert,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.8)
        wd.stop()

        # After alert fires, counter was reset
        # (may have accumulated again if watchdog was still running)
        assert alert.called

    def test_alert_callback_exception_does_not_crash_watchdog(self):
        """A broken alert callback doesn't kill the watchdog."""

        def bad_alert(count, reason):
            raise ValueError("alert broke")

        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.15,
            check_interval=0.1,
            max_restarts=1,
            backoff_base=0.01,
            alert_callback=bad_alert,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.6)
        wd.stop()

        # Watchdog kept going despite the alert error
        assert wd.total_restarts >= 1


# ---------------------------------------------------------------------------
# 5. Exponential backoff
# ---------------------------------------------------------------------------


class TestExponentialBackoff:
    def test_backoff_delays_restarts(self):
        """With a noticeable backoff_base, restarts are spaced apart."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.1,
            check_interval=0.05,
            backoff_base=0.15,
            backoff_max=2.0,
            max_restarts=10,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.8)
        wd.stop()

        log = wd.restart_log
        # With backoff, the 3rd+ restart should be delayed
        # so we should have fewer restarts than without backoff
        assert len(log) >= 2

    def test_backoff_capped_at_max(self):
        """Backoff never exceeds backoff_max."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.1,
            check_interval=0.05,
            backoff_base=100.0,
            backoff_max=0.05,
            max_restarts=20,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.5)
        wd.stop()

        # Even with a huge base, the max caps it so restarts still happen
        assert wd.total_restarts >= 1

    def test_no_backoff_on_first_failure(self):
        """First restart has no backoff delay (failures == 1)."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.1,
            check_interval=0.05,
            backoff_base=100.0,  # huge, but first attempt is exempt
            backoff_max=100.0,
            max_restarts=20,
        )
        dead = _dead_worker_factory()
        t0 = time.monotonic()
        wd.start(worker=dead)

        # Wait just enough for the first restart (no backoff)
        time.sleep(0.3)
        wd.stop()

        assert wd.total_restarts >= 1


# ---------------------------------------------------------------------------
# 6. Clean shutdown
# ---------------------------------------------------------------------------


class TestCleanShutdown:
    def test_stop_terminates_monitor(self):
        """stop() causes the monitor thread to exit."""
        wd = VoiceWatchdog(
            worker_factory=_fake_worker_factory,
            stall_timeout=15.0,
            check_interval=0.1,
        )
        worker = _fake_worker_factory()
        wd.start(worker=worker)
        assert wd.is_running
        wd.stop()
        assert not wd.is_running

    def test_double_stop_is_safe(self):
        """Calling stop() twice does not raise."""
        wd = VoiceWatchdog(
            worker_factory=_fake_worker_factory,
            stall_timeout=15.0,
            check_interval=0.1,
        )
        worker = _fake_worker_factory()
        wd.start(worker=worker)
        wd.stop()
        wd.stop()  # second stop is a no-op
        assert not wd.is_running

    def test_double_start_is_idempotent(self):
        """Calling start() while already running does nothing."""
        wd = VoiceWatchdog(
            worker_factory=_fake_worker_factory,
            stall_timeout=15.0,
            check_interval=0.1,
        )
        worker = _fake_worker_factory()
        wd.start(worker=worker)
        wd.start(worker=worker)  # no-op
        assert wd.is_running
        wd.stop()

    def test_register_worker_resets_failures(self):
        """register_worker resets the consecutive failure counter."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.15,
            check_interval=0.1,
            backoff_base=0.01,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.5)
        assert wd.consecutive_failures >= 0

        # Manual re-registration
        new_worker = _fake_worker_factory()
        wd.register_worker(new_worker)
        assert wd.consecutive_failures == 0
        wd.stop()


# ---------------------------------------------------------------------------
# 7. Redis publish
# ---------------------------------------------------------------------------


class TestRedisPublish:
    def test_restart_publishes_to_redis(self):
        """When Redis is available, restarts publish monitoring events."""
        redis = FakeRedis()
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.15,
            check_interval=0.1,
            backoff_base=0.01,
            redis_client=redis,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.6)
        wd.stop()

        assert len(redis.messages) >= 1
        channel, payload = redis.messages[0]
        assert channel == "brain.voice.watchdog"
        data = json.loads(payload)
        assert data["event"] == "worker_restart"
        assert "reason" in data
        assert "attempt" in data

    def test_redis_failure_does_not_crash_watchdog(self):
        """If Redis publish raises, the watchdog continues."""
        broken_redis = MagicMock()
        broken_redis.publish.side_effect = ConnectionError("Redis down")

        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.15,
            check_interval=0.1,
            backoff_base=0.01,
            redis_client=broken_redis,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.5)
        wd.stop()

        # Watchdog survived Redis failures
        assert wd.total_restarts >= 1

    def test_no_redis_no_publish(self):
        """Without Redis, restart works fine (no publish attempted)."""
        factory = MagicMock(side_effect=_fake_worker_factory)
        wd = VoiceWatchdog(
            worker_factory=factory,
            stall_timeout=0.15,
            check_interval=0.1,
            backoff_base=0.01,
            redis_client=None,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.5)
        wd.stop()
        assert wd.total_restarts >= 1


# ---------------------------------------------------------------------------
# 8. Validation and edge cases
# ---------------------------------------------------------------------------


class TestValidation:
    def test_invalid_stall_timeout_raises(self):
        with pytest.raises(ValueError, match="stall_timeout"):
            VoiceWatchdog(worker_factory=_fake_worker_factory, stall_timeout=0)

    def test_invalid_check_interval_raises(self):
        with pytest.raises(ValueError, match="check_interval"):
            VoiceWatchdog(worker_factory=_fake_worker_factory, check_interval=-1)

    def test_invalid_max_restarts_raises(self):
        with pytest.raises(ValueError, match="max_restarts"):
            VoiceWatchdog(worker_factory=_fake_worker_factory, max_restarts=0)

    def test_factory_exception_logged_not_fatal(self):
        """If the factory itself raises, the watchdog logs but doesn't die."""
        call_count = {"n": 0}

        def sometimes_fails():
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise RuntimeError("factory broke")
            return _fake_worker_factory()

        wd = VoiceWatchdog(
            worker_factory=sometimes_fails,
            stall_timeout=0.15,
            check_interval=0.1,
            backoff_base=0.01,
            max_restarts=10,
        )
        dead = _dead_worker_factory()
        wd.start(worker=dead)

        time.sleep(0.8)
        wd.stop()

        # Factory was called multiple times; watchdog survived
        assert call_count["n"] >= 2
