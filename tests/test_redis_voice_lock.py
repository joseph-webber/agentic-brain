# SPDX-License-Identifier: Apache-2.0
#
# Tests for the Redis-backed distributed voice lock.
#
# Cross-process voice overlap is an accessibility
# catastrophe.  These tests prove the distributed lock prevents it.

import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice._speech_lock import (
    INTER_UTTERANCE_GAP,
    RedisVoiceLock,
    _global_speak_inner,
    _set_speech_lock_for_testing,
    get_global_lock,
    interrupt_speech,
    is_speech_active,
    voice_lock_status,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal in-memory Redis stub supporting SET NX EX, GET, DEL, EVAL."""

    def __init__(self, *, fail: bool = False):
        self._store: dict = {}
        self._fail = fail

    def ping(self):
        if self._fail:
            raise ConnectionError("Redis down")
        return True

    def set(self, key, value, *, nx=False, ex=None):
        if self._fail:
            raise ConnectionError("Redis down")
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    def get(self, key):
        if self._fail:
            raise ConnectionError("Redis down")
        return self._store.get(key)

    def delete(self, key):
        if self._fail:
            raise ConnectionError("Redis down")
        return self._store.pop(key, None) is not None

    def ttl(self, key):
        if self._fail:
            raise ConnectionError("Redis down")
        return 30 if key in self._store else -2

    def eval(self, script, numkeys, *args):
        """Very simple Lua emulator for the two scripts we use."""
        if self._fail:
            raise ConnectionError("Redis down")
        key = args[0]
        expected_owner = args[1]
        current = self._store.get(key)
        if current == expected_owner:
            if "del" in script:
                self._store.pop(key, None)
                return 1
            if "expire" in script:
                return 1
        return 0


# ---------------------------------------------------------------------------
# Core lock behaviour
# ---------------------------------------------------------------------------


class TestRedisVoiceLockAcquireRelease:
    """Verify basic acquire/release semantics with Redis."""

    def test_acquire_and_release(self):
        r = FakeRedis()
        lock = RedisVoiceLock(redis_client=r, ttl=5)

        assert lock.acquire(timeout=1)
        assert lock.is_held
        assert lock.mode == "redis"
        assert r.get("voice:speaking") == lock.owner

        lock.release()
        assert not lock.is_held
        assert lock.mode == "none"
        assert r.get("voice:speaking") is None

    def test_context_manager(self):
        r = FakeRedis()
        lock = RedisVoiceLock(redis_client=r, ttl=5)

        with lock:
            assert lock.is_held
            assert lock.mode == "redis"
        assert not lock.is_held

    def test_release_idempotent(self):
        r = FakeRedis()
        lock = RedisVoiceLock(redis_client=r, ttl=5)
        lock.acquire(timeout=1)
        lock.release()
        lock.release()  # Should not raise
        assert not lock.is_held


class TestRedisVoiceLockContention:
    """Verify that two owners cannot hold the lock simultaneously."""

    def test_second_acquire_fails_immediately(self):
        r = FakeRedis()
        lock_a = RedisVoiceLock(redis_client=r, ttl=5)
        lock_b = RedisVoiceLock(redis_client=r, ttl=5)

        assert lock_a.acquire(timeout=1)
        assert not lock_b.acquire(timeout=0.2)

        lock_a.release()
        assert lock_b.acquire(timeout=1)
        lock_b.release()

    def test_concurrent_threads_serialize(self):
        """Multiple threads must execute sequentially, never overlap."""
        r = FakeRedis()
        order: list = []
        errors: list = []

        def worker(lock: RedisVoiceLock, label: str):
            try:
                if lock.acquire(timeout=5):
                    order.append(f"{label}-start")
                    time.sleep(0.05)
                    order.append(f"{label}-end")
                    lock.release()
            except Exception as exc:
                errors.append(exc)

        threads = []
        for i in range(4):
            lk = RedisVoiceLock(redis_client=r, ttl=5)
            t = threading.Thread(target=worker, args=(lk, str(i)))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Unexpected errors: {errors}"
        # Verify no overlaps: every start must be followed by its end
        # before the next start.
        for idx in range(0, len(order), 2):
            label = order[idx].split("-")[0]
            assert order[idx] == f"{label}-start"
            assert order[idx + 1] == f"{label}-end"


class TestRedisVoiceLockOwnerSafety:
    """Release must only delete the key if we still own it."""

    def test_stolen_lock_not_deleted(self):
        r = FakeRedis()
        lock = RedisVoiceLock(redis_client=r, ttl=5)
        lock.acquire(timeout=1)

        # Simulate another process stealing the key (TTL expired, re-acquired).
        r._store["voice:speaking"] = "other-owner-xyz"

        lock.release()
        # The key must still belong to the other owner.
        assert r.get("voice:speaking") == "other-owner-xyz"


# ---------------------------------------------------------------------------
# Fallback to local lock
# ---------------------------------------------------------------------------


class TestLocalFallback:
    """When Redis is down the lock must fall back to a local threading.Lock."""

    def test_fallback_on_connection_failure(self):
        r = FakeRedis(fail=True)
        lock = RedisVoiceLock(redis_client=r, ttl=5)

        assert lock.acquire(timeout=1)
        assert lock.is_held
        assert lock.mode == "local"
        lock.release()
        assert not lock.is_held

    def test_fallback_context_manager(self):
        r = FakeRedis(fail=True)
        lock = RedisVoiceLock(redis_client=r, ttl=5)

        with lock:
            assert lock.mode == "local"
        assert not lock.is_held

    @patch("agentic_brain.voice._speech_lock.RedisVoiceLock._ensure_redis")
    def test_no_redis_import_needed(self, mock_ensure):
        """If Redis is unavailable at import time, the lock still works."""
        mock_ensure.return_value = False
        lock = RedisVoiceLock(ttl=5)

        assert lock.acquire(timeout=1)
        assert lock.mode == "local"
        lock.release()


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


class TestHeartbeat:
    """The heartbeat thread must renew the TTL while the lock is held."""

    def test_heartbeat_starts_and_stops(self):
        r = FakeRedis()
        lock = RedisVoiceLock(redis_client=r, ttl=5, heartbeat_interval=0.1)
        lock.acquire(timeout=1)

        assert lock._heartbeat_thread is not None
        assert lock._heartbeat_thread.is_alive()

        lock.release()
        time.sleep(0.15)
        assert lock._heartbeat_thread is None or not lock._heartbeat_thread.is_alive()

    def test_heartbeat_renews_key(self):
        r = FakeRedis()
        lock = RedisVoiceLock(redis_client=r, ttl=5, heartbeat_interval=0.05)
        lock.acquire(timeout=1)

        # Wait for at least one heartbeat cycle.
        time.sleep(0.15)

        # Key must still be present (heartbeat renewed it).
        assert r.get("voice:speaking") == lock.owner

        lock.release()


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


class TestDiagnostics:
    def test_status_with_redis(self):
        r = FakeRedis()
        lock = RedisVoiceLock(redis_client=r, ttl=5)
        lock.acquire(timeout=1)

        info = lock.status()
        assert info["held_by_us"] is True
        assert info["mode"] == "redis"
        assert info["redis_available"] is True
        assert info["redis_lock_owner"] == lock.owner

        lock.release()

    def test_status_without_redis(self):
        r = FakeRedis(fail=True)
        lock = RedisVoiceLock(redis_client=r, ttl=5)

        # Force a connection attempt so the lock discovers Redis is down.
        lock.acquire(timeout=0.1)
        lock.release()

        info = lock.status()
        assert info["held_by_us"] is False
        assert info["redis_available"] is False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestModuleLevelAPI:
    """Verify that the public module API still works."""

    def test_get_global_lock_returns_redis_voice_lock(self):
        lock = get_global_lock()
        assert isinstance(lock, RedisVoiceLock)

    def test_voice_lock_status_returns_dict(self):
        info = voice_lock_status()
        assert isinstance(info, dict)
        assert "held_by_us" in info

    def test_is_speech_active_default(self):
        assert not is_speech_active()

    def test_interrupt_speech_safe(self):
        interrupt_speech()  # Should not raise even with nothing active.


# ---------------------------------------------------------------------------
# Integration with _global_speak_inner
# ---------------------------------------------------------------------------


class TestGlobalSpeakInner:
    """Verify that the speak helper acquires the distributed lock."""

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_speak_acquires_and_releases(self, mock_popen):
        r = FakeRedis()
        lock = RedisVoiceLock(redis_client=r, ttl=5)
        _set_speech_lock_for_testing(lock)

        proc = MagicMock()
        proc.poll.return_value = 0
        proc.wait.return_value = None
        proc.returncode = 0
        mock_popen.return_value = proc

        result = _global_speak_inner(
            ["say", "hello"],
            timeout=5,
            inter_gap=0,
        )
        assert result is True
        # Lock should be released after the call.
        assert not lock.is_held
        assert r.get("voice:speaking") is None

        # Restore default lock.
        _set_speech_lock_for_testing(None)

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_speak_releases_lock_on_error(self, mock_popen):
        r = FakeRedis()
        lock = RedisVoiceLock(redis_client=r, ttl=5)
        _set_speech_lock_for_testing(lock)

        mock_popen.side_effect = FileNotFoundError("say not found")

        result = _global_speak_inner(
            ["say", "hello"],
            timeout=5,
            inter_gap=0,
        )
        assert result is False
        assert not lock.is_held

        _set_speech_lock_for_testing(None)


# ---------------------------------------------------------------------------
# Serializer integration (light check)
# ---------------------------------------------------------------------------


class TestSerializerIntegration:
    """Verify the serializer picks up the RedisVoiceLock type."""

    def test_serializer_speech_lock_is_redis_type(self):
        from agentic_brain.voice.serializer import VoiceSerializer

        vs = VoiceSerializer()
        assert isinstance(vs._speech_lock, RedisVoiceLock)
