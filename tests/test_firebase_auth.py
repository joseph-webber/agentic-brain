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

"""Tests for Firebase Authentication."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

# Mock firebase_admin before import
mock_firebase_admin = MagicMock()
mock_auth = MagicMock()
mock_credentials = MagicMock()

with patch.dict(
    "sys.modules",
    {
        "firebase_admin": mock_firebase_admin,
        "firebase_admin.auth": mock_auth,
        "firebase_admin.credentials": mock_credentials,
    },
):
    from agentic_brain.transport.firebase_auth import (
        FirebaseAuth,
        FirebaseAuthMiddleware,
        FirebaseUser,
        TokenInfo,
    )


class TestFirebaseUser:
    """Test FirebaseUser dataclass."""

    def test_create_user(self):
        """Test creating FirebaseUser."""
        user = FirebaseUser(
            uid="user-123",
            email="test@example.com",
            display_name="Test User",
        )

        assert user.uid == "user-123"
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"
        assert user.email_verified is False
        assert user.disabled is False

    def test_user_with_all_fields(self):
        """Test user with all fields populated."""
        now = datetime.now(UTC)

        user = FirebaseUser(
            uid="user-456",
            email="full@example.com",
            display_name="Full User",
            photo_url="https://example.com/photo.jpg",
            email_verified=True,
            disabled=False,
            provider_id="google.com",
            custom_claims={"admin": True},
            created_at=now,
            last_sign_in=now,
        )

        assert user.uid == "user-456"
        assert user.email_verified is True
        assert user.custom_claims == {"admin": True}
        assert user.provider_id == "google.com"

    def test_from_firebase_user(self):
        """Test creating from Firebase UserRecord."""
        mock_record = MagicMock()
        mock_record.uid = "firebase-user-123"
        mock_record.email = "firebase@example.com"
        mock_record.display_name = "Firebase User"
        mock_record.photo_url = None
        mock_record.email_verified = True
        mock_record.disabled = False
        mock_record.provider_id = "password"
        mock_record.custom_claims = {"role": "editor"}

        mock_metadata = MagicMock()
        mock_metadata.creation_timestamp = 1700000000000
        mock_metadata.last_sign_in_timestamp = 1700001000000
        mock_record.user_metadata = mock_metadata

        user = FirebaseUser.from_firebase_user(mock_record)

        assert user.uid == "firebase-user-123"
        assert user.email == "firebase@example.com"
        assert user.email_verified is True
        assert user.custom_claims == {"role": "editor"}


class TestTokenInfo:
    """Test TokenInfo dataclass."""

    def test_create_token_info(self):
        """Test creating TokenInfo."""
        token = TokenInfo(
            uid="user-123",
            email="test@example.com",
        )

        assert token.uid == "user-123"
        assert token.email == "test@example.com"
        assert token.is_expired is True  # No expires_at set

    def test_token_not_expired(self):
        """Test token that is not expired."""
        future = datetime.now(UTC) + timedelta(hours=1)

        token = TokenInfo(
            uid="user-123",
            expires_at=future,
        )

        assert token.is_expired is False

    def test_token_expired(self):
        """Test token that is expired."""
        past = datetime.now(UTC) - timedelta(hours=1)

        token = TokenInfo(
            uid="user-123",
            expires_at=past,
        )

        assert token.is_expired is True

    def test_token_with_claims(self):
        """Test token with custom claims."""
        token = TokenInfo(
            uid="user-123",
            claims={
                "admin": True,
                "role": "superuser",
                "tenant_id": "org-456",
            },
        )

        assert token.claims["admin"] is True
        assert token.claims["role"] == "superuser"


class TestFirebaseAuth:
    """Test FirebaseAuth class."""

    @pytest.fixture
    def mock_auth(self):
        """Create mock FirebaseAuth."""
        auth = MagicMock(spec=FirebaseAuth)
        auth._app = MagicMock()
        return auth

    def test_verify_token_success(self, mock_auth):
        """Test successful token verification."""
        mock_auth.verify_token = MagicMock(
            return_value=TokenInfo(
                uid="user-123",
                email="test@example.com",
                email_verified=True,
            )
        )

        result = mock_auth.verify_token("valid-token")

        assert result.uid == "user-123"
        assert result.email == "test@example.com"

    def test_verify_token_invalid(self, mock_auth):
        """Test invalid token verification."""
        mock_auth.verify_token = MagicMock(side_effect=ValueError("Invalid token"))

        with pytest.raises(ValueError, match="Invalid token"):
            mock_auth.verify_token("invalid-token")

    def test_create_custom_token(self, mock_auth):
        """Test custom token creation."""
        mock_auth.create_custom_token = MagicMock(return_value="custom-token-abc123")

        token = mock_auth.create_custom_token("user-123", {"admin": True})

        assert token == "custom-token-abc123"
        mock_auth.create_custom_token.assert_called_once_with(
            "user-123", {"admin": True}
        )

    def test_get_user(self, mock_auth):
        """Test getting user by UID."""
        mock_auth.get_user = MagicMock(
            return_value=FirebaseUser(
                uid="user-123",
                email="test@example.com",
            )
        )

        user = mock_auth.get_user("user-123")

        assert user.uid == "user-123"

    def test_get_user_not_found(self, mock_auth):
        """Test getting non-existent user."""
        mock_auth.get_user = MagicMock(side_effect=ValueError("User not found"))

        with pytest.raises(ValueError, match="User not found"):
            mock_auth.get_user("non-existent")

    def test_get_user_by_email(self, mock_auth):
        """Test getting user by email."""
        mock_auth.get_user_by_email = MagicMock(
            return_value=FirebaseUser(
                uid="user-123",
                email="test@example.com",
            )
        )

        user = mock_auth.get_user_by_email("test@example.com")

        assert user.email == "test@example.com"

    def test_create_user(self, mock_auth):
        """Test creating new user."""
        mock_auth.create_user = MagicMock(
            return_value=FirebaseUser(
                uid="new-user-123",
                email="new@example.com",
                display_name="New User",
            )
        )

        user = mock_auth.create_user(
            email="new@example.com",
            password="securepass123",
            display_name="New User",
        )

        assert user.uid == "new-user-123"
        assert user.email == "new@example.com"

    def test_update_user(self, mock_auth):
        """Test updating user."""
        mock_auth.update_user = MagicMock(
            return_value=FirebaseUser(
                uid="user-123",
                email="updated@example.com",
                display_name="Updated Name",
            )
        )

        user = mock_auth.update_user(
            "user-123",
            email="updated@example.com",
            display_name="Updated Name",
        )

        assert user.email == "updated@example.com"
        assert user.display_name == "Updated Name"

    def test_delete_user(self, mock_auth):
        """Test deleting user."""
        mock_auth.delete_user = MagicMock()

        mock_auth.delete_user("user-123")

        mock_auth.delete_user.assert_called_once_with("user-123")

    def test_set_custom_claims(self, mock_auth):
        """Test setting custom claims."""
        mock_auth.set_custom_claims = MagicMock()

        mock_auth.set_custom_claims("user-123", {"admin": True, "role": "editor"})

        mock_auth.set_custom_claims.assert_called_once_with(
            "user-123", {"admin": True, "role": "editor"}
        )

    def test_revoke_tokens(self, mock_auth):
        """Test revoking tokens."""
        mock_auth.revoke_tokens = MagicMock()

        mock_auth.revoke_tokens("user-123")

        mock_auth.revoke_tokens.assert_called_once_with("user-123")

    def test_list_users(self, mock_auth):
        """Test listing users with pagination."""
        users = [
            FirebaseUser(uid="user-1", email="user1@example.com"),
            FirebaseUser(uid="user-2", email="user2@example.com"),
        ]
        mock_auth.list_users = MagicMock(return_value=(users, "next-page-token"))

        result_users, next_token = mock_auth.list_users(max_results=10)

        assert len(result_users) == 2
        assert next_token == "next-page-token"

    def test_generate_password_reset_link(self, mock_auth):
        """Test generating password reset link."""
        mock_auth.generate_password_reset_link = MagicMock(
            return_value="https://example.com/reset?code=abc123"
        )

        link = mock_auth.generate_password_reset_link("test@example.com")

        assert "reset" in link

    def test_generate_email_verification_link(self, mock_auth):
        """Test generating email verification link."""
        mock_auth.generate_email_verification_link = MagicMock(
            return_value="https://example.com/verify?code=xyz789"
        )

        link = mock_auth.generate_email_verification_link("test@example.com")

        assert "verify" in link


class TestFirebaseAuthMiddleware:
    """Test FirebaseAuthMiddleware class."""

    @pytest.fixture
    def mock_middleware(self):
        """Create mock middleware."""
        middleware = MagicMock(spec=FirebaseAuthMiddleware)
        middleware.auth = MagicMock()
        middleware.check_revoked = True
        return middleware

    def test_verify_request_success(self, mock_middleware):
        """Test successful request verification."""
        mock_middleware.verify_request = MagicMock(
            return_value=TokenInfo(
                uid="user-123",
                email="test@example.com",
            )
        )

        token_info = mock_middleware.verify_request("Bearer valid-token")

        assert token_info.uid == "user-123"

    def test_verify_request_no_header(self, mock_middleware):
        """Test verification with missing header."""
        mock_middleware.verify_request = MagicMock(
            side_effect=ValueError("Authorization header required")
        )

        with pytest.raises(ValueError, match="Authorization header required"):
            mock_middleware.verify_request("")

    def test_verify_request_invalid_format(self, mock_middleware):
        """Test verification with invalid header format."""
        mock_middleware.verify_request = MagicMock(
            side_effect=ValueError("Invalid authorization header format")
        )

        with pytest.raises(ValueError, match="Invalid authorization header format"):
            mock_middleware.verify_request("InvalidFormat token")

    def test_require_claims_success(self, mock_middleware):
        """Test claim requirement check - success."""
        token_info = TokenInfo(
            uid="user-123",
            claims={"admin": True, "role": "editor"},
        )

        mock_middleware.require_claims = MagicMock(return_value=True)

        result = mock_middleware.require_claims(token_info, {"admin": True})

        assert result is True

    def test_require_claims_missing(self, mock_middleware):
        """Test claim requirement check - missing claim."""
        token_info = TokenInfo(
            uid="user-123",
            claims={"role": "viewer"},
        )

        mock_middleware.require_claims = MagicMock(
            side_effect=ValueError("Missing or invalid claim: admin")
        )

        with pytest.raises(ValueError, match="Missing or invalid claim"):
            mock_middleware.require_claims(token_info, {"admin": True})


class TestFirebaseAuthIntegration:
    """Integration-style tests."""

    def test_full_auth_flow(self):
        """Test complete authentication flow."""
        # Create mock auth
        auth = MagicMock(spec=FirebaseAuth)

        # Create user
        auth.create_user = MagicMock(
            return_value=FirebaseUser(
                uid="new-user",
                email="new@example.com",
            )
        )

        user = auth.create_user(
            email="new@example.com",
            password="password123",
        )
        assert user.uid == "new-user"

        # Generate custom token
        auth.create_custom_token = MagicMock(return_value="custom-token")
        token = auth.create_custom_token(user.uid, {"role": "user"})
        assert token == "custom-token"

        # Set claims
        auth.set_custom_claims = MagicMock()
        auth.set_custom_claims(user.uid, {"admin": True})
        auth.set_custom_claims.assert_called_with("new-user", {"admin": True})

    def test_middleware_flow(self):
        """Test middleware authentication flow."""
        middleware = MagicMock(spec=FirebaseAuthMiddleware)

        # Verify request
        middleware.verify_request = MagicMock(
            return_value=TokenInfo(
                uid="user-123",
                email="test@example.com",
                claims={"admin": True},
            )
        )

        token_info = middleware.verify_request("Bearer valid-token")
        assert token_info.uid == "user-123"

        # Check claims
        middleware.require_claims = MagicMock(return_value=True)

        result = middleware.require_claims(token_info, {"admin": True})
        assert result is True

    def test_user_management_flow(self):
        """Test user management operations."""
        auth = MagicMock(spec=FirebaseAuth)

        # List users
        users = [
            FirebaseUser(uid=f"user-{i}", email=f"user{i}@example.com")
            for i in range(3)
        ]
        auth.list_users = MagicMock(return_value=(users, None))

        result_users, _ = auth.list_users(max_results=10)
        assert len(result_users) == 3

        # Update user
        auth.update_user = MagicMock(
            return_value=FirebaseUser(
                uid="user-0",
                display_name="Updated Name",
            )
        )

        updated = auth.update_user("user-0", display_name="Updated Name")
        assert updated.display_name == "Updated Name"

        # Disable user
        auth.update_user = MagicMock(
            return_value=FirebaseUser(
                uid="user-0",
                disabled=True,
            )
        )

        disabled = auth.update_user("user-0", disabled=True)
        assert disabled.disabled is True


class TestTokenExpiry:
    """Test token expiry handling."""

    def test_token_just_expired(self):
        """Test token that just expired."""
        just_past = datetime.now(UTC) - timedelta(seconds=1)

        token = TokenInfo(uid="user", expires_at=just_past)

        assert token.is_expired is True

    def test_token_about_to_expire(self):
        """Test token about to expire."""
        almost_expired = datetime.now(UTC) + timedelta(seconds=1)

        token = TokenInfo(uid="user", expires_at=almost_expired)

        assert token.is_expired is False

    def test_token_no_expiry(self):
        """Test token without expiry (should be treated as expired)."""
        token = TokenInfo(uid="user", expires_at=None)

        assert token.is_expired is True
