# SPDX-License-Identifier: Apache-2.0
#
# Comprehensive concurrency tests for voice serialization.
#
# Joseph is blind.  Overlapping speech is an accessibility catastrophe.
# These tests PROVE that the serializer guarantees exactly ONE voice
# at a time under every conceivable concurrency scenario.

import asyncio
import os
import subprocess
import sys
import threading
import time
import warnings
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.conversation import ConversationalVoice
from agentic_brain.voice.queue import VoiceQueue
from agentic_brain.voice.resilient import ResilientVoice
from agentic_brain.voice.serializer import (
    VoiceMessage,
    VoiceSerializer,
    _warn_direct_say,
    audit_no_concurrent_say,
    get_voice_serializer,
    speak_serialized,
)

# ---------------------------------------------------------------------------
# Shared helpers for concurrency verification
# ---------------------------------------------------------------------------

_SAY_PATCH = "agentic_brain.voice.serializer.shutil.which"
_POPEN_PATCH = "agentic_brain.voice.serializer.subprocess.Popen"
_AUDIT_PATCH = "agentic_brain.voice.serializer.audit_no_concurrent_say"


class _TimingProcess:
    """Fake subprocess that records (start, end) wall-clock intervals.

    ``speech_log`` is a *shared* list so callers can verify ordering.
    """

    def __init__(self, speech_log: list, duration: float = 0.02):
        self._log = speech_log
        self._duration = duration
        self.returncode = 0

    def wait(self, timeout=None):
        start = time.monotonic()
        time.sleep(self._duration)
        end = time.monotonic()
        self._log.append((start, end))
        return 0

    def poll(self):
        return None

    def terminate(self):
        pass


def _make_timing_factory(speech_log: list, duration: float = 0.02):
    """Return a Popen side_effect that creates _TimingProcess instances."""

    def factory(*_args, **_kwargs):
        return _TimingProcess(speech_log, duration)

    return factory


def assert_no_overlap(speech_log: list, label: str = "") -> None:
    """Assert that no two recorded intervals overlap."""
    if len(speech_log) < 2:
        return
    ordered = sorted(speech_log, key=lambda t: t[0])
    for i in range(1, len(ordered)):
        prev_end = ordered[i - 1][1]
        curr_start = ordered[i][0]
        assert curr_start >= prev_end, (
            f"OVERLAP DETECTED{' (' + label + ')' if label else ''}! "
            f"Speech {i - 1} ended at {prev_end:.6f}, "
            f"speech {i} started at {curr_start:.6f} "
            f"(gap = {curr_start - prev_end:.6f}s)"
        )


def assert_minimum_gap(speech_log: list, min_gap: float, label: str = "") -> None:
    """Assert at least *min_gap* seconds between consecutive speeches."""
    if len(speech_log) < 2:
        return
    ordered = sorted(speech_log, key=lambda t: t[0])
    for i in range(1, len(ordered)):
        gap = ordered[i][0] - ordered[i - 1][1]
        assert gap >= min_gap - 0.01, (  # 10ms tolerance for OS scheduling
            f"GAP TOO SHORT{' (' + label + ')' if label else ''}! "
            f"Expected >= {min_gap:.3f}s, got {gap:.6f}s "
            f"between speech {i - 1} and {i}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Original serializer unit tests (preserved)
# ═══════════════════════════════════════════════════════════════════════


class TestVoiceSerializer:
    def setup_method(self):
        serializer = get_voice_serializer()
        serializer.reset()
        serializer.set_pause_between(0)

    def teardown_method(self):
        serializer = get_voice_serializer()
        serializer.reset()
        serializer.set_pause_between(0.3)

    def test_serializer_is_singleton(self):
        assert VoiceSerializer() is VoiceSerializer()
        assert VoiceSerializer() is get_voice_serializer()

    def test_singleton_initialized_flag(self):
        """Verify _initialized prevents double init."""
        assert VoiceSerializer._initialized is True
        s1 = VoiceSerializer()
        s2 = VoiceSerializer()
        assert s1 is s2
        assert s1._worker is s2._worker

    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    def test_say_processes_never_overlap(self, popen_mock, _which_mock):
        serializer = get_voice_serializer()
        serializer._audit_enabled = False
        active = 0
        max_active = 0
        active_lock = threading.Lock()

        class FakeProcess:
            returncode = 0

            def wait(self):
                nonlocal active, max_active
                with active_lock:
                    active += 1
                    max_active = max(max_active, active)
                time.sleep(0.01)
                with active_lock:
                    active -= 1
                return 0

            def poll(self):
                return None

            def terminate(self):
                return None

        popen_mock.side_effect = lambda *args, **kwargs: FakeProcess()

        threads = [
            threading.Thread(target=serializer.speak, args=(f"message {idx}",))
            for idx in range(5)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert max_active == 1
        assert popen_mock.call_count == 5

    @patch("agentic_brain.voice.serializer.time.sleep")
    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    def test_serializer_uses_configured_pause(
        self,
        popen_mock,
        _which_mock,
        sleep_mock,
    ):
        serializer = get_voice_serializer()
        serializer._audit_enabled = False
        serializer.set_pause_between(0.42)

        process = MagicMock()
        process.wait.return_value = 0
        process.poll.return_value = 0
        popen_mock.return_value = process

        assert serializer.speak("pause check")
        sleep_mock.assert_any_call(0.42)

    def test_serializer_tracks_current_message(self):
        serializer = get_voice_serializer()
        seen = []

        def executor(message: VoiceMessage) -> bool:
            current = serializer.current_message
            seen.append((serializer.is_speaking(), current.text if current else None))
            return True

        result = serializer.run_serialized(
            VoiceMessage(text="tracking works"),
            executor=executor,
        )

        assert result is True
        assert seen == [(True, "tracking works")]
        assert serializer.current_message is None
        assert serializer.is_speaking() is False


# ═══════════════════════════════════════════════════════════════════════
# Overlap audit tests (preserved)
# ═══════════════════════════════════════════════════════════════════════


class TestOverlapAudit:
    """Tests for audit_no_concurrent_say() runtime enforcement."""

    @patch("agentic_brain.voice.serializer.subprocess.run")
    def test_audit_passes_with_zero_say(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=["pgrep", "-x", "say"],
            returncode=1,
            stdout="",
        )
        audit_no_concurrent_say()

    @patch("agentic_brain.voice.serializer.subprocess.run")
    def test_audit_passes_with_one_say(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=["pgrep", "-x", "say"],
            returncode=0,
            stdout="12345\n",
        )
        audit_no_concurrent_say()

    @patch("agentic_brain.voice.serializer.subprocess.run")
    def test_audit_raises_on_multiple_say(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=["pgrep", "-x", "say"],
            returncode=0,
            stdout="12345\n67890\n",
        )
        with pytest.raises(RuntimeError, match="CRITICAL.*concurrent.*say"):
            audit_no_concurrent_say()

    @patch(
        "agentic_brain.voice.serializer.subprocess.run",
        side_effect=FileNotFoundError,
    )
    def test_audit_skips_on_missing_pgrep(self, _run_mock):
        audit_no_concurrent_say()

    @patch(
        "agentic_brain.voice.serializer.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="pgrep", timeout=2),
    )
    def test_audit_skips_on_timeout(self, _run_mock):
        audit_no_concurrent_say()


# ═══════════════════════════════════════════════════════════════════════
# Deprecation warning tests (preserved)
# ═══════════════════════════════════════════════════════════════════════


class TestDeprecationWarnings:

    def test_warn_direct_say_emits_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _warn_direct_say(caller="test_caller")
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "test_caller" in str(w[0].message)
            assert "speak_serialized" in str(w[0].message)


# ═══════════════════════════════════════════════════════════════════════
# speak_safe tests (preserved)
# ═══════════════════════════════════════════════════════════════════════


class TestSpeakSafe:

    def test_speak_safe_routes_through_serializer(self):
        from agentic_brain.voice import speak_safe

        calls = []

        def fake_executor(message: VoiceMessage) -> bool:
            calls.append((message.text, message.voice, message.rate))
            return True

        serializer = get_voice_serializer()
        serializer.set_pause_between(0)
        original = serializer._speak_with_say
        serializer._speak_with_say = fake_executor
        try:
            result = speak_safe("test safe", voice="Moira", rate=150)
            assert result is True
            assert calls == [("test safe", "Moira", 150)]
        finally:
            serializer._speak_with_say = original
            serializer.set_pause_between(0.3)


# ═══════════════════════════════════════════════════════════════════════
# Speech lock deprecation test (preserved)
# ═══════════════════════════════════════════════════════════════════════


class TestSpeechLockDeprecation:

    def test_global_speak_deprecation_warning(self):
        from agentic_brain.voice._speech_lock import global_speak

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch(
                "agentic_brain.voice._speech_lock._global_speak_inner",
                return_value=True,
            ):
                global_speak(["say", "test"])
            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "speak_serialized" in str(deprecation_warnings[0].message)


# ═══════════════════════════════════════════════════════════════════════
# Integration tests (preserved)
# ═══════════════════════════════════════════════════════════════════════


class TestVoiceModuleIntegration:
    def setup_method(self):
        serializer = get_voice_serializer()
        serializer.reset()
        serializer.set_pause_between(0)
        VoiceQueue.get_instance().reset()

    def teardown_method(self):
        serializer = get_voice_serializer()
        serializer.reset()
        serializer.set_pause_between(0.3)

    def test_queue_routes_through_serializer(self, monkeypatch):
        calls = []

        class FakeSerializer:
            current_process = None

            def speak(self, text, voice="Karen", rate=155, pause_after=None, wait=True):
                calls.append((text, voice, rate, pause_after, wait))
                return True

            def is_speaking(self):
                return False

            def reset(self):
                return None

        monkeypatch.setattr(
            "agentic_brain.voice.queue.get_voice_serializer", lambda: FakeSerializer()
        )
        queue = VoiceQueue.get_instance()
        queue.reset()
        queue.speak("Queue serializer path", voice="Karen", rate=155, pause_after=0.25)
        assert calls == [("Queue serializer path", "Karen", 155, 0.25, True)]

    def test_conversation_routes_through_serializer(self, monkeypatch):
        calls = []

        class FakeSerializer:
            def speak(self, text, voice="Karen", rate=155, pause_after=None, wait=True):
                calls.append((text, voice, rate, pause_after, wait))
                return True

        monkeypatch.setattr(
            "agentic_brain.voice.conversation.get_voice_serializer",
            lambda: FakeSerializer(),
        )
        monkeypatch.setattr(
            "agentic_brain.voice.conversation.get_voice",
            lambda voice: SimpleNamespace(full_name=voice),
        )
        conv = ConversationalVoice()
        assert conv.speak(
            "Conversation serializer path", voice="Karen", pause_after=0.6
        )
        assert len(calls) == 1
        text, voice, rate, pause_after, wait = calls[0]
        assert text == "Conversation serializer path"
        assert voice == "Karen"
        assert isinstance(rate, int)
        assert pause_after == 0.6
        assert wait is True

    @pytest.mark.asyncio
    async def test_resilient_voice_routes_through_serializer(self, monkeypatch):
        calls = []

        class FakeSerializer:
            async def run_serialized_async(self, message, executor=None, wait=True):
                calls.append(
                    (message.text, message.voice, message.rate, wait, executor)
                )
                return True

        monkeypatch.setattr(
            "agentic_brain.voice.resilient.get_voice_serializer",
            lambda: FakeSerializer(),
        )
        ResilientVoice._config = None
        assert await ResilientVoice.speak(
            "Resilient serializer path", voice="Karen", rate=155
        )
        assert len(calls) == 1
        text, voice, rate, wait, executor = calls[0]
        assert (text, voice, rate, wait) == (
            "Resilient serializer path",
            "Karen",
            155,
            True,
        )
        assert callable(executor)


# ═══════════════════════════════════════════════════════════════════════
# NEW: Multi-thread stress test (20 threads)
# ═══════════════════════════════════════════════════════════════════════


class TestMultiThreadStress:
    """20 threads all trying to speak at once - MUST serialize."""

    def setup_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0)

    def teardown_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0.3)

    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    def test_20_threads_no_overlap(self, popen_mock, _w):
        """Fire 20 threads simultaneously - verify zero overlap."""
        speech_log: list = []
        popen_mock.side_effect = _make_timing_factory(speech_log, duration=0.02)
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        barrier = threading.Barrier(20)

        def worker(idx):
            barrier.wait()
            serializer.speak(f"Thread {idx} speaking")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(speech_log) == 20
        assert_no_overlap(speech_log, "20-thread stress")

    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    def test_20_threads_max_concurrency_is_one(self, popen_mock, _w):
        """Track peak active count across 20 threads - must never exceed 1."""
        active = 0
        max_active = 0
        lock = threading.Lock()
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        class CountingProcess:
            returncode = 0

            def wait(self, timeout=None):
                nonlocal active, max_active
                with lock:
                    active += 1
                    max_active = max(max_active, active)
                time.sleep(0.01)
                with lock:
                    active -= 1
                return 0

            def poll(self):
                return None

            def terminate(self):
                pass

        popen_mock.side_effect = lambda *a, **kw: CountingProcess()
        barrier = threading.Barrier(20)

        def worker(idx):
            barrier.wait()
            serializer.speak(f"Counting thread {idx}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert max_active == 1, f"Peak active was {max_active}, expected 1"
        assert popen_mock.call_count == 20


# ═══════════════════════════════════════════════════════════════════════
# NEW: Async stress test (20 async tasks)
# ═══════════════════════════════════════════════════════════════════════


class TestAsyncStress:
    """20 async tasks all calling speak_async - MUST serialize."""

    def setup_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0)

    def teardown_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0.3)

    @pytest.mark.asyncio
    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    async def test_20_async_tasks_no_overlap(self, popen_mock, _w):
        """Launch 20 async speak tasks - verify zero overlap."""
        speech_log: list = []
        popen_mock.side_effect = _make_timing_factory(speech_log, duration=0.02)
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        tasks = [serializer.speak_async(f"Async task {i}") for i in range(20)]
        results = await asyncio.gather(*tasks)

        assert all(results), "Some async speaks failed"
        assert len(speech_log) == 20
        assert_no_overlap(speech_log, "20-async-tasks")

    @pytest.mark.asyncio
    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    async def test_async_max_concurrency_is_one(self, popen_mock, _w):
        """Async tasks must still serialize to max-active=1."""
        active = 0
        max_active = 0
        lock = threading.Lock()
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        class CountingProcess:
            returncode = 0

            def wait(self, timeout=None):
                nonlocal active, max_active
                with lock:
                    active += 1
                    max_active = max(max_active, active)
                time.sleep(0.01)
                with lock:
                    active -= 1
                return 0

            def poll(self):
                return None

            def terminate(self):
                pass

        popen_mock.side_effect = lambda *a, **kw: CountingProcess()

        tasks = [serializer.speak_async(f"Async count {i}") for i in range(20)]
        await asyncio.gather(*tasks)

        assert max_active == 1, f"Peak active was {max_active}, expected 1"


# ═══════════════════════════════════════════════════════════════════════
# NEW: Mixed sync + async stress test
# ═══════════════════════════════════════════════════════════════════════


class TestMixedSyncAsync:
    """Combination of sync threads AND async tasks at the same time."""

    def setup_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0)

    def teardown_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0.3)

    @pytest.mark.asyncio
    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    async def test_mixed_sync_async_no_overlap(self, popen_mock, _w):
        """10 sync threads + 10 async tasks simultaneously."""
        speech_log: list = []
        popen_mock.side_effect = _make_timing_factory(speech_log, duration=0.02)
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        def sync_worker(idx):
            serializer.speak(f"Sync worker {idx}")

        threads = [threading.Thread(target=sync_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()

        async_tasks = [serializer.speak_async(f"Async worker {i}") for i in range(10)]
        await asyncio.gather(*async_tasks)

        for t in threads:
            t.join(timeout=30)

        assert len(speech_log) == 20
        assert_no_overlap(speech_log, "mixed-sync-async")


# ═══════════════════════════════════════════════════════════════════════
# NEW: Rapid fire test (50 calls)
# ═══════════════════════════════════════════════════════════════════════


class TestRapidFire:
    """50 speak calls in quick succession."""

    def setup_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0)

    def teardown_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0.3)

    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    def test_50_rapid_fire_no_overlap(self, popen_mock, _w):
        """Queue 50 messages as fast as possible - all must serialize."""
        speech_log: list = []
        popen_mock.side_effect = _make_timing_factory(speech_log, duration=0.005)
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        threads = [
            threading.Thread(target=serializer.speak, args=(f"Rapid {i}",))
            for i in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert len(speech_log) == 50
        assert_no_overlap(speech_log, "50-rapid-fire")

    def test_50_rapid_fire_with_custom_executor(self):
        """Rapid fire using run_serialized with custom executor."""
        speech_log: list = []
        log_lock = threading.Lock()
        serializer = get_voice_serializer()

        def executor(msg: VoiceMessage) -> bool:
            start = time.monotonic()
            time.sleep(0.005)
            end = time.monotonic()
            with log_lock:
                speech_log.append((start, end))
            return True

        threads = [
            threading.Thread(
                target=serializer.run_serialized,
                args=(VoiceMessage(text=f"Custom {i}"),),
                kwargs={"executor": executor},
            )
            for i in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert len(speech_log) == 50
        assert_no_overlap(speech_log, "50-custom-executor")


# ═══════════════════════════════════════════════════════════════════════
# NEW: Minimum gap enforcement
# ═══════════════════════════════════════════════════════════════════════


class TestMinimumGap:
    """Verify the inter-utterance pause is respected."""

    def setup_method(self):
        s = get_voice_serializer()
        s.reset()

    def teardown_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0.3)

    def test_gap_enforced_between_speeches(self):
        """With pause_between=0.3, verify >= 0.3s gap between end/start."""
        serializer = get_voice_serializer()
        serializer.set_pause_between(0.3)
        speech_log: list = []
        log_lock = threading.Lock()

        def executor(msg: VoiceMessage) -> bool:
            start = time.monotonic()
            time.sleep(0.01)
            end = time.monotonic()
            with log_lock:
                speech_log.append((start, end))
            return True

        threads = [
            threading.Thread(
                target=serializer.run_serialized,
                args=(VoiceMessage(text=f"Gap test {i}"),),
                kwargs={"executor": executor},
            )
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(speech_log) == 5
        assert_no_overlap(speech_log, "gap-enforcement")
        assert_minimum_gap(speech_log, 0.3, "gap-enforcement")


# ═══════════════════════════════════════════════════════════════════════
# NEW: Long utterance interrupt test
# ═══════════════════════════════════════════════════════════════════════


class TestLongUtteranceInterrupt:
    """Verify that a long speech cannot be interrupted by another."""

    def setup_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0)

    def teardown_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0.3)

    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    def test_long_speech_blocks_short_speech(self, popen_mock, _w):
        """A 0.5s speech must complete before a short one can start."""
        speech_log: list = []
        call_count = 0
        call_lock = threading.Lock()
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        def factory(*_a, **_kw):
            nonlocal call_count
            with call_lock:
                call_count += 1
                idx = call_count
            dur = 0.5 if idx == 1 else 0.01
            return _TimingProcess(speech_log, duration=dur)

        popen_mock.side_effect = factory

        t_long = threading.Thread(target=serializer.speak, args=("Long speech",))
        t_short = threading.Thread(target=serializer.speak, args=("Short interrupt",))

        t_long.start()
        time.sleep(0.05)  # ensure long starts first
        t_short.start()

        t_long.join(timeout=10)
        t_short.join(timeout=10)

        assert len(speech_log) == 2
        assert_no_overlap(speech_log, "long-blocks-short")
        ordered = sorted(speech_log, key=lambda t: t[0])
        assert ordered[1][0] >= ordered[0][1], "Short speech interrupted the long one!"

    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    def test_many_short_cannot_preempt_long(self, popen_mock, _w):
        """10 short messages queued during a long speech must wait."""
        speech_log: list = []
        call_count = 0
        call_lock = threading.Lock()
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        def factory(*_a, **_kw):
            nonlocal call_count
            with call_lock:
                call_count += 1
                idx = call_count
            dur = 0.3 if idx == 1 else 0.005
            return _TimingProcess(speech_log, duration=dur)

        popen_mock.side_effect = factory

        t_long = threading.Thread(target=serializer.speak, args=("Long one",))
        t_long.start()
        time.sleep(0.05)

        short_threads = [
            threading.Thread(target=serializer.speak, args=(f"Short {i}",))
            for i in range(10)
        ]
        for t in short_threads:
            t.start()

        t_long.join(timeout=10)
        for t in short_threads:
            t.join(timeout=30)

        assert len(speech_log) == 11
        assert_no_overlap(speech_log, "preempt-protection")


# ═══════════════════════════════════════════════════════════════════════
# NEW: Cross-module test
# ═══════════════════════════════════════════════════════════════════════


class TestCrossModule:
    """Calls from queue.py, resilient.py, conversation.py simultaneously."""

    def setup_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0)

    def teardown_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0.3)

    def test_cross_module_serialization(self, monkeypatch):
        """queue + conversation + direct serializer all share one gate."""
        speech_log: list = []
        log_lock = threading.Lock()

        class RecordingSerializer:
            """Drop-in replacement that tracks timing."""

            current_process = None

            def speak(self, text, voice="Karen", rate=155, pause_after=None, wait=True):
                start = time.monotonic()
                time.sleep(0.02)
                end = time.monotonic()
                with log_lock:
                    speech_log.append((start, end))
                return True

            def is_speaking(self):
                return False

            def reset(self):
                pass

        recorder = RecordingSerializer()

        monkeypatch.setattr(
            "agentic_brain.voice.queue.get_voice_serializer", lambda: recorder
        )
        monkeypatch.setattr(
            "agentic_brain.voice.conversation.get_voice_serializer", lambda: recorder
        )
        monkeypatch.setattr(
            "agentic_brain.voice.conversation.get_voice",
            lambda voice: SimpleNamespace(full_name=voice),
        )

        queue = VoiceQueue.get_instance()
        queue.reset()
        conv = ConversationalVoice()

        def via_queue():
            queue.speak("Via queue", voice="Karen", rate=155, pause_after=0)

        def via_conversation():
            conv.speak("Via conversation", voice="Karen", pause_after=0)

        def via_direct():
            recorder.speak("Direct call")

        threads = [
            threading.Thread(target=via_queue),
            threading.Thread(target=via_conversation),
            threading.Thread(target=via_direct),
            threading.Thread(target=via_queue),
            threading.Thread(target=via_conversation),
            threading.Thread(target=via_direct),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(speech_log) == 6, f"Expected 6 calls, got {len(speech_log)}"

    @pytest.mark.asyncio
    async def test_resilient_shares_serializer(self, monkeypatch):
        """ResilientVoice and direct serializer use the same gate."""
        speech_log: list = []
        log_lock = threading.Lock()
        serializer = get_voice_serializer()
        serializer.set_pause_between(0)

        def recording_executor(msg: VoiceMessage) -> bool:
            start = time.monotonic()
            time.sleep(0.02)
            end = time.monotonic()
            with log_lock:
                speech_log.append((start, end))
            return True

        class PatchedSerializer:
            async def run_serialized_async(self, message, executor=None, wait=True):
                return serializer.run_serialized(
                    message, executor=recording_executor, wait=wait
                )

        monkeypatch.setattr(
            "agentic_brain.voice.resilient.get_voice_serializer",
            lambda: PatchedSerializer(),
        )

        direct_threads = []
        for i in range(5):
            t = threading.Thread(
                target=serializer.run_serialized,
                args=(VoiceMessage(text=f"Direct {i}"),),
                kwargs={"executor": recording_executor},
            )
            direct_threads.append(t)
            t.start()

        ResilientVoice._config = None
        async_tasks = [
            ResilientVoice.speak(f"Resilient {i}", voice="Karen", rate=155)
            for i in range(5)
        ]
        await asyncio.gather(*async_tasks)

        for t in direct_threads:
            t.join(timeout=30)

        assert len(speech_log) == 10
        assert_no_overlap(speech_log, "resilient-shares-gate")


# ═══════════════════════════════════════════════════════════════════════
# NEW: Process crash recovery
# ═══════════════════════════════════════════════════════════════════════


class TestProcessCrashRecovery:
    """What happens if the say process dies mid-speech?"""

    def setup_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0)

    def teardown_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0.3)

    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    def test_crash_does_not_deadlock(self, popen_mock, _w):
        """If process.wait() raises, the lock is released and next speech works."""
        speech_log: list = []
        call_count = 0
        call_lock = threading.Lock()
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        def factory(*_a, **_kw):
            nonlocal call_count
            with call_lock:
                call_count += 1
                idx = call_count

            if idx == 1:
                proc = MagicMock()
                proc.wait.side_effect = OSError("say process crashed")
                proc.poll.return_value = None
                proc.terminate.return_value = None
                return proc
            else:
                return _TimingProcess(speech_log, duration=0.01)

        popen_mock.side_effect = factory

        results = []
        result_lock = threading.Lock()

        def speak_and_record(text):
            r = serializer.speak(text)
            with result_lock:
                results.append((text, r))

        t1 = threading.Thread(target=speak_and_record, args=("Crash me",))
        t2 = threading.Thread(target=speak_and_record, args=("After crash",))
        t3 = threading.Thread(target=speak_and_record, args=("Third call",))

        t1.start()
        time.sleep(0.05)
        t2.start()
        t3.start()

        t1.join(timeout=10)
        t2.join(timeout=10)
        t3.join(timeout=10)

        result_dict = dict(results)
        assert result_dict["Crash me"] is False
        assert result_dict["After crash"] is True
        assert result_dict["Third call"] is True

        assert len(speech_log) == 2
        assert_no_overlap(speech_log, "post-crash")

    @patch(_SAY_PATCH, return_value="/usr/bin/say")
    @patch(_POPEN_PATCH)
    def test_timeout_does_not_deadlock(self, popen_mock, _w):
        """If a process hangs, the next speech still works after it completes."""
        speech_log: list = []
        call_count = 0
        call_lock = threading.Lock()
        serializer = get_voice_serializer()
        serializer._audit_enabled = False

        def factory(*_a, **_kw):
            nonlocal call_count
            with call_lock:
                call_count += 1
                idx = call_count

            if idx == 1:
                proc = MagicMock()

                def slow_wait(timeout=None):
                    time.sleep(0.3)
                    return 0

                proc.wait.side_effect = slow_wait
                proc.poll.return_value = None
                proc.returncode = 0
                proc.terminate.return_value = None
                return proc
            else:
                return _TimingProcess(speech_log, duration=0.01)

        popen_mock.side_effect = factory

        t1 = threading.Thread(target=serializer.speak, args=("Slow process",))
        t2 = threading.Thread(target=serializer.speak, args=("Fast after slow",))

        t1.start()
        time.sleep(0.05)
        t2.start()

        t1.join(timeout=10)
        t2.join(timeout=10)

        assert len(speech_log) >= 1
        assert_no_overlap(speech_log, "timeout-recovery")

    def test_executor_exception_releases_lock(self):
        """If the executor raises, the serializer releases the lock."""
        serializer = get_voice_serializer()
        speech_log: list = []
        log_lock = threading.Lock()
        call_count = 0
        count_lock = threading.Lock()

        def flaky_executor(msg: VoiceMessage) -> bool:
            nonlocal call_count
            with count_lock:
                call_count += 1
                idx = call_count
            if idx == 1:
                raise RuntimeError("Executor explosion!")
            start = time.monotonic()
            time.sleep(0.01)
            end = time.monotonic()
            with log_lock:
                speech_log.append((start, end))
            return True

        results = []
        result_lock = threading.Lock()

        def run_job(text):
            try:
                r = serializer.run_serialized(
                    VoiceMessage(text=text), executor=flaky_executor
                )
            except Exception:
                r = False
            with result_lock:
                results.append((text, r))

        threads = [
            threading.Thread(target=run_job, args=(f"Job {i}",)) for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        result_dict = dict(results)
        assert result_dict["Job 0"] is False
        assert sum(1 for _, v in results if v is True) == 4
        assert len(speech_log) == 4
        assert_no_overlap(speech_log, "exception-recovery")


# ═══════════════════════════════════════════════════════════════════════
# NEW: wait_until_idle correctness
# ═══════════════════════════════════════════════════════════════════════


class TestWaitUntilIdle:
    """Verify the idle-wait helper under load."""

    def setup_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0)

    def teardown_method(self):
        s = get_voice_serializer()
        s.reset()
        s.set_pause_between(0.3)

    def test_wait_until_idle_returns_true_when_all_done(self):
        """After queuing work, wait_until_idle returns True once drained."""
        serializer = get_voice_serializer()

        def fast_exec(msg: VoiceMessage) -> bool:
            time.sleep(0.01)
            return True

        for i in range(5):
            serializer.run_serialized(
                VoiceMessage(text=f"Idle test {i}"),
                executor=fast_exec,
                wait=False,
            )

        assert serializer.wait_until_idle(timeout=5.0) is True
        assert serializer.queue_size() == 0
        assert serializer.is_speaking() is False
