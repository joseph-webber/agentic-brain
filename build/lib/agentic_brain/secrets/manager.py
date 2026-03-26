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
Unified secrets management for agentic-brain agents.

This module provides:
1. SecretsManager - Unified interface with fallback chain across multiple backends
2. BotSecrets - Legacy simple interface (maintained for backward compatibility)

Supported backends (via backends.py):
- Environment variables (simple, dev-friendly)
- .env files
- macOS Keychain (native Apple security)
- HashiCorp Vault (enterprise standard)
- AWS Secrets Manager
- Azure Key Vault
- Google Cloud Secret Manager

Secrets are never logged or exposed in error messages.

Example:
    >>> from agentic_brain.secrets import SecretsManager
    >>>
    >>> # Auto-configure based on environment
    >>> manager = SecretsManager.from_config()
    >>> api_key = await manager.get("OPENAI_API_KEY")
    >>>
    >>> # Or with explicit backends
    >>> from agentic_brain.secrets.backends import EnvVarBackend, AppleKeychainBackend
    >>> manager = SecretsManager([AppleKeychainBackend(), EnvVarBackend()])
    >>> api_key = await manager.require("OPENAI_API_KEY")  # Raises if not found
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
from pathlib import Path
from typing import Any

from agentic_brain.secrets.backends import (
    AppleKeychainBackend,
    AWSSecretsManagerBackend,
    AzureKeyVaultBackend,
    DotEnvBackend,
    EnvVarBackend,
    GCPSecretManagerBackend,
    HashiCorpVaultBackend,
    SecretNotFoundError,
    SecretsBackend,
    SecretsBackendError,
)

try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    keyring = None  # type: ignore
    KeyringError = Exception  # type: ignore

# Logger that NEVER logs secret values
logger = logging.getLogger(__name__)


# =============================================================================
# Security Utilities for Secrets
# =============================================================================


def _sanitize_log_message(key: str, value: str | None = None) -> str:
    """
    Create a safe log message that never includes the secret value.

    Args:
        key: The secret key (safe to log)
        value: The secret value (NEVER logged, used only to indicate presence)

    Returns:
        Safe message for logging
    """
    if value is not None:
        return f"secret '{key}' (value present, length={len(value)})"
    return f"secret '{key}' (value not present)"


def _wipe_memory(data: str | bytes | bytearray) -> None:
    """
    Attempt to wipe sensitive data from memory.

    Note: This is a best-effort operation. Python's garbage collector
    and string interning make true memory wiping difficult.
    In production, consider using libraries like 'cryptography' that
    have proper memory wiping support for sensitive operations.

    Args:
        data: The sensitive data to wipe
    """
    if isinstance(data, bytearray):
        # bytearrays are mutable, can be overwritten
        for i in range(len(data)):
            data[i] = 0
    # Strings and bytes are immutable in Python - can't truly wipe
    # Best practice: use bytearray for sensitive data in memory
    pass


class BotSecrets:
    """
    Secure secrets management with multiple backend support.

    Retrieval priority:
        1. macOS Keychain (if keyring available)
        2. Environment variable (AGENTIC_BRAIN_{KEY})
        3. .env file (~/.agentic-brain/.env)
        4. Default value

    Example:
        >>> secrets = BotSecrets()
        >>>
        >>> # Get a secret
        >>> api_key = secrets.get("OPENAI_API_KEY")
        >>>
        >>> # Set a secret (stored in keychain or env)
        >>> secrets.set("MY_SECRET", "value123")
        >>>
        >>> # Check if secret exists
        >>> if secrets.exists("API_KEY"):
        ...     secrets.delete("API_KEY")
        >>>
        >>> # List available keys
        >>> keys = secrets.list_keys()
    """

    def __init__(self, service_name: str = "agentic-brain") -> None:
        """
        Initialize BotSecrets.

        Args:
            service_name: Service name for keyring storage. Defaults to "agentic-brain".
        """
        self.service_name = service_name
        self._env_cache: dict[str, str] = {}
        self._keyring_available = KEYRING_AVAILABLE
        self._env_file_loaded = False
        self._env_file_path = Path.home() / ".agentic-brain" / ".env"

        logger.debug(
            f"BotSecrets initialized with service_name='{service_name}', "
            f"keyring_available={self._keyring_available}"
        )

    def _load_env_file(self) -> None:
        """Load secrets from .env file if it exists."""
        if self._env_file_loaded or not self._env_file_path.exists():
            return

        try:
            with open(self._env_file_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        if (
                            value.startswith('"')
                            and value.endswith('"')
                            or value.startswith("'")
                            and value.endswith("'")
                        ):
                            value = value[1:-1]

                        self._env_cache[key] = value

            self._env_file_loaded = True
            logger.debug(
                f"Loaded {len(self._env_cache)} secrets from {self._env_file_path}"
            )
        except OSError as e:
            logger.warning(f"Failed to load .env file from {self._env_file_path}: {e}")
            self._env_file_loaded = True

    def _normalize_key(self, key: str) -> str:
        """
        Normalize key name for consistent lookups.

        Args:
            key: The secret key name.

        Returns:
            Normalized key (uppercase).
        """
        return key.upper()

    def get(self, key: str, default: str | None = None) -> str | None:
        """
        Retrieve a secret value with fallback chain.

        Priority:
            1. Keychain (if available)
            2. Environment variable (AGENTIC_BRAIN_{KEY})
            3. .env file
            4. default value

        Args:
            key: The secret key name.
            default: Default value if secret not found.

        Returns:
            The secret value or default if not found.
        """
        normalized_key = self._normalize_key(key)

        if self._keyring_available and keyring:
            try:
                value = keyring.get_password(self.service_name, normalized_key)
                if value is not None:
                    logger.debug(f"Retrieved secret '{key}' from keyring")
                    return value
            except KeyringError as e:
                logger.debug(f"Keyring lookup failed for '{key}': {e}")
            except Exception as e:
                logger.debug(f"Unexpected error accessing keyring for '{key}': {e}")

        env_key = f"AGENTIC_BRAIN_{normalized_key}"
        if env_key in os.environ:
            logger.debug(f"Retrieved secret '{key}' from environment variable")
            return os.environ[env_key]

        self._load_env_file()
        if normalized_key in self._env_cache:
            logger.debug(f"Retrieved secret '{key}' from .env file")
            return self._env_cache[normalized_key]

        if default is not None:
            logger.debug(f"Using default value for secret '{key}'")
        return default

    async def get_async(self, key: str, default: str | None = None) -> str | None:
        """
        Retrieve a secret value asynchronously.

        Args:
            key: The secret key name.
            default: Default value if secret not found.

        Returns:
            The secret value or default if not found.
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self.get, key, default
        )

    def set(self, key: str, value: str) -> bool:
        """
        Store a secret value in keyring (primary backend).

        Prefers keyring if available, falls back to environment variable.
        Does NOT modify .env file (it's read-only for safety).

        Args:
            key: The secret key name.
            value: The secret value to store.

        Returns:
            True if successful, False otherwise.
        """
        normalized_key = self._normalize_key(key)

        if self._keyring_available and keyring:
            try:
                keyring.set_password(self.service_name, normalized_key, value)
                logger.debug(f"Stored secret '{key}' in keyring")
                return True
            except KeyringError as e:
                logger.warning(f"Keyring storage failed for '{key}': {e}")
            except Exception as e:
                logger.warning(f"Unexpected error storing in keyring for '{key}': {e}")

        env_key = f"AGENTIC_BRAIN_{normalized_key}"
        try:
            os.environ[env_key] = value
            logger.debug(f"Stored secret '{key}' in environment variable")
            return True
        except Exception as e:
            logger.error(f"Failed to store secret '{key}' in environment: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete a secret from all backends.

        Attempts to delete from:
        1. Keyring
        2. Environment variables

        Args:
            key: The secret key name.

        Returns:
            True if deleted from at least one backend, False if not found anywhere.
        """
        normalized_key = self._normalize_key(key)
        deleted = False

        if self._keyring_available and keyring:
            try:
                keyring.delete_password(self.service_name, normalized_key)
                logger.debug(f"Deleted secret '{key}' from keyring")
                deleted = True
            except KeyringError:
                pass
            except Exception as e:
                logger.warning(f"Error deleting from keyring for '{key}': {e}")

        env_key = f"AGENTIC_BRAIN_{normalized_key}"
        if env_key in os.environ:
            del os.environ[env_key]
            logger.debug(f"Deleted secret '{key}' from environment variable")
            deleted = True

        if not deleted:
            logger.debug(f"Secret '{key}' not found in any backend")

        return deleted

    def exists(self, key: str) -> bool:
        """
        Check if a secret exists in any backend.

        Args:
            key: The secret key name.

        Returns:
            True if secret exists, False otherwise.
        """
        normalized_key = self._normalize_key(key)

        if self._keyring_available and keyring:
            try:
                value = keyring.get_password(self.service_name, normalized_key)
                if value is not None:
                    return True
            except (KeyringError, Exception):
                pass

        env_key = f"AGENTIC_BRAIN_{normalized_key}"
        if env_key in os.environ:
            return True

        self._load_env_file()
        return normalized_key in self._env_cache

    def list_keys(self) -> list[str]:
        """
        List all available secret keys.

        Returns keys from all backends (deduplicated).
        Note: Keyring may not support listing on all platforms.

        Returns:
            List of available secret keys (normalized to uppercase).
        """
        keys: set[str] = set()

        for key in os.environ:
            if key.startswith("AGENTIC_BRAIN_"):
                secret_key = key[len("AGENTIC_BRAIN_") :]
                keys.add(secret_key)

        self._load_env_file()
        keys.update(self._env_cache.keys())

        return sorted(keys)

    def get_backend_info(self) -> dict[str, bool]:
        """
        Get information about available backends.

        Returns:
            Dictionary with backend availability status.
        """
        return {
            "keyring": self._keyring_available,
            "environment_variables": True,
            "env_file": self._env_file_path.exists(),
        }


class SecretsManager:
    """
    Unified secrets manager with fallback chain across multiple backends.

    Tries backends in priority order until a secret is found. This allows
    seamless migration between backends and environment-specific configuration.

    Priority order (default):
        1. Apple Keychain (macOS only, priority 10)
        2. HashiCorp Vault (priority 20)
        3. Cloud backends (AWS/Azure/GCP, priority 25)
        4. Environment variables (priority 50)
        5. .env file (priority 60)

    Example:
        >>> # Auto-configure based on environment
        >>> manager = SecretsManager.from_config()
        >>> api_key = await manager.get("OPENAI_API_KEY")
        >>>
        >>> # Explicit backend list
        >>> from agentic_brain.secrets.backends import EnvVarBackend, AppleKeychainBackend
        >>> manager = SecretsManager([AppleKeychainBackend(), EnvVarBackend()])
        >>> db_pass = await manager.require("DB_PASSWORD")  # Raises if not found
    """

    def __init__(
        self,
        backends: list[SecretsBackend] | None = None,
        *,
        auto_configure: bool = True,
    ) -> None:
        """
        Initialize SecretsManager.

        Args:
            backends: List of backends to use. If None and auto_configure is True,
                     backends will be auto-configured based on environment.
            auto_configure: If True and backends is None, auto-configure backends.
        """
        if backends is not None:
            self._backends = backends
        elif auto_configure:
            self._backends = self._auto_configure_backends()
        else:
            self._backends = []

        # Sort by priority (lower = higher priority)
        self._backends.sort(key=lambda b: b.priority)

        backend_names = [b.name for b in self._backends]
        logger.debug(f"SecretsManager initialized with backends: {backend_names}")

    def _auto_configure_backends(self) -> list[SecretsBackend]:
        """Auto-configure backends based on environment."""
        backends: list[SecretsBackend] = []

        # Always add env and dotenv backends
        backends.append(EnvVarBackend())
        backends.append(DotEnvBackend())

        # Add Apple Keychain on macOS
        if platform.system() == "Darwin":
            keychain = AppleKeychainBackend()
            if keychain.is_available():
                backends.append(keychain)

        # Add Vault if configured
        if os.environ.get("VAULT_ADDR") and os.environ.get("VAULT_TOKEN"):
            vault = HashiCorpVaultBackend()
            if vault.is_available():
                backends.append(vault)

        # Add AWS if configured
        if os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION"):
            try:
                aws = AWSSecretsManagerBackend()
                if aws.is_available():
                    backends.append(aws)
            except Exception:
                pass

        # Add Azure if configured
        if os.environ.get("AZURE_KEYVAULT_URL"):
            azure = AzureKeyVaultBackend()
            if azure.is_available():
                backends.append(azure)

        # Add GCP if configured
        if os.environ.get("GOOGLE_CLOUD_PROJECT"):
            gcp = GCPSecretManagerBackend()
            if gcp.is_available():
                backends.append(gcp)

        return backends

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SecretsManager:
        """
        Create SecretsManager from configuration dictionary.

        Args:
            config: Configuration dictionary with backend settings.
                   If None, auto-configures based on environment.
            **kwargs: Additional arguments passed to backends.

        Returns:
            Configured SecretsManager instance.

        Example config:
            {
                "backends": ["keychain", "env", "dotenv"],
                "keychain": {"service_name": "my-app"},
                "vault": {"vault_addr": "https://vault.example.com"},
                "aws": {"region_name": "us-east-1"},
            }
        """
        if config is None:
            return cls(auto_configure=True)

        backends: list[SecretsBackend] = []
        backend_names = config.get("backends", ["env", "dotenv"])

        for name in backend_names:
            backend_config = config.get(name, {})
            backend_config.update(kwargs.get(name, {}))

            if name in ("env", "envvar", "environment"):
                backends.append(EnvVarBackend(**backend_config))
            elif name in ("dotenv", ".env"):
                backends.append(DotEnvBackend(**backend_config))
            elif name in ("keychain", "apple_keychain"):
                backends.append(AppleKeychainBackend(**backend_config))
            elif name in ("vault", "hashicorp_vault"):
                backends.append(HashiCorpVaultBackend(**backend_config))
            elif name in ("aws", "aws_secrets_manager"):
                backends.append(AWSSecretsManagerBackend(**backend_config))
            elif name in ("azure", "azure_key_vault"):
                backends.append(AzureKeyVaultBackend(**backend_config))
            elif name in ("gcp", "gcp_secret_manager"):
                backends.append(GCPSecretManagerBackend(**backend_config))
            else:
                logger.warning(f"Unknown backend: {name}")

        return cls(backends=backends, auto_configure=False)

    @property
    def backends(self) -> list[SecretsBackend]:
        """Get the list of configured backends."""
        return self._backends.copy()

    def get_backend_info(self) -> list[dict[str, Any]]:
        """
        Get information about all configured backends.

        Returns:
            List of backend info dictionaries.
        """
        return [
            {
                "name": b.name,
                "priority": b.priority,
                "available": b.is_available(),
            }
            for b in self._backends
        ]

    async def get(self, key: str, default: str | None = None) -> str | None:
        """
        Get a secret, trying backends in priority order.

        Args:
            key: The secret key name.
            default: Default value if not found in any backend.

        Returns:
            The secret value, or default if not found.
        """
        for backend in self._backends:
            if not backend.is_available():
                continue

            try:
                value = await backend.get_secret(key)
                logger.debug(f"Retrieved '{key}' from {backend.name}")
                return value
            except SecretNotFoundError:
                continue
            except SecretsBackendError as e:
                logger.debug(f"Backend {backend.name} error for '{key}': {e}")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error in {backend.name} for '{key}': {e}")
                continue

        logger.debug(f"Secret '{key}' not found in any backend")
        return default

    async def require(self, key: str) -> str:
        """
        Get a secret that must exist. Raises if not found.

        Args:
            key: The secret key name.

        Returns:
            The secret value.

        Raises:
            SecretNotFoundError: If secret not found in any backend.
        """
        value = await self.get(key)
        if value is None:
            raise SecretNotFoundError(
                f"Required secret '{key}' not found in any backend"
            )
        return value

    async def set(
        self,
        key: str,
        value: str,
        backend_name: str | None = None,
    ) -> bool:
        """
        Set a secret in a specific backend or the first writable one.

        Args:
            key: The secret key name.
            value: The secret value.
            backend_name: Optional specific backend to use.

        Returns:
            True if successfully stored.
        """
        if backend_name:
            # Use specific backend
            for backend in self._backends:
                if backend.name == backend_name:
                    try:
                        await backend.set_secret(key, value)
                        logger.debug(f"Stored '{key}' in {backend.name}")
                        return True
                    except Exception as e:
                        logger.error(f"Failed to store in {backend.name}: {e}")
                        return False
            logger.error(f"Backend '{backend_name}' not found")
            return False

        # Try first available backend
        for backend in self._backends:
            if not backend.is_available():
                continue

            try:
                await backend.set_secret(key, value)
                logger.debug(f"Stored '{key}' in {backend.name}")
                return True
            except SecretsBackendError as e:
                logger.debug(f"Cannot store in {backend.name}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Unexpected error in {backend.name}: {e}")
                continue

        logger.error(f"Failed to store '{key}' in any backend")
        return False

    async def delete(self, key: str, all_backends: bool = False) -> bool:
        """
        Delete a secret from backends.

        Args:
            key: The secret key name.
            all_backends: If True, delete from all backends. Otherwise, only
                         delete from the first backend that has it.

        Returns:
            True if deleted from at least one backend.
        """
        deleted = False

        for backend in self._backends:
            if not backend.is_available():
                continue

            try:
                await backend.delete_secret(key)
                logger.debug(f"Deleted '{key}' from {backend.name}")
                deleted = True
                if not all_backends:
                    break
            except SecretNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"Failed to delete from {backend.name}: {e}")
                continue

        return deleted

    async def exists(self, key: str) -> bool:
        """
        Check if a secret exists in any backend.

        Args:
            key: The secret key name.

        Returns:
            True if the secret exists.
        """
        value = await self.get(key)
        return value is not None

    async def list_secrets(self, deduplicate: bool = True) -> list[str]:
        """
        List all secrets from all backends.

        Args:
            deduplicate: If True, return unique keys only.

        Returns:
            List of secret key names.
        """
        all_keys: list[str] = []

        for backend in self._backends:
            if not backend.is_available():
                continue

            try:
                keys = await backend.list_secrets()
                all_keys.extend(keys)
            except Exception as e:
                logger.debug(f"Failed to list from {backend.name}: {e}")
                continue

        if deduplicate:
            return sorted(set(all_keys))
        return sorted(all_keys)

    # Sync wrappers for convenience
    def get_sync(self, key: str, default: str | None = None) -> str | None:
        """Synchronous version of get()."""
        return asyncio.get_event_loop().run_until_complete(self.get(key, default))

    def require_sync(self, key: str) -> str:
        """Synchronous version of require()."""
        return asyncio.get_event_loop().run_until_complete(self.require(key))

    def set_sync(self, key: str, value: str, backend_name: str | None = None) -> bool:
        """Synchronous version of set()."""
        return asyncio.get_event_loop().run_until_complete(
            self.set(key, value, backend_name)
        )


__all__ = [
    "BotSecrets",
    "SecretsManager",
    "SecretNotFoundError",
    "SecretsBackendError",
    "KEYRING_AVAILABLE",
]
