# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

import asyncio
import json
from typing import Any

import pytest

from agentic_brain.commerce.woo_api.client import (
    WooAPIClient,
    WooAPIError,
    WooResourceAPI,
)


class FakeResponse:
    def __init__(
        self, status: int, payload: Any, headers: dict[str, str] | None = None
    ) -> None:
        self.status = status
        self._payload = payload
        self.headers = headers or {"Content-Type": "application/json"}

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: D401
        return False

    async def json(self, loads=json.loads) -> Any:  # noqa: D401
        return self._payload

    async def text(self) -> str:
        if isinstance(self._payload, str):
            return self._payload
        return json.dumps(self._payload)


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.closed = False
        self.last_request: tuple[str, str, dict[str, Any]] | None = None

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.last_request = (method, url, kwargs)
        return self._response

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_request_success() -> None:
    session = FakeSession(FakeResponse(200, {"ok": True}))
    client = WooAPIClient("https://example.com", "ck", "cs", session=session)

    data = await client.request("GET", "products")

    assert data == {"ok": True}
    assert session.last_request[0] == "GET"
    assert session.last_request[1].endswith("/products")


@pytest.mark.asyncio
async def test_request_error() -> None:
    session = FakeSession(
        FakeResponse(404, {"code": "not_found", "message": "Missing"})
    )
    client = WooAPIClient("https://example.com", "ck", "cs", session=session)

    with pytest.raises(WooAPIError) as exc:
        await client.request("GET", "products/999")

    assert exc.value.status == 404
    assert "Missing" in str(exc.value)


@pytest.mark.asyncio
async def test_paginate_accumulates(monkeypatch: pytest.MonkeyPatch) -> None:
    client = WooAPIClient("https://example.com", "ck", "cs")
    responses = [[{"id": 1}], []]

    async def fake_request(method: str, endpoint: str, **kwargs: Any) -> Any:
        return responses.pop(0)

    monkeypatch.setattr(client, "request", fake_request)

    result = await client.paginate("products", per_page=50)

    assert result == [{"id": 1}]


@pytest.mark.asyncio
async def test_batch_requires_payload() -> None:
    client = WooAPIClient("https://example.com", "ck", "cs")
    with pytest.raises(ValueError):
        await client.batch("products/batch", {})


def test_resource_sync_proxy_runs_coroutines() -> None:
    class DummyClient:
        def run_sync(self, awaitable: Any) -> Any:
            return asyncio.run(awaitable)

    class DummyResource(WooResourceAPI):
        def __init__(self) -> None:
            super().__init__(DummyClient())

        async def echo(self, value: int) -> int:
            return value

    resource = DummyResource()

    assert resource.sync.echo(7) == 7
