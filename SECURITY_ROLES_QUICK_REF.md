# Security Roles Quick Reference

## 4-Tier Security Model

Agentic Brain implements a 4-tier security model for all autonomous agents and chatbots.

### Tier 1: FULL_ADMIN (Platform Owner/Administrator)

**Complete unrestricted access**

- ✅ Full YOLO mode - execute ANY command
- ✅ Direct machine access (shell, files, database)
- ✅ Can do everything GitHub Copilot/Claude can do and MORE
- ✅ No restrictions whatsoever
- ✅ No confirmations required
- ✅ Infinite rate limit

**Use cases:**
- Platform owner/administrator personal development
- System administration
- Emergency fixes
- Full control over all systems

### Tier 2: SAFE_ADMIN (Developers/Trusted admins)

**Almost full access WITH guardrails**

- ✅ YOLO mode with safety confirmations for dangerous ops
- ✅ Can code, execute, modify files
- ⚠️ Confirmations required for: `rm -rf`, `sudo`, system modifications
- ✅ Full API access (read, write, delete)
- ✅ Rate limit: 1000 requests/minute
- ❌ No access to secrets
- ❌ No admin scope on APIs

**Use cases:**
- Trusted developers
- DevOps engineers
- System maintainers
- Code reviewers

**Guardrails:**
- Dangerous commands require confirmation
- Limited write access (development paths only)
- Cannot access system secrets
- Cannot manage users

### Tier 3: USER (API-only access)

**Customers/Employees - NO machine access**

- ❌ NO direct machine access
- ❌ NO shell commands
- ❌ NO file system access
- ✅ ONLY API access (WordPress REST, WooCommerce REST, etc.)
- ✅ Permissions controlled by external API's role system
- ✅ Can read FAQ, docs, manuals
- ✅ Rate limit: 60 requests/minute

**Use cases:**
- Customer chatbots
- Employee assistants
- Authenticated users
- Service integrations

**What they CAN do:**
- Access WordPress/WooCommerce REST APIs
- Create/update posts, products, orders (via API)
- Chat with AI
- Access documentation

**What they CANNOT do:**
- Execute shell commands
- Access files directly
- Modify system configuration
- See or modify code

### Tier 4: GUEST (Very restricted)

**Anonymous visitors - Read-only**

- ❌ NO machine access
- ❌ NO API write access
- ❌ NO shell commands
- ❌ NO file system access
- ✅ Read-only access to:
  - FAQ content
  - Help documentation
  - Setup guides
  - Product information
  - User manuals
- ✅ Heavily rate limited: 10 requests/minute

**Use cases:**
- Anonymous website visitors
- Public demos
- Documentation browsing
- Pre-signup users

## Permission Matrix

| Permission | FULL_ADMIN | SAFE_ADMIN | USER | GUEST |
|------------|-----------|-----------|------|-------|
| YOLO Mode | ✅ (no confirm) | ✅ (with confirm) | ❌ | ❌ |
| Shell Access | ✅ | ✅ | ❌ | ❌ |
| File System | ✅ (all) | ✅ (limited) | ❌ | ❌ |
| API Access | ✅ (all scopes) | ✅ (r/w/d) | ✅ (r/w only) | ❌ |
| Read FAQ/Docs | ✅ | ✅ | ✅ | ✅ |
| Modify Config | ✅ | ✅ (project) | ❌ | ❌ |
| Access Secrets | ✅ | ❌ | ❌ | ❌ |
| Manage Users | ✅ | ❌ | ❌ | ❌ |
| Rate Limit | ∞ | 1000/min | 60/min | 10/min |

## API Scopes

### Read Scope
- GET requests
- View data
- Search/query
- Export (where permitted)

### Write Scope
- POST requests
- Create new resources
- Update existing resources
- PATCH operations

### Delete Scope
- DELETE requests
- Remove resources
- Soft delete operations

### Admin Scope
- User management
- System configuration
- Security settings
- Full API access

## Implementation

### Python

```python
from agentic_brain.security.roles import SecurityRole, get_permissions

# Get permissions for a role
perms = get_permissions(SecurityRole.USER)

# Check if command is allowed
allowed, reason = perms.is_command_allowed("rm -rf /")
if not allowed:
    print(f"Blocked: {reason}")

# Check if path is writable
allowed, reason = perms.is_path_writable("/etc/passwd")
if not allowed:
    print(f"Blocked: {reason}")
```

### Security Guard

```python
from agentic_brain.security.guards import SecurityGuard, require_role

# Create a guard
guard = SecurityGuard(SecurityRole.SAFE_ADMIN)

# Check permissions
if guard.can_yolo():
    # Execute command with guardrails
    guard.execute_with_confirmation("sudo apt-get update")

# Require specific role
@require_role(SecurityRole.SAFE_ADMIN)
def deploy_to_production():
    # Only SAFE_ADMIN or FULL_ADMIN can call this
    pass
```

## Key Principles

1. **Least Privilege**: Start with the most restricted role and grant only what's needed
2. **API-First for Customers**: Customer chatbots should NEVER have machine access
3. **Explicit Confirmations**: SAFE_ADMIN requires confirmation for dangerous operations
4. **Rate Limiting**: All roles except FULL_ADMIN are rate limited
5. **No Secrets Leakage**: Only FULL_ADMIN can access system secrets
6. **Audit Trail**: All actions are logged with role information

## Upgrading from 3-Tier Model

Old Role → New Role:
- `ADMIN` → `FULL_ADMIN`
- `DEVELOPER` → `SAFE_ADMIN`
- `USER` → `USER` (unchanged)
- `GUEST` → `GUEST` (unchanged)

## Security Considerations

### For FULL_ADMIN
- Use only for platform owner/administrator access
- Never expose admin keys in code
- Store admin key in environment variable: `AGENTIC_BRAIN_ADMIN_KEY`

### For SAFE_ADMIN
- Trusted developers only
- Review dangerous operations before confirming
- Monitor for unusual activity

### For USER
- Perfect for customer chatbots
- Configure API permissions carefully
- Rate limit aggressively
- Monitor API usage

### For GUEST
- Assume hostile actors
- Never trust input
- Rate limit very strictly
- No sensitive data exposure

## Migration Checklist

- [x] Update `src/agentic_brain/security/roles.py` with 4-tier model
- [x] Rename `ADMIN` → `FULL_ADMIN`
- [x] Rename `DEVELOPER` → `SAFE_ADMIN`
- [x] Update all code references
- [x] Update all test files
- [ ] Update BrainChat Swift app
- [ ] Update API documentation
- [ ] Update user guides
- [ ] Run test suite
- [ ] Update deployment configs

---

**Last Updated**: 2026-04-02  
**Status**: Implementation Complete  
**Next**: BrainChat Swift integration
