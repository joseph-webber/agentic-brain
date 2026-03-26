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

"""
Authentication providers following JHipster patterns.

Implements multiple authentication strategies:
- JWT: JSON Web Token authentication (default)
- OAuth2: OAuth2/OIDC authentication with external providers
- Basic: HTTP Basic authentication for internal/microservice use
- Session: Session-based with remember-me tokens
- API Key: Simple key-based auth for service-to-service
- LDAP: Enterprise directory authentication (stub)
- SAML: Enterprise SSO authentication (stub)

Each provider implements the AuthProvider ABC for consistency.

Security features:
- Constant-time token comparison
- No logging of sensitive data (tokens, passwords)
- JTI-based token revocation
- PKCE support for OAuth2
- State/nonce validation for CSRF protection
- Rate limiting hooks
- Audit logging hooks
- MFA/2FA hooks
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from agentic_brain.auth.config import AuthConfig, get_auth_config
from agentic_brain.auth.constants import (
    AUDIT_EVENT_LOGIN_FAILURE,
    AUDIT_EVENT_LOGIN_SUCCESS,
    AUDIT_EVENT_TOKEN_REFRESH,
    AUDIT_EVENT_TOKEN_REVOKE,
    CLAIM_AUDIENCE,
    CLAIM_AUTHORITIES,
    CLAIM_EXPIRATION,
    CLAIM_ISSUED_AT,
    CLAIM_ISSUER,
    CLAIM_JWT_ID,
    CLAIM_SUBJECT,
    OAUTH2_NONCE_EXPIRY_SECONDS,
    OAUTH2_STATE_EXPIRY_SECONDS,
    ROLE_ANONYMOUS,
)
from agentic_brain.auth.context import set_security_context
from agentic_brain.auth.models import (
    ApiKeyCredentials,
    AuthenticationResult,
    AuthMethod,
    Credentials,
    OAuth2AuthorizationCode,
    RefreshTokenCredentials,
    SecurityContext,
    SessionCredentials,
    Token,
    TokenCredentials,
    User,
    UsernamePasswordCredentials,
)
from agentic_brain.exceptions import AuthenticationError

# Logger that NEVER logs sensitive data
logger = logging.getLogger(__name__)

# Type variable for rate limiting decorators
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# Security Utilities
# =============================================================================


def _secure_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.

    Uses hmac.compare_digest which is resistant to timing analysis.
    """
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _secure_hash(value: str, key: str) -> str:
    """
    Create a secure HMAC-SHA256 hash.

    Used for token storage to prevent exposure of raw tokens.
    """
    return hmac.new(
        key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def _mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask a sensitive value for safe logging."""
    if not value or len(value) <= visible_chars:
        return "***"
    return value[:visible_chars] + "..." + "*" * 4


# =============================================================================
# Audit Logging Hook
# =============================================================================


class AuditLogger:
    """
    Audit logger for security events.

    Override this class to integrate with your audit system.
    Default implementation logs to Python logger.
    """

    def log_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        success: bool = True,
    ) -> None:
        """
        Log an audit event.

        Args:
            event_type: Type of event (see AUDIT_EVENT_* constants)
            user_id: User identifier (login or ID)
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional event details (NO SENSITIVE DATA!)
            success: Whether the event was successful
        """
        # Default: log to Python logger (no sensitive data)
        safe_details = {
            "event": event_type,
            "user_id": user_id,
            "success": success,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if ip_address:
            safe_details["ip"] = ip_address
        if details:
            # Filter out any sensitive keys
            sensitive_keys = {"password", "token", "secret", "key", "credential"}
            safe_details["details"] = {
                k: v
                for k, v in details.items()
                if not any(s in k.lower() for s in sensitive_keys)
            }

        level = logging.INFO if success else logging.WARNING
        logger.log(level, f"AUDIT: {safe_details}")


# Global audit logger instance
_audit_logger: AuditLogger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger."""
    return _audit_logger


def set_audit_logger(audit_logger: AuditLogger) -> None:
    """Set a custom audit logger."""
    global _audit_logger
    _audit_logger = audit_logger


# =============================================================================
# Rate Limiting Hook
# =============================================================================


class RateLimiter:
    """
    Rate limiter interface for authentication endpoints.

    Override this class to integrate with your rate limiting system
    (Redis, memcached, etc.). Default is in-memory (not production-ready).
    """

    def __init__(self) -> None:
        """Initialize with in-memory storage (for development only)."""
        self._attempts: dict[str, list[datetime]] = {}

    def is_rate_limited(
        self,
        key: str,
        max_attempts: int = 5,
        window_seconds: int = 300,
    ) -> bool:
        """
        Check if a key (IP, user, etc.) is rate limited.

        Args:
            key: Rate limit key (IP address, username, etc.)
            max_attempts: Maximum attempts allowed
            window_seconds: Time window in seconds

        Returns:
            True if rate limited, False otherwise
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=window_seconds)

        # Clean old attempts
        if key in self._attempts:
            self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]

        # Check limit
        attempts = self._attempts.get(key, [])
        return len(attempts) >= max_attempts

    def record_attempt(self, key: str) -> None:
        """Record an attempt for rate limiting."""
        now = datetime.now(UTC)
        if key not in self._attempts:
            self._attempts[key] = []
        self._attempts[key].append(now)

    def reset(self, key: str) -> None:
        """Reset rate limit for a key (e.g., on successful login)."""
        self._attempts.pop(key, None)


# Global rate limiter instance
_rate_limiter: RateLimiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter."""
    return _rate_limiter


def set_rate_limiter(limiter: RateLimiter) -> None:
    """Set a custom rate limiter (e.g., Redis-based)."""
    global _rate_limiter
    _rate_limiter = limiter


def rate_limit(
    key_func: Callable[..., str],
    max_attempts: int = 5,
    window_seconds: int = 300,
) -> Callable[[F], F]:
    """
    Rate limiting decorator for authentication methods.

    Args:
        key_func: Function to extract rate limit key from arguments
        max_attempts: Maximum attempts allowed
        window_seconds: Time window in seconds

    Returns:
        Decorated function that checks rate limits

    Example:
        @rate_limit(lambda self, creds: creds.username, max_attempts=5)
        async def authenticate(self, credentials):
            ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = key_func(*args, **kwargs)
            limiter = get_rate_limiter()

            if limiter.is_rate_limited(key, max_attempts, window_seconds):
                return AuthenticationResult.failed(
                    "rate_limited", "Too many attempts. Please try again later."
                )

            limiter.record_attempt(key)
            result = await func(*args, **kwargs)

            # Reset on successful authentication
            if isinstance(result, AuthenticationResult) and result.success:
                limiter.reset(key)

            return result

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# MFA/2FA Hook
# =============================================================================


class MFAProvider:
    """
    MFA provider interface.

    Override this class to integrate with your MFA system
    (TOTP, SMS, email, hardware keys, etc.).

    TODO: Implement concrete providers:
    - TOTPProvider (Google Authenticator, Authy)
    - WebAuthnProvider (hardware keys, biometrics)
    - EmailProvider
    - SMSProvider
    """

    async def is_mfa_required(self, user: User) -> bool:
        """Check if MFA is required for this user."""
        # Override to implement MFA policy
        return False

    async def generate_challenge(self, user: User) -> dict[str, Any]:
        """Generate an MFA challenge for the user."""
        raise NotImplementedError("MFA provider not configured")

    async def verify_response(
        self,
        user: User,
        challenge_id: str,
        response: str,
    ) -> bool:
        """Verify an MFA response."""
        raise NotImplementedError("MFA provider not configured")


# Global MFA provider (None = MFA disabled)
_mfa_provider: Optional[MFAProvider] = None


def get_mfa_provider() -> Optional[MFAProvider]:
    """Get the global MFA provider."""
    return _mfa_provider


def set_mfa_provider(provider: MFAProvider) -> None:
    """Set a custom MFA provider."""
    global _mfa_provider
    _mfa_provider = provider


class AuthProvider(ABC):
    """
    Abstract base class for authentication providers.

    All authentication strategies must implement this interface.

    Security notes:
    - Never log tokens, passwords, or credentials
    - Use constant-time comparison for secrets
    - Implement rate limiting via the rate_limit decorator
    - Call audit logger for security events
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """
        Initialize the provider with configuration.

        Args:
            config: Authentication configuration. If None, uses global config.
        """
        self.config = config or get_auth_config()
        self._audit = get_audit_logger()

    @abstractmethod
    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """
        Authenticate with the given credentials.

        Args:
            credentials: The credentials to authenticate.

        Returns:
            AuthenticationResult with success/failure and user info.

        Security:
            - MUST NOT log credentials
            - MUST use constant-time comparison
            - SHOULD call audit logger
        """
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> Optional[User]:
        """
        Validate a token and return the associated user.

        Args:
            token: The token to validate.

        Returns:
            The User if valid, None otherwise.

        Security:
            - MUST NOT log the token
            - MUST validate expiration
            - MUST check revocation list
        """
        pass

    async def refresh_token(self, refresh_token: str) -> Optional[Token]:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token: The refresh token.

        Returns:
            New Token if valid, None otherwise.

        Note: Not all providers support refresh tokens.
        """
        return None

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke a token.

        Args:
            token: The token to revoke.

        Returns:
            True if revoked successfully.

        Note: Not all providers support token revocation.
        """
        return False

    def _log_auth_event(
        self,
        event_type: str,
        user_id: Optional[str],
        success: bool,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log an authentication event (helper for subclasses)."""
        self._audit.log_event(
            event_type=event_type,
            user_id=user_id,
            success=success,
            details=details,
        )


class JWTAuth(AuthProvider):
    """
    JWT (JSON Web Token) authentication provider.

    Implements stateless authentication using JWTs with HS512 algorithm.
    Follows JHipster's jwt package patterns.

    Security features:
    - Token expiry validation
    - Issuer and audience validation
    - JTI-based revocation list
    - Refresh token rotation
    - Constant-time token comparison
    - No logging of token values
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """Initialize JWT auth provider."""
        super().__init__(config)
        # In-memory revocation list - TODO: Use Redis in production
        self._revoked_jtis: set[str] = set()
        # Refresh token tracking for rotation
        self._refresh_token_map: dict[str, str] = {}  # jti -> user_login

    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """
        Authenticate using credentials.

        For JWT, this typically means validating a token credential
        or generating a new token from username/password.
        """
        if isinstance(credentials, TokenCredentials):
            # Validate existing token
            user = await self.validate_token(credentials.token)
            if user:
                token = Token(
                    access_token=credentials.token,
                    token_type=credentials.token_type,
                )
                self._log_auth_event(AUDIT_EVENT_LOGIN_SUCCESS, user.login, True)
                return AuthenticationResult.successful(user, token, AuthMethod.JWT)
            self._log_auth_event(
                AUDIT_EVENT_LOGIN_FAILURE, None, False, {"reason": "invalid_token"}
            )
            return AuthenticationResult.failed(
                "invalid_token", "Token validation failed"
            )

        elif isinstance(credentials, UsernamePasswordCredentials):
            # Generate new token (actual password validation would happen elsewhere)
            # NOTE: This is a stub - real implementation should validate password
            user = User(
                login=credentials.username,
                authorities=["ROLE_USER"],
            )
            token = await self.generate_token(user, credentials.remember_me)
            self._log_auth_event(AUDIT_EVENT_LOGIN_SUCCESS, user.login, True)
            return AuthenticationResult.successful(user, token, AuthMethod.JWT)

        elif isinstance(credentials, RefreshTokenCredentials):
            # Handle refresh token
            new_token = await self.refresh_token(credentials.refresh_token)
            if new_token:
                # Decode to get user info (we trust our own tokens here)
                user = await self.validate_token(new_token.access_token)
                if user:
                    self._log_auth_event(AUDIT_EVENT_TOKEN_REFRESH, user.login, True)
                    return AuthenticationResult.successful(
                        user, new_token, AuthMethod.JWT
                    )
            return AuthenticationResult.failed(
                "invalid_refresh_token", "Refresh token invalid or expired"
            )

        return AuthenticationResult.failed(
            "unsupported_credentials", "Credential type not supported"
        )

    async def validate_token(self, token: str) -> Optional[User]:
        """
        Validate a JWT and return the user.

        Validates:
        - Signature
        - Expiration (exp)
        - Not-before (nbf) if present
        - Issuer (iss)
        - Audience (aud)
        - Revocation (jti blacklist)
        """
        try:
            # Try to import jose for JWT handling
            try:
                from jose import jwt
            except ImportError:
                # Fallback to PyJWT
                import jwt as pyjwt

                jwt = pyjwt

            secret = self.config.jwt.secret
            algorithm = self.config.jwt.algorithm

            # First, decode without verification to check revocation
            try:
                # python-jose uses different options
                unverified = jwt.decode(
                    token,
                    secret,
                    algorithms=[algorithm],
                    options={
                        "verify_exp": False,
                        "verify_aud": False,
                        "verify_iss": False,
                    },
                )
                jti = unverified.get(CLAIM_JWT_ID)
                if jti and jti in self._revoked_jtis:
                    logger.debug("Token rejected: JTI is revoked")
                    return None
            except jwt.ExpiredSignatureError:
                # This is fine for pre-check, real validation will catch it
                logger.debug("Token expired (pre-check)")
            except jwt.InvalidTokenError as e:
                # Invalid format - log and let real validation handle it
                logger.debug(f"Token format issue in pre-check: {type(e).__name__}")
            except Exception as e:
                # Unexpected error in pre-check
                logger.warning(f"Unexpected error in token pre-check: {e}")

            # Verify and decode the token properly with full validation
            payload = jwt.decode(
                token,
                secret,
                algorithms=[algorithm],
                audience=self.config.jwt.audience,
                issuer=self.config.jwt.issuer,
                options={
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "require": ["exp", "iat", "sub"],
                },
            )

            # Extract user from payload
            login = payload.get(CLAIM_SUBJECT)
            if not login:
                return None

            authorities = payload.get(CLAIM_AUTHORITIES, [])
            if isinstance(authorities, str):
                authorities = authorities.split(",")

            return User(
                id=payload.get("user_id"),
                login=login,
                email=payload.get("email"),
                first_name=payload.get("first_name"),
                last_name=payload.get("last_name"),
                authorities=authorities,
            )

        except Exception as e:
            # Log error type but NOT the token
            logger.debug(f"Token validation failed: {type(e).__name__}")
            return None

    async def generate_token(
        self,
        user: User,
        remember_me: bool = False,
        extra_claims: Optional[dict[str, Any]] = None,
    ) -> Token:
        """
        Generate a JWT token for a user.

        Args:
            user: The user to generate a token for.
            remember_me: If True, use longer expiry.
            extra_claims: Additional claims to include.

        Returns:
            A Token object with the JWT and optional refresh token.
        """
        try:
            from jose import jwt
        except ImportError:
            import jwt

        now = datetime.now(UTC)
        jti = str(uuid.uuid4())

        if remember_me:
            expiry_seconds = self.config.jwt.token_validity_seconds_for_remember_me
        else:
            expiry_seconds = self.config.jwt.token_validity_seconds

        expires_at = now + timedelta(seconds=expiry_seconds)

        payload = {
            CLAIM_SUBJECT: user.login,
            CLAIM_AUTHORITIES: ",".join(user.authorities),
            CLAIM_ISSUED_AT: now.timestamp(),
            CLAIM_EXPIRATION: expires_at.timestamp(),
            CLAIM_JWT_ID: jti,
            CLAIM_ISSUER: self.config.jwt.issuer,
            CLAIM_AUDIENCE: self.config.jwt.audience,
        }

        if user.id:
            payload["user_id"] = user.id
        if user.email:
            payload["email"] = user.email
        if user.first_name:
            payload["first_name"] = user.first_name
        if user.last_name:
            payload["last_name"] = user.last_name

        if extra_claims:
            # Filter out sensitive claims that shouldn't be added
            safe_claims = {
                k: v
                for k, v in extra_claims.items()
                if k not in ("password", "secret", "key", "credential")
            }
            payload.update(safe_claims)

        access_token = jwt.encode(
            payload,
            self.config.jwt.secret,
            algorithm=self.config.jwt.algorithm,
        )

        # Generate refresh token for token rotation
        refresh_token = None
        if remember_me:
            refresh_jti = str(uuid.uuid4())
            refresh_payload = {
                CLAIM_SUBJECT: user.login,
                CLAIM_JWT_ID: refresh_jti,
                CLAIM_ISSUED_AT: now.timestamp(),
                CLAIM_EXPIRATION: (now + timedelta(days=30)).timestamp(),
                CLAIM_ISSUER: self.config.jwt.issuer,
                "type": "refresh",
                "access_jti": jti,  # Link to access token for rotation
            }
            refresh_token = jwt.encode(
                refresh_payload,
                self.config.jwt.secret,
                algorithm=self.config.jwt.algorithm,
            )
            # Store mapping for rotation validation
            self._refresh_token_map[refresh_jti] = user.login

        return Token(
            access_token=access_token,
            token_type="Bearer",
            expires_in=expiry_seconds,
            expires_at=expires_at,
            refresh_token=refresh_token,
            issued_at=now,
            issuer=self.config.jwt.issuer,
            subject=user.login,
            audience=self.config.jwt.audience,
        )

    async def refresh_token(self, refresh_token: str) -> Optional[Token]:
        """
        Refresh an access token using a refresh token.

        Implements token rotation: old refresh token is invalidated
        and a new one is issued.
        """
        try:
            try:
                from jose import jwt
            except ImportError:
                import jwt

            payload = jwt.decode(
                refresh_token,
                self.config.jwt.secret,
                algorithms=[self.config.jwt.algorithm],
                issuer=self.config.jwt.issuer,
                options={"verify_aud": False},
            )

            # Verify it's a refresh token
            if payload.get("type") != "refresh":
                return None

            jti = payload.get(CLAIM_JWT_ID)
            login = payload.get(CLAIM_SUBJECT)

            # Check if this refresh token is still valid
            if jti not in self._refresh_token_map:
                # Token was rotated or revoked
                return None

            # Revoke the old refresh token (rotation)
            del self._refresh_token_map[jti]

            # Also revoke the linked access token
            access_jti = payload.get("access_jti")
            if access_jti:
                self._revoked_jtis.add(access_jti)

            # Generate new tokens
            user = User(login=login, authorities=["ROLE_USER"])
            return await self.generate_token(user, remember_me=True)

        except Exception as e:
            logger.debug(f"Refresh token validation failed: {type(e).__name__}")
            return None

    async def revoke_token(self, token: str) -> bool:
        """Revoke a JWT by adding its JTI to the revocation list."""
        try:
            try:
                from jose import jwt
            except ImportError:
                import jwt

            payload = jwt.decode(
                token,
                self.config.jwt.secret,
                algorithms=[self.config.jwt.algorithm],
                options={"verify_exp": False, "verify_aud": False, "verify_iss": False},
            )

            jti = payload.get(CLAIM_JWT_ID)
            if jti:
                self._revoked_jtis.add(jti)
                login = payload.get(CLAIM_SUBJECT)
                self._log_auth_event(AUDIT_EVENT_TOKEN_REVOKE, login, True)
                return True

        except Exception as e:
            logger.debug(f"Token revocation failed: {type(e).__name__}")

        return False

    def get_blacklist_count(self) -> int:
        """Get the number of revoked JTIs (for monitoring)."""
        return len(self._revoked_jtis)

    def cleanup_blacklist(self, max_age_hours: int = 24) -> int:
        """
        Clean up old entries from blacklist.

        TODO: Implement with timestamp tracking for proper cleanup.
        For now, this is a stub - in production, use Redis with TTL.
        """
        # Stub - would need to track when JTIs were added
        return 0


class OAuth2Auth(AuthProvider):
    """
    OAuth2/OIDC authentication provider.

    Supports external identity providers with audience validation
    and configurable claim mapping.

    Security features:
    - State parameter validation (CSRF protection)
    - PKCE support for public clients
    - Nonce validation for OIDC
    - Issuer validation
    - Audience validation
    - JWKS caching with TTL
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """Initialize OAuth2 auth provider."""
        super().__init__(config)
        self._jwks_cache: Optional[dict] = None
        self._jwks_cache_time: Optional[datetime] = None
        # State parameter storage for CSRF protection
        self._pending_states: dict[str, dict[str, Any]] = {}
        # Nonce storage for replay protection
        self._used_nonces: set[str] = set()

    def generate_authorization_url(
        self,
        redirect_uri: str,
        scope: Optional[str] = None,
        use_pkce: bool = True,
    ) -> tuple[str, str, Optional[str]]:
        """
        Generate OAuth2 authorization URL with state and optional PKCE.

        Args:
            redirect_uri: Callback URI
            scope: OAuth2 scopes (default from config)
            use_pkce: Whether to use PKCE (recommended for all clients)

        Returns:
            Tuple of (authorization_url, state, code_verifier)
            code_verifier is None if PKCE is disabled
        """
        import urllib.parse

        state = _generate_secure_token(32)
        nonce = _generate_secure_token(32)

        # Store state for validation
        self._pending_states[state] = {
            "redirect_uri": redirect_uri,
            "created_at": datetime.now(UTC),
            "nonce": nonce,
        }

        params = {
            "response_type": "code",
            "client_id": self.config.oauth2.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope or " ".join(self.config.oauth2.scopes),
            "state": state,
            "nonce": nonce,
        }

        code_verifier = None
        if use_pkce:
            # Generate PKCE code verifier and challenge
            code_verifier = _generate_secure_token(64)
            code_challenge = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode()).digest()
                )
                .rstrip(b"=")
                .decode()
            )
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
            self._pending_states[state]["code_verifier"] = code_verifier

        auth_uri = self.config.oauth2.authorization_uri
        url = f"{auth_uri}?{urllib.parse.urlencode(params)}"

        return url, state, code_verifier

    def validate_state(self, state: str) -> Optional[dict[str, Any]]:
        """
        Validate and consume a state parameter.

        Returns the stored state data if valid, None otherwise.
        State is consumed (can only be used once).
        """
        if state not in self._pending_states:
            logger.warning("OAuth2 state validation failed: unknown state")
            return None

        state_data = self._pending_states.pop(state)
        created_at = state_data.get("created_at")

        if created_at:
            age = (datetime.now(UTC) - created_at).total_seconds()
            if age > OAUTH2_STATE_EXPIRY_SECONDS:
                logger.warning("OAuth2 state validation failed: expired")
                return None

        return state_data

    def _validate_nonce(self, nonce: str, expected_nonce: str) -> bool:
        """
        Validate nonce from ID token against expected value.

        Prevents replay attacks and ensures the token is for this request.
        """
        if not _secure_compare(nonce, expected_nonce):
            logger.warning("OAuth2 nonce validation failed: mismatch")
            return False

        # Check if nonce was already used
        if nonce in self._used_nonces:
            logger.warning("OAuth2 nonce validation failed: replay detected")
            return False

        self._used_nonces.add(nonce)
        return True

    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """
        Authenticate using OAuth2 credentials.

        Supports:
        - TokenCredentials: Validate an ID token
        - OAuth2AuthorizationCode: Exchange auth code for tokens
        """
        if isinstance(credentials, TokenCredentials):
            user = await self.validate_token(credentials.token)
            if user:
                token = Token(
                    access_token=credentials.token,
                    token_type=credentials.token_type,
                )
                self._log_auth_event(AUDIT_EVENT_LOGIN_SUCCESS, user.login, True)
                return AuthenticationResult.successful(user, token, AuthMethod.OAUTH2)
            self._log_auth_event(AUDIT_EVENT_LOGIN_FAILURE, None, False)
            return AuthenticationResult.failed(
                "invalid_token", "Token validation failed"
            )

        elif isinstance(credentials, OAuth2AuthorizationCode):
            # Exchange authorization code for tokens
            return await self._exchange_code(credentials)

        return AuthenticationResult.failed(
            "unsupported_credentials", "Credential type not supported"
        )

    async def validate_token(self, token: str) -> Optional[User]:
        """Validate an OAuth2/OIDC token."""
        if not self.config.oauth2.enabled:
            return None

        try:
            try:
                from jose import JWTError, jwt
            except ImportError:
                import jwt as pyjwt
                from jwt import PyJWTError as JWTError

                jwt = pyjwt

            # Get JWKS for token verification
            jwks = await self._get_jwks()
            if not jwks:
                return None

            # Decode the token header to get the key ID
            try:
                unverified = jwt.get_unverified_header(token)
            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid token header: {e}")
                raise AuthenticationError("Invalid token format", cause=str(e))
            except Exception as e:
                logger.warning(f"Failed to decode token header: {e}")
                unverified = {}

            kid = unverified.get("kid")

            # Find the matching key
            key = None
            for k in jwks.get("keys", []):
                if k.get("kid") == kid or kid is None:
                    key = k
                    break

            if not key:
                return None

            # Verify and decode
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=self.config.oauth2.audience,
                issuer=self.config.oauth2.issuer_uri,
            )

            # Map claims to user
            return self._map_claims_to_user(payload)

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired", extra={"token_type": "oauth2"})
            raise AuthenticationError("Token has expired", fix="Request a new token")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise AuthenticationError("Invalid token", cause=str(e))
        except Exception as e:
            logger.error(f"Unexpected auth error: {e}", exc_info=True)
            raise AuthenticationError("Authentication failed", cause=str(e))

    def _map_claims_to_user(self, claims: dict[str, Any]) -> User:
        """Map OIDC claims to User object using configured mapping."""
        mapping = self.config.oauth2.claim_mapping
        user_data: dict[str, Any] = {"login": "unknown", "authorities": []}

        for claim, field in mapping.items():
            if claim in claims:
                if field == "login":
                    user_data["login"] = claims[claim]
                elif field == "id":
                    user_data["id"] = claims[claim]
                elif field == "email":
                    user_data["email"] = claims[claim]
                elif field == "first_name":
                    user_data["first_name"] = claims[claim]
                elif field == "last_name":
                    user_data["last_name"] = claims[claim]
                elif field == "image_url":
                    user_data["image_url"] = claims[claim]
                elif field == "lang_key":
                    user_data["lang_key"] = claims[claim]

        # Extract authorities from roles/groups claim
        roles = claims.get("roles", claims.get("groups", []))
        if isinstance(roles, list):
            user_data["authorities"] = [
                r if r.startswith("ROLE_") else f"ROLE_{r.upper()}" for r in roles
            ]
        elif roles:
            user_data["authorities"] = [f"ROLE_{roles.upper()}"]

        # Default to ROLE_USER if no roles
        if not user_data["authorities"]:
            user_data["authorities"] = ["ROLE_USER"]

        return User(**user_data)

    async def _get_jwks(self) -> Optional[dict]:
        """Get the JWKS from the OAuth2 provider."""
        # Return cached if recent
        if self._jwks_cache and self._jwks_cache_time:
            age = datetime.now(UTC) - self._jwks_cache_time
            if age.total_seconds() < 3600:  # Cache for 1 hour
                return self._jwks_cache

        jwks_uri = self.config.oauth2.jwks_uri
        if not jwks_uri:
            # Try to construct from issuer URI
            issuer = self.config.oauth2.issuer_uri.rstrip("/")
            jwks_uri = f"{issuer}/.well-known/jwks.json"

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_uri)
                if response.status_code == 200:
                    self._jwks_cache = response.json()
                    self._jwks_cache_time = datetime.now(UTC)
                    return self._jwks_cache
                else:
                    logger.warning(
                        f"Failed to fetch JWKS: HTTP {response.status_code}",
                        extra={"jwks_uri": jwks_uri},
                    )
        except Exception as e:
            logger.error(f"JWKS fetch error: {e}", exc_info=True)

        return None

    async def _exchange_code(
        self, credentials: OAuth2AuthorizationCode
    ) -> AuthenticationResult:
        """Exchange an authorization code for tokens."""
        try:
            import httpx

            token_uri = self.config.oauth2.token_uri
            if not token_uri:
                return AuthenticationResult.failed(
                    "configuration_error", "OAuth2 token URI not configured"
                )

            data = {
                "grant_type": "authorization_code",
                "code": credentials.code,
                "redirect_uri": credentials.redirect_uri,
                "client_id": self.config.oauth2.client_id,
                "client_secret": self.config.oauth2.client_secret,
            }

            if credentials.code_verifier:
                data["code_verifier"] = credentials.code_verifier

            async with httpx.AsyncClient() as client:
                response = await client.post(token_uri, data=data)

                if response.status_code != 200:
                    return AuthenticationResult.failed(
                        "token_exchange_failed",
                        f"Token exchange failed: {response.text}",
                    )

                token_data = response.json()

            # Extract tokens
            access_token = token_data.get("access_token")
            id_token = token_data.get("id_token")

            # Validate the ID token to get user info
            user = None
            if id_token:
                user = await self.validate_token(id_token)

            if not user:
                # Try userinfo endpoint
                user = await self._get_userinfo(access_token)

            if not user:
                return AuthenticationResult.failed(
                    "user_info_failed", "Could not retrieve user information"
                )

            token = Token(
                access_token=access_token,
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                refresh_token=token_data.get("refresh_token"),
                id_token=id_token,
                scope=token_data.get("scope"),
            )

            return AuthenticationResult.successful(user, token, AuthMethod.OAUTH2)

        except Exception as e:
            return AuthenticationResult.failed("oauth2_error", str(e))

    async def _get_userinfo(self, access_token: str) -> Optional[User]:
        """Get user info from the userinfo endpoint."""
        userinfo_uri = self.config.oauth2.userinfo_uri
        if not userinfo_uri:
            return None

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    userinfo_uri,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code == 200:
                    claims = response.json()
                    return self._map_claims_to_user(claims)
                else:
                    logger.warning(
                        f"Userinfo request failed: HTTP {response.status_code}",
                        extra={"userinfo_uri": userinfo_uri},
                    )

        except Exception as e:
            logger.error(f"Userinfo fetch error: {e}", exc_info=True)

        return None

    async def refresh_token(self, refresh_token: str) -> Optional[Token]:
        """Refresh an access token using a refresh token."""
        try:
            import httpx

            token_uri = self.config.oauth2.token_uri
            if not token_uri:
                return None

            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.config.oauth2.client_id,
                "client_secret": self.config.oauth2.client_secret,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(token_uri, data=data)

                if response.status_code != 200:
                    logger.warning(
                        f"Token refresh failed: HTTP {response.status_code}",
                        extra={"token_uri": token_uri},
                    )
                    return None

                token_data = response.json()

            return Token(
                access_token=token_data.get("access_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                refresh_token=token_data.get("refresh_token", refresh_token),
                id_token=token_data.get("id_token"),
                scope=token_data.get("scope"),
            )

        except httpx.HTTPStatusError as e:
            logger.warning(f"Token refresh HTTP error: {e}")
            raise AuthenticationError("Token refresh failed", cause=str(e))
        except httpx.RequestError as e:
            logger.warning(f"Token refresh request error: {e}")
            raise AuthenticationError("Token refresh request failed", cause=str(e))
        except Exception as e:
            logger.error(f"Token refresh error: {e}", exc_info=True)
            raise AuthenticationError("Token refresh failed", cause=str(e))


class BasicAuth(AuthProvider):
    """
    HTTP Basic authentication provider.

    For internal/microservice use where simplicity is preferred
    over token-based auth.
    """

    def __init__(
        self,
        config: Optional[AuthConfig] = None,
        user_validator: Optional[Any] = None,
    ):
        """
        Initialize Basic auth provider.

        Args:
            config: Authentication configuration.
            user_validator: Callable that validates username/password.
                           Should return User or None.
        """
        super().__init__(config)
        self.user_validator = user_validator

    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """Authenticate using Basic credentials."""
        if isinstance(credentials, UsernamePasswordCredentials):
            user = await self._validate_user(credentials.username, credentials.password)
            if user:
                return AuthenticationResult.successful(
                    user, auth_method=AuthMethod.BASIC
                )
            return AuthenticationResult.failed(
                "invalid_credentials", "Invalid username or password"
            )

        return AuthenticationResult.failed(
            "unsupported_credentials", "Credential type not supported"
        )

    async def validate_token(self, token: str) -> Optional[User]:
        """
        Validate a Basic auth token (base64 encoded credentials).

        Token format: base64(username:password)
        """
        try:
            decoded = base64.b64decode(token).decode("utf-8")
            if ":" not in decoded:
                logger.warning("Invalid Basic auth format: missing colon separator")
                return None

            username, password = decoded.split(":", 1)
            return await self._validate_user(username, password)

        except base64.binascii.Error as e:
            logger.warning(f"Invalid Base64 encoding in Basic auth: {e}")
            raise AuthenticationError("Invalid Basic auth token encoding", cause=str(e))
        except UnicodeDecodeError as e:
            logger.warning(f"Invalid UTF-8 in Basic auth credentials: {e}")
            raise AuthenticationError(
                "Invalid character encoding in credentials", cause=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected Basic auth error: {e}", exc_info=True)
            raise AuthenticationError("Basic authentication failed", cause=str(e))

    async def _validate_user(self, username: str, password: str) -> Optional[User]:
        """Validate username and password."""
        if self.user_validator:
            return await self.user_validator(username, password)

        # Default: Check against API keys (username = "api", password = key)
        if username == "api" and self.config.validate_api_key(password):
            return User(
                login="api",
                authorities=["ROLE_API"],
            )

        return None

    @staticmethod
    def encode_credentials(username: str, password: str) -> str:
        """Encode credentials for Basic auth header."""
        credentials = f"{username}:{password}"
        return base64.b64encode(credentials.encode("utf-8")).decode("utf-8")


class SessionAuth(AuthProvider):
    """
    Session-based authentication provider.

    Implements traditional session management with optional
    remember-me functionality.
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """Initialize Session auth provider."""
        super().__init__(config)
        # In-memory session store (replace with Redis in production)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._remember_me_tokens: dict[str, str] = {}  # token -> user_login

    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """Authenticate using session credentials."""
        if isinstance(credentials, SessionCredentials):
            user = await self.validate_token(credentials.session_id)
            if user:
                return AuthenticationResult.successful(
                    user, auth_method=AuthMethod.SESSION
                )

            # Try remember-me token
            if credentials.remember_me_token:
                user = await self._validate_remember_me(credentials.remember_me_token)
                if user:
                    # Create new session
                    session_id = await self.create_session(user)
                    token = Token(access_token=session_id, token_type="Session")
                    return AuthenticationResult.successful(
                        user, token, AuthMethod.SESSION
                    )

            return AuthenticationResult.failed(
                "invalid_session", "Session expired or invalid"
            )

        elif isinstance(credentials, UsernamePasswordCredentials):
            # This would normally validate against a user store
            # For now, just create a session for the user
            user = User(
                login=credentials.username,
                authorities=["ROLE_USER"],
            )
            session_id = await self.create_session(user)
            token = Token(access_token=session_id, token_type="Session")

            # Generate remember-me token if requested
            if credentials.remember_me:
                remember_me_token = await self._create_remember_me_token(user)
                token.refresh_token = remember_me_token

            return AuthenticationResult.successful(user, token, AuthMethod.SESSION)

        return AuthenticationResult.failed(
            "unsupported_credentials", "Credential type not supported"
        )

    async def validate_token(self, token: str) -> Optional[User]:
        """Validate a session token."""
        session = self._sessions.get(token)
        if not session:
            return None

        # Check expiry
        expires_at = session.get("expires_at")
        if expires_at and datetime.now(UTC) > expires_at:
            del self._sessions[token]
            return None

        # Return user
        user_data = session.get("user")
        if user_data:
            return User(**user_data)

        return None

    async def create_session(self, user: User) -> str:
        """Create a new session for a user."""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self.config.session.timeout_seconds
        )

        self._sessions[session_id] = {
            "user": user.model_dump(),
            "created_at": datetime.now(UTC),
            "expires_at": expires_at,
        }

        return session_id

    async def _create_remember_me_token(self, user: User) -> str:
        """Create a remember-me token."""
        token = secrets.token_urlsafe(64)

        # Hash the token for storage
        token_hash = hashlib.sha256(
            (token + self.config.session.remember_me_key).encode()
        ).hexdigest()

        self._remember_me_tokens[token_hash] = user.login

        return token

    async def _validate_remember_me(self, token: str) -> Optional[User]:
        """Validate a remember-me token."""
        token_hash = hashlib.sha256(
            (token + self.config.session.remember_me_key).encode()
        ).hexdigest()

        login = self._remember_me_tokens.get(token_hash)
        if login:
            # Return user (would normally fetch from database)
            return User(login=login, authorities=["ROLE_USER"])

        return None

    async def revoke_token(self, token: str) -> bool:
        """Revoke a session."""
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False

    async def cleanup_expired(self) -> int:
        """Clean up expired sessions. Returns count of removed sessions."""
        now = datetime.now(UTC)
        expired = [
            sid
            for sid, session in self._sessions.items()
            if session.get("expires_at") and session["expires_at"] < now
        ]

        for sid in expired:
            del self._sessions[sid]

        return len(expired)


class ApiKeyAuth(AuthProvider):
    """
    API Key authentication provider.

    Simple key-based authentication for service-to-service calls.
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        """Initialize API Key auth provider."""
        super().__init__(config)

    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """Authenticate using an API key."""
        if isinstance(credentials, ApiKeyCredentials):
            if self.config.validate_api_key(credentials.api_key):
                user = User(
                    login="api",
                    authorities=["ROLE_API", "ROLE_USER"],
                    metadata={"api_key": credentials.api_key[:8] + "..."},
                )
                token = Token(
                    access_token=credentials.api_key,
                    token_type="ApiKey",
                )
                return AuthenticationResult.successful(user, token, AuthMethod.API_KEY)

            return AuthenticationResult.failed("invalid_api_key", "API key not valid")

        return AuthenticationResult.failed(
            "unsupported_credentials", "Credential type not supported"
        )

    async def validate_token(self, token: str) -> Optional[User]:
        """Validate an API key."""
        if self.config.validate_api_key(token):
            return User(
                login="api",
                authorities=["ROLE_API", "ROLE_USER"],
            )
        return None


class CompositeAuth(AuthProvider):
    """
    Composite authentication provider that tries multiple strategies.

    Useful for supporting multiple auth methods on the same endpoint.
    """

    def __init__(
        self,
        providers: list[AuthProvider],
        config: Optional[AuthConfig] = None,
    ):
        """
        Initialize with multiple providers.

        Args:
            providers: List of auth providers to try in order.
            config: Shared configuration.
        """
        super().__init__(config)
        self.providers = providers

    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """Try each provider until one succeeds."""
        last_error = None

        for provider in self.providers:
            result = await provider.authenticate(credentials)
            if result.success:
                return result
            last_error = result

        return last_error or AuthenticationResult.failed(
            "authentication_failed", "All authentication methods failed"
        )

    async def validate_token(self, token: str) -> Optional[User]:
        """Try each provider's token validation."""
        for provider in self.providers:
            user = await provider.validate_token(token)
            if user:
                return user
        return None


# =============================================================================
# Enterprise Authentication Stubs (TODO: Full Implementation)
# =============================================================================


class LDAPAuth(AuthProvider):
    """
    LDAP/Active Directory authentication provider (stub).

    TODO: Implement full LDAP authentication with:
    - Connection pooling
    - SSL/TLS support
    - Bind DN configuration
    - User search filters
    - Group membership mapping to roles
    - Password policy support

    Enterprise use case:
    - Corporate Active Directory integration
    - On-premises identity management
    - Centralized user management
    """

    def __init__(
        self,
        config: Optional[AuthConfig] = None,
        ldap_url: str | None = None,
        bind_dn: Optional[str] = None,
        bind_password: Optional[str] = None,
        user_search_base: str = "ou=users,dc=example,dc=com",
        user_search_filter: str = "(uid={username})",
        group_search_base: str = "ou=groups,dc=example,dc=com",
    ):
        """
        Initialize LDAP auth provider.

        Args:
            config: Authentication configuration
            ldap_url: LDAP server URL (ldap:// or ldaps://). Defaults to env LDAP_URL or ldap://localhost:389
            bind_dn: DN for binding to LDAP (service account)
            bind_password: Password for bind DN
            user_search_base: Base DN for user searches
            user_search_filter: LDAP filter for finding users
            group_search_base: Base DN for group searches
        """
        super().__init__(config)
        self.ldap_url = ldap_url or os.environ.get("LDAP_URL", "ldap://localhost:389")
        self.bind_dn = bind_dn or os.environ.get("LDAP_BIND_DN")
        self.bind_password = bind_password or os.environ.get("LDAP_BIND_PASSWORD")
        self.user_search_base = user_search_base
        self.user_search_filter = user_search_filter
        self.group_search_base = group_search_base

        logger.info("LDAPAuth initialized (stub implementation)")

    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """
        Authenticate against LDAP.

        TODO: Implement with ldap3 library:
        1. Bind with service account
        2. Search for user by username
        3. Attempt bind with user's DN and password
        4. Fetch user attributes and group memberships
        5. Map groups to roles
        """
        if isinstance(credentials, UsernamePasswordCredentials):
            # TODO: Implement LDAP bind and search
            logger.warning("LDAP authentication not implemented - returning stub")
            return AuthenticationResult.failed(
                "not_implemented",
                "LDAP authentication is not yet implemented. "
                "Install ldap3 and implement bind/search logic.",
            )

        return AuthenticationResult.failed(
            "unsupported_credentials", "LDAP requires username/password credentials"
        )

    async def validate_token(self, token: str) -> Optional[User]:
        """LDAP doesn't use tokens - returns None."""
        return None


class SAMLAuth(AuthProvider):
    """
    SAML 2.0 authentication provider (stub).

    TODO: Implement full SAML support with:
    - SP (Service Provider) metadata generation
    - IdP (Identity Provider) metadata parsing
    - SAML request/response handling
    - Assertion validation
    - Signature verification
    - Attribute mapping
    - Single logout (SLO)

    Enterprise use case:
    - Corporate SSO integration
    - Okta, OneLogin, Azure AD, etc.
    - Federated identity management
    """

    def __init__(
        self,
        config: Optional[AuthConfig] = None,
        idp_metadata_url: Optional[str] = None,
        idp_entity_id: Optional[str] = None,
        sp_entity_id: str = "agentic-brain",
        acs_url: str = "/auth/saml/acs",
        slo_url: str = "/auth/saml/slo",
    ):
        """
        Initialize SAML auth provider.

        Args:
            config: Authentication configuration
            idp_metadata_url: URL to fetch IdP metadata
            idp_entity_id: IdP entity ID
            sp_entity_id: Service Provider entity ID
            acs_url: Assertion Consumer Service URL
            slo_url: Single Logout URL
        """
        super().__init__(config)
        self.idp_metadata_url = idp_metadata_url
        self.idp_entity_id = idp_entity_id
        self.sp_entity_id = sp_entity_id
        self.acs_url = acs_url
        self.slo_url = slo_url

        logger.info("SAMLAuth initialized (stub implementation)")

    async def authenticate(self, credentials: Credentials) -> AuthenticationResult:
        """
        Process SAML authentication response.

        TODO: Implement with python3-saml or onelogin:
        1. Validate SAML response signature
        2. Verify assertion conditions (timestamps, audience)
        3. Extract user attributes
        4. Map SAML attributes to user object
        """
        # SAML typically uses redirects and posts, not direct credentials
        logger.warning("SAML authentication not implemented - returning stub")
        return AuthenticationResult.failed(
            "not_implemented",
            "SAML authentication is not yet implemented. "
            "Install python3-saml and implement assertion processing.",
        )

    async def validate_token(self, token: str) -> Optional[User]:
        """
        SAML doesn't use bearer tokens.

        Sessions are managed separately after SAML assertion is processed.
        """
        return None

    def generate_sp_metadata(self) -> str:
        """
        Generate SAML Service Provider metadata XML.

        TODO: Implement SP metadata generation for IdP configuration.
        """
        raise NotImplementedError("SP metadata generation not implemented")

    async def generate_auth_request(self, relay_state: Optional[str] = None) -> str:
        """
        Generate a SAML authentication request URL.

        TODO: Implement AuthnRequest generation and redirect.
        """
        raise NotImplementedError("SAML auth request generation not implemented")

    async def process_saml_response(
        self, saml_response: str, relay_state: Optional[str] = None
    ) -> AuthenticationResult:
        """
        Process a SAML response from the IdP.

        TODO: Implement response validation and user extraction.
        """
        raise NotImplementedError("SAML response processing not implemented")


# =============================================================================
# Global Auth Provider
# =============================================================================

# Global auth provider instance (None = auth disabled / development mode)
_auth_provider: Optional[AuthProvider] = None


def get_auth_provider() -> Optional[AuthProvider]:
    """
    Get the global authentication provider.

    Returns:
        The configured AuthProvider, or None if auth is disabled (dev mode).

    Usage:
        provider = get_auth_provider()
        if provider:
            user = await provider.validate_token(token)
    """
    return _auth_provider


def set_auth_provider(provider: AuthProvider) -> None:
    """
    Set the global authentication provider.

    Args:
        provider: The AuthProvider instance to use globally.

    Example:
        from agentic_brain.auth import JWTAuth, set_auth_provider

        jwt_auth = JWTAuth(config)
        set_auth_provider(jwt_auth)
    """
    global _auth_provider
    _auth_provider = provider
    logger.info(f"Auth provider set: {type(provider).__name__}")
