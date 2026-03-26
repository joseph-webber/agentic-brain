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

from __future__ import annotations

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Authentication module for Agentic Brain API.

Provides optional JWT and API key authentication that can be enabled via environment
variables. When AUTH_ENABLED=false (default), all endpoints are public.

Features:
- API Key authentication via header (X-API-Key) or query param (api_key)
- JWT token authentication with role-based access
- Configurable via environment variables
- Zero-config when disabled - no impact on existing code

Environment Variables:
    AUTH_ENABLED: Set to "true" to enable authentication (default: false)
    API_KEYS: Comma-separated list of valid API keys
    JWT_SECRET: Secret key for JWT token signing
    JWT_ALGORITHM: Algorithm for JWT (default: HS256)

Example:
    # Enable auth in .env:
    AUTH_ENABLED=true
    API_KEYS=key1,key2,key3
    JWT_SECRET=your-secret-key

    # Use in routes:
    from .auth import get_optional_auth, AuthContext

    @app.post("/chat")
    async def chat(auth: AuthContext = Depends(get_optional_auth)):
        if auth.authenticated:
            print(f"User: {auth.user_id}")
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery, OAuth2PasswordBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


def is_auth_enabled() -> bool:
    """Check if authentication is enabled via environment variable."""
    return os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")


def get_api_keys() -> list[str]:
    """Get list of valid API keys from environment."""
    keys_str = os.getenv("API_KEYS", "")
    if not keys_str:
        return []
    return [k.strip() for k in keys_str.split(",") if k.strip()]


def get_jwt_secret() -> str:
    """Get JWT secret from environment."""
    return os.getenv("JWT_SECRET", "")


def get_jwt_algorithm() -> str:
    """Get JWT algorithm from environment."""
    return os.getenv("JWT_ALGORITHM", "HS256")


def _get_api_key_roles(api_key: str) -> list[str]:
    """
    Get roles for a specific API key.
    
    API key roles are configured via API_KEY_ROLES environment variable.
    Format: "key1:ROLE_ADMIN,ROLE_USER;key2:ROLE_USER"
    
    Args:
        api_key: The API key to look up roles for
        
    Returns:
        List of roles for this API key, or ["ROLE_USER"] as default
    """
    roles_str = os.getenv("API_KEY_ROLES", "")
    if not roles_str:
        # Default: API keys get basic user role
        return ["ROLE_USER"]
    
    # Parse format: "key1:ROLE_ADMIN,ROLE_USER;key2:ROLE_USER"
    for entry in roles_str.split(";"):
        entry = entry.strip()
        if ":" in entry:
            key, roles_part = entry.split(":", 1)
            if key.strip() == api_key:
                return [r.strip() for r in roles_part.split(",") if r.strip()]
    
    # Key not found in config - default role
    return ["ROLE_USER"]


# =============================================================================
# Security Schemes
# =============================================================================

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)

# OAuth2 scheme for JWT - token in Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


# =============================================================================
# Models
# =============================================================================


class TokenData(BaseModel):
    """Data extracted from a valid JWT token."""

    user_id: str
    roles: list[str] = []
    exp: Optional[datetime] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_123",
                "roles": ["user", "admin"],
                "exp": "2026-12-31T23:59:59+00:00",
            }
        }
    }


class AuthContext(BaseModel):
    """Authentication context passed to route handlers."""

    authenticated: bool = False
    method: Optional[str] = None  # "api_key" or "jwt"
    user_id: Optional[str] = None
    roles: list[str] = []
    api_key: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "authenticated": True,
                "method": "jwt",
                "user_id": "user_123",
                "roles": ["user"],
                "api_key": None,
            }
        }
    }


# =============================================================================
# API Key Authentication
# =============================================================================


async def get_api_key(
    api_key_header_value: Optional[str] = Security(api_key_header),
    api_key_query_value: Optional[str] = Security(api_key_query),
) -> Optional[str]:
    """
    Validate API key from header or query parameter.

    Checks for API key in the following order:
    1. X-API-Key header
    2. api_key query parameter

    Args:
        api_key_header_value: API key from X-API-Key header
        api_key_query_value: API key from api_key query param

    Returns:
        The validated API key if valid, None otherwise

    Raises:
        HTTPException: 401 if auth is enabled and key is invalid
    """
    # Get the key from header or query
    api_key = api_key_header_value or api_key_query_value

    if not api_key:
        return None

    valid_keys = get_api_keys()

    if not valid_keys:
        logger.warning("API_KEYS environment variable not set")
        return None

    if api_key in valid_keys:
        logger.debug(f"Valid API key provided (key ending: ...{api_key[-4:]})")
        return api_key

    logger.warning(
        f"Invalid API key attempted (key ending: ...{api_key[-4:] if len(api_key) > 4 else '****'})"
    )
    return None


async def require_api_key(
    api_key_header_value: Optional[str] = Security(api_key_header),
    api_key_query_value: Optional[str] = Security(api_key_query),
) -> str:
    """
    Require a valid API key - raises 401 if invalid.

    Use this dependency when an endpoint MUST have API key auth.

    Returns:
        The validated API key

    Raises:
        HTTPException: 401 if no valid API key provided
    """
    api_key = await get_api_key(api_key_header_value, api_key_query_value)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


# =============================================================================
# JWT Authentication
# =============================================================================


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[TokenData]:
    """
    Decode and validate JWT token.

    Extracts user information from a valid JWT token. Returns None if
    no token provided or token is invalid.

    Args:
        token: JWT token from Authorization: Bearer header

    Returns:
        TokenData with user_id and roles if valid, None otherwise

    Raises:
        HTTPException: 401 if token is invalid (when auth enabled)
    """
    if not token:
        return None

    jwt_secret = get_jwt_secret()
    if not jwt_secret:
        logger.warning("JWT_SECRET not configured")
        return None

    try:
        # Import jose here to make it optional
        from jose import JWTError
        from jose import jwt as jose_jwt

        payload = jose_jwt.decode(token, jwt_secret, algorithms=[get_jwt_algorithm()])

        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            logger.warning("JWT token missing user_id/sub claim")
            return None

        roles = payload.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]

        exp = payload.get("exp")
        exp_dt = None
        if exp:
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)

        return TokenData(
            user_id=str(user_id),
            roles=roles,
            exp=exp_dt,
        )

    except ImportError:
        logger.error(
            "python-jose not installed. Install with: pip install python-jose[cryptography]"
        )
        return None
    except JWTError as e:
        logger.warning(f"JWT validation error: {e}")
        return None


async def require_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> TokenData:
    """
    Require a valid JWT token - raises 401 if invalid.

    Use this dependency when an endpoint MUST have JWT auth.

    Returns:
        TokenData with user information

    Raises:
        HTTPException: 401 if no valid token provided
    """
    user = await get_current_user(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# =============================================================================
# Combined Optional Auth (Primary Interface)
# =============================================================================


async def get_optional_auth(
    api_key_header_value: Optional[str] = Security(api_key_header),
    api_key_query_value: Optional[str] = Security(api_key_query),
    token: Optional[str] = Depends(oauth2_scheme),
) -> AuthContext:
    """
    Get authentication context - works whether auth is enabled or not.

    This is the PRIMARY dependency to use in route handlers. It:
    - Returns an empty AuthContext when AUTH_ENABLED=false
    - Validates API key and/or JWT when AUTH_ENABLED=true
    - Allows requests with no auth when auth is disabled

    Priority:
    1. JWT token (if valid, uses this)
    2. API key (if valid and no JWT)
    3. No auth (allowed when auth disabled)

    Args:
        api_key_header_value: API key from header
        api_key_query_value: API key from query
        token: JWT token from Authorization header

    Returns:
        AuthContext with authentication status and user info

    Example:
        @app.post("/chat")
        async def chat(auth: AuthContext = Depends(get_optional_auth)):
            if auth.authenticated:
                print(f"Authenticated as {auth.user_id}")
            else:
                print("Anonymous request")
    """
    # If auth is disabled, return unauthenticated context (request allowed)
    if not is_auth_enabled():
        return AuthContext(authenticated=False)

    # Try JWT first
    user = await get_current_user(token)
    if user:
        return AuthContext(
            authenticated=True,
            method="jwt",
            user_id=user.user_id,
            roles=user.roles,
        )

    # Try API key
    api_key = await get_api_key(api_key_header_value, api_key_query_value)
    if api_key:
        return AuthContext(
            authenticated=True,
            method="api_key",
            api_key=api_key,
        )

    # No valid auth provided
    return AuthContext(authenticated=False)


async def require_auth(
    api_key_header_value: Optional[str] = Security(api_key_header),
    api_key_query_value: Optional[str] = Security(api_key_query),
    token: Optional[str] = Depends(oauth2_scheme),
) -> AuthContext:
    """
    Require authentication when AUTH_ENABLED=true.

    Use this for endpoints that MUST be protected when auth is enabled.
    When auth is disabled, all requests are allowed.

    Returns:
        AuthContext with authentication info

    Raises:
        HTTPException: 401 if auth enabled and no valid credentials
    """
    context = await get_optional_auth(
        api_key_header_value,
        api_key_query_value,
        token,
    )

    # If auth is enabled, require authentication
    if is_auth_enabled() and not context.authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer, ApiKey"},
        )

    return context


# =============================================================================
# Role-based Access Control Helpers
# =============================================================================


def require_role(required_role: str):
    """
    Dependency factory for role-based access control.

    Use this to create a dependency that requires a specific role.
    Only applies when authentication is enabled.

    Args:
        required_role: The role required to access the endpoint

    Returns:
        A dependency function that validates the role

    Example:
        @app.delete("/admin/users")
        async def delete_users(
            auth: AuthContext = Depends(require_role("admin"))
        ):
            ...
    """

    async def role_checker(
        auth: AuthContext = Depends(require_auth),
    ) -> AuthContext:
        # If auth is disabled, allow all
        if not is_auth_enabled():
            return auth

        # API key auth: check if key has required role
        # API keys can be configured with roles via API_KEY_ROLES env var
        # Format: "key1:ROLE_ADMIN,ROLE_USER;key2:ROLE_USER"
        if auth.method == "api_key":
            api_key_roles = _get_api_key_roles(auth.user_id)
            if required_role not in api_key_roles and "ROLE_ADMIN" not in api_key_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API key does not have role '{required_role}'",
                )
            return auth

        # Check role for JWT auth
        if required_role not in auth.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )

        return auth

    return role_checker


# =============================================================================
# Utility Functions
# =============================================================================


def create_test_token(
    user_id: str,
    roles: list[str] = None,
    expires_in_seconds: int = 3600,
) -> str:
    """
    Create a JWT token for testing purposes.

    NOT FOR PRODUCTION USE - this is a helper for tests.

    Args:
        user_id: User ID to encode
        roles: List of roles
        expires_in_seconds: Token validity period

    Returns:
        JWT token string

    Raises:
        ImportError: If python-jose not installed
        ValueError: If JWT_SECRET not configured
    """
    from datetime import timedelta

    from jose import jwt as jose_jwt

    jwt_secret = get_jwt_secret()
    if not jwt_secret:
        raise ValueError("JWT_SECRET must be configured")

    expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    payload = {
        "sub": user_id,
        "user_id": user_id,
        "roles": roles or [],
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }

    return jose_jwt.encode(payload, jwt_secret, algorithm=get_jwt_algorithm())


__all__ = [
    # Configuration
    "is_auth_enabled",
    "get_api_keys",
    "get_jwt_secret",
    "get_jwt_algorithm",
    # Security schemes
    "API_KEY_NAME",
    "api_key_header",
    "api_key_query",
    "oauth2_scheme",
    # Models
    "TokenData",
    "AuthContext",
    # API Key auth
    "get_api_key",
    "require_api_key",
    # JWT auth
    "get_current_user",
    "require_current_user",
    # Combined auth (primary interface)
    "get_optional_auth",
    "require_auth",
    # Role-based access
    "require_role",
    # Utilities
    "create_test_token",
]
