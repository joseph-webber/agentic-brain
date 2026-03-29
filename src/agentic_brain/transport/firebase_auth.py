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

"""Firebase Authentication integration.

Provides authentication for Firebase transports with support for:
- Service account authentication (server-side)
- Custom token generation for clients
- Token verification and refresh
- User management helpers
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Firebase Admin is optional
try:
    import firebase_admin
    from firebase_admin import auth, credentials

    FIREBASE_AUTH_AVAILABLE = True
except ImportError:
    FIREBASE_AUTH_AVAILABLE = False
    firebase_admin = None  # type: ignore
    auth = None  # type: ignore
    credentials = None  # type: ignore


@dataclass
class FirebaseUser:
    """Firebase user representation."""

    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    email_verified: bool = False
    disabled: bool = False
    provider_id: Optional[str] = None
    custom_claims: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    last_sign_in: Optional[datetime] = None

    @classmethod
    def from_firebase_user(cls, user: Any) -> "FirebaseUser":
        """Create from Firebase UserRecord.

        Args:
            user: Firebase UserRecord object.

        Returns:
            FirebaseUser instance.
        """
        return cls(
            uid=user.uid,
            email=user.email,
            display_name=user.display_name,
            photo_url=user.photo_url,
            email_verified=user.email_verified,
            disabled=user.disabled,
            provider_id=user.provider_id,
            custom_claims=user.custom_claims,
            created_at=(
                datetime.fromtimestamp(
                    user.user_metadata.creation_timestamp / 1000, tz=UTC
                )
                if user.user_metadata and user.user_metadata.creation_timestamp
                else None
            ),
            last_sign_in=(
                datetime.fromtimestamp(
                    user.user_metadata.last_sign_in_timestamp / 1000, tz=UTC
                )
                if user.user_metadata and user.user_metadata.last_sign_in_timestamp
                else None
            ),
        )


@dataclass
class TokenInfo:
    """Decoded token information."""

    uid: str
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    email_verified: bool = False
    auth_time: Optional[datetime] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    claims: Optional[dict[str, Any]] = None

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return True
        return datetime.now(UTC) > self.expires_at


class FirebaseAuth:
    """Firebase Authentication manager.

    Handles server-side authentication operations:
    - Initialize Firebase Admin SDK
    - Verify ID tokens from clients
    - Generate custom tokens for clients
    - Manage users (create, update, delete)
    - Set custom claims for authorization

    Usage:
        ```python
        from agentic_brain.transport.firebase_auth import FirebaseAuth

        # Initialize with service account
        auth = FirebaseAuth("/path/to/service-account.json")

        # Verify client token
        token_info = auth.verify_token(id_token)
        print(f"User: {token_info.uid}")

        # Generate custom token for client
        custom_token = auth.create_custom_token("user-123", {"role": "admin"})
        ```
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        credentials_dict: Optional[dict[str, Any]] = None,
        app_name: str = "[DEFAULT]",
    ):
        """Initialize Firebase Auth.

        Args:
            credentials_path: Path to service account JSON file.
            credentials_dict: Service account credentials as dict.
            app_name: Firebase app name (for multiple apps).

        Raises:
            ImportError: If firebase-admin not installed.
            ValueError: If no credentials provided.
        """
        if not FIREBASE_AUTH_AVAILABLE:
            raise ImportError(
                "Firebase Admin SDK not installed. Run: pip install firebase-admin"
            )

        self.app_name = app_name
        self._app = None

        # Initialize Firebase Admin
        try:
            # Check if app already exists
            self._app = firebase_admin.get_app(app_name)
            logger.info(f"Using existing Firebase app: {app_name}")
        except ValueError:
            # App doesn't exist, create it
            if credentials_path:
                cred = credentials.Certificate(credentials_path)
            elif credentials_dict:
                cred = credentials.Certificate(credentials_dict)
            else:
                # Try default credentials
                cred = credentials.ApplicationDefault()

            self._app = firebase_admin.initialize_app(cred, name=app_name)
            logger.info(f"Initialized Firebase app: {app_name}")

    def verify_token(
        self,
        id_token: str,
        check_revoked: bool = True,
    ) -> TokenInfo:
        """Verify a Firebase ID token.

        Args:
            id_token: The ID token to verify.
            check_revoked: Whether to check if token was revoked.

        Returns:
            TokenInfo with decoded claims.

        Raises:
            ValueError: If token is invalid or expired.
        """
        try:
            decoded = auth.verify_id_token(
                id_token,
                app=self._app,
                check_revoked=check_revoked,
            )

            return TokenInfo(
                uid=decoded["uid"],
                email=decoded.get("email"),
                name=decoded.get("name"),
                picture=decoded.get("picture"),
                email_verified=decoded.get("email_verified", False),
                auth_time=datetime.fromtimestamp(decoded["auth_time"], tz=UTC),
                issued_at=datetime.fromtimestamp(decoded["iat"], tz=UTC),
                expires_at=datetime.fromtimestamp(decoded["exp"], tz=UTC),
                claims=decoded,
            )

        except auth.InvalidIdTokenError as e:
            raise ValueError(f"Invalid token: {e}")
        except auth.ExpiredIdTokenError as e:
            raise ValueError(f"Token expired: {e}")
        except auth.RevokedIdTokenError as e:
            raise ValueError(f"Token revoked: {e}")

    def create_custom_token(
        self,
        uid: str,
        custom_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a custom token for client authentication.

        Custom tokens allow you to integrate Firebase Auth with your
        own authentication system. Send to client to sign in.

        Args:
            uid: Unique user identifier.
            custom_claims: Additional claims to include.

        Returns:
            Custom token string (valid for 1 hour).
        """
        token = auth.create_custom_token(
            uid,
            developer_claims=custom_claims,
            app=self._app,
        )

        # Token is bytes, decode to string
        if isinstance(token, bytes):
            return str(token.decode("utf-8"))
        return str(token)

    def get_user(self, uid: str) -> FirebaseUser:
        """Get user by UID.

        Args:
            uid: User identifier.

        Returns:
            FirebaseUser instance.

        Raises:
            ValueError: If user not found.
        """
        try:
            user = auth.get_user(uid, app=self._app)
            return FirebaseUser.from_firebase_user(user)
        except auth.UserNotFoundError:
            raise ValueError(f"User not found: {uid}")

    def get_user_by_email(self, email: str) -> FirebaseUser:
        """Get user by email address.

        Args:
            email: User email address.

        Returns:
            FirebaseUser instance.

        Raises:
            ValueError: If user not found.
        """
        try:
            user = auth.get_user_by_email(email, app=self._app)
            return FirebaseUser.from_firebase_user(user)
        except auth.UserNotFoundError:
            raise ValueError(f"User not found: {email}")

    def create_user(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        display_name: Optional[str] = None,
        uid: Optional[str] = None,
        email_verified: bool = False,
        disabled: bool = False,
    ) -> FirebaseUser:
        """Create a new user.

        Args:
            email: User email address.
            password: User password (min 6 chars).
            display_name: Display name.
            uid: Custom UID (auto-generated if not provided).
            email_verified: Whether email is verified.
            disabled: Whether user is disabled.

        Returns:
            Created FirebaseUser.
        """
        kwargs: dict[str, Any] = {}
        if email:
            kwargs["email"] = email
        if password:
            kwargs["password"] = password
        if display_name:
            kwargs["display_name"] = display_name
        if uid:
            kwargs["uid"] = uid
        kwargs["email_verified"] = email_verified
        kwargs["disabled"] = disabled

        user = auth.create_user(**kwargs, app=self._app)
        return FirebaseUser.from_firebase_user(user)

    def update_user(
        self,
        uid: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        display_name: Optional[str] = None,
        photo_url: Optional[str] = None,
        email_verified: Optional[bool] = None,
        disabled: Optional[bool] = None,
    ) -> FirebaseUser:
        """Update an existing user.

        Args:
            uid: User identifier.
            email: New email address.
            password: New password.
            display_name: New display name.
            photo_url: New photo URL.
            email_verified: Whether email is verified.
            disabled: Whether user is disabled.

        Returns:
            Updated FirebaseUser.
        """
        kwargs: dict[str, Any] = {}
        if email is not None:
            kwargs["email"] = email
        if password is not None:
            kwargs["password"] = password
        if display_name is not None:
            kwargs["display_name"] = display_name
        if photo_url is not None:
            kwargs["photo_url"] = photo_url
        if email_verified is not None:
            kwargs["email_verified"] = email_verified
        if disabled is not None:
            kwargs["disabled"] = disabled

        user = auth.update_user(uid, **kwargs, app=self._app)
        return FirebaseUser.from_firebase_user(user)

    def delete_user(self, uid: str) -> None:
        """Delete a user.

        Args:
            uid: User identifier.
        """
        auth.delete_user(uid, app=self._app)
        logger.info(f"Deleted user: {uid}")

    def set_custom_claims(
        self,
        uid: str,
        claims: dict[str, Any],
    ) -> None:
        """Set custom claims on a user for authorization.

        Claims are included in ID tokens and can be used for
        role-based access control.

        Args:
            uid: User identifier.
            claims: Custom claims dict (max 1000 bytes).

        Example:
            ```python
            # Set admin role
            auth.set_custom_claims("user-123", {"admin": True})

            # Set multiple roles
            auth.set_custom_claims("user-123", {
                "role": "editor",
                "tenant_id": "org-456",
            })
            ```
        """
        auth.set_custom_user_claims(uid, claims, app=self._app)
        logger.info(f"Set custom claims for user: {uid}")

    def revoke_tokens(self, uid: str) -> None:
        """Revoke all refresh tokens for a user.

        Forces user to re-authenticate on all devices.

        Args:
            uid: User identifier.
        """
        auth.revoke_refresh_tokens(uid, app=self._app)
        logger.info(f"Revoked tokens for user: {uid}")

    def list_users(
        self,
        max_results: int = 100,
        page_token: Optional[str] = None,
    ) -> tuple[list[FirebaseUser], Optional[str]]:
        """List users with pagination.

        Args:
            max_results: Maximum users per page.
            page_token: Token for next page.

        Returns:
            Tuple of (users list, next page token).
        """
        page = auth.list_users(
            max_results=max_results,
            page_token=page_token,
            app=self._app,
        )

        users = [FirebaseUser.from_firebase_user(u) for u in page.users]
        next_token = page.next_page_token

        return users, next_token

    def generate_password_reset_link(
        self,
        email: str,
        action_code_settings: Optional[dict[str, Any]] = None,
    ) -> str:
        """Generate password reset link.

        Args:
            email: User email address.
            action_code_settings: Optional action code settings.

        Returns:
            Password reset URL.
        """
        settings = None
        if action_code_settings:
            settings = auth.ActionCodeSettings(**action_code_settings)

        link = auth.generate_password_reset_link(
            email,
            action_code_settings=settings,
            app=self._app,
        )
        return str(link)

    def generate_email_verification_link(
        self,
        email: str,
        action_code_settings: Optional[dict[str, Any]] = None,
    ) -> str:
        """Generate email verification link.

        Args:
            email: User email address.
            action_code_settings: Optional action code settings.

        Returns:
            Email verification URL.
        """
        settings = None
        if action_code_settings:
            settings = auth.ActionCodeSettings(**action_code_settings)

        link = auth.generate_email_verification_link(
            email,
            action_code_settings=settings,
            app=self._app,
        )
        return str(link)


class FirebaseAuthMiddleware:
    """Middleware for verifying Firebase tokens in HTTP requests.

    Use with FastAPI, Flask, or other frameworks.

    Usage with FastAPI:
        ```python
        from fastapi import Depends, HTTPException, Header
        from agentic_brain.transport.firebase_auth import FirebaseAuthMiddleware

        auth_middleware = FirebaseAuthMiddleware("/path/to/creds.json")

        async def get_current_user(
            authorization: str = Header(...),
        ) -> TokenInfo:
            return auth_middleware.verify_request(authorization)

        @app.get("/protected")
        async def protected_route(user: TokenInfo = Depends(get_current_user)):
            return {"uid": user.uid}
        ```
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        credentials_dict: Optional[dict[str, Any]] = None,
        check_revoked: bool = True,
    ):
        """Initialize middleware.

        Args:
            credentials_path: Path to service account JSON.
            credentials_dict: Service account credentials.
            check_revoked: Whether to check revoked tokens.
        """
        self.auth = FirebaseAuth(credentials_path, credentials_dict)
        self.check_revoked = check_revoked

    def verify_request(
        self,
        authorization_header: str,
    ) -> TokenInfo:
        """Verify authorization header.

        Args:
            authorization_header: "Bearer <token>" header value.

        Returns:
            TokenInfo with user details.

        Raises:
            ValueError: If token is invalid.
        """
        if not authorization_header:
            raise ValueError("Authorization header required")

        parts = authorization_header.split()

        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise ValueError("Invalid authorization header format. Use: Bearer <token>")

        token = parts[1]
        return self.auth.verify_token(token, check_revoked=self.check_revoked)

    def require_claims(
        self,
        token_info: TokenInfo,
        required_claims: dict[str, Any],
    ) -> bool:
        """Check if token has required claims.

        Args:
            token_info: Decoded token info.
            required_claims: Claims that must match.

        Returns:
            True if all claims match.

        Raises:
            ValueError: If claims don't match.
        """
        if not token_info.claims:
            raise ValueError("Token has no claims")

        for key, value in required_claims.items():
            if token_info.claims.get(key) != value:
                raise ValueError(f"Missing or invalid claim: {key}")

        return True
