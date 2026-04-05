# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Security utilities for password hashing, token comparison, and secret validation

"""
Security Utilities for Cryptographic Operations

Provides safe implementations of:
- Password hashing with bcrypt
- Constant-time comparison (timing attack prevention)
- Secure token generation
- Secret validation
"""

import hmac
import logging
import os
import secrets
from hashlib import sha256
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False
    logger.warning("bcrypt not available, using fallback hashing")


def hash_password(password: str) -> str:
    """
    Hash a password securely using bcrypt or fallback to sha256+salt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string

    Raises:
        ValueError: If password is empty
    """
    if not password:
        raise ValueError("Password cannot be empty")

    if HAS_BCRYPT:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode(), salt).decode()
    else:
        salt = secrets.token_hex(16)
        hashed = sha256(f"{password}{salt}".encode()).hexdigest()
        return f"sha256_salt${salt}${hashed}"


def verify_password(provided: str, stored: str) -> bool:
    """
    Verify a password against its hash using constant-time comparison.

    SECURITY: Uses hmac.compare_digest() to prevent timing attacks.

    Args:
        provided: Plain text password provided by user
        stored: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    if not provided or not stored:
        return False

    try:
        if stored.startswith("sha256_salt$"):
            parts = stored.split("$")
            if len(parts) != 3:
                return False
            salt = parts[1]
            stored_hash = parts[2]
            provided_hash = sha256(f"{provided}{salt}".encode()).hexdigest()
            return hmac.compare_digest(provided_hash, stored_hash)
        elif HAS_BCRYPT:
            provided_hash = bcrypt.hashpw(provided.encode(), stored.encode()).decode()
            return hmac.compare_digest(provided_hash, stored)
        else:
            return False
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.

    SECURITY: Uses hmac.compare_digest() which is timing-attack resistant.

    Args:
        a: First string (e.g., provided token)
        b: Second string (e.g., stored token)

    Returns:
        True if strings match, False otherwise
    """
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)


def generate_secure_token(nbytes: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    SECURITY: Uses secrets module which is suitable for security tokens.

    Args:
        nbytes: Number of bytes to generate (default 32 = 256 bits)

    Returns:
        URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(nbytes)


def validate_jwt_secret(secret: Optional[str] = None) -> str:
    """
    Validate JWT secret configuration.

    Ensures:
    - Secret is set
    - Secret is at least 32 characters (256 bits)
    - Secret is strong (contains variety of characters)

    Args:
        secret: JWT secret (from JWT_SECRET env var if None)

    Returns:
        Validated JWT secret

    Raises:
        ValueError: If secret is invalid or too weak
    """
    if secret is None:
        secret = os.getenv("JWT_SECRET", "")

    if not secret:
        raise ValueError(
            "JWT_SECRET environment variable not set. "
            "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    if len(secret) < 32:
        raise ValueError(
            f"JWT_SECRET too short: {len(secret)} bytes. "
            "Minimum 32 bytes required for HS256. "
            "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    # Check for variety in secret (not just repeated characters)
    unique_chars = len(set(secret))
    if unique_chars < 10:
        logger.warning(
            f"JWT_SECRET has low character variety: {unique_chars} unique characters. "
            "Consider using a stronger secret."
        )

    return secret


def validate_api_key(key: str) -> None:
    """
    Validate an API key format.

    Args:
        key: API key to validate

    Raises:
        ValueError: If API key is invalid
    """
    if not key:
        raise ValueError("API key cannot be empty")

    if len(key) < 20:
        raise ValueError(f"API key too short: {len(key)} bytes. Minimum 20 bytes required.")

    if not any(c.isupper() for c in key) or not any(c.isdigit() for c in key):
        logger.warning("API key should contain uppercase letters and digits for better entropy")


def get_secret_from_vault(key_name: str) -> Optional[str]:
    """
    Get a secret from a vault (environment variable, AWS Secrets Manager, etc).

    Designed to be extended for different vault providers.

    Args:
        key_name: Name of the secret key

    Returns:
        Secret value, or None if not found
    """
    # First try environment variables (development)
    secret = os.getenv(key_name)
    if secret:
        return secret

    # TODO: Add AWS Secrets Manager support
    # TODO: Add HashiCorp Vault support
    # TODO: Add Azure Key Vault support

    return None


def is_development_mode() -> bool:
    """Check if running in development mode."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    return env in ("development", "dev", "local")


def is_production_mode() -> bool:
    """Check if running in production mode."""
    env = os.getenv("ENVIRONMENT", "production").lower()
    return env in ("production", "prod")
