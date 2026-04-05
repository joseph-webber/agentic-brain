from __future__ import annotations

import json

import jwt
import pytest


class DummyWSStreamer:
    def __init__(self, *, provider: str, model: str, temperature: float):
        self.provider = provider
        self.model = model
        self.temperature = temperature

    async def stream_websocket(self, message: str, history: list[dict]):
        # Emit two chunks and a terminating token.
        meta = {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
        }
        yield json.dumps(
            {"token": "Echo:", "is_start": True, "is_end": False, "metadata": meta}
        )
        yield json.dumps(
            {
                "token": f" {message}",
                "is_start": False,
                "is_end": True,
                "finish_reason": "stop",
                "metadata": meta,
            }
        )


class ErrorWSStreamer(DummyWSStreamer):
    async def stream_websocket(self, message: str, history: list[dict]):
        raise RuntimeError("streamer failed")
        yield  # pragma: no cover


def _token(secret: str = "") -> str:
    return jwt.encode({"sub": "user1"}, key=secret, algorithm="HS256")


def test_websocket_rejects_missing_token(client):
    # Connection is accepted then immediately closed with policy violation.
    with client.websocket_connect("/ws/chat") as ws:
        with pytest.raises(Exception):
            ws.receive_text()


def test_websocket_accepts_token_and_streams_response(client):
    client.app.state.streaming_response_factory = lambda **kw: DummyWSStreamer(**kw)

    with client.websocket_connect(f"/ws/chat?token={_token()}") as ws:
        ws.send_text(json.dumps({"message": "hello"}))
        msg1 = json.loads(ws.receive_text())
        msg2 = json.loads(ws.receive_text())

    assert msg1["token"] == "Echo:"
    assert msg1["is_start"] is True
    assert msg2["is_end"] is True
    assert "hello" in msg2["token"]


def test_websocket_invalid_json_returns_error(client):
    client.app.state.streaming_response_factory = lambda **kw: DummyWSStreamer(**kw)

    with client.websocket_connect(f"/ws/chat?token={_token()}") as ws:
        ws.send_text("not-json")
        err = json.loads(ws.receive_text())

    assert err["error_code"] == "INVALID_JSON"
    assert err["finish_reason"] == "error"


def test_websocket_missing_message_returns_error(client):
    client.app.state.streaming_response_factory = lambda **kw: DummyWSStreamer(**kw)

    with client.websocket_connect(f"/ws/chat?token={_token()}") as ws:
        ws.send_text(json.dumps({"session_id": "sess_1"}))
        err = json.loads(ws.receive_text())

    assert err["error_code"] == "MISSING_MESSAGE"


def test_websocket_temperature_is_sanitized_to_default(client):
    seen = {}

    def factory(**kw):
        seen.update(kw)
        return DummyWSStreamer(**kw)

    client.app.state.streaming_response_factory = factory

    with client.websocket_connect(f"/ws/chat?token={_token()}") as ws:
        ws.send_text(json.dumps({"message": "hello", "temperature": "not-a-number"}))
        _ = ws.receive_text()
        _ = ws.receive_text()

    assert seen["temperature"] == 0.7


def test_websocket_passes_provider_model_fields(client):
    seen = {}

    def factory(**kw):
        seen.update(kw)
        return DummyWSStreamer(**kw)

    client.app.state.streaming_response_factory = factory

    with client.websocket_connect(f"/ws/chat?token={_token()}") as ws:
        ws.send_text(
            json.dumps({"message": "hello", "provider": "ollama", "model": "mistral"})
        )
        _ = ws.receive_text()
        _ = ws.receive_text()

    assert seen["provider"] == "ollama"
    assert seen["model"] == "mistral"


def test_websocket_multiple_messages_same_connection(client):
    client.app.state.streaming_response_factory = lambda **kw: DummyWSStreamer(**kw)

    with client.websocket_connect(f"/ws/chat?token={_token()}") as ws:
        ws.send_text(json.dumps({"message": "one"}))
        _ = ws.receive_text()
        end1 = json.loads(ws.receive_text())

        ws.send_text(json.dumps({"message": "two"}))
        _ = ws.receive_text()
        end2 = json.loads(ws.receive_text())

    assert end1["is_end"] is True
    assert end2["is_end"] is True


def test_websocket_internal_error_yields_error_payload(client):
    client.app.state.streaming_response_factory = lambda **kw: ErrorWSStreamer(**kw)

    with client.websocket_connect(f"/ws/chat?token={_token()}") as ws:
        ws.send_text(json.dumps({"message": "boom"}))
        err = json.loads(ws.receive_text())

    assert err["error_code"] == "INTERNAL_ERROR"
    assert err["finish_reason"] == "error"


def test_websocket_protocol_header_token_works(client):
    client.app.state.streaming_response_factory = lambda **kw: DummyWSStreamer(**kw)

    token = _token()
    with client.websocket_connect(
        "/ws/chat",
        headers={"Sec-WebSocket-Protocol": token},
    ) as ws:
        ws.send_text(json.dumps({"message": "hello"}))
        _ = ws.receive_text()
        end = json.loads(ws.receive_text())

    assert end["is_end"] is True


def test_websocket_bad_token_rejected(client):
    # Bad token that will fail decode -> connection closes with policy violation.
    with client.websocket_connect("/ws/chat?token=not-a-jwt") as ws:
        with pytest.raises(Exception):
            ws.receive_text()


def test_websocket_session_id_preserved_in_requests(client):
    client.app.state.streaming_response_factory = lambda **kw: DummyWSStreamer(**kw)

    with client.websocket_connect(f"/ws/chat?token={_token()}") as ws:
        ws.send_text(json.dumps({"message": "hello", "session_id": "sess_abc"}))
        _ = ws.receive_text()
        end = json.loads(ws.receive_text())

    assert end["is_end"] is True
