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
Enterprise secrets backends for agentic-brain.

Provides multiple secrets storage backends with a unified interface:
- EnvVarBackend: Environment variables (simple, dev-friendly)
- DotEnvBackend: Load from .env file
- AppleKeychainBackend: macOS Keychain (native Apple security)
- HashiCorpVaultBackend: HashiCorp Vault (enterprise standard)
- AWSSecretsManagerBackend: AWS Secrets Manager
- AzureKeyVaultBackend: Azure Key Vault
- GCPSecretManagerBackend: Google Cloud Secret Manager

Example:
    >>> from agentic_brain.secrets.backends import EnvVarBackend, AppleKeychainBackend
    >>>
    >>> # Simple env backend
    >>> env_backend = EnvVarBackend()
    >>> await env_backend.set_secret("API_KEY", "secret123")
    >>> value = await env_backend.get_secret("API_KEY")
    >>>
    >>> # macOS Keychain
    >>> keychain = AppleKeychainBackend(service_name="my-app")
    >>> await keychain.set_secret("DB_PASSWORD", "secure_pass")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SecretsBackendError(Exception):
    """Base exception for secrets backend errors."""

    pass


class SecretNotFoundError(SecretsBackendError):
    """Raised when a secret is not found."""

    pass


class BackendUnavailableError(SecretsBackendError):
    """Raised when a backend is not available or misconfigured."""

    pass


class SecretsBackend(ABC):
    """
    Abstract base class for secrets backends.

    All backends must implement async methods for getting, setting,
    deleting, and listing secrets. The interface is designed to be
    simple and consistent across all backend types.

    Attributes:
        name: Human-readable name of the backend.
        priority: Default priority when used in fallback chain (lower = higher priority).
    """

    name: str = "base"
    priority: int = 100

    @abstractmethod
    async def get_secret(self, key: str) -> str:
        """
        Retrieve a secret value.

        Args:
            key: The secret key name.

        Returns:
            The secret value.

        Raises:
            SecretNotFoundError: If the secret doesn't exist.
            SecretsBackendError: If retrieval fails.
        """
        pass

    @abstractmethod
    async def set_secret(self, key: str, value: str) -> None:
        """
        Store a secret value.

        Args:
            key: The secret key name.
            value: The secret value to store.

        Raises:
            SecretsBackendError: If storage fails.
        """
        pass

    @abstractmethod
    async def delete_secret(self, key: str) -> None:
        """
        Delete a secret.

        Args:
            key: The secret key name.

        Raises:
            SecretNotFoundError: If the secret doesn't exist.
            SecretsBackendError: If deletion fails.
        """
        pass

    @abstractmethod
    async def list_secrets(self) -> list[str]:
        """
        List all available secret keys.

        Returns:
            List of secret key names.

        Raises:
            SecretsBackendError: If listing fails.
        """
        pass

    async def exists(self, key: str) -> bool:
        """
        Check if a secret exists.

        Args:
            key: The secret key name.

        Returns:
            True if the secret exists, False otherwise.
        """
        try:
            await self.get_secret(key)
            return True
        except SecretNotFoundError:
            return False
        except SecretsBackendError:
            return False

    def is_available(self) -> bool:
        """
        Check if this backend is available and properly configured.

        Returns:
            True if the backend is ready to use.
        """
        return True

    def _normalize_key(self, key: str) -> str:
        """Normalize key to uppercase for consistency."""
        return key.upper().strip()


class EnvVarBackend(SecretsBackend):
    """
    Environment variables backend - simple and dev-friendly.

    Secrets are stored as environment variables with an optional prefix.
    This is the simplest backend, ideal for development and CI/CD.

    Attributes:
        prefix: Prefix for environment variable names (default: "AGENTIC_BRAIN_").

    Example:
        >>> backend = EnvVarBackend(prefix="MYAPP_")
        >>> await backend.set_secret("API_KEY", "secret123")
        >>> # This sets MYAPP_API_KEY=secret123
    """

    name = "environment_variables"
    priority = 50

    def __init__(self, prefix: str = "AGENTIC_BRAIN_") -> None:
        """
        Initialize EnvVarBackend.

        Args:
            prefix: Prefix for environment variable names.
        """
        self.prefix = prefix
        logger.debug(f"EnvVarBackend initialized with prefix='{prefix}'")

    def _get_env_key(self, key: str) -> str:
        """Get the full environment variable name."""
        return f"{self.prefix}{self._normalize_key(key)}"

    async def get_secret(self, key: str) -> str:
        env_key = self._get_env_key(key)
        value = os.environ.get(env_key)
        if value is None:
            raise SecretNotFoundError(f"Secret '{key}' not found in environment")
        logger.debug(f"Retrieved secret '{key}' from environment")
        return value

    async def set_secret(self, key: str, value: str) -> None:
        env_key = self._get_env_key(key)
        os.environ[env_key] = value
        logger.debug(f"Stored secret '{key}' in environment")

    async def delete_secret(self, key: str) -> None:
        env_key = self._get_env_key(key)
        if env_key not in os.environ:
            raise SecretNotFoundError(f"Secret '{key}' not found in environment")
        del os.environ[env_key]
        logger.debug(f"Deleted secret '{key}' from environment")

    async def list_secrets(self) -> list[str]:
        secrets = []
        for key in os.environ:
            if key.startswith(self.prefix):
                secret_name = key[len(self.prefix) :]
                secrets.append(secret_name)
        return sorted(secrets)


class DotEnvBackend(SecretsBackend):
    """
    .env file backend - load secrets from dotenv files.

    Reads secrets from a .env file. Supports reading and writing,
    with automatic file creation if it doesn't exist.

    Attributes:
        env_path: Path to the .env file.
        readonly: If True, don't allow writing to the file.

    Example:
        >>> backend = DotEnvBackend(env_path="~/.myapp/.env")
        >>> secrets = await backend.list_secrets()
    """

    name = "dotenv"
    priority = 60

    def __init__(
        self,
        env_path: str | Path | None = None,
        readonly: bool = False,
    ) -> None:
        """
        Initialize DotEnvBackend.

        Args:
            env_path: Path to .env file. Defaults to ~/.agentic-brain/.env
            readonly: If True, don't allow writing to the file.
        """
        if env_path is None:
            self.env_path = Path.home() / ".agentic-brain" / ".env"
        else:
            self.env_path = Path(env_path).expanduser()
        self.readonly = readonly
        self._cache: dict[str, str] = {}
        self._loaded = False
        logger.debug(f"DotEnvBackend initialized with path='{self.env_path}'")

    def _load_file(self) -> None:
        """Load the .env file into cache."""
        if self._loaded:
            return

        self._cache.clear()
        if not self.env_path.exists():
            self._loaded = True
            return

        try:
            with open(self.env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = self._normalize_key(key)
                        value = value.strip()

                        # Remove quotes
                        if (value.startswith('"') and value.endswith('"')) or (
                            value.startswith("'") and value.endswith("'")
                        ):
                            value = value[1:-1]

                        self._cache[key] = value

            self._loaded = True
            logger.debug(f"Loaded {len(self._cache)} secrets from {self.env_path}")
        except OSError as e:
            logger.warning(f"Failed to load .env file: {e}")
            self._loaded = True

    def _save_file(self) -> None:
        """Save cache to .env file."""
        if self.readonly:
            raise SecretsBackendError("Backend is read-only")

        # Ensure directory exists
        self.env_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.env_path, "w") as f:
                f.write("# agentic-brain secrets\n")
                f.write("# Auto-generated - do not edit manually\n\n")
                for key in sorted(self._cache.keys()):
                    value = self._cache[key]
                    # Quote values with spaces or special chars
                    if " " in value or '"' in value or "'" in value:
                        value = f'"{value}"'
                    f.write(f"{key}={value}\n")
            logger.debug(f"Saved {len(self._cache)} secrets to {self.env_path}")
        except OSError as e:
            raise SecretsBackendError(f"Failed to save .env file: {e}")

    async def get_secret(self, key: str) -> str:
        self._load_file()
        normalized = self._normalize_key(key)
        if normalized not in self._cache:
            raise SecretNotFoundError(f"Secret '{key}' not found in .env file")
        return self._cache[normalized]

    async def set_secret(self, key: str, value: str) -> None:
        if self.readonly:
            raise SecretsBackendError("Backend is read-only")
        self._load_file()
        normalized = self._normalize_key(key)
        self._cache[normalized] = value
        self._save_file()
        logger.debug(f"Stored secret '{key}' in .env file")

    async def delete_secret(self, key: str) -> None:
        if self.readonly:
            raise SecretsBackendError("Backend is read-only")
        self._load_file()
        normalized = self._normalize_key(key)
        if normalized not in self._cache:
            raise SecretNotFoundError(f"Secret '{key}' not found in .env file")
        del self._cache[normalized]
        self._save_file()
        logger.debug(f"Deleted secret '{key}' from .env file")

    async def list_secrets(self) -> list[str]:
        self._load_file()
        return sorted(self._cache.keys())

    def is_available(self) -> bool:
        return self.env_path.exists() or not self.readonly


class AppleKeychainBackend(SecretsBackend):
    """
    macOS Keychain backend - native Apple security.

    Uses the macOS Keychain to store secrets securely. Supports both
    the keyring library and direct security CLI access.

    Attributes:
        service_name: Service name for keychain entries.

    Example:
        >>> backend = AppleKeychainBackend(service_name="my-app")
        >>> await backend.set_secret("API_KEY", "secret123")
        >>> # Stored securely in macOS Keychain
    """

    name = "apple_keychain"
    priority = 10  # Highest priority - most secure

    def __init__(self, service_name: str = "agentic-brain") -> None:
        """
        Initialize AppleKeychainBackend.

        Args:
            service_name: Service name for keychain entries.
        """
        self.service_name = service_name
        self._keyring_available = self._check_keyring()
        logger.debug(
            f"AppleKeychainBackend initialized with service='{service_name}', "
            f"keyring={self._keyring_available}"
        )

    def _check_keyring(self) -> bool:
        """Check if keyring library is available."""
        try:
            import keyring  # noqa: F401

            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Check if running on macOS with Keychain access."""
        import platform

        return platform.system() == "Darwin"

    async def get_secret(self, key: str) -> str:
        normalized = self._normalize_key(key)

        if self._keyring_available:
            import keyring

            try:
                value = await asyncio.get_event_loop().run_in_executor(
                    None, keyring.get_password, self.service_name, normalized
                )
                if value is not None:
                    logger.debug(f"Retrieved secret '{key}' from keyring")
                    return value
            except Exception as e:
                logger.debug(f"Keyring lookup failed: {e}")

        # Fallback to security CLI
        try:
            result = await asyncio.create_subprocess_exec(
                "security",
                "find-generic-password",
                "-s",
                self.service_name,
                "-a",
                normalized,
                "-w",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            if result.returncode == 0:
                value = stdout.decode().strip()
                logger.debug(f"Retrieved secret '{key}' from security CLI")
                return value
        except Exception as e:
            logger.debug(f"Security CLI lookup failed: {e}")

        raise SecretNotFoundError(f"Secret '{key}' not found in Keychain")

    async def set_secret(self, key: str, value: str) -> None:
        normalized = self._normalize_key(key)

        if self._keyring_available:
            import keyring

            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, keyring.set_password, self.service_name, normalized, value
                )
                logger.debug(f"Stored secret '{key}' in keyring")
                return
            except Exception as e:
                logger.debug(f"Keyring storage failed: {e}")

        # Fallback to security CLI
        try:
            # Delete existing if present
            await asyncio.create_subprocess_exec(
                "security",
                "delete-generic-password",
                "-s",
                self.service_name,
                "-a",
                normalized,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            result = await asyncio.create_subprocess_exec(
                "security",
                "add-generic-password",
                "-s",
                self.service_name,
                "-a",
                normalized,
                "-w",
                value,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await result.communicate()
            if result.returncode == 0:
                logger.debug(f"Stored secret '{key}' via security CLI")
                return
        except Exception as e:
            raise SecretsBackendError(f"Failed to store in Keychain: {e}")

        raise SecretsBackendError("Failed to store secret in Keychain")

    async def delete_secret(self, key: str) -> None:
        normalized = self._normalize_key(key)

        if self._keyring_available:
            import keyring

            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, keyring.delete_password, self.service_name, normalized
                )
                logger.debug(f"Deleted secret '{key}' from keyring")
                return
            except Exception as e:
                logger.debug(f"Keyring deletion failed: {e}")

        # Fallback to security CLI
        try:
            result = await asyncio.create_subprocess_exec(
                "security",
                "delete-generic-password",
                "-s",
                self.service_name,
                "-a",
                normalized,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await result.communicate()
            if result.returncode == 0:
                logger.debug(f"Deleted secret '{key}' via security CLI")
                return
        except Exception as e:
            logger.debug(f"Security CLI deletion failed: {e}")

        raise SecretNotFoundError(f"Secret '{key}' not found in Keychain")

    async def list_secrets(self) -> list[str]:
        # Note: Listing keychain items requires parsing security output
        # This is a simplified implementation
        secrets: list[str] = []

        try:
            result = await asyncio.create_subprocess_exec(
                "security",
                "dump-keychain",
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            stdout, _ = await result.communicate()
            output = stdout.decode()

            # Parse for our service entries
            import re

            pattern = rf'"svce"<blob>="{re.escape(self.service_name)}".*?"acct"<blob>="([^"]+)"'
            matches = re.findall(pattern, output, re.DOTALL)
            secrets.extend(matches)
        except Exception as e:
            logger.debug(f"Failed to list keychain items: {e}")

        return sorted(set(secrets))


class HashiCorpVaultBackend(SecretsBackend):
    """
    HashiCorp Vault backend - enterprise standard secrets management.

    Supports token-based authentication with the Vault KV secrets engine.

    Attributes:
        vault_addr: Vault server address.
        mount_point: KV secrets engine mount point.
        path_prefix: Prefix for secret paths.

    Example:
        >>> backend = HashiCorpVaultBackend(
        ...     vault_addr="https://vault.example.com",
        ...     token="hvs.xxx"
        ... )
        >>> await backend.set_secret("database/password", "secure123")
    """

    name = "hashicorp_vault"
    priority = 20

    def __init__(
        self,
        vault_addr: str | None = None,
        token: str | None = None,
        mount_point: str = "secret",
        path_prefix: str = "agentic-brain",
        namespace: str | None = None,
    ) -> None:
        """
        Initialize HashiCorpVaultBackend.

        Args:
            vault_addr: Vault server address. Defaults to VAULT_ADDR env var.
            token: Vault token. Defaults to VAULT_TOKEN env var.
            mount_point: KV secrets engine mount point.
            path_prefix: Prefix for secret paths.
            namespace: Vault namespace (Enterprise feature).
        """
        self.vault_addr = vault_addr or os.environ.get("VAULT_ADDR", "")
        self.token = token or os.environ.get("VAULT_TOKEN", "")
        self.mount_point = mount_point
        self.path_prefix = path_prefix
        self.namespace = namespace
        self._client: Any = None
        logger.debug(f"HashiCorpVaultBackend initialized for {self.vault_addr}")

    def _get_client(self) -> Any:
        """Get or create Vault client."""
        if self._client is None:
            try:
                import hvac

                self._client = hvac.Client(
                    url=self.vault_addr,
                    token=self.token,
                    namespace=self.namespace,
                )
            except ImportError:
                raise BackendUnavailableError(
                    "hvac library required for Vault backend. "
                    "Install with: pip install hvac"
                )
        return self._client

    def is_available(self) -> bool:
        """Check if Vault is configured and accessible."""
        if not self.vault_addr or not self.token:
            return False
        try:
            client = self._get_client()
            return client.is_authenticated()
        except Exception:
            return False

    def _get_path(self, key: str) -> str:
        """Get the full Vault path for a key."""
        normalized = self._normalize_key(key).lower().replace("_", "/")
        return f"{self.path_prefix}/{normalized}"

    async def get_secret(self, key: str) -> str:
        path = self._get_path(key)

        def _get() -> str:
            client = self._get_client()
            try:
                # Try KV v2 first
                result = client.secrets.kv.v2.read_secret_version(
                    path=path, mount_point=self.mount_point
                )
                data = result.get("data", {}).get("data", {})
                if "value" in data:
                    return data["value"]
                # Return first value if only one key
                if len(data) == 1:
                    return list(data.values())[0]
                raise SecretNotFoundError(f"Secret '{key}' has no 'value' field")
            except Exception as e:
                if "permission denied" in str(e).lower():
                    raise SecretsBackendError(f"Permission denied for '{key}'")
                raise SecretNotFoundError(f"Secret '{key}' not found in Vault: {e}")

        try:
            return await asyncio.get_event_loop().run_in_executor(None, _get)
        except (SecretNotFoundError, SecretsBackendError):
            raise
        except Exception as e:
            raise SecretsBackendError(f"Vault error: {e}")

    async def set_secret(self, key: str, value: str) -> None:
        path = self._get_path(key)

        def _set() -> None:
            client = self._get_client()
            client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret={"value": value},
                mount_point=self.mount_point,
            )

        try:
            await asyncio.get_event_loop().run_in_executor(None, _set)
            logger.debug(f"Stored secret '{key}' in Vault")
        except Exception as e:
            raise SecretsBackendError(f"Failed to store in Vault: {e}")

    async def delete_secret(self, key: str) -> None:
        path = self._get_path(key)

        def _delete() -> None:
            client = self._get_client()
            try:
                client.secrets.kv.v2.delete_metadata_and_all_versions(
                    path=path, mount_point=self.mount_point
                )
            except Exception as e:
                if "not found" in str(e).lower():
                    raise SecretNotFoundError(f"Secret '{key}' not found")
                raise

        try:
            await asyncio.get_event_loop().run_in_executor(None, _delete)
            logger.debug(f"Deleted secret '{key}' from Vault")
        except SecretNotFoundError:
            raise
        except Exception as e:
            raise SecretsBackendError(f"Failed to delete from Vault: {e}")

    async def list_secrets(self) -> list[str]:
        def _list() -> list[str]:
            client = self._get_client()
            try:
                result = client.secrets.kv.v2.list_secrets(
                    path=self.path_prefix, mount_point=self.mount_point
                )
                keys = result.get("data", {}).get("keys", [])
                return [k.rstrip("/").upper().replace("/", "_") for k in keys]
            except Exception:
                return []

        try:
            return await asyncio.get_event_loop().run_in_executor(None, _list)
        except Exception as e:
            logger.debug(f"Failed to list Vault secrets: {e}")
            return []


class AWSSecretsManagerBackend(SecretsBackend):
    """
    AWS Secrets Manager backend - AWS cloud secrets management.

    Uses boto3 to interact with AWS Secrets Manager.

    Attributes:
        region_name: AWS region.
        prefix: Prefix for secret names.

    Example:
        >>> backend = AWSSecretsManagerBackend(region_name="us-east-1")
        >>> await backend.set_secret("api-key", "secret123")
    """

    name = "aws_secrets_manager"
    priority = 25

    def __init__(
        self,
        region_name: str | None = None,
        prefix: str = "agentic-brain/",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> None:
        """
        Initialize AWSSecretsManagerBackend.

        Args:
            region_name: AWS region. Defaults to AWS_DEFAULT_REGION env var.
            prefix: Prefix for secret names.
            aws_access_key_id: AWS access key. Defaults to env var.
            aws_secret_access_key: AWS secret key. Defaults to env var.
        """
        self.region_name = region_name or os.environ.get("AWS_DEFAULT_REGION")
        self.prefix = prefix
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self._client: Any = None
        logger.debug(
            f"AWSSecretsManagerBackend initialized for region={self.region_name}"
        )

    def _get_client(self) -> Any:
        """Get or create AWS Secrets Manager client."""
        if self._client is None:
            try:
                import boto3

                kwargs: dict[str, Any] = {}
                if self.region_name:
                    kwargs["region_name"] = self.region_name
                if self.aws_access_key_id:
                    kwargs["aws_access_key_id"] = self.aws_access_key_id
                if self.aws_secret_access_key:
                    kwargs["aws_secret_access_key"] = self.aws_secret_access_key

                self._client = boto3.client("secretsmanager", **kwargs)
            except ImportError:
                raise BackendUnavailableError(
                    "boto3 library required for AWS backend. "
                    "Install with: pip install boto3"
                )
        return self._client

    def is_available(self) -> bool:
        """Check if AWS credentials are configured."""
        try:
            self._get_client()
            return True
        except Exception:
            return False

    def _get_secret_name(self, key: str) -> str:
        """Get the full AWS secret name."""
        normalized = self._normalize_key(key).lower().replace("_", "-")
        return f"{self.prefix}{normalized}"

    async def get_secret(self, key: str) -> str:
        secret_name = self._get_secret_name(key)

        def _get() -> str:
            client = self._get_client()
            try:
                response = client.get_secret_value(SecretId=secret_name)
                if "SecretString" in response:
                    # Try to parse as JSON
                    try:
                        data = json.loads(response["SecretString"])
                        if isinstance(data, dict) and "value" in data:
                            return data["value"]
                        if isinstance(data, str):
                            return data
                    except json.JSONDecodeError:
                        pass
                    return response["SecretString"]
                raise SecretNotFoundError(f"Secret '{key}' has no string value")
            except self._get_client().exceptions.ResourceNotFoundException:
                raise SecretNotFoundError(f"Secret '{key}' not found in AWS")
            except Exception as e:
                raise SecretsBackendError(f"AWS error: {e}")

        return await asyncio.get_event_loop().run_in_executor(None, _get)

    async def set_secret(self, key: str, value: str) -> None:
        secret_name = self._get_secret_name(key)

        def _set() -> None:
            client = self._get_client()
            try:
                # Try to update existing
                client.put_secret_value(
                    SecretId=secret_name, SecretString=json.dumps({"value": value})
                )
            except client.exceptions.ResourceNotFoundException:
                # Create new
                client.create_secret(
                    Name=secret_name,
                    SecretString=json.dumps({"value": value}),
                    Tags=[{"Key": "application", "Value": "agentic-brain"}],
                )

        try:
            await asyncio.get_event_loop().run_in_executor(None, _set)
            logger.debug(f"Stored secret '{key}' in AWS Secrets Manager")
        except Exception as e:
            raise SecretsBackendError(f"Failed to store in AWS: {e}")

    async def delete_secret(self, key: str) -> None:
        secret_name = self._get_secret_name(key)

        def _delete() -> None:
            client = self._get_client()
            try:
                client.delete_secret(
                    SecretId=secret_name, ForceDeleteWithoutRecovery=True
                )
            except client.exceptions.ResourceNotFoundException:
                raise SecretNotFoundError(f"Secret '{key}' not found in AWS")

        try:
            await asyncio.get_event_loop().run_in_executor(None, _delete)
            logger.debug(f"Deleted secret '{key}' from AWS Secrets Manager")
        except SecretNotFoundError:
            raise
        except Exception as e:
            raise SecretsBackendError(f"Failed to delete from AWS: {e}")

    async def list_secrets(self) -> list[str]:
        def _list() -> list[str]:
            client = self._get_client()
            secrets = []
            paginator = client.get_paginator("list_secrets")
            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    name = secret["Name"]
                    if name.startswith(self.prefix):
                        key = name[len(self.prefix) :].upper().replace("-", "_")
                        secrets.append(key)
            return sorted(secrets)

        try:
            return await asyncio.get_event_loop().run_in_executor(None, _list)
        except Exception as e:
            logger.debug(f"Failed to list AWS secrets: {e}")
            return []


class AzureKeyVaultBackend(SecretsBackend):
    """
    Azure Key Vault backend - Azure cloud secrets management.

    Uses azure-identity and azure-keyvault-secrets libraries.

    Attributes:
        vault_url: Azure Key Vault URL.

    Example:
        >>> backend = AzureKeyVaultBackend(
        ...     vault_url="https://my-vault.vault.azure.net"
        ... )
        >>> await backend.get_secret("api-key")
    """

    name = "azure_key_vault"
    priority = 25

    def __init__(
        self,
        vault_url: str | None = None,
    ) -> None:
        """
        Initialize AzureKeyVaultBackend.

        Args:
            vault_url: Azure Key Vault URL. Defaults to AZURE_KEYVAULT_URL env var.
        """
        self.vault_url = vault_url or os.environ.get("AZURE_KEYVAULT_URL", "")
        self._client: Any = None
        logger.debug(f"AzureKeyVaultBackend initialized for {self.vault_url}")

    def _get_client(self) -> Any:
        """Get or create Azure Key Vault client."""
        if self._client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient

                credential = DefaultAzureCredential()
                self._client = SecretClient(
                    vault_url=self.vault_url, credential=credential
                )
            except ImportError:
                raise BackendUnavailableError(
                    "azure-identity and azure-keyvault-secrets required. "
                    "Install with: pip install azure-identity azure-keyvault-secrets"
                )
        return self._client

    def is_available(self) -> bool:
        """Check if Azure credentials are configured."""
        return bool(self.vault_url)

    def _normalize_azure_name(self, key: str) -> str:
        """Azure secret names can only contain alphanumeric and dashes."""
        return self._normalize_key(key).lower().replace("_", "-")

    async def get_secret(self, key: str) -> str:
        name = self._normalize_azure_name(key)

        def _get() -> str:
            client = self._get_client()
            try:
                secret = client.get_secret(name)
                if secret.value is None:
                    raise SecretNotFoundError(f"Secret '{key}' has no value")
                return secret.value
            except Exception as e:
                if (
                    "SecretNotFound" in str(type(e).__name__)
                    or "not found" in str(e).lower()
                ):
                    raise SecretNotFoundError(f"Secret '{key}' not found in Azure")
                raise SecretsBackendError(f"Azure error: {e}")

        return await asyncio.get_event_loop().run_in_executor(None, _get)

    async def set_secret(self, key: str, value: str) -> None:
        name = self._normalize_azure_name(key)

        def _set() -> None:
            client = self._get_client()
            client.set_secret(name, value)

        try:
            await asyncio.get_event_loop().run_in_executor(None, _set)
            logger.debug(f"Stored secret '{key}' in Azure Key Vault")
        except Exception as e:
            raise SecretsBackendError(f"Failed to store in Azure: {e}")

    async def delete_secret(self, key: str) -> None:
        name = self._normalize_azure_name(key)

        def _delete() -> None:
            client = self._get_client()
            try:
                poller = client.begin_delete_secret(name)
                poller.wait()
            except Exception as e:
                if "SecretNotFound" in str(type(e).__name__):
                    raise SecretNotFoundError(f"Secret '{key}' not found in Azure")
                raise

        try:
            await asyncio.get_event_loop().run_in_executor(None, _delete)
            logger.debug(f"Deleted secret '{key}' from Azure Key Vault")
        except SecretNotFoundError:
            raise
        except Exception as e:
            raise SecretsBackendError(f"Failed to delete from Azure: {e}")

    async def list_secrets(self) -> list[str]:
        def _list() -> list[str]:
            client = self._get_client()
            secrets = []
            for secret_properties in client.list_properties_of_secrets():
                name = secret_properties.name
                if name:
                    secrets.append(name.upper().replace("-", "_"))
            return sorted(secrets)

        try:
            return await asyncio.get_event_loop().run_in_executor(None, _list)
        except Exception as e:
            logger.debug(f"Failed to list Azure secrets: {e}")
            return []


class GCPSecretManagerBackend(SecretsBackend):
    """
    Google Cloud Secret Manager backend - GCP cloud secrets management.

    Uses google-cloud-secret-manager library.

    Attributes:
        project_id: GCP project ID.
        prefix: Prefix for secret names.

    Example:
        >>> backend = GCPSecretManagerBackend(project_id="my-project")
        >>> await backend.get_secret("api-key")
    """

    name = "gcp_secret_manager"
    priority = 25

    def __init__(
        self,
        project_id: str | None = None,
        prefix: str = "agentic-brain-",
    ) -> None:
        """
        Initialize GCPSecretManagerBackend.

        Args:
            project_id: GCP project ID. Defaults to GOOGLE_CLOUD_PROJECT env var.
            prefix: Prefix for secret names.
        """
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        self.prefix = prefix
        self._client: Any = None
        logger.debug(
            f"GCPSecretManagerBackend initialized for project={self.project_id}"
        )

    def _get_client(self) -> Any:
        """Get or create GCP Secret Manager client."""
        if self._client is None:
            try:
                from google.cloud import secretmanager

                self._client = secretmanager.SecretManagerServiceClient()
            except ImportError:
                raise BackendUnavailableError(
                    "google-cloud-secret-manager required. "
                    "Install with: pip install google-cloud-secret-manager"
                )
        return self._client

    def is_available(self) -> bool:
        """Check if GCP credentials are configured."""
        return bool(self.project_id)

    def _normalize_gcp_name(self, key: str) -> str:
        """GCP secret names: lowercase, alphanumeric, underscores, dashes."""
        return self.prefix + self._normalize_key(key).lower().replace("_", "-")

    def _get_secret_path(self, key: str) -> str:
        """Get the full GCP secret path."""
        name = self._normalize_gcp_name(key)
        return f"projects/{self.project_id}/secrets/{name}"

    def _get_version_path(self, key: str, version: str = "latest") -> str:
        """Get the full GCP secret version path."""
        return f"{self._get_secret_path(key)}/versions/{version}"

    async def get_secret(self, key: str) -> str:
        version_path = self._get_version_path(key)

        def _get() -> str:
            client = self._get_client()
            try:
                response = client.access_secret_version(name=version_path)
                return response.payload.data.decode("utf-8")
            except Exception as e:
                if "NOT_FOUND" in str(e) or "not found" in str(e).lower():
                    raise SecretNotFoundError(f"Secret '{key}' not found in GCP")
                raise SecretsBackendError(f"GCP error: {e}")

        return await asyncio.get_event_loop().run_in_executor(None, _get)

    async def set_secret(self, key: str, value: str) -> None:
        secret_path = self._get_secret_path(key)
        parent = f"projects/{self.project_id}"
        secret_id = self._normalize_gcp_name(key)

        def _set() -> None:
            client = self._get_client()

            # Try to create secret first
            try:
                client.create_secret(
                    parent=parent,
                    secret_id=secret_id,
                    secret={"replication": {"automatic": {}}},
                )
            except Exception as e:
                if "ALREADY_EXISTS" not in str(e):
                    raise

            # Add version with value
            client.add_secret_version(
                parent=secret_path, payload={"data": value.encode("utf-8")}
            )

        try:
            await asyncio.get_event_loop().run_in_executor(None, _set)
            logger.debug(f"Stored secret '{key}' in GCP Secret Manager")
        except Exception as e:
            raise SecretsBackendError(f"Failed to store in GCP: {e}")

    async def delete_secret(self, key: str) -> None:
        secret_path = self._get_secret_path(key)

        def _delete() -> None:
            client = self._get_client()
            try:
                client.delete_secret(name=secret_path)
            except Exception as e:
                if "NOT_FOUND" in str(e):
                    raise SecretNotFoundError(f"Secret '{key}' not found in GCP")
                raise

        try:
            await asyncio.get_event_loop().run_in_executor(None, _delete)
            logger.debug(f"Deleted secret '{key}' from GCP Secret Manager")
        except SecretNotFoundError:
            raise
        except Exception as e:
            raise SecretsBackendError(f"Failed to delete from GCP: {e}")

    async def list_secrets(self) -> list[str]:
        parent = f"projects/{self.project_id}"

        def _list() -> list[str]:
            client = self._get_client()
            secrets = []
            for secret in client.list_secrets(parent=parent):
                name = secret.name.split("/")[-1]
                if name.startswith(self.prefix):
                    key = name[len(self.prefix) :].upper().replace("-", "_")
                    secrets.append(key)
            return sorted(secrets)

        try:
            return await asyncio.get_event_loop().run_in_executor(None, _list)
        except Exception as e:
            logger.debug(f"Failed to list GCP secrets: {e}")
            return []


__all__ = [
    "SecretsBackend",
    "SecretsBackendError",
    "SecretNotFoundError",
    "BackendUnavailableError",
    "EnvVarBackend",
    "DotEnvBackend",
    "AppleKeychainBackend",
    "HashiCorpVaultBackend",
    "AWSSecretsManagerBackend",
    "AzureKeyVaultBackend",
    "GCPSecretManagerBackend",
]
