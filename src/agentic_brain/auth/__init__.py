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
Enterprise Authentication Module for Agentic Brain.

This module provides enterprise-grade authentication following JHipster patterns:
- Multiple auth providers (JWT, OAuth2, Basic, Session)
- Role-based and authority-based access control
- Thread-safe security context
- FastAPI integration with async support

Example usage:
    from agentic_brain.auth import JWTAuth, require_role, current_user

    # Configure JWT auth
    auth = JWTAuth(config)
    token = await auth.authenticate(credentials)

    # Protect endpoints
    @app.get("/admin")
    @require_role("ADMIN")
    async def admin_endpoint():
        user = current_user()
        return {"user": user.login}
"""

from agentic_brain.auth.config import AuthConfig
from agentic_brain.auth.constants import (
    AUTHORITY_ADMIN,
    AUTHORITY_USER,
    ROLE_ADMIN,
    ROLE_ANONYMOUS,
    ROLE_USER,
)
from agentic_brain.auth.context import (
    clear_security_context,
    current_user,
    current_user_async,
    get_current_token,
    has_any_authority,
    has_authority,
    is_authenticated,
    set_security_context,
)
from agentic_brain.auth.decorators import (
    require_authenticated,
    require_authority,
    require_role,
)
from agentic_brain.auth.enterprise_providers import (
    # API Key
    APIKeyAuthProvider,
    APIKeyConfig,
    APIKeyCredentials,
    APIKeyInfo,
    APIKeyScope,
    # LDAP
    LDAPAuthProvider,
    LDAPConfig,
    LDAPCredentials,
    MFAConfig,
    MFAMethod,
    # MFA
    MFAProvider,
    MFASetupResult,
    MFAVerifyResult,
    # SAML
    SAMLAuthProvider,
    SAMLAuthRequest,
    SAMLConfig,
)
from agentic_brain.auth.firebase_auth import (
    FIREBASE_AUTH_AVAILABLE,
    FirebaseAPIAuth,
    FirebaseAuthConfig,
    FirebaseTokenClaims,
)
from agentic_brain.auth.firebase_provider import FirebaseAuthProvider
from agentic_brain.auth.models import Token, User
from agentic_brain.auth.providers import (
    ApiKeyAuth,
    AuditLogger,
    AuthProvider,
    BasicAuth,
    CompositeAuth,
    JWTAuth,
    LDAPAuth,
    OAuth2Auth,
    RateLimiter,
    SAMLAuth,
    SessionAuth,
    get_audit_logger,
    get_auth_provider,
    get_mfa_provider,
    get_rate_limiter,
    rate_limit,
    set_audit_logger,
    set_auth_provider,
    set_mfa_provider,
    set_rate_limiter,
)

__all__ = [
    # Core Providers
    "AuthProvider",
    "JWTAuth",
    "OAuth2Auth",
    "BasicAuth",
    "SessionAuth",
    "ApiKeyAuth",
    "CompositeAuth",
    "LDAPAuth",  # Stub in providers.py
    "SAMLAuth",  # Stub in providers.py
    "FirebaseAuthProvider",
    # Enterprise Providers (from enterprise_providers.py)
    "LDAPAuthProvider",
    "LDAPConfig",
    "LDAPCredentials",
    "SAMLAuthProvider",
    "SAMLConfig",
    "SAMLAuthRequest",
    "APIKeyAuthProvider",
    "APIKeyConfig",
    "APIKeyCredentials",
    "APIKeyInfo",
    "APIKeyScope",
    "MFAProvider",
    "MFAConfig",
    "MFAMethod",
    "MFASetupResult",
    "MFAVerifyResult",
    # Security Hooks
    "AuditLogger",
    "get_audit_logger",
    "set_audit_logger",
    "RateLimiter",
    "get_rate_limiter",
    "set_rate_limiter",
    "rate_limit",
    "get_mfa_provider",
    "set_mfa_provider",
    # Global Auth Provider
    "get_auth_provider",
    "set_auth_provider",
    # Decorators
    "require_role",
    "require_authority",
    "require_authenticated",
    # Context
    "current_user",
    "current_user_async",
    "is_authenticated",
    "has_authority",
    "has_any_authority",
    "get_current_token",
    "set_security_context",
    "clear_security_context",
    # Models
    "Token",
    "User",
    # Config
    "AuthConfig",
    # Constants
    "ROLE_ADMIN",
    "ROLE_USER",
    "ROLE_ANONYMOUS",
    "AUTHORITY_ADMIN",
    "AUTHORITY_USER",
    "FirebaseAPIAuth",
    "FirebaseAuthConfig",
    "FirebaseTokenClaims",
    "FIREBASE_AUTH_AVAILABLE",
]
