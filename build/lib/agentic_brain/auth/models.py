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
Authentication models following JHipster's domain patterns.

Provides User, Token, and Credentials classes with Pydantic validation.
"""

from datetime import UTC, datetime, timezone
from enum import Enum, StrEnum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuthMethod(StrEnum):
    """Authentication methods."""

    JWT = "jwt"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    SESSION = "session"
    API_KEY = "api_key"
    ANONYMOUS = "anonymous"


class User(BaseModel):
    """
    User model following JHipster's User entity.

    Represents an authenticated user with their authorities.
    """

    id: Optional[str] = None
    login: str
    email: Optional[str] = None  # Email validation optional
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    image_url: Optional[str] = None
    activated: bool = True
    lang_key: str = "en"
    authorities: list[str] = Field(default_factory=list)
    created_by: Optional[str] = None
    created_date: Optional[datetime] = None
    last_modified_by: Optional[str] = None
    last_modified_date: Optional[datetime] = None

    # Additional fields for agentic brain
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """Get the user's full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.login

    def has_authority(self, authority: str) -> bool:
        """Check if user has a specific authority."""
        return authority in self.authorities

    def has_any_authority(self, *authorities: str) -> bool:
        """Check if user has any of the specified authorities."""
        return any(auth in self.authorities for auth in authorities)

    def has_all_authorities(self, *authorities: str) -> bool:
        """Check if user has all of the specified authorities."""
        return all(auth in self.authorities for auth in authorities)

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role (with ROLE_ prefix)."""
        role_name = role if role.startswith("ROLE_") else f"ROLE_{role}"
        return role_name in self.authorities

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "user-123",
                "login": "johndoe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "activated": True,
                "authorities": ["ROLE_USER", "ROLE_ADMIN"],
            }
        }
    )


class Token(BaseModel):
    """
    Token model representing authentication credentials.

    Can represent JWT tokens, session tokens, or refresh tokens.
    """

    access_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None

    # Token metadata
    issued_at: Optional[datetime] = None
    issuer: Optional[str] = None
    subject: Optional[str] = None
    audience: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if self.expires_at is None:
            return False
        now = datetime.now(UTC)
        # Handle both aware and naive datetimes
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return now > expires

    @property
    def authorization_header(self) -> str:
        """Get the Authorization header value."""
        return f"{self.token_type} {self.access_token}"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzUxMiJ9...",
                "token_type": "Bearer",
                "expires_in": 86400,
            }
        }
    )


class Credentials(BaseModel):
    """Base credentials model."""

    pass


class UsernamePasswordCredentials(Credentials):
    """Username/password credentials for Basic or Form auth."""

    username: str
    password: str
    remember_me: bool = False


class TokenCredentials(Credentials):
    """Token-based credentials for JWT or OAuth2."""

    token: str
    token_type: str = "Bearer"


class RefreshTokenCredentials(Credentials):
    """Refresh token credentials."""

    refresh_token: str


class OAuth2AuthorizationCode(Credentials):
    """OAuth2 authorization code grant credentials."""

    code: str
    redirect_uri: str
    code_verifier: Optional[str] = None  # For PKCE


class ApiKeyCredentials(Credentials):
    """API key credentials."""

    api_key: str


class SessionCredentials(Credentials):
    """Session-based credentials."""

    session_id: str
    remember_me_token: Optional[str] = None


class AuthenticationResult(BaseModel):
    """Result of an authentication attempt."""

    success: bool
    user: Optional[User] = None
    token: Optional[Token] = None
    error: Optional[str] = None
    error_description: Optional[str] = None
    auth_method: Optional[AuthMethod] = None

    @classmethod
    def failed(
        cls, error: str, error_description: Optional[str] = None
    ) -> "AuthenticationResult":
        """Create a failed authentication result."""
        return cls(success=False, error=error, error_description=error_description)

    @classmethod
    def successful(
        cls,
        user: User,
        token: Optional[Token] = None,
        auth_method: Optional[AuthMethod] = None,
    ) -> "AuthenticationResult":
        """Create a successful authentication result."""
        return cls(success=True, user=user, token=token, auth_method=auth_method)


class SecurityContext(BaseModel):
    """
    Security context holding current authentication state.

    Thread-local storage pattern for accessing current user.
    """

    user: Optional[User] = None
    token: Optional[Token] = None
    auth_method: Optional[AuthMethod] = None
    authenticated: bool = False
    session_id: Optional[str] = None

    @classmethod
    def anonymous(cls) -> "SecurityContext":
        """Create an anonymous security context."""
        return cls(
            user=User(
                login="anonymousUser",
                authorities=["ROLE_ANONYMOUS"],
            ),
            auth_method=AuthMethod.ANONYMOUS,
            authenticated=False,
        )

    @classmethod
    def from_user(
        cls,
        user: User,
        token: Optional[Token] = None,
        auth_method: Optional[AuthMethod] = None,
    ) -> "SecurityContext":
        """Create a security context from a user."""
        return cls(
            user=user,
            token=token,
            auth_method=auth_method,
            authenticated=True,
        )
