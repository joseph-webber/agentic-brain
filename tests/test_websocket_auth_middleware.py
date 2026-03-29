# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

import datetime
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import WebSocket, status

from agentic_brain.api.websocket_auth import WebSocketAuthConfig, WebSocketAuthenticator


class TestWebSocketAuthenticator:

    @pytest.fixture
    def secret(self):
        return "test-secret-with-at-least-32-bytes"

    @pytest.fixture
    def config(self, secret):
        return WebSocketAuthConfig(secret_key=secret, require_auth=True)

    @pytest.fixture
    def authenticator(self, config):
        return WebSocketAuthenticator(config)

    @pytest.fixture
    def websocket(self):
        ws = AsyncMock(spec=WebSocket)
        ws.query_params = {}
        ws.headers = {}
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_auth_disabled(self, websocket):
        auth = WebSocketAuthenticator(WebSocketAuthConfig(require_auth=False))
        result = await auth.authenticate(websocket)
        assert result["authenticated"] is False
        assert result["user"] == "anonymous"
        websocket.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_token(self, authenticator, websocket):
        result = await authenticator.authenticate(websocket)
        assert result is None
        websocket.close.assert_called_once()
        call_args = websocket.close.call_args
        assert call_args.kwargs["code"] == status.WS_1008_POLICY_VIOLATION
        assert call_args.kwargs["reason"].startswith("Authentication required")

    @pytest.mark.asyncio
    async def test_valid_token_query_param(self, authenticator, websocket, secret):
        token = jwt.encode(
            {
                "sub": "user123",
                "exp": datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(hours=1),
            },
            secret,
            algorithm="HS256",
        )
        websocket.query_params = {"token": token}

        result = await authenticator.authenticate(websocket)
        assert result["authenticated"] is True
        assert result["user"] == "user123"
        websocket.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_token_header(self, authenticator, websocket, secret):
        token = jwt.encode(
            {
                "sub": "user123",
                "exp": datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(hours=1),
            },
            secret,
            algorithm="HS256",
        )
        websocket.headers = {"authorization": f"Bearer {token}"}

        result = await authenticator.authenticate(websocket)
        assert result["authenticated"] is True
        assert result["user"] == "user123"

    @pytest.mark.asyncio
    async def test_valid_token_protocol(self, authenticator, websocket, secret):
        token = jwt.encode(
            {
                "sub": "user123",
                "exp": datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(hours=1),
            },
            secret,
            algorithm="HS256",
        )
        websocket.headers = {"sec-websocket-protocol": f"json, {token}"}

        result = await authenticator.authenticate(websocket)
        assert result["authenticated"] is True
        assert result["user"] == "user123"

    @pytest.mark.asyncio
    async def test_invalid_token(self, authenticator, websocket):
        websocket.query_params = {"token": "invalid.token.here"}

        result = await authenticator.authenticate(websocket)
        assert result is None
        # Verify call was made with code 1008 and SOME reason starting with "Invalid token"
        websocket.close.assert_called_once()
        call_args = websocket.close.call_args
        assert call_args.kwargs["code"] == status.WS_1008_POLICY_VIOLATION
        assert call_args.kwargs["reason"].startswith("Invalid token:")

    @pytest.mark.asyncio
    async def test_expired_token(self, authenticator, websocket, secret):
        token = jwt.encode(
            {
                "sub": "user123",
                "exp": datetime.datetime.now(datetime.UTC)
                - datetime.timedelta(hours=1),
            },
            secret,
            algorithm="HS256",
        )
        websocket.query_params = {"token": token}

        result = await authenticator.authenticate(websocket)
        assert result is None
        websocket.close.assert_called_once()
        call_args = websocket.close.call_args
        assert call_args.kwargs["code"] == status.WS_1008_POLICY_VIOLATION
        assert call_args.kwargs["reason"].startswith("Token expired")
