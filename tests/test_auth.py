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
Tests for authentication module.

Tests cover:
- API key validation (header and query param)
- JWT token decode and validation
- Auth disabled mode (default)
- Protected endpoints with auth enabled
- Role-based access control
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest


class TestAuthDisabled:
    """Tests for when AUTH_ENABLED=false (default)."""

    @pytest.fixture
    def auth_disabled_env(self, monkeypatch):
        """Ensure auth is disabled."""
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("API_KEYS", "test_key_1,test_key_2")
        monkeypatch.setenv("JWT_SECRET", "test_secret_key")

    @pytest.mark.asyncio
    async def test_optional_auth_returns_unauthenticated(self, auth_disabled_env):
        """When auth disabled, get_optional_auth returns unauthenticated context."""
        from agentic_brain.api.auth import get_optional_auth, is_auth_enabled

        assert not is_auth_enabled()

        context = await get_optional_auth(None, None, None)

        assert not context.authenticated
        assert context.method is None
        assert context.user_id is None

    @pytest.mark.asyncio
    async def test_require_auth_allows_all_when_disabled(self, auth_disabled_env):
        """When auth disabled, require_auth allows all requests."""
        from agentic_brain.api.auth import require_auth

        # Should not raise even with no credentials
        context = await require_auth(None, None, None)

        assert not context.authenticated

    def test_is_auth_enabled_false_by_default(self, monkeypatch):
        """Auth should be disabled by default."""
        monkeypatch.delenv("AUTH_ENABLED", raising=False)

        from agentic_brain.api.auth import is_auth_enabled

        assert not is_auth_enabled()


class TestAuthEnabled:
    """Tests for when AUTH_ENABLED=true."""

    @pytest.fixture
    def auth_enabled_env(self, monkeypatch):
        """Enable auth with test keys."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "valid_key_1,valid_key_2,valid_key_3")
        monkeypatch.setenv("JWT_SECRET", "test_jwt_secret_key_for_testing")
        monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    @pytest.mark.asyncio
    async def test_require_auth_raises_without_credentials(self, auth_enabled_env):
        """When auth enabled, require_auth raises 401 without credentials."""
        from fastapi import HTTPException

        from agentic_brain.api.auth import require_auth

        with pytest.raises(HTTPException) as exc_info:
            await require_auth(None, None, None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail


class TestAPIKeyValidation:
    """Tests for API key authentication."""

    @pytest.fixture
    def api_keys_env(self, monkeypatch):
        """Configure API keys."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "key_alpha,key_beta,key_gamma")

    @pytest.mark.asyncio
    async def test_valid_api_key_in_header(self, api_keys_env):
        """Valid API key in header should authenticate."""
        from agentic_brain.api.auth import get_api_key

        result = await get_api_key("key_alpha", None)

        assert result == "key_alpha"

    @pytest.mark.asyncio
    async def test_valid_api_key_in_query(self, api_keys_env):
        """Valid API key in query param should authenticate."""
        from agentic_brain.api.auth import get_api_key

        result = await get_api_key(None, "key_beta")

        assert result == "key_beta"

    @pytest.mark.asyncio
    async def test_header_takes_priority_over_query(self, api_keys_env):
        """Header API key should take priority over query param."""
        from agentic_brain.api.auth import get_api_key

        result = await get_api_key("key_alpha", "key_beta")

        assert result == "key_alpha"

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_none(self, api_keys_env):
        """Invalid API key should return None."""
        from agentic_brain.api.auth import get_api_key

        result = await get_api_key("invalid_key", None)

        assert result is None

    @pytest.mark.asyncio
    async def test_require_api_key_raises_on_invalid(self, api_keys_env):
        """require_api_key should raise 401 on invalid key."""
        from fastapi import HTTPException

        from agentic_brain.api.auth import require_api_key

        with pytest.raises(HTTPException) as exc_info:
            await require_api_key("invalid_key", None)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_require_api_key_returns_valid_key(self, api_keys_env):
        """require_api_key should return the key when valid."""
        from agentic_brain.api.auth import require_api_key

        result = await require_api_key("key_gamma", None)

        assert result == "key_gamma"

    def test_get_api_keys_parses_comma_separated(self, api_keys_env):
        """get_api_keys should parse comma-separated keys."""
        from agentic_brain.api.auth import get_api_keys

        keys = get_api_keys()

        assert keys == ["key_alpha", "key_beta", "key_gamma"]

    def test_get_api_keys_empty_when_not_set(self, monkeypatch):
        """get_api_keys should return empty list when not set."""
        monkeypatch.delenv("API_KEYS", raising=False)

        from agentic_brain.api.auth import get_api_keys

        keys = get_api_keys()

        assert keys == []


class TestJWTValidation:
    """Tests for JWT token authentication."""

    @pytest.fixture
    def jwt_env(self, monkeypatch):
        """Configure JWT settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("JWT_SECRET", "super_secret_key_for_testing_only")
        monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    def test_create_test_token(self, jwt_env):
        """create_test_token should create a valid token."""
        pytest.importorskip("jose")
        from agentic_brain.api.auth import create_test_token

        token = create_test_token(
            user_id="user_123",
            roles=["user", "admin"],
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_token(self, jwt_env):
        """get_current_user should decode valid token."""
        pytest.importorskip("jose")
        from agentic_brain.api.auth import create_test_token, get_current_user

        token = create_test_token(
            user_id="test_user_456",
            roles=["reader"],
        )

        user = await get_current_user(token)

        assert user is not None
        assert user.user_id == "test_user_456"
        assert user.roles == ["reader"]

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token(self, jwt_env):
        """get_current_user should return None for invalid token."""
        pytest.importorskip("jose")
        from agentic_brain.api.auth import get_current_user

        user = await get_current_user("invalid.jwt.token")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_current_user_with_expired_token(self, jwt_env):
        """get_current_user should return None for expired token."""
        pytest.importorskip("jose")
        from jose import jwt as jose_jwt

        from agentic_brain.api.auth import get_current_user

        # Create expired token
        payload = {
            "sub": "expired_user",
            "roles": [],
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        expired_token = jose_jwt.encode(
            payload,
            "super_secret_key_for_testing_only",
            algorithm="HS256",
        )

        user = await get_current_user(expired_token)

        assert user is None

    @pytest.mark.asyncio
    async def test_require_current_user_raises_on_invalid(self, jwt_env):
        """require_current_user should raise 401 on invalid token."""
        pytest.importorskip("jose")
        from fastapi import HTTPException

        from agentic_brain.api.auth import require_current_user

        with pytest.raises(HTTPException) as exc_info:
            await require_current_user("invalid.token")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, jwt_env):
        """get_current_user should return None when no token."""
        from agentic_brain.api.auth import get_current_user

        user = await get_current_user(None)

        assert user is None


class TestCombinedAuth:
    """Tests for combined API key + JWT auth."""

    @pytest.fixture
    def combined_env(self, monkeypatch):
        """Configure both API keys and JWT."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "api_key_combo")
        monkeypatch.setenv("JWT_SECRET", "jwt_combo_secret")
        monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    @pytest.mark.asyncio
    async def test_jwt_takes_priority_over_api_key(self, combined_env):
        """JWT should be preferred over API key when both valid."""
        pytest.importorskip("jose")
        from agentic_brain.api.auth import create_test_token, get_optional_auth

        token = create_test_token(user_id="jwt_user", roles=["premium"])

        context = await get_optional_auth("api_key_combo", None, token)

        assert context.authenticated
        assert context.method == "jwt"
        assert context.user_id == "jwt_user"

    @pytest.mark.asyncio
    async def test_api_key_used_when_no_jwt(self, combined_env):
        """API key should be used when JWT not provided."""
        from agentic_brain.api.auth import get_optional_auth

        context = await get_optional_auth("api_key_combo", None, None)

        assert context.authenticated
        assert context.method == "api_key"
        assert context.api_key == "api_key_combo"


class TestRoleBasedAccess:
    """Tests for role-based access control."""

    @pytest.fixture
    def rbac_env(self, monkeypatch):
        """Configure for RBAC tests."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "admin_api_key")
        monkeypatch.setenv("JWT_SECRET", "rbac_test_secret")

    @pytest.mark.asyncio
    async def test_require_role_allows_matching_role(self, rbac_env):
        """require_role should allow user with matching role."""
        pytest.importorskip("jose")
        from agentic_brain.api.auth import AuthContext, create_test_token, require_role

        token = create_test_token(user_id="admin_user", roles=["admin", "user"])

        role_checker = require_role("admin")

        # Simulate the dependency injection
        from agentic_brain.api.auth import get_optional_auth

        await get_optional_auth(None, None, token)
        auth_context = AuthContext(
            authenticated=True,
            method="jwt",
            user_id="admin_user",
            roles=["admin", "user"],
        )

        # The role checker should not raise
        result = await role_checker(auth_context)
        assert result.user_id == "admin_user"

    @pytest.mark.asyncio
    async def test_require_role_denies_missing_role(self, rbac_env):
        """require_role should deny user without required role."""
        from fastapi import HTTPException

        from agentic_brain.api.auth import AuthContext, require_role

        role_checker = require_role("superadmin")

        auth_context = AuthContext(
            authenticated=True,
            method="jwt",
            user_id="regular_user",
            roles=["user"],
        )

        with pytest.raises(HTTPException) as exc_info:
            await role_checker(auth_context)

        assert exc_info.value.status_code == 403
        assert "superadmin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_role_allows_api_key(self, rbac_env):
        """require_role should allow API key auth (no role check)."""
        from agentic_brain.api.auth import AuthContext, require_role

        role_checker = require_role("admin")

        # API key auth now requires role configuration
        # Set up API_KEY_ROLES environment variable for the test
        import os

        original_roles = os.environ.get("API_KEY_ROLES", "")
        os.environ["API_KEY_ROLES"] = "admin_api_key:admin,user"

        try:
            auth_context = AuthContext(
                authenticated=True,
                method="api_key",
                api_key="admin_api_key",
                user_id="admin_api_key",  # API key is used as user_id
            )

            # Should not raise - this API key has 'admin' role
            result = await role_checker(auth_context)
            assert result.method == "api_key"
        finally:
            os.environ["API_KEY_ROLES"] = original_roles


class TestAuthModels:
    """Tests for auth data models."""

    def test_token_data_defaults(self):
        """TokenData should have sensible defaults."""
        from agentic_brain.api.auth import TokenData

        data = TokenData(user_id="user_1")

        assert data.user_id == "user_1"
        assert data.roles == []
        assert data.exp is None

    def test_auth_context_defaults(self):
        """AuthContext should have sensible defaults."""
        from agentic_brain.api.auth import AuthContext

        context = AuthContext()

        assert not context.authenticated
        assert context.method is None
        assert context.user_id is None
        assert context.roles == []
        assert context.api_key is None

    def test_auth_context_authenticated(self):
        """AuthContext should store auth info correctly."""
        from agentic_brain.api.auth import AuthContext

        context = AuthContext(
            authenticated=True,
            method="jwt",
            user_id="user_abc",
            roles=["editor", "viewer"],
        )

        assert context.authenticated
        assert context.method == "jwt"
        assert context.user_id == "user_abc"
        assert "editor" in context.roles


class TestConfigurationFunctions:
    """Tests for configuration helper functions."""

    def test_is_auth_enabled_true_values(self, monkeypatch):
        """is_auth_enabled should recognize various true values."""
        from agentic_brain.api.auth import is_auth_enabled

        for value in ["true", "True", "TRUE", "1", "yes", "YES"]:
            monkeypatch.setenv("AUTH_ENABLED", value)
            assert is_auth_enabled(), f"Failed for value: {value}"

    def test_is_auth_enabled_false_values(self, monkeypatch):
        """is_auth_enabled should recognize various false values."""
        from agentic_brain.api.auth import is_auth_enabled

        for value in ["false", "False", "0", "no", "", "random"]:
            monkeypatch.setenv("AUTH_ENABLED", value)
            assert not is_auth_enabled(), f"Failed for value: {value}"

    def test_get_jwt_algorithm_default(self, monkeypatch):
        """get_jwt_algorithm should default to HS256."""
        monkeypatch.delenv("JWT_ALGORITHM", raising=False)

        from agentic_brain.api.auth import get_jwt_algorithm

        assert get_jwt_algorithm() == "HS256"

    def test_get_jwt_algorithm_custom(self, monkeypatch):
        """get_jwt_algorithm should respect custom value."""
        monkeypatch.setenv("JWT_ALGORITHM", "HS512")

        from agentic_brain.api.auth import get_jwt_algorithm

        assert get_jwt_algorithm() == "HS512"


class TestProtectedEndpointsIntegration:
    """Integration tests for protected endpoints."""

    @pytest.fixture
    def test_client_auth_disabled(self, monkeypatch):
        """Create test client with auth disabled."""
        monkeypatch.setenv("AUTH_ENABLED", "false")

        from fastapi.testclient import TestClient

        from agentic_brain.api.server import create_app

        app = create_app()
        return TestClient(app)

    @pytest.fixture
    def test_client_auth_enabled(self, monkeypatch):
        """Create test client with auth enabled."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("API_KEYS", "test_api_key_12345")
        monkeypatch.setenv("JWT_SECRET", "test_secret_for_integration")

        from fastapi.testclient import TestClient

        from agentic_brain.api.server import create_app

        app = create_app()
        return TestClient(app)

    def test_health_always_public(self, test_client_auth_disabled):
        """Health endpoint should always be public."""
        response = test_client_auth_disabled.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_docs_always_public(self, test_client_auth_disabled):
        """Docs endpoint should always be public."""
        response = test_client_auth_disabled.get("/docs")

        # Docs returns HTML
        assert response.status_code == 200

    def test_chat_accessible_when_auth_disabled(self, test_client_auth_disabled):
        """Chat should be accessible when auth disabled."""
        response = test_client_auth_disabled.post(
            "/chat",
            json={"message": "Hello"},
        )

        # Should not get 401
        assert response.status_code != 401
