# API Access Control Guide

## Overview

Agentic Brain's API access rules are defined by the canonical four-tier model:

1. **FULL_ADMIN** - unrestricted
2. **SAFE_ADMIN** - guarded developer access
3. **USER** - API-only customer access
4. **GUEST** - help-only anonymous access

**Key principle:** only `FULL_ADMIN`, `SAFE_ADMIN`, and `USER` may access APIs. `GUEST` may not call business APIs at all.

## Role Rules

| Role | API Access | Intended use |
| --- | --- | --- |
| `FULL_ADMIN` | Unrestricted | Owner and infrastructure operations |
| `SAFE_ADMIN` | Allowed | Developer tooling, maintenance, and integration work |
| `USER` | Approved endpoints only | Customer self-service |
| `GUEST` | None | Public help, docs, manuals, troubleshooting |

## Why USER Is API-Only

USER is the safe customer role.

A USER session can:

- query approved WordPress or WooCommerce endpoints
- update account data through approved REST APIs
- retrieve business data that belongs to that user

A USER session cannot:

- run shell commands
- execute code
- access the server file system
- bypass endpoint allow-lists

## Why GUEST Has No API Access

GUEST is intentionally limited to public help content.

This prevents anonymous traffic from reaching:

- account data
- order data
- downloads data
- mutable business endpoints
- infrastructure or machine resources

For public chat experiences, serve curated help content instead of live business API calls.

## Recommended Flow

```text
Visitor or customer → Chat layer → Role resolution → Access controller → Allowed content or approved API
```

Role resolution should be:

- anonymous visitor → `GUEST`
- authenticated customer → `USER`
- trusted developer → `SAFE_ADMIN`
- platform owner/administrator → `FULL_ADMIN`

## USER Examples

### WordPress Customer (USER mode)

- **"Where is my order?"** → Calls WooCommerce API
- **"Update my address"** → Calls WordPress REST API
- **"Show my downloads"** → Calls WooCommerce downloads endpoint

These calls must remain customer-scoped and audited.

## GUEST Examples

### Website Visitor (GUEST mode)

- **"How do I install this?"** → Shows setup guide
- **"What does this product do?"** → Shows product FAQ
- **"I need help"** → Shows help documentation

These flows should resolve from documentation, manuals, knowledge bases, or product content — not from protected APIs.

## Controller Requirements

An API access controller should:

1. validate the resolved role
2. allow only approved roles to call APIs
3. enforce endpoint and method allow-lists
4. enforce customer or tenant scope for USER traffic
5. audit every API request
6. reject all GUEST API attempts

## Example Policy Matrix

| Operation | FULL_ADMIN | SAFE_ADMIN | USER | GUEST |
| --- | --- | --- | --- | --- |
| Call WordPress content API | ✅ | ✅ | ✅ if approved | ❌ |
| Call WooCommerce customer orders API | ✅ | ✅ | ✅ scoped to self | ❌ |
| Update customer profile via REST API | ✅ | ✅ | ✅ scoped to self | ❌ |
| Call admin-only commerce endpoint | ✅ | ⚠️ if authorized | ❌ | ❌ |
| Read FAQ or setup guide | ✅ | ✅ | ✅ | ✅ |

## Security Best Practices

1. keep `USER` endpoint lists minimal
2. require customer scope for all personal data
3. deny all API traffic from `GUEST`
4. separate public help content from authenticated business integrations
5. audit all allow and deny outcomes
6. use HTTPS only
7. rotate integration credentials regularly

## WordPress and WooCommerce Notes

- WordPress content browsing for anonymous visitors should be served as public documentation content, not privileged API proxy traffic.
- WooCommerce customer flows must resolve to `USER` and include customer scoping.
- Administrative or maintenance integrations should resolve to `SAFE_ADMIN` or `FULL_ADMIN`.

## Related Documentation

- [Security roles overview](./SECURITY_ROLES.md)
- [Security implementation details](./SECURITY_IMPLEMENTATION.md)
- [WordPress integration](./WORDPRESS_INTEGRATION.md)
