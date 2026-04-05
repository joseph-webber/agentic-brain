# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_brain.auth.models import SessionCredentials, UsernamePasswordCredentials


@pytest.mark.asyncio
async def test_create_session_returns_unique_opaque_ids(session_auth, auth_user):
    first = await session_auth.create_session(auth_user)
    second = await session_auth.create_session(auth_user)

    assert first != second
    assert len(first) > 20
    assert len(second) > 20
    assert auth_user.login not in first


@pytest.mark.asyncio
async def test_validate_token_returns_user_for_active_session(session_auth, auth_user):
    session_id = await session_auth.create_session(auth_user)

    validated = await session_auth.validate_token(session_id)

    assert validated is not None
    assert validated.login == auth_user.login
    assert validated.authorities == auth_user.authorities


@pytest.mark.asyncio
async def test_validate_token_returns_none_for_unknown_session(session_auth):
    assert await session_auth.validate_token("missing-session") is None


@pytest.mark.asyncio
async def test_validate_token_removes_expired_session(session_auth, auth_user):
    session_id = await session_auth.create_session(auth_user)
    session_auth._sessions[session_id]["expires_at"] = datetime.now(UTC) - timedelta(
        seconds=1
    )

    assert await session_auth.validate_token(session_id) is None
    assert session_id not in session_auth._sessions


@pytest.mark.asyncio
async def test_authenticate_with_session_credentials_succeeds(session_auth, auth_user):
    session_id = await session_auth.create_session(auth_user)

    result = await session_auth.authenticate(SessionCredentials(session_id=session_id))

    assert result.success is True
    assert result.user is not None
    assert result.user.login == auth_user.login


@pytest.mark.asyncio
async def test_authenticate_with_invalid_session_fails(session_auth):
    result = await session_auth.authenticate(SessionCredentials(session_id="missing"))

    assert result.success is False
    assert result.error == "invalid_session"


@pytest.mark.asyncio
async def test_authenticate_username_password_creates_session_token(session_auth):
    result = await session_auth.authenticate(
        UsernamePasswordCredentials(username="jane", password="secret")
    )

    assert result.success is True
    assert result.user is not None
    assert result.user.login == "jane"
    assert result.token is not None
    assert result.token.token_type == "Session"
    assert result.token.access_token in session_auth._sessions


@pytest.mark.asyncio
async def test_authenticate_username_password_with_remember_me_adds_refresh_token(
    session_auth,
):
    result = await session_auth.authenticate(
        UsernamePasswordCredentials(
            username="remembered",
            password="secret",
            remember_me=True,
        )
    )

    assert result.success is True
    assert result.token is not None
    assert result.token.refresh_token is not None


@pytest.mark.asyncio
async def test_authenticate_uses_valid_remember_me_token_to_reissue_session(
    session_auth,
):
    original = await session_auth.authenticate(
        UsernamePasswordCredentials(
            username="remembered",
            password="secret",
            remember_me=True,
        )
    )
    old_session_id = original.token.access_token
    remember_me_token = original.token.refresh_token
    await session_auth.revoke_token(old_session_id)

    result = await session_auth.authenticate(
        SessionCredentials(
            session_id="expired-session",
            remember_me_token=remember_me_token,
        )
    )

    assert result.success is True
    assert result.user is not None
    assert result.user.login == "remembered"
    assert result.token is not None
    assert result.token.access_token != old_session_id
    assert result.token.access_token in session_auth._sessions


@pytest.mark.asyncio
async def test_remember_me_storage_uses_hash_not_raw_token(session_auth, auth_user):
    remember_me_token = await session_auth._create_remember_me_token(auth_user)

    assert remember_me_token not in session_auth._remember_me_tokens
    assert len(session_auth._remember_me_tokens) == 1


@pytest.mark.asyncio
async def test_remember_me_token_invalid_after_key_change(session_auth, auth_user):
    remember_me_token = await session_auth._create_remember_me_token(auth_user)
    session_auth.config.session.remember_me_key = "different-key"

    assert await session_auth._validate_remember_me(remember_me_token) is None


@pytest.mark.asyncio
async def test_revoke_token_invalidates_existing_session(session_auth, auth_user):
    session_id = await session_auth.create_session(auth_user)

    assert await session_auth.revoke_token(session_id) is True
    assert await session_auth.validate_token(session_id) is None


@pytest.mark.asyncio
async def test_revoke_token_returns_false_for_missing_session(session_auth):
    assert await session_auth.revoke_token("missing") is False


@pytest.mark.asyncio
async def test_cleanup_expired_removes_only_expired_sessions(session_auth, auth_user):
    active = await session_auth.create_session(auth_user)
    expired = await session_auth.create_session(auth_user)
    session_auth._sessions[expired]["expires_at"] = datetime.now(UTC) - timedelta(
        seconds=1
    )

    removed = await session_auth.cleanup_expired()

    assert removed == 1
    assert active in session_auth._sessions
    assert expired not in session_auth._sessions


@pytest.mark.asyncio
async def test_session_expiry_uses_configured_timeout(monkeypatch, auth_user):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_AUTH_ENABLED", "true")
    monkeypatch.setenv("SESSION_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("REMEMBER_ME_KEY", "timeout-key")

    from agentic_brain.auth.config import reset_auth_config
    from agentic_brain.auth.providers import SessionAuth

    reset_auth_config()
    auth = SessionAuth()
    session_id = await auth.create_session(auth_user)
    created = auth._sessions[session_id]["created_at"]
    expires = auth._sessions[session_id]["expires_at"]

    assert int((expires - created).total_seconds()) == 5


@pytest.mark.asyncio
async def test_authenticate_rejects_unsupported_credentials(session_auth):
    from agentic_brain.auth.models import TokenCredentials

    result = await session_auth.authenticate(TokenCredentials(token="jwt"))

    assert result.success is False
    assert result.error == "unsupported_credentials"
