from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).resolve().parents[1] / "talk_to_karen_sox.py"
spec = importlib.util.spec_from_file_location("talk_to_karen_sox", MODULE_PATH)
talk_to_karen_sox = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = talk_to_karen_sox
assert spec.loader is not None
spec.loader.exec_module(talk_to_karen_sox)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.published: list[tuple[str, str]] = []
        self.history: list[tuple[str, str]] = []

    def set(self, key: str, value: str) -> None:
        self.values[key] = value

    def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))

    def lpush(self, key: str, payload: str) -> None:
        self.history.append((key, payload))

    def ltrim(self, key: str, start: int, end: int) -> None:
        self.values[f"trim:{key}"] = f"{start}:{end}"


def test_resolve_backend_prefers_sox(monkeypatch) -> None:
    monkeypatch.setattr(
        talk_to_karen_sox.shutil,
        "which",
        lambda name: "/opt/homebrew/bin/sox" if name == "sox" else None,
    )

    assert talk_to_karen_sox.resolve_backend("auto") == "sox"


def test_record_audio_uses_sox(monkeypatch) -> None:
    output_path = MODULE_PATH.parent / ".cache" / "test-recordings" / "clip.wav"
    monkeypatch.setattr(talk_to_karen_sox, "resolve_backend", lambda backend: "sox")
    monkeypatch.setattr(talk_to_karen_sox, "build_audio_path", lambda: output_path)

    seen: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool) -> None:
        seen.append(cmd)
        assert check is True

    monkeypatch.setattr(talk_to_karen_sox.subprocess, "run", fake_run)

    path, backend = talk_to_karen_sox.record_audio(duration=3, sample_rate=22050, backend="auto")

    assert path == output_path
    assert backend == "sox"
    assert seen == [[
        "sox",
        "-q",
        "-d",
        "-r",
        "22050",
        "-c",
        "1",
        "-b",
        "16",
        str(output_path),
        "trim",
        "0",
        "3",
    ]]


def test_transcribe_audio_joins_segments(monkeypatch) -> None:
    sample_path = MODULE_PATH.parent / ".cache" / "test-recordings" / "sample.wav"
    fake_segment_1 = SimpleNamespace(text="Hello")
    fake_segment_2 = SimpleNamespace(text=" there ")

    class FakeModel:
        def __init__(self, model_name: str, device: str, compute_type: str) -> None:
            assert model_name == "tiny.en"
            assert device == "cpu"
            assert compute_type == "int8"

        def transcribe(self, audio_path: str):
            assert audio_path == str(sample_path)
            return [fake_segment_1, fake_segment_2], {}

    sys.modules["faster_whisper"] = SimpleNamespace(WhisperModel=FakeModel)

    result = talk_to_karen_sox.transcribe_audio(sample_path)

    assert result == "Hello there"


def test_get_llm_response_uses_ollama(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"response": "G'day mate"}

    captured: dict[str, object] = {}

    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(talk_to_karen_sox.requests, "post", fake_post)

    result = talk_to_karen_sox.get_llm_response("How are you?")

    assert result == "G'day mate"
    assert captured["url"] == talk_to_karen_sox.OLLAMA_URL
    assert captured["json"]["model"] == talk_to_karen_sox.DEFAULT_MODEL
    assert "How are you?" in captured["json"]["prompt"]
    assert captured["timeout"] == 90


def test_report_status_updates_redis() -> None:
    client = FakeRedis()

    talk_to_karen_sox.report_status(client, "done", backend="sox")

    payload = json.loads(client.values["voice:sox:last_status"])
    assert payload["event"] == "done"
    assert payload["backend"] == "sox"
    assert client.published[0][0] == "voice:sox:status"
    assert client.history[0][0] == "voice:sox:history"
