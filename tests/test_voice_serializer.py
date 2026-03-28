# SPDX-License-Identifier: Apache-2.0

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
    _legacy_speak,
    _warn_direct_say,
    audit_no_concurrent_say,
    get_voice_serializer,
    speak_serialized,
)


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
        # Worker thread should only exist once
        assert s1._worker is s2._worker

    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_say_processes_never_overlap(self, popen_mock, _which_mock):
        serializer = get_voice_serializer()
        serializer._audit_enabled = False  # skip pgrep in test
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
    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
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


class TestOverlapAudit:
    """Tests for audit_no_concurrent_say() runtime enforcement."""

    @patch("agentic_brain.voice.serializer.subprocess.run")
    def test_audit_passes_with_zero_say(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=["pgrep", "-x", "say"],
            returncode=1,
            stdout="",
        )
        # Should not raise
        audit_no_concurrent_say()

    @patch("agentic_brain.voice.serializer.subprocess.run")
    def test_audit_passes_with_one_say(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=["pgrep", "-x", "say"],
            returncode=0,
            stdout="12345\n",
        )
        # Single say process is fine
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
        # Should not raise on non-macOS
        audit_no_concurrent_say()

    @patch(
        "agentic_brain.voice.serializer.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="pgrep", timeout=2),
    )
    def test_audit_skips_on_timeout(self, _run_mock):
        audit_no_concurrent_say()


class TestDeprecationWarnings:
    """Tests for deprecation gate on legacy paths."""

    def test_warn_direct_say_emits_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _warn_direct_say(caller="test_caller")
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "test_caller" in str(w[0].message)
            assert "speak_serialized" in str(w[0].message)

    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_legacy_speak_emits_warning_and_works(self, popen_mock, _which):
        serializer = get_voice_serializer()
        serializer._audit_enabled = False
        serializer.set_pause_between(0)

        process = MagicMock()
        process.wait.return_value = 0
        process.poll.return_value = 0
        popen_mock.return_value = process

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _legacy_speak("hello from legacy")
            assert result is True
            deprecation_warnings = [
                x for x in w if issubclass(x.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()


class TestSpeakSafe:
    """Tests for the unified speak_safe entry point."""

    def test_speak_safe_routes_through_serializer(self):
        from agentic_brain.voice import speak_safe

        calls = []

        def fake_executor(message: VoiceMessage) -> bool:
            calls.append((message.text, message.voice, message.rate))
            return True

        serializer = get_voice_serializer()
        serializer.set_pause_between(0)
        original = serializer._speak_with_say
        serializer._speak_with_say = fake_executor  # type: ignore[assignment]
        try:
            result = speak_safe("test safe", voice="Moira", rate=150)
            assert result is True
            assert calls == [("test safe", "Moira", 150)]
        finally:
            serializer._speak_with_say = original  # type: ignore[assignment]
            serializer.set_pause_between(0.3)


class TestSpeechLockDeprecation:
    """Verify _speech_lock.global_speak emits deprecation."""

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


class TestVoiceModuleIntegration:
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

    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_say_processes_never_overlap(self, popen_mock, _which_mock):
        serializer = get_voice_serializer()
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
    @patch("agentic_brain.voice.serializer.shutil.which", return_value="/usr/bin/say")
    @patch("agentic_brain.voice.serializer.subprocess.Popen")
    def test_serializer_uses_configured_pause(
        self,
        popen_mock,
        _which_mock,
        sleep_mock,
    ):
        serializer = get_voice_serializer()
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


class TestVoiceModuleIntegration:
    def setup_method(self):
        VoiceQueue.get_instance().reset()

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

        monkeypatch.setattr("agentic_brain.voice.queue.get_voice_serializer", lambda: FakeSerializer())

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
        assert conv.speak("Conversation serializer path", voice="Karen", pause_after=0.6)
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
                calls.append((message.text, message.voice, message.rate, wait, executor))
                return True

        monkeypatch.setattr(
            "agentic_brain.voice.resilient.get_voice_serializer",
            lambda: FakeSerializer(),
        )

        ResilientVoice._config = None
        assert await ResilientVoice.speak("Resilient serializer path", voice="Karen", rate=155)
        assert len(calls) == 1
        text, voice, rate, wait, executor = calls[0]
        assert (text, voice, rate, wait) == ("Resilient serializer path", "Karen", 155, True)
        assert callable(executor)
