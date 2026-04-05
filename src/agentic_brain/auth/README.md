# Authentication Module Documentation

## Overview

The `agentic_brain.auth` package provides a unified authentication and authorization layer for the Agentic Brain platform. It follows JHipster-inspired patterns and is designed for FastAPI and async workloads, while remaining framework-agnostic at the core.

Key capabilities:
- Multiple authentication strategies (JWT, API keys, sessions, OAuth2/OIDC, LDAP, SAML, Firebase)
- Central security context and helper APIs
- Role-based and authority-based access control
- Audit logging, rate limiting, and refresh token rotation hooks

---

## Architecture Overview

```text
┌──────────────────────────────────────────────┐
│ Incoming request (HTTP/WebSocket/CLI)       │
└─────────────────────────────┬────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────┐
│ FastAPI / transport layer                    │
│  - Routers, middleware, dependencies         │
└─────────────────────────────┬────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────┐
│ Authentication providers (providers.py)      │
│  - JWTAuth, OAuth2Auth, BasicAuth           │
│  - SessionAuth, ApiKeyAuth                  │
│  - LDAPAuth, SAMLAuth, FirebaseAuthProvider │
└─────────────────────────────┬────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────┐
│ Security context (context.py, models.py)     │
│  - User, Token, SecurityContext              │
│  - contextvars-based storage                 │
└─────────────────────────────┬────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────┐
│ Authorization layer (decorators.py)         │
│  - Role/authority decorators                 │
│  - FastAPI dependencies                      │
└─────────────────────────────┬────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────┐
│ Application logic                            │
└──────────────────────────────────────────────┘
```

### Module Components

| Module | Purpose | Key Types |
|--------|---------|----------|
| `config.py` | Type-safe authentication configuration | `AuthConfig`, `JWTConfig`, `OAuth2Config`, `SessionConfig` |
| `constants.py` | Role, authority, and token constants | `ROLE_*`, `AUTHORITY_*`, claim and scope names |
| `models.py` | Core auth models | `User`, `Token`, `Credentials`, `AuthenticationResult`, `SecurityContext` |
| `context.py` | Security context helpers | `set_security_context`, `current_user`, `has_role`, `has_authority` |
| `decorators.py` | Authorization decorators & dependencies | `require_role`, `require_authority`, `pre_authorize`, `RoleChecker` |
| `providers.py` | Authentication provider implementations | `AuthProvider`, `JWTAuth`, `OAuth2Auth`, `BasicAuth`, `SessionAuth`, `ApiKeyAuth` |
| `enterprise_providers.py` | Enterprise integrations | `LDAPAuthProvider`, `SAMLAuthProvider`, `APIKeyAuthProvider`, `MFAProvider` |
| `refresh_tokens.py` | Refresh token rotation | `RefreshTokenService`, `RefreshTokenStore`, `InMemoryRefreshTokenStore` |
| `firebase_auth.py` | Firebase API auth integration | `FirebaseAPIAuth`, `FirebaseAuthConfig`, `FirebaseTokenClaims` |
| `firebase_provider.py` | Firebase provider implementing `AuthProvider` | `FirebaseAuthProvider` |
| `saml_provider.py` | Lightweight SAML helper | `SAMLConfig`, `SAMLProvider` |

---

## Supported Authentication Methods

### JWT (JSON Web Tokens)

**Files**: `config.py`, `providers.py`, `refresh_tokens.py`, `constants.py`

- Primary stateless authentication mechanism
- Configured via `JWTConfig` (secret, algorithm, issuer, audience, lifetimes)
- Implemented by `JWTAuth` (iss/exp/aud/subject validation, JTI support)
- Integrated with `RefreshTokenService` for secure rotation and reuse detection

**Typical flow**:
1. Client exchanges credentials for a short-lived access token and long-lived refresh token
2. Access token is sent in the `Authorization: Bearer` header
3. Server validates signature, expiry, issuer, audience, and JTI
4. When expired, client uses the refresh token to obtain a new pair

### API Keys

**Files**: `config.py`, `enterprise_providers.py`, `providers.py`

- Designed for service-to-service and internal automation calls
- Static keys are configured via `AuthConfig.api_keys` (environment variable `API_KEYS`)
- `AuthConfig.validate_api_key()` performs constant-time comparisons
- `APIKeyAuthProvider` and `ApiKeyAuth` can attach roles or authorities per key

### Session-Based Authentication

**Files**: `config.py`, `constants.py`, `providers.py`

- Optional session management for browser-based flows
- `SessionConfig` controls timeouts and cookie behaviour (Secure, HttpOnly, SameSite)
- `SessionAuth` issues and validates server-side sessions and remember-me tokens
- Integrates cleanly with the security context and decorators

### OAuth2 / OpenID Connect

**Files**: `config.py`, `providers.py`

- `OAuth2Config` holds issuer, client, and endpoint configuration
- `OAuth2Auth` validates ID/access tokens from external identity providers
- Claim mapping allows adaptation of provider-specific claims into the internal `User` model

### HTTP Basic Authentication

**Files**: `config.py`, `providers.py`

- Intended for internal tools and simple integrations
- Controlled by `BasicAuthConfig` (enabled flag and realm)
- Password hashing and comparison respect `PasswordConfig` settings

### LDAP / Active Directory

**Files**: `enterprise_providers.py`

- `LDAPConfig` describes connection, bind, search bases, and group-to-role mapping
- `LDAPAuthProvider` authenticates users against directory services and maps groups to authorities
- Designed to work with `ROLE_*` constants and existing decorators

### SAML 2.0 (Helper)

**Files**: `saml_provider.py`, `enterprise_providers.py`

- `SAMLProvider` offers minimal AuthnRequest generation, response parsing, and SP metadata
- `SAMLAuthProvider` (enterprise) integrates SAML flows into the `AuthProvider` model
- Production deployments should pair this with a hardened SAML library for full signature and replay protection

### Firebase Authentication

**Files**: `firebase_auth.py`, `firebase_provider.py`

- `FirebaseAPIAuth` provides dependency-friendly Firebase token verification for HTTP APIs
- `FirebaseAuthProvider` implements `AuthProvider` around Firebase ID tokens
- Normalizes roles and authorities from custom claims into the internal `User` model

---

## Role-Based Access Control

The authentication module uses a combination of **roles** and **authorities**:

- Roles: Coarse-grained, prefixed with `ROLE_` (for example `ROLE_ADMIN`, `ROLE_USER`)
- Authorities: Fine-grained permissions (for example `USER_VIEW`, `MEMORY_WRITE`)

### Role and Authority Storage

- Both roles and authorities are stored in `User.authorities`
- `User.has_role("ADMIN")` automatically adds the `ROLE_` prefix
- `constants.py` defines shared role and authority names used across the platform

### Helper Functions

From `context.py` and `models.py`:

- `is_authenticated()` – whether a user is present in the current security context
- `has_role("ADMIN")` – checks for a specific role
- `has_authority("USER_VIEW")` – checks for a specific authority
- `has_any_authority("ADMIN", "MODERATOR")` – any of the listed authorities
- `run_as_user(user)` – temporarily executes code under a different user

### Decorators and Dependencies

From `decorators.py`:

- `@require_role("ADMIN")` – decorator enforcing role membership
- `@require_authority("USER_VIEW", require_all=False)` – decorator enforcing authorities
- `@pre_authorize("hasRole('ADMIN') or hasAuthority('USER_MANAGE')")` – expression-based checks
- `RoleChecker([...])`, `AuthorityChecker([...])`, `AuthenticationChecker()` – FastAPI dependencies

**Example (FastAPI endpoint):**

```python
from fastapi import APIRouter, Depends
from agentic_brain.auth import (
    require_role,
    AuthorityChecker,
    current_user,
)

router = APIRouter()

@router.get("/admin/users", dependencies=[Depends(AuthorityChecker(["USER_VIEW"]))])
@require_role("ADMIN")
async def list_users():
    user = current_user()
    return {"requested_by": user.login if user else None}
```

---

## Integration Guide

### 1. Configure Authentication

Most configuration is environment-driven and loaded via `AuthConfig.from_env()`:

```python
from agentic_brain.auth import AuthConfig, set_auth_config

config = AuthConfig.from_env()
set_auth_config(config)
```

Key environment variables:

- `AUTH_ENABLED` – enable/disable authentication globally
- `JWT_SECRET` or `JWT_BASE64_SECRET` – signing key for JWT
- `JWT_ALGORITHM`, `JWT_TOKEN_VALIDITY_SECONDS` – algorithm and lifetime
- `API_KEYS` – comma-separated API keys for service-to-service auth
- `SESSION_AUTH_ENABLED`, `SESSION_TIMEOUT_SECONDS`, `SESSION_COOKIE_*` – session settings
- `OAUTH2_ENABLED`, `OAUTH2_ISSUER_URI`, `OAUTH2_CLIENT_ID`, `OAUTH2_CLIENT_SECRET` – OAuth2/OIDC

### 2. Choose and Initialize Providers

In most cases, you can rely on `get_auth_provider()` to return a composite that selects the appropriate strategy based on configuration:

```python
from agentic_brain.auth import get_auth_provider

auth_provider = get_auth_provider()
result = await auth_provider.authenticate(credentials)
```

For explicit control (e.g., dedicated JWT-only service):

```python
from agentic_brain.auth import JWTAuth, AuthConfig

config = AuthConfig.from_env()
jwt_auth = JWTAuth(config)
result = await jwt_auth.authenticate(token_credentials)
```

Enterprise environments can wire in LDAP, SAML, and MFA providers from `enterprise_providers.py` and set them globally via `set_auth_provider` or composite providers.

### 3. Integrate With FastAPI

Use authorization decorators and dependencies in your routers and middleware:

```python
from fastapi import FastAPI, Depends
from agentic_brain.auth import (
    authenticated,
    require_admin,
    get_current_token,
)

app = FastAPI()

@app.get("/profile", dependencies=[Depends(authenticated)])
async def profile():
    token = get_current_token()
    return {"token_expires_at": token.expires_at if token else None}

@app.get("/admin/metrics", dependencies=[Depends(require_admin)])
async def admin_metrics():
    # Only users with an administrator role can access this route
    ...
```

WebSocket and background workers can use `set_security_context` and `SecurityContextManager` to propagate identity into non-request code paths.

### 4. Enable Refresh Tokens (Optional)

Use `RefreshTokenService` to issue and rotate refresh tokens:

```python
from agentic_brain.auth.refresh_tokens import RefreshTokenService

service = RefreshTokenService()

result = await service.create_tokens(
    user_id=user.id,
    user_login=user.login,
    generate_access_token=make_jwt_for_user,
)

refresh_result = await service.refresh(
    refresh_token=result.refresh_token,
    generate_access_token=make_jwt_for_user,
)
```

Backends such as Redis or databases can be integrated by implementing `RefreshTokenStore` and injecting it into `RefreshTokenService`.

---

## Security Best Practices

- **Use strong secrets**: Provide a long, random `JWT_SECRET` or `JWT_BASE64_SECRET`; never use defaults in production.
- **Prefer short-lived access tokens**: Keep JWT access tokens short-lived and rely on refresh tokens for session continuity.
- **Protect refresh tokens**: Store refresh tokens securely on the client and always enable rotation to detect reuse.
- **Secure cookies**: For sessions, set `cookie_secure=True`, `cookie_httponly=True`, and appropriate SameSite settings; terminate TLS at the edge.
- **Apply least privilege**: Assign only the roles and authorities required for each identity; avoid using administrator-level roles for routine calls.
- **Harden audit logging**: Provide a custom `AuditLogger` that streams events to an append-only log or SIEM, without sensitive fields.
- **Enable rate limiting**: Replace the default in-memory `RateLimiter` with a distributed implementation and apply `@rate_limit` to sensitive operations.
- **Avoid logging secrets**: Never log tokens, passwords, API keys, or raw credentials; use `_mask_sensitive()` helpers where needed.
- **Validate external tokens**: Always validate issuer, audience, expiry, and revocation status for OAuth2, SAML, and Firebase tokens.
- **Test access control**: Add automated tests that verify critical endpoints are correctly protected by roles and authorities.
