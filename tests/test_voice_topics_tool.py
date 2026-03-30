from __future__ import annotations

import importlib.util
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


voice_topics = load_module("voice_topics_tool", "tools/voice_topics.py")


class FakeFuture:
    def get(self, timeout: int = 5) -> dict[str, str]:
        return {"status": "ok"}


class FakeProducer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict, bytes | None]] = []
        self.flushed = False

    def send(self, topic: str, value: dict, key: bytes | None = None):
        self.messages.append((topic, value, key))
        return FakeFuture()

    def flush(self) -> None:
        self.flushed = True


class FakeAdminClient:
    def __init__(self, topics: list[str] | None = None) -> None:
        self.created: list[object] = []
        self.closed = False
        self.topics = topics or []

    def create_topics(self, new_topics, validate_only: bool = False) -> None:
        self.created.extend(new_topics)
        self.topics = sorted({*self.topics, *(topic.name for topic in new_topics)})

    def list_topics(self):
        return self.topics

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

    def __iter__(self):
        for payload in self.payloads:
            yield SimpleNamespace(value=payload)

    def close(self) -> None:
        self.closed = True


def reset_module_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice_topics, "_topics_ensured", False)
    monkeypatch.setattr(voice_topics, "_producer", None)


def test_ensure_voice_topics_creates_brain_chat_topics(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_module_state(monkeypatch)
    admin = FakeAdminClient()
    monkeypatch.setattr(voice_topics, "KafkaAdminClient", lambda *args, **kwargs: admin)
    monkeypatch.setattr(voice_topics, "NewTopic", FakeNewTopic)

    topics = voice_topics.ensure_voice_topics()

    assert topics == voice_topics.VOICE_TOPICS
    assert [topic.name for topic in admin.created] == list(voice_topics.VOICE_TOPICS)
    assert admin.closed is True


def test_publish_voice_input_publishes_normalized_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_module_state(monkeypatch)
    admin = FakeAdminClient()
    producer = FakeProducer()
    monkeypatch.setattr(voice_topics, "KafkaAdminClient", lambda *args, **kwargs: admin)
    monkeypatch.setattr(voice_topics, "NewTopic", FakeNewTopic)
    monkeypatch.setattr(voice_topics, "_get_producer", lambda: producer)

    payload = voice_topics.publish_voice_input("Hello Iris", "session-123")

    assert payload["session_id"] == "session-123"
    assert payload["text"] == "Hello Iris"
    assert payload["confidence"] == 1.0
    assert payload["source"] == "brainchat"
    assert payload["timestamp"].endswith("Z")
    assert producer.messages == [
        (voice_topics.VOICE_INPUT_TOPIC, payload, b"session-123")
    ]
    assert producer.flushed is True


def test_subscribe_voice_responses_normalizes_legacy_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_module_state(monkeypatch)
    admin = FakeAdminClient()
    consumer = FakeConsumer(
        [
            {
                "text": "Righto, all done.",
                "session_id": "swift-session",
                "provider": "copilot",
                "ts": 1710000000.0,
            }
        ]
    )
    monkeypatch.setattr(voice_topics, "KafkaAdminClient", lambda *args, **kwargs: admin)
    monkeypatch.setattr(voice_topics, "NewTopic", FakeNewTopic)
    monkeypatch.setattr(voice_topics, "_create_consumer", lambda *args, **kwargs: consumer)

    seen: list[dict] = []
    processed = voice_topics.subscribe_voice_responses(seen.append)

    assert processed == 1
    assert consumer.closed is True
    assert seen == [
        {
            "text": "Righto, all done.",
            "session_id": "swift-session",
            "provider": "copilot",
            "ts": 1710000000.0,
            "timestamp": "2024-03-09T16:00:00Z",
            "voice": "Karen",
            "priority": "normal",
            "source": "copilot",
        }
    ]


def test_get_voice_status_reports_healthy_topics(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_module_state(monkeypatch)
    admin_for_ensure = FakeAdminClient()
    admin_for_status = FakeAdminClient(list(voice_topics.VOICE_TOPICS))
    producer = FakeProducer()
    admin_calls = iter([admin_for_ensure, admin_for_status])

    monkeypatch.setattr(
        voice_topics,
        "KafkaAdminClient",
        lambda *args, **kwargs: next(admin_calls),
    )
    monkeypatch.setattr(voice_topics, "NewTopic", FakeNewTopic)
    monkeypatch.setattr(voice_topics, "_get_producer", lambda: producer)

    status = voice_topics.get_voice_status()

    assert status["status"] == "healthy"
    assert status["source"] == "brainchat"
    assert status["details"]["missing_topics"] == []
    assert status["details"]["bootstrap_servers"] == voice_topics.REDPANDA_BOOTSTRAP_SERVERS
    assert producer.messages[0][0] == voice_topics.VOICE_STATUS_TOPIC
