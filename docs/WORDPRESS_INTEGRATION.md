# WordPress Integration

## Overview

WordPress and WooCommerce integrations must follow the canonical four-tier security model:

1. **FULL_ADMIN** - unrestricted owner access
2. **SAFE_ADMIN** - trusted developer access with guardrails
3. **USER** - authenticated customer API access
4. **GUEST** - anonymous help-only access

This keeps storefront support useful without exposing machine access or privileged business endpoints.

## Role Mapping

| WordPress audience | Canonical role | Allowed behavior |
| --- | --- | --- |
| Joseph / platform owner | `FULL_ADMIN` | Unrestricted platform control |
| Developer or trusted maintainer | `SAFE_ADMIN` | Integration work, diagnostics, and maintenance |
| Logged-in customer | `USER` | Approved WordPress/WooCommerce API calls |
| Anonymous visitor | `GUEST` | Help docs, setup guides, manuals, product information |

## Customer vs Visitor Behavior

### WordPress Customer (USER mode)

USER mode is for authenticated customers.

Examples:

- **"Where is my order?"** → Calls WooCommerce API
- **"Update my address"** → Calls WordPress REST API
- **"Show my downloads"** → Calls WooCommerce downloads endpoint

Requirements:

- customer identity must be verified
- requests must be scoped to the current customer
- every API call should be audited
- no shell, code execution, or file system access is allowed

### Website Visitor (GUEST mode)

GUEST mode is for anonymous visitors.

Examples:

- **"How do I install this?"** → Shows setup guide
- **"What does this product do?"** → Shows product FAQ
- **"I need help"** → Shows help documentation

Requirements:

- respond from public help content only
- do not call business APIs
- do not expose account or order data
- do not allow code execution, file access, or machine access

## What GUEST Can Access

GUEST users can only access:

- FAQ content
- help documentation
- setup guides
- product information
- user manuals
- basic troubleshooting

## What GUEST Cannot Access

GUEST users cannot:

- execute any code
- access any APIs
- modify any data
- access machine resources

## Recommended Integration Pattern

### Public website widget

Resolve anonymous traffic to `GUEST` and serve:

- product FAQ
- setup content
- troubleshooting guides
- public documentation

### Customer self-service widget

Resolve authenticated traffic to `USER` and allow:

- order status lookups
- address updates
- downloads access
- account-specific support workflows

### Admin and maintenance tooling

Resolve internal tooling to `SAFE_ADMIN` or `FULL_ADMIN` depending on risk:

- content sync maintenance
- webhook troubleshooting
- plugin diagnostics
- deployment and infrastructure tasks

## Security Boundaries

| Capability | FULL_ADMIN | SAFE_ADMIN | USER | GUEST |
| --- | --- | --- | --- | --- |
| Shell commands | ✅ | ✅ confirm | ❌ | ❌ |
| File system | ✅ | ✅ | ❌ | ❌ |
| WordPress/WooCommerce APIs | ✅ | ✅ | ✅ approved only | ❌ |
| LLM chat | ✅ | ✅ | ✅ | ⚠️ limited |
| Public help content | ✅ | ✅ | ✅ | ✅ |

## Implementation Guidance

- map WordPress auth state to one canonical role before handling the request
- never let anonymous traffic resolve to API-capable behavior
- keep USER flows strictly API-based
- keep GUEST flows strictly content-based
- reserve YOLO and machine access for SAFE_ADMIN and FULL_ADMIN only
- reserve unrestricted ownership actions for FULL_ADMIN only

## Related Documentation

- [Security roles overview](./SECURITY_ROLES.md)
- [API access control](./API_ACCESS_CONTROL.md)
- [Security implementation details](./SECURITY_IMPLEMENTATION.md)
