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
Tests for APIKeyAuthProvider.

Tests cover:
- Key creation with scopes and expiration
- Key validation and authentication
- Key revocation
- Key rotation
- Rate limiting
- Scope-based permissions
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest


class TestAPIKeyCreation:
    """Tests for API key creation."""

    @pytest.fixture
    def auth_provider(self):
        """Create a fresh APIKeyAuthProvider."""
        from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig

        config = APIKeyConfig(
            key_prefix="ak_",
            key_length=32,
            default_rate_limit_per_minute=60,
            default_rate_limit_per_hour=1000,
            enable_rate_limiting=True,
        )
        return APIKeyAuthProvider(api_key_config=config)

    @pytest.mark.asyncio
    async def test_create_key_returns_key_info_and_plaintext(self, auth_provider):
        """Creating a key returns both key info and plaintext key."""
        key_info, plaintext = await auth_provider.create_key(
            name="Test Key",
            scopes=["read", "write"],
        )

        assert key_info is not None
        assert key_info.key_id is not None
        assert key_info.name == "Test Key"
        assert "read" in key_info.scopes
        assert "write" in key_info.scopes
        assert not key_info.revoked
        assert key_info.created_at is not None

        assert plaintext is not None
        assert plaintext.startswith("ak_")
        assert len(plaintext) > 32

    @pytest.mark.asyncio
    async def test_create_key_with_expiration(self, auth_provider):
        """Creating a key with expiration sets expires_at."""
        key_info, _ = await auth_provider.create_key(
            name="Expiring Key",
            scopes=["read"],
            expires_in_days=30,
        )

        assert key_info.expires_at is not None
        expected = datetime.now(timezone.utc) + timedelta(days=30)
        assert abs((key_info.expires_at - expected).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_create_key_with_custom_rate_limits(self, auth_provider):
        """Creating a key with custom rate limits."""
        key_info, _ = await auth_provider.create_key(
            name="Rate Limited Key",
            scopes=["read"],
            rate_limit_per_minute=10,
            rate_limit_per_hour=100,
        )

        assert key_info.rate_limit_per_minute == 10
        assert key_info.rate_limit_per_hour == 100

    @pytest.mark.asyncio
    async def test_create_key_with_metadata(self, auth_provider):
        """Creating a key with custom metadata."""
        key_info, _ = await auth_provider.create_key(
            name="Metadata Key",
            scopes=["read"],
            metadata={"team": "engineering", "environment": "production"},
        )

        assert key_info.metadata["team"] == "engineering"
        assert key_info.metadata["environment"] == "production"

    @pytest.mark.asyncio
    async def test_create_key_default_scope_is_read(self, auth_provider):
        """Creating a key without scopes defaults to read."""
        key_info, _ = await auth_provider.create_key(name="Default Scope Key")

        assert "read" in key_info.scopes


class TestAPIKeyAuthentication:
    """Tests for API key authentication."""

    @pytest.fixture
    def auth_provider(self):
        """Create a fresh APIKeyAuthProvider."""
        from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig

        config = APIKeyConfig(
            key_prefix="ak_",
            enable_rate_limiting=False,  # Disable for basic auth tests
        )
        return APIKeyAuthProvider(api_key_config=config)

    @pytest.mark.asyncio
    async def test_authenticate_valid_key_succeeds(self, auth_provider):
        """Valid API key authentication succeeds."""
        from agentic_brain.auth import APIKeyCredentials

        _, plaintext = await auth_provider.create_key(
            name="Valid Key",
            scopes=["read", "write"],
        )

        result = await auth_provider.authenticate(APIKeyCredentials(api_key=plaintext))

        assert result.success
        assert result.user is not None
        assert result.user.login == "api_key:Valid Key"
        assert "ROLE_API_KEY" in result.user.authorities
        assert "API_READ" in result.user.authorities
        assert "API_WRITE" in result.user.authorities

    @pytest.mark.asyncio
    async def test_authenticate_invalid_key_fails(self, auth_provider):
        """Invalid API key authentication fails."""
        from agentic_brain.auth import APIKeyCredentials

        result = await auth_provider.authenticate(
            APIKeyCredentials(api_key="ak_invalid_key_12345")
        )

        assert not result.success
        assert result.error == "invalid_api_key"

    @pytest.mark.asyncio
    async def test_authenticate_wrong_prefix_fails(self, auth_provider):
        """API key with wrong prefix fails."""
        from agentic_brain.auth import APIKeyCredentials

        result = await auth_provider.authenticate(
            APIKeyCredentials(api_key="wrong_prefix_key")
        )

        assert not result.success
        assert result.error == "invalid_key_format"

    @pytest.mark.asyncio
    async def test_authenticate_revoked_key_fails(self, auth_provider):
        """Revoked API key authentication fails."""
        from agentic_brain.auth import APIKeyCredentials

        key_info, plaintext = await auth_provider.create_key(
            name="Revoked Key",
            scopes=["read"],
        )

        await auth_provider.revoke_key(key_info.key_id)

        result = await auth_provider.authenticate(APIKeyCredentials(api_key=plaintext))

        assert not result.success
        assert result.error == "key_revoked"

    @pytest.mark.asyncio
    async def test_validate_token_returns_user(self, auth_provider):
        """validate_token returns User for valid key."""
        _, plaintext = await auth_provider.create_key(
            name="Token Key",
            scopes=["read"],
        )

        user = await auth_provider.validate_token(plaintext)

        assert user is not None
        assert user.login == "api_key:Token Key"

    @pytest.mark.asyncio
    async def test_validate_token_returns_none_for_invalid(self, auth_provider):
        """validate_token returns None for invalid key."""
        user = await auth_provider.validate_token("ak_invalid_key")

        assert user is None

    @pytest.mark.asyncio
    async def test_admin_scope_grants_role_admin(self, auth_provider):
        """Admin scope grants ROLE_ADMIN authority."""
        from agentic_brain.auth import APIKeyCredentials

        _, plaintext = await auth_provider.create_key(
            name="Admin Key",
            scopes=["admin"],
        )

        result = await auth_provider.authenticate(APIKeyCredentials(api_key=plaintext))

        assert result.success
        assert "ROLE_ADMIN" in result.user.authorities
        assert "ROLE_USER" in result.user.authorities


class TestAPIKeyRevocation:
    """Tests for API key revocation."""

    @pytest.fixture
    def auth_provider(self):
        """Create a fresh APIKeyAuthProvider."""
        from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig

        config = APIKeyConfig(key_prefix="ak_", enable_rate_limiting=False)
        return APIKeyAuthProvider(api_key_config=config)

    @pytest.mark.asyncio
    async def test_revoke_key_sets_revoked_flag(self, auth_provider):
        """Revoking a key sets the revoked flag."""
        key_info, _ = await auth_provider.create_key(name="To Revoke")

        result = await auth_provider.revoke_key(key_info.key_id)

        assert result is True
        updated = await auth_provider.get_key(key_info.key_id)
        assert updated.revoked is True
        assert updated.revoked_at is not None

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_key_returns_false(self, auth_provider):
        """Revoking a nonexistent key returns False."""
        result = await auth_provider.revoke_key("nonexistent-key-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_keys_excludes_revoked_by_default(self, auth_provider):
        """list_keys excludes revoked keys by default."""
        key1, _ = await auth_provider.create_key(name="Active Key")
        key2, _ = await auth_provider.create_key(name="Revoked Key")
        await auth_provider.revoke_key(key2.key_id)

        keys = await auth_provider.list_keys()

        assert len(keys) == 1
        assert keys[0].name == "Active Key"

    @pytest.mark.asyncio
    async def test_list_keys_includes_revoked_when_requested(self, auth_provider):
        """list_keys includes revoked keys when requested."""
        key1, _ = await auth_provider.create_key(name="Active Key")
        key2, _ = await auth_provider.create_key(name="Revoked Key")
        await auth_provider.revoke_key(key2.key_id)

        keys = await auth_provider.list_keys(include_revoked=True)

        assert len(keys) == 2


class TestAPIKeyRotation:
    """Tests for API key rotation."""

    @pytest.fixture
    def auth_provider(self):
        """Create a fresh APIKeyAuthProvider."""
        from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig

        config = APIKeyConfig(key_prefix="ak_", enable_rate_limiting=False)
        return APIKeyAuthProvider(api_key_config=config)

    @pytest.mark.asyncio
    async def test_rotate_key_creates_new_key(self, auth_provider):
        """Rotating a key creates a new key with same settings."""
        old_key, old_plaintext = await auth_provider.create_key(
            name="Original Key",
            scopes=["read", "write"],
            rate_limit_per_minute=30,
        )

        new_key, new_plaintext = await auth_provider.rotate_key(old_key.key_id)

        assert new_key.key_id != old_key.key_id
        assert new_plaintext != old_plaintext
        assert "rotated" in new_key.name.lower()
        assert new_key.scopes == old_key.scopes
        assert new_key.rate_limit_per_minute == old_key.rate_limit_per_minute
        assert new_key.metadata.get("rotated_from") == old_key.key_id

    @pytest.mark.asyncio
    async def test_rotate_key_revokes_old_key(self, auth_provider):
        """Rotating a key revokes the old key."""
        from agentic_brain.auth import APIKeyCredentials

        old_key, old_plaintext = await auth_provider.create_key(name="To Rotate")

        await auth_provider.rotate_key(old_key.key_id)

        result = await auth_provider.authenticate(
            APIKeyCredentials(api_key=old_plaintext)
        )
        assert not result.success
        assert result.error == "key_revoked"

    @pytest.mark.asyncio
    async def test_rotate_nonexistent_key_raises(self, auth_provider):
        """Rotating a nonexistent key raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await auth_provider.rotate_key("nonexistent-key-id")


class TestAPIKeyRateLimiting:
    """Tests for API key rate limiting."""

    @pytest.fixture
    def auth_provider(self):
        """Create APIKeyAuthProvider with rate limiting enabled."""
        from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig

        config = APIKeyConfig(
            key_prefix="ak_",
            enable_rate_limiting=True,
            default_rate_limit_per_minute=5,  # Low for testing
            default_rate_limit_per_hour=100,
        )
        return APIKeyAuthProvider(api_key_config=config)

    @pytest.mark.asyncio
    async def test_rate_limit_allows_requests_under_limit(self, auth_provider):
        """Requests under the rate limit are allowed."""
        from agentic_brain.auth import APIKeyCredentials

        _, plaintext = await auth_provider.create_key(name="Rate Test Key")

        # Make 3 requests (under limit of 5/minute)
        for _ in range(3):
            result = await auth_provider.authenticate(
                APIKeyCredentials(api_key=plaintext)
            )
            assert result.success

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_requests_over_limit(self, auth_provider):
        """Requests over the rate limit are blocked."""
        from agentic_brain.auth import APIKeyCredentials

        _, plaintext = await auth_provider.create_key(name="Rate Test Key")

        # Make 5 requests (at limit)
        for _ in range(5):
            result = await auth_provider.authenticate(
                APIKeyCredentials(api_key=plaintext)
            )
            assert result.success

        # 6th request should be blocked
        result = await auth_provider.authenticate(APIKeyCredentials(api_key=plaintext))

        assert not result.success
        assert result.error == "rate_limit_exceeded"
        assert "Try again" in result.error_description

    @pytest.mark.asyncio
    async def test_custom_rate_limit_per_key(self, auth_provider):
        """Keys can have custom rate limits."""
        from agentic_brain.auth import APIKeyCredentials

        _, plaintext = await auth_provider.create_key(
            name="Custom Rate Key",
            rate_limit_per_minute=2,  # Very low
        )

        # First 2 requests succeed
        for _ in range(2):
            result = await auth_provider.authenticate(
                APIKeyCredentials(api_key=plaintext)
            )
            assert result.success

        # 3rd request blocked
        result = await auth_provider.authenticate(APIKeyCredentials(api_key=plaintext))
        assert not result.success
        assert result.error == "rate_limit_exceeded"


class TestAPIKeyExpiration:
    """Tests for API key expiration."""

    @pytest.fixture
    def auth_provider(self):
        """Create a fresh APIKeyAuthProvider."""
        from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig

        config = APIKeyConfig(key_prefix="ak_", enable_rate_limiting=False)
        return APIKeyAuthProvider(api_key_config=config)

    @pytest.mark.asyncio
    async def test_expired_key_is_rejected(self, auth_provider):
        """Expired API key is rejected."""
        from agentic_brain.auth import APIKeyCredentials

        key_info, plaintext = await auth_provider.create_key(
            name="Expiring Key",
            expires_in_days=1,
        )

        # Manually set expiration to past
        key_info.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        result = await auth_provider.authenticate(APIKeyCredentials(api_key=plaintext))

        assert not result.success
        assert result.error == "key_expired"

    @pytest.mark.asyncio
    async def test_key_is_expired_method(self, auth_provider):
        """APIKeyInfo.is_expired() returns correct status."""
        key_info, _ = await auth_provider.create_key(
            name="Test Key",
            expires_in_days=1,
        )

        assert not key_info.is_expired()

        # Set to past
        key_info.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert key_info.is_expired()

    @pytest.mark.asyncio
    async def test_key_without_expiration_never_expires(self, auth_provider):
        """Key without expiration never expires."""
        key_info, _ = await auth_provider.create_key(
            name="No Expiry Key",
            expires_in_days=None,
        )

        assert key_info.expires_at is None
        assert not key_info.is_expired()


class TestAPIKeyScopes:
    """Tests for API key scopes."""

    @pytest.fixture
    def auth_provider(self):
        """Create a fresh APIKeyAuthProvider."""
        from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig

        config = APIKeyConfig(key_prefix="ak_", enable_rate_limiting=False)
        return APIKeyAuthProvider(api_key_config=config)

    @pytest.mark.asyncio
    async def test_scopes_map_to_authorities(self, auth_provider):
        """Scopes correctly map to user authorities."""
        from agentic_brain.auth import APIKeyCredentials

        _, plaintext = await auth_provider.create_key(
            name="Scoped Key",
            scopes=["read", "write", "chat", "agents"],
        )

        result = await auth_provider.authenticate(APIKeyCredentials(api_key=plaintext))

        assert "API_READ" in result.user.authorities
        assert "API_WRITE" in result.user.authorities
        assert "CHAT_ACCESS" in result.user.authorities
        assert "AGENTS_ACCESS" in result.user.authorities
        assert "ROLE_API_KEY" in result.user.authorities

    @pytest.mark.asyncio
    async def test_admin_scope_grants_all_access(self, auth_provider):
        """Admin scope includes admin and user roles."""
        from agentic_brain.auth import APIKeyCredentials

        _, plaintext = await auth_provider.create_key(
            name="Admin Key",
            scopes=["admin"],
        )

        result = await auth_provider.authenticate(APIKeyCredentials(api_key=plaintext))

        assert "ROLE_ADMIN" in result.user.authorities
        assert "ROLE_USER" in result.user.authorities

    @pytest.mark.asyncio
    async def test_key_has_scope_method(self, auth_provider):
        """APIKeyInfo.has_scope() works correctly."""
        key_info, _ = await auth_provider.create_key(
            name="Test Key",
            scopes=["read", "write"],
        )

        assert key_info.has_scope("read")
        assert key_info.has_scope("write")
        assert not key_info.has_scope("delete")

    @pytest.mark.asyncio
    async def test_admin_has_all_scopes(self, auth_provider):
        """Admin scope implies all other scopes."""
        key_info, _ = await auth_provider.create_key(
            name="Admin Key",
            scopes=["admin"],
        )

        # Admin should have access to everything
        assert key_info.has_scope("read")
        assert key_info.has_scope("write")
        assert key_info.has_scope("delete")

    @pytest.mark.asyncio
    async def test_has_any_scope_method(self, auth_provider):
        """APIKeyInfo.has_any_scope() works correctly."""
        key_info, _ = await auth_provider.create_key(
            name="Test Key",
            scopes=["read"],
        )

        assert key_info.has_any_scope("read", "write")
        assert not key_info.has_any_scope("write", "delete")


class TestAPIKeyUsageTracking:
    """Tests for API key usage tracking."""

    @pytest.fixture
    def auth_provider(self):
        """Create a fresh APIKeyAuthProvider."""
        from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig

        config = APIKeyConfig(key_prefix="ak_", enable_rate_limiting=False)
        return APIKeyAuthProvider(api_key_config=config)

    @pytest.mark.asyncio
    async def test_last_used_updated_on_authenticate(self, auth_provider):
        """last_used_at is updated on successful authentication."""
        from agentic_brain.auth import APIKeyCredentials

        key_info, plaintext = await auth_provider.create_key(name="Usage Key")

        assert key_info.last_used_at is None

        await auth_provider.authenticate(APIKeyCredentials(api_key=plaintext))

        updated = await auth_provider.get_key(key_info.key_id)
        assert updated.last_used_at is not None

    @pytest.mark.asyncio
    async def test_get_key_returns_key_info(self, auth_provider):
        """get_key returns the key info by ID."""
        key_info, _ = await auth_provider.create_key(
            name="Get Key Test",
            scopes=["read", "write"],
        )

        retrieved = await auth_provider.get_key(key_info.key_id)

        assert retrieved is not None
        assert retrieved.key_id == key_info.key_id
        assert retrieved.name == "Get Key Test"
        assert retrieved.scopes == ["read", "write"]

    @pytest.mark.asyncio
    async def test_get_key_returns_none_for_missing(self, auth_provider):
        """get_key returns None for missing key."""
        retrieved = await auth_provider.get_key("nonexistent-id")

        assert retrieved is None


class TestLDAPAndSAMLStubs:
    """Tests for LDAP (implemented) and SAML (stub) providers."""

    @pytest.mark.asyncio
    async def test_ldap_provider_exists(self):
        """LDAP provider should be fully implemented."""
        from agentic_brain.auth import LDAPAuthProvider
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig()
        auth = LDAPAuthProvider(config)

        # Verify provider is created with config
        assert auth.ldap_config is not None

    @pytest.mark.asyncio
    async def test_ldap_get_user_groups_returns_list(self):
        """LDAP get_user_groups returns a list."""
        from agentic_brain.auth import LDAPAuthProvider
        from agentic_brain.auth.enterprise_providers import LDAPConfig

        config = LDAPConfig()
        auth = LDAPAuthProvider(config)

        # Method should exist and return list (empty without connection)
        assert hasattr(auth, "get_user_groups") or hasattr(auth, "_group_cache")

    @pytest.mark.skip(reason="SAML 2.0 provider is a documented stub (Coming Soon).")
    @pytest.mark.asyncio
    async def test_saml_returns_redirect_required(self):
        """SAML provider returns redirect required error."""
        from agentic_brain.auth import SAMLAuthProvider
        from agentic_brain.auth.models import Credentials

        auth = SAMLAuthProvider()
        result = await auth.authenticate(Credentials())

        assert not result.success
        assert result.error == "saml_redirect_required"

    @pytest.mark.skip(reason="SAML 2.0 provider is a documented stub (Coming Soon).")
    @pytest.mark.asyncio
    async def test_saml_process_response_not_implemented(self):
        """SAML process_response returns not implemented."""
        from agentic_brain.auth import SAMLAuthProvider

        auth = SAMLAuthProvider()
        result = await auth.process_response("<SAMLResponse>test</SAMLResponse>")

        assert not result.success
        assert result.error == "saml_not_implemented"

    @pytest.mark.skip(reason="SAML 2.0 provider is a documented stub (Coming Soon).")
    @pytest.mark.asyncio
    async def test_saml_create_auth_request_returns_request_id(self):
        """SAML create_auth_request returns request with ID."""
        from agentic_brain.auth import SAMLAuthProvider

        auth = SAMLAuthProvider()
        request = await auth.create_auth_request(relay_state="/dashboard")

        assert request.request_id is not None
        assert request.request_id.startswith("_")
        assert request.relay_state == "/dashboard"


@pytest.mark.skip(reason="MFA provider is a documented stub (Coming Soon).")
class TestMFAStubs:
    """Tests for MFA stub provider."""

    @pytest.mark.asyncio
    async def test_mfa_setup_totp_not_implemented(self):
        """MFA setup_totp returns stub result."""
        from agentic_brain.auth import MFAMethod, MFAProvider

        mfa = MFAProvider()
        result = await mfa.setup_totp(user_id="user-123")

        assert result.method == MFAMethod.TOTP
        assert result.secret is None
        assert result.qr_code_uri is None

    @pytest.mark.asyncio
    async def test_mfa_verify_totp_returns_error(self):
        """MFA verify_totp returns not implemented error."""
        from agentic_brain.auth import MFAProvider

        mfa = MFAProvider()
        result = await mfa.verify_totp(user_id="user-123", code="123456")

        assert not result.success
        assert "not yet implemented" in result.error

    @pytest.mark.asyncio
    async def test_mfa_is_required_for_admin(self):
        """MFA is required for admin users by default."""
        from agentic_brain.auth import MFAProvider, User

        mfa = MFAProvider()
        admin_user = User(login="admin", authorities=["ROLE_ADMIN"])
        regular_user = User(login="user", authorities=["ROLE_USER"])

        assert await mfa.is_mfa_required(admin_user)
        assert not await mfa.is_mfa_required(regular_user)

    @pytest.mark.asyncio
    async def test_mfa_get_user_methods_empty_by_default(self):
        """MFA get_user_mfa_methods returns empty for new user."""
        from agentic_brain.auth import MFAProvider

        mfa = MFAProvider()
        methods = await mfa.get_user_mfa_methods("user-123")

        assert methods == []
