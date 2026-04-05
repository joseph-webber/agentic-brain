from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_brain.auth.constants import (
    CLAIM_AUDIENCE,
    CLAIM_AUTHORITIES,
    CLAIM_ISSUER,
    CLAIM_JWT_ID,
    CLAIM_SUBJECT,
)
from agentic_brain.auth.models import RefreshTokenCredentials, TokenCredentials
from agentic_brain.auth.refresh_tokens import (
    InMemoryRefreshTokenStore,
    RefreshTokenService,
)


def _get_jwt_backend():
    try:
        from jose import jwt

        return jwt
    except ImportError:
        import jwt

        return jwt


def _decode_without_verification(token: str):
    jwt_backend = _get_jwt_backend()
    if hasattr(jwt_backend, "get_unverified_claims"):
        return jwt_backend.get_unverified_claims(token)
    return jwt_backend.decode(token, options={"verify_signature": False})


def _encode_token(jwt_backend, secret: str, algorithm: str, payload: dict):
    return jwt_backend.encode(payload, secret, algorithm=algorithm)


@pytest.mark.asyncio
async def test_generate_token_round_trips_user_claims(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(auth_user)
    validated = await jwt_auth.validate_token(token.access_token)

    assert validated is not None
    assert validated.login == auth_user.login
    assert validated.email == auth_user.email
    assert validated.first_name == auth_user.first_name
    assert validated.last_name == auth_user.last_name
    assert validated.authorities == auth_user.authorities


@pytest.mark.asyncio
async def test_generate_token_includes_expected_registered_claims(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(auth_user)
    payload = _decode_without_verification(token.access_token)

    assert payload[CLAIM_SUBJECT] == auth_user.login
    assert payload[CLAIM_AUDIENCE] == jwt_auth.config.jwt.audience
    assert payload[CLAIM_ISSUER] == jwt_auth.config.jwt.issuer
    assert payload[CLAIM_AUTHORITIES] == ",".join(auth_user.authorities)
    assert payload[CLAIM_JWT_ID]


@pytest.mark.asyncio
async def test_generate_token_filters_sensitive_extra_claims(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(
        auth_user,
        extra_claims={
            "team": "security",
            "password": "should-not-leak",
            "secret": "hidden",
            "api_key": "hidden-too",
            "credential_blob": "hidden-three",
        },
    )
    payload = _decode_without_verification(token.access_token)

    assert payload["team"] == "security"
    assert "password" not in payload
    assert "secret" not in payload
    assert "api_key" not in payload
    assert "credential_blob" not in payload


@pytest.mark.asyncio
async def test_generate_token_with_remember_me_issues_refresh_token(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(auth_user, remember_me=True)

    assert token.refresh_token is not None
    assert token.expires_in == jwt_auth.config.jwt.token_validity_seconds_for_remember_me


@pytest.mark.asyncio
async def test_validate_token_rejects_tampered_token(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(auth_user)
    tampered = f"{token.access_token[:-1]}x"

    assert await jwt_auth.validate_token(tampered) is None


@pytest.mark.asyncio
async def test_validate_token_rejects_expired_token(jwt_auth, auth_user):
    jwt_backend = _get_jwt_backend()
    now = datetime.now(UTC)
    payload = {
        CLAIM_SUBJECT: auth_user.login,
        CLAIM_AUTHORITIES: ",".join(auth_user.authorities),
        CLAIM_ISSUER: jwt_auth.config.jwt.issuer,
        CLAIM_AUDIENCE: jwt_auth.config.jwt.audience,
        "iat": (now - timedelta(hours=2)).timestamp(),
        "exp": (now - timedelta(hours=1)).timestamp(),
        CLAIM_JWT_ID: "expired-jti",
    }
    token = _encode_token(
        jwt_backend,
        jwt_auth.config.jwt.secret,
        jwt_auth.config.jwt.algorithm,
        payload,
    )

    assert await jwt_auth.validate_token(token) is None


@pytest.mark.asyncio
async def test_revoke_token_prevents_future_validation(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(auth_user)

    assert await jwt_auth.revoke_token(token.access_token) is True
    assert await jwt_auth.validate_token(token.access_token) is None
    assert jwt_auth.get_blacklist_count() == 1


@pytest.mark.asyncio
async def test_refresh_token_rotates_refresh_token_and_revokes_prior_access(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(auth_user, remember_me=True)

    refreshed = await jwt_auth.refresh_token(token.refresh_token)

    assert refreshed is not None
    assert refreshed.refresh_token is not None
    assert refreshed.refresh_token != token.refresh_token
    assert await jwt_auth.validate_token(token.access_token) is None
    assert await jwt_auth.validate_token(refreshed.access_token) is not None


@pytest.mark.asyncio
async def test_refresh_token_cannot_be_used_twice(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(auth_user, remember_me=True)

    first = await jwt_auth.refresh_token(token.refresh_token)
    second = await jwt_auth.refresh_token(token.refresh_token)

    assert first is not None
    assert second is None


@pytest.mark.asyncio
async def test_refresh_token_rejects_access_token_input(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(auth_user)

    assert await jwt_auth.refresh_token(token.access_token) is None


@pytest.mark.asyncio
async def test_authenticate_token_credentials_succeeds(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(auth_user)

    result = await jwt_auth.authenticate(TokenCredentials(token=token.access_token))

    assert result.success is True
    assert result.user is not None
    assert result.user.login == auth_user.login
    assert result.token is not None


@pytest.mark.asyncio
async def test_authenticate_invalid_token_credentials_fails(jwt_auth):
    result = await jwt_auth.authenticate(TokenCredentials(token="not-a-real-token"))

    assert result.success is False
    assert result.error == "invalid_token"


@pytest.mark.asyncio
async def test_authenticate_refresh_token_credentials_succeeds(jwt_auth, auth_user):
    issued = await jwt_auth.generate_token(auth_user, remember_me=True)

    result = await jwt_auth.authenticate(
        RefreshTokenCredentials(refresh_token=issued.refresh_token)
    )

    assert result.success is True
    assert result.token is not None
    assert result.token.access_token != issued.access_token


@pytest.mark.asyncio
async def test_refresh_token_service_creates_access_and_refresh_tokens():
    service = RefreshTokenService(
        store=InMemoryRefreshTokenStore(),
        access_token_ttl_seconds=600,
        refresh_token_ttl_seconds=1200,
    )

    result = await service.create_tokens(
        user_id="user-1",
        user_login="alice",
        generate_access_token=lambda user_id: f"access:{user_id}",
    )

    assert result.success is True
    assert result.access_token == "access:user-1"
    assert result.refresh_token is not None
    assert result.expires_in == 600


@pytest.mark.asyncio
async def test_refresh_token_service_detects_reuse_and_revokes_family():
    store = InMemoryRefreshTokenStore()
    service = RefreshTokenService(store=store)

    initial = await service.create_tokens(
        user_id="user-1",
        user_login="alice",
        generate_access_token=lambda user_id: f"access:{user_id}",
    )
    rotated = await service.refresh(
        initial.refresh_token,
        generate_access_token=lambda user_id: f"access2:{user_id}",
    )
    reused = await service.refresh(
        initial.refresh_token,
        generate_access_token=lambda user_id: f"access3:{user_id}",
    )

    assert rotated.success is True
    assert reused.success is False
    assert reused.error == "token_reused"

    new_token_data = await store.get(service._hash_token(rotated.refresh_token))
    assert new_token_data is not None
    assert new_token_data.revoked is True
    assert new_token_data.revoked_reason == "reuse_attack"


@pytest.mark.asyncio
async def test_refresh_token_service_rejects_client_mismatch():
    service = RefreshTokenService(
        store=InMemoryRefreshTokenStore(),
        bind_to_client=True,
    )
    initial = await service.create_tokens(
        user_id="user-1",
        user_login="alice",
        generate_access_token=lambda user_id: f"access:{user_id}",
        client_ip="10.0.0.1",
        user_agent="browser-a",
    )

    result = await service.refresh(
        initial.refresh_token,
        generate_access_token=lambda user_id: f"access:{user_id}",
        client_ip="10.0.0.2",
        user_agent="browser-a",
    )

    assert result.success is False
    assert result.error == "client_mismatch"
