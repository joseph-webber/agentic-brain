# Security Architecture

<div align="center">

[![Security](https://img.shields.io/badge/Security-Enterprise_Grade-00A86B?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAxTDMgNXY2YzAgNS41NSAzLjg0IDEwLjc0IDkgMTIgNS4xNi0xLjI2IDktNi40NSA5LTEyVjVsLTktNHptMCAyLjE4bDcgMy4xMnY1LjdjMCA0LjgzLTMuMjMgOS4zNi03IDEwLjYzLTMuNzctMS4yNy03LTUuOC03LTEwLjYzVjYuM2w3LTMuMTJ6Ii8+PC9zdmc+)](./SECURITY.md)
[![OWASP](https://img.shields.io/badge/OWASP-Top_10_Protected-000000?style=for-the-badge&logo=owasp&logoColor=white)](./SECURITY.md)
[![Zero Trust](https://img.shields.io/badge/Zero_Trust-Architecture-4A90D9?style=for-the-badge)](./SECURITY.md)
[![Pen Tested](https://img.shields.io/badge/Penetration-Tested-DC143C?style=for-the-badge)](./SECURITY.md)

**Defense in Depth · Zero Trust · Secure by Default**

*Built for organizations where security is non-negotiable.*

</div>

---

## 📋 Table of Contents

- [Security Overview](#security-overview)
- [Authentication & Authorization](#authentication--authorization)
- [Cryptography](#cryptography)
- [Network Security](#network-security)
- [Application Security](#application-security)
- [Data Protection](#data-protection)
- [Audit & Monitoring](#audit--monitoring)
- [Secrets Management](#secrets-management)
- [Vulnerability Management](#vulnerability-management)
- [Security Testing](#security-testing)
- [Incident Response](#incident-response)
- [Production Hardening](#production-hardening)

---

## Security Overview

### Security Architecture

Agentic Brain implements **defense in depth** with multiple security layers:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              SECURITY LAYERS                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 1: PERIMETER                                                      │ │
│  │  • WAF (Web Application Firewall)                                        │ │
│  │  • DDoS Protection                                                       │ │
│  │  • Rate Limiting (60 req/min/IP)                                        │ │
│  │  • Geo-blocking (configurable)                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 2: AUTHENTICATION                                                 │ │
│  │  • JWT with RS256/ES256                                                  │ │
│  │  • OAuth 2.0 / OIDC                                                      │ │
│  │  • API Key (HMAC-SHA256)                                                │ │
│  │  • mTLS (mutual TLS)                                                    │ │
│  │  • MFA Support                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 3: AUTHORIZATION                                                  │ │
│  │  • RBAC (Role-Based Access Control)                                     │ │
│  │  • ABAC (Attribute-Based Access Control)                                │ │
│  │  • Tenant Isolation                                                     │ │
│  │  • Resource-level permissions                                           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 4: APPLICATION                                                    │ │
│  │  • Input Validation (Pydantic)                                          │ │
│  │  • Output Encoding                                                       │ │
│  │  • CSRF Protection                                                       │ │
│  │  • SQL/Cypher Injection Prevention                                      │ │
│  │  • Prompt Injection Defense                                             │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                     │                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  LAYER 5: DATA                                                           │ │
│  │  • Encryption at Rest (AES-256-GCM)                                     │ │
│  │  • Encryption in Transit (TLS 1.3)                                      │ │
│  │  • Field-level Encryption                                               │ │
│  │  • Key Management (KMS/HSM)                                             │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Zero Trust Principles

| Principle | Implementation |
|-----------|----------------|
| **Never Trust, Always Verify** | Every request authenticated, regardless of source |
| **Least Privilege** | Minimum necessary permissions per role |
| **Assume Breach** | Comprehensive logging, micro-segmentation |
| **Verify Explicitly** | Multi-factor authentication, continuous validation |
| **Secure All Paths** | East-west traffic encrypted, service mesh ready |

---

## Authentication & Authorization

### JWT Authentication

```python
from agentic_brain.auth import JWTAuth

# Configure JWT authentication
auth = JWTAuth(
    algorithm="RS256",  # RSA for production (ES256 also supported)
    issuer="https://auth.company.com",
    audience="agentic-brain",
    public_key_url="https://auth.company.com/.well-known/jwks.json",
    token_expiry_minutes=60,
    refresh_token_expiry_days=7
)

# Verify token
claims = await auth.verify_token(token)
# Returns: {"sub": "user-123", "roles": ["analyst"], "tenant": "acme-corp"}
```

**JWT Configuration:**

```yaml
# config/auth.yaml
jwt:
  algorithm: RS256  # RS256, RS384, RS512, ES256, ES384, ES512
  issuer: "https://auth.company.com"
  audience: "agentic-brain"
  
  # Key sources (in priority order)
  keys:
    - type: jwks
      url: "https://auth.company.com/.well-known/jwks.json"
      cache_ttl_seconds: 3600
    - type: pem
      path: "/etc/agentic-brain/keys/public.pem"
  
  # Token settings
  access_token_expiry_minutes: 60
  refresh_token_expiry_days: 7
  require_exp: true
  require_iat: true
  clock_skew_seconds: 30
  
  # Claims validation
  required_claims:
    - sub
    - iat
    - exp
  
  custom_claims:
    tenant_id: "tid"
    roles: "roles"
```

### OAuth 2.0 / OIDC

```python
from agentic_brain.auth import OIDCAuth

# Configure OIDC
oidc = OIDCAuth(
    provider="okta",  # or: auth0, azure-ad, google, keycloak
    client_id="${OIDC_CLIENT_ID}",
    client_secret="${OIDC_CLIENT_SECRET}",
    discovery_url="https://company.okta.com/.well-known/openid-configuration",
    scopes=["openid", "profile", "email", "groups"]
)

# Supported providers
PROVIDERS = {
    "okta": "https://{domain}.okta.com",
    "auth0": "https://{domain}.auth0.com",
    "azure-ad": "https://login.microsoftonline.com/{tenant}/v2.0",
    "google": "https://accounts.google.com",
    "keycloak": "https://{host}/realms/{realm}",
    "cognito": "https://cognito-idp.{region}.amazonaws.com/{pool_id}"
}
```

### API Key Management

```python
from agentic_brain.auth import APIKeyManager

# Create and manage API keys
key_manager = APIKeyManager(
    hash_algorithm="sha256",
    key_prefix="ab_",
    rotation_days=90
)

# Generate new key
key = await key_manager.create(
    name="production-service",
    scopes=["read:sessions", "write:messages"],
    rate_limit=1000,  # requests per minute
    expires_days=365,
    ip_whitelist=["10.0.0.0/8", "192.168.0.0/16"]
)

# Validate key
valid = await key_manager.validate(api_key)
```

**API Key Format:**

```
ab_prod_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
│   │    │
│   │    └── 32-char random (base62)
│   └── Environment (prod, dev, test)
└── Prefix (always "ab_")
```

### Role-Based Access Control (RBAC)

```yaml
# config/rbac.yaml
roles:
  admin:
    description: "Full system access"
    permissions:
      - "*"  # All permissions
    
  analyst:
    description: "Read-only analytics access"
    permissions:
      - "sessions:read"
      - "messages:read"
      - "analytics:read"
    
  developer:
    description: "Development access"
    permissions:
      - "sessions:*"
      - "messages:*"
      - "plugins:read"
      - "plugins:execute"
    
  service:
    description: "Service account"
    permissions:
      - "messages:write"
      - "sessions:create"
    constraints:
      require_api_key: true
      rate_limit: 10000

# Permission format: resource:action
# Wildcards: "*" = all, "resource:*" = all actions on resource
```

### Attribute-Based Access Control (ABAC)

```python
from agentic_brain.auth import ABACPolicy

# Define policies
policy = ABACPolicy(
    rules=[
        {
            "name": "tenant-isolation",
            "condition": "subject.tenant_id == resource.tenant_id",
            "effect": "allow"
        },
        {
            "name": "business-hours",
            "condition": "time.hour >= 9 and time.hour <= 17",
            "effect": "allow",
            "resources": ["financial:*"]
        },
        {
            "name": "geo-restriction",
            "condition": "subject.country in ['AU', 'NZ', 'SG']",
            "effect": "allow",
            "resources": ["apra:*"]
        }
    ]
)
```

### Multi-Factor Authentication (MFA)

```yaml
# config/mfa.yaml
mfa:
  enabled: true
  methods:
    - totp  # Time-based OTP (Google Authenticator, Authy)
    - webauthn  # Hardware keys (YubiKey, TouchID)
    - sms  # SMS codes (backup only)
    - email  # Email codes (backup only)
  
  policy:
    require_for_roles: [admin, financial]
    require_for_actions: [delete, export, config_change]
    remember_device_days: 30
    
  totp:
    issuer: "Agentic Brain"
    algorithm: SHA256
    digits: 6
    period: 30
```

---

## Cryptography

### Encryption at Rest

```yaml
# config/encryption.yaml
encryption:
  at_rest:
    enabled: true
    algorithm: AES-256-GCM
    
    # Key management
    key_provider: aws-kms  # or: azure-keyvault, gcp-kms, hashicorp-vault, local
    
    # AWS KMS configuration
    aws_kms:
      key_id: "alias/agentic-brain-prod"
      region: "ap-southeast-2"
      key_rotation: true
    
    # Field-level encryption
    encrypted_fields:
      messages:
        - content
        - metadata.pii
      users:
        - email
        - phone
      sessions:
        - context
    
    # Per-tenant keys (enterprise)
    tenant_keys:
      enabled: true
      isolation: "key-per-tenant"
```

### Encryption in Transit

```yaml
encryption:
  in_transit:
    tls:
      min_version: "1.3"
      max_version: "1.3"
      cipher_suites:
        - TLS_AES_256_GCM_SHA384
        - TLS_CHACHA20_POLY1305_SHA256
        - TLS_AES_128_GCM_SHA256
      
      # Certificate configuration
      cert_file: "/etc/ssl/certs/agentic-brain.crt"
      key_file: "/etc/ssl/private/agentic-brain.key"
      ca_file: "/etc/ssl/certs/ca-bundle.crt"
      
      # Certificate pinning
      pinning:
        enabled: true
        pins:
          - "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
      
      # HSTS
      hsts:
        enabled: true
        max_age: 31536000
        include_subdomains: true
        preload: true
    
    # Mutual TLS (for service-to-service)
    mtls:
      enabled: true  # In enterprise mode
      client_ca: "/etc/ssl/certs/client-ca.crt"
      verify_client: required
```

### Key Management

```python
from agentic_brain.crypto import KeyManager

# Initialize key manager
keys = KeyManager(
    provider="aws-kms",  # or: azure-keyvault, gcp-kms, hashicorp-vault
    master_key_id="alias/agentic-brain"
)

# Generate data encryption key
dek = await keys.generate_data_key(
    key_spec="AES_256",
    context={"tenant": "acme-corp", "purpose": "message-encryption"}
)

# Encrypt data
ciphertext = await keys.encrypt(
    plaintext=sensitive_data,
    key_id="alias/agentic-brain",
    context={"tenant": "acme-corp"}
)

# Key rotation
await keys.rotate(
    key_id="alias/agentic-brain",
    retain_old_versions=3
)
```

### Cryptographic Standards

| Purpose | Algorithm | Key Size | Notes |
|---------|-----------|----------|-------|
| **Symmetric Encryption** | AES-256-GCM | 256-bit | NIST approved |
| **Asymmetric Encryption** | RSA-OAEP | 4096-bit | Key exchange |
| **Digital Signatures** | ECDSA P-384 | 384-bit | JWT signing |
| **Key Derivation** | HKDF-SHA256 | 256-bit | Per-tenant keys |
| **Password Hashing** | Argon2id | - | Memory-hard |
| **Message Authentication** | HMAC-SHA256 | 256-bit | API signatures |
| **Random Generation** | CSPRNG | - | OS-provided |

---

## Network Security

### Security Headers

All responses include these security headers:

```python
SECURITY_HEADERS = {
    # Prevent MIME sniffing
    "X-Content-Type-Options": "nosniff",
    
    # Prevent clickjacking
    "X-Frame-Options": "DENY",
    
    # XSS protection (legacy browsers)
    "X-XSS-Protection": "1; mode=block",
    
    # HTTPS enforcement
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    
    # Content Security Policy
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    
    # Referrer control
    "Referrer-Policy": "strict-origin-when-cross-origin",
    
    # Feature restrictions
    "Permissions-Policy": (
        "accelerometer=(), "
        "camera=(), "
        "geolocation=(), "
        "gyroscope=(), "
        "magnetometer=(), "
        "microphone=(), "
        "payment=(), "
        "usb=()"
    ),
    
    # Cross-origin isolation
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin"
}
```

### Rate Limiting

```yaml
# config/rate-limiting.yaml
rate_limiting:
  enabled: true
  
  # Global limits
  global:
    requests_per_minute: 60
    requests_per_hour: 1000
    burst_size: 10
  
  # Per-endpoint limits
  endpoints:
    "/api/v1/chat":
      requests_per_minute: 30
      burst_size: 5
    "/api/v1/sessions":
      requests_per_minute: 100
    "/api/v1/bulk/*":
      requests_per_minute: 10
  
  # Per-tier limits (API keys)
  tiers:
    free:
      requests_per_minute: 10
      requests_per_day: 100
    pro:
      requests_per_minute: 60
      requests_per_day: 10000
    enterprise:
      requests_per_minute: 1000
      requests_per_day: unlimited
  
  # Response
  response:
    status_code: 429
    headers:
      - X-RateLimit-Limit
      - X-RateLimit-Remaining
      - X-RateLimit-Reset
      - Retry-After
```

### CORS Configuration

```yaml
# config/cors.yaml
cors:
  enabled: true
  
  # Allowed origins
  allowed_origins:
    - "https://app.company.com"
    - "https://*.company.com"
  
  # Or allow specific patterns
  origin_patterns:
    - "^https://.*\\.company\\.com$"
  
  # Allowed methods
  allowed_methods:
    - GET
    - POST
    - PUT
    - DELETE
    - OPTIONS
  
  # Allowed headers
  allowed_headers:
    - Authorization
    - Content-Type
    - X-Request-ID
    - X-API-Key
  
  # Exposed headers
  exposed_headers:
    - X-Request-ID
    - X-RateLimit-Remaining
  
  # Credentials
  allow_credentials: true
  
  # Preflight cache
  max_age: 3600
```

### Network Isolation

```yaml
# docker-compose.prod.yml
services:
  agentic-brain:
    networks:
      - frontend  # Public-facing
      - backend   # Internal only
    
  neo4j:
    networks:
      - backend   # Internal only
    # NOT exposed to internet
    
  redis:
    networks:
      - backend   # Internal only
    # NOT exposed to internet

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access
```

---

## Application Security

### Input Validation

```python
from pydantic import BaseModel, Field, validator
from agentic_brain.validation import sanitize_html, sanitize_sql

class ChatMessage(BaseModel):
    session_id: str = Field(
        ...,
        regex=r'^[a-zA-Z0-9_-]{1,64}$',
        description="Alphanumeric session identifier"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User message content"
    )
    user_id: str | None = Field(
        None,
        regex=r'^[a-zA-Z0-9_-]{1,64}$'
    )
    
    @validator('message')
    def sanitize_message(cls, v):
        # Remove potential XSS
        v = sanitize_html(v)
        # Remove null bytes
        v = v.replace('\x00', '')
        return v
    
    @validator('session_id', 'user_id')
    def validate_identifier(cls, v):
        if v:
            # Prevent path traversal
            if '..' in v or '/' in v or '\\' in v:
                raise ValueError('Invalid characters in identifier')
        return v
```

### SQL/Cypher Injection Prevention

```python
# ALWAYS use parameterized queries
# ❌ NEVER do this:
query = f"MATCH (n:Session {{id: '{session_id}'}}) RETURN n"

# ✅ ALWAYS do this:
query = "MATCH (n:Session {id: $session_id}) RETURN n"
result = await neo4j.execute(query, {"session_id": session_id})
```

**Injection Prevention Controls:**

| Control | Implementation | Status |
|---------|----------------|--------|
| Parameterized Queries | All database operations | ✅ |
| Input Type Validation | Pydantic models | ✅ |
| Character Whitelisting | Regex patterns | ✅ |
| Query Complexity Limits | Max depth/nodes | ✅ |
| Prepared Statements | Neo4j driver | ✅ |

### Prompt Injection Defense

```python
from agentic_brain.security import PromptGuard

guard = PromptGuard(
    detection_models=["openai-moderation", "local-classifier"],
    actions={
        "injection_attempt": "block",
        "jailbreak_attempt": "block",
        "data_exfiltration": "alert_and_block",
        "prompt_leaking": "sanitize"
    }
)

# Check message before processing
result = await guard.check(user_message)
if result.threat_detected:
    raise SecurityException(f"Blocked: {result.threat_type}")
```

**Prompt Injection Defenses:**

| Defense | Description |
|---------|-------------|
| **System Prompt Isolation** | System prompts separated from user input |
| **Input Sanitization** | Special characters escaped |
| **Output Filtering** | Sensitive data redacted from responses |
| **Instruction Hierarchy** | System > Assistant > User priority |
| **Canary Tokens** | Detect prompt extraction attempts |
| **Rate Limiting** | Limit rapid prompt variations |

### XSS Protection

```python
from agentic_brain.security import XSSFilter

xss_filter = XSSFilter(
    mode="strict",  # or: permissive (allows safe HTML)
    allowed_tags=["b", "i", "u", "code", "pre"],
    allowed_attributes={"a": ["href"], "img": ["src", "alt"]},
    strip_scripts=True,
    encode_entities=True
)

# All output is filtered
safe_response = xss_filter.clean(response)
```

---

## Data Protection

### Data Classification

```yaml
# config/data-classification.yaml
classification:
  levels:
    public:
      retention: unlimited
      encryption: optional
      access: all_authenticated
      
    internal:
      retention: 5_years
      encryption: at_rest
      access: employees
      
    confidential:
      retention: 7_years
      encryption: at_rest_and_transit
      access: need_to_know
      audit: full
      
    restricted:
      retention: as_required
      encryption: field_level
      access: explicit_approval
      audit: enhanced
      mfa_required: true

  # Auto-classification rules
  auto_classify:
    - pattern: "\\b\\d{3}-\\d{2}-\\d{4}\\b"  # SSN
      level: restricted
      tag: pii
    - pattern: "\\b[A-Z]{2}\\d{6}\\b"  # Passport
      level: restricted
      tag: pii
    - pattern: "\\b\\d{16}\\b"  # Credit card
      level: restricted
      tag: pci
```

### PII Detection & Protection

```python
from agentic_brain.privacy import PIIDetector, PIIProtector

detector = PIIDetector(
    models=["spacy-ner", "regex-patterns", "ml-classifier"],
    entity_types=[
        "person_name", "email", "phone", "ssn", "passport",
        "credit_card", "bank_account", "medical_id", "ip_address",
        "address", "date_of_birth", "driver_license"
    ]
)

protector = PIIProtector(
    default_action="tokenize",  # or: mask, encrypt, redact
    actions_by_type={
        "ssn": "tokenize",
        "credit_card": "tokenize",
        "email": "mask",  # j***@example.com
        "phone": "partial_mask",  # ***-***-1234
        "person_name": "pseudonymize"
    }
)

# Detect and protect PII
entities = await detector.detect(text)
protected_text = await protector.protect(text, entities)
```

### Data Isolation (Multi-Tenancy)

```python
from agentic_brain.tenancy import TenantContext

# All operations are tenant-scoped
async with TenantContext(tenant_id="acme-corp") as ctx:
    # Queries automatically filtered to tenant
    sessions = await db.query("MATCH (s:Session) RETURN s")
    # Returns ONLY acme-corp sessions
    
    # Cross-tenant access blocked
    try:
        other_data = await db.query(
            "MATCH (s:Session {tenant: 'other-corp'}) RETURN s"
        )
    except TenantViolation:
        # Blocked and logged
        pass
```

---

## Audit & Monitoring

### Audit Logging

```python
from agentic_brain.audit import AuditLogger

audit = AuditLogger(
    destinations=["file", "siem", "neo4j"],
    format="json",
    include_fields=[
        "timestamp", "event_type", "actor", "action",
        "resource", "outcome", "client_ip", "user_agent",
        "request_id", "duration_ms"
    ],
    exclude_fields=["message_content"],  # Never log content
    retention_days=2555,  # 7 years
    tamper_evident=True  # Cryptographic chaining
)

# Automatic audit events
@audit.log_action("session.create")
async def create_session(session_id: str, user_id: str):
    ...

# Manual audit events
await audit.log({
    "event_type": "data_export",
    "actor": user_id,
    "resource": f"session:{session_id}",
    "outcome": "success",
    "details": {"format": "json", "records": 150}
})
```

**Audit Event Types:**

| Category | Events |
|----------|--------|
| **Authentication** | login, logout, mfa_challenge, token_refresh, api_key_used |
| **Authorization** | permission_granted, permission_denied, role_change |
| **Data Access** | session_read, message_read, bulk_export, search |
| **Data Modification** | session_create, message_create, session_delete |
| **Configuration** | config_change, key_rotation, user_create |
| **Security** | rate_limit_exceeded, injection_attempt, suspicious_activity |

### SIEM Integration

```yaml
# config/siem.yaml
siem:
  enabled: true
  
  # Splunk
  splunk:
    enabled: true
    hec_url: "https://splunk.company.com:8088"
    token: "${SPLUNK_HEC_TOKEN}"
    index: "agentic-brain"
    source: "agentic-brain-api"
    
  # Datadog
  datadog:
    enabled: true
    api_key: "${DATADOG_API_KEY}"
    site: "datadoghq.com"
    service: "agentic-brain"
    
  # Elastic/ELK
  elasticsearch:
    enabled: true
    hosts: ["https://elastic.company.com:9200"]
    index_pattern: "agentic-brain-audit-%Y.%m.%d"
    
  # AWS CloudWatch
  cloudwatch:
    enabled: true
    log_group: "/agentic-brain/audit"
    region: "ap-southeast-2"
```

### Security Monitoring

```yaml
# config/monitoring.yaml
monitoring:
  alerts:
    - name: "brute_force_detection"
      condition: "auth_failure_count > 10 in 5m for same IP"
      severity: high
      action: block_ip
      
    - name: "unusual_data_access"
      condition: "data_export_count > 5 in 1h for same user"
      severity: medium
      action: alert_security_team
      
    - name: "after_hours_access"
      condition: "admin_action AND time NOT IN business_hours"
      severity: medium
      action: require_mfa
      
    - name: "privilege_escalation"
      condition: "role_change TO admin"
      severity: high
      action: alert_and_audit
```

---

## Secrets Management

### Supported Secret Managers

```yaml
# config/secrets.yaml
secrets:
  provider: hashicorp-vault  # or: aws-secrets-manager, azure-keyvault, gcp-secret-manager
  
  # HashiCorp Vault
  vault:
    address: "https://vault.company.com:8200"
    auth_method: kubernetes  # or: token, approle, aws-iam
    role: "agentic-brain"
    secret_path: "secret/data/agentic-brain"
    
  # AWS Secrets Manager
  aws:
    region: "ap-southeast-2"
    secret_prefix: "agentic-brain/"
    
  # Environment variable fallback
  env:
    enabled: true
    prefix: "AB_"
```

### Secret Rotation

```python
from agentic_brain.secrets import SecretRotator

rotator = SecretRotator(
    secrets=[
        {"name": "db_password", "rotation_days": 90},
        {"name": "api_keys", "rotation_days": 30},
        {"name": "jwt_secret", "rotation_days": 7}
    ]
)

# Automatic rotation
await rotator.rotate_all()

# Zero-downtime rotation
await rotator.rotate("api_keys", grace_period_hours=24)
```

### Secrets Best Practices

| Practice | Implementation |
|----------|----------------|
| **Never in code** | All secrets from environment/vault |
| **Never in logs** | Automatic redaction |
| **Encrypted at rest** | Vault/KMS encryption |
| **Rotation** | Automated 30-90 day rotation |
| **Least privilege** | Per-service credentials |
| **Audit trail** | All access logged |

---

## Vulnerability Management

### Dependency Scanning

```bash
# Scan for vulnerabilities
ab security scan

# Output:
# ┌─────────────────────────────────────────────────────────────┐
# │                    SECURITY SCAN RESULTS                     │
# ├─────────────────────────────────────────────────────────────┤
# │ Scanned: 47 dependencies                                     │
# │ Vulnerabilities: 0 critical, 0 high, 2 medium, 5 low        │
# │ License Issues: 0                                            │
# │ Outdated: 3                                                  │
# └─────────────────────────────────────────────────────────────┘
```

### Container Scanning

```yaml
# .github/workflows/security.yml
security-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: aquasecurity/trivy-action@master
      with:
        image-ref: 'agentic-brain:latest'
        severity: 'CRITICAL,HIGH'
        exit-code: '1'
```

### Penetration Testing

| Test Type | Frequency | Scope |
|-----------|-----------|-------|
| **Automated DAST** | Weekly | API endpoints |
| **Automated SAST** | Every commit | Source code |
| **Manual Pen Test** | Annually | Full application |
| **Bug Bounty** | Ongoing | Public surface |

---

## Security Testing

### Running Security Tests

```bash
# All security tests
python -m pytest tests/test_security.py -v

# Specific categories
python -m pytest tests/test_security.py -v -k "injection"
python -m pytest tests/test_security.py -v -k "authentication"
python -m pytest tests/test_security.py -v -k "authorization"
```

### Security Test Coverage

| Category | Tests | Description |
|----------|-------|-------------|
| **Authentication** | 15 | JWT, API keys, OAuth, MFA |
| **Authorization** | 12 | RBAC, ABAC, tenant isolation |
| **Input Validation** | 20 | XSS, injection, sanitization |
| **Cryptography** | 8 | Encryption, hashing, signatures |
| **Rate Limiting** | 6 | Per-IP, per-user, per-endpoint |
| **Prompt Injection** | 10 | LLM-specific attacks |
| **Data Protection** | 8 | PII handling, data isolation |
| **Audit Logging** | 5 | Event capture, integrity |

---

## Incident Response

### Response Plan

```yaml
# config/incident-response.yaml
incident_response:
  severity_levels:
    critical:
      response_time: 15_minutes
      escalation: [security_team, cto, legal]
      communication: immediate
      
    high:
      response_time: 1_hour
      escalation: [security_team, engineering_lead]
      communication: within_4_hours
      
    medium:
      response_time: 4_hours
      escalation: [security_team]
      communication: next_business_day
      
    low:
      response_time: 24_hours
      escalation: [security_team]
      communication: weekly_report

  contacts:
    security_team: security@agentic-brain.dev
    on_call: "+61-XXX-XXX-XXX"
    
  runbooks:
    - data_breach
    - ddos_attack
    - credential_compromise
    - ransomware
```

### Breach Notification

```python
from agentic_brain.security import BreachNotifier

notifier = BreachNotifier(
    regulators={
        "gdpr": {"authority": "oaic.gov.au", "deadline_hours": 72},
        "hipaa": {"authority": "hhs.gov", "deadline_hours": 60},
        "apra": {"authority": "apra.gov.au", "deadline_hours": 72}
    }
)

# Notify affected parties
await notifier.notify_breach(
    breach_type="unauthorized_access",
    affected_records=1500,
    data_types=["email", "name"],
    discovery_time=datetime.now()
)
```

---

## Production Hardening

### Pre-Deployment Checklist

```markdown
## Security Checklist

### Authentication
- [ ] JWT secrets are strong (256+ bits)
- [ ] API keys rotated from development
- [ ] MFA enabled for admin accounts
- [ ] OAuth configured with PKCE

### Encryption
- [ ] TLS 1.3 enforced
- [ ] Certificates valid and pinned
- [ ] Encryption at rest enabled
- [ ] Key rotation configured

### Network
- [ ] CORS restricted to production origins
- [ ] Rate limiting configured
- [ ] Security headers enabled
- [ ] Neo4j not publicly accessible

### Secrets
- [ ] No secrets in code or config files
- [ ] Secrets manager configured
- [ ] Service accounts use minimal permissions
- [ ] .env files excluded from deployment

### Monitoring
- [ ] Audit logging enabled
- [ ] SIEM integration configured
- [ ] Alerting rules active
- [ ] Log retention configured

### Compliance
- [ ] Data classification applied
- [ ] PII detection enabled
- [ ] Retention policies configured
- [ ] Compliance mode activated
```

### Hardening Commands

```bash
# Generate secure secrets
ab security generate-secrets --output .env.production

# Validate configuration
ab security validate-config

# Run security audit
ab security audit --output audit-report.pdf

# Check compliance posture
ab compliance check --framework soc2
```

---

## Vulnerability Reporting

**DO NOT** report security vulnerabilities via public GitHub issues.

**Email:** security@agentic-brain.dev

**PGP Key:** Available at https://agentic-brain.dev/.well-known/security.txt

### Response Timeline

| Severity | Response | Fix | Disclosure |
|----------|----------|-----|------------|
| Critical | 4 hours | 24-48 hours | 7 days |
| High | 24 hours | 7 days | 30 days |
| Medium | 48 hours | 30 days | 90 days |
| Low | 7 days | Next release | 90 days |

### Bug Bounty

We offer bounties for responsibly disclosed vulnerabilities:

| Severity | Bounty (AUD) |
|----------|--------------|
| Critical | $5,000 - $15,000 |
| High | $1,000 - $5,000 |
| Medium | $250 - $1,000 |
| Low | $50 - $250 |

---

## See Also

- [COMPLIANCE.md](./COMPLIANCE.md) — Regulatory compliance
- [AUTHENTICATION.md](./AUTHENTICATION.md) — Auth setup guide
- [DEPLOYMENT.md](./DEPLOYMENT.md) — Production deployment
- [ENTERPRISE.md](./ENTERPRISE.md) — Enterprise features

---

<div align="center">

**Security is not a feature. It's a foundation.**

*Questions? Contact: security@agentic-brain.dev*

</div>

---

**Last Updated**: 2026-03-22
