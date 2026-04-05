from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from agentic_brain.auth.config import AuthConfig
from agentic_brain.auth.context import SecurityContextManager
from agentic_brain.auth.decorators import _evaluate_security_expression
from agentic_brain.auth.models import AuthenticationResult, User
from agentic_brain.auth.providers import (
    AuditLogger,
    RateLimiter,
    _mask_sensitive,
    _secure_compare,
    _secure_hash,
    rate_limit,
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


def test_secure_compare_matches_only_equal_strings():
    assert _secure_compare("same-value", "same-value") is True
    assert _secure_compare("same-value", "different-value") is False


def test_secure_compare_rejects_non_string_inputs():
    assert _secure_compare("text", b"text") is False
    assert _secure_compare(None, "text") is False


def test_secure_hash_is_deterministic_for_same_input_and_key():
    first = _secure_hash("token-value", "key-1")
    second = _secure_hash("token-value", "key-1")

    assert first == second


def test_secure_hash_changes_when_key_changes():
    first = _secure_hash("token-value", "key-1")
    second = _secure_hash("token-value", "key-2")

    assert first != second


def test_mask_sensitive_masks_long_and_short_values():
    assert _mask_sensitive("abcdefghijkl") == "abcd...****"
    assert _mask_sensitive("abc") == "***"
    assert _mask_sensitive("") == "***"


def test_validate_api_key_uses_constant_time_compare(monkeypatch):
    comparisons: list[tuple[str, str]] = []

    def fake_compare(left: str, right: str) -> bool:
        comparisons.append((left, right))
        return left == right

    config = AuthConfig(api_keys=["key-a", "key-b"])

    with patch("secrets.compare_digest", side_effect=fake_compare):
        assert config.validate_api_key("key-b") is True

    assert comparisons == [("key-b", "key-a"), ("key-b", "key-b")]


def test_validate_api_key_rejects_empty_and_missing_values():
    assert AuthConfig(api_keys=[]).validate_api_key("key-a") is False
    assert AuthConfig(api_keys=["key-a"]).validate_api_key("") is False
    assert AuthConfig(api_keys=["key-a"]).validate_api_key(None) is False


def test_validate_api_key_rejects_injection_style_input():
    config = AuthConfig(api_keys=["safe-key"])

    assert config.validate_api_key("safe-key\nX-Injected: true") is False
    assert config.validate_api_key("' OR 1=1 --") is False


def test_audit_logger_filters_sensitive_fields_from_logs(caplog):
    logger = AuditLogger()

    with caplog.at_level("INFO"):
        logger.log_event(
            event_type="LOGIN",
            user_id="alice",
            details={
                "ip": "127.0.0.1",
                "password": "secret",
                "token": "secret-token",
                "api_key_name": "should-hide",
                "safe": "visible",
            },
        )

    message = caplog.text
    assert "password" not in message
    assert "secret-token" not in message
    assert "api_key_name" not in message
    assert "safe" in message


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_max_attempts():
    calls = {"count": 0}

    @rate_limit(lambda username: username, max_attempts=2, window_seconds=300)
    async def authenticate(username: str):
        calls["count"] += 1
        return AuthenticationResult.failed("invalid_credentials")

    first = await authenticate("alice")
    second = await authenticate("alice")
    third = await authenticate("alice")

    assert first.error == "invalid_credentials"
    assert second.error == "invalid_credentials"
    assert third.error == "rate_limited"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_rate_limit_resets_after_success():
    calls = {"count": 0}

    @rate_limit(lambda username, succeed=False: username, max_attempts=2, window_seconds=300)
    async def authenticate(username: str, succeed: bool = False):
        calls["count"] += 1
        if succeed:
            return AuthenticationResult.successful(User(login=username, authorities=["ROLE_USER"]))
        return AuthenticationResult.failed("invalid_credentials")

    await authenticate("alice")
    success = await authenticate("alice", succeed=True)
    next_attempt = await authenticate("alice")

    assert success.success is True
    assert next_attempt.error == "invalid_credentials"
    assert calls["count"] == 3


def test_rate_limiter_discards_attempts_outside_window():
    limiter = RateLimiter()
    old = datetime.now(UTC) - timedelta(minutes=10)
    limiter._attempts["alice"] = [old, old]

    assert limiter.is_rate_limited("alice", max_attempts=2, window_seconds=60) is False
    assert limiter._attempts["alice"] == []


def test_rate_limiter_reset_clears_recorded_attempts():
    limiter = RateLimiter()
    limiter.record_attempt("alice")
    limiter.record_attempt("alice")

    limiter.reset("alice")

    assert limiter._attempts.get("alice") is None


def test_invalid_security_expression_defaults_to_false_without_execution():
    with SecurityContextManager(User(login="admin", authorities=["ROLE_ADMIN"])):
        assert _evaluate_security_expression("__import__('os').system('echo hacked')") is False
        assert _evaluate_security_expression("hasRole('ADMIN'") is False


@pytest.mark.asyncio
async def test_jwt_generation_does_not_include_secret_like_claims(jwt_auth, auth_user):
    token = await jwt_auth.generate_token(
        auth_user,
        extra_claims={"safe": "yes", "key_material": "hide-me", "credential": "hide-me-too"},
    )

    payload = _decode_without_verification(token.access_token)

    assert payload["safe"] == "yes"
    assert "key_material" not in payload
    assert "credential" not in payload


@pytest.mark.asyncio
async def test_session_remember_me_storage_never_keeps_raw_token(session_auth, auth_user):
    remember_me = await session_auth._create_remember_me_token(auth_user)

    assert remember_me not in session_auth._remember_me_tokens
    assert all(len(key) == 64 for key in session_auth._remember_me_tokens)
