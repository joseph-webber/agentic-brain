# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Tests for the global speech lock - ensures NO voice overlap.

CRITICAL for accessibility - Joseph is blind and overlapping voices
make it impossible for him to understand what's being said.

Tests verify:
- ✅ Only ONE process runs at a time (global mutex)
- ✅ Concurrent calls are serialized (no overlap)
- ✅ Inter-utterance gap is enforced
- ✅ Timeout handling works
- ✅ All voice modules route through the lock
"""

import os
import subprocess
import sys
import threading
import time
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice._speech_lock import (
    INTER_UTTERANCE_GAP,
    global_speak,
    interrupt_speech,
    is_speech_active,
)


class TestGlobalSpeechLock:
    """Test the global speech lock prevents overlap."""

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_single_speak_succeeds(self, mock_popen):
        """Single speech call completes normally."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = None
        proc.returncode = 0
        mock_popen.return_value = proc

        result = global_speak(["say", "Hello"], inter_gap=0)
        assert result is True
        mock_popen.assert_called_once()
        proc.wait.assert_called_once()

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_concurrent_calls_are_serialized(self, mock_popen):
        """Two concurrent speak calls must NOT overlap."""
        execution_log = []

        def mock_wait(timeout=None):
            # Record when each "speech" starts and ends
            execution_log.append(("start", time.monotonic()))
            time.sleep(0.1)  # Simulate speech duration
            execution_log.append(("end", time.monotonic()))

        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.side_effect = mock_wait
        proc.returncode = 0
        mock_popen.return_value = proc

        # Launch two concurrent speech calls
        t1 = threading.Thread(
            target=global_speak, args=(["say", "First"],), kwargs={"inter_gap": 0}
        )
        t2 = threading.Thread(
            target=global_speak, args=(["say", "Second"],), kwargs={"inter_gap": 0}
        )

        t1.start()
        time.sleep(0.01)  # Ensure t1 grabs the lock first
        t2.start()

        t1.join(timeout=5)
        t2.join(timeout=5)

        # Verify: second speech must start AFTER first speech ends
        assert len(execution_log) == 4, f"Expected 4 events, got {len(execution_log)}"
        first_end = execution_log[1][1]
        second_start = execution_log[2][1]
        assert second_start >= first_end, (
            f"OVERLAP DETECTED! Second speech started at {second_start} "
            f"but first ended at {first_end}"
        )

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_inter_utterance_gap_enforced(self, mock_popen):
        """A pause is inserted between consecutive utterances."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = None
        proc.returncode = 0
        mock_popen.return_value = proc

        start = time.monotonic()
        global_speak(["say", "First"], inter_gap=INTER_UTTERANCE_GAP)
        global_speak(["say", "Second"], inter_gap=INTER_UTTERANCE_GAP)
        elapsed = time.monotonic() - start

        # Should have at least 2x the gap (one after each utterance)
        assert elapsed >= INTER_UTTERANCE_GAP * 2, (
            f"Expected at least {INTER_UTTERANCE_GAP * 2}s gap, "
            f"but only {elapsed:.3f}s elapsed"
        )

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_timeout_does_not_block_forever(self, mock_popen):
        """Speech that times out is terminated, not hung."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.side_effect = subprocess.TimeoutExpired(cmd="say", timeout=1)
        proc.returncode = None
        mock_popen.return_value = proc

        result = global_speak(["say", "Stuck"], timeout=1, inter_gap=0)
        assert result is False
        proc.terminate.assert_called_once()

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_command_not_found_returns_false(self, mock_popen):
        """Missing command returns False without crashing."""
        mock_popen.side_effect = FileNotFoundError("say not found")

        result = global_speak(["say", "test"], inter_gap=0)
        assert result is False

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_many_concurrent_threads_no_overlap(self, mock_popen):
        """Stress test: 10 threads all try to speak simultaneously."""
        execution_windows = []
        lock = threading.Lock()

        def mock_wait(timeout=None):
            start = time.monotonic()
            time.sleep(0.02)
            end = time.monotonic()
            with lock:
                execution_windows.append((start, end))

        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.side_effect = mock_wait
        proc.returncode = 0
        mock_popen.return_value = proc

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=global_speak,
                args=(["say", f"Message {i}"],),
                kwargs={"inter_gap": 0},
            )
            threads.append(t)

        # Start all threads at once
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Verify no overlaps: each window must not overlap with any other
        execution_windows.sort(key=lambda w: w[0])
        for i in range(len(execution_windows) - 1):
            current_end = execution_windows[i][1]
            next_start = execution_windows[i + 1][0]
            assert next_start >= current_end, (
                f"OVERLAP between utterance {i} (end={current_end:.4f}) "
                f"and {i+1} (start={next_start:.4f})"
            )


class TestVoiceModulesUseGlobalLock:
    """Verify all voice modules route through the global lock."""

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_queue_uses_global_lock(self, mock_popen):
        """VoiceQueue.speak() routes through global_speak."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = None
        proc.returncode = 0
        mock_popen.return_value = proc

        from agentic_brain.voice.queue import VoiceQueue

        # Reset singleton for clean test
        VoiceQueue._instance = None
        q = VoiceQueue.get_instance()
        q.speak("Test from queue", voice="Karen", rate=155, pause_after=0)

        # Verify Popen was called (through global_speak)
        mock_popen.assert_called()
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "say"
        assert "Karen" in cmd
        assert "Test from queue" in cmd

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_conversation_uses_global_lock(self, mock_popen):
        """ConversationalVoice.speak() routes through global_speak."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = None
        proc.returncode = 0
        mock_popen.return_value = proc

        from agentic_brain.voice.conversation import ConversationalVoice

        conv = ConversationalVoice()
        conv.speak("Test from conversation", voice="Karen")

        mock_popen.assert_called()
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "say"

    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    @patch("agentic_brain.voice.serializer.audit_no_concurrent_say")
    def test_voiceover_uses_global_lock(self, mock_audit, mock_popen):
        """VoiceOverCoordinator.speak_coordinated() routes through serializer
        which now shares the ONE global lock from _speech_lock.py."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = 0
        proc.returncode = 0
        mock_popen.return_value = proc

        from agentic_brain.voice.voiceover import VoiceOverCoordinator

        with patch.object(VoiceOverCoordinator, "_update_status"):
            vo = VoiceOverCoordinator()
            vo.speak_coordinated("Test from voiceover", wait_for_vo=False)

        mock_popen.assert_called()
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "say"

        # Verify the serializer's lock IS the global lock from _speech_lock
        from agentic_brain.voice._speech_lock import get_global_lock
        from agentic_brain.voice.serializer import get_voice_serializer

        assert get_voice_serializer()._speech_lock is get_global_lock()

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_audio_speak_uses_global_lock(self, mock_popen):
        """Audio.speak() routes through global_speak on macOS."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = None
        proc.returncode = 0
        mock_popen.return_value = proc

        from agentic_brain.audio import Audio, AudioConfig, Platform

        with patch.object(Platform, "current", return_value=Platform.MACOS):
            with patch("shutil.which", return_value="/usr/bin/say"):
                audio = Audio()
                audio.speak("Test from audio", voice="Karen", wait=True)

        mock_popen.assert_called()
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "say"

    @patch("agentic_brain.voice._speech_lock.subprocess.Popen")
    def test_audio_speak_wait_false_still_uses_lock(self, mock_popen):
        """Audio.speak(wait=False) STILL uses global lock (no fire-and-forget)."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = None
        proc.returncode = 0
        mock_popen.return_value = proc

        from agentic_brain.audio import Audio, AudioConfig, Platform

        with patch.object(Platform, "current", return_value=Platform.MACOS):
            with patch("shutil.which", return_value="/usr/bin/say"):
                audio = Audio()
                audio.speak("Fire and forget test", voice="Karen", wait=False)

        # Must still call Popen + wait (via global_speak), NOT fire-and-forget
        mock_popen.assert_called()
        proc.wait.assert_called()


class TestUnifiedLockIdentity:
    """Verify every speech path shares the ONE global lock."""

    def test_serializer_uses_global_lock(self):
        """VoiceSerializer._speech_lock is the global lock from _speech_lock.py."""
        from agentic_brain.voice._speech_lock import get_global_lock
        from agentic_brain.voice.serializer import get_voice_serializer

        assert get_voice_serializer()._speech_lock is get_global_lock()

    def test_global_speak_uses_same_lock(self):
        """_global_speak_inner uses the same lock object as the serializer."""
        from agentic_brain.voice._speech_lock import _speech_lock, get_global_lock
        from agentic_brain.voice.serializer import get_voice_serializer

        assert get_voice_serializer()._speech_lock is _speech_lock
        assert get_global_lock() is _speech_lock

    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    @patch("agentic_brain.voice.serializer.audit_no_concurrent_say")
    def test_concurrent_serializer_and_global_speak_no_overlap(
        self, mock_audit, mock_popen
    ):
        """Simultaneous calls through serializer and global_speak never overlap."""
        import threading

        from agentic_brain.voice._speech_lock import _global_speak_inner
        from agentic_brain.voice.serializer import get_voice_serializer

        execution_log = []
        log_lock = threading.Lock()

        def mock_subprocess(*args, **kwargs):
            proc = MagicMock()
            proc.poll.return_value = None

            def fake_wait(timeout=None):
                with log_lock:
                    execution_log.append(("start", threading.current_thread().name))
                import time

                time.sleep(0.05)
                with log_lock:
                    execution_log.append(("end", threading.current_thread().name))
                return 0

            proc.wait.side_effect = fake_wait
            proc.returncode = 0
            return proc

        mock_popen.side_effect = mock_subprocess

        # Also mock Popen in _speech_lock for global_speak path
        with patch(
            "agentic_brain.voice._speech_lock.subprocess.Popen"
        ) as mock_gs_popen:
            mock_gs_popen.side_effect = mock_subprocess

            def call_serializer():
                get_voice_serializer().speak("via serializer", wait=True)

            def call_global_speak():
                _global_speak_inner(
                    ["say", "-v", "Karen", "via global_speak"], timeout=60
                )

            t1 = threading.Thread(target=call_serializer, name="serializer-thread")
            t2 = threading.Thread(target=call_global_speak, name="global-speak-thread")

            t1.start()
            import time

            time.sleep(0.01)  # slight stagger
            t2.start()

            t1.join(timeout=5)
            t2.join(timeout=5)

        # Verify no overlapping execution windows
        starts = [i for i, (ev, _) in enumerate(execution_log) if ev == "start"]
        ends = [i for i, (ev, _) in enumerate(execution_log) if ev == "end"]
        assert len(starts) == 2, f"Expected 2 starts, got {starts} in {execution_log}"
        assert len(ends) == 2, f"Expected 2 ends, got {ends} in {execution_log}"
        # First must end before second starts
        assert ends[0] < starts[1], f"Overlap detected! Log: {execution_log}"
