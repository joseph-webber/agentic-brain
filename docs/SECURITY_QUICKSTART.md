# Security Quick Start

## Overview

Use this guide to choose the correct role quickly and apply the canonical four-tier model:

1. **FULL_ADMIN** - unrestricted owner access
2. **SAFE_ADMIN** - development with guardrails
3. **USER** - API-only customer access
4. **GUEST** - help-only anonymous access

## Choose the Right Role

### FULL_ADMIN

Use for platform owner/administrator-level ownership tasks:

- infrastructure work
- secret rotation
- emergency recovery
- unrestricted debugging

### SAFE_ADMIN

Use for trusted development tasks:

- editing source files
- running tests
- integration maintenance
- WordPress and WooCommerce adapter work

### USER

Use for authenticated customer workflows:

- order lookup
- address updates
- downloads lookup
- account support

### GUEST

Use for public website or anonymous help:

- setup questions
- product information
- FAQs
- basic troubleshooting

## Expected Access by Role

| Role | Shell | File System | APIs | LLM Chat | Rate Limit |
| --- | --- | --- | --- | --- | --- |
| FULL_ADMIN | ✅ | ✅ | ✅ | ✅ | None |
| SAFE_ADMIN | ✅ confirm | ✅ | ✅ | ✅ | 1000/min |
| USER | ❌ | ❌ | ✅ | ✅ | 60/min |
| GUEST | ❌ | ❌ | ❌ | ⚠️ Limited | 10/min |

## Quick Configuration Patterns

### Local owner session

```bash
export AGENTIC_BRAIN_ADMIN_MODE=true
```

Treat this as **FULL_ADMIN**.

### Trusted development session

Use your application or auth layer to resolve trusted developers to **SAFE_ADMIN**.

If a legacy path still exposes `developer`, map it to `safe_admin` in your configuration and docs.

### Authenticated customer session

Resolve logged-in customers to **USER**.

Important: USER is API-only. Do not grant shell, code execution, or file access.

### Anonymous public session

Resolve all unauthenticated visitors to **GUEST**.

Important: GUEST is help-only. Do not call business APIs from guest mode.

## WordPress Examples

### USER example

**Question:** "Where is my order?"

**Expected behavior:** call WooCommerce API with customer scope and return the result.

### GUEST example

**Question:** "How do I install this?"

**Expected behavior:** return the setup guide or relevant help documentation.

## Security Checks

Before shipping, confirm the following:

- FULL_ADMIN has unrestricted access
- SAFE_ADMIN can work productively but sees confirmations for risky actions
- USER cannot access shell, files, or machine resources
- USER can call only approved APIs
- GUEST cannot access APIs or modify data
- public help content is still available to GUEST

## Migration Reminder

If older code or docs still mention:

- `ADMIN` → treat as `FULL_ADMIN`
- `DEVELOPER` → treat as `SAFE_ADMIN`

Use the canonical names in all new setup guides and public documentation.

## Related Documentation

- [Security roles overview](./SECURITY_ROLES.md)
- [Security implementation details](./SECURITY_IMPLEMENTATION.md)
- [API access control](./API_ACCESS_CONTROL.md)
