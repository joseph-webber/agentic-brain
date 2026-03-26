# Enterprise Authentication Guide

Agentic Brain provides **enterprise-grade authentication** following JHipster security patterns. Support for JWT, OAuth2/OIDC, Basic Auth, and Session-based authentication with role-based access control.

---

## Quick Start

### 1. JWT Authentication (Default)

The simplest way to add authentication:

```python
from agentic_brain.auth import JWTAuth, AuthConfig, require_role, current_user

# Configure JWT
config = AuthConfig()
auth = JWTAuth(config)

# Authenticate and get token
from agentic_brain.auth import User, UsernamePasswordCredentials

user = User(login="admin", authorities=["ROLE_ADMIN", "ROLE_USER"])
token = await auth.generate_token(user)
print(f"Token: {token.access_token}")

# Protect endpoints
from fastapi import FastAPI

app = FastAPI()

@app.get("/admin")
@require_role("ADMIN")
async def admin_only():
    user = current_user()
    return {"message": f"Hello, {user.login}!"}
```

### 2. OAuth2/OIDC (External Identity Provider)

```python
from agentic_brain.auth import OAuth2Auth, AuthConfig

config = AuthConfig()
auth = OAuth2Auth(config)

# Exchange authorization code for tokens
from agentic_brain.auth.models import OAuth2AuthorizationCode

result = await auth.authenticate(OAuth2AuthorizationCode(
    code="auth_code_from_idp",
    redirect_uri="https://app.example.com/callback"
))

if result.success:
    print(f"User: {result.user.login}")
    print(f"Token: {result.token.access_token}")
```

### 3. Basic Auth (Microservices)

```python
from agentic_brain.auth import BasicAuth, AuthConfig

config = AuthConfig()
auth = BasicAuth(config)

# Authenticate with username/password
from agentic_brain.auth import UsernamePasswordCredentials

result = await auth.authenticate(UsernamePasswordCredentials(
    username="service-account",
    password="secret"
))
```

### 4. Session Auth (Web Applications)

```python
from agentic_brain.auth import SessionAuth, AuthConfig

config = AuthConfig()
auth = SessionAuth(config)

# Authenticate with remember-me support
from agentic_brain.auth import UsernamePasswordCredentials

result = await auth.authenticate(UsernamePasswordCredentials(
    username="user@example.com",
    password="password123",
    remember_me=True  # Extended session
))
```

---

## Configuration

All configuration via environment variables or `AuthConfig`:

### Environment Variables

```bash
# Global toggle
AUTH_ENABLED=true

# JWT Configuration
JWT_SECRET=your-512-bit-secret-minimum-64-chars
JWT_BASE64_SECRET=                    # Alternative: base64-encoded secret
JWT_ALGORITHM=HS512                   # HS256, HS384, HS512, RS256, RS384, RS512
JWT_TOKEN_VALIDITY_SECONDS=86400      # 24 hours
JWT_REMEMBER_ME_VALIDITY_SECONDS=2592000  # 30 days
JWT_ISSUER=agentic-brain
JWT_AUDIENCE=agentic-brain

# OAuth2/OIDC Configuration
OAUTH2_ENABLED=true
OAUTH2_ISSUER_URI=https://auth.example.com
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
OAUTH2_AUDIENCE=https://api.example.com
OAUTH2_SCOPES=openid,profile,email
OAUTH2_JWKS_URI=https://auth.example.com/.well-known/jwks.json

# Session Configuration
SESSION_AUTH_ENABLED=true
SESSION_TIMEOUT_SECONDS=1800          # 30 minutes
SESSION_COOKIE_NAME=AGENTIC_SESSION
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax
REMEMBER_ME_ENABLED=true
REMEMBER_ME_TIMEOUT_SECONDS=2592000   # 30 days

# Basic Auth Configuration
BASIC_AUTH_ENABLED=true
BASIC_AUTH_REALM=agentic-brain

# API Keys (comma-separated)
API_KEYS=key1,key2,key3

# Password Encoding
PASSWORD_ENCODER=bcrypt               # bcrypt or argon2
BCRYPT_ROUNDS=12
```

### Python Configuration

```python
from agentic_brain.auth import (
    AuthConfig,
    JWTConfig,
    OAuth2Config,
    SessionConfig,
    BasicAuthConfig,
)

config = AuthConfig(
    enabled=True,
    jwt=JWTConfig(
        secret="your-512-bit-secret",
        algorithm="HS512",
        token_validity_seconds=86400,
        token_validity_seconds_for_remember_me=2592000,
        issuer="my-app",
        audience="my-app",
    ),
    oauth2=OAuth2Config(
        enabled=True,
        issuer_uri="https://auth.example.com",
        client_id="my-client",
        client_secret="my-secret",
    ),
    session=SessionConfig(
        enabled=True,
        timeout_seconds=1800,
        remember_me_enabled=True,
    ),
    basic=BasicAuthConfig(
        enabled=True,
        realm="my-app",
    ),
    api_keys=["key1", "key2"],
    public_paths=["/health", "/ready", "/docs"],
)
```

---

## Role-Based Access Control

### Using Decorators

```python
from agentic_brain.auth import require_role, require_authority, require_authenticated

# Require specific role
@app.get("/admin/users")
@require_role("ADMIN")
async def list_users():
    return {"users": [...]}

# Require any of multiple roles
@app.get("/moderator/reports")
@require_role("ADMIN", "MODERATOR")
async def get_reports():
    return {"reports": [...]}

# Require specific authority
@app.post("/users")
@require_authority("USER_CREATE")
async def create_user(user: UserCreate):
    return {"created": True}

# Require all authorities
@app.delete("/users/{id}")
@require_authority("USER_DELETE", "USER_MANAGE", require_all=True)
async def delete_user(id: str):
    return {"deleted": True}

# Just require authentication (any role)
@app.get("/profile")
@require_authenticated
async def get_profile():
    user = current_user()
    return {"login": user.login}
```

### Using Dependencies

```python
from fastapi import Depends
from agentic_brain.auth import RoleChecker, AuthorityChecker, AuthenticationChecker

# Role-based dependency
@app.get("/admin", dependencies=[Depends(RoleChecker(["ADMIN"]))])
async def admin_endpoint():
    return {"admin": True}

# Authority-based dependency
@app.get("/reports", dependencies=[Depends(AuthorityChecker(["REPORT_VIEW"]))])
async def view_reports():
    return {"reports": [...]}

# Authentication-only dependency
@app.get("/me", dependencies=[Depends(AuthenticationChecker())])
async def get_me():
    return {"authenticated": True}
```

### Spring Security-Style Expressions

```python
from agentic_brain.auth.decorators import pre_authorize

# Simple role check
@app.get("/admin")
@pre_authorize("hasRole('ADMIN')")
async def admin_only():
    pass

# OR expression
@app.get("/content")
@pre_authorize("hasRole('ADMIN') or hasAuthority('CONTENT_MANAGE')")
async def manage_content():
    pass

# AND expression
@app.delete("/critical")
@pre_authorize("hasRole('ADMIN') and hasAuthority('CRITICAL_DELETE')")
async def delete_critical():
    pass

# Any authority
@app.get("/dashboard")
@pre_authorize("hasAnyAuthority('DASHBOARD_VIEW', 'ADMIN')")
async def view_dashboard():
    pass
```

---

## Security Context

Thread-safe and async-safe access to current user:

```python
from agentic_brain.auth import (
    current_user,
    current_user_async,
    is_authenticated,
    has_authority,
    has_any_authority,
    has_role,
    get_current_token,
    get_authorities,
)

# Check authentication
if is_authenticated():
    user = current_user()
    print(f"Logged in as: {user.login}")

# Check roles/authorities
if has_role("ADMIN"):
    print("User is admin")

if has_any_authority("USER_VIEW", "USER_MANAGE"):
    print("User can view or manage users")

# Get all authorities
authorities = get_authorities()  # ["ROLE_ADMIN", "USER_VIEW", ...]

# Get current token
token = get_current_token()
print(f"Expires at: {token.expires_at}")
```

### Running Code as Another User

```python
from agentic_brain.auth import User, run_as_user, SecurityContextManager

# Create admin user
admin = User(login="admin", authorities=["ROLE_ADMIN"])

# Run code as admin
with run_as_user(admin):
    # This code runs with admin privileges
    if has_role("ADMIN"):
        print("Running as admin!")
# Original context restored

# Async support
async with SecurityContextManager(admin):
    user = current_user()
    print(f"Async running as: {user.login}")
```

---

## JWT Token Management

### Generating Tokens

```python
from agentic_brain.auth import JWTAuth, User, AuthConfig

auth = JWTAuth(AuthConfig())

# Create user
user = User(
    id="user-123",
    login="john.doe",
    email="john@example.com",
    first_name="John",
    last_name="Doe",
    authorities=["ROLE_USER", "ROLE_ADMIN"],
)

# Generate token
token = await auth.generate_token(user, remember_me=False)
print(f"Access Token: {token.access_token}")
print(f"Expires In: {token.expires_in} seconds")
print(f"Expires At: {token.expires_at}")

# Generate with remember-me (longer expiry)
long_token = await auth.generate_token(user, remember_me=True)

# Add custom claims
token = await auth.generate_token(
    user,
    extra_claims={
        "tenant_id": "acme-corp",
        "permissions": ["read", "write"],
    }
)
```

### Validating Tokens

```python
# Validate and get user
user = await auth.validate_token(token.access_token)
if user:
    print(f"Valid token for: {user.login}")
    print(f"Authorities: {user.authorities}")
else:
    print("Invalid or expired token")
```

### Revoking Tokens

```python
# Revoke a specific token
success = await auth.revoke_token(token.access_token)
if success:
    print("Token revoked")

# Subsequent validation will fail
user = await auth.validate_token(token.access_token)  # Returns None
```

---

## OAuth2/OIDC Integration

### Configuration for Common Providers

#### Keycloak

```bash
OAUTH2_ENABLED=true
OAUTH2_ISSUER_URI=https://keycloak.example.com/realms/myrealm
OAUTH2_CLIENT_ID=my-app
OAUTH2_CLIENT_SECRET=my-secret
OAUTH2_JWKS_URI=https://keycloak.example.com/realms/myrealm/protocol/openid-connect/certs
```

#### Auth0

```bash
OAUTH2_ENABLED=true
OAUTH2_ISSUER_URI=https://your-tenant.auth0.com/
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
OAUTH2_AUDIENCE=https://api.example.com
OAUTH2_JWKS_URI=https://your-tenant.auth0.com/.well-known/jwks.json
```

#### Okta

```bash
OAUTH2_ENABLED=true
OAUTH2_ISSUER_URI=https://your-org.okta.com/oauth2/default
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
OAUTH2_JWKS_URI=https://your-org.okta.com/oauth2/default/v1/keys
```

#### Azure AD

```bash
OAUTH2_ENABLED=true
OAUTH2_ISSUER_URI=https://login.microsoftonline.com/{tenant-id}/v2.0
OAUTH2_CLIENT_ID=your-client-id
OAUTH2_CLIENT_SECRET=your-client-secret
OAUTH2_JWKS_URI=https://login.microsoftonline.com/{tenant-id}/discovery/v2.0/keys
```

### Token Validation with JWKS

```python
from agentic_brain.auth import OAuth2Auth, AuthConfig

config = AuthConfig()
auth = OAuth2Auth(config)

# Validate an ID token or access token from your IdP
user = await auth.validate_token(id_token)
if user:
    print(f"User: {user.login}")
    print(f"Email: {user.email}")
    print(f"Name: {user.first_name} {user.last_name}")
```

---

## Session Authentication

### Web Application Example

```python
from fastapi import FastAPI, Response, Request
from agentic_brain.auth import SessionAuth, AuthConfig

app = FastAPI()
auth = SessionAuth(AuthConfig())

@app.post("/login")
async def login(username: str, password: str, remember_me: bool, response: Response):
    # Validate credentials (your logic)
    if valid_credentials(username, password):
        from agentic_brain.auth import UsernamePasswordCredentials
        
        result = await auth.authenticate(UsernamePasswordCredentials(
            username=username,
            password=password,
            remember_me=remember_me,
        ))
        
        if result.success:
            # Set session cookie
            response.set_cookie(
                key="AGENTIC_SESSION",
                value=result.token.access_token,
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=result.token.expires_in,
            )
            return {"success": True}
    
    return {"success": False}

@app.post("/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get("AGENTIC_SESSION")
    if session_id:
        await auth.invalidate_session(session_id)
    response.delete_cookie("AGENTIC_SESSION")
    return {"success": True}
```

---

## Basic Auth for Microservices

### Internal Service-to-Service Communication

```python
from agentic_brain.auth import BasicAuth, AuthConfig

config = AuthConfig()
auth = BasicAuth(config)

# Create middleware for internal APIs
from fastapi import Request, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

@app.get("/internal/data")
async def internal_data(credentials: HTTPBasicCredentials = Depends(security)):
    from agentic_brain.auth import UsernamePasswordCredentials
    
    result = await auth.authenticate(UsernamePasswordCredentials(
        username=credentials.username,
        password=credentials.password,
    ))
    
    if not result.success:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {"data": "internal-data"}
```

---

## FastAPI Integration

### Complete Application Setup

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from agentic_brain.auth import (
    JWTAuth,
    AuthConfig,
    set_security_context,
    clear_security_context,
    SecurityContext,
    require_role,
    current_user,
)

app = FastAPI()
auth = JWTAuth(AuthConfig())
bearer_scheme = HTTPBearer(auto_error=False)

# Middleware to set security context
@app.middleware("http")
async def auth_middleware(request, call_next):
    # Extract token from header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = await auth.validate_token(token)
        if user:
            ctx = SecurityContext.from_user(user)
            token_obj = set_security_context(ctx)
            try:
                response = await call_next(request)
                return response
            finally:
                clear_security_context()
    
    return await call_next(request)

# Protected endpoints
@app.get("/admin/dashboard")
@require_role("ADMIN")
async def admin_dashboard():
    user = current_user()
    return {"message": f"Welcome, {user.login}!", "role": "admin"}

@app.get("/user/profile")
@require_role("USER")
async def user_profile():
    user = current_user()
    return {
        "login": user.login,
        "email": user.email,
        "authorities": user.authorities,
    }

# Public endpoint
@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

## Security Best Practices

### JWT Security

1. **Use HS512 or RS256** — HS256 is minimum, HS512 recommended for symmetric
2. **64+ character secrets** — Generate cryptographically random secrets
3. **Short token lifetimes** — 15 minutes to 24 hours for access tokens
4. **Validate all claims** — Check `exp`, `iss`, `aud`, `jti`
5. **Use HTTPS only** — Never transmit tokens over HTTP
6. **Implement token revocation** — For logout and compromised tokens

### OAuth2 Security

1. **Use PKCE** — Proof Key for Code Exchange for public clients
2. **Validate state parameter** — Prevent CSRF attacks
3. **Verify token signatures** — Always validate with JWKS
4. **Check audience claim** — Ensure token is for your API
5. **Short authorization code lifetime** — 60 seconds maximum

### Session Security

1. **Secure cookies** — `Secure=true`, `HttpOnly=true`, `SameSite=Lax/Strict`
2. **Regenerate session ID** — After authentication
3. **Idle timeout** — 30 minutes for sensitive applications
4. **Absolute timeout** — 8-12 hours maximum session length
5. **Session fixation protection** — New session on login

### Password Security

1. **Use bcrypt or Argon2** — Never MD5/SHA1/SHA256 alone
2. **12+ bcrypt rounds** — Adjust based on hardware
3. **Never store plaintext** — Hash immediately
4. **Rate limit attempts** — Prevent brute force
5. **Account lockout** — After 5-10 failed attempts

### Production Checklist

- [ ] `AUTH_ENABLED=true`
- [ ] Strong JWT secret (64+ random characters)
- [ ] Secrets in secrets manager (not `.env`)
- [ ] HTTPS/TLS enforced
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] Audit logging active
- [ ] Token revocation implemented
- [ ] Session timeout configured
- [ ] Password policy enforced

---

## Error Responses

### 401 Unauthorized

```json
{
    "detail": "Authentication required",
    "headers": {"WWW-Authenticate": "Bearer"}
}
```

### 403 Forbidden

```json
{
    "detail": "Required roles: ADMIN, MODERATOR"
}
```

```json
{
    "detail": "Required authorities: USER_DELETE, USER_MANAGE"
}
```

```json
{
    "detail": "Access denied by expression: hasRole('ADMIN') and hasAuthority('CRITICAL')"
}
```

---

## Constants Reference

```python
from agentic_brain.auth import (
    # Roles
    ROLE_ADMIN,      # "ROLE_ADMIN"
    ROLE_USER,       # "ROLE_USER"
    ROLE_ANONYMOUS,  # "ROLE_ANONYMOUS"
    
    # Authorities
    AUTHORITY_ADMIN, # "ADMIN"
    AUTHORITY_USER,  # "USER"
)
```

---

## Dependencies

```bash
# JWT support
pip install python-jose[cryptography]

# Or with bcrypt for password hashing
pip install python-jose[cryptography] bcrypt

# Or install all auth extras
pip install agentic-brain[auth]
```

---

## Enterprise Authentication Providers

Agentic Brain supports enterprise authentication patterns for large-scale deployments.

### API Key Authentication (Full Implementation)

Secure API key management with scopes, rate limiting, and key rotation:

```python
from agentic_brain.auth import APIKeyAuthProvider, APIKeyConfig, APIKeyCredentials

# Configure API key provider
config = APIKeyConfig(
    key_header="X-API-Key",
    key_prefix="ak_",
    enable_rate_limiting=True,
    default_rate_limit_per_minute=60,
    default_rate_limit_per_hour=1000,
)
auth = APIKeyAuthProvider(api_key_config=config)

# Create a new API key
key_info, plaintext_key = await auth.create_key(
    name="Production API Key",
    scopes=["read", "write", "chat"],
    expires_in_days=365,
    rate_limit_per_minute=100,
    metadata={"team": "engineering"}
)
print(f"API Key (save this!): {plaintext_key}")

# Authenticate with API key
result = await auth.authenticate(APIKeyCredentials(api_key=plaintext_key))
if result.success:
    print(f"Authenticated: {result.user.login}")
    print(f"Authorities: {result.user.authorities}")

# Rotate a key (creates new, revokes old)
new_key_info, new_plaintext = await auth.rotate_key(key_info.key_id)

# Revoke a key
await auth.revoke_key(key_info.key_id)
```

#### API Key Scopes

| Scope | Authority Granted | Description |
|-------|-------------------|-------------|
| `read` | `API_READ` | Read-only access |
| `write` | `API_WRITE` | Create/update access |
| `delete` | `API_DELETE` | Delete access |
| `admin` | `ROLE_ADMIN` | Full admin access |
| `chat` | `CHAT_ACCESS` | Chat endpoint access |
| `agents` | `AGENTS_ACCESS` | Agent management |
| `plugins` | `PLUGINS_ACCESS` | Plugin management |
| `webhooks` | `WEBHOOKS_ACCESS` | Webhook management |

#### API Key Configuration

```bash
# API Key Configuration
API_KEY_HEADER=X-API-Key
API_KEY_PREFIX=ak_
API_KEY_LENGTH=32
API_KEY_RATE_LIMIT_PER_MINUTE=60
API_KEY_RATE_LIMIT_PER_HOUR=1000
API_KEY_ENABLE_RATE_LIMITING=true
```

---

### LDAP/Active Directory (Coming Soon)

🚧 **Status: Coming Soon** 🚧

Enterprise LDAP authentication with Active Directory and OpenLDAP support:

```python
from agentic_brain.auth import LDAPAuthProvider, LDAPConfig

# Active Directory configuration
config = LDAPConfig(
    server="ldap://ad.company.com",
    port=389,
    use_ssl=True,
    bind_dn="CN=ServiceAccount,OU=Service Accounts,DC=company,DC=com",
    bind_password="${AD_BIND_PASSWORD}",
    base_dn="DC=company,DC=com",
    user_search_base="OU=Users,DC=company,DC=com",
    user_search_filter="(sAMAccountName={username})",
    group_role_mapping={
        "CN=Admins,OU=Groups,DC=company,DC=com": ["ROLE_ADMIN"],
        "CN=Users,OU=Groups,DC=company,DC=com": ["ROLE_USER"],
    },
)
auth = LDAPAuthProvider(ldap_config=config)

# OpenLDAP configuration
openldap_config = LDAPConfig(
    server="ldap://ldap.company.com",
    bind_dn="cn=admin,dc=company,dc=com",
    base_dn="dc=company,dc=com",
    user_search_filter="(uid={username})",
)
```

**Planned features:**
- Connection pooling
- Nested group resolution
- LDAPS (LDAP over SSL)
- StartTLS support
- Group caching

---

### SAML 2.0 SSO (Coming Soon)

🚧 **Status: Coming Soon** 🚧

SAML 2.0 Single Sign-On with major identity providers:

```python
from agentic_brain.auth import SAMLAuthProvider, SAMLConfig

# Okta configuration
config = SAMLConfig(
    sp_entity_id="https://app.example.com",
    sp_assertion_consumer_service_url="https://app.example.com/auth/saml/acs",
    idp_metadata_url="https://company.okta.com/app/xxx/sso/saml/metadata",
    group_role_mapping={
        "Admins": ["ROLE_ADMIN", "ROLE_USER"],
        "Users": ["ROLE_USER"],
    },
)
auth = SAMLAuthProvider(saml_config=config)

# Initiate SSO (redirect user to IdP)
auth_request = await auth.create_auth_request(relay_state="/dashboard")
# Redirect to: auth_request.redirect_url

# Process SAML response (at ACS endpoint)
result = await auth.process_response(saml_response_xml)
```

#### Supported Identity Providers

| Provider | Configuration Example |
|----------|----------------------|
| **Okta** | `idp_metadata_url=https://company.okta.com/app/xxx/sso/saml/metadata` |
| **Azure AD** | `idp_metadata_url=https://login.microsoftonline.com/{tenant}/federationmetadata/...` |
| **OneLogin** | `idp_metadata_url=https://company.onelogin.com/saml/metadata/xxx` |
| **Google Workspace** | `idp_metadata_url=https://accounts.google.com/samlsso/...` |

**Planned features:**
- SP-initiated SSO
- IdP-initiated SSO
- Single Logout (SLO)
- Signed/encrypted assertions
- Attribute mapping

---

### Multi-Factor Authentication (Coming Soon)

🚧 **Status: Coming Soon** 🚧

Multi-factor authentication with TOTP, SMS, and recovery codes:

```python
from agentic_brain.auth import MFAProvider, MFAConfig

config = MFAConfig(
    totp_issuer="Agentic Brain",
    totp_digits=6,
    recovery_code_count=10,
    require_mfa_for_roles=["ROLE_ADMIN"],
)
mfa = MFAProvider(config)

# Setup TOTP for a user
setup = await mfa.setup_totp(user_id="user-123")
print(f"Scan QR code: {setup.qr_code_uri}")
print(f"Recovery codes: {setup.recovery_codes}")

# Verify TOTP code
result = await mfa.verify_totp(user_id="user-123", code="123456")
if result.success:
    print("MFA verified!")

# Check if MFA is required
user = User(login="admin", authorities=["ROLE_ADMIN"])
if await mfa.is_mfa_required(user):
    print("MFA required for this user")
```

**Planned features:**
- TOTP (Google Authenticator, Authy)
- SMS verification codes
- Email verification codes
- Recovery codes
- Device remembering
- FIDO2/WebAuthn support

---

## See Also

- [SECURITY.md](./SECURITY.md) — Security overview and secrets management
- [ENTERPRISE.md](./ENTERPRISE.md) — Enterprise features overview
- [configuration.md](./configuration.md) — All configuration options
- [api-reference.md](./api-reference.md) — API documentation

---

**Last Updated**: 2026-03-21
