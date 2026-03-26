# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Security/authentication tests for CI coverage.

Covers:
- JWT token validation (issuer/audience mismatch)
- API key authentication provider
- Session management (remember-me, cleanup)
- Rate limiting utility
- Input validation for API keys
- OAuth2 security (state + PKCE)
- SAML (stubbed; skipped)
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest


class TestJwtValidation:
    """JWT validation tests for issuer/audience checks."""

    @pytest.fixture
    def jwt_env(self, monkeypatch):
        """Configure JWT settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-unit-tests-12345678")
        monkeypatch.setenv("JWT_ALGORITHM", "HS256")
        monkeypatch.setenv("JWT_ISSUER", "issuer-a")
        monkeypatch.setenv("JWT_AUDIENCE", "audience-a")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_rejects_wrong_audience(self, jwt_env):
        """JWTAuth should reject tokens with wrong audience."""
        from agentic_brain.auth import JWTAuth, User

        auth = JWTAuth()
        token = await auth.generate_token(
            User(login="testuser", authorities=["ROLE_USER"])
        )

        # Change expected audience so validation should fail
        auth.config.jwt.audience = "audience-b"

        result = await auth.validate_token(token.access_token)
        assert result is None

    @pytest.mark.asyncio
    async def test_rejects_wrong_issuer(self, jwt_env):
        """JWTAuth should reject tokens with wrong issuer."""
        from agentic_brain.auth import JWTAuth, User

        auth = JWTAuth()
        token = await auth.generate_token(
            User(login="testuser", authorities=["ROLE_USER"])
        )

        # Change expected issuer so validation should fail
        auth.config.jwt.issuer = "issuer-b"

        result = await auth.validate_token(token.access_token)
        assert result is None


class TestApiKeyAuthProvider:
    """API key provider tests."""

    @pytest.fixture
    def api_key_env(self, monkeypatch):
        """Configure API key settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "alpha-key,bravo-key")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_api_key_auth_success(self, api_key_env):
        """ApiKeyAuth should authenticate a valid key."""
        from agentic_brain.auth.models import ApiKeyCredentials, AuthMethod
        from agentic_brain.auth.providers import ApiKeyAuth

        auth = ApiKeyAuth()
        result = await auth.authenticate(ApiKeyCredentials(api_key="alpha-key"))

        assert result.success is True
        assert result.auth_method == AuthMethod.API_KEY
        assert result.user is not None
        assert result.user.login == "api"
        assert result.token is not None
        assert result.token.token_type == "ApiKey"

    @pytest.mark.asyncio
    async def test_api_key_auth_failure(self, api_key_env):
        """ApiKeyAuth should reject invalid keys."""
        from agentic_brain.auth.models import ApiKeyCredentials
        from agentic_brain.auth.providers import ApiKeyAuth

        auth = ApiKeyAuth()
        result = await auth.authenticate(ApiKeyCredentials(api_key="invalid-key"))

        assert result.success is False
        assert result.user is None


class TestSessionManagement:
    """Session management tests (remember-me + cleanup)."""

    @pytest.fixture
    def session_env(self, monkeypatch):
        """Configure session settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("SESSION_AUTH_ENABLED", "true")
        monkeypatch.setenv("SESSION_TIMEOUT_SECONDS", "3600")
        monkeypatch.setenv("REMEMBER_ME_ENABLED", "true")
        monkeypatch.setenv("REMEMBER_ME_KEY", "test-remember-me-key")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_remember_me_creates_new_session(self, session_env):
        """Remember-me token should authenticate and create new session."""
        from agentic_brain.auth.models import (
            SessionCredentials,
            UsernamePasswordCredentials,
        )
        from agentic_brain.auth.providers import SessionAuth

        auth = SessionAuth()

        initial = await auth.authenticate(
            UsernamePasswordCredentials(
                username="user", password="pw", remember_me=True
            )
        )
        assert initial.success is True
        assert initial.token is not None
        assert initial.token.refresh_token is not None

        # Use remember-me token when session id is invalid
        result = await auth.authenticate(
            SessionCredentials(
                session_id="invalid-session",
                remember_me_token=initial.token.refresh_token,
            )
        )

        assert result.success is True
        assert result.token is not None
        assert result.token.access_token != initial.token.access_token

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_env):
        """Expired sessions should be cleaned up."""
        from agentic_brain.auth import User
        from agentic_brain.auth.providers import SessionAuth

        auth = SessionAuth()
        session_id = await auth.create_session(
            User(login="expired-user", authorities=["ROLE_USER"])
        )

        # Force expiry
        auth._sessions[session_id]["expires_at"] = datetime.now(UTC) - timedelta(
            seconds=1
        )

        removed = await auth.cleanup_expired()

        assert removed == 1
        assert await auth.validate_token(session_id) is None


class TestRateLimiting:
    """Rate limiter utility tests."""

    def test_rate_limiter_blocks_after_limit(self):
        """RateLimiter should block when attempts exceed max_attempts."""
        from agentic_brain.auth.providers import RateLimiter

        limiter = RateLimiter()
        key = "limit-user"

        for _ in range(3):
            limiter.record_attempt(key)

        assert limiter.is_rate_limited(key, max_attempts=3, window_seconds=60) is True
        assert (
            limiter.is_rate_limited("other-user", max_attempts=3, window_seconds=60)
            is False
        )


class TestInputValidation:
    """Input validation tests for API keys."""

    def test_api_key_validation_rejects_empty(self, monkeypatch):
        """Empty or whitespace-only API keys should be rejected."""
        monkeypatch.setenv("API_KEYS", "alpha-key")

        from agentic_brain.auth.config import AuthConfig, reset_auth_config

        reset_auth_config()
        config = AuthConfig()

        assert config.validate_api_key("") is False
        assert config.validate_api_key(" ") is False


class TestOAuth2Security:
    """OAuth2 security tests (state + PKCE storage)."""

    @pytest.fixture
    def oauth_env(self, monkeypatch):
        """Configure OAuth2 settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("OAUTH2_ENABLED", "true")
        monkeypatch.setenv("OAUTH2_CLIENT_ID", "test-client")
        monkeypatch.setenv("OAUTH2_ISSUER_URI", "https://auth.example.com")
        monkeypatch.setenv(
            "OAUTH2_AUTHORIZATION_URI", "https://auth.example.com/authorize"
        )

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    def test_state_contains_pkce_verifier(self, oauth_env):
        """PKCE should store code_verifier in pending state data."""
        from agentic_brain.auth.providers import OAuth2Auth

        auth = OAuth2Auth()
        _url, state, code_verifier = auth.generate_authorization_url(
            "http://localhost/callback", use_pkce=True
        )

        assert code_verifier is not None

        state_data = auth.validate_state(state)
        assert state_data is not None
        assert state_data.get("code_verifier") == code_verifier


class TestSAMLStub:
    """SAML is stubbed - tests are skipped until implemented."""

    @pytest.mark.skip(reason="Not implemented")
    def test_saml_authentication_stub(self):
        pass
