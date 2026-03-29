# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

pytestmark = pytest.mark.requires_firebase

# Import the class to test (assuming it's available via auth package)
from agentic_brain.auth import FirebaseAuthProvider
from agentic_brain.auth.models import TokenCredentials, User
from agentic_brain.exceptions import AuthenticationError


class TestFirebaseAuth:
    """Test Firebase authentication provider"""

    def test_firebase_provider_exists(self):
        """Firebase provider should be importable"""
        # We can check if it's in the auth package
        import agentic_brain.auth

        assert hasattr(agentic_brain.auth, "FirebaseAuthProvider")

    def test_firebase_init(self):
        """Test Firebase provider initialization"""
        config = {"firebase_project_id": "test-project"}
        with patch("firebase_admin.initialize_app") as mock_init:
            with patch(
                "firebase_admin.get_app", side_effect=ValueError
            ):  # Simulate app not existing
                provider = FirebaseAuthProvider(config)
                mock_init.assert_called_once()
                assert provider.config == config

    @patch("agentic_brain.auth.firebase_provider.firebase_auth")
    def test_firebase_verify_token(self, mock_auth):
        """Test Firebase token verification"""
        # Mock the verify_id_token response
        mock_auth.verify_id_token.return_value = {
            "uid": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "http://example.com/pic.jpg",
        }

        provider = FirebaseAuthProvider({})
        # Ensure app is mocked/set
        provider._app = MagicMock()

        credentials = TokenCredentials(token="valid-token")

        # We need to run async test
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(provider.authenticate(credentials))

        assert result.success
        assert result.user.id == "test-user-123"
        assert result.user.email == "test@example.com"
        assert result.user.first_name == "Test"
        loop.close()

    @patch("agentic_brain.auth.firebase_provider.firebase_auth")
    def test_firebase_invalid_token(self, mock_auth):
        """Test handling of invalid Firebase token"""
        mock_auth.verify_id_token.side_effect = ValueError("Invalid token")

        provider = FirebaseAuthProvider({})
        provider._app = MagicMock()

        credentials = TokenCredentials(token="invalid-token")

        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with pytest.raises(AuthenticationError) as excinfo:
            loop.run_until_complete(provider.authenticate(credentials))

        assert "Invalid authentication token" in str(excinfo.value)
        loop.close()

    @patch("agentic_brain.auth.firebase_provider.firebase_auth")
    def test_firebase_expired_token(self, mock_auth):
        """Test handling of expired token"""
        # Firebase raises generic exceptions or ValueError usually, usually ExpiredIdTokenError
        # But for mock we can simulate Exception
        mock_auth.verify_id_token.side_effect = Exception("Token expired")

        provider = FirebaseAuthProvider({})
        provider._app = MagicMock()

        credentials = TokenCredentials(token="expired-token")

        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with pytest.raises(AuthenticationError):
            loop.run_until_complete(provider.authenticate(credentials))
        loop.close()

    def test_firebase_without_credentials(self):
        """Test graceful handling when credentials missing"""
        # If credentials file is missing and no default credentials, it might fail or warn
        # But here we test passing empty config
        with patch("firebase_admin.initialize_app") as mock_init:
            with patch("firebase_admin.get_app", side_effect=ValueError):
                FirebaseAuthProvider({})
                # Should use default credentials (no specific cred file passed)
                mock_init.assert_called()


class TestFirebaseIntegration:
    """Integration tests for Firebase (mocked)"""

    @pytest.mark.skipif(True, reason="Requires Firebase credentials")
    def test_firebase_real_auth(self):
        """Real Firebase auth test"""
        pass
