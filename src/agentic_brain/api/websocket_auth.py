# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""WebSocket Authentication Middleware with JWT validation.

This module enforces JWT authentication on WebSocket connections.
All WebSocket connections MUST provide a valid JWT token for security.

Security Features:
- Requires JWT token on all connections (production-ready)
- Validates token signature and expiration
- Rejects unauthenticated connections immediately with proper error codes
- Supports token from query params, headers, or protocol headers
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import jwt
from fastapi import WebSocket, WebSocketDisconnect, status

logger = logging.getLogger(__name__)


@dataclass
class WebSocketAuthConfig:
    """WebSocket authentication configuration."""

    secret_key: str = None
    algorithm: str = "HS256"
    require_auth: bool = True  # CRITICAL: Always require auth by default
    max_token_age: int = 3600  # Token validity in seconds

    def __post_init__(self):
        if self.secret_key is None:
            self.secret_key = os.getenv("JWT_SECRET", "")
            # CRITICAL SECURITY: In production, JWT_SECRET MUST be set
            if not self.secret_key and self.require_auth:
                # Check if running in production
                environment = os.getenv("ENVIRONMENT", "development").lower()
                if environment in ("production", "prod"):
                    # FAIL HARD in production - no default secrets allowed
                    raise ValueError(
                        "🔒 SECURITY ERROR: JWT_SECRET not configured in production! "
                        "Set JWT_SECRET environment variable before starting the server."
                    )
                else:
                    logger.warning(
                        "⚠️  JWT_SECRET not configured. WebSocket auth enforcement will be limited. "
                        "This is UNSAFE for production!"
                    )


class WebSocketAuthenticator:
    """Authenticate WebSocket connections with JWT tokens.

    Security Implementation:
    - Requires JWT token on all connections (when require_auth=True)
    - Validates token signature and expiration
    - Rejects unauthenticated connections immediately
    - Supports multiple token delivery methods for client flexibility

    Token sources (checked in order):
    1. Query parameter: ?token=<jwt>
    2. Authorization header: Authorization: Bearer <jwt>
    3. Sec-WebSocket-Protocol header (non-standard, for browser compatibility)
    """

    def __init__(self, config: Optional[WebSocketAuthConfig] = None):
        self.config = config or WebSocketAuthConfig(require_auth=True)
        if self.config.require_auth and not self.config.secret_key:
            # Try to get from env one more time
            self.config.secret_key = os.getenv("JWT_SECRET", "")
            if not self.config.secret_key:
                # Check if running in production
                environment = os.getenv("ENVIRONMENT", "development").lower()
                if environment in ("production", "prod"):
                    # FAIL HARD in production
                    raise ValueError(
                        "🔒 SECURITY ERROR: JWT_SECRET not configured in production! "
                        "WebSocket authentication cannot proceed without it."
                    )
                else:
                    logger.error(
                        "🔒 CRITICAL: JWT_SECRET not configured! "
                        "WebSocket authentication will be disabled without it!"
                    )

    async def authenticate(self, websocket: WebSocket) -> Optional[Dict[str, Any]]:
        """Authenticate a WebSocket connection with JWT validation.

        Security: Rejects connection if:
        - Authentication is required and no token provided
        - Token is invalid or expired
        - Secret key not configured (in production mode)

        Args:
            websocket: The WebSocket connection to authenticate

        Returns:
            Dict with user info if authenticated, None if connection was closed

        Raises:
            Nothing - connections are closed with proper WebSocket error codes
        """
        if not self.config.require_auth:
            logger.warning(
                "⚠️  WebSocket authentication is DISABLED. This is only safe for development!"
            )
            return {"user": "anonymous", "authenticated": False}

        # Attempt to extract token from multiple sources
        token = self._extract_token(websocket)

        if not token:
            # CRITICAL: Reject unauthenticated connections
            client_addr = websocket.client.host if websocket.client else "unknown"
            logger.warning(
                f"�� WebSocket connection REJECTED: no authentication token provided from {client_addr}"
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Authentication required: provide JWT token via ?token=<jwt> parameter or Authorization header",
            )
            return None

        # Validate the token
        validated_payload = await self._validate_token(websocket, token)
        return validated_payload

    def _extract_token(self, websocket: WebSocket) -> Optional[str]:
        """Extract JWT token from WebSocket connection using multiple methods.

        Args:
            websocket: The WebSocket connection

        Returns:
            The JWT token if found, None otherwise
        """
        # Method 1: Query parameter (standard for WebSocket)
        token = websocket.query_params.get("token")
        if token:
            logger.debug("✓ Token extracted from query parameter")
            return token

        # Method 2: Authorization header
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            logger.debug("✓ Token extracted from Authorization header")
            return token

        # Method 3: Sec-WebSocket-Protocol header (non-standard, for browser compatibility)
        protocols = websocket.headers.get("sec-websocket-protocol", "")
        if protocols:
            for part in protocols.split(","):
                part = part.strip()
                # Check if it looks like a JWT (3 parts separated by dots)
                if len(part.split(".")) == 3:
                    logger.debug("✓ Token extracted from Sec-WebSocket-Protocol header")
                    return part

        return None

    async def _validate_token(
        self, websocket: WebSocket, token: str
    ) -> Optional[Dict[str, Any]]:
        """Validate JWT token signature and expiration.

        Args:
            websocket: The WebSocket connection
            token: The JWT token to validate

        Returns:
            Dict with user info if valid, None if validation failed (connection closed)
        """
        try:
            # Validate JWT signature and expiration
            payload = jwt.decode(
                token, self.config.secret_key, algorithms=[self.config.algorithm]
            )
            user_id = payload.get("sub", "unknown")
            client_addr = websocket.client.host if websocket.client else "unknown"
            logger.info(
                f"✓ WebSocket authenticated for user: {user_id} from {client_addr}"
            )
            return {
                "user": user_id,
                "authenticated": True,
                "payload": payload,
                "iat": payload.get("iat", 0),
            }
        except jwt.ExpiredSignatureError:
            client_addr = websocket.client.host if websocket.client else "unknown"
            logger.warning(f"🔒 WebSocket REJECTED: token expired from {client_addr}")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Token expired: provide fresh JWT token",
            )
            return None
        except jwt.InvalidTokenError as e:
            client_addr = websocket.client.host if websocket.client else "unknown"
            logger.warning(
                f"🔒 WebSocket REJECTED: invalid token from {client_addr} - {str(e)}"
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason=f"Invalid token: {str(e)}"
            )
            return None
