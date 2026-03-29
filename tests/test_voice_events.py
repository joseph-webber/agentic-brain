# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from agentic_brain.events.voice_events import (
    LLM_STREAMING,
    VOICE_CONTROL,
    VOICE_INPUT,
    VOICE_REQUEST,
    VOICE_STATUS,
    VoiceEventConsumer,
    VoiceEventProducer,
    VoiceRequest,
    VoiceStatus,
)
from agentic_brain.voice.llm_voice import stream_voice_response
from agentic_brain.voice.redpanda_queue import RedpandaVoiceQueue, VoicePriority


class FakeFuture:
    def get(self, timeout: int = 5) -> dict[str, str]:
        return {"status": "ok"}


class FakeProducer:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict, bytes | None]] = []
        self.flushed = False
        self.closed = False

    def send(self, topic: str, value: dict, key: bytes | None = None, headers=None):
        self.messages.append((topic, value, key))
        return FakeFuture()

    def flush(self, timeout: int = 5) -> None:
        self.flushed = True

    def close(self) -> None:
        self.closed = True


class FakeConsumer:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = [SimpleNamespace(value=message) for message in messages]
        self.closed = False

    def __iter__(self):
        return iter(self._messages)

    def poll(self, timeout_ms: int = 1000, max_records: int = 100):
        return {"topic": self._messages[:max_records]}

    def close(self) -> None:
        self.closed = True


class RecordingEventProducer:
    def __init__(self) -> None:
        self.requests: list[VoiceRequest] = []
        self.statuses: list[VoiceStatus] = []
        self.streams: list[dict] = []
        self.closed = False

    def request_speech(self, request: VoiceRequest) -> bool:
        self.requests.append(request)
        return True

    def publish_status(self, status: VoiceStatus) -> bool:
        self.statuses.append(status)
        return True

    def publish_llm_stream(self, text: str, **kwargs) -> bool:
        self.streams.append({"text": text, **kwargs})
        return True

    def close(self) -> None:
        self.closed = True


def test_voice_request_round_trip() -> None:
    request = VoiceRequest(
        text="Hello Joseph",
        voice="Karen",
        rate=160,
        priority=75,
        spatial_position=(1, 2, 3),
        metadata={"source": "test"},
    )

    payload = request.to_payload()
    restored = VoiceRequest.from_payload(payload)

    assert restored.text == "Hello Joseph"
    assert restored.voice == "Karen"
    assert restored.priority == 75
    assert restored.spatial_position == (1.0, 2.0, 3.0)
    assert restored.metadata["source"] == "test"


def test_voice_status_round_trip() -> None:
    status = VoiceStatus(
        event="completed",
        text="Done",
        voice="Karen",
        queue_depth=2,
        request_id="req-1",
        metadata={"source": "test"},
    )

    restored = VoiceStatus.from_payload(status.to_payload())
    assert restored.event == "completed"
    assert restored.queue_depth == 2
    assert restored.request_id == "req-1"
    assert restored.metadata["source"] == "test"


def test_voice_event_producer_publishes_all_topics() -> None:
    fake = FakeProducer()
    producer = VoiceEventProducer(producer=fake)

    request = VoiceRequest(text="Speak now")
    status = VoiceStatus(
        event="started", text="Speak now", voice="Karen", queue_depth=1
    )

    assert producer.request_speech(request) is True
    assert producer.publish_status(status) is True
    assert producer.publish_input("hi", source="mic") is True
    assert producer.publish_control("stop") is True
    assert producer.publish_llm_stream("chunk", request_id="abc", done=False) is True

    topics = [topic for topic, _, _ in fake.messages]
    assert topics == [
        VOICE_REQUEST,
        VOICE_STATUS,
        VOICE_INPUT,
        VOICE_CONTROL,
        LLM_STREAMING,
    ]

    producer.close()
    assert fake.flushed is True
    assert fake.closed is True


def test_voice_event_consumer_processes_messages() -> None:
    received: list[dict] = []
    consumer = VoiceEventConsumer(
        [VOICE_REQUEST],
        consumer=FakeConsumer([{"text": "one"}, {"text": "two"}]),
    )

    processed = consumer.process_requests(received.append)

    assert processed == 2
    assert received == [{"text": "one"}, {"text": "two"}]
    consumer.close()


@pytest.mark.asyncio
async def test_redpanda_queue_publishes_request_and_status_events() -> None:
    recorder = RecordingEventProducer()
    spoken: list[tuple[str, str, int]] = []

    async def fake_speak(text: str, voice: str, rate: int) -> bool:
        spoken.append((text, voice, rate))
        return True

    queue = RedpandaVoiceQueue(
        backend="memory",
        speak_func=fake_speak,
        event_producer=recorder,
    )
    await queue.connect()
    await queue.speak("Queued hello", priority=VoicePriority.HIGH)

    task = asyncio.create_task(queue.process_queue())
    await asyncio.sleep(0.05)
    await queue.stop()
    task.cancel()

    assert spoken == [("Queued hello", "Karen", 155)]
    assert len(recorder.requests) == 1
    assert [status.event for status in recorder.statuses] == ["started", "completed"]


@pytest.mark.asyncio
async def test_stream_voice_response_publishes_stream_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = RecordingEventProducer()
    monkeypatch.setattr(
        "agentic_brain.voice.llm_voice.get_voice_event_producer",
        lambda: recorder,
    )

    spoken: list[str] = []
    monkeypatch.setattr(
        "agentic_brain.voice.llm_voice._speak_sentence",
        lambda text, voice: spoken.append(text),
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            for line in [
                '{"response": "Hello there. "}',
                '{"response": "How are you?"}',
            ]:
                yield line

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def stream(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "agentic_brain.voice.llm_voice.httpx.AsyncClient", FakeAsyncClient
    )

    async def fake_get_llm_voice():
        return SimpleNamespace(_model="test-model", _base_url="http://localhost:11434")

    monkeypatch.setattr(
        "agentic_brain.voice.llm_voice.get_llm_voice", fake_get_llm_voice
    )

    await stream_voice_response("Say hello")

    assert spoken == ["Hello there.", "How are you?"]
    assert recorder.streams[0]["metadata"]["phase"] == "started"
    assert recorder.streams[-1]["done"] is True
    assert recorder.streams[-1]["metadata"]["phase"] == "completed"
