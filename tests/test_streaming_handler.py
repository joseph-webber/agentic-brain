from __future__ import annotations

import json

import pytest

from agentic_brain.streaming.stream_handler import (
    StreamingResponse,
    StreamProvider,
    StreamToken,
    iter_chunked_lines,
    iter_sse_payloads,
    iter_text_chunks,
)


class DummyStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for chunk in self._chunks:
            yield chunk


class DummyResponder(StreamingResponse):
    async def stream(self, message: str, conversation_history=None):
        yield StreamToken(token="hello", is_start=True, metadata={"provider": "dummy"})
        yield StreamToken(token=" world", is_end=True, finish_reason="stop")


def test_stream_token_defaults_metadata():
    token = StreamToken(token="hi")
    assert token.metadata == {}


def test_stream_token_to_dict():
    token = StreamToken(
        token="hi", is_end=True, finish_reason="stop", metadata={"a": 1}
    )
    assert token.to_dict()["metadata"]["a"] == 1


def test_stream_token_to_sse():
    token = StreamToken(token="hi", is_start=True)
    assert token.to_sse().startswith("data: ")
    assert token.to_sse().endswith("\n\n")


@pytest.mark.asyncio
async def test_iter_text_chunks_decodes_bytes():
    chunks = DummyStream([b"hel", "lo"])
    assert [chunk async for chunk in iter_text_chunks(chunks)] == ["hel", "lo"]


@pytest.mark.asyncio
async def test_iter_text_chunks_skips_none():
    chunks = DummyStream([None, b"ok"])
    assert [chunk async for chunk in iter_text_chunks(chunks)] == ["ok"]


@pytest.mark.asyncio
async def test_iter_chunked_lines_reassembles_split_line():
    chunks = DummyStream([b'{"a":', b'1}\n{"b":2}\n'])
    assert [line async for line in iter_chunked_lines(chunks)] == ['{"a":1}', '{"b":2}']


@pytest.mark.asyncio
async def test_iter_chunked_lines_handles_final_partial_line():
    chunks = DummyStream([b'{"a":1}'])
    assert [line async for line in iter_chunked_lines(chunks)] == ['{"a":1}']


@pytest.mark.asyncio
async def test_iter_chunked_lines_ignores_blank_lines():
    chunks = DummyStream([b"\n\n", b"hello\n"])
    assert [line async for line in iter_chunked_lines(chunks)] == ["hello"]


@pytest.mark.asyncio
async def test_iter_sse_payloads_reads_data_lines():
    chunks = DummyStream([b"data: one\n\n", b"data: two\n\n"])
    assert [item async for item in iter_sse_payloads(chunks)] == ["one", "two"]


@pytest.mark.asyncio
async def test_iter_sse_payloads_handles_done():
    chunks = DummyStream([b"data: [DONE]\n\n"])
    assert [item async for item in iter_sse_payloads(chunks)] == ["[DONE]"]


@pytest.mark.asyncio
async def test_iter_sse_payloads_joins_multiline_events():
    chunks = DummyStream([b'data: {"a":1}\n', b'data: {"b":2}\n\n'])
    assert [item async for item in iter_sse_payloads(chunks)] == ['{"a":1}\n{"b":2}']


def test_stream_provider_values():
    assert StreamProvider.OLLAMA.value == "ollama"
    assert StreamProvider.OPENAI.value == "openai"
    assert StreamProvider.ANTHROPIC.value == "anthropic"


def test_streaming_response_ollama_defaults():
    streamer = StreamingResponse(provider="ollama")
    assert streamer.api_base == "http://localhost:11434"
    assert streamer.system_prompt == "You are a helpful assistant."


def test_streaming_response_openai_requires_key():
    with pytest.raises(ValueError):
        StreamingResponse(provider="openai")


def test_streaming_response_anthropic_requires_key():
    with pytest.raises(ValueError):
        StreamingResponse(provider="anthropic")


def test_streaming_response_make_messages_copies_history():
    streamer = StreamingResponse(provider="ollama")
    history = [{"role": "assistant", "content": "x"}]
    messages = streamer._make_messages("y", history)
    assert len(history) == 1
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_stream_sse_wraps_stream():
    streamer = DummyResponder(provider="ollama")
    items = [item async for item in streamer.stream_sse("hello")]
    assert len(items) == 2
    assert json.loads(items[0][6:-2])["token"] == "hello"


@pytest.mark.asyncio
async def test_stream_websocket_wraps_stream():
    streamer = DummyResponder(provider="ollama")
    items = [item async for item in streamer.stream_websocket("hello")]
    assert json.loads(items[1])["is_end"] is True


@pytest.mark.asyncio
async def test_as_fastapi_response_uses_event_stream_headers():
    streamer = DummyResponder(provider="ollama")
    response = streamer.as_fastapi_response("hello", headers={"X-Test": "1"})
    assert response.media_type == "text/event-stream"
    assert response.headers["x-test"] == "1"


@pytest.mark.asyncio
async def test_as_fastapi_response_body_iterator_yields_sse():
    streamer = DummyResponder(provider="ollama")
    response = streamer.as_fastapi_response("hello")
    body = [chunk async for chunk in response.body_iterator]
    assert any(
        ("hello" in chunk.decode() if isinstance(chunk, bytes) else "hello" in chunk)
        for chunk in body
    )


@pytest.mark.asyncio
async def test_stream_routes_to_ollama(monkeypatch):
    streamer = StreamingResponse(provider="ollama")

    async def fake_ollama(message, conversation_history=None):
        yield StreamToken(token="ollama")

    monkeypatch.setattr(streamer, "_stream_ollama", fake_ollama)
    tokens = [token async for token in streamer.stream("x")]
    assert tokens[0].token == "ollama"


@pytest.mark.asyncio
async def test_stream_routes_to_openai(monkeypatch):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("OPENAI_API_KEY", "sk-test")
        streamer = StreamingResponse(provider="openai")

    async def fake_openai(message, conversation_history=None):
        yield StreamToken(token="openai")

    monkeypatch.setattr(streamer, "_stream_openai", fake_openai)
    tokens = [token async for token in streamer.stream("x")]
    assert tokens[0].token == "openai"


@pytest.mark.asyncio
async def test_stream_routes_to_anthropic(monkeypatch):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ANTHROPIC_API_KEY", "sk-test")
        streamer = StreamingResponse(provider="anthropic")

    async def fake_anthropic(message, conversation_history=None):
        yield StreamToken(token="anthropic")

    monkeypatch.setattr(streamer, "_stream_anthropic", fake_anthropic)
    tokens = [token async for token in streamer.stream("x")]
    assert tokens[0].token == "anthropic"
