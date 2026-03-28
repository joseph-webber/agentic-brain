from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from agentic_brain.voice.events import (
    VoicePriorityLane,
    VoiceSpeechCompleted,
    VoiceSpeechFailed,
    VoiceSpeechRequested,
    VoiceSpeechStarted,
    deserialize_event,
    serialize_event,
)
from agentic_brain.voice.stream import (
    BRAIN_VOICE_ERRORS,
    BRAIN_VOICE_REQUESTS,
    BRAIN_VOICE_STATUS,
    VOICE_TOPICS,
    VoiceEventConsumer,
    VoiceEventProducer,
    get_voice_event_producer,
    speak_async,
)


class FakeFuture:
    def get(self, timeout: int = 5) -> dict[str, str]:
        return {"status": "ok"}


class FakeProducer:
    def __init__(self, *args, **kwargs) -> None:
        self.messages: list[tuple[str, object]] = []
        self.closed = False

    def send(self, topic: str, value: object):
        self.messages.append((topic, value))
        return FakeFuture()

    def close(self) -> None:
        self.closed = True


class FailingProducer(FakeProducer):
    def send(self, topic: str, value: object):
        raise RuntimeError("broker unavailable")


class FakeAdminClient:
    def __init__(self, *args, **kwargs) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    def create_topics(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))


class FakeConsumer:
    def __init__(self, events: list[object]) -> None:
        self._events = [SimpleNamespace(value=event) for event in events]
        self.closed = False

    def poll(self, timeout_ms: int = 1000, max_records: int = 100) -> dict[str, list]:
        batch = self._events[:max_records]
        self._events = self._events[max_records:]
        return {BRAIN_VOICE_REQUESTS: batch}

    def close(self) -> None:
        self.closed = True


class RecordingProducer:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def publish(self, event) -> bool:
        if isinstance(event, VoiceSpeechRequested):
            topic = BRAIN_VOICE_REQUESTS
        elif isinstance(event, VoiceSpeechFailed):
            topic = BRAIN_VOICE_ERRORS
        else:
            topic = BRAIN_VOICE_STATUS
        self.events.append((topic, event))
        return True

    def publish_speech_request(self, *args, **kwargs) -> bool:
        event = VoiceSpeechRequested(
            text=args[0],
            lady=kwargs.get("lady", "Karen"),
            priority=kwargs.get("priority", VoicePriorityLane.NORMAL),
            source=kwargs.get("source", "test"),
        )
        self.events.append((BRAIN_VOICE_REQUESTS, event))
        return True


def test_voice_speech_requested_defaults() -> None:
    event = VoiceSpeechRequested(text="Hello Joseph")

    assert event.lady == "Karen"
    assert event.priority == VoicePriorityLane.NORMAL
    assert event.source == "agentic_brain.voice"


def test_voice_speech_requested_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        VoiceSpeechRequested(text="   ")


def test_voice_speech_failed_requires_error_text() -> None:
    event = VoiceSpeechFailed(text="Oops", error="   ")

    assert event.error == "speech failed"


def test_serialize_and_deserialize_requested_event() -> None:
    event = VoiceSpeechRequested(
        text="Queue me",
        lady="Moira",
        priority=VoicePriorityLane.URGENT,
        source="test",
    )

    restored = deserialize_event(serialize_event(event))

    assert isinstance(restored, VoiceSpeechRequested)
    assert restored.lady == "Moira"
    assert restored.priority == VoicePriorityLane.URGENT


def test_deserialize_bytes_payload() -> None:
    payload = json.dumps(
        VoiceSpeechCompleted(text="Done", request_id="req-1").to_dict()
    ).encode("utf-8")

    restored = deserialize_event(payload)

    assert isinstance(restored, VoiceSpeechCompleted)
    assert restored.request_id == "req-1"


def test_started_event_from_request_preserves_request_id() -> None:
    request = VoiceSpeechRequested(text="Start me", request_id="req-2")

    started = VoiceSpeechStarted.from_request(request)

    assert started.request_id == "req-2"
    assert started.text == "Start me"


def test_failed_event_from_request_preserves_priority() -> None:
    request = VoiceSpeechRequested(
        text="Fail me",
        priority=VoicePriorityLane.BACKGROUND,
    )

    failed = VoiceSpeechFailed.from_request(request, error="speaker down")

    assert failed.priority == VoicePriorityLane.BACKGROUND
    assert failed.error == "speaker down"


def test_voice_event_producer_publishes_request_topic() -> None:
    fake = FakeProducer()
    producer = VoiceEventProducer(producer=fake, admin_client=FakeAdminClient())

    result = producer.publish_speech_request("Speak now", lady="Karen")

    assert result is True
    topic, event = fake.messages[0]
    assert topic == BRAIN_VOICE_REQUESTS
    assert isinstance(event, VoiceSpeechRequested)


def test_voice_event_producer_routes_completed_to_status_topic() -> None:
    fake = FakeProducer()
    producer = VoiceEventProducer(producer=fake, create_topics=False)

    producer.publish(VoiceSpeechCompleted(text="Done"))

    assert fake.messages[0][0] == BRAIN_VOICE_STATUS


def test_voice_event_producer_routes_failed_to_dead_letter_topic() -> None:
    fake = FakeProducer()
    producer = VoiceEventProducer(producer=fake, create_topics=False)

    producer.publish(VoiceSpeechFailed(text="Nope", error="boom"))

    assert [topic for topic, _ in fake.messages] == [BRAIN_VOICE_STATUS, BRAIN_VOICE_ERRORS]


def test_voice_event_producer_creates_topics() -> None:
    admin = FakeAdminClient()
    producer = VoiceEventProducer(producer=FakeProducer(), admin_client=admin)

    assert producer.ensure_topics() is True
    assert len(admin.calls) == 1


def test_voice_event_producer_gracefully_handles_missing_kafka(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import agentic_brain.voice.stream as stream_module

    monkeypatch.setattr(stream_module, "KafkaProducer", None)
    producer = VoiceEventProducer(
        producer_factory=None,
        admin_factory=None,
        enabled=True,
    )

    assert producer.publish_speech_request("Fallback please") is False


def test_consumer_poll_orders_priority_then_timestamp() -> None:
    background = VoiceSpeechRequested(
        text="background",
        priority=VoicePriorityLane.BACKGROUND,
        timestamp=30,
    )
    urgent = VoiceSpeechRequested(
        text="urgent",
        priority=VoicePriorityLane.URGENT,
        timestamp=20,
    )
    normal = VoiceSpeechRequested(
        text="normal",
        priority=VoicePriorityLane.NORMAL,
        timestamp=10,
    )
    consumer = VoiceEventConsumer(
        consumer=FakeConsumer(
            [background.to_dict(), normal.to_json(), serialize_event(urgent).encode("utf-8")]
        ),
        event_producer=RecordingProducer(),
    )

    polled = consumer.poll()

    assert [event.text for event in polled] == ["urgent", "normal", "background"]


@pytest.mark.asyncio
async def test_consumer_process_batch_speaks_and_publishes_statuses() -> None:
    recorder = RecordingProducer()
    spoken: list[tuple[str, str]] = []

    async def speaker(text: str, lady: str) -> bool:
        spoken.append((text, lady))
        return True

    consumer = VoiceEventConsumer(
        consumer=FakeConsumer([VoiceSpeechRequested(text="Hello", lady="Karen").to_dict()]),
        event_producer=recorder,
        speaker=speaker,
    )

    processed = await consumer.process_batch()

    assert [event.text for event in processed] == ["Hello"]
    assert spoken == [("Hello", "Karen")]
    assert [type(event).__name__ for _, event in recorder.events] == [
        "VoiceSpeechStarted",
        "VoiceSpeechCompleted",
    ]


@pytest.mark.asyncio
async def test_consumer_dead_letters_failed_speech() -> None:
    recorder = RecordingProducer()

    async def speaker(text: str, lady: str) -> bool:
        return False

    consumer = VoiceEventConsumer(
        consumer=FakeConsumer([VoiceSpeechRequested(text="Hello").to_dict()]),
        event_producer=recorder,
        speaker=speaker,
    )

    await consumer.process_batch()

    assert [topic for topic, _ in recorder.events] == [BRAIN_VOICE_STATUS, BRAIN_VOICE_ERRORS]
    assert isinstance(recorder.events[-1][1], VoiceSpeechFailed)


@pytest.mark.asyncio
async def test_consumer_dead_letters_exceptions() -> None:
    recorder = RecordingProducer()

    async def speaker(text: str, lady: str) -> bool:
        raise RuntimeError("say exploded")

    consumer = VoiceEventConsumer(
        consumer=FakeConsumer([VoiceSpeechRequested(text="Hello").to_dict()]),
        event_producer=recorder,
        speaker=speaker,
    )

    await consumer.process_batch()

    failed_event = recorder.events[-1][1]
    assert isinstance(failed_event, VoiceSpeechFailed)
    assert failed_event.error == "say exploded"


@pytest.mark.asyncio
async def test_consume_forever_respects_stop_event() -> None:
    recorder = RecordingProducer()
    stop_event = asyncio.Event()

    async def speaker(text: str, lady: str) -> bool:
        stop_event.set()
        return True

    consumer = VoiceEventConsumer(
        consumer=FakeConsumer([VoiceSpeechRequested(text="Hello").to_dict()]),
        event_producer=recorder,
        speaker=speaker,
    )

    batches = await consumer.consume_forever(stop_event=stop_event, poll_interval=0.01)

    assert batches == 1


@pytest.mark.asyncio
async def test_stream_speak_async_publishes_when_enabled() -> None:
    recorder = RecordingProducer()

    result = await speak_async(
        "Queue this",
        lady="Zosia",
        producer=recorder,
    )

    assert result is True
    assert recorder.events[0][0] == BRAIN_VOICE_REQUESTS
    assert recorder.events[0][1].lady == "Zosia"


@pytest.mark.asyncio
async def test_stream_speak_async_falls_back_when_publish_fails() -> None:
    fallback_calls: list[str] = []

    producer = VoiceEventProducer(producer=FailingProducer(), create_topics=False)

    result = await speak_async(
        "Fallback now",
        lady="Karen",
        producer=producer,
        fallback=lambda: fallback_calls.append("called") or True,
    )

    assert result is True
    assert fallback_calls == ["called"]


def test_shared_producer_uses_redpanda_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    import agentic_brain.voice.stream as stream_module

    monkeypatch.setenv("AGENTIC_BRAIN_VOICE_USE_REDPANDA", "true")
    monkeypatch.setattr(stream_module, "KafkaProducer", FakeProducer)
    stream_module._shared_voice_event_producer = None
    producer = get_voice_event_producer(enabled=None)

    assert producer.enabled is True


def test_consumer_close_closes_underlying_consumer() -> None:
    fake_consumer = FakeConsumer([])
    consumer = VoiceEventConsumer(consumer=fake_consumer, event_producer=RecordingProducer())

    consumer.close()

    assert fake_consumer.closed is True


def test_topic_constants_match_expected_contract() -> None:
    assert VOICE_TOPICS == (
        "brain.voice.requests",
        "brain.voice.status",
        "brain.voice.errors",
    )
