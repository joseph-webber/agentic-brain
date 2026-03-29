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

"""Firebase Authentication helpers for API endpoints.

Provides server-side Firebase Auth integration with:
- JWT bearer token validation for HTTP APIs
- Role and authority extraction from custom claims
- Anonymous auth support
- User management helpers
- FastAPI dependency helpers without requiring FastAPI at import time
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Callable, Optional

from agentic_brain.auth.models import AuthenticationResult, AuthMethod, Token, User
from agentic_brain.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import auth, credentials

    FIREBASE_AUTH_AVAILABLE = True
except ImportError:
    FIREBASE_AUTH_AVAILABLE = False
    firebase_admin = None  # type: ignore[assignment]
    auth = None  # type: ignore[assignment]
    credentials = None  # type: ignore[assignment]

try:
    from fastapi import Header, HTTPException, status

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    Header = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    status = None  # type: ignore[assignment]


@dataclass(slots=True)
class FirebaseAuthConfig:
    """Configuration for Firebase API authentication."""

    project_id: Optional[str] = None
    credentials_path: Optional[str] = None
    credentials_dict: Optional[dict[str, Any]] = None
    app_name: str = "agentic-brain-auth"
    check_revoked: bool = True
    allow_anonymous: bool = False
    roles_claim: str = "roles"
    authorities_claim: str = "authorities"
    default_authorities: list[str] = field(default_factory=lambda: ["ROLE_USER"])


@dataclass(slots=True)
class FirebaseTokenClaims:
    """Normalized Firebase token claims."""

    uid: str
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    issuer: Optional[str] = None
    audience: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    auth_time: Optional[datetime] = None
    sign_in_provider: Optional[str] = None
    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def is_anonymous(self) -> bool:
        return self.sign_in_provider == "anonymous"


class FirebaseAPIAuth:
    """Firebase Authentication manager for API endpoints."""

    def __init__(self, config: Optional[FirebaseAuthConfig] = None, **kwargs: Any):
        self.config = config or FirebaseAuthConfig(**kwargs)
        self._app: Any = None
        self._initialized = False

    def _require_sdk(self) -> None:
        if not FIREBASE_AUTH_AVAILABLE:
            raise ImportError(
                "Firebase Admin SDK not installed. Install with: pip install firebase-admin"
            )

    def initialize(self) -> Any:
        self._require_sdk()
        if self._initialized and self._app is not None:
            return self._app
        try:
            self._app = firebase_admin.get_app(self.config.app_name)
            self._initialized = True
            return self._app
        except ValueError:
            pass
        options = (
            {"projectId": self.config.project_id} if self.config.project_id else None
        )
        if self.config.credentials_path:
            cred = credentials.Certificate(self.config.credentials_path)
            self._app = firebase_admin.initialize_app(
                cred,
                options=options,
                name=self.config.app_name,
            )
        elif self.config.credentials_dict:
            cred = credentials.Certificate(self.config.credentials_dict)
            self._app = firebase_admin.initialize_app(
                cred,
                options=options,
                name=self.config.app_name,
            )
        else:
            self._app = firebase_admin.initialize_app(
                options=options,
                name=self.config.app_name,
            )
        self._initialized = True
        return self._app

    @staticmethod
    def _as_datetime(epoch_value: Any) -> Optional[datetime]:
        if epoch_value is None:
            return None
        try:
            return datetime.fromtimestamp(float(epoch_value), tz=UTC)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_authority(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        return cleaned if cleaned.startswith("ROLE_") else f"ROLE_{cleaned.upper()}"

    def _extract_authorities(self, decoded_token: dict[str, Any]) -> list[str]:
        authorities: list[str] = []
        roles_value = decoded_token.get(
            self.config.roles_claim, decoded_token.get("role")
        )
        if isinstance(roles_value, str):
            authorities.append(self._normalize_authority(roles_value))
        elif isinstance(roles_value, (list, tuple, set)):
            authorities.extend(
                self._normalize_authority(str(role)) for role in roles_value
            )
        authority_value = decoded_token.get(self.config.authorities_claim)
        if isinstance(authority_value, str):
            authorities.extend(
                self._normalize_authority(part)
                for part in authority_value.split(",")
                if part.strip()
            )
        elif isinstance(authority_value, (list, tuple, set)):
            authorities.extend(
                self._normalize_authority(str(authority))
                for authority in authority_value
            )
        if not authorities:
            authorities.extend(self.config.default_authorities)
        if self._is_anonymous_claim(decoded_token):
            authorities.append("ROLE_ANONYMOUS")
        return [authority for authority in dict.fromkeys(authorities) if authority]

    @staticmethod
    def _is_anonymous_claim(decoded_token: dict[str, Any]) -> bool:
        firebase_claim = decoded_token.get("firebase", {})
        return (
            isinstance(firebase_claim, dict)
            and firebase_claim.get("sign_in_provider") == "anonymous"
        )

    def verify_token(
        self, id_token: str, check_revoked: Optional[bool] = None
    ) -> FirebaseTokenClaims:
        self.initialize()
        try:
            decoded = auth.verify_id_token(
                id_token,
                app=self._app,
                check_revoked=(
                    self.config.check_revoked
                    if check_revoked is None
                    else check_revoked
                ),
            )
        except Exception as exc:  # pragma: no cover - SDK-specific subclasses vary
            raise AuthenticationError(
                "Firebase token verification failed",
                cause=str(exc),
                fix="Provide a valid Firebase ID token or refresh the client session.",
                debug_info={"app_name": self.config.app_name},
            ) from exc
        firebase_claim = decoded.get("firebase", {})
        sign_in_provider = (
            firebase_claim.get("sign_in_provider")
            if isinstance(firebase_claim, dict)
            else None
        )
        claims = FirebaseTokenClaims(
            uid=decoded["uid"],
            email=decoded.get("email"),
            name=decoded.get("name"),
            picture=decoded.get("picture"),
            issuer=decoded.get("iss"),
            audience=decoded.get("aud"),
            issued_at=self._as_datetime(decoded.get("iat")),
            expires_at=self._as_datetime(decoded.get("exp")),
            auth_time=self._as_datetime(decoded.get("auth_time")),
            sign_in_provider=sign_in_provider,
            claims=decoded,
        )
        if claims.is_anonymous and not self.config.allow_anonymous:
            raise AuthenticationError(
                "Anonymous Firebase sign-in is disabled",
                cause="Token belongs to an anonymous Firebase user.",
                fix="Enable allow_anonymous or authenticate with a permanent Firebase account.",
            )
        return claims

    def claims_to_user(self, claims: FirebaseTokenClaims) -> User:
        display_name = (claims.name or "").strip()
        first_name = display_name.split(" ")[0] if display_name else None
        last_name = (
            " ".join(display_name.split(" ")[1:]) if " " in display_name else None
        )
        return User(
            id=claims.uid,
            login=claims.email or claims.uid,
            email=claims.email,
            first_name=first_name,
            last_name=last_name,
            image_url=claims.picture,
            activated=True,
            authorities=self._extract_authorities(claims.claims),
            created_date=claims.issued_at,
            metadata={
                "firebase_claims": claims.claims,
                "firebase_sign_in_provider": claims.sign_in_provider,
            },
        )

    def authenticate_bearer_token(
        self, authorization_header: Optional[str]
    ) -> AuthenticationResult:
        if not authorization_header:
            if self.config.allow_anonymous:
                return AuthenticationResult.successful(
                    self.create_anonymous_user(),
                    auth_method=AuthMethod.ANONYMOUS,
                )
            return AuthenticationResult.failed(
                error="missing_authorization",
                error_description="Authorization header is required.",
            )
        scheme, _, token_value = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token_value:
            return AuthenticationResult.failed(
                error="invalid_authorization_header",
                error_description="Use 'Bearer <firebase-id-token>'.",
            )
        claims = self.verify_token(token_value)
        user = self.claims_to_user(claims)
        token = Token(
            access_token=token_value,
            token_type="Bearer",
            expires_at=claims.expires_at,
            issued_at=claims.issued_at,
            issuer=claims.issuer,
            audience=claims.audience,
            subject=claims.uid,
        )
        auth_method = AuthMethod.ANONYMOUS if claims.is_anonymous else AuthMethod.OAUTH2
        return AuthenticationResult.successful(
            user=user, token=token, auth_method=auth_method
        )

    def require_roles(self, user: User, *roles: str) -> bool:
        normalized = [self._normalize_authority(role) for role in roles]
        missing = [role for role in normalized if role and not user.has_role(role)]
        if missing:
            raise PermissionError(f"Missing required roles: {', '.join(missing)}")
        return True

    def require_authorities(self, user: User, *authorities: str) -> bool:
        normalized = [self._normalize_authority(authority) for authority in authorities]
        missing = [
            authority
            for authority in normalized
            if authority and not user.has_authority(authority)
        ]
        if missing:
            raise PermissionError(f"Missing required authorities: {', '.join(missing)}")
        return True

    def create_anonymous_user(self) -> User:
        return User(
            id="anonymous",
            login="anonymous",
            activated=True,
            authorities=["ROLE_ANONYMOUS"],
            metadata={"firebase_sign_in_provider": "anonymous"},
        )

    def create_user(self, **kwargs: Any) -> User:
        self.initialize()
        record = auth.create_user(app=self._app, **kwargs)
        claims = FirebaseTokenClaims(
            uid=record.uid,
            email=getattr(record, "email", None),
            name=getattr(record, "display_name", None),
            picture=getattr(record, "photo_url", None),
            sign_in_provider=getattr(record, "provider_id", None),
            claims=getattr(record, "custom_claims", {}) or {},
        )
        return self.claims_to_user(claims)

    def update_user(self, uid: str, **kwargs: Any) -> User:
        self.initialize()
        record = auth.update_user(uid, app=self._app, **kwargs)
        claims = FirebaseTokenClaims(
            uid=record.uid,
            email=getattr(record, "email", None),
            name=getattr(record, "display_name", None),
            picture=getattr(record, "photo_url", None),
            sign_in_provider=getattr(record, "provider_id", None),
            claims=getattr(record, "custom_claims", {}) or {},
        )
        return self.claims_to_user(claims)

    def delete_user(self, uid: str) -> None:
        self.initialize()
        auth.delete_user(uid, app=self._app)

    def set_user_roles(
        self, uid: str, roles: list[str], extra_claims: Optional[dict[str, Any]] = None
    ) -> None:
        self.initialize()
        claims = dict(extra_claims or {})
        claims[self.config.roles_claim] = [
            self._normalize_authority(role) for role in roles
        ]
        auth.set_custom_user_claims(uid, claims, app=self._app)

    def fastapi_dependency(
        self,
        *,
        required_roles: Optional[list[str]] = None,
        required_authorities: Optional[list[str]] = None,
        allow_anonymous: Optional[bool] = None,
    ) -> Callable[..., User]:
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI is required to build Firebase auth dependencies")

        async def dependency(
            authorization: Optional[str] = Header(default=None, alias="Authorization"),
        ) -> User:
            original_allow = self.config.allow_anonymous
            if allow_anonymous is not None:
                self.config.allow_anonymous = allow_anonymous
            try:
                result = self.authenticate_bearer_token(authorization)
            finally:
                self.config.allow_anonymous = original_allow
            if not result.success or result.user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=result.error_description or "Authentication failed",
                )
            try:
                if required_roles:
                    self.require_roles(result.user, *required_roles)
                if required_authorities:
                    self.require_authorities(result.user, *required_authorities)
            except PermissionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=str(exc),
                ) from exc
            return result.user

        return dependency
