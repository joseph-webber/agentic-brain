from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, file_name: str):
    path = PROJECT_ROOT / file_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


voice_standalone = _load_module("voice_standalone", "voice_standalone.py")
voice_copilot_bridge = _load_module("voice_copilot_bridge", "voice_copilot_bridge.py")
voice_launcher = _load_module("voice_launcher", "voice_launcher.py")


class FakeVoiceIO:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def play_ready_tone(self) -> None:
        return None

    def record_audio(self):
        raise AssertionError("record_audio should not be called in text override tests")

    def transcribe(self, audio_path):
        raise AssertionError("transcribe should not be called in text override tests")

    def cleanup_recording(self, audio_path):
        return None


class FakeStateStore:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def write(self, suffix: str, value):
        self.values[suffix] = value

    def status(self, state: str, **details):
        self.values["status"] = {"status": state, **details}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(
            {
                "content": [
                    {
                        "type": "text",
                        "text": "Hello, the standalone voice agent is working.",
                    }
                ]
            }
        )


def test_standalone_process_turn_updates_state(monkeypatch):
    monkeypatch.setenv("CLAUDE_API_KEY", "test-key")
    settings = voice_standalone.VoiceSettings(say_enabled=True)
    io = FakeVoiceIO()
    state = FakeStateStore()
    session = FakeSession()
    agent = voice_standalone.StandaloneVoiceAgent(
        settings=settings,
        io=io,
        state_store=state,
        session=session,
    )

    response = agent.process_turn("Hello there")

    assert "standalone voice agent is working" in response.lower()
    assert io.spoken[-1] == response
    assert state.values["last_heard"]["text"] == "Hello there"
    assert state.values["last_response"]["text"] == response
    assert session.calls[0]["url"] == "https://api.anthropic.com/v1/messages"


def test_copilot_bridge_runs_copilot_and_speaks(monkeypatch):
    settings = voice_standalone.VoiceSettings(namespace="voice:bridge", say_enabled=True)
    io = FakeVoiceIO()
    state = FakeStateStore()
    bridge = voice_copilot_bridge.CopilotVoiceBridge(
        settings=settings,
        io=io,
        state_store=state,
        repo_path=PROJECT_ROOT,
    )

    def fake_run(command, cwd=None, check=False, capture_output=False, text=False):
        assert command[:3] == ["gh", "copilot", "-p"]
        assert cwd == PROJECT_ROOT

        class Result:
            returncode = 0
            stdout = "Copilot says hello."
            stderr = ""

        return Result()

    monkeypatch.setattr(voice_copilot_bridge.subprocess, "run", fake_run)

    response = bridge.process_turn("Explain this repository")

    assert response == "Copilot says hello."
    assert io.spoken[-1] == "Copilot says hello."
    assert state.values["last_heard"]["text"] == "Explain this repository"
    assert state.values["last_response"]["text"] == "Copilot says hello."


def test_launcher_records_integrator_state(monkeypatch):
    launches = []

    class FakeIntegratorStore:
        def __init__(self, namespace):
            self.namespace = namespace

        def write(self, suffix, value):
            launches.append((suffix, value))

        def status(self, state, **details):
            launches.append(("status", {"status": state, **details}))

    class FakeStandaloneAgent:
        def __init__(self, settings):
            self.settings = settings

        def run(self, *, once=False, text_override=None):
            assert once is True
            assert text_override == "hello"
            return 0

    monkeypatch.setattr(voice_launcher, "RedisStateStore", FakeIntegratorStore)
    monkeypatch.setattr(voice_launcher, "StandaloneVoiceAgent", FakeStandaloneAgent)
    monkeypatch.setattr(voice_launcher, "VoiceIO", lambda settings: FakeVoiceIO())

    exit_code = voice_launcher.main(["--mode", "standalone", "--once", "--text", "hello", "--no-speak"])

    assert exit_code == 0
    assert launches[0][0] == "last_launch"
    assert launches[-1][0] == "last_result"
