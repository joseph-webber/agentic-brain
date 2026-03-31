# Authentication Guide

Agentic Brain provides a comprehensive, enterprise-grade authentication system following JHipster patterns. This guide covers all authentication methods, configuration, and best practices.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Authentication Methods](#authentication-methods)
  - [JWT Authentication](#jwt-authentication)
  - [API Key Authentication](#api-key-authentication)
  - [LDAP/Active Directory](#ldapactive-directory)
  - [Firebase Authentication](#firebase-authentication)
  - [OAuth2/OIDC](#oauth2oidc-scaffolding)
  - [Session Authentication](#session-authentication)
- [WebSocket Authentication](#websocket-authentication)
- [Refresh Token Security](#refresh-token-security)
- [Role-Based Access Control](#role-based-access-control)
- [Security Decorators](#security-decorators)
- [Security Context](#security-context)
- [Rate Limiting](#rate-limiting)
- [Audit Logging](#audit-logging)
- [MFA Integration Points](#mfa-integration-points)
- [Environment Variables](#environment-variables)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

Agentic Brain's authentication system is designed with security-first principles:

- **Multiple auth methods**: JWT, API Key, LDAP, Firebase, OAuth2, Session
- **Zero-config development**: Auth disabled by default (`AUTH_ENABLED=false`)
- **Production-ready**: Token rotation, blacklisting, rate limiting
- **Enterprise features**: LDAP/AD integration, SAML scaffolding, MFA hooks
- **Spring Security-style decorators**: `@require_role`, `@pre_authorize`
- **Thread-safe context**: Async-safe security context management

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Routes                              │
├─────────────────────────────────────────────────────────────────┤
│  @require_role("ADMIN")  │  @require_authority("USER_VIEW")     │
├─────────────────────────────────────────────────────────────────┤
│                    Security Decorators                           │
├─────────────────────────────────────────────────────────────────┤
│                    Security Context                              │
│            (Thread-safe, async-safe contextvars)                 │
├─────────────────────────────────────────────────────────────────┤
│                   Auth Providers                                 │
│  ┌─────────┬─────────┬────────┬──────────┬─────────┬─────────┐ │
│  │   JWT   │ API Key │  LDAP  │ Firebase │ OAuth2  │ Session │ │
│  └─────────┴─────────┴────────┴──────────┴─────────┴─────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Rate Limiter  │  Audit Logger  │  MFA Provider  │  Token Store │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Development Mode (Auth Disabled)

By default, authentication is disabled for easy development:

```python
from agentic_brain.api.auth import get_optional_auth, AuthContext

@app.post("/chat")
async def chat(auth: AuthContext = Depends(get_optional_auth)):
    # Works without any auth when AUTH_ENABLED=false
    return {"message": "Hello!"}
```

### Enable Authentication

Set environment variables to enable auth:

```bash
# .env file
AUTH_ENABLED=true
API_KEYS=my-key-1,my-key-2
JWT_SECRET=your-256-bit-secret-key-here
```

### Protected Endpoint Example

```python
from agentic_brain.api.auth import require_auth, AuthContext

@app.post("/protected")
async def protected_endpoint(auth: AuthContext = Depends(require_auth)):
    if auth.authenticated:
        return {"user": auth.user_id, "method": auth.method}
    raise HTTPException(status_code=401, detail="Not authenticated")
```

---

## Authentication Methods

### JWT Authentication

JSON Web Token authentication for stateless API access.

#### Configuration

```bash
# Environment variables
JWT_SECRET=your-super-secret-key-at-least-256-bits
JWT_ALGORITHM=HS256              # Default
JWT_TOKEN_VALIDITY_SECONDS=86400 # 24 hours
JWT_ISSUER=agentic-brain
JWT_AUDIENCE=agentic-brain
```

#### Creating Tokens

```python
from agentic_brain.api.auth import create_test_token

# For testing only - production tokens should be issued via proper auth flow
token = create_test_token(
    user_id="user_123",
    roles=["ROLE_USER", "ROLE_ADMIN"],
    expires_in_seconds=3600
)
```

#### Using JWT in Requests

```bash
# HTTP Header
curl -H "Authorization: Bearer eyJhbG..." https://api.example.com/protected

# The token contains:
# - sub/user_id: User identifier
# - roles: List of user roles
# - exp: Expiration timestamp
# - iat: Issued at timestamp
# - jti: Unique token ID (for revocation)
```

#### JWT with Roles

```python
from agentic_brain.auth import JWTAuth
from agentic_brain.auth.config import AuthConfig

# Initialize JWT provider
config = AuthConfig()
jwt_auth = JWTAuth(config)

# Authenticate with credentials
from agentic_brain.auth.models import UsernamePasswordCredentials

result = await jwt_auth.authenticate(
    UsernamePasswordCredentials(
        username="john",
        password="secret",
        remember_me=False
    )
)

if result.success:
    print(f"Token: {result.token.access_token}")
    print(f"User: {result.user.login}")
    print(f"Roles: {result.user.authorities}")
```

#### Token Blacklisting

The JWT provider maintains a JTI (JWT ID) revocation list:

```python
# Revoke a token
await jwt_auth.revoke_token(token_string)

# The token will be rejected on subsequent validation attempts
user = await jwt_auth.validate_token(token_string)  # Returns None
```

---

### API Key Authentication

Simple and effective for service-to-service communication and external integrations.

#### Basic Setup

```bash
# Environment variables
API_KEYS=key1,key2,key3
API_KEY_ROLES=key1:ROLE_ADMIN,ROLE_USER;key2:ROLE_USER
```

#### Using API Keys in Requests

```bash
# Via header (preferred)
curl -H "X-API-Key: my-api-key" https://api.example.com/protected

# Via query parameter
curl "https://api.example.com/protected?api_key=my-api-key"
```

#### Enterprise API Key Provider

For advanced use cases with scopes, rate limiting, and expiration:

```python
from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig, APIKeyCredentials

# Configure the provider
config = APIKeyConfig(
    key_header="X-API-Key",
    key_prefix="ak_",              # Keys start with "ak_"
    enable_rate_limiting=True,
    default_rate_limit_per_minute=60,
    default_rate_limit_per_hour=1000,
)

auth = APIKeyAuthProvider(config)

# Create a new API key
key_info, plaintext_key = await auth.create_key(
    name="Production Integration",
    scopes=["read", "write", "agents"],
    expires_in_days=365,
    rate_limit_per_minute=100,
    metadata={"team": "platform", "environment": "production"}
)

print(f"API Key (save this!): {plaintext_key}")
print(f"Key ID: {key_info.key_id}")
print(f"Expires: {key_info.expires_at}")
```

#### API Key Scopes

Available scopes:

| Scope | Authority | Description |
|-------|-----------|-------------|
| `read` | `API_READ` | Read-only access |
| `write` | `API_WRITE` | Create/update resources |
| `delete` | `API_DELETE` | Delete resources |
| `admin` | `ROLE_ADMIN` | Full administrative access |
| `chat` | `CHAT_ACCESS` | Chat functionality |
| `agents` | `AGENTS_ACCESS` | Agent management |
| `plugins` | `PLUGINS_ACCESS` | Plugin management |
| `webhooks` | `WEBHOOKS_ACCESS` | Webhook management |

#### Per-Key Rate Limiting

Each API key can have individual rate limits:

```python
key_info, key = await auth.create_key(
    name="High-volume Service",
    scopes=["read", "write"],
    rate_limit_per_minute=1000,    # Override default (60)
    rate_limit_per_hour=50000,     # Override default (1000)
)
```

Rate limit errors return:

```json
{
  "error": "rate_limit_exceeded",
  "error_description": "Rate limit exceeded. Try again in 45 seconds"
}
```

#### Revoking API Keys

```python
# Revoke by key ID
success = await auth.revoke_key(key_id="abc-123")

# Revoked keys return a clear error
# {"error": "key_revoked", "error_description": "API key has been revoked"}
```

---

### LDAP/Active Directory

Enterprise directory authentication with full support for Active Directory and OpenLDAP.

#### Active Directory Configuration

```python
from agentic_brain.auth import LDAPAuthProvider, LDAPConfig

config = LDAPConfig(
    server="ldap://ad.company.com",
    port=389,
    use_ssl=True,
    ssl_port=636,
    
    # Service account for lookups
    bind_dn="CN=ServiceAccount,OU=Service Accounts,DC=company,DC=com",
    bind_password=os.getenv("LDAP_BIND_PASSWORD"),
    
    # Search settings
    base_dn="DC=company,DC=com",
    user_search_base="OU=Users,DC=company,DC=com",
    user_search_filter="(sAMAccountName={username})",
    
    # Attribute mappings
    username_attribute="sAMAccountName",
    email_attribute="mail",
    first_name_attribute="givenName",
    last_name_attribute="sn",
    
    # Group to role mapping
    group_role_mapping={
        "CN=Admins,OU=Groups,DC=company,DC=com": ["ROLE_ADMIN", "ROLE_USER"],
        "CN=Users,OU=Groups,DC=company,DC=com": ["ROLE_USER"],
        "CN=Developers,OU=Groups,DC=company,DC=com": ["ROLE_USER", "ROLE_DEVELOPER"],
    },
)

ldap_auth = LDAPAuthProvider(config)
```

#### OpenLDAP Configuration

```python
config = LDAPConfig(
    server="ldap://ldap.company.com",
    port=389,
    use_ssl=False,
    
    bind_dn="cn=admin,dc=company,dc=com",
    bind_password=os.getenv("LDAP_BIND_PASSWORD"),
    
    base_dn="dc=company,dc=com",
    user_search_base="ou=people,dc=company,dc=com",
    user_search_filter="(uid={username})",
    group_search_filter="(memberUid={username})",
    
    username_attribute="uid",
)
```

#### Authenticating Users

```python
from agentic_brain.auth import LDAPCredentials

result = await ldap_auth.authenticate(
    LDAPCredentials(
        username="john.doe",
        password="user-password"
    )
)

if result.success:
    print(f"Welcome, {result.user.full_name}!")
    print(f"Email: {result.user.email}")
    print(f"Groups: {result.user.metadata.get('ldap_groups', [])}")
    print(f"Roles: {result.user.authorities}")
```

#### LDAP Features

- **Connection pooling**: Configurable pool size for performance
- **Nested group resolution**: Active Directory transitive membership
- **Group caching**: 5-minute TTL for group memberships
- **User search**: Search users by username, email, or display name
- **Connection testing**: Diagnostic endpoint for troubleshooting

```python
# Test LDAP connection
status = await ldap_auth.test_connection()
print(f"Connected: {status['success']}")
print(f"Server: {status['server_info']}")

# Search users
users = await ldap_auth.search_users("john", limit=10)
for user in users:
    print(f"{user['username']} - {user['email']}")
```

#### LDAP Session Tokens

After LDAP authentication, you can issue JWT tokens for subsequent requests:

```python
if result.success:
    # Generate a JWT for the LDAP-authenticated user
    token = await ldap_auth.generate_session_token(result.user)
    # Token valid for 8 hours by default
```

---

### Firebase Authentication

Server-side Firebase Auth integration for mobile and web apps.

#### Configuration

```python
from agentic_brain.auth import FirebaseAPIAuth, FirebaseAuthConfig

config = FirebaseAuthConfig(
    project_id="your-firebase-project",
    credentials_path="/path/to/service-account.json",
    # Or use credentials dict
    # credentials_dict={"type": "service_account", ...},
    
    check_revoked=True,           # Check if token was revoked
    allow_anonymous=False,        # Reject anonymous Firebase users
    roles_claim="roles",          # Custom claim for roles
    authorities_claim="authorities",
    default_authorities=["ROLE_USER"],
)

firebase_auth = FirebaseAPIAuth(config)
```

#### Validating Firebase Tokens

```python
# Validate a Firebase ID token
claims = firebase_auth.verify_token(firebase_id_token)

print(f"User ID: {claims.uid}")
print(f"Email: {claims.email}")
print(f"Sign-in provider: {claims.sign_in_provider}")
print(f"Is anonymous: {claims.is_anonymous}")

# Convert to User object
user = firebase_auth.claims_to_user(claims)
```

#### FastAPI Dependency

```python
# Create a FastAPI dependency
require_firebase = firebase_auth.fastapi_dependency(
    required_roles=["ROLE_ADMIN"],
    allow_anonymous=False,
)

@app.get("/admin")
async def admin_endpoint(user: User = Depends(require_firebase)):
    return {"admin": user.login}
```

#### User Management

```python
# Create a Firebase user
user = firebase_auth.create_user(
    email="john@example.com",
    password="secure-password",
    display_name="John Doe",
)

# Update user roles
firebase_auth.set_user_roles(
    uid=user.id,
    roles=["ROLE_ADMIN", "ROLE_USER"],
)

# Delete user
firebase_auth.delete_user(uid=user.id)
```

---

### OAuth2/OIDC (Scaffolding)

OAuth2 configuration is scaffolded for future implementation.

#### Configuration (Planned)

```bash
# Environment variables
OAUTH2_ENABLED=true
OAUTH2_ISSUER_URI=https://accounts.google.com
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
OAUTH2_SCOPES=openid,profile,email
```

```python
from agentic_brain.auth.config import OAuth2Config

oauth2_config = OAuth2Config(
    enabled=True,
    issuer_uri="https://accounts.google.com",
    client_id=os.getenv("OAUTH2_CLIENT_ID"),
    client_secret=os.getenv("OAUTH2_CLIENT_SECRET"),
    scopes=["openid", "profile", "email"],
    
    # Claim mapping
    claim_mapping={
        "sub": "id",
        "preferred_username": "login",
        "email": "email",
        "given_name": "first_name",
        "family_name": "last_name",
        "picture": "image_url",
    }
)
```

---

### Session Authentication

Cookie-based session authentication for web applications.

#### Configuration

```bash
SESSION_AUTH_ENABLED=true
SESSION_TIMEOUT_SECONDS=1800          # 30 minutes
SESSION_COOKIE_NAME=AGENTIC_SESSION
SESSION_COOKIE_SECURE=true            # HTTPS only
SESSION_COOKIE_HTTPONLY=true          # No JavaScript access
SESSION_COOKIE_SAMESITE=lax

# Remember me
REMEMBER_ME_ENABLED=true
REMEMBER_ME_TIMEOUT_SECONDS=2592000   # 30 days
```

---

## WebSocket Authentication

WebSocket connections require JWT authentication for security.

#### Configuration

```python
from agentic_brain.api.websocket_auth import WebSocketAuthenticator, WebSocketAuthConfig

config = WebSocketAuthConfig(
    secret_key=os.getenv("JWT_SECRET"),
    algorithm="HS256",
    require_auth=True,              # CRITICAL: Always True in production
    max_token_age=3600,
)

ws_auth = WebSocketAuthenticator(config)
```

#### Client Connection

```javascript
// JavaScript client
const token = "your-jwt-token";

// Method 1: Query parameter (recommended for WebSocket)
const ws = new WebSocket(`wss://api.example.com/ws?token=${token}`);

// Method 2: Protocol header (browser-compatible)
const ws = new WebSocket("wss://api.example.com/ws", [token]);
```

#### Server-Side Validation

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Authenticate the connection
    auth_result = await ws_auth.authenticate(websocket)
    
    if auth_result is None:
        # Connection was closed with 1008 Policy Violation
        return
    
    if not auth_result["authenticated"]:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    # Connection authenticated
    await websocket.accept()
    user_id = auth_result["user"]
    print(f"WebSocket connected for user: {user_id}")
```

#### WebSocket Error Codes

| Code | Reason | Description |
|------|--------|-------------|
| 1008 | Policy Violation | No token provided or token invalid |
| 4001 | Unauthorized | Custom code for auth failures |

---

## Refresh Token Security

Secure refresh token implementation with rotation attack detection.

#### Token Family Tracking

```python
from agentic_brain.auth.refresh_tokens import RefreshTokenService

# Initialize service
refresh_service = RefreshTokenService(
    access_token_ttl_seconds=3600,     # 1 hour
    refresh_token_ttl_seconds=2592000, # 30 days
    rotate_on_refresh=True,            # Always rotate tokens
    bind_to_client=False,              # Optional: bind to IP/user-agent
)

# Create initial tokens
def generate_access_token(user_id: str) -> str:
    return jwt_auth.create_token(user_id)

result = await refresh_service.create_tokens(
    user_id="user-123",
    user_login="john@example.com",
    generate_access_token=generate_access_token,
)

print(f"Access Token: {result.access_token}")
print(f"Refresh Token: {result.refresh_token}")  # Store securely!
```

#### Token Rotation

```python
# Refresh tokens (rotation happens automatically)
refresh_result = await refresh_service.refresh(
    refresh_token=stored_refresh_token,
    generate_access_token=generate_access_token,
)

if refresh_result.success:
    # Always use the NEW refresh token
    print(f"New Access Token: {refresh_result.access_token}")
    print(f"New Refresh Token: {refresh_result.refresh_token}")
else:
    print(f"Refresh failed: {refresh_result.error}")
```

#### Rotation Attack Detection

If a refresh token is reused after rotation (indicating theft):

```python
# Scenario: Attacker stole old refresh token
# When they try to use it:

result = await refresh_service.refresh(old_stolen_token, ...)

# Result:
# {
#   "success": false,
#   "error": "token_reused",
#   "error_description": "This refresh token was already used. 
#                         All sessions revoked for security."
# }

# The ENTIRE token family is revoked, logging out the real user too
# This alerts them that their token was compromised
```

#### Token Data Model

```python
@dataclass
class RefreshTokenData:
    token_hash: str          # SHA-256 hash (never store plaintext!)
    user_id: str
    user_login: str
    family_id: str           # Tracks token chain
    issued_at: datetime
    expires_at: datetime
    revoked: bool
    revoked_at: Optional[datetime]
    revoked_reason: Optional[str]
    previous_token_hash: Optional[str]   # For chain tracking
    replaced_by_hash: Optional[str]      # Reuse detection
    client_ip: Optional[str]
    user_agent: Optional[str]
```

#### Global Sign-Out

```python
# Revoke single token (one device)
await refresh_service.revoke(refresh_token)

# Revoke all user tokens (all devices)
count = await refresh_service.revoke_all_user_tokens(user_id)
print(f"Revoked {count} sessions")

# Cleanup expired tokens (run periodically)
cleaned = await refresh_service.cleanup()
```

---

## Role-Based Access Control

### User Model

```python
from agentic_brain.auth.models import User

user = User(
    id="user-123",
    login="john@example.com",
    email="john@example.com",
    first_name="John",
    last_name="Doe",
    authorities=["ROLE_USER", "ROLE_ADMIN", "CHAT_ACCESS"],
)

# Check permissions
user.has_role("ADMIN")                    # True (checks ROLE_ADMIN)
user.has_authority("CHAT_ACCESS")         # True
user.has_any_authority("API_READ", "API_WRITE")  # True if either
user.has_all_authorities("ROLE_USER", "ROLE_ADMIN")  # True if both
```

### Standard Roles

| Role | Description |
|------|-------------|
| `ROLE_ADMIN` | Full administrative access |
| `ROLE_USER` | Standard user access |
| `ROLE_ANONYMOUS` | Unauthenticated access |
| `ROLE_API_KEY` | API key authentication |

---

## Security Decorators

Spring Security-style decorators for protecting endpoints.

### require_role

```python
from agentic_brain.auth.decorators import require_role

@app.delete("/admin/users/{user_id}")
@require_role("ADMIN")
async def delete_user(user_id: str):
    # Only ROLE_ADMIN can access
    return {"deleted": user_id}

@app.get("/moderator/reports")
@require_role("ADMIN", "MODERATOR")  # Either role works
async def get_reports():
    return {"reports": []}
```

### require_authority

```python
from agentic_brain.auth.decorators import require_authority

@app.get("/users")
@require_authority("USER_VIEW")
async def list_users():
    return {"users": []}

@app.post("/users")
@require_authority("USER_CREATE", "USER_DELETE", require_all=True)
async def manage_users():
    # Requires BOTH authorities
    return {"status": "ok"}
```

### require_authenticated

```python
from agentic_brain.auth.decorators import require_authenticated

@app.get("/profile")
@require_authenticated
async def get_profile():
    # Any authenticated user can access
    user = current_user()
    return {"user": user.login}
```

### allow_anonymous

```python
from agentic_brain.auth.decorators import allow_anonymous

@app.get("/public/info")
@allow_anonymous
async def public_info():
    # Explicitly marked as public
    return {"info": "This is public"}
```

### pre_authorize (Spring Security-style)

```python
from agentic_brain.auth.decorators import pre_authorize

@app.get("/admin/dashboard")
@pre_authorize("hasRole('ADMIN')")
async def admin_dashboard():
    return {"dashboard": "admin"}

@app.get("/content")
@pre_authorize("hasRole('ADMIN') or hasAuthority('CONTENT_VIEW')")
async def view_content():
    return {"content": []}

@app.put("/settings")
@pre_authorize("hasAnyRole('ADMIN', 'MODERATOR')")
async def update_settings():
    return {"updated": True}
```

Supported expressions:

- `hasRole('ROLE_NAME')`
- `hasAuthority('AUTHORITY')`
- `hasAnyRole('ROLE1', 'ROLE2')`
- `hasAnyAuthority('AUTH1', 'AUTH2')`
- `isAuthenticated()`
- `and`, `or` operators

### Dependency-Based Checkers

```python
from agentic_brain.auth.decorators import RoleChecker, AuthorityChecker

# Use as FastAPI dependency
@app.get("/admin", dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def admin_endpoint():
    return {"admin": True}

@app.get("/data", dependencies=[Depends(AuthorityChecker(["DATA_READ", "DATA_WRITE"]))])
async def data_endpoint():
    return {"data": []}
```

---

## Security Context

Thread-safe and async-safe security context management.

### Getting Current User

```python
from agentic_brain.auth.context import (
    current_user,
    is_authenticated,
    has_role,
    has_authority,
    get_authorities,
)

# In any function/handler
def some_function():
    if is_authenticated():
        user = current_user()
        print(f"Current user: {user.login}")
        
        if has_role("ADMIN"):
            print("User is admin")
        
        if has_authority("CHAT_ACCESS"):
            print("User can access chat")
        
        print(f"All authorities: {get_authorities()}")
```

### Setting Security Context

```python
from agentic_brain.auth.context import (
    set_security_context,
    clear_security_context,
    run_as_user,
)
from agentic_brain.auth.models import SecurityContext

# Manual context management
context = SecurityContext.from_user(user, token)
token = set_security_context(context)
try:
    # Code runs with this security context
    do_work()
finally:
    clear_security_context()

# Context manager (preferred)
with run_as_user(admin_user):
    # Code runs as admin
    perform_admin_action()
# Original context restored
```

### Async Support

```python
from agentic_brain.auth.context import current_user_async

async def async_handler():
    user = await current_user_async()
    if user:
        return f"Hello, {user.login}!"
```

---

## Rate Limiting

Built-in rate limiting for authentication endpoints.

### Global Rate Limiter

```python
from agentic_brain.auth import get_rate_limiter, set_rate_limiter

# Check if rate limited
limiter = get_rate_limiter()
if limiter.is_rate_limited(
    key="192.168.1.1",      # IP address, username, etc.
    max_attempts=5,
    window_seconds=300,     # 5 minutes
):
    return {"error": "Too many attempts"}

# Record attempt
limiter.record_attempt("192.168.1.1")

# Reset on success
limiter.reset("192.168.1.1")
```

### Rate Limit Decorator

```python
from agentic_brain.auth import rate_limit

@rate_limit(
    key_func=lambda self, creds: creds.username,
    max_attempts=5,
    window_seconds=300,
)
async def authenticate(self, credentials):
    # Rate limiting applied automatically
    pass
```

### Custom Rate Limiter

For production, implement a Redis-backed limiter:

```python
from agentic_brain.auth import RateLimiter, set_rate_limiter

class RedisRateLimiter(RateLimiter):
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def is_rate_limited(self, key, max_attempts=5, window_seconds=300):
        count = self.redis.get(f"rate:{key}")
        return int(count or 0) >= max_attempts
    
    def record_attempt(self, key, window_seconds=300):
        pipe = self.redis.pipeline()
        pipe.incr(f"rate:{key}")
        pipe.expire(f"rate:{key}", window_seconds)
        pipe.execute()
    
    def reset(self, key):
        self.redis.delete(f"rate:{key}")

# Set as global limiter
set_rate_limiter(RedisRateLimiter(redis_client))
```

---

## Audit Logging

Security event logging for compliance and monitoring.

### Default Audit Logger

```python
from agentic_brain.auth import get_audit_logger

logger = get_audit_logger()

# Log security events
logger.log_event(
    event_type="LOGIN_SUCCESS",
    user_id="john@example.com",
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0...",
    details={"method": "jwt"},
    success=True,
)
```

### Custom Audit Logger

```python
from agentic_brain.auth import AuditLogger, set_audit_logger

class DatabaseAuditLogger(AuditLogger):
    def __init__(self, db):
        self.db = db
    
    def log_event(self, event_type, user_id=None, ip_address=None, 
                  user_agent=None, details=None, success=True):
        # Store in database
        self.db.audit_logs.insert({
            "event": event_type,
            "user_id": user_id,
            "ip": ip_address,
            "user_agent": user_agent,
            "details": details,
            "success": success,
            "timestamp": datetime.now(UTC),
        })
        
        # Also log to external SIEM if needed
        if not success:
            self.send_to_siem(event_type, user_id, ip_address)

set_audit_logger(DatabaseAuditLogger(db))
```

### Audit Event Types

| Event | Description |
|-------|-------------|
| `LOGIN_SUCCESS` | Successful authentication |
| `LOGIN_FAILURE` | Failed authentication attempt |
| `TOKEN_REFRESH` | Token refreshed |
| `TOKEN_REVOKE` | Token revoked |
| `MFA_CHALLENGE` | MFA challenge sent |
| `MFA_VERIFY` | MFA verification attempt |

---

## MFA Integration Points

Multi-Factor Authentication scaffolding for future implementation.

### MFA Configuration (Planned)

```python
from agentic_brain.auth import MFAConfig, MFAMethod

config = MFAConfig(
    # TOTP (Google Authenticator, Authy)
    totp_issuer="Agentic Brain",
    totp_digits=6,
    totp_interval=30,
    
    # SMS OTP
    sms_code_length=6,
    sms_code_expiry_seconds=300,
    
    # Recovery codes
    recovery_code_count=10,
    recovery_code_length=8,
    
    # Enforcement
    require_mfa_for_roles=["ROLE_ADMIN"],
    allow_remember_device=True,
    remember_device_days=30,
)
```

### MFA Provider Interface

```python
from agentic_brain.auth import MFAProvider, set_mfa_provider

class TOTPProvider(MFAProvider):
    async def is_mfa_required(self, user: User) -> bool:
        return user.has_role("ADMIN")
    
    async def generate_challenge(self, user: User) -> dict:
        # Generate TOTP challenge
        return {"challenge_id": "...", "method": "totp"}
    
    async def verify_response(self, user: User, challenge_id: str, 
                              response: str) -> bool:
        # Verify TOTP code
        return pyotp.TOTP(user_secret).verify(response)

# Enable MFA
set_mfa_provider(TOTPProvider())
```

---

## Environment Variables

### Core Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_ENABLED` | `false` | Enable/disable authentication |
| `API_KEYS` | `` | Comma-separated list of valid API keys |
| `API_KEY_ROLES` | `` | Key-to-roles mapping (`key1:ROLE_A;key2:ROLE_B`) |

### JWT Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | auto-generated | Secret for signing JWTs |
| `JWT_BASE64_SECRET` | `` | Base64-encoded secret (alternative) |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_TOKEN_VALIDITY_SECONDS` | `86400` | Token lifetime (24 hours) |
| `JWT_REMEMBER_ME_VALIDITY_SECONDS` | `2592000` | Remember-me token (30 days) |
| `JWT_ISSUER` | `agentic-brain` | Token issuer claim |
| `JWT_AUDIENCE` | `agentic-brain` | Token audience claim |

### WebSocket Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | `` | **Required in production** |
| `ENVIRONMENT` | `development` | Set to `production` to enforce secrets |

### OAuth2 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OAUTH2_ENABLED` | `false` | Enable OAuth2 |
| `OAUTH2_ISSUER_URI` | `` | OAuth2 issuer URL |
| `OAUTH2_CLIENT_ID` | `` | OAuth2 client ID |
| `OAUTH2_CLIENT_SECRET` | `` | OAuth2 client secret |
| `OAUTH2_SCOPES` | `openid,profile,email` | Requested scopes |

### Session Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_AUTH_ENABLED` | `false` | Enable session auth |
| `SESSION_TIMEOUT_SECONDS` | `1800` | Session timeout (30 min) |
| `SESSION_COOKIE_NAME` | `AGENTIC_SESSION` | Cookie name |
| `SESSION_COOKIE_SECURE` | `true` | HTTPS-only cookie |
| `SESSION_COOKIE_HTTPONLY` | `true` | No JS access |
| `REMEMBER_ME_ENABLED` | `true` | Allow remember-me |
| `REMEMBER_ME_TIMEOUT_SECONDS` | `2592000` | Remember-me duration |

### LDAP Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LDAP_SERVER` | `ldap://localhost` | LDAP server URL |
| `LDAP_BIND_PASSWORD` | `` | Bind account password |

### Password Security

| Variable | Default | Description |
|----------|---------|-------------|
| `PASSWORD_ENCODER` | `bcrypt` | Encoder type |
| `BCRYPT_ROUNDS` | `12` | BCrypt cost factor |

---

## Security Best Practices

### 1. Production Secrets

**Never use default secrets in production:**

```bash
# Generate a secure JWT secret
python -c "import secrets; print(secrets.token_hex(64))"

# Set in production
export JWT_SECRET="your-generated-256-bit-secret"
```

### 2. HTTPS Only

Always use HTTPS in production:

```python
# Enforce secure cookies
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=strict
```

### 3. API Key Security

- **Never log API keys** - Use masked versions only
- **Rotate keys periodically** - Set expiration dates
- **Use scopes** - Grant minimal required permissions
- **Monitor usage** - Track key usage patterns

### 4. Token Storage

**Client-side:**
- Store access tokens in memory (not localStorage)
- Store refresh tokens in httpOnly cookies
- Never expose tokens in URLs (except WebSocket query params)

**Server-side:**
- Hash tokens before storage (SHA-256)
- Use secure storage (Redis with encryption, encrypted DB)
- Implement token cleanup routines

### 5. Rate Limiting

Implement rate limiting on all auth endpoints:

```python
# Recommended limits
LOGIN_MAX_ATTEMPTS = 5      # Per 5 minutes
API_KEY_RATE_MINUTE = 60    # Requests per minute
API_KEY_RATE_HOUR = 1000    # Requests per hour
```

### 6. Audit Everything

Log all security events:

```python
# Critical events to audit
- LOGIN_SUCCESS / LOGIN_FAILURE
- TOKEN_REFRESH
- TOKEN_REVOKE
- API_KEY_CREATE / API_KEY_REVOKE
- PERMISSION_DENIED
- RATE_LIMIT_EXCEEDED
```

### 7. WebSocket Security

```python
# In production, ALWAYS require auth
WebSocketAuthConfig(
    require_auth=True,           # Never False in production!
    max_token_age=3600,
)
```

### 8. LDAP Security

- Use SSL/TLS for LDAP connections
- Use service accounts with minimal permissions
- Implement connection timeouts
- Cache group memberships to reduce queries

---

## Troubleshooting

### Common Issues

#### "JWT_SECRET not configured"

**Problem:** WebSocket or JWT auth fails in production.

**Solution:** Set `JWT_SECRET` environment variable:

```bash
export JWT_SECRET="your-256-bit-secret-minimum"
```

#### "API key not found"

**Problem:** Valid API key rejected.

**Solution:** Check key format and prefix:

```python
# If using prefix
APIKeyConfig(key_prefix="ak_")
# Keys must start with "ak_"
```

#### "Rate limit exceeded"

**Problem:** Too many auth attempts.

**Solution:** Wait for window to expire or contact admin:

```python
# Check retry_after in error response
{"error": "rate_limit_exceeded", "retry_after": 45}
```

#### "Token reused" / All sessions revoked

**Problem:** Refresh token rotation detected theft.

**Solution:** 
1. User's refresh token was stolen and used
2. All sessions are revoked for security
3. User must re-authenticate

#### LDAP Connection Timeout

**Problem:** LDAP auth takes too long or times out.

**Solution:**
```python
LDAPConfig(
    timeout_seconds=10,       # Increase if needed
    pool_size=10,             # Connection pooling
)
```

#### Firebase Token Verification Failed

**Problem:** Firebase token rejected.

**Solution:**
1. Check token hasn't expired
2. Verify project_id matches
3. Ensure credentials are valid
4. Check if token was revoked

### Debug Mode

Enable debug logging for auth:

```python
import logging
logging.getLogger("agentic_brain.auth").setLevel(logging.DEBUG)
```

### Health Check

```bash
# Check auth system status
curl http://localhost:8000/health

# Test LDAP connection (if configured)
from agentic_brain.auth import LDAPAuthProvider
status = await ldap_auth.test_connection()
print(status)
```

---

## License

Apache License 2.0 - See LICENSE file for details.

Copyright 2024-2026 Agentic Brain Contributors
