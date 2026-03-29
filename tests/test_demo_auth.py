# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
CI Tests for Demo Authentication - JHipster Style.

Tests cover:
- Demo users: admin/admin, user/user, guest/(no password)
- Dev mode vs Prod mode
- JWT token generation and validation
- Role/authority checking
- CLI login support
"""

import os

import pytest

# Skip demo auth tests if optional JWT dependency is not installed
pytest.importorskip("jose")

# Set dev mode for tests
os.environ["MODE"] = "DEV"

from agentic_brain.auth.demo import (
    DemoAuthService,
    cli_login,
    cli_show_hints,
    is_dev_mode,
)


class TestDemoUsers:
    """Test demo user authentication."""

    @pytest.fixture
    def auth_service(self):
        """Create fresh auth service for each test."""
        return DemoAuthService(create_demo_users=True)

    def test_admin_login(self, auth_service):
        """Test admin/admin login."""
        result = auth_service.authenticate("admin", "admin")
        assert result is not None
        assert result.access_token
        assert result.token_type == "Bearer"
        assert result.refresh_token

    def test_user_login(self, auth_service):
        """Test user/user login."""
        result = auth_service.authenticate("user", "user")
        assert result is not None
        assert result.access_token

    def test_guest_login_no_password(self, auth_service):
        """Test guest login with empty password."""
        result = auth_service.authenticate("guest", "")
        assert result is not None
        assert result.access_token

    def test_guest_login_wrong_password_fails(self, auth_service):
        """Guest with wrong password should fail."""
        result = auth_service.authenticate("guest", "wrongpassword")
        assert result is None

    def test_admin_wrong_password_fails(self, auth_service):
        """Admin with wrong password should fail."""
        result = auth_service.authenticate("admin", "wrongpassword")
        assert result is None

    def test_nonexistent_user_fails(self, auth_service):
        """Nonexistent user should fail."""
        result = auth_service.authenticate("nobody", "anything")
        assert result is None


class TestUserAuthorities:
    """Test user roles and authorities."""

    @pytest.fixture
    def auth_service(self):
        return DemoAuthService(create_demo_users=True)

    def test_admin_has_admin_role(self, auth_service):
        """Admin should have ROLE_ADMIN."""
        user = auth_service.get_user("admin")
        assert user is not None
        assert user.has_authority("ROLE_ADMIN")
        assert user.has_role("ADMIN")

    def test_admin_has_user_role(self, auth_service):
        """Admin should also have ROLE_USER."""
        user = auth_service.get_user("admin")
        assert user.has_authority("ROLE_USER")

    def test_user_has_user_role(self, auth_service):
        """User should have ROLE_USER."""
        user = auth_service.get_user("user")
        assert user.has_authority("ROLE_USER")
        assert not user.has_authority("ROLE_ADMIN")

    def test_guest_has_guest_role(self, auth_service):
        """Guest should have ROLE_GUEST."""
        user = auth_service.get_user("guest")
        assert user.has_authority("ROLE_GUEST")
        assert not user.has_authority("ROLE_USER")
        assert not user.has_authority("ROLE_ADMIN")


class TestJWTTokens:
    """Test JWT token generation and validation."""

    @pytest.fixture
    def auth_service(self):
        return DemoAuthService(create_demo_users=True)

    def test_token_contains_user(self, auth_service):
        """Token should resolve to correct user."""
        result = auth_service.authenticate("admin", "admin")
        user = auth_service.get_user_from_token(result.access_token)
        assert user is not None
        assert user.username == "admin"

    def test_token_contains_authorities(self, auth_service):
        """Token should contain user authorities."""
        result = auth_service.authenticate("admin", "admin")
        user = auth_service.get_user_from_token(result.access_token)
        assert "ROLE_ADMIN" in user.authorities

    def test_invalid_token_fails(self, auth_service):
        """Invalid token should return None."""
        user = auth_service.get_user_from_token("invalid-token")
        assert user is None

    def test_refresh_token_works(self, auth_service):
        """Refresh token should generate new access token."""
        result = auth_service.authenticate("user", "user")
        new_result = auth_service.refresh_token(result.refresh_token)
        assert new_result is not None
        assert new_result.access_token


class TestDevMode:
    """Test dev mode vs prod mode behavior."""

    def test_dev_mode_default(self):
        """Default should be dev mode."""
        os.environ["MODE"] = "DEV"
        assert is_dev_mode() is True

    def test_prod_mode_hides_hints(self):
        """Prod mode should hide login hints."""
        os.environ["MODE"] = "PROD"
        service = DemoAuthService()
        hints = service.get_login_hints()
        assert hints is None
        os.environ["MODE"] = "DEV"  # Reset

    def test_dev_mode_shows_hints(self):
        """Dev mode should show login hints."""
        os.environ["MODE"] = "DEV"
        service = DemoAuthService()
        hints = service.get_login_hints()
        assert hints is not None
        assert len(hints.demo_users) == 3

    def test_hints_contain_all_demo_users(self):
        """Hints should contain admin, user, guest."""
        os.environ["MODE"] = "DEV"
        service = DemoAuthService()
        hints = service.get_login_hints()
        usernames = [u["username"] for u in hints.demo_users]
        assert "admin" in usernames
        assert "user" in usernames
        assert "guest" in usernames


class TestCLILogin:
    """Test CLI login functions."""

    def test_cli_login_admin(self):
        """CLI login should return token for admin."""
        token = cli_login("admin", "admin")
        assert token is not None
        assert len(token) > 50  # JWT tokens are long

    def test_cli_login_guest(self):
        """CLI login should work for guest."""
        token = cli_login("guest", "")
        assert token is not None

    def test_cli_login_fails_wrong_password(self):
        """CLI login should fail with wrong password."""
        token = cli_login("admin", "wrong")
        assert token is None

    def test_cli_show_hints_dev_mode(self, capsys):
        """CLI hints should print in dev mode."""
        os.environ["MODE"] = "DEV"
        cli_show_hints()
        captured = capsys.readouterr()
        assert "admin" in captured.out
        assert "user" in captured.out
        assert "guest" in captured.out


class TestUserCreation:
    """Test creating new users."""

    @pytest.fixture
    def auth_service(self):
        return DemoAuthService(create_demo_users=False)

    def test_create_custom_user(self, auth_service):
        """Should be able to create custom users."""
        user = auth_service.create_user(
            username="customuser",
            password="custompass",
            authorities=["ROLE_USER", "ROLE_CUSTOM"],
            email="custom@example.com",
        )
        assert user is not None
        assert user.username == "customuser"
        assert user.has_authority("ROLE_CUSTOM")

    def test_authenticate_custom_user(self, auth_service):
        """Custom user should be able to login."""
        auth_service.create_user(
            username="testuser",
            password="testpass",
            authorities=["ROLE_USER"],
        )
        result = auth_service.authenticate("testuser", "testpass")
        assert result is not None

    def test_duplicate_user_fails(self, auth_service):
        """Creating duplicate user should return None."""
        auth_service.create_user("dup", "pass", ["ROLE_USER"])
        user2 = auth_service.create_user("dup", "pass2", ["ROLE_USER"])
        assert user2 is None


class TestUserModel:
    """Test DemoUser model methods."""

    @pytest.fixture
    def admin_user(self):
        service = DemoAuthService()
        return service.get_user("admin")

    def test_to_dict_no_password(self, admin_user):
        """to_dict should not include password."""
        d = admin_user.to_dict()
        assert "hashed_password" not in d
        assert "password" not in d
        assert d["login"] == "admin"

    def test_has_role_with_prefix(self, admin_user):
        """has_role should work with ROLE_ prefix."""
        assert admin_user.has_role("ROLE_ADMIN")

    def test_has_role_without_prefix(self, admin_user):
        """has_role should work without ROLE_ prefix."""
        assert admin_user.has_role("ADMIN")


# E2E Test for FastAPI Integration
class TestFastAPIRouter:
    """Test FastAPI router integration."""

    @pytest.fixture
    def client(self):
        """Create test client with auth router."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from agentic_brain.auth.demo import DemoAuthService, create_demo_router

        app = FastAPI()
        service = DemoAuthService()
        app.include_router(create_demo_router(service))
        return TestClient(app)

    def test_authenticate_endpoint(self, client):
        """POST /api/authenticate should return token."""
        response = client.post(
            "/api/authenticate",
            json={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "Bearer"

    def test_authenticate_guest(self, client):
        """Guest should authenticate with empty password."""
        response = client.post(
            "/api/authenticate",
            json={"username": "guest", "password": ""},
        )
        assert response.status_code == 200

    def test_authenticate_invalid(self, client):
        """Invalid credentials should return 401."""
        response = client.post(
            "/api/authenticate",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_account_endpoint(self, client):
        """GET /api/account should return user info."""
        # First login
        login_response = client.post(
            "/api/authenticate",
            json={"username": "admin", "password": "admin"},
        )
        token = login_response.json()["access_token"]

        # Then get account
        response = client.get(
            "/api/account",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["login"] == "admin"
        assert "ROLE_ADMIN" in data["authorities"]

    def test_account_no_token(self, client):
        """GET /api/account without token should return 401."""
        response = client.get("/api/account")
        assert response.status_code == 401

    def test_login_hints_dev_mode(self, client):
        """GET /api/login-hints should return hints in dev mode."""
        os.environ["MODE"] = "DEV"
        response = client.get("/api/login-hints")
        assert response.status_code == 200
        data = response.json()
        assert len(data["demo_users"]) == 3

    def test_authorities_endpoint(self, client):
        """GET /api/authorities should return user roles."""
        login_response = client.post(
            "/api/authenticate",
            json={"username": "admin", "password": "admin"},
        )
        token = login_response.json()["access_token"]

        response = client.get(
            "/api/authorities",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "ROLE_ADMIN" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
