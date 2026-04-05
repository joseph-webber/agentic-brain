# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest
from fastapi import Depends, HTTPException, status
from fastapi.testclient import TestClient


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.status_code == 200

    # Core security headers
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "Strict-Transport-Security" in resp.headers
    assert "Content-Security-Policy" in resp.headers
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_cors_preflight_allows_configured_origin(client):
    headers = {
        "Origin": "http://example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    resp = client.options("/chat", headers=headers)
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://example.com"


def test_cors_preflight_blocks_unknown_origin(client):
    headers = {
        "Origin": "http://evil.example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    resp = client.options("/chat", headers=headers)
    # Starlette CORSMiddleware returns 400 for disallowed preflight origins.
    assert resp.status_code == 400
    assert resp.headers.get("access-control-allow-origin") != "http://evil.example.com"


def test_http_exception_handler_shapes_json(client):
    app = client.app

    @app.get("/__raise_http")
    async def _raise_http():
        raise HTTPException(status_code=418, detail="teapot")

    resp = client.get("/__raise_http")
    assert resp.status_code == 418
    body = resp.json()
    assert body["error"] == "teapot"
    assert body["status_code"] == 418


def test_generic_exception_handler_returns_500_json(client):
    app = client.app

    @app.get("/__boom")
    async def _boom():
        raise RuntimeError("boom")

    # Default TestClient re-raises server exceptions; disable for this test.
    with TestClient(app, raise_server_exceptions=False) as safe_client:
        resp = safe_client.get("/__boom")

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] == "Internal server error"
    assert body["status_code"] == 500


def test_rate_limiting_returns_429(monkeypatch, client):
    from agentic_brain.api import routes

    monkeypatch.setattr(routes, "RATE_LIMIT", 1)
    routes.request_counts.clear()

    first = client.post("/chat", json={"message": "hi"})
    assert first.status_code == 200

    second = client.post("/chat", json={"message": "hi again"})
    assert second.status_code == 429
    body = second.json()
    assert body["status_code"] == 429


def test_auth_required_returns_401(auth_client):
    resp = auth_client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 401


def test_auth_valid_api_key_allows(auth_client):
    resp = auth_client.post(
        "/chat", json={"message": "hi"}, headers={"X-API-Key": "valid-key"}
    )
    assert resp.status_code == 200


def test_auth_invalid_api_key_returns_401(auth_client):
    resp = auth_client.post(
        "/chat", json={"message": "hi"}, headers={"X-API-Key": "wrong"}
    )
    assert resp.status_code == 401


def test_forbidden_403_error_shape(client):
    app = client.app

    async def forbid():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    @app.get("/__forbidden")
    async def _forbidden(_: None = Depends(forbid)):
        return {"ok": True}

    resp = client.get("/__forbidden")
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"] == "forbidden"
    assert body["status_code"] == 403


def test_not_found_404_returns_default_shape(client):
    resp = client.get("/definitely-not-a-route")
    assert resp.status_code == 404
