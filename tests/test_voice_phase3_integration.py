# SPDX-License-Identifier: Apache-2.0
#
# Phase 3 voice integration tests.

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.phase3 import (  # noqa: E402
    Phase3VoiceSystem,
    _set_phase3_voice_system_for_testing,
    get_phase3_voice_system,
)


@pytest.fixture()
def phase3() -> Phase3VoiceSystem:
    return Phase3VoiceSystem()


@pytest.fixture()
def repo_scratch(request) -> Path:
    root = Path(__file__).resolve().parent / ".phase3-artifacts" / request.node.name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        if root.exists():
            shutil.rmtree(root)


def _fake_speed_manager(profile: str = "working", rate: int = 200):
    return SimpleNamespace(
        current_profile=SimpleNamespace(value=profile),
        current_rate=rate,
        set_profile=MagicMock(),
    )


class TestPhase3VoiceSystemBasics:
    def test_import_and_construct(self):
        assert Phase3VoiceSystem is not None
        system = Phase3VoiceSystem()
        assert isinstance(system, Phase3VoiceSystem)

    def test_singleton_accessor(self):
        _set_phase3_voice_system_for_testing(None)
        one = get_phase3_voice_system()
        two = get_phase3_voice_system()
        assert one is two
        _set_phase3_voice_system_for_testing(None)

    def test_status_returns_summary(self, phase3):
        status = phase3.status()
        assert "summary" in status
        assert "Phase 3 Voice" in status["summary"]

    def test_health_returns_subsystems(self, phase3):
        health = phase3.health()
        assert "subsystems" in health
        assert "speech_path" in health["subsystems"]
        assert "speed_profiles" in health["subsystems"]

    def test_empty_text_is_rejected(self, phase3):
        assert phase3.speak("   ") is False

    def test_list_ladies_falls_back_to_kokoro_map(self, phase3):
        ladies = phase3.list_ladies()
        assert "Karen" in ladies
        assert "Kyoko" in ladies


class TestSpeakRouting:
    def test_speak_uses_neural_router_when_available(self, phase3):
        router = MagicMock()
        router.speak.return_value = True
        phase3._components["neural_router"] = router
        phase3._components["speed_manager"] = _fake_speed_manager()

        assert phase3.speak("Hello Joseph", lady="Moira") is True
        router.speak.assert_called_once()

    @patch("agentic_brain.voice.serializer.get_voice_serializer")
    def test_speak_falls_back_to_serializer(self, mock_get_serializer, phase3):
        phase3._components["neural_router"] = None
        phase3._components["speed_manager"] = _fake_speed_manager(rate=155)
        serializer = MagicMock()
        serializer.speak.return_value = True
        mock_get_serializer.return_value = serializer

        assert phase3.speak("Fallback route", lady="Karen") is True
        serializer.speak.assert_called_once()

    @patch("agentic_brain.voice.serializer.get_voice_serializer")
    def test_speak_returns_false_when_all_paths_fail(self, mock_get_serializer, phase3):
        phase3._components["neural_router"] = MagicMock(speak=MagicMock(side_effect=RuntimeError("boom")))
        phase3._components["speed_manager"] = _fake_speed_manager()
        serializer = MagicMock()
        serializer.speak.side_effect = RuntimeError("boom")
        mock_get_serializer.return_value = serializer

        assert phase3.speak("No route left") is False

    @patch("agentic_brain.voice.serializer.get_voice_serializer")
    def test_speak_system_sets_system_category(self, mock_get_serializer, phase3):
        phase3._components["neural_router"] = None
        serializer = MagicMock()
        serializer.speak.return_value = True
        mock_get_serializer.return_value = serializer

        assert phase3.speak_system("Deployment complete") is True
        serializer.speak.assert_called_once()

    def test_repeat_detection_blocks_speech(self, phase3):
        detector = MagicMock()
        detector.is_repeat.return_value = True
        phase3._components["repeat_detector"] = detector
        phase3._components["speed_manager"] = _fake_speed_manager()
        phase3._components["neural_router"] = MagicMock()

        assert phase3.speak("Same line twice") is False
        phase3._components["neural_router"].speak.assert_not_called()

    def test_remember_turn_runs_after_success(self, phase3):
        memory = MagicMock()
        memory.record.return_value = object()
        phase3._components["conversation_memory"] = memory
        phase3._components["speed_manager"] = _fake_speed_manager()
        router = MagicMock()
        router.speak.return_value = True
        phase3._components["neural_router"] = router

        assert phase3.speak("Remember this") is True
        memory.record.assert_called_once()

    def test_speak_can_disable_memory(self, phase3):
        memory = MagicMock()
        phase3._components["conversation_memory"] = memory
        phase3._components["speed_manager"] = _fake_speed_manager()
        router = MagicMock()
        router.speak.return_value = True
        phase3._components["neural_router"] = router

        assert phase3.speak("Do not store", remember=False) is True
        memory.remember.assert_not_called()


class TestOptionalSubsystems:
    def test_classify_content_uses_optional_classifier(self, phase3):
        classifier = MagicMock()
        classifier.classify.return_value = "progress"
        phase3._components["content_classifier"] = classifier
        assert phase3.classify_content("working...") == "progress"

    def test_classify_content_heuristics_error(self, phase3):
        phase3._components["content_classifier"] = None
        assert phase3.classify_content("This failed badly") == "error"

    def test_classify_content_heuristics_notification(self, phase3):
        phase3._components["content_classifier"] = None
        assert phase3.classify_content("All good") == "notification"

    def test_resolve_emotion_uses_optional_module(self, phase3):
        emotions = MagicMock()
        emotions.detect.return_value = "joyful"
        phase3._components["emotions"] = emotions
        assert phase3.resolve_emotion("Lovely news") == "joyful"

    def test_resolve_emotion_heuristics(self, phase3):
        phase3._components["emotions"] = None
        assert phase3.resolve_emotion("Sorry about that") == "empathetic"
        assert phase3.resolve_emotion("Great work!") == "excited"

    def test_apply_expression_uses_optional_module(self, phase3):
        expression = MagicMock()
        expression.apply.return_value = "<expressed>Hello</expressed>"
        phase3._components["expression"] = expression
        assert phase3.apply_expression("Hello", lady="Karen") == "<expressed>Hello</expressed>"

    def test_get_recent_turns_empty_when_memory_missing(self, phase3):
        phase3._components["conversation_memory"] = None
        assert phase3.get_recent_turns() == []

    def test_get_recent_turns_uses_memory_module(self, phase3):
        memory = MagicMock()
        memory.get_recent.return_value = ["a", "b"]
        phase3._components["conversation_memory"] = memory
        assert phase3.get_recent_turns(limit=2) == ["a", "b"]

    def test_analyze_quality_degrades_gracefully(self, phase3):
        phase3._components["quality_analyzer"] = None
        phase3._components["quality_gate"] = None
        result = phase3.analyze_quality()
        assert result["available"] is False
        assert result["analysis"] is None
        assert result["gate"] is None

    def test_analyze_quality_uses_both_components(self, phase3):
        analyzer = MagicMock()
        analyzer.analyze_audio.return_value = {"score": 0.9}
        gate = MagicMock()
        gate.check.return_value = {"pass": True}
        phase3._components["quality_analyzer"] = analyzer
        phase3._components["quality_gate"] = gate

        result = phase3.analyze_quality("demo.wav")
        assert result["available"] is True
        assert result["analysis"] == {"score": 0.9}
        assert result["gate"] == {"pass": True}

    def test_clone_voice_degrades_gracefully(self, phase3):
        phase3._components["voice_cloning"] = None
        phase3._components["voice_library"] = None
        result = phase3.clone_voice("sample.wav", name="Karen-ish")
        assert result["available"] is False
        assert result["clone"] is None

    def test_clone_voice_updates_library(self, phase3):
        cloning = MagicMock()
        cloning.clone_voice.return_value = {"voice_id": "clone-1"}
        library = MagicMock()
        library.register.return_value = {"stored": True}
        phase3._components["voice_cloning"] = cloning
        phase3._components["voice_library"] = library

        result = phase3.clone_voice("sample.wav", name="Karen-ish")
        assert result["clone"] == {"voice_id": "clone-1"}
        assert result["library"] == {"stored": True}


class TestRuntimeControls:
    def test_play_earcon_uses_player(self, phase3):
        player = MagicMock()
        player.play.return_value = True
        phase3._components["earcon_player"] = player

        assert phase3.play_earcon("task_done", blocking=True) is True
        player.play.assert_called_once_with("task_done", blocking=True)

    def test_play_earcon_returns_false_without_player(self, phase3):
        phase3._components["earcon_player"] = None
        assert phase3.play_earcon("task_done") is False

    def test_get_current_rate_defaults_without_manager(self, phase3):
        phase3._components["speed_manager"] = None
        assert phase3.get_current_rate() == 155

    def test_get_speed_profile_reads_manager(self, phase3):
        phase3._components["speed_manager"] = _fake_speed_manager(profile="focused", rate=280)
        assert phase3.get_speed_profile() == "focused"

    def test_set_speed_profile_uses_enum(self, phase3):
        manager = _fake_speed_manager(profile="working", rate=200)
        phase3._components["speed_manager"] = manager
        assert phase3.set_speed_profile("power") == "power"
        manager.set_profile.assert_called_once()

    @pytest.mark.asyncio
    async def test_live_daemon_start_stop_and_status(self, phase3):
        daemon = MagicMock()
        daemon.get_stats.return_value = {
            "running": True,
            "ready": True,
            "queue_size": 0,
            "processed": 0,
            "errors": 0,
            "error_rate": "0.0%",
        }
        daemon.stop = AsyncMock()

        with (
            patch("agentic_brain.voice.phase3.get_daemon", AsyncMock(return_value=daemon)),
            patch("agentic_brain.voice.resilient._daemon_instance", daemon),
        ):
            started = await phase3.start_live_daemon()
            status = phase3.live_daemon_status()
            stopped = await phase3.stop_live_daemon()

        assert started is daemon
        assert status["available"] is True
        assert status["daemon_running"] is True
        assert stopped["ok"] is True
        daemon.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_live_daemon_stop_is_noop_when_not_started(self, phase3):
        with patch("agentic_brain.voice.resilient._daemon_instance", None):
            stopped = await phase3.stop_live_daemon()
            status = phase3.live_daemon_status()

        assert stopped["ok"] is True
        assert status["available"] is True
        assert status["daemon_running"] is False


class TestHealthAndCompatibility:
    def test_health_marks_core_healthy_with_fallbacks(self, phase3):
        phase3._components["speed_manager"] = _fake_speed_manager()
        phase3._components["neural_router"] = None
        health = phase3.health()
        assert health["healthy"] is True
        assert health["subsystems"]["speech_path"]["degraded"] is True

    def test_health_marks_optional_modules_missing(self, phase3):
        phase3._components["voice_cloning"] = None
        phase3._components["conversation_memory"] = None
        health = phase3.health()
        assert health["subsystems"]["voice_cloning"]["available"] is False
        assert health["subsystems"]["conversation_memory"]["available"] is False

    def test_health_includes_loaded_optional_modules(self, phase3):
        phase3._components["speed_manager"] = _fake_speed_manager()
        phase3._components["voice_cloning"] = SimpleNamespace()
        phase3._components["conversation_memory"] = SimpleNamespace()
        health = phase3.health()
        assert health["subsystems"]["voice_cloning"]["available"] is True
        assert health["subsystems"]["conversation_memory"]["available"] is True

    def test_voice_package_lazy_exports_phase3(self):
        from agentic_brain.voice import Phase3VoiceSystem as ExportedPhase3
        from agentic_brain.voice import get_phase3_voice_system as exported_getter

        assert ExportedPhase3 is Phase3VoiceSystem
        assert callable(exported_getter)

    def test_voice_package_lazy_exports_kokoro_alias(self):
        from agentic_brain.voice import KokoroTTS, KokoroVoice

        assert KokoroTTS is KokoroVoice

    def test_voice_package_lazy_exports_neural_router(self):
        from agentic_brain.voice import NeuralVoiceRouter

        assert NeuralVoiceRouter.__name__ == "NeuralVoiceRouter"

    def test_lazy_phase3_loader(self):
        from agentic_brain.voice import _lazy_phase3

        cls, getter = _lazy_phase3()
        assert cls is Phase3VoiceSystem
        assert callable(getter)

    def test_lazy_earcons_loader_uses_audio_module(self):
        from agentic_brain.voice import _lazy_earcons

        cls, getter = _lazy_earcons()
        assert cls.__name__ == "EarconPlayer"
        assert callable(getter)


class TestCliCompatibility:
    def test_voice_health_command_uses_unified_system(self, capsys):
        from agentic_brain.cli.voice_commands import voice_health_command

        fake_unified = SimpleNamespace(
            status=lambda: {"summary": "Voice System: HEALTHY", "health": {}}
        )
        with patch("agentic_brain.voice.unified.get_unified", return_value=fake_unified):
            assert voice_health_command(SimpleNamespace()) == 0

        out = capsys.readouterr().out
        assert "Voice System: HEALTHY" in out

    def test_live_daemon_cli_start(self, capsys):
        from agentic_brain.cli.voice_commands import _live_daemon_command

        fake_daemon = SimpleNamespace(
            DaemonConfig=lambda **kwargs: SimpleNamespace(**kwargs),
            start_daemon=lambda cfg: {"ok": True, "pid": 42},
            stop_daemon=lambda: {"ok": True},
            daemon_status=lambda: {"daemon_running": True, "pid": 42},
        )
        with patch.dict(sys.modules, {"agentic_brain.voice.live_daemon": fake_daemon}):
            rc = _live_daemon_command(
                action="start",
                voice="Karen",
                rate=160,
                wake_words=("hey karen",),
                session_timeout=30.0,
                use_whisper=True,
            )

        assert rc == 0
        assert "started" in capsys.readouterr().out.lower()

    def test_voice_command_help_still_prints(self, capsys):
        from agentic_brain.cli.voice_commands import voice_command

        assert voice_command(SimpleNamespace()) == 0
        out = capsys.readouterr().out
        assert "Agentic Brain Voice System" in out
        assert "Phase 2 Commands" in out
