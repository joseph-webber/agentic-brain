# Agentic Brain Security Roles

## Overview

Agentic Brain uses a **four-tier security model** for every interactive surface, automation flow, and embedded assistant:

1. **FULL_ADMIN** - Unrestricted access for Joseph and equivalent owners
2. **SAFE_ADMIN** - Full development power with confirmation guardrails
3. **USER** - API-only access for authenticated customers
4. **GUEST** - Help-only access for anonymous visitors

The model is intentionally simple:

- **FULL_ADMIN** and **SAFE_ADMIN** can work on the machine
- **USER** can work through approved APIs only
- **GUEST** can only read public help content

## Canonical Role Definitions

| Role | Primary audience | Access model | Summary |
| --- | --- | --- | --- |
| `FULL_ADMIN` | Joseph | Unrestricted machine + platform access | No guardrails, no rate limit |
| `SAFE_ADMIN` | Developers and trusted operators | Machine access with confirmations | Powerful, but protected from risky mistakes |
| `USER` | Authenticated customers | API-only | Can use approved business APIs, but cannot touch the machine |
| `GUEST` | Anonymous visitors | Help-only | Can read guidance, but cannot execute or change anything |

## Feature Matrix

| Feature | FULL_ADMIN | SAFE_ADMIN | USER | GUEST |
|---------|------------|------------|------|-------|
| YOLO Mode | ✅ | ✅ (confirm) | ❌ | ❌ |
| Shell Commands | ✅ | ✅ (confirm) | ❌ | ❌ |
| File System | ✅ | ✅ | ❌ | ❌ |
| API Access | ✅ | ✅ | ✅ | ❌ |
| LLM Chat | ✅ | ✅ | ✅ | ⚠️ Limited |
| Code Execution | ✅ | ✅ | ❌ | ❌ |
| FAQ/Help | ✅ | ✅ | ✅ | ✅ |
| User Manuals | ✅ | ✅ | ✅ | ✅ |
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

**Typical examples:** Joseph debugging production, emergency recovery, system-wide maintenance.

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
- call approved business APIs
- retrieve or update data only through those APIs

USER cannot:

- execute shell commands
- execute code
- access the file system directly
- modify server configuration
- access machine resources

**Typical examples:** WooCommerce customers checking orders, updating account details, viewing downloads.

### GUEST

**Purpose:** anonymous help and product education.

GUEST users can **ONLY** access:

- FAQ content
- Help documentation
- Setup guides
- Product information
- User manuals
- Basic troubleshooting

GUEST users **CANNOT**:

- Execute any code
- Access any APIs
- Modify any data
- Access machine resources

GUEST chat is intentionally limited to safe help and explanation flows.

## Use Case Examples

### WordPress Customer (USER mode)

- **"Where is my order?"** → Calls WooCommerce API
- **"Update my address"** → Calls WordPress REST API
- **"Show my downloads"** → Calls WooCommerce downloads endpoint

### Website Visitor (GUEST mode)

- **"How do I install this?"** → Shows setup guide
- **"What does this product do?"** → Shows product FAQ
- **"I need help"** → Shows help documentation

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

- approved REST APIs
- scoped customer endpoints
- audited integration layers

### Help-only role

**GUEST** is intentionally separate from API access.

GUEST is limited to public, read-only assistance such as:

- onboarding
- manuals
- FAQs
- troubleshooting guidance

## Operational Guidance

- Use **FULL_ADMIN** only for Joseph-level ownership tasks.
- Use **SAFE_ADMIN** for day-to-day development and maintenance.
- Use **USER** for authenticated customer workflows.
- Use **GUEST** for anonymous chat widgets, marketing pages, and public support.
- Default to the lowest role that can complete the task.

## Related Documentation

- [Security implementation details](./SECURITY_IMPLEMENTATION.md)
- [Security quick start](./SECURITY_QUICKSTART.md)
- [API access control](./API_ACCESS_CONTROL.md)
- [WordPress integration](./WORDPRESS_INTEGRATION.md)
