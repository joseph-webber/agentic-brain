# Agentic Brain Security Roles

## Overview

Agentic Brain uses a **four-tier security model** for every interactive surface, automation flow, and embedded assistant:

1. **FULL_ADMIN** - unrestricted owner access
2. **SAFE_ADMIN** - trusted developer access with confirmation guardrails
3. **USER** - authenticated customer API access
4. **GUEST** - context-aware anonymous access that mirrors platform guest permissions

The model is intentionally simple:

- **FULL_ADMIN** and **SAFE_ADMIN** can work on the machine
- **USER** can work through approved authenticated APIs only
- **GUEST** can use public or session-scoped guest capabilities exposed by the connected platform
- if no platform is connected, **GUEST** falls back to FAQ, help docs, and basic troubleshooting

## Canonical Role Definitions

| Role | Primary audience | Access model | Summary |
| --- | --- | --- | --- |
| `FULL_ADMIN` | Platform owner/administrator | Unrestricted machine + platform access | No guardrails, no rate limit |
| `SAFE_ADMIN` | Developers and trusted operators | Machine access with confirmations | Powerful, but protected from risky mistakes |
| `USER` | Authenticated customers | API-only | Can use approved business APIs, but cannot touch the machine |
| `GUEST` | Anonymous visitors | Context-aware public access | Mirrors what guests can do on the connected platform without gaining machine or privileged API access |

## Feature Matrix

| Feature | FULL_ADMIN | SAFE_ADMIN | USER | GUEST |
|---------|------------|------------|------|-------|
| YOLO Mode | ✅ | ✅ (confirm) | ❌ | ❌ |
| Shell Commands | ✅ | ✅ (confirm) | ❌ | ❌ |
| File System | ✅ | ✅ | ❌ | ❌ |
| API Access | ✅ | ✅ | ✅ | ⚠️ Public or guest-scoped only |
| LLM Chat | ✅ | ✅ | ✅ | ⚠️ Limited |
| Code Execution | ✅ | ✅ | ❌ | ❌ |
| FAQ/Help | ✅ | ✅ | ✅ | ✅ |
| User Manuals | ✅ | ✅ | ✅ | ✅ |
| Platform Guest Actions | ✅ | ✅ | n/a | ✅ if platform allows |
| Rate Limit | None | 1000/min | 60/min | 10/min |

## Role Details

### FULL_ADMIN

**Purpose:** unrestricted ownership and recovery access.

FULL_ADMIN can:

- run shell commands without confirmation gates
- read and write the full file system
- execute code freely
- use all APIs and admin endpoints
- access secrets, configuration, and infrastructure controls
- use all LLM features, including YOLO flows

**Typical examples:** Administrator debugging production, emergency recovery, system-wide maintenance.

### SAFE_ADMIN

**Purpose:** trusted development with guardrails.

SAFE_ADMIN can:

- run shell commands, but risky operations should require confirmation
- read and write project files
- execute code and automation safely
- use approved APIs and developer tooling
- use full LLM chat and coding features

SAFE_ADMIN should **not** be treated as unrestricted ownership. It exists for fast delivery with safety checks.

**Typical examples:** developers shipping features, running tests, updating integrations, maintaining documentation.

### USER

**Purpose:** secure customer self-service through APIs.

USER can:

- chat with the assistant
- read FAQ, manuals, and setup guides
- call approved authenticated business APIs
- retrieve or update data only through those APIs

USER cannot:

- execute shell commands
- execute code
- access the file system directly
- modify server configuration
- access machine resources

**Typical examples:** WooCommerce customers checking orders, updating account details, viewing downloads.

### GUEST

**Purpose:** context-aware anonymous assistance that mirrors platform guest permissions.

GUEST does **not** mean "no access." It means the assistant may do whatever an unauthenticated visitor can do on the connected platform, while still blocking machine access and privileged APIs.

GUEST users can access:

- FAQ content, help documentation, setup guides, and manuals
- public product and catalog information
- public or session-scoped storefront endpoints exposed to guests
- public WordPress posts, pages, and search results
- comment submission if the site allows anonymous comments
- basic troubleshooting and onboarding guidance

GUEST users **CANNOT**:

- execute code or shell commands
- access the file system or machine resources
- use admin, staff, or authenticated customer APIs
- access another user's account, order history, or personal data
- change server configuration or infrastructure settings
- bypass the connected platform's permission checks

#### GUEST examples by platform

**WooCommerce GUEST can:**

- browse products
- add items to a session cart
- view the cart
- review shipping options
- apply coupons
- complete guest checkout if the store allows it

**WordPress GUEST can:**

- read public posts and pages
- search public content
- browse public product content on WooCommerce-backed sites
- submit comments if enabled by the site owner

**Standalone GUEST can:**

- access FAQ content
- read help documentation
- follow setup guides
- get basic troubleshooting help

GUEST chat is intentionally limited to safe public assistance and guest-capable flows.

## Use Case Examples

### WordPress Customer (USER mode)

- **"Where is my order?"** → Calls WooCommerce customer API
- **"Update my address"** → Calls authenticated WordPress or WooCommerce API
- **"Show my downloads"** → Calls WooCommerce downloads endpoint

### Website Visitor (GUEST mode)

- **"Show me laptops under $1000"** → Uses public WooCommerce product browsing
- **"Add this to my cart"** → Uses a guest cart endpoint for the current session
- **"How do I install this?"** → Shows setup guide
- **"What does this product do?"** → Shows product FAQ or public content

### SAFE_ADMIN Session

- run tests with confirmation for risky steps
- edit project files directly
- inspect logs and integrations
- use coding and automation tools without full owner privileges

### Owner Session (FULL_ADMIN mode)

- rotate secrets
- recover from outages
- update infrastructure or deployment settings
- perform emergency actions without guardrails

## Access Model Summary

### Machine-capable roles

**FULL_ADMIN** and **SAFE_ADMIN** can interact with the machine itself.

That includes:

- shell commands
- file system access
- code execution
- automation workflows

### API-only role

**USER** never gets direct machine access.

USER workflows must go through:

- approved authenticated REST APIs
- scoped customer endpoints
- audited integration layers

### Context-aware guest role

**GUEST** never gets machine access, but it may use the same public or guest-scoped capabilities a platform exposes to anonymous visitors.

Examples:

- WooCommerce Store API product, cart, coupon, shipping, and checkout flows for the current guest session
- WordPress public posts, pages, and search endpoints
- standalone FAQ, docs, manuals, and troubleshooting guidance

If the connected platform does not expose a guest capability, **GUEST** cannot perform it.

## Operational Guidance

- Use **FULL_ADMIN** only for platform owner/administrator-level tasks.
- Use **SAFE_ADMIN** for day-to-day development and maintenance.
- Use **USER** for authenticated customer workflows.
- Use **GUEST** for anonymous chat widgets, storefront visitors, marketing pages, and public support.
- Treat **GUEST** as platform-aware public access, not as an authenticated role.
- Default to the lowest role that can complete the task.

## Related Documentation

- [Security implementation details](./SECURITY_IMPLEMENTATION.md)
- [Security quick start](./SECURITY_QUICKSTART.md)
- [API access control](./API_ACCESS_CONTROL.md)
- [WordPress integration](./WORDPRESS_INTEGRATION.md)
- [Guest API access guide](./GUEST_API_ACCESS.md)
