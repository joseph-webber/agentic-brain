# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from collections.abc import Generator

import pytest


def get_jwt_backend():
    try:
        from jose import jwt

        return jwt
    except ImportError:
        import jwt

        return jwt


@pytest.fixture(autouse=True)
def reset_auth_state() -> Generator[None, None, None]:
    from agentic_brain.auth.config import reset_auth_config
    from agentic_brain.auth.context import clear_security_context
    from agentic_brain.auth.providers import (
        AuditLogger,
        RateLimiter,
        set_audit_logger,
        set_rate_limiter,
    )

    clear_security_context()
    reset_auth_config()
    set_audit_logger(AuditLogger())
    set_rate_limiter(RateLimiter())
    yield
    clear_security_context()
    reset_auth_config()
    set_audit_logger(AuditLogger())
    set_rate_limiter(RateLimiter())


@pytest.fixture
def auth_user():
    from agentic_brain.auth.models import User

    return User(
        id="user-123",
        login="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Admin",
        authorities=["ROLE_USER", "ROLE_ADMIN", "USER_VIEW", "USER_EDIT"],
    )


@pytest.fixture
def jwt_auth(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-auth-tests-1234567890")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_TOKEN_VALIDITY_SECONDS", "3600")
    monkeypatch.setenv("JWT_REMEMBER_ME_VALIDITY_SECONDS", "7200")
    monkeypatch.setenv("JWT_ISSUER", "auth-tests")
    monkeypatch.setenv("JWT_AUDIENCE", "auth-tests-clients")

    from agentic_brain.auth.config import reset_auth_config
    from agentic_brain.auth.providers import JWTAuth

    reset_auth_config()
    return JWTAuth()


@pytest.fixture
def session_auth(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_TIMEOUT_SECONDS", "1800")
    monkeypatch.setenv("REMEMBER_ME_ENABLED", "true")
    monkeypatch.setenv("REMEMBER_ME_KEY", "session-remember-key-for-tests")

    from agentic_brain.auth.config import reset_auth_config
    from agentic_brain.auth.providers import SessionAuth

    reset_auth_config()
    return SessionAuth()
