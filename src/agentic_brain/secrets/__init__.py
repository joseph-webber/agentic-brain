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
Secrets management module for agentic-brain.

Provides secure credential handling with multiple backend support:
- Environment variables (simple, dev-friendly)
- .env files
- macOS Keychain (native Apple security)
- HashiCorp Vault (enterprise standard)
- AWS Secrets Manager
- Azure Key Vault
- Google Cloud Secret Manager

Quick Start:
    >>> from agentic_brain.secrets import SecretsManager
    >>>
    >>> # Auto-configure based on environment
    >>> manager = SecretsManager.from_config()
    >>> api_key = await manager.get("OPENAI_API_KEY")
    >>>
    >>> # Require a secret (raises if not found)
    >>> db_pass = await manager.require("DB_PASSWORD")

Legacy Interface:
    >>> from agentic_brain.secrets import BotSecrets
    >>>
    >>> secrets = BotSecrets()
    >>> api_key = secrets.get("OPENAI_API_KEY")
"""

from agentic_brain.secrets.backends import (
    AppleKeychainBackend,
    AWSSecretsManagerBackend,
    AzureKeyVaultBackend,
    BackendUnavailableError,
    DotEnvBackend,
    EnvVarBackend,
    GCPSecretManagerBackend,
    HashiCorpVaultBackend,
    SecretNotFoundError,
    SecretsBackend,
    SecretsBackendError,
)
from agentic_brain.secrets.manager import (
    KEYRING_AVAILABLE,
    BotSecrets,
    SecretsManager,
)

__all__ = [
    # Main classes
    "SecretsManager",
    "BotSecrets",
    # Base class and exceptions
    "SecretsBackend",
    "SecretsBackendError",
    "SecretNotFoundError",
    "BackendUnavailableError",
    # Backends
    "EnvVarBackend",
    "DotEnvBackend",
    "AppleKeychainBackend",
    "HashiCorpVaultBackend",
    "AWSSecretsManagerBackend",
    "AzureKeyVaultBackend",
    "GCPSecretManagerBackend",
    # Constants
    "KEYRING_AVAILABLE",
]
