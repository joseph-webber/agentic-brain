# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Enhanced JWT Refresh Token Service (JHipster-aligned).

Provides secure refresh token rotation with:
- Token family tracking (detects stolen tokens)
- Automatic revocation on reuse
- Configurable token lifetimes
- Redis-backed storage for production
- In-memory storage for development

JHipster equivalent: security/jwt/TokenProvider.java
"""

import hashlib
import logging
import secrets
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class RefreshTokenData(BaseModel):
    """Refresh token metadata stored in backend."""

    token_hash: str  # SHA-256 of token (never store raw)
    user_id: str
    user_login: str
    family_id: str  # Token family for rotation tracking
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    # Track token chain for family-based revocation
    previous_token_hash: Optional[str] = None
    replaced_by_hash: Optional[str] = None
    # Client info for security audit
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(UTC) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired, not revoked)."""
        return not self.revoked and not self.is_expired

    model_config = ConfigDict(from_attributes=True)


class RefreshTokenResult(BaseModel):
    """Result of refresh token operation."""

    success: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    error: Optional[str] = None
    error_description: Optional[str] = None

    @classmethod
    def failed(
        cls, error: str, description: Optional[str] = None
    ) -> "RefreshTokenResult":
        return cls(success=False, error=error, error_description=description)


class RefreshTokenStore(ABC):
    """
    Abstract store for refresh tokens.

    Implementations:
    - InMemoryRefreshTokenStore: Development
    - RedisRefreshTokenStore: Production
    - Neo4jRefreshTokenStore: Graph-based audit trail
    """

    @abstractmethod
    async def save(self, data: RefreshTokenData) -> bool:
        """Save refresh token data."""
        pass

    @abstractmethod
    async def get(self, token_hash: str) -> Optional[RefreshTokenData]:
        """Get refresh token data by hash."""
        pass

    @abstractmethod
    async def revoke(self, token_hash: str, reason: str = "manual") -> bool:
        """Revoke a specific token."""
        pass

    @abstractmethod
    async def revoke_family(self, family_id: str, reason: str = "security") -> int:
        """Revoke all tokens in a family (security breach)."""
        pass

    @abstractmethod
    async def revoke_user(self, user_id: str, reason: str = "logout_all") -> int:
        """Revoke all tokens for a user."""
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired tokens."""
        pass


class InMemoryRefreshTokenStore(RefreshTokenStore):
    """
    In-memory refresh token store for development.

    WARNING: Not suitable for production - loses tokens on restart.
    """

    def __init__(self) -> None:
        self._tokens: dict[str, RefreshTokenData] = {}
        self._family_index: dict[str, set[str]] = {}  # family_id -> token_hashes
        self._user_index: dict[str, set[str]] = {}  # user_id -> token_hashes

    async def save(self, data: RefreshTokenData) -> bool:
        """Save token to memory."""
        self._tokens[data.token_hash] = data

        # Update indexes
        if data.family_id not in self._family_index:
            self._family_index[data.family_id] = set()
        self._family_index[data.family_id].add(data.token_hash)

        if data.user_id not in self._user_index:
            self._user_index[data.user_id] = set()
        self._user_index[data.user_id].add(data.token_hash)

        return True

    async def get(self, token_hash: str) -> Optional[RefreshTokenData]:
        """Get token from memory."""
        return self._tokens.get(token_hash)

    async def revoke(self, token_hash: str, reason: str = "manual") -> bool:
        """Revoke a token."""
        token = self._tokens.get(token_hash)
        if token and not token.revoked:
            token.revoked = True
            token.revoked_at = datetime.now(UTC)
            token.revoked_reason = reason
            return True
        return False

    async def revoke_family(self, family_id: str, reason: str = "security") -> int:
        """Revoke all tokens in a family."""
        hashes = self._family_index.get(family_id, set())
        count = 0
        for token_hash in hashes:
            if await self.revoke(token_hash, reason):
                count += 1
        return count

    async def revoke_user(self, user_id: str, reason: str = "logout_all") -> int:
        """Revoke all tokens for a user."""
        hashes = self._user_index.get(user_id, set())
        count = 0
        for token_hash in hashes:
            if await self.revoke(token_hash, reason):
                count += 1
        return count

    async def cleanup_expired(self) -> int:
        """Remove expired tokens from memory."""
        expired_hashes = [h for h, t in self._tokens.items() if t.is_expired]
        for token_hash in expired_hashes:
            token = self._tokens.pop(token_hash, None)
            if token:
                self._family_index.get(token.family_id, set()).discard(token_hash)
                self._user_index.get(token.user_id, set()).discard(token_hash)
        return len(expired_hashes)


class RefreshTokenService:
    """
    Refresh token service with rotation and family tracking.

    Security features:
    - Token rotation: Each refresh generates new token pair
    - Family tracking: Detects and revokes stolen tokens
    - Automatic reuse detection: If old token is reused, entire family is revoked
    - Configurable lifetimes
    - Client binding (optional IP/user-agent validation)

    JHipster equivalent: security/jwt/TokenProvider.java
    """

    def __init__(
        self,
        store: Optional[RefreshTokenStore] = None,
        access_token_ttl_seconds: int = 3600,  # 1 hour
        refresh_token_ttl_seconds: int = 2592000,  # 30 days
        rotate_on_refresh: bool = True,
        bind_to_client: bool = False,
    ) -> None:
        """
        Initialize refresh token service.

        Args:
            store: Token storage backend
            access_token_ttl_seconds: Access token lifetime
            refresh_token_ttl_seconds: Refresh token lifetime
            rotate_on_refresh: Issue new refresh token on refresh
            bind_to_client: Bind tokens to client IP/user-agent
        """
        self.store = store or InMemoryRefreshTokenStore()
        self.access_token_ttl = access_token_ttl_seconds
        self.refresh_token_ttl = refresh_token_ttl_seconds
        self.rotate_on_refresh = rotate_on_refresh
        self.bind_to_client = bind_to_client

    def _hash_token(self, token: str) -> str:
        """Create SHA-256 hash of token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _generate_token(self) -> str:
        """Generate cryptographically secure random token."""
        return secrets.token_urlsafe(48)  # 384 bits of entropy

    async def create_tokens(
        self,
        user_id: str,
        user_login: str,
        generate_access_token: callable,  # Function that generates JWT
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> RefreshTokenResult:
        """
        Create new access and refresh token pair.

        Args:
            user_id: User identifier
            user_login: User login/username
            generate_access_token: Function that returns JWT given user_id
            client_ip: Client IP for binding
            user_agent: User agent for binding

        Returns:
            RefreshTokenResult with tokens
        """
        try:
            # Generate tokens
            access_token = generate_access_token(user_id)
            refresh_token = self._generate_token()
            token_hash = self._hash_token(refresh_token)
            family_id = str(uuid4())

            now = datetime.now(UTC)

            # Store refresh token metadata
            token_data = RefreshTokenData(
                token_hash=token_hash,
                user_id=user_id,
                user_login=user_login,
                family_id=family_id,
                issued_at=now,
                expires_at=now + timedelta(seconds=self.refresh_token_ttl),
                client_ip=client_ip if self.bind_to_client else None,
                user_agent=user_agent if self.bind_to_client else None,
            )

            await self.store.save(token_data)

            logger.debug(
                f"Created refresh token family {family_id} for user {user_login}"
            )

            return RefreshTokenResult(
                success=True,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=self.access_token_ttl,
            )

        except Exception as e:
            logger.error(f"Failed to create tokens: {e}")
            return RefreshTokenResult.failed("token_generation_failed", str(e))

    async def refresh(
        self,
        refresh_token: str,
        generate_access_token: callable,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> RefreshTokenResult:
        """
        Refresh tokens using a refresh token.

        Implements secure token rotation:
        1. Validate the refresh token
        2. Check for reuse attack (already rotated = revoke family)
        3. Generate new access token
        4. Generate new refresh token (if rotation enabled)
        5. Mark old token as replaced

        Args:
            refresh_token: The refresh token
            generate_access_token: Function that returns JWT given user_id
            client_ip: Client IP for validation
            user_agent: User agent for validation

        Returns:
            RefreshTokenResult with new tokens
        """
        token_hash = self._hash_token(refresh_token)
        token_data = await self.store.get(token_hash)

        # Token not found
        if not token_data:
            logger.warning("Refresh token not found - possible theft attempt")
            return RefreshTokenResult.failed("invalid_token", "Refresh token not found")

        # Token already revoked
        if token_data.revoked:
            # SECURITY: If a revoked token is reused, someone has a stolen copy
            # Revoke the entire family to be safe
            logger.warning(
                f"Revoked token reuse detected! Family {token_data.family_id} - "
                f"possible token theft"
            )
            await self.store.revoke_family(token_data.family_id, "reuse_attack")
            return RefreshTokenResult.failed(
                "token_reused",
                "Refresh token was already used. All sessions revoked for security.",
            )

        # Token expired
        if token_data.is_expired:
            return RefreshTokenResult.failed(
                "token_expired", "Refresh token has expired"
            )

        # Already rotated (replaced by another token)
        if token_data.replaced_by_hash:
            # SECURITY: Reuse attack! Revoke entire family
            logger.warning(
                f"Token reuse attack detected! Token was already rotated. "
                f"Revoking family {token_data.family_id}"
            )
            await self.store.revoke_family(token_data.family_id, "reuse_attack")
            return RefreshTokenResult.failed(
                "token_reused",
                "This refresh token was already used. All sessions revoked for security.",
            )

        # Client binding validation (if enabled)
        if self.bind_to_client:
            if client_ip and token_data.client_ip and client_ip != token_data.client_ip:
                logger.warning(
                    f"Client IP mismatch: {client_ip} vs {token_data.client_ip}"
                )
                return RefreshTokenResult.failed(
                    "client_mismatch", "Token bound to different client"
                )

        # Generate new access token
        try:
            new_access_token = generate_access_token(token_data.user_id)
        except Exception as e:
            logger.error(f"Failed to generate access token: {e}")
            return RefreshTokenResult.failed("token_generation_failed", str(e))

        # Token rotation
        new_refresh_token = refresh_token  # Default: reuse same token
        if self.rotate_on_refresh:
            new_refresh_token = self._generate_token()
            new_token_hash = self._hash_token(new_refresh_token)
            now = datetime.now(UTC)

            # Create new token in same family
            new_token_data = RefreshTokenData(
                token_hash=new_token_hash,
                user_id=token_data.user_id,
                user_login=token_data.user_login,
                family_id=token_data.family_id,  # Same family!
                issued_at=now,
                expires_at=now + timedelta(seconds=self.refresh_token_ttl),
                previous_token_hash=token_hash,
                client_ip=client_ip if self.bind_to_client else None,
                user_agent=user_agent if self.bind_to_client else None,
            )
            await self.store.save(new_token_data)

            # Mark old token as replaced (for reuse detection)
            token_data.replaced_by_hash = new_token_hash
            token_data.revoked = True
            token_data.revoked_at = now
            token_data.revoked_reason = "rotated"

            logger.debug(
                f"Rotated refresh token in family {token_data.family_id} "
                f"for user {token_data.user_login}"
            )

        return RefreshTokenResult(
            success=True,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=self.access_token_ttl,
        )

    async def revoke(self, refresh_token: str) -> bool:
        """
        Revoke a refresh token (single sign-out from device).

        Args:
            refresh_token: The refresh token to revoke

        Returns:
            True if revoked successfully
        """
        token_hash = self._hash_token(refresh_token)
        return await self.store.revoke(token_hash, "user_logout")

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        Revoke all refresh tokens for a user (global sign-out).

        Args:
            user_id: User identifier

        Returns:
            Number of tokens revoked
        """
        return await self.store.revoke_user(user_id, "global_logout")

    async def cleanup(self) -> int:
        """
        Clean up expired tokens from storage.

        Should be run periodically (e.g., daily cron).

        Returns:
            Number of tokens cleaned up
        """
        return await self.store.cleanup_expired()


# Default service instance (development mode)
_refresh_token_service: Optional[RefreshTokenService] = None


def get_refresh_token_service() -> RefreshTokenService:
    """Get or create the global refresh token service."""
    global _refresh_token_service
    if _refresh_token_service is None:
        _refresh_token_service = RefreshTokenService()
    return _refresh_token_service


def set_refresh_token_service(service: RefreshTokenService) -> None:
    """Set a custom refresh token service (e.g., with Redis store)."""
    global _refresh_token_service
    _refresh_token_service = service
