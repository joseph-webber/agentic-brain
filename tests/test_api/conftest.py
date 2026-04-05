# SPDX-License-Identifier: Apache-2.0
"""Fixtures for API test suite.

These tests are intentionally self-contained and avoid external services.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# Ensure FastAPI app factory runs in test mode even if modules are imported early.
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("SESSION_BACKEND", "memory")
# WebSocket auth uses JWT_SECRET. Empty is allowed in development mode.
os.environ.setdefault("JWT_SECRET", "")


def build_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    auth_enabled: bool = False,
    api_keys: str | None = None,
    cors_origins: list[str] | None = None,
    oauth2_enabled: bool = False,
) -> object:
    """Create an isolated FastAPI app instance for tests."""

    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("SESSION_BACKEND", "memory")
    monkeypatch.setenv("JWT_SECRET", "")

    monkeypatch.setenv("AUTH_ENABLED", "true" if auth_enabled else "false")
    if api_keys is not None:
        monkeypatch.setenv("API_KEYS", api_keys)
    else:
        monkeypatch.delenv("API_KEYS", raising=False)

    # Enable a minimal generic OIDC provider so /auth/sso/* endpoints can be exercised.
    monkeypatch.setenv("OAUTH2_ENABLED", "true" if oauth2_enabled else "false")
    if oauth2_enabled:
        monkeypatch.setenv("OAUTH2_CLIENT_ID", "client-id")
        monkeypatch.setenv("OAUTH2_CLIENT_SECRET", "client-secret")
        monkeypatch.setenv(
            "OAUTH2_AUTHORIZATION_URI", "https://example.com/oauth/authorize"
        )
        monkeypatch.setenv("OAUTH2_TOKEN_URI", "https://example.com/oauth/token")
        monkeypatch.setenv("OAUTH2_ISSUER_URI", "https://example.com")

    from agentic_brain.api import routes, sessions
    from agentic_brain.api.server import create_app

    # Reset global state between tests to avoid cross-test coupling.
    routes.request_counts.clear()
    routes._session_backend = None  # type: ignore[attr-defined]
    sessions.reset_session_backend()

    app = create_app(cors_origins=cors_origins)
    return app


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch):
    return build_app(monkeypatch, cors_origins=["http://example.com"])


@pytest.fixture()
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def auth_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    app = build_app(
        monkeypatch,
        auth_enabled=True,
        api_keys="valid-key",
        cors_origins=["http://example.com"],
    )
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def sso_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    app = build_app(
        monkeypatch,
        oauth2_enabled=True,
        cors_origins=["http://example.com"],
    )
    with TestClient(app) as client:
        yield client
