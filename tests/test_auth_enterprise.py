# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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
Comprehensive tests for the enterprise authentication module.

Tests cover:
- JWT authentication (token generation, validation, revocation)
- OAuth2 authentication (claim mapping, JWKS)
- Basic authentication (credential validation)
- Session authentication (session management, remember-me)
- Authorization decorators (roles, authorities)
- Security context (thread-local, async context)
- Configuration (env vars, defaults)
"""

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestJWTAuth:
    """Tests for JWT authentication provider."""

    @pytest.fixture
    def jwt_config(self, monkeypatch):
        """Configure JWT settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-unit-tests-12345678")
        monkeypatch.setenv("JWT_ALGORITHM", "HS256")
        monkeypatch.setenv("JWT_TOKEN_VALIDITY_SECONDS", "3600")
        monkeypatch.setenv("JWT_ISSUER", "test-issuer")
        monkeypatch.setenv("JWT_AUDIENCE", "test-audience")

        # Reset config
        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_generate_token_creates_valid_jwt(self, jwt_config):
        """JWTAuth should generate valid JWT tokens."""
        from agentic_brain.auth import JWTAuth, User

        auth = JWTAuth()
        user = User(login="testuser", authorities=["ROLE_USER", "ROLE_ADMIN"])

        token = await auth.generate_token(user)

        assert token is not None
        assert token.access_token is not None
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600
        assert token.subject == "testuser"

    @pytest.mark.asyncio
    async def test_validate_token_returns_user(self, jwt_config):
        """JWTAuth should validate tokens and return user."""
        from agentic_brain.auth import JWTAuth, User

        auth = JWTAuth()
        user = User(
            id="user-123",
            login="testuser",
            email="test@example.com",
            authorities=["ROLE_USER"],
        )

        token = await auth.generate_token(user)
        validated_user = await auth.validate_token(token.access_token)

        assert validated_user is not None
        assert validated_user.login == "testuser"
        assert validated_user.email == "test@example.com"
        assert "ROLE_USER" in validated_user.authorities

    @pytest.mark.asyncio
    async def test_validate_invalid_token_returns_none(self, jwt_config):
        """JWTAuth should return None for invalid tokens."""
        from agentic_brain.auth import JWTAuth

        auth = JWTAuth()

        result = await auth.validate_token("invalid.jwt.token")

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_expired_token_returns_none(self, jwt_config, monkeypatch):
        """JWTAuth should return None for expired tokens."""
        monkeypatch.setenv("JWT_TOKEN_VALIDITY_SECONDS", "1")

        from agentic_brain.auth import JWTAuth, User
        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

        auth = JWTAuth()
        user = User(login="testuser", authorities=["ROLE_USER"])

        token = await auth.generate_token(user)

        # Wait for token to expire
        await asyncio.sleep(2)

        result = await auth.validate_token(token.access_token)

        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_token_prevents_validation(self, jwt_config):
        """JWTAuth should prevent validation of revoked tokens."""
        from agentic_brain.auth import JWTAuth, User

        auth = JWTAuth()
        user = User(login="testuser", authorities=["ROLE_USER"])

        token = await auth.generate_token(user)

        # Revoke the token
        revoked = await auth.revoke_token(token.access_token)
        assert revoked is True

        # Validation should fail
        result = await auth.validate_token(token.access_token)
        assert result is None

    @pytest.mark.asyncio
    async def test_remember_me_extends_expiry(self, jwt_config, monkeypatch):
        """JWTAuth should use longer expiry for remember-me tokens."""
        monkeypatch.setenv("JWT_TOKEN_VALIDITY_SECONDS", "3600")
        monkeypatch.setenv("JWT_REMEMBER_ME_VALIDITY_SECONDS", "604800")

        from agentic_brain.auth import JWTAuth, User
        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

        auth = JWTAuth()
        user = User(login="testuser", authorities=["ROLE_USER"])

        normal_token = await auth.generate_token(user, remember_me=False)
        remember_me_token = await auth.generate_token(user, remember_me=True)

        assert normal_token.expires_in == 3600
        assert remember_me_token.expires_in == 604800


class TestOAuth2Auth:
    """Tests for OAuth2 authentication provider."""

    @pytest.fixture
    def oauth2_config(self, monkeypatch):
        """Configure OAuth2 settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("OAUTH2_ENABLED", "true")
        monkeypatch.setenv("OAUTH2_ISSUER_URI", "https://auth.example.com")
        monkeypatch.setenv("OAUTH2_CLIENT_ID", "test-client")
        monkeypatch.setenv("OAUTH2_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("OAUTH2_AUDIENCE", "test-audience")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    def test_claim_mapping_default(self, oauth2_config):
        """OAuth2Auth should have default claim mappings."""
        from agentic_brain.auth import OAuth2Auth

        auth = OAuth2Auth()

        assert auth.config.oauth2.claim_mapping["sub"] == "id"
        assert auth.config.oauth2.claim_mapping["preferred_username"] == "login"
        assert auth.config.oauth2.claim_mapping["email"] == "email"

    def test_map_claims_to_user(self, oauth2_config):
        """OAuth2Auth should map OIDC claims to User object."""
        from agentic_brain.auth import OAuth2Auth

        auth = OAuth2Auth()
        claims = {
            "sub": "user-123",
            "preferred_username": "johndoe",
            "email": "john@example.com",
            "given_name": "John",
            "family_name": "Doe",
            "roles": ["admin", "user"],
        }

        user = auth._map_claims_to_user(claims)

        assert user.id == "user-123"
        assert user.login == "johndoe"
        assert user.email == "john@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert "ROLE_ADMIN" in user.authorities
        assert "ROLE_USER" in user.authorities

    def test_map_claims_defaults_to_role_user(self, oauth2_config):
        """OAuth2Auth should default to ROLE_USER when no roles in claims."""
        from agentic_brain.auth import OAuth2Auth

        auth = OAuth2Auth()
        claims = {"sub": "user-456", "preferred_username": "norolezuser"}

        user = auth._map_claims_to_user(claims)

        assert "ROLE_USER" in user.authorities


class TestBasicAuth:
    """Tests for Basic authentication provider."""

    @pytest.fixture
    def basic_config(self, monkeypatch):
        """Configure Basic auth settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("BASIC_AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "test-api-key-123,another-key-456")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_validate_api_key_as_password(self, basic_config):
        """BasicAuth should accept API key as password."""
        from agentic_brain.auth.providers import BasicAuth

        auth = BasicAuth()

        user = await auth._validate_user("api", "test-api-key-123")

        assert user is not None
        assert user.login == "api"
        assert "ROLE_API" in user.authorities

    @pytest.mark.asyncio
    async def test_reject_invalid_api_key(self, basic_config):
        """BasicAuth should reject invalid API keys."""
        from agentic_brain.auth.providers import BasicAuth

        auth = BasicAuth()

        user = await auth._validate_user("api", "invalid-key")

        assert user is None

    def test_encode_credentials(self, basic_config):
        """BasicAuth should correctly encode credentials."""
        from agentic_brain.auth.providers import BasicAuth

        encoded = BasicAuth.encode_credentials("testuser", "testpass")

        import base64

        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "testuser:testpass"

    @pytest.mark.asyncio
    async def test_validate_encoded_token(self, basic_config):
        """BasicAuth should validate base64 encoded tokens."""
        from agentic_brain.auth.providers import BasicAuth

        auth = BasicAuth()
        encoded = BasicAuth.encode_credentials("api", "test-api-key-123")

        user = await auth.validate_token(encoded)

        assert user is not None
        assert user.login == "api"


class TestSessionAuth:
    """Tests for Session authentication provider."""

    @pytest.fixture
    def session_config(self, monkeypatch):
        """Configure session settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("SESSION_AUTH_ENABLED", "true")
        monkeypatch.setenv("SESSION_TIMEOUT_SECONDS", "3600")
        monkeypatch.setenv("REMEMBER_ME_ENABLED", "true")
        monkeypatch.setenv("REMEMBER_ME_KEY", "test-remember-me-key")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_create_session(self, session_config):
        """SessionAuth should create sessions."""
        from agentic_brain.auth import User
        from agentic_brain.auth.providers import SessionAuth

        auth = SessionAuth()
        user = User(login="testuser", authorities=["ROLE_USER"])

        session_id = await auth.create_session(user)

        assert session_id is not None
        assert len(session_id) > 20

    @pytest.mark.asyncio
    async def test_validate_session(self, session_config):
        """SessionAuth should validate sessions and return user."""
        from agentic_brain.auth import User
        from agentic_brain.auth.providers import SessionAuth

        auth = SessionAuth()
        user = User(login="sessionuser", authorities=["ROLE_ADMIN"])

        session_id = await auth.create_session(user)
        validated_user = await auth.validate_token(session_id)

        assert validated_user is not None
        assert validated_user.login == "sessionuser"
        assert "ROLE_ADMIN" in validated_user.authorities

    @pytest.mark.asyncio
    async def test_revoke_session(self, session_config):
        """SessionAuth should revoke sessions."""
        from agentic_brain.auth import User
        from agentic_brain.auth.providers import SessionAuth

        auth = SessionAuth()
        user = User(login="testuser", authorities=["ROLE_USER"])

        session_id = await auth.create_session(user)

        # Revoke
        revoked = await auth.revoke_token(session_id)
        assert revoked is True

        # Validation should fail
        result = await auth.validate_token(session_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_session_returns_none(self, session_config):
        """SessionAuth should return None for invalid session."""
        from agentic_brain.auth.providers import SessionAuth

        auth = SessionAuth()

        result = await auth.validate_token("nonexistent-session-id")

        assert result is None


class TestSecurityContext:
    """Tests for security context management."""

    def test_set_and_get_context(self):
        """Should set and get security context."""
        from agentic_brain.auth import User
        from agentic_brain.auth.context import (
            clear_security_context,
            current_user,
            get_security_context,
            set_security_context,
        )
        from agentic_brain.auth.models import SecurityContext

        user = User(login="contextuser", authorities=["ROLE_USER"])
        ctx = SecurityContext.from_user(user)

        set_security_context(ctx)
        try:
            assert get_security_context() == ctx
            assert current_user() == user
        finally:
            clear_security_context()

    def test_is_authenticated(self):
        """Should correctly report authentication status."""
        from agentic_brain.auth import User
        from agentic_brain.auth.context import (
            clear_security_context,
            is_authenticated,
            set_security_context,
        )
        from agentic_brain.auth.models import SecurityContext

        # Not authenticated initially
        clear_security_context()
        assert is_authenticated() is False

        # Set context
        user = User(login="testuser", authorities=["ROLE_USER"])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        assert is_authenticated() is True

        clear_security_context()
        assert is_authenticated() is False

    def test_has_authority(self):
        """Should check user authorities."""
        from agentic_brain.auth import User
        from agentic_brain.auth.context import (
            clear_security_context,
            has_any_authority,
            has_authority,
            set_security_context,
        )
        from agentic_brain.auth.models import SecurityContext

        user = User(login="testuser", authorities=["ROLE_USER", "ADMIN"])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        try:
            assert has_authority("ADMIN") is True
            assert has_authority("SUPER_ADMIN") is False
            assert has_any_authority("SUPER_ADMIN", "ADMIN") is True
            assert has_any_authority("SUPER_ADMIN", "OTHER") is False
        finally:
            clear_security_context()

    def test_run_as_user_context_manager(self):
        """Should support running code as different user."""
        from agentic_brain.auth import User
        from agentic_brain.auth.context import (
            clear_security_context,
            current_user,
            run_as_user,
        )

        clear_security_context()

        admin = User(login="admin", authorities=["ROLE_ADMIN"])

        with run_as_user(admin):
            assert current_user() == admin

        # Context should be cleared after
        assert current_user() is None


class TestAuthorizationDecorators:
    """Tests for authorization decorators."""

    @pytest.fixture
    def auth_setup(self, monkeypatch):
        """Set up auth environment."""
        monkeypatch.setenv("AUTH_ENABLED", "true")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_require_role_allows_matching_role(self, auth_setup):
        """@require_role should allow users with matching role."""
        from agentic_brain.auth import User, require_role
        from agentic_brain.auth.context import (
            clear_security_context,
            set_security_context,
        )
        from agentic_brain.auth.models import SecurityContext

        @require_role("ADMIN")
        async def admin_endpoint():
            return "success"

        user = User(login="admin", authorities=["ROLE_ADMIN"])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        try:
            result = await admin_endpoint()
            assert result == "success"
        finally:
            clear_security_context()

    @pytest.mark.asyncio
    async def test_require_role_denies_missing_role(self, auth_setup):
        """@require_role should deny users without required role."""
        from fastapi import HTTPException

        from agentic_brain.auth import User, require_role
        from agentic_brain.auth.context import (
            clear_security_context,
            set_security_context,
        )
        from agentic_brain.auth.models import SecurityContext

        @require_role("ADMIN")
        async def admin_endpoint():
            return "success"

        user = User(login="regular", authorities=["ROLE_USER"])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        try:
            with pytest.raises(HTTPException) as exc_info:
                await admin_endpoint()
            assert exc_info.value.status_code == 403
        finally:
            clear_security_context()

    @pytest.mark.asyncio
    async def test_require_authenticated_allows_any_auth(self, auth_setup):
        """@require_authenticated should allow any authenticated user."""
        from agentic_brain.auth import User, require_authenticated
        from agentic_brain.auth.context import (
            clear_security_context,
            set_security_context,
        )
        from agentic_brain.auth.models import SecurityContext

        @require_authenticated
        async def protected_endpoint():
            return "authenticated"

        user = User(login="anyuser", authorities=[])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        try:
            result = await protected_endpoint()
            assert result == "authenticated"
        finally:
            clear_security_context()

    @pytest.mark.asyncio
    async def test_require_authenticated_denies_unauthenticated(self, auth_setup):
        """@require_authenticated should deny unauthenticated requests."""
        from fastapi import HTTPException

        from agentic_brain.auth import require_authenticated
        from agentic_brain.auth.context import clear_security_context

        @require_authenticated
        async def protected_endpoint():
            return "authenticated"

        clear_security_context()

        with pytest.raises(HTTPException) as exc_info:
            await protected_endpoint()
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_authority_checks_permissions(self, auth_setup):
        """@require_authority should check fine-grained permissions."""
        from fastapi import HTTPException

        from agentic_brain.auth import User, require_authority
        from agentic_brain.auth.context import (
            clear_security_context,
            set_security_context,
        )
        from agentic_brain.auth.models import SecurityContext

        @require_authority("USER_VIEW")
        async def view_users():
            return "users"

        # User with authority
        user = User(login="viewer", authorities=["USER_VIEW"])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        try:
            result = await view_users()
            assert result == "users"
        finally:
            clear_security_context()

        # User without authority
        user2 = User(login="noauth", authorities=["OTHER_PERM"])
        ctx2 = SecurityContext.from_user(user2)
        set_security_context(ctx2)

        try:
            with pytest.raises(HTTPException) as exc_info:
                await view_users()
            assert exc_info.value.status_code == 403
        finally:
            clear_security_context()


class TestAuthConfig:
    """Tests for authentication configuration."""

    def test_default_config_auth_disabled(self, monkeypatch):
        """Auth should be disabled by default."""
        monkeypatch.delenv("AUTH_ENABLED", raising=False)

        from agentic_brain.auth import AuthConfig
        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()
        config = AuthConfig()

        assert config.enabled is False

    def test_jwt_secret_auto_generated(self, monkeypatch):
        """JWT secret should be auto-generated if not provided."""
        monkeypatch.delenv("JWT_SECRET", raising=False)
        monkeypatch.delenv("JWT_BASE64_SECRET", raising=False)

        from agentic_brain.auth.config import JWTConfig, reset_auth_config

        reset_auth_config()
        config = JWTConfig()

        assert config.secret is not None
        assert len(config.secret) >= 32

    def test_api_keys_parsed_from_env(self, monkeypatch):
        """API keys should be parsed from comma-separated env var."""
        monkeypatch.setenv("API_KEYS", "key1,key2,key3")

        from agentic_brain.auth import AuthConfig
        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()
        config = AuthConfig()

        assert config.api_keys == ["key1", "key2", "key3"]

    def test_is_public_path(self, monkeypatch):
        """Should correctly identify public paths."""
        from agentic_brain.auth import AuthConfig
        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()
        config = AuthConfig()

        assert config.is_public_path("/health") is True
        assert config.is_public_path("/health/") is True
        assert config.is_public_path("/docs") is True
        assert config.is_public_path("/api/private") is False


class TestConstants:
    """Tests for authentication constants."""

    def test_role_constants(self):
        """Role constants should have ROLE_ prefix."""
        from agentic_brain.auth.constants import ROLE_ADMIN, ROLE_ANONYMOUS, ROLE_USER

        assert ROLE_ADMIN == "ROLE_ADMIN"
        assert ROLE_USER == "ROLE_USER"
        assert ROLE_ANONYMOUS == "ROLE_ANONYMOUS"

    def test_claim_constants(self):
        """JWT claim constants should be standard."""
        from agentic_brain.auth.constants import (
            CLAIM_AUDIENCE,
            CLAIM_EXPIRATION,
            CLAIM_ISSUER,
            CLAIM_SUBJECT,
        )

        assert CLAIM_SUBJECT == "sub"
        assert CLAIM_EXPIRATION == "exp"
        assert CLAIM_ISSUER == "iss"
        assert CLAIM_AUDIENCE == "aud"


class TestUserModel:
    """Tests for User model."""

    def test_user_has_authority(self):
        """User should check authorities correctly."""
        from agentic_brain.auth import User

        user = User(login="testuser", authorities=["ROLE_USER", "ADMIN", "VIEW"])

        assert user.has_authority("ADMIN") is True
        assert user.has_authority("DELETE") is False

    def test_user_has_role(self):
        """User should check roles with ROLE_ prefix."""
        from agentic_brain.auth import User

        user = User(login="testuser", authorities=["ROLE_ADMIN", "ROLE_USER"])

        assert user.has_role("ADMIN") is True
        assert user.has_role("ROLE_ADMIN") is True
        assert user.has_role("MODERATOR") is False

    def test_user_full_name(self):
        """User should construct full name."""
        from agentic_brain.auth import User

        user1 = User(
            login="johndoe", first_name="John", last_name="Doe", authorities=[]
        )
        user2 = User(login="onlylogin", authorities=[])

        assert user1.full_name == "John Doe"
        assert user2.full_name == "onlylogin"


class TestTokenModel:
    """Tests for Token model."""

    def test_token_is_expired(self):
        """Token should correctly report expiration."""
        from agentic_brain.auth import Token

        # Not expired
        future = datetime.now(UTC) + timedelta(hours=1)
        token1 = Token(access_token="test", expires_at=future)
        assert token1.is_expired is False

        # Expired
        past = datetime.now(UTC) - timedelta(hours=1)
        token2 = Token(access_token="test", expires_at=past)
        assert token2.is_expired is True

        # No expiry set
        token3 = Token(access_token="test")
        assert token3.is_expired is False

    def test_authorization_header(self):
        """Token should format authorization header."""
        from agentic_brain.auth import Token

        token = Token(access_token="abc123", token_type="Bearer")

        assert token.authorization_header == "Bearer abc123"


class TestSecurityExpression:
    """Tests for pre_authorize expression evaluation."""

    def test_evaluate_has_role(self):
        """Should evaluate hasRole expressions."""
        from agentic_brain.auth import User
        from agentic_brain.auth.context import (
            clear_security_context,
            set_security_context,
        )
        from agentic_brain.auth.decorators import _evaluate_security_expression
        from agentic_brain.auth.models import SecurityContext

        user = User(login="testuser", authorities=["ROLE_ADMIN"])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        try:
            assert _evaluate_security_expression("hasRole('ADMIN')") is True
            assert _evaluate_security_expression("hasRole('USER')") is False
        finally:
            clear_security_context()

    def test_evaluate_has_authority(self):
        """Should evaluate hasAuthority expressions."""
        from agentic_brain.auth import User
        from agentic_brain.auth.context import (
            clear_security_context,
            set_security_context,
        )
        from agentic_brain.auth.decorators import _evaluate_security_expression
        from agentic_brain.auth.models import SecurityContext

        user = User(login="testuser", authorities=["VIEW", "EDIT"])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        try:
            assert _evaluate_security_expression("hasAuthority('VIEW')") is True
            assert _evaluate_security_expression("hasAuthority('DELETE')") is False
        finally:
            clear_security_context()

    def test_evaluate_or_expression(self):
        """Should evaluate OR expressions."""
        from agentic_brain.auth import User
        from agentic_brain.auth.context import (
            clear_security_context,
            set_security_context,
        )
        from agentic_brain.auth.decorators import _evaluate_security_expression
        from agentic_brain.auth.models import SecurityContext

        user = User(login="testuser", authorities=["ROLE_USER"])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        try:
            assert (
                _evaluate_security_expression("hasRole('ADMIN') or hasRole('USER')")
                is True
            )
            assert (
                _evaluate_security_expression("hasRole('ADMIN') or hasRole('SUPER')")
                is False
            )
        finally:
            clear_security_context()

    def test_evaluate_and_expression(self):
        """Should evaluate AND expressions."""
        from agentic_brain.auth import User
        from agentic_brain.auth.context import (
            clear_security_context,
            set_security_context,
        )
        from agentic_brain.auth.decorators import _evaluate_security_expression
        from agentic_brain.auth.models import SecurityContext

        user = User(login="testuser", authorities=["ROLE_USER", "ROLE_ADMIN"])
        ctx = SecurityContext.from_user(user)
        set_security_context(ctx)

        try:
            assert (
                _evaluate_security_expression("hasRole('ADMIN') and hasRole('USER')")
                is True
            )
            assert (
                _evaluate_security_expression("hasRole('ADMIN') and hasRole('SUPER')")
                is False
            )
        finally:
            clear_security_context()


class TestApiKeyAuth:
    """Tests for API key authentication."""

    @pytest.fixture
    def api_key_config(self, monkeypatch):
        """Configure API key settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "valid-api-key-1,valid-api-key-2")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_valid_api_key(self, api_key_config):
        """ApiKeyAuth should accept valid API keys."""
        from agentic_brain.auth.models import ApiKeyCredentials
        from agentic_brain.auth.providers import ApiKeyAuth

        auth = ApiKeyAuth()
        creds = ApiKeyCredentials(api_key="valid-api-key-1")

        result = await auth.authenticate(creds)

        assert result.success is True
        assert result.user is not None
        assert result.user.login == "api"

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, api_key_config):
        """ApiKeyAuth should reject invalid API keys."""
        from agentic_brain.auth.models import ApiKeyCredentials
        from agentic_brain.auth.providers import ApiKeyAuth

        auth = ApiKeyAuth()
        creds = ApiKeyCredentials(api_key="invalid-key")

        result = await auth.authenticate(creds)

        assert result.success is False
        assert result.error == "invalid_api_key"


class TestCompositeAuth:
    """Tests for composite authentication."""

    @pytest.fixture
    def composite_config(self, monkeypatch):
        """Configure for composite auth."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        monkeypatch.setenv("API_KEYS", "test-api-key")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_tries_providers_in_order(self, composite_config):
        """CompositeAuth should try providers in order."""
        from agentic_brain.auth.models import ApiKeyCredentials
        from agentic_brain.auth.providers import ApiKeyAuth, CompositeAuth, JWTAuth

        auth = CompositeAuth([JWTAuth(), ApiKeyAuth()])
        creds = ApiKeyCredentials(api_key="test-api-key")

        result = await auth.authenticate(creds)

        # JWT won't work, but ApiKey should
        assert result.success is True
