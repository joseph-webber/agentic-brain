# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Authentication for the security roles system.

Provides:
- API key based authentication
- Session management
- Admin authentication via special key or environment variable
"""

from __future__ import annotations

import hmac
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .roles import SecurityRole
from .guards import (
    SecurityGuard,
    get_security_guard,
    set_security_guard,
)

logger = logging.getLogger(__name__)

# Environment variables for authentication
ADMIN_KEY_ENV = "AGENTIC_BRAIN_ADMIN_KEY"
ADMIN_USER_ENV = "AGENTIC_BRAIN_ADMIN_USER"
DEFAULT_ADMIN_USER = "joseph"  # Joseph is always admin by default


@dataclass(slots=True)
class Session:
    """A security session with associated role."""
    
    session_id: str
    role: SecurityRole
    user_id: str | None
    created_at: datetime
    expires_at: datetime | None
    last_active: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at
    
    @property
    def is_admin(self) -> bool:
        """Check if this is an admin session."""
        return self.role == SecurityRole.FULL_ADMIN
    
    def touch(self) -> None:
        """Update last active timestamp."""
        self.last_active = datetime.now(UTC)


class SessionManager:
    """
    Manages security sessions.
    
    Provides session creation, validation, and cleanup.
    """
    
    def __init__(
        self,
        *,
        default_session_duration: timedelta = timedelta(hours=8),
        max_sessions: int = 1000,
    ):
        self._sessions: dict[str, Session] = {}
        self._default_duration = default_session_duration
        self._max_sessions = max_sessions
    
    def create_session(
        self,
        role: SecurityRole,
        *,
        user_id: str | None = None,
        duration: timedelta | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """
        Create a new session.
        
        Args:
            role: The security role for this session.
            user_id: Optional user identifier.
            duration: Session duration (None for non-expiring admin sessions).
            metadata: Additional session metadata.
            
        Returns:
            The created session.
        """
        # Cleanup old sessions if at capacity
        if len(self._sessions) >= self._max_sessions:
            self._cleanup_expired()
        
        session_id = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        
        # Admin sessions can be non-expiring if duration not specified
        expires_at = None
        if role != SecurityRole.FULL_ADMIN or duration is not None:
            expires_at = now + (duration or self._default_duration)
        
        session = Session(
            session_id=session_id,
            role=role,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
            last_active=now,
            metadata=metadata or {},
        )
        
        self._sessions[session_id] = session
        logger.info(f"Created session {session_id[:8]}... for role {role.value}")
        
        return session
    
    def get_session(self, session_id: str) -> Session | None:
        """
        Get a session by ID.
        
        Returns None if session doesn't exist or is expired.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None
        
        if session.is_expired:
            self.invalidate_session(session_id)
            return None
        
        session.touch()
        return session
    
    def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a session.
        
        Returns:
            True if session was invalidated, False if not found.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Invalidated session {session_id[:8]}...")
            return True
        return False
    
    def _cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count removed."""
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired
        ]
        for sid in expired:
            del self._sessions[sid]
        
        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired sessions")
        
        return len(expired)
    
    def get_active_sessions(self) -> list[Session]:
        """Get all non-expired sessions."""
        self._cleanup_expired()
        return list(self._sessions.values())


class AdminAuthenticator:
    """
    Authenticates admin access.
    
    Admin authentication can happen via:
    1. Environment variable AGENTIC_BRAIN_ADMIN_KEY
    2. Config file ~/.brain/admin.key
    3. Special user (joseph)
    """
    
    def __init__(self):
        self._admin_key: str | None = None
        self._admin_users: set[str] = {DEFAULT_ADMIN_USER}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load admin configuration from environment and files."""
        # From environment
        env_key = os.getenv(ADMIN_KEY_ENV)
        if env_key:
            self._admin_key = env_key
            logger.debug("Admin key loaded from environment")
        
        # From config file
        config_file = Path.home() / ".brain" / "admin.key"
        if config_file.exists() and self._admin_key is None:
            try:
                self._admin_key = config_file.read_text().strip()
                logger.debug("Admin key loaded from config file")
            except Exception as e:
                logger.warning(f"Failed to read admin key file: {e}")
        
        # Additional admin users from environment
        admin_users = os.getenv(ADMIN_USER_ENV, "")
        for user in admin_users.split(","):
            user = user.strip()
            if user:
                self._admin_users.add(user.lower())
    
    def authenticate_key(self, api_key: str) -> bool:
        """
        Check if an API key grants admin access.
        
        Uses constant-time comparison to prevent timing attacks.
        """
        if self._admin_key is None:
            env_key = os.getenv(ADMIN_KEY_ENV)
            if env_key:
                self._admin_key = env_key
        if self._admin_key is None:
            return False
        
        return hmac.compare_digest(api_key, self._admin_key)
    
    def is_admin_user(self, user_id: str) -> bool:
        """Check if a user ID is an admin."""
        return user_id.lower() in self._admin_users
    
    def generate_admin_key(self) -> str:
        """
        Generate a new admin API key.
        
        Returns:
            The generated key (should be stored securely).
        """
        key = secrets.token_urlsafe(32)
        self._admin_key = key
        logger.info("Generated new admin key")
        return key
    
    def save_admin_key(self, key: str | None = None) -> Path:
        """
        Save admin key to config file.
        
        Args:
            key: Key to save, or use current key.
            
        Returns:
            Path to the config file.
        """
        key = key or self._admin_key
        if not key:
            key = self.generate_admin_key()
        
        config_dir = Path.home() / ".brain"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = config_dir / "admin.key"
        config_file.write_text(key)
        config_file.chmod(0o600)  # Owner read/write only
        
        self._admin_key = key
        logger.info(f"Admin key saved to {config_file}")
        
        return config_file


# Global instances
_session_manager = SessionManager()
_admin_auth = AdminAuthenticator()


def get_session_manager() -> SessionManager:
    """Get the global session manager."""
    return _session_manager


def get_admin_authenticator() -> AdminAuthenticator:
    """Get the global admin authenticator."""
    return _admin_auth


def authenticate_api_key(api_key: str) -> tuple[SecurityRole, str | None]:
    """
    Authenticate an API key and return the associated role.
    
    Args:
        api_key: The API key to authenticate.
        
    Returns:
        Tuple of (role, user_id or None)
    """
    # Check for admin key
    if _admin_auth.authenticate_key(api_key):
        return SecurityRole.FULL_ADMIN, "admin"
    
    # For now, any non-admin API key gets USER role
    # In production, this would check against a database
    if api_key and len(api_key) >= 16:
        return SecurityRole.USER, None
    
    # Invalid or no key = GUEST
    return SecurityRole.GUEST, None


def authenticate_request(
    api_key: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> SecurityGuard:
    """
    Authenticate a request and return a SecurityGuard.
    
    Priority:
    1. Existing session
    2. Admin user (joseph)
    3. API key
    4. Guest (default)
    
    Args:
        api_key: Optional API key.
        user_id: Optional user identifier.
        session_id: Optional existing session ID.
        
    Returns:
        A configured SecurityGuard for the authenticated role.
    """
    # Check existing session first
    if session_id:
        session = _session_manager.get_session(session_id)
        if session:
            guard = SecurityGuard(session.role)
            set_security_guard(guard)
            return guard
    
    # Check for admin user
    if user_id and _admin_auth.is_admin_user(user_id):
        guard = SecurityGuard(SecurityRole.FULL_ADMIN)
        set_security_guard(guard)
        logger.info(f"Admin access granted to user {user_id}")
        return guard
    
    # Check API key
    if api_key:
        role, auth_user = authenticate_api_key(api_key)
        guard = SecurityGuard(role)
        set_security_guard(guard)
        return guard
    
    # Default to guest
    guard = SecurityGuard(SecurityRole.GUEST)
    set_security_guard(guard)
    return guard


def get_current_role() -> SecurityRole:
    """Get the current security role."""
    guard = get_security_guard()
    if guard is None:
        return SecurityRole.GUEST
    return guard.role


def is_admin() -> bool:
    """Check if current role is ADMIN."""
    return get_current_role() == SecurityRole.FULL_ADMIN


def is_user() -> bool:
    """Check if current role is USER or above."""
    return get_current_role() >= SecurityRole.USER


def is_guest() -> bool:
    """Check if current role is GUEST (lowest)."""
    return get_current_role() == SecurityRole.GUEST


def create_admin_session(
    user_id: str = DEFAULT_ADMIN_USER,
    **metadata: Any,
) -> Session:
    """
    Create an admin session for Joseph or other admin users.
    
    This is the easy path for Joseph to use admin mode.
    """
    if not _admin_auth.is_admin_user(user_id):
        raise ValueError(f"User {user_id} is not an admin user")
    
    return _session_manager.create_session(
        SecurityRole.FULL_ADMIN,
        user_id=user_id,
        metadata={"source": "admin_session", **metadata},
    )


def setup_admin_from_env() -> SecurityGuard | None:
    """
    Set up admin access if environment indicates admin mode.
    
    Checks:
    - AGENTIC_BRAIN_ADMIN_MODE=true
    - AGENTIC_BRAIN_ADMIN_KEY is set
    - Running as user joseph
    
    Returns:
        SecurityGuard with ADMIN role if conditions met, None otherwise.
    """
    # Check explicit admin mode flag
    admin_mode = os.getenv("AGENTIC_BRAIN_ADMIN_MODE", "").lower()
    if admin_mode in ("true", "1", "yes", "on"):
        guard = SecurityGuard(SecurityRole.FULL_ADMIN)
        set_security_guard(guard)
        logger.info("Admin mode enabled via AGENTIC_BRAIN_ADMIN_MODE")
        return guard
    
    # Check if admin key is configured
    if os.getenv(ADMIN_KEY_ENV):
        # Admin key exists but not auto-enabled - require explicit auth
        pass
    
    # Check current OS user
    import getpass
    current_user = getpass.getuser().lower()
    if current_user in _admin_auth._admin_users:
        guard = SecurityGuard(SecurityRole.FULL_ADMIN)
        set_security_guard(guard)
        logger.info(f"Admin mode enabled for user {current_user}")
        return guard
    
    return None
