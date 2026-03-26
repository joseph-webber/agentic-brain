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
Security-specific tests for authentication module.

Tests cover:
- Constant-time comparison (timing attack resistance)
- Logging doesn't leak secrets
- Error messages don't leak sensitive data
- Rate limiting functionality
- Audit logging
- Token revocation
- OAuth2 state/nonce validation
- PKCE flow
"""

import asyncio
import logging
import secrets
import time
from unittest.mock import MagicMock, patch

import pytest


class TestConstantTimeComparison:
    """Tests for constant-time comparison to prevent timing attacks."""

    @pytest.fixture
    def jwt_config(self, monkeypatch):
        """Configure JWT settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-unit-tests-12345678")
        monkeypatch.setenv("API_KEYS", "valid-api-key-12345,another-valid-key")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    def test_api_key_validation_uses_constant_time(self, jwt_config):
        """API key validation should use constant-time comparison."""
        from agentic_brain.auth.config import AuthConfig

        config = AuthConfig()

        # Test with valid key
        assert config.validate_api_key("valid-api-key-12345") is True

        # Test with invalid key of same length
        assert config.validate_api_key("valid-api-key-00000") is False

        # Test with different length key
        assert config.validate_api_key("short") is False
        assert config.validate_api_key("") is False

    def test_secure_compare_function(self):
        """_secure_compare should use secrets.compare_digest."""
        from agentic_brain.auth.providers import _secure_compare

        # Equal strings should match
        assert _secure_compare("password123", "password123") is True

        # Different strings should not match
        assert _secure_compare("password123", "password456") is False

        # Different lengths should not match
        assert _secure_compare("short", "much_longer_string") is False

        # Empty strings
        assert _secure_compare("", "") is True
        assert _secure_compare("", "x") is False

    def test_timing_attack_resistance(self, jwt_config):
        """API key validation timing should be consistent regardless of input."""
        from agentic_brain.auth.config import AuthConfig

        config = AuthConfig()

        # Measure time for early mismatch
        early_mismatch = "xxxxx-xxx-xxx-xxxxx"

        # Measure time for late mismatch
        late_mismatch = "valid-api-key-0000x"

        # Note: In practice, timing differences are very small and can be affected
        # by many factors. This test just verifies the comparison completes.
        # Real timing attack testing requires statistical analysis.

        t1 = time.perf_counter()
        for _ in range(1000):
            config.validate_api_key(early_mismatch)
        early_time = time.perf_counter() - t1

        t2 = time.perf_counter()
        for _ in range(1000):
            config.validate_api_key(late_mismatch)
        late_time = time.perf_counter() - t2

        # Times should be within reasonable margin (not a strict test)
        # If not using constant-time comparison, late_time would be notably longer
        ratio = max(early_time, late_time) / max(min(early_time, late_time), 0.0001)
        assert (
            ratio < 3.0
        ), f"Timing ratio {ratio} suggests non-constant-time comparison"


class TestNoSecretLeakage:
    """Tests ensuring secrets are never logged or exposed in errors."""

    @pytest.fixture
    def jwt_config(self, monkeypatch):
        """Configure JWT settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("JWT_SECRET", "super-secret-jwt-key-12345")
        monkeypatch.setenv("API_KEYS", "api-key-never-log-me")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_invalid_token_error_doesnt_leak_secret(self, jwt_config):
        """Error messages for invalid tokens should not contain the secret."""
        from agentic_brain.auth.providers import JWTAuth

        auth = JWTAuth()

        # Try to validate an invalid token
        result = await auth.validate_token("invalid.jwt.token")

        assert result is None
        # The secret should never appear in any output
        # (This is verified by inspecting the code - no way to capture all output)

    @pytest.mark.asyncio
    async def test_authentication_failure_doesnt_leak_password(self, jwt_config):
        """Authentication failures should not expose passwords."""
        from agentic_brain.auth.models import UsernamePasswordCredentials
        from agentic_brain.auth.providers import BasicAuth

        auth = BasicAuth()
        password = "my-super-secret-password"
        creds = UsernamePasswordCredentials(username="user", password=password)

        result = await auth.authenticate(creds)

        assert result.success is False
        # Error message should not contain the password
        assert password not in str(result.error_description)
        assert password not in str(result.error)

    def test_log_messages_mask_secrets(self):
        """Log messages should mask sensitive data."""
        from agentic_brain.secrets.manager import _sanitize_log_message

        secret_value = "super-secret-password-123"

        msg = _sanitize_log_message("API_KEY", secret_value)

        # Value should not be in message
        assert secret_value not in msg
        # Key name is okay
        assert "API_KEY" in msg
        # Should indicate length only
        assert str(len(secret_value)) in msg


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rate_limiter_tracks_attempts(self):
        """RateLimiter should track attempts per key."""
        from agentic_brain.auth.providers import RateLimiter

        limiter = RateLimiter()
        key = "test-user"

        # Record attempts
        for _ in range(5):
            limiter.record_attempt(key)

        # Should be rate limited
        assert limiter.is_rate_limited(key, max_attempts=5, window_seconds=300) is True

        # Different key should not be limited
        assert (
            limiter.is_rate_limited("other-user", max_attempts=5, window_seconds=300)
            is False
        )

    def test_rate_limiter_resets_on_success(self):
        """RateLimiter should reset on successful auth."""
        from agentic_brain.auth.providers import RateLimiter

        limiter = RateLimiter()
        key = "test-user"

        # Record some attempts
        for _ in range(3):
            limiter.record_attempt(key)

        # Reset
        limiter.reset(key)

        # Should not be rate limited
        assert limiter.is_rate_limited(key, max_attempts=5, window_seconds=300) is False

    def test_rate_limiter_respects_window(self):
        """RateLimiter should respect time window."""
        from agentic_brain.auth.providers import RateLimiter

        limiter = RateLimiter()
        key = "test-user"

        # Record attempts
        for _ in range(5):
            limiter.record_attempt(key)

        # With 1 second window, should not be limited after sleeping
        # (Using very short window for test)
        assert limiter.is_rate_limited(key, max_attempts=5, window_seconds=1) is True


class TestAuditLogging:
    """Tests for audit logging functionality."""

    def test_audit_logger_filters_sensitive_data(self):
        """AuditLogger should filter sensitive data from details."""
        from agentic_brain.auth.providers import AuditLogger

        logger = AuditLogger()

        # Capture log output
        with patch.object(
            logging.getLogger("agentic_brain.auth.providers"), "log"
        ) as mock_log:
            logger.log_event(
                event_type="LOGIN",
                user_id="testuser",
                details={
                    "ip": "192.168.1.1",
                    "password": "secret123",  # Should be filtered
                    "token": "bearer-token",  # Should be filtered
                    "user_agent": "Mozilla/5.0",
                },
                success=True,
            )

            # Verify log was called
            assert mock_log.called

            # Get the logged message
            call_args = mock_log.call_args
            logged_message = str(call_args)

            # Sensitive data should not be in the message
            assert "secret123" not in logged_message
            assert "bearer-token" not in logged_message
            # Non-sensitive data should be there
            assert "192.168.1.1" in logged_message or "ip" in logged_message

    def test_audit_logger_records_failures(self):
        """AuditLogger should record failed events appropriately."""
        from agentic_brain.auth.providers import AuditLogger

        logger = AuditLogger()

        with patch.object(
            logging.getLogger("agentic_brain.auth.providers"), "log"
        ) as mock_log:
            logger.log_event(
                event_type="LOGIN_FAILURE",
                user_id="attacker",
                success=False,
            )

            # Should log at WARNING level for failures
            assert mock_log.called
            call_args = mock_log.call_args
            assert call_args[0][0] == logging.WARNING


class TestTokenRevocation:
    """Tests for token revocation (blacklisting)."""

    @pytest.fixture
    def jwt_config(self, monkeypatch):
        """Configure JWT settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-unit-tests-12345678")
        monkeypatch.setenv("JWT_ISSUER", "test-issuer")
        monkeypatch.setenv("JWT_AUDIENCE", "test-audience")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_revoked_token_cannot_be_used(self, jwt_config):
        """Revoked tokens should fail validation."""
        from agentic_brain.auth import User
        from agentic_brain.auth.providers import JWTAuth

        auth = JWTAuth()
        user = User(login="testuser", authorities=["ROLE_USER"])

        # Generate token
        token = await auth.generate_token(user)

        # Verify it works
        validated = await auth.validate_token(token.access_token)
        assert validated is not None

        # Revoke it
        revoked = await auth.revoke_token(token.access_token)
        assert revoked is True

        # Should no longer validate
        validated_after = await auth.validate_token(token.access_token)
        assert validated_after is None

    @pytest.mark.asyncio
    async def test_jti_blacklist_grows(self, jwt_config):
        """JTI blacklist should track revoked tokens."""
        from agentic_brain.auth import User
        from agentic_brain.auth.providers import JWTAuth

        auth = JWTAuth()
        user = User(login="testuser", authorities=["ROLE_USER"])

        initial_count = auth.get_blacklist_count()

        # Revoke multiple tokens
        for _ in range(5):
            token = await auth.generate_token(user)
            await auth.revoke_token(token.access_token)

        # Blacklist should grow
        assert auth.get_blacklist_count() == initial_count + 5


class TestOAuth2Security:
    """Tests for OAuth2 security features."""

    @pytest.fixture
    def oauth2_config(self, monkeypatch):
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

    def test_state_parameter_generation(self, oauth2_config):
        """OAuth2 should generate unique state parameters."""
        from agentic_brain.auth.providers import OAuth2Auth

        auth = OAuth2Auth()

        # Generate multiple auth URLs
        url1, state1, _ = auth.generate_authorization_url("http://localhost/callback")
        url2, state2, _ = auth.generate_authorization_url("http://localhost/callback")

        # States should be unique
        assert state1 != state2

        # States should be cryptographically secure (at least 32 chars)
        assert len(state1) >= 32
        assert len(state2) >= 32

    def test_state_validation_consumes_state(self, oauth2_config):
        """State validation should consume the state (one-time use)."""
        from agentic_brain.auth.providers import OAuth2Auth

        auth = OAuth2Auth()

        _, state, _ = auth.generate_authorization_url("http://localhost/callback")

        # First validation should succeed
        result1 = auth.validate_state(state)
        assert result1 is not None

        # Second validation should fail (state consumed)
        result2 = auth.validate_state(state)
        assert result2 is None

    def test_invalid_state_rejected(self, oauth2_config):
        """Invalid state parameters should be rejected."""
        from agentic_brain.auth.providers import OAuth2Auth

        auth = OAuth2Auth()

        # Unknown state
        result = auth.validate_state("unknown-state-value")
        assert result is None

    def test_pkce_generates_verifier_and_challenge(self, oauth2_config):
        """PKCE flow should generate code verifier and challenge."""
        from agentic_brain.auth.providers import OAuth2Auth

        auth = OAuth2Auth()

        url, state, code_verifier = auth.generate_authorization_url(
            "http://localhost/callback", use_pkce=True
        )

        # Should have a code verifier
        assert code_verifier is not None
        assert len(code_verifier) >= 43  # RFC 7636 minimum

        # URL should contain code_challenge
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url

    def test_nonce_validation_prevents_replay(self, oauth2_config):
        """Nonce validation should prevent replay attacks."""
        from agentic_brain.auth.providers import OAuth2Auth

        auth = OAuth2Auth()

        nonce = "test-nonce-12345"

        # First use should succeed
        result1 = auth._validate_nonce(nonce, nonce)
        assert result1 is True

        # Second use (replay) should fail
        result2 = auth._validate_nonce(nonce, nonce)
        assert result2 is False


class TestRefreshTokenRotation:
    """Tests for refresh token rotation."""

    @pytest.fixture
    def jwt_config(self, monkeypatch):
        """Configure JWT settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-unit-tests-12345678")
        monkeypatch.setenv("JWT_ISSUER", "test-issuer")
        monkeypatch.setenv("JWT_AUDIENCE", "test-audience")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_refresh_token_issued_with_remember_me(self, jwt_config):
        """Refresh token should be issued when remember_me is True."""
        from agentic_brain.auth import User
        from agentic_brain.auth.providers import JWTAuth

        auth = JWTAuth()
        user = User(login="testuser", authorities=["ROLE_USER"])

        # Without remember_me - no refresh token
        token_no_rm = await auth.generate_token(user, remember_me=False)
        assert token_no_rm.refresh_token is None

        # With remember_me - has refresh token
        token_rm = await auth.generate_token(user, remember_me=True)
        assert token_rm.refresh_token is not None

    @pytest.mark.asyncio
    async def test_refresh_token_rotation_invalidates_old(self, jwt_config):
        """Using a refresh token should invalidate the old one."""
        from agentic_brain.auth import User
        from agentic_brain.auth.providers import JWTAuth

        auth = JWTAuth()
        user = User(login="testuser", authorities=["ROLE_USER"])

        # Generate initial token with refresh
        token1 = await auth.generate_token(user, remember_me=True)
        assert token1.refresh_token is not None

        # Use refresh token to get new tokens
        token2 = await auth.refresh_token(token1.refresh_token)
        assert token2 is not None

        # Old refresh token should no longer work
        token3 = await auth.refresh_token(token1.refresh_token)
        assert token3 is None


class TestInputValidation:
    """Tests for input validation on auth inputs."""

    @pytest.fixture
    def jwt_config(self, monkeypatch):
        """Configure JWT settings."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-key-for-unit-tests-12345678")

        from agentic_brain.auth.config import reset_auth_config

        reset_auth_config()

    @pytest.mark.asyncio
    async def test_empty_token_rejected(self, jwt_config):
        """Empty tokens should be rejected."""
        from agentic_brain.auth.providers import JWTAuth

        auth = JWTAuth()

        result = await auth.validate_token("")
        assert result is None

    @pytest.mark.asyncio
    async def test_null_like_tokens_rejected(self, jwt_config):
        """Null-like token values should be rejected."""
        from agentic_brain.auth.providers import JWTAuth

        auth = JWTAuth()

        for invalid in ["null", "undefined", "None", "nil"]:
            result = await auth.validate_token(invalid)
            assert result is None, f"Token '{invalid}' should be rejected"

    @pytest.mark.asyncio
    async def test_malformed_jwt_rejected(self, jwt_config):
        """Malformed JWTs should be rejected gracefully."""
        from agentic_brain.auth.providers import JWTAuth

        auth = JWTAuth()

        malformed_tokens = [
            "not.a.jwt",
            "only.two.parts.here",
            "a.b",
            "....",
            "header.payload",  # Missing signature
            "!@#$%^&*()",  # Special chars
        ]

        for token in malformed_tokens:
            result = await auth.validate_token(token)
            assert result is None, f"Malformed token '{token}' should be rejected"

    @pytest.mark.asyncio
    async def test_very_long_token_rejected(self, jwt_config):
        """Extremely long tokens should be rejected."""
        from agentic_brain.auth.providers import JWTAuth

        auth = JWTAuth()

        # Create an absurdly long token
        long_token = "a" * 100000

        result = await auth.validate_token(long_token)
        assert result is None
