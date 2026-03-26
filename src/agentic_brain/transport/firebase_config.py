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

"""Firebase configuration from environment variables.

Configuration for Firebase Realtime Database transport.
Supports both service account (server) and API key (client) authentication.
"""

import contextlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FirebaseConfig:
    """Firebase configuration.

    Load from environment variables:
    - FIREBASE_PROJECT_ID: Firebase project ID
    - FIREBASE_DATABASE_URL: Realtime Database URL (https://xxx.firebaseio.com)
    - FIREBASE_CREDENTIALS_FILE: Path to service account JSON file
    - FIREBASE_API_KEY: Optional API key for client-side auth
    - FIREBASE_APP_ID: Optional app ID
    - FIREBASE_STORAGE_BUCKET: Optional storage bucket name

    Usage:
    ```python
    from agentic_brain.transport.firebase_config import FirebaseConfig, load_firebase_config

    # Load from environment
    config = load_firebase_config()

    # Or create directly
    config = FirebaseConfig(
        project_id="my-project",
        database_url="https://my-project.firebaseio.com",
        credentials_file="/path/to/service-account.json",
    )

    # Use with transport
    from agentic_brain.transport import FirebaseTransport, TransportConfig

    transport_config = TransportConfig(
        firebase_url=config.database_url,
        firebase_credentials=config.credentials_file,
    )
    transport = FirebaseTransport(transport_config)
    ```
    """

    # Required
    project_id: str
    database_url: str

    # Server-side auth (service account)
    credentials_file: Optional[str] = None
    credentials_dict: Optional[dict[str, Any]] = None

    # Client-side auth (API key)
    api_key: Optional[str] = None

    # Optional Firebase config
    app_id: Optional[str] = None
    storage_bucket: Optional[str] = None
    messaging_sender_id: Optional[str] = None
    auth_domain: Optional[str] = None

    # Connection settings
    timeout: float = 30.0
    max_retries: int = 3

    def validate(self) -> bool:
        """Validate configuration has required fields.

        Returns:
            True if configuration is valid.

        Raises:
            ValueError: If configuration is invalid.
        """
        if not self.project_id:
            raise ValueError("project_id is required")

        if not self.database_url:
            raise ValueError("database_url is required")

        if not self.database_url.startswith("https://"):
            raise ValueError("database_url must start with https://")

        if not self.credentials_file and not self.credentials_dict and not self.api_key:
            raise ValueError(
                "Either credentials_file, credentials_dict, or api_key is required"
            )

        if self.credentials_file and not Path(self.credentials_file).exists():
            raise ValueError(f"credentials_file not found: {self.credentials_file}")

        return True

    def to_transport_config_kwargs(self) -> dict[str, Any]:
        """Get kwargs for TransportConfig.

        Returns:
            Dictionary suitable for TransportConfig initialization.
        """
        return {
            "firebase_url": self.database_url,
            "firebase_credentials": self.credentials_file,
            "timeout": self.timeout,
        }

    def to_firebase_options(self) -> dict[str, Any]:
        """Get Firebase Admin SDK options.

        Returns:
            Dictionary suitable for firebase_admin.initialize_app options.
        """
        options: dict[str, Any] = {
            "databaseURL": self.database_url,
            "projectId": self.project_id,
        }

        if self.storage_bucket:
            options["storageBucket"] = self.storage_bucket

        return options

    def to_web_config(self) -> dict[str, Any]:
        """Get web/client-side Firebase configuration.

        Suitable for JavaScript SDK initialization.

        Returns:
            Dictionary for Firebase web SDK config.
        """
        config: dict[str, Any] = {
            "projectId": self.project_id,
            "databaseURL": self.database_url,
        }

        if self.api_key:
            config["apiKey"] = self.api_key
        if self.auth_domain:
            config["authDomain"] = self.auth_domain
        if self.storage_bucket:
            config["storageBucket"] = self.storage_bucket
        if self.messaging_sender_id:
            config["messagingSenderId"] = self.messaging_sender_id
        if self.app_id:
            config["appId"] = self.app_id

        return config


def load_firebase_config(
    env_prefix: str = "FIREBASE_",
    credentials_file: Optional[str] = None,
) -> FirebaseConfig:
    """Load Firebase configuration from environment variables.

    Environment variables (with default FIREBASE_ prefix):
    - FIREBASE_PROJECT_ID: Project ID
    - FIREBASE_DATABASE_URL: Database URL
    - FIREBASE_CREDENTIALS_FILE: Path to service account JSON
    - FIREBASE_API_KEY: API key for client auth
    - FIREBASE_APP_ID: App ID
    - FIREBASE_STORAGE_BUCKET: Storage bucket
    - FIREBASE_MESSAGING_SENDER_ID: Messaging sender ID
    - FIREBASE_AUTH_DOMAIN: Auth domain

    Args:
        env_prefix: Prefix for environment variables (default: "FIREBASE_")
        credentials_file: Override credentials file path

    Returns:
        FirebaseConfig instance

    Raises:
        ValueError: If required environment variables are missing
    """

    def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(f"{env_prefix}{key}", default)

    project_id = get_env("PROJECT_ID", "")
    database_url = get_env("DATABASE_URL", "")
    creds_file = (
        credentials_file or get_env("CREDENTIALS_FILE") or get_env("CREDENTIALS")
    )

    # Try to infer project_id from database_url if not set
    if not project_id and database_url:
        # Extract from https://project-id.firebaseio.com
        with contextlib.suppress(Exception):
            project_id = database_url.replace("https://", "").split(".")[0]

    # Try to infer database_url from project_id if not set
    if not database_url and project_id:
        database_url = f"https://{project_id}.firebaseio.com"

    # Load credentials dict from file if exists
    credentials_dict = None
    if creds_file and Path(creds_file).exists():
        try:
            with open(creds_file) as f:
                credentials_dict = json.load(f)
                # Extract project_id from credentials if not set
                if not project_id and "project_id" in credentials_dict:
                    project_id = credentials_dict["project_id"]
        except Exception as e:
            logger.warning(f"Failed to load credentials file: {e}")

    # Ensure strings
    project_id_str: str = project_id or ""
    database_url_str: str = database_url or ""

    config = FirebaseConfig(
        project_id=project_id_str,
        database_url=database_url_str,
        credentials_file=creds_file,
        credentials_dict=credentials_dict,
        api_key=get_env("API_KEY"),
        app_id=get_env("APP_ID"),
        storage_bucket=get_env("STORAGE_BUCKET"),
        messaging_sender_id=get_env("MESSAGING_SENDER_ID"),
        auth_domain=get_env("AUTH_DOMAIN"),
    )

    return config


def validate_credentials_file(path: str) -> bool:
    """Validate a Firebase service account credentials file.

    Args:
        path: Path to credentials JSON file

    Returns:
        True if file is valid

    Raises:
        ValueError: If file is invalid or missing required fields
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise ValueError(f"Credentials file not found: {path}")

    try:
        with open(path_obj) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in credentials file: {e}")

    required_fields = ["type", "project_id", "private_key", "client_email"]
    missing = [f for f in required_fields if f not in data]

    if missing:
        raise ValueError(f"Missing required fields in credentials: {missing}")

    if data.get("type") != "service_account":
        raise ValueError(
            f"Invalid credentials type: {data.get('type')}, expected 'service_account'"
        )

    return True


def create_sample_config() -> str:
    """Create a sample .env configuration string.

    Returns:
        Sample environment configuration
    """
    return """# Firebase Realtime Database Configuration
# ==========================================

# Required: Firebase Project ID
FIREBASE_PROJECT_ID=your-project-id

# Required: Realtime Database URL
FIREBASE_DATABASE_URL=https://your-project-id.firebaseio.com

# Required: Path to service account credentials JSON
# Download from: Firebase Console > Project Settings > Service Accounts > Generate New Private Key
FIREBASE_CREDENTIALS_FILE=/path/to/service-account.json

# Optional: API Key for client-side auth
# Get from: Firebase Console > Project Settings > General > Web API Key
# FIREBASE_API_KEY=AIza...

# Optional: Additional configuration
# FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
# FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
# FIREBASE_MESSAGING_SENDER_ID=123456789
# FIREBASE_APP_ID=1:123456789:web:abc123
"""
