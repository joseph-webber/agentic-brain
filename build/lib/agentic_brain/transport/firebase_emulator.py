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
Firebase Emulator Suite support for local development.

This module provides:
- Automatic emulator detection and configuration
- Connection helpers for all Firebase products
- Development/testing utilities
"""

import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class EmulatorConfig:
    """Configuration for Firebase Emulator Suite."""

    # Emulator hosts (configurable via env vars for CI/containers)
    auth_host: str = field(
        default_factory=lambda: os.environ.get("FIREBASE_AUTH_HOST", "localhost")
    )
    auth_port: int = 9099

    firestore_host: str = field(
        default_factory=lambda: os.environ.get("FIREBASE_FIRESTORE_HOST", "localhost")
    )
    firestore_port: int = 8080

    database_host: str = field(
        default_factory=lambda: os.environ.get("FIREBASE_DATABASE_HOST", "localhost")
    )
    database_port: int = 9000

    storage_host: str = field(
        default_factory=lambda: os.environ.get("FIREBASE_STORAGE_HOST", "localhost")
    )
    storage_port: int = 9199

    functions_host: str = field(
        default_factory=lambda: os.environ.get("FIREBASE_FUNCTIONS_HOST", "localhost")
    )
    functions_port: int = 5001

    pubsub_host: str = field(
        default_factory=lambda: os.environ.get("FIREBASE_PUBSUB_HOST", "localhost")
    )
    pubsub_port: int = 8085

    # Project settings
    project_id: str = "demo-project"

    @property
    def auth_url(self) -> str:
        """Get Auth emulator URL."""
        return f"http://{self.auth_host}:{self.auth_port}"

    @property
    def firestore_url(self) -> str:
        """Get Firestore emulator URL."""
        return f"{self.firestore_host}:{self.firestore_port}"

    @property
    def database_url(self) -> str:
        """Get Realtime Database emulator URL."""
        return f"http://{self.database_host}:{self.database_port}"

    @property
    def storage_url(self) -> str:
        """Get Storage emulator URL."""
        return f"http://{self.storage_host}:{self.storage_port}"

    @property
    def functions_url(self) -> str:
        """Get Functions emulator URL."""
        return f"http://{self.functions_host}:{self.functions_port}"

    @classmethod
    def from_env(cls) -> "EmulatorConfig":
        """
        Create config from environment variables.

        Reads FIREBASE_*_EMULATOR_HOST variables.
        """
        config = cls()

        # Parse emulator host env vars
        if auth := os.getenv("FIREBASE_AUTH_EMULATOR_HOST"):
            host, port = auth.rsplit(":", 1)
            config.auth_host = host
            config.auth_port = int(port)

        if firestore := os.getenv("FIRESTORE_EMULATOR_HOST"):
            host, port = firestore.rsplit(":", 1)
            config.firestore_host = host
            config.firestore_port = int(port)

        if database := os.getenv("FIREBASE_DATABASE_EMULATOR_HOST"):
            host, port = database.rsplit(":", 1)
            config.database_host = host
            config.database_port = int(port)

        if storage := os.getenv("FIREBASE_STORAGE_EMULATOR_HOST"):
            host, port = storage.rsplit(":", 1)
            config.storage_host = host
            config.storage_port = int(port)

        if functions := os.getenv("FIREBASE_FUNCTIONS_EMULATOR_HOST"):
            host, port = functions.rsplit(":", 1)
            config.functions_host = host
            config.functions_port = int(port)

        if project := os.getenv("GCLOUD_PROJECT"):
            config.project_id = project

        return config

    def to_env_dict(self) -> dict[str, str]:
        """
        Convert to environment variable dictionary.

        Returns:
            Dict of env var name -> value
        """
        return {
            "FIREBASE_AUTH_EMULATOR_HOST": f"{self.auth_host}:{self.auth_port}",
            "FIRESTORE_EMULATOR_HOST": f"{self.firestore_host}:{self.firestore_port}",
            "FIREBASE_DATABASE_EMULATOR_HOST": f"{self.database_host}:{self.database_port}",
            "FIREBASE_STORAGE_EMULATOR_HOST": f"{self.storage_host}:{self.storage_port}",
            "FIREBASE_FUNCTIONS_EMULATOR_HOST": f"{self.functions_host}:{self.functions_port}",
            "GCLOUD_PROJECT": self.project_id,
        }

    def apply_to_env(self) -> None:
        """Apply configuration to environment variables."""
        for key, value in self.to_env_dict().items():
            os.environ[key] = value
        logger.info("Applied emulator config to environment")


@dataclass
class EmulatorStatus:
    """Status of Firebase emulators."""

    auth_running: bool = False
    firestore_running: bool = False
    database_running: bool = False
    storage_running: bool = False
    functions_running: bool = False
    pubsub_running: bool = False

    @property
    def any_running(self) -> bool:
        """Check if any emulator is running."""
        return any(
            [
                self.auth_running,
                self.firestore_running,
                self.database_running,
                self.storage_running,
                self.functions_running,
                self.pubsub_running,
            ]
        )

    @property
    def all_running(self) -> bool:
        """Check if all emulators are running."""
        return all(
            [
                self.auth_running,
                self.firestore_running,
                self.database_running,
                self.storage_running,
                self.functions_running,
                self.pubsub_running,
            ]
        )

    def to_dict(self) -> dict[str, bool]:
        """Convert to dictionary."""
        return {
            "auth": self.auth_running,
            "firestore": self.firestore_running,
            "database": self.database_running,
            "storage": self.storage_running,
            "functions": self.functions_running,
            "pubsub": self.pubsub_running,
        }


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """
    Check if a port is open.

    Args:
        host: Hostname
        port: Port number
        timeout: Connection timeout

    Returns:
        True if port is open
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


class FirebaseEmulator:
    """
    Firebase Emulator Suite manager.

    Helps detect running emulators and configure clients
    to use them for local development.

    Usage:
        emulator = FirebaseEmulator()

        # Check status
        status = emulator.check_status()
        if status.firestore_running:
            # Configure Firestore client for emulator
            emulator.configure_firestore()

        # Or auto-configure everything
        emulator.auto_configure()
    """

    def __init__(self, config: Optional[EmulatorConfig] = None):
        """
        Initialize emulator manager.

        Args:
            config: Emulator configuration (auto-detected from env if None)
        """
        self.config = config or EmulatorConfig.from_env()
        self._status: Optional[EmulatorStatus] = None

    def check_status(self, refresh: bool = False) -> EmulatorStatus:
        """
        Check which emulators are running.

        Args:
            refresh: Force refresh of status

        Returns:
            EmulatorStatus with running states
        """
        if self._status and not refresh:
            return self._status

        self._status = EmulatorStatus(
            auth_running=is_port_open(self.config.auth_host, self.config.auth_port),
            firestore_running=is_port_open(
                self.config.firestore_host, self.config.firestore_port
            ),
            database_running=is_port_open(
                self.config.database_host, self.config.database_port
            ),
            storage_running=is_port_open(
                self.config.storage_host, self.config.storage_port
            ),
            functions_running=is_port_open(
                self.config.functions_host, self.config.functions_port
            ),
            pubsub_running=is_port_open(
                self.config.pubsub_host, self.config.pubsub_port
            ),
        )

        return self._status

    def is_running(self, service: str) -> bool:
        """
        Check if a specific service is running.

        Args:
            service: Service name (auth, firestore, database, storage, functions, pubsub)

        Returns:
            True if running
        """
        status = self.check_status()
        return getattr(status, f"{service}_running", False)

    def configure_auth(self) -> bool:
        """
        Configure environment for Auth emulator.

        Returns:
            True if configured
        """
        if not self.is_running("auth"):
            logger.warning("Auth emulator not running")
            return False

        os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = (
            f"{self.config.auth_host}:{self.config.auth_port}"
        )
        logger.info(f"Configured Auth emulator at {self.config.auth_url}")
        return True

    def configure_firestore(self) -> bool:
        """
        Configure environment for Firestore emulator.

        Returns:
            True if configured
        """
        if not self.is_running("firestore"):
            logger.warning("Firestore emulator not running")
            return False

        os.environ["FIRESTORE_EMULATOR_HOST"] = (
            f"{self.config.firestore_host}:{self.config.firestore_port}"
        )
        logger.info(f"Configured Firestore emulator at {self.config.firestore_url}")
        return True

    def configure_database(self) -> bool:
        """
        Configure environment for Realtime Database emulator.

        Returns:
            True if configured
        """
        if not self.is_running("database"):
            logger.warning("Database emulator not running")
            return False

        os.environ["FIREBASE_DATABASE_EMULATOR_HOST"] = (
            f"{self.config.database_host}:{self.config.database_port}"
        )
        logger.info(f"Configured Database emulator at {self.config.database_url}")
        return True

    def configure_storage(self) -> bool:
        """
        Configure environment for Storage emulator.

        Returns:
            True if configured
        """
        if not self.is_running("storage"):
            logger.warning("Storage emulator not running")
            return False

        os.environ["FIREBASE_STORAGE_EMULATOR_HOST"] = (
            f"{self.config.storage_host}:{self.config.storage_port}"
        )
        logger.info(f"Configured Storage emulator at {self.config.storage_url}")
        return True

    def auto_configure(self) -> dict[str, bool]:
        """
        Auto-configure all running emulators.

        Returns:
            Dict of service -> configured status
        """
        results = {}

        status = self.check_status(refresh=True)

        if status.auth_running:
            results["auth"] = self.configure_auth()

        if status.firestore_running:
            results["firestore"] = self.configure_firestore()

        if status.database_running:
            results["database"] = self.configure_database()

        if status.storage_running:
            results["storage"] = self.configure_storage()

        configured = sum(1 for v in results.values() if v)
        logger.info(f"Auto-configured {configured} emulators")

        return results

    def get_connection_info(self) -> dict[str, Any]:
        """
        Get connection info for all services.

        Returns:
            Dict with URLs and status for each service
        """
        status = self.check_status()

        return {
            "auth": {
                "url": self.config.auth_url,
                "running": status.auth_running,
                "env_var": "FIREBASE_AUTH_EMULATOR_HOST",
            },
            "firestore": {
                "url": self.config.firestore_url,
                "running": status.firestore_running,
                "env_var": "FIRESTORE_EMULATOR_HOST",
            },
            "database": {
                "url": self.config.database_url,
                "running": status.database_running,
                "env_var": "FIREBASE_DATABASE_EMULATOR_HOST",
            },
            "storage": {
                "url": self.config.storage_url,
                "running": status.storage_running,
                "env_var": "FIREBASE_STORAGE_EMULATOR_HOST",
            },
            "functions": {
                "url": self.config.functions_url,
                "running": status.functions_running,
                "env_var": "FIREBASE_FUNCTIONS_EMULATOR_HOST",
            },
            "project_id": self.config.project_id,
        }


# Global emulator instance
_emulator: Optional[FirebaseEmulator] = None


def get_emulator() -> FirebaseEmulator:
    """Get global emulator instance."""
    global _emulator
    if _emulator is None:
        _emulator = FirebaseEmulator()
    return _emulator


def use_emulators() -> bool:
    """
    Check if emulators should be used.

    Checks FIREBASE_USE_EMULATOR or USE_FIREBASE_EMULATOR env vars.

    Returns:
        True if emulators should be used
    """
    return os.getenv("FIREBASE_USE_EMULATOR", "").lower() in (
        "1",
        "true",
        "yes",
    ) or os.getenv("USE_FIREBASE_EMULATOR", "").lower() in ("1", "true", "yes")


def setup_emulators() -> dict[str, bool]:
    """
    Setup emulators if available.

    Call this at application startup to automatically
    configure Firebase clients for emulator use.

    Returns:
        Dict of service -> configured status
    """
    if not use_emulators():
        logger.info("Emulator mode not enabled")
        return {}

    emulator = get_emulator()
    return emulator.auto_configure()


# Test data helpers


def create_test_user(
    email: str = "test@example.com",
    password: str = "testpassword123",
    display_name: str = "Test User",
) -> dict[str, Any]:
    """
    Create a test user in Auth emulator.

    Args:
        email: User email
        password: User password
        display_name: Display name

    Returns:
        User data dict
    """
    import requests

    emulator = get_emulator()
    if not emulator.is_running("auth"):
        raise RuntimeError("Auth emulator not running")

    url = f"{emulator.config.auth_url}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key"

    response = requests.post(
        url,
        json={
            "email": email,
            "password": password,
            "displayName": display_name,
            "returnSecureToken": True,
        },
    )

    response.raise_for_status()
    return response.json()


def clear_firestore_data() -> bool:
    """
    Clear all data in Firestore emulator.

    Returns:
        True if cleared
    """
    import requests

    emulator = get_emulator()
    if not emulator.is_running("firestore"):
        return False

    url = f"http://{emulator.config.firestore_url}/emulator/v1/projects/{emulator.config.project_id}/databases/(default)/documents"

    try:
        response = requests.delete(url)
        response.raise_for_status()
        logger.info("Cleared Firestore emulator data")
        return True
    except Exception as e:
        logger.error(f"Failed to clear Firestore: {e}")
        return False


def clear_auth_users() -> bool:
    """
    Clear all users in Auth emulator.

    Returns:
        True if cleared
    """
    import requests

    emulator = get_emulator()
    if not emulator.is_running("auth"):
        return False

    url = f"{emulator.config.auth_url}/emulator/v1/projects/{emulator.config.project_id}/accounts"

    try:
        response = requests.delete(url)
        response.raise_for_status()
        logger.info("Cleared Auth emulator users")
        return True
    except Exception as e:
        logger.error(f"Failed to clear Auth users: {e}")
        return False
