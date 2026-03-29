# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Simple Authentication Service - JHipster Style.

Zero-config authentication using SQLite in-memory database.
Works with React frontend AND terminal CLI.

Usage:
    from agentic_brain.auth.demo import DemoAuthService, create_demo_router

    # Create service
    auth = DemoAuthService()

    # Add routes to FastAPI
    app.include_router(create_demo_router(auth))

    # Authenticate
    token = auth.authenticate("admin", "admin")
    user = auth.get_user_from_token(token.access_token)
"""

import os
import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# =============================================================================
# Configuration
# =============================================================================

# Dev mode detection - multiple ways to enable
DEV_MODE_ENV_VARS = ["DEV", "DEVELOPMENT", "DEBUG", "AGENTIC_DEV_MODE"]


def is_dev_mode() -> bool:
    """Check if running in development mode."""
    for var in DEV_MODE_ENV_VARS:
        val = os.getenv(var, "").lower()
        if val in ("true", "1", "yes", "dev", "development"):
            return True
    # Default to dev mode if MODE not explicitly set to prod
    mode = os.getenv("MODE", "DEV").upper()
    return mode != "PROD" and mode != "PRODUCTION"


# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))

# Password hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# =============================================================================
# Models
# =============================================================================


@dataclass
class DemoUser:
    """User model following JHipster patterns."""

    id: int
    username: str
    hashed_password: str
    authorities: list[str] = field(default_factory=list)
    activated: bool = True
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    def has_authority(self, authority: str) -> bool:
        """Check if user has specific authority."""
        return authority in self.authorities

    def has_role(self, role: str) -> bool:
        """Check if user has role (with ROLE_ prefix)."""
        role_name = role if role.startswith("ROLE_") else f"ROLE_{role}"
        return role_name in self.authorities

    def to_dict(self) -> dict:
        """Convert to dict for API response (no password)."""
        return {
            "id": self.id,
            "login": self.username,
            "email": self.email,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "activated": self.activated,
            "authorities": self.authorities,
        }


class TokenResponse(BaseModel):
    """JWT token response following JHipster format."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request body."""

    username: str
    password: str = ""
    remember_me: bool = False


class LoginHints(BaseModel):
    """Demo login hints for dev mode."""

    message: str
    demo_users: list[dict]


# =============================================================================
# Demo Auth Service
# =============================================================================


class DemoAuthService:
    """
    Simple authentication service using SQLite in-memory.

    Follows JHipster patterns for user management.
    Zero external dependencies - just works.
    """

    # Default demo users (like JHipster)
    DEMO_USERS = [
        {
            "username": "admin",
            "password": "admin",
            "authorities": ["ROLE_ADMIN", "ROLE_USER"],
            "email": "admin@localhost",
            "first_name": "Admin",
            "last_name": "Administrator",
        },
        {
            "username": "user",
            "password": "user",
            "authorities": ["ROLE_USER"],
            "email": "user@localhost",
            "first_name": "User",
            "last_name": "User",
        },
        {
            "username": "guest",
            "password": "",  # No password required
            "authorities": ["ROLE_GUEST"],
            "email": "guest@localhost",
            "first_name": "Guest",
            "last_name": "Guest",
        },
    ]

    def __init__(self, create_demo_users: bool = True):
        """Initialize with SQLite in-memory database."""
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        if create_demo_users:
            self._create_demo_users()

    def _init_db(self) -> None:
        """Create database schema."""
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                authorities TEXT NOT NULL,
                activated INTEGER DEFAULT 1,
                email TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
        )
        self.conn.commit()

    def _create_demo_users(self) -> None:
        """Create demo users like JHipster."""
        for user_data in self.DEMO_USERS:
            self.create_user(
                username=user_data["username"],
                password=user_data["password"],
                authorities=user_data["authorities"],
                email=user_data.get("email"),
                first_name=user_data.get("first_name"),
                last_name=user_data.get("last_name"),
            )

    def create_user(
        self,
        username: str,
        password: str,
        authorities: list[str],
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Optional[DemoUser]:
        """Create a new user."""
        try:
            # Hash password (empty string for guest)
            hashed = pwd_context.hash(password) if password else ""

            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO users (username, hashed_password, authorities, email, first_name, last_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    username,
                    hashed,
                    ",".join(authorities),
                    email,
                    first_name,
                    last_name,
                ),
            )
            self.conn.commit()
            return self.get_user(username)
        except sqlite3.IntegrityError:
            return None  # User already exists

    def get_user(self, username: str) -> Optional[DemoUser]:
        """Get user by username."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if row:
            return DemoUser(
                id=row["id"],
                username=row["username"],
                hashed_password=row["hashed_password"],
                authorities=row["authorities"].split(",") if row["authorities"] else [],
                activated=bool(row["activated"]),
                email=row["email"],
                first_name=row["first_name"],
                last_name=row["last_name"],
            )
        return None

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        # Guest user (empty password)
        if hashed_password == "":
            return plain_password == ""
        return pwd_context.verify(plain_password, hashed_password)

    def authenticate(
        self, username: str, password: str, remember_me: bool = False
    ) -> Optional[TokenResponse]:
        """
        Authenticate user and return JWT tokens.

        Args:
            username: User login
            password: User password (empty for guest)
            remember_me: Extend token validity

        Returns:
            TokenResponse with access and refresh tokens, or None if failed
        """
        user = self.get_user(username)
        if not user:
            return None

        if not self.verify_password(password, user.hashed_password):
            return None

        if not user.activated:
            return None

        # Create access token
        expire_minutes = (
            ACCESS_TOKEN_EXPIRE_MINUTES * 24
            if remember_me
            else ACCESS_TOKEN_EXPIRE_MINUTES
        )
        access_token = self._create_token(
            data={"sub": user.username, "auth": user.authorities},
            expires_delta=timedelta(minutes=expire_minutes),
        )

        # Create refresh token
        refresh_token = self._create_token(
            data={"sub": user.username, "type": "refresh"},
            expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )

        return TokenResponse(
            access_token=access_token,
            expires_in=expire_minutes * 60,
            refresh_token=refresh_token,
        )

    def _create_token(self, data: dict, expires_delta: timedelta) -> str:
        """Create JWT token."""
        to_encode = data.copy()
        expire = datetime.now(UTC) + expires_delta
        to_encode.update({"exp": expire, "iat": datetime.now(UTC)})
        return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def get_user_from_token(self, token: str) -> Optional[DemoUser]:
        """Get user from JWT token."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username = payload.get("sub")
            if username is None:
                return None
            return self.get_user(username)
        except JWTError:
            return None

    def refresh_token(self, refresh_token: str) -> Optional[TokenResponse]:
        """Refresh access token using refresh token."""
        try:
            payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "refresh":
                return None
            username = payload.get("sub")
            if not username:
                return None
            user = self.get_user(username)
            if not user:
                return None
            return self.authenticate(user.username, "", remember_me=False)
        except JWTError:
            return None

    def get_login_hints(self) -> Optional[LoginHints]:
        """Get demo login hints (only in dev mode)."""
        if not is_dev_mode():
            return None

        return LoginHints(
            message="Development mode - demo users available",
            demo_users=[
                {"username": "admin", "password": "admin", "role": "Administrator"},
                {"username": "user", "password": "user", "role": "User"},
                {"username": "guest", "password": "", "role": "Guest (no password)"},
            ],
        )


# =============================================================================
# FastAPI Integration
# =============================================================================

# Global service instance
_auth_service: Optional[DemoAuthService] = None


def get_demo_auth_service() -> DemoAuthService:
    """Get or create the demo auth service."""
    global _auth_service
    if _auth_service is None:
        _auth_service = DemoAuthService()
    return _auth_service


def get_current_user(token: str) -> Optional[DemoUser]:
    """Get current user from token (for dependency injection)."""
    service = get_demo_auth_service()
    return service.get_user_from_token(token)


def create_demo_router(auth_service: Optional[DemoAuthService] = None):
    """
    Create FastAPI router with auth endpoints.

    Follows JHipster endpoint naming:
    - POST /api/authenticate - Login
    - GET /api/account - Get current user
    - GET /api/login-hints - Demo credentials (dev mode only)
    - POST /api/token/refresh - Refresh token
    """
    from fastapi import APIRouter, Depends, HTTPException
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    router = APIRouter(prefix="/api", tags=["authentication"])
    security = HTTPBearer(auto_error=False)

    service = auth_service or get_demo_auth_service()

    @router.post("/authenticate", response_model=TokenResponse)
    async def authenticate(login: LoginRequest):
        """
        Authenticate user and get JWT token.

        Demo users (dev mode):
        - admin/admin - Administrator
        - user/user - Normal user
        - guest/(empty) - Guest access
        """
        result = service.authenticate(login.username, login.password, login.remember_me)
        if not result:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return result

    @router.get("/account")
    async def get_account(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ):
        """Get current authenticated user."""
        if not credentials:
            raise HTTPException(status_code=401, detail="Not authenticated")

        user = service.get_user_from_token(credentials.credentials)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        return user.to_dict()

    @router.get("/login-hints", response_model=LoginHints)
    async def login_hints():
        """
        Get demo login credentials (dev mode only).

        Returns 404 in production mode.
        """
        hints = service.get_login_hints()
        if not hints:
            raise HTTPException(status_code=404, detail="Not found")
        return hints

    @router.post("/token/refresh", response_model=TokenResponse)
    async def refresh(refresh_token: str):
        """Refresh access token using refresh token."""
        result = service.refresh_token(refresh_token)
        if not result:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        return result

    @router.get("/authorities")
    async def get_authorities(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ):
        """Get current user's authorities/roles."""
        if not credentials:
            raise HTTPException(status_code=401, detail="Not authenticated")

        user = service.get_user_from_token(credentials.credentials)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")

        return user.authorities

    return router


# =============================================================================
# CLI Support
# =============================================================================


def cli_login(username: str, password: str = "") -> Optional[str]:
    """
    Login from CLI and get access token.

    Usage:
        token = cli_login("admin", "admin")
        # Use token in Authorization header
    """
    service = get_demo_auth_service()
    result = service.authenticate(username, password)
    if result:
        return result.access_token
    return None


def cli_show_hints() -> None:
    """Print demo login hints for CLI users."""
    service = get_demo_auth_service()
    hints = service.get_login_hints()
    if hints:
        print("\n" + "=" * 50)
        print("  DEMO LOGIN CREDENTIALS")
        print("=" * 50)
        for user in hints.demo_users:
            pwd = user["password"] if user["password"] else "(no password)"
            print(f"  {user['username']:10} / {pwd:10} - {user['role']}")
        print("=" * 50 + "\n")
    else:
        print("Login hints not available (production mode)")
