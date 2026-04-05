# Security Module Documentation

## Overview

The security module provides a **four-tier role-based access control (RBAC)** system protecting the Agentic Brain from unauthorized access and dangerous operations. This document outlines the security architecture, authentication methods, authorization model, and configuration guidelines.

### Key Principles

- **Principle of Least Privilege**: Users receive only the minimum permissions needed for their role
- **Defense in Depth**: Multiple security layers (authentication → authorization → operation guards)
- **Explicit Over Implicit**: Permissions are explicitly granted, not implied
- **API-First for Non-Admins**: Customer/user roles access external APIs only, not local machine resources

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              Request Entry Point                        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Authentication Layer (auth.py)                          │
│ - API key validation                                    │
│ - Session creation/validation                          │
│ - Admin key verification                               │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Role & Permissions (roles.py)                          │
│ - Role assignment                                      │
│ - Permission lookup (ROLE_PERMISSIONS dict)            │
│ - Dangerous command patterns                           │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Security Guards (guards.py)                            │
│ - YOLO command validation                              │
│ - File access checks                                   │
│ - Operation decorators                                 │
│ - Security event logging                              │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Operation Execution Layers                              │
│ - Shell execution (guarded)                            │
│ - File operations (path validation)                    │
│ - LLM access (chat_only vs full)                       │
│ - API access (api_access.py)                           │
│ - Tool execution (tool_guard.py)                       │
│ - Code execution (llm_guard.py, prompt_filter.py)     │
└─────────────────────────────────────────────────────────┘
```

### Module Components

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `roles.py` | Role definitions & permissions | `SecurityRole`, `RolePermissions`, `ROLE_PERMISSIONS` |
| `auth.py` | Authentication & sessions | `Session`, API key validation |
| `guards.py` | Permission enforcement | `SecurityGuard`, decorators, event logging |
| `api_access.py` | API-based access control | `APIScope`, `AuthType`, scoped API connections |
| `tool_guard.py` | Tool execution restrictions | Tool whitelisting |
| `llm_guard.py` | LLM prompt safety | Prompt filtering |
| `prompt_filter.py` | Prompt injection prevention | Filter rules |
| `platform_security.py` | Platform-specific access levels | Platform profiles |
| `base_agent.py` | Base agent class with security | Secure agent initialization |

---

## Authentication Methods

### 1. API Key Authentication

**File**: `auth.py`

```python
from agentic_brain.security import create_session, validate_session

# Create session with API key
session = create_session(api_key="user-api-key-123", user_id="user@example.com")

# Use session for subsequent operations
if validate_session(session):
    # Proceed with operation
    pass
```

**Features**:
- API keys are validated and mapped to roles
- Sessions are time-bound (configurable expiry)
- Support for multiple concurrent sessions per user

**Environment Variables**:
```bash
AGENTIC_BRAIN_ADMIN_KEY=<admin-key>      # Admin authentication key
AGENTIC_BRAIN_ADMIN_USER=<admin-username> # Admin user identifier
```

### 2. Admin Authentication

Administrators authenticate via:
- **Admin Key**: Secret key stored in `AGENTIC_BRAIN_ADMIN_KEY` environment variable
- **Default Admin User**: Specified in `AGENTIC_BRAIN_ADMIN_USER` (default: "admin")

```python
from agentic_brain.security import authenticate_admin

# Admin login
admin_session = authenticate_admin(admin_key=os.getenv("AGENTIC_BRAIN_ADMIN_KEY"))
if admin_session:
    print(f"Admin authenticated as role: {admin_session.role}")
```

### 3. Session Management

Sessions are created with:
- **session_id**: Unique identifier (generated)
- **role**: Assigned `SecurityRole` from authentication
- **user_id**: Optional user identifier
- **created_at**: Session creation timestamp

```python
@dataclass(slots=True)
class Session:
    session_id: str
    role: SecurityRole
    user_id: str | None
    created_at: datetime
```

**Session Validation**:
- Tokens are HMAC-signed to prevent tampering
- Session expiry is enforced (default: 24 hours)
- Invalid sessions are rejected

---

## Authorization Model

### Role Hierarchy

The system uses a **four-tier role hierarchy** with increasing privileges:

```
                         ┌──────────────┐
                         │ FULL_ADMIN   │
                         │ (Tier 1)     │
                         │              │
                         │ • Owner      │
                         │ • Full access│
                         │ • No limits  │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ SAFE_ADMIN   │
                         │ (Tier 2)     │
                         │              │
                         │ • Developers │
                         │ • With guards│
                         │ • Confirmed  │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ USER         │
                         │ (Tier 3)     │
                         │              │
                         │ • Employees  │
                         │ • API only   │
                         │ • Rate limit │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ GUEST        │
                         │ (Tier 4)     │
                         │              │
                         │ • Public     │
                         │ • Read-only  │
                         │ • Strict limit
                         └──────────────┘
```

### Role Definitions

#### FULL_ADMIN (Tier 1)

**Purpose**: Unrestricted system access for owner/root user only

**Permissions**:
- ✅ YOLO execution (no confirmation needed)
- ✅ Full file system access (read & write)
- ✅ Shell command execution (no restrictions)
- ✅ Secret/config access
- ✅ Full LLM access
- ✅ No rate limiting
- ✅ Full API access (all scopes)
- ✅ Tool access (all tools, no whitelist)

**Use Case**: Initial setup, critical maintenance, security operations

#### SAFE_ADMIN (Tier 2)

**Purpose**: Development and trusted administrator tasks with safety guardrails

**Permissions**:
- ✅ YOLO execution (requires confirmation for dangerous commands)
- ✅ File system access (development paths only)
- ✅ Shell commands (blocked patterns filtered)
- ❌ Secret/config access
- ✅ Full LLM access
- ⚠️ High rate limit (1000 req/min)
- ✅ API access (no admin-level)
- ✅ Tool access (all tools)

**Blocked Commands**:
- Destructive file ops: `rm -rf /`, `shred`, `mkfs`
- System modification: `sudo`, `chmod 777`, `chown`, `mount`
- Process termination: `kill -9 -1`, `pkill -9`
- Database destruction: `DROP DATABASE`, `DROP TABLE CASCADE`
- Force git operations: `git push --force`, `git reset --hard`
- Fork bombs, environment tampering

**Use Case**: Development, testing, code deployment

#### USER (Tier 3)

**Purpose**: Customer/employee API access without machine resources

**Permissions**:
- ❌ YOLO execution
- ❌ File system access
- ❌ Shell commands
- ❌ Secret/config access
- ✅ Chat-only LLM access
- ⚠️ Moderate rate limit (60 req/min)
- ✅ API access (user-level endpoints only)
- ✅ Tool access (whitelisted tools only)

**Allowed Tools**: `view_orders`, `create_order`, `update_profile`, `view_account`, `track_shipment`, `submit_review`, `manage_wishlist`

**Allowed API Scopes**: `read`, `write` (no delete, no admin)

**Use Case**: End users, customer support, internal employees

#### GUEST (Tier 4)

**Purpose**: Public/anonymous access with minimal permissions

**Permissions**:
- ❌ YOLO execution
- ❌ File system access
- ❌ Shell commands
- ❌ Secret/config access
- ✅ Chat-only LLM access
- ⚠️ Strict rate limit (10 req/min)
- ✅ API access (public endpoints only)
- ✅ Tool access (very limited whitelist)
- ❌ Web search (blocked - expensive)

**Allowed Tools**: `help`, `faq`, `documentation`, `product_search`, `product_view`, `cart_view`, `cart_add`, `cart_remove`, `checkout`, `customer_support`

**Allowed API Scopes**: `read` only (no write, no delete)

**Use Case**: Anonymous visitors, public FAQ browsing, product browsing

---

## Permission Matrix

| Operation | FULL_ADMIN | SAFE_ADMIN | USER | GUEST |
|-----------|-----------|-----------|------|-------|
| **YOLO Execution** | ✅ No confirm | ⚠️ Confirm | ❌ | ❌ |
| **Shell Commands** | ✅ All | ✅ Filtered | ❌ | ❌ |
| **File Write** | ✅ Anywhere | ✅ Dev paths | ❌ | ❌ |
| **File Read** | ✅ All files | ✅ All files | ❌ | ❌ |
| **Secrets Access** | ✅ | ❌ | ❌ | ❌ |
| **Config Modify** | ✅ | ✅ | ❌ | ❌ |
| **LLM Access** | ✅ Full | ✅ Full | ✅ Chat | ✅ Chat |
| **Web Search** | ✅ | ✅ | ❌ | ❌ |
| **Guest APIs** | ✅ | ✅ | ✅ | ✅ |
| **Auth APIs** | ✅ | ✅ | ✅ | ❌ |
| **Admin APIs** | ✅ | ❌ | ❌ | ❌ |
| **Rate Limit** | ∞ | 1000/min | 60/min | 10/min |
| **Tool Access** | ✅ All | ✅ All | ✅ Whitelist | ✅ Whitelist |
| **Database Access** | ✅ | ✅ | ❌ | ❌ |
| **System Config** | ✅ | ✅ | ❌ | ❌ |

---

## Configuration Guide

### Environment Variables

```bash
# Authentication
export AGENTIC_BRAIN_ADMIN_KEY="<secure-admin-key>"
export AGENTIC_BRAIN_ADMIN_USER="administrator"

# Session management
export AGENTIC_BRAIN_SESSION_TTL_HOURS=24

# Rate limiting
export AGENTIC_BRAIN_RATE_LIMIT_STRICT=10      # Guest limit
export AGENTIC_BRAIN_RATE_LIMIT_MODERATE=60    # User limit
export AGENTIC_BRAIN_RATE_LIMIT_HIGH=1000      # Safe admin limit
```

### Programmatic Configuration

#### Setting Up a Security Guard

```python
from agentic_brain.security import SecurityGuard, SecurityRole

# Create a security guard for a specific role
guard = SecurityGuard(role=SecurityRole.USER)

# Check command permissions
is_allowed, reason = guard.is_command_allowed("ls -la /data")
if not is_allowed:
    print(f"Command blocked: {reason}")

# Check file access
is_allowed, reason = guard.is_path_writable("/home/user/output")
if is_allowed:
    # Safe to write
    pass
```

#### Creating Sessions

```python
from agentic_brain.security import create_session, SecurityRole

# Create session for USER role
session = create_session(
    role=SecurityRole.USER,
    user_id="user@example.com",
    api_key="user-key-123"
)

# Use session in operations
with session:
    # Protected operations here
    pass
```

#### Using Decorators

```python
from agentic_brain.security import require_role, SecurityRole

@require_role(SecurityRole.SAFE_ADMIN)
def deploy_to_production():
    """Only SAFE_ADMIN and FULL_ADMIN can call this."""
    print("Deploying...")

@require_role(SecurityRole.USER)
def get_user_orders(user_id):
    """USER role and above can call this."""
    return database.get_orders(user_id)
```

### API Access Configuration

```python
from agentic_brain.security import APIScope, AuthType
from agentic_brain.security.api_access import APIConnection

# Configure API connection for authenticated user
api_config = APIConnection(
    endpoint="https://api.example.com",
    auth_type=AuthType.BEARER,
    token="user-bearer-token",
    scopes=[APIScope.READ, APIScope.WRITE],
    rate_limit=60
)

# Execute API call (respects role permissions)
response = api_config.request("GET", "/api/user/orders")
```

---

## Security Events & Logging

All security-relevant operations are logged via `SecurityEvent`:

```python
@dataclass(slots=True)
class SecurityEvent:
    """Record of a security-relevant action."""
    timestamp: datetime
    role: SecurityRole
    action: str              # "command_executed", "file_read", "file_write"
    resource: str | None     # Path, command, or resource identifier
    allowed: bool            # Whether action was permitted
    reason: str | None       # Reason if blocked
```

**Enable Security Logging**:

```python
import logging

security_logger = logging.getLogger("agentic_brain.security")
security_logger.setLevel(logging.INFO)

# Add handler to persist security events
handler = logging.FileHandler("security_events.log")
security_logger.addHandler(handler)
```

---

## Dangerous Command Patterns

The system blocks commands matching these patterns for non-FULL_ADMIN roles:

### Destructive File Operations
- `rm -rf /` — recursive delete from root
- `shred` — secure file deletion
- `mkfs` — filesystem destruction
- `dd of=/dev/` — disk imaging

### System Modification
- `sudo` — privilege escalation
- `chmod 777` — world-writable permissions
- `chown` — ownership changes
- `mount`/`umount` — filesystem mounting

### Process Termination
- `kill -9 -1` — kill all processes
- `pkill -9` — mass process killing
- `systemctl stop` — service termination

### Database Operations
- `DROP DATABASE` — database destruction
- `DROP TABLE CASCADE` — table deletion
- `TRUNCATE TABLE` — data destruction

### Git Operations
- `git push --force` — history rewriting
- `git reset --hard` — local changes destruction
- `git clean -fd` — file deletion

### Resource Exhaustion
- Fork bombs: `:(){ :|: & };:`
- Infinite loops: `while true; do ...; done`

---

## Best Practices

### 1. Always Validate User Input

```python
from agentic_brain.security import SecurityGuard

guard = SecurityGuard(role=user_role)
command = user_input.strip()

is_allowed, reason = guard.is_command_allowed(command)
if not is_allowed:
    raise PermissionError(f"Command not allowed: {reason}")
```

### 2. Use Least Privilege by Default

Always assign the lowest role that can accomplish the task:
- Public users → `GUEST`
- Customers/employees → `USER`
- Developers → `SAFE_ADMIN`
- Owner only → `FULL_ADMIN`

### 3. Confirm Dangerous Operations

```python
from agentic_brain.security import SecurityGuard, SecurityRole

if guard.role == SecurityRole.SAFE_ADMIN:
    dangerous, pattern = is_dangerous_command(user_command)
    if dangerous:
        # Require confirmation before executing
        confirmed = confirm_with_user(f"Execute {user_command}?")
        if not confirmed:
            raise PermissionError("Operation cancelled by user")
```

### 4. Rotate API Keys Regularly

Implement key rotation every 90 days:
- Generate new key
- Transition users to new key
- Revoke old key
- Log all key changes

### 5. Monitor Security Events

```python
# Track failed access attempts
failed_attempts = []

for event in security_events:
    if not event.allowed and event.action == "command_executed":
        failed_attempts.append(event)
        if len(failed_attempts) > 5 and event.timestamp < now - timedelta(minutes=5):
            # Alert: potential attack
            send_security_alert(event)
```

### 6. Use API Scopes for Fine-Grained Control

```python
# Good: Limit user API to read-only
user_api = APIConnection(
    scopes=[APIScope.READ],
    allowed_api_scopes=frozenset({"read"})
)

# Bad: Giving write access to read-only operations
# user_api = APIConnection(scopes=[APIScope.READ, APIScope.WRITE])
```

---

## Common Scenarios

### Scenario 1: Onboarding a New Employee

```python
from agentic_brain.security import create_session, SecurityRole

# Create limited USER session for new employee
session = create_session(
    role=SecurityRole.USER,
    user_id="employee@company.com",
    api_key="generated-key-abc123"
)

# Employee can:
# - Access customer/employee APIs
# - View their own data
# - Submit support tickets
# Employee cannot:
# - Execute shell commands
# - Access filesystem
# - Modify system configuration
```

### Scenario 2: Granting Developer Access

```python
# Grant SAFE_ADMIN for development work
dev_session = create_session(
    role=SecurityRole.SAFE_ADMIN,
    user_id="developer@company.com",
    api_key="generated-key-def456"
)

# Developer can:
# - Execute commands with confirmation for dangerous ones
# - Write to /data, /logs, /cache, /agentic-brain, /web, /backend
# - Access full LLM
# - Test deployments
# Developer cannot:
# - Access production secrets
# - Execute unrestricted commands
# - Write outside designated paths
```

### Scenario 3: Public API Access

```python
# Create GUEST session for public chatbot
guest_session = create_session(
    role=SecurityRole.GUEST,
    user_id=None  # Anonymous
)

# Guest can:
# - Browse public product catalog
# - View FAQ and documentation
# - Add items to cart
# Guest cannot:
# - View other users' orders
# - Access admin endpoints
# - Execute any system commands
# - Perform web searches
```

### Scenario 4: Emergency Admin Access

```python
# Use admin key for emergency maintenance
from agentic_brain.security import authenticate_admin
import os

admin_session = authenticate_admin(
    admin_key=os.getenv("AGENTIC_BRAIN_ADMIN_KEY")
)

if admin_session and admin_session.role == SecurityRole.FULL_ADMIN:
    # Full unrestricted access for critical operations
    perform_emergency_maintenance()
```

---

## Troubleshooting

### "Command blocked by security policy"

**Cause**: The command matches a dangerous pattern restricted to your role.

**Solution**:
1. Check your role: `print(session.role)`
2. If SAFE_ADMIN, request confirmation for the operation
3. If USER/GUEST, escalate to SAFE_ADMIN or FULL_ADMIN

### "Path not in allowed write locations"

**Cause**: Attempting to write outside permitted directories.

**Solution**:
- USER role: Write to `~/brain/output`, `~/brain/test-results`, `~/brain/session-artifacts`
- SAFE_ADMIN role: Write to development paths in `~/brain`
- FULL_ADMIN role: Write anywhere

### "YOLO execution not permitted for this role"

**Cause**: Role doesn't have YOLO permissions.

**Solution**:
- USER/GUEST roles: No shell access. Use API calls instead.
- SAFE_ADMIN: Use with confirmation for dangerous commands
- FULL_ADMIN: Unrestricted access

### Session Expired

**Cause**: Session token exceeded TTL (default 24 hours).

**Solution**: Re-authenticate using your API key to create a new session.

---

## Additional Resources

- **API Access Control**: See `api_access.py` for external API integration
- **Tool Guards**: See `tool_guard.py` for tool execution restrictions
- **LLM Guards**: See `llm_guard.py` for prompt safety
- **Platform Security**: See `platform_security.py` for platform-specific profiles

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-Q1 | Initial four-tier RBAC model |
| 1.1 | 2024-Q2 | Added API scope granularity |
| 1.2 | 2024-Q3 | Added tool whitelisting |
| 1.3 | 2025-Q1 | Added platform security profiles |
| 2.0 | 2026-Q1 | Comprehensive documentation |

---

**Last Updated**: 2026  
**Maintainers**: Agentic Brain Security Team  
**License**: Apache 2.0
