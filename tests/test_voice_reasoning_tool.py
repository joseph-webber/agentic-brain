from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def load_module(module_name: str, relative_path: str):
    path = Path(__file__).resolve().parents[1] / relative_path
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


voice_reasoning = load_module("voice_reasoning_tool", "tools/voice_reasoning.py")


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.history: list[str] = []

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def lpush(self, key: str, value: str) -> None:
        self.history.insert(0, value)

    def ltrim(self, key: str, start: int, stop: int) -> None:
        self.history = self.history[start : stop + 1]

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        end = None if stop == -1 else stop + 1
        return self.history[start:end]

    def llen(self, key: str) -> int:
        return len(self.history)

    def publish(self, key: str, value: str) -> None:
        self.values[f"pub:{key}"] = value


def test_process_voice_input_event_publishes_reasoning_and_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = FakeRedis()
    published: list[tuple[str, dict]] = []
    progress: list[tuple[str, dict]] = []
    state_updates: dict[str, str] = {}

    monkeypatch.setattr(
        voice_reasoning,
        "publish_voice_event",
        lambda topic, payload: published.append((topic, payload)),
    )
    monkeypatch.setattr(
        voice_reasoning,
        "publish_progress",
        lambda status, extra=None: progress.append((status, extra or {})),
    )
    monkeypatch.setattr(
        voice_reasoning,
        "set_voice_state",
        lambda key, value: state_updates.__setitem__(key, value),
    )
    monkeypatch.setattr(
        voice_reasoning,
        "generate_reply",
        lambda text, recommendation: "Hello there, the bus is working.",
    )

    response = voice_reasoning.process_voice_input_event(
        {
            "request_id": "req-1",
            "session_id": "session-1",
            "text": "Can you hear me?",
        },
        fake_redis,
    )

    assert response["request_id"] == "req-1"
    assert response["text"] == "Hello there, the bus is working."
    assert [topic for topic, _ in published] == [
        voice_reasoning.VOICE_REASONING_TOPIC,
        voice_reasoning.VOICE_RESPONSE_TOPIC,
    ]
    assert state_updates[voice_reasoning.INPUT_KEY] == "Can you hear me?"
    assert json.loads(fake_redis.values[voice_reasoning.RESPONSE_KEY])["text"] == (
        "Hello there, the bus is working."
    )
    assert [status for status, _ in progress] == [
        "voice-reasoning-started",
        "voice-response-published",
    ]
