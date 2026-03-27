# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
import asyncio
import datetime
import json
import os
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import quote

import jwt
import pytest
from fastapi.testclient import TestClient

from agentic_brain.api.routes import session_messages, sessions
from agentic_brain.api.server import create_app
from agentic_brain.transport import (
    TransportConfig,
    WebSocketAuthConfig,
    WebSocketTransport,
)
from agentic_brain.transport.websocket_presence import WebSocketPresence


class DummyStreamer:
    def __init__(self, tokens):
        self._tokens = tokens

    async def stream_websocket(self, message, history):
        for token in self._tokens:
            yield token


class FailingStreamer:
    async def stream_websocket(self, message, history):
        raise RuntimeError("stream failure")
        yield  # pragma: no cover


@pytest.fixture(autouse=True)
def reset_legacy_sessions():
    sessions.clear()
    session_messages.clear()
    yield
    sessions.clear()
    session_messages.clear()


@pytest.fixture
def websocket_token(monkeypatch):
    secret = "test-secret-with-at-least-32-bytes"
    monkeypatch.setenv("JWT_SECRET", secret)
    payload = {
        "sub": "test-user",
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return quote(token)


@pytest.fixture
def client(websocket_token):
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.mark.skipif(
    os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true",
    reason="WebSocket tests hang on CI - StreamingResponse mock incompatible with CI event loop",
)
class TestWebSocketConnection:
    """Test WebSocket connection handling"""

    def test_websocket_endpoint_exists(self, client, websocket_token):
        """WebSocket endpoint should be registered"""
        with client.websocket_connect(f"/ws/chat?token={websocket_token}") as websocket:
            assert websocket is not None

    def test_websocket_connect(self, client, websocket_token):
        """Test WebSocket connection establishment"""
        tokens = [
            json.dumps({"token": "Hello", "is_end": False}),
            json.dumps({"token": "!", "is_end": True}),
        ]
        with patch(
            "agentic_brain.api.websocket.StreamingResponse",
            return_value=DummyStreamer(tokens),
        ):
            with client.websocket_connect(
                f"/ws/chat?token={websocket_token}"
            ) as websocket:
                websocket.send_text(json.dumps({"message": "Hi"}))
                first = websocket.receive_json()
                second = websocket.receive_json()

        assert first["token"] == "Hello"
        assert second["token"] == "!"
        assert len(sessions) == 1
        session_id = next(iter(sessions))
        assert sessions[session_id]["message_count"] == 1

    def test_websocket_send_message(self, client, websocket_token):
        """Test sending message over WebSocket"""
        tokens = [json.dumps({"token": "OK", "is_end": True})]
        session_id = "sess_test"
        with patch(
            "agentic_brain.api.websocket.StreamingResponse",
            return_value=DummyStreamer(tokens),
        ):
            with client.websocket_connect(
                f"/ws/chat?token={websocket_token}"
            ) as websocket:
                websocket.send_text(
                    json.dumps(
                        {"message": "Hello", "session_id": session_id, "user_id": "u1"}
                    )
                )
                websocket.receive_json()

        assert session_id in sessions
        assert session_messages[session_id][0]["role"] == "user"
        assert session_messages[session_id][0]["content"] == "Hello"

    def test_websocket_receive_message(self, client, websocket_token):
        """Test receiving message over WebSocket"""
        tokens = [
            json.dumps({"token": "A", "is_end": False}),
            json.dumps({"token": "B", "is_end": True}),
        ]
        with patch(
            "agentic_brain.api.websocket.StreamingResponse",
            return_value=DummyStreamer(tokens),
        ):
            with client.websocket_connect(
                f"/ws/chat?token={websocket_token}"
            ) as websocket:
                websocket.send_text(json.dumps({"message": "Ping"}))
                first = websocket.receive_json()
                second = websocket.receive_json()

        assert first["token"] == "A"
        assert second["token"] == "B"
        session_id = next(iter(sessions))
        assert session_messages[session_id][-1]["role"] == "assistant"
        assert session_messages[session_id][-1]["content"] == "AB"

    def test_websocket_disconnect(self, client, websocket_token):
        """Test graceful disconnect"""
        with client.websocket_connect(f"/ws/chat?token={websocket_token}") as websocket:
            assert websocket is not None

    def test_websocket_auth_required(self):
        """Test authentication is required if configured"""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.close = AsyncMock()
        mock_ws.send_json = AsyncMock()

        config = TransportConfig()
        auth_config = WebSocketAuthConfig(require_auth=True)
        transport = WebSocketTransport(config, mock_ws, auth_config=auth_config)

        with patch(
            "agentic_brain.transport.websocket.get_auth_provider", return_value=None
        ):
            result = asyncio.run(transport.connect(token="bad-token"))

        assert result is False
        mock_ws.close.assert_called_once()
        sent_payload = mock_ws.send_json.call_args[0][0]
        assert sent_payload["type"] == "auth_result"
        assert sent_payload["success"] is False

    @pytest.mark.asyncio
    async def test_websocket_broadcast(self):
        """Test broadcast to multiple clients"""
        presence = WebSocketPresence()
        ws_one = AsyncMock()
        ws_two = AsyncMock()

        await presence.add_connection("user1", ws_one, auto_online=False)
        await presence.add_connection("user2", ws_two, auto_online=False)

        await presence.set_online("user1")

        assert ws_one.send_json.call_count == 1
        assert ws_two.send_json.call_count == 1

    def test_websocket_error_handling(self, client, websocket_token):
        """Test error handling on bad messages"""
        with client.websocket_connect(f"/ws/chat?token={websocket_token}") as websocket:
            websocket.send_text("not-json")
            error = websocket.receive_json()

        assert error["error"] == "Invalid JSON"
        assert error["finish_reason"] == "error"

        with patch(
            "agentic_brain.api.websocket.StreamingResponse",
            return_value=FailingStreamer(),
        ):
            with client.websocket_connect(
                f"/ws/chat?token={websocket_token}"
            ) as websocket:
                websocket.send_text(json.dumps({"message": "Hello"}))
                error = websocket.receive_json()

        assert error["error"] == "stream failure"
        assert error["finish_reason"] == "error"
