from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_module(module_name: str, relative_path: str):
    path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


voice_event_bus = load_module("voice_event_bus_tool", "tools/voice_event_bus.py")


class FakeFuture:
    def get(self, timeout: int = 5) -> dict[str, str]:
        return {"status": "ok"}


class FakeProducer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []
        self.flushed = False

    def send(self, topic: str, value: dict):
        self.messages.append((topic, value))
        return FakeFuture()

    def flush(self) -> None:
        self.flushed = True


class FakeAdminClient:
    def __init__(self, *args, **kwargs) -> None:
        self.created: list[object] = []
        self.closed = False

    def create_topics(self, new_topics, validate_only: bool = False) -> None:
        self.created.extend(new_topics)

    def close(self) -> None:
        self.closed = True


class FakeNewTopic:
    def __init__(self, name: str, num_partitions: int, replication_factor: int) -> None:
        self.name = name
        self.num_partitions = num_partitions
        self.replication_factor = replication_factor


class FakeConsumer:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.closed = False

    def poll(self, timeout_ms: int = 1000, max_records: int = 10):
        if not self.payloads:
            return {}
        payload = self.payloads.pop(0)
        return {"topic": [SimpleNamespace(value=payload)]}

    def close(self) -> None:
        self.closed = True


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self.values[key] = value

    def get(self, key: str) -> str | None:
        return self.values.get(key)


def test_publish_voice_event_flushes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProducer()
    monkeypatch.setattr(voice_event_bus, "producer", fake)

    voice_event_bus.publish_voice_event(voice_event_bus.VOICE_INPUT_TOPIC, {"text": "hello"})

    assert fake.messages == [(voice_event_bus.VOICE_INPUT_TOPIC, {"text": "hello"})]
    assert fake.flushed is True


def test_ensure_voice_topics_creates_all_topics(monkeypatch: pytest.MonkeyPatch) -> None:
    created_admin = FakeAdminClient()
    monkeypatch.setattr(voice_event_bus, "KafkaAdminClient", lambda *args, **kwargs: created_admin)
    monkeypatch.setattr(voice_event_bus, "NewTopic", FakeNewTopic)

    topics = voice_event_bus.ensure_voice_topics()

    assert topics == voice_event_bus.VOICE_TOPICS
    assert [topic.name for topic in created_admin.created] == list(voice_event_bus.VOICE_TOPICS)
    assert created_admin.closed is True


def test_wait_for_voice_event_matches_predicate(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_consumer = FakeConsumer(
        [
            {"request_id": "ignore", "text": "old"},
            {"request_id": "req-1", "text": "ready"},
        ]
    )
    monkeypatch.setattr(
        voice_event_bus,
        "create_voice_consumer",
        lambda *args, **kwargs: fake_consumer,
    )

    payload = voice_event_bus.wait_for_voice_event(
        voice_event_bus.VOICE_RESPONSE_TOPIC,
        predicate=lambda event: event.get("request_id") == "req-1",
        timeout=0.1,
    )

    assert payload == {"request_id": "req-1", "text": "ready"}
    assert fake_consumer.closed is True


def test_publish_progress_updates_redis_and_coordination_topic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_producer = FakeProducer()
    fake_redis = FakeRedis()
    monkeypatch.setattr(voice_event_bus, "producer", fake_producer)
    monkeypatch.setattr(voice_event_bus, "_get_redis_client", lambda: fake_redis)

    payload = voice_event_bus.publish_progress("working", {"session_id": "abc"})

    assert payload["status"] == "working"
    assert fake_producer.messages[0][0] == voice_event_bus.VOICE_COORDINATION_TOPIC
    stored = json.loads(fake_redis.values[voice_event_bus.PROGRESS_KEY])
    assert stored["status"] == "working"
    assert stored["session_id"] == "abc"
