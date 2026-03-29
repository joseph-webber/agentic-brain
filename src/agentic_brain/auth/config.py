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
Type-safe authentication configuration.

Follows JHipster's application.yml pattern with dataclasses for validation.
Supports environment variable overrides and sensible defaults.
"""

import os
import secrets
from dataclasses import dataclass, field
from typing import Optional

from agentic_brain.auth.constants import (
    DEFAULT_JWT_ALGORITHM,
    DEFAULT_JWT_EXPIRY_SECONDS,
    DEFAULT_REFRESH_TOKEN_EXPIRY_SECONDS,
    PASSWORD_ENCODER_BCRYPT,
    REMEMBER_ME_TIMEOUT_SECONDS,
    SESSION_TIMEOUT_SECONDS,
)


@dataclass
class JWTConfig:
    """JWT-specific configuration."""

    secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", ""))
    base64_secret: str = field(
        default_factory=lambda: os.getenv("JWT_BASE64_SECRET", "")
    )
    algorithm: str = field(
        default_factory=lambda: os.getenv("JWT_ALGORITHM", DEFAULT_JWT_ALGORITHM)
    )
    token_validity_seconds: int = field(
        default_factory=lambda: int(
            os.getenv("JWT_TOKEN_VALIDITY_SECONDS", str(DEFAULT_JWT_EXPIRY_SECONDS))
        )
    )
    token_validity_seconds_for_remember_me: int = field(
        default_factory=lambda: int(
            os.getenv(
                "JWT_REMEMBER_ME_VALIDITY_SECONDS",
                str(DEFAULT_REFRESH_TOKEN_EXPIRY_SECONDS),
            )
        )
    )
    issuer: str = field(
        default_factory=lambda: os.getenv("JWT_ISSUER", "agentic-brain")
    )
    audience: str = field(
        default_factory=lambda: os.getenv("JWT_AUDIENCE", "agentic-brain")
    )

    def __post_init__(self) -> None:
        """Validate JWT configuration."""
        if not self.secret and not self.base64_secret:
            # Generate a random secret for development
            self.secret = secrets.token_hex(64)

    def get_secret_bytes(self) -> bytes:
        """Get the secret as bytes, handling base64 encoding."""
        import base64

        if self.base64_secret:
            return base64.b64decode(self.base64_secret)
        return self.secret.encode("utf-8")


@dataclass
class OAuth2Config:
    """OAuth2/OIDC configuration."""

    enabled: bool = field(
        default_factory=lambda: os.getenv("OAUTH2_ENABLED", "false").lower() == "true"
    )
    issuer_uri: str = field(default_factory=lambda: os.getenv("OAUTH2_ISSUER_URI", ""))
    client_id: str = field(default_factory=lambda: os.getenv("OAUTH2_CLIENT_ID", ""))
    client_secret: str = field(
        default_factory=lambda: os.getenv("OAUTH2_CLIENT_SECRET", "")
    )
    audience: str = field(default_factory=lambda: os.getenv("OAUTH2_AUDIENCE", ""))
    scopes: list[str] = field(
        default_factory=lambda: os.getenv(
            "OAUTH2_SCOPES", "openid,profile,email"
        ).split(",")
    )
    authorization_uri: str = field(
        default_factory=lambda: os.getenv("OAUTH2_AUTHORIZATION_URI", "")
    )
    token_uri: str = field(default_factory=lambda: os.getenv("OAUTH2_TOKEN_URI", ""))
    userinfo_uri: str = field(
        default_factory=lambda: os.getenv("OAUTH2_USERINFO_URI", "")
    )
    jwks_uri: str = field(default_factory=lambda: os.getenv("OAUTH2_JWKS_URI", ""))

    # Claim mapping (OIDC claim -> internal field)
    claim_mapping: dict[str, str] = field(
        default_factory=lambda: {
            "sub": "id",
            "preferred_username": "login",
            "email": "email",
            "given_name": "first_name",
            "family_name": "last_name",
            "picture": "image_url",
            "locale": "lang_key",
        }
    )


@dataclass
class SessionConfig:
    """Session-based authentication configuration."""

    enabled: bool = field(
        default_factory=lambda: os.getenv("SESSION_AUTH_ENABLED", "false").lower()
        == "true"
    )
    timeout_seconds: int = field(
        default_factory=lambda: int(
            os.getenv("SESSION_TIMEOUT_SECONDS", str(SESSION_TIMEOUT_SECONDS))
        )
    )
    cookie_name: str = field(
        default_factory=lambda: os.getenv("SESSION_COOKIE_NAME", "AGENTIC_SESSION")
    )
    cookie_secure: bool = field(
        default_factory=lambda: os.getenv("SESSION_COOKIE_SECURE", "true").lower()
        == "true"
    )
    cookie_httponly: bool = field(
        default_factory=lambda: os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower()
        == "true"
    )
    cookie_samesite: str = field(
        default_factory=lambda: os.getenv("SESSION_COOKIE_SAMESITE", "lax")
    )

    # Remember me configuration
    remember_me_enabled: bool = field(
        default_factory=lambda: os.getenv("REMEMBER_ME_ENABLED", "true").lower()
        == "true"
    )
    remember_me_timeout_seconds: int = field(
        default_factory=lambda: int(
            os.getenv("REMEMBER_ME_TIMEOUT_SECONDS", str(REMEMBER_ME_TIMEOUT_SECONDS))
        )
    )
    remember_me_key: str = field(
        default_factory=lambda: os.getenv("REMEMBER_ME_KEY", secrets.token_hex(32))
    )


@dataclass
class BasicAuthConfig:
    """HTTP Basic authentication configuration."""

    enabled: bool = field(
        default_factory=lambda: os.getenv("BASIC_AUTH_ENABLED", "false").lower()
        == "true"
    )
    realm: str = field(
        default_factory=lambda: os.getenv("BASIC_AUTH_REALM", "agentic-brain")
    )


@dataclass
class PasswordConfig:
    """Password encoding configuration."""

    encoder: str = field(
        default_factory=lambda: os.getenv("PASSWORD_ENCODER", PASSWORD_ENCODER_BCRYPT)
    )
    bcrypt_rounds: int = field(
        default_factory=lambda: int(os.getenv("BCRYPT_ROUNDS", "12"))
    )
    argon2_memory_cost: int = field(
        default_factory=lambda: int(os.getenv("ARGON2_MEMORY_COST", "65536"))
    )
    argon2_time_cost: int = field(
        default_factory=lambda: int(os.getenv("ARGON2_TIME_COST", "3"))
    )
    argon2_parallelism: int = field(
        default_factory=lambda: int(os.getenv("ARGON2_PARALLELISM", "4"))
    )


@dataclass
class AuthConfig:
    """
    Main authentication configuration container.

    Mirrors JHipster's SecurityConfiguration with type-safe Python dataclasses.

    Example:
        config = AuthConfig()
        # Or with explicit values
        config = AuthConfig(
            jwt=JWTConfig(secret="my-secret"),
            oauth2=OAuth2Config(enabled=True, issuer_uri="https://...")
        )
    """

    # Enable/disable authentication globally
    enabled: bool = field(
        default_factory=lambda: os.getenv("AUTH_ENABLED", "false").lower() == "true"
    )

    # Sub-configurations
    jwt: JWTConfig = field(default_factory=JWTConfig)
    oauth2: OAuth2Config = field(default_factory=OAuth2Config)
    session: SessionConfig = field(default_factory=SessionConfig)
    basic: BasicAuthConfig = field(default_factory=BasicAuthConfig)
    password: PasswordConfig = field(default_factory=PasswordConfig)

    # API keys for service-to-service auth
    api_keys: list[str] = field(
        default_factory=lambda: [
            k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()
        ]
    )

    # Public paths that don't require authentication
    public_paths: list[str] = field(
        default_factory=lambda: [
            "/health",
            "/health/",
            "/ready",
            "/ready/",
            "/metrics",
            "/docs",
            "/docs/",
            "/openapi.json",
            "/redoc",
            "/redoc/",
        ]
    )

    # CORS configuration
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(",")
    )
    cors_methods: list[str] = field(
        default_factory=lambda: os.getenv(
            "CORS_METHODS", "GET,POST,PUT,DELETE,OPTIONS"
        ).split(",")
    )
    cors_headers: list[str] = field(
        default_factory=lambda: os.getenv("CORS_HEADERS", "*").split(",")
    )

    def is_public_path(self, path: str) -> bool:
        """Check if a path is public (doesn't require authentication)."""
        return any(path.startswith(p.rstrip("/")) for p in self.public_paths)

    def validate_api_key(self, key: str) -> bool:
        """
        Validate an API key using constant-time comparison.

        Uses secrets.compare_digest to prevent timing attacks.
        """
        import secrets as sec

        if not key or not self.api_keys:
            return False

        # Use constant-time comparison to prevent timing attacks
        return any(sec.compare_digest(key, valid_key) for valid_key in self.api_keys)

    @classmethod
    def from_env(cls) -> "AuthConfig":
        """Create configuration from environment variables."""
        return cls()


# Global configuration instance (lazy-loaded)
_config: Optional[AuthConfig] = None


def get_auth_config() -> AuthConfig:
    """Get the global authentication configuration."""
    global _config
    if _config is None:
        _config = AuthConfig.from_env()
    return _config


def set_auth_config(config: AuthConfig) -> None:
    """Set the global authentication configuration."""
    global _config
    _config = config


def reset_auth_config() -> None:
    """Reset the global configuration (for testing)."""
    global _config
    _config = None
