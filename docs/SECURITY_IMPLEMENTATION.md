# Security Implementation

## Overview

Agentic Brain implements a **four-tier security model** across runtime enforcement, LLM controls, and external integrations.

Canonical roles:

1. **FULL_ADMIN** - unrestricted owner access
2. **SAFE_ADMIN** - guarded development access
3. **USER** - API-only customer access
4. **GUEST** - help-only anonymous access

Every security-sensitive feature should map to one of these roles.

## Enforcement Layers

### 1. Runtime enforcement

Runtime enforcement covers machine-level actions such as:

- shell commands
- file system reads and writes
- code execution
- configuration changes
- secret access
- admin APIs

Runtime enforcement is responsible for the hard separation between:

- **machine-capable roles**: `FULL_ADMIN`, `SAFE_ADMIN`
- **API-only role**: `USER`
- **help-only role**: `GUEST`

### 2. LLM enforcement

LLM enforcement controls:

- allowed providers
- prompt filtering level
- code execution permissions
- file modification permissions
- YOLO availability
- request rate limits

The LLM layer must follow the same four-tier model as the runtime layer so chat behavior matches platform security behavior.

### 3. Integration enforcement

External integrations such as WordPress and WooCommerce must preserve the same role boundaries:

- `FULL_ADMIN` can perform unrestricted administrative operations
- `SAFE_ADMIN` can perform developer and maintenance actions with guardrails
- `USER` can call approved APIs only
- `GUEST` can only consume public help content

## Canonical Permission Matrix

| Capability | FULL_ADMIN | SAFE_ADMIN | USER | GUEST |
| --- | --- | --- | --- | --- |
| Machine access | ✅ | ✅ | ❌ | ❌ |
| Shell commands | ✅ | ✅ with confirmation | ❌ | ❌ |
| File writes | ✅ | ✅ project-scoped | ❌ | ❌ |
| Code execution | ✅ | ✅ | ❌ | ❌ |
| API access | ✅ | ✅ | ✅ approved only | ❌ |
| LLM chat | ✅ | ✅ | ✅ | ⚠️ limited |
| Help/manuals | ✅ | ✅ | ✅ | ✅ |
| Rate limit | None | 1000/min | 60/min | 10/min |

## GUEST Enforcement Requirements

GUEST is a **help-only** role, not a lightweight API role.

GUEST users may access:

- FAQ content
- help documentation
- setup guides
- product information
- user manuals
- basic troubleshooting flows

GUEST users may not access:

- code execution
- shell commands
- business APIs
- account data
- file system operations
- machine resources
- data mutation endpoints

Implementation consequence: public website chat should resolve answers from curated documentation, not from privileged runtime or business API calls.

## USER Enforcement Requirements

USER is an **API-only** role.

Implementation rules:

- all business actions must go through approved controllers
- no direct shell or file access is allowed
- no direct machine inspection is allowed
- user identity and tenant/customer scope must be enforced before every API call
- audit logs should capture user, endpoint, method, outcome, and scope

Typical USER operations include:

- order lookup
- address update
- downloads lookup
- account status checks

## SAFE_ADMIN Enforcement Requirements

SAFE_ADMIN is the default role for trusted developers.

Implementation rules:

- allow project file access
- allow shell and code execution
- require confirmation or policy checks for destructive operations
- block or gate sensitive owner-only actions such as secret rotation or unrestricted infrastructure changes unless explicitly elevated

Typical SAFE_ADMIN operations include:

- editing source files
- running tests and migrations
- updating WordPress adapters
- troubleshooting integrations

## FULL_ADMIN Enforcement Requirements

FULL_ADMIN is the owner-level role.

Implementation rules:

- allow unrestricted runtime access
- allow unrestricted LLM capabilities
- allow secret and infrastructure access
- avoid artificial throttling unless imposed by an external provider

Typical FULL_ADMIN operations include:

- rotating credentials
- infrastructure recovery
- emergency rollback or remediation
- system-wide configuration changes

## Legacy Naming Note

Some older code paths and examples may still refer to `ADMIN` and `DEVELOPER`.

For documentation and new implementation work, use this canonical mapping:

| Legacy name | Canonical role |
| --- | --- |
| `ADMIN` | `FULL_ADMIN` |
| `DEVELOPER` | `SAFE_ADMIN` |
| `USER` | `USER` |
| `GUEST` | `GUEST` |

When updating code, prefer the canonical four-tier names in public APIs, configuration, and documentation.

## Authentication and Resolution

Role resolution should follow this order:

1. existing authenticated session
2. explicit owner/admin authentication → `FULL_ADMIN`
3. trusted developer authentication → `SAFE_ADMIN`
4. authenticated customer context → `USER`
5. anonymous fallback → `GUEST`

Important requirement: anonymous traffic must never resolve to API-capable or machine-capable behavior.

## WordPress and WooCommerce Mapping

| Audience | Role | Allowed behavior |
| --- | --- | --- |
| Anonymous visitor | `GUEST` | Help docs, setup, FAQ, product information |
| Logged-in customer | `USER` | Approved WordPress/WooCommerce API calls |
| Developer / maintainer | `SAFE_ADMIN` | Maintenance and integration work with guardrails |
| Owner / Joseph | `FULL_ADMIN` | Unrestricted platform control |

## Audit Expectations

Audit logs should capture:

- timestamp
- resolved role
- user or session identity
- action type
- target resource
- allow or deny decision
- reason for denial when blocked
- integration metadata for API-backed actions

## Recommended Verification

When changing security behavior, verify:

- `FULL_ADMIN` remains unrestricted
- `SAFE_ADMIN` keeps confirmations on risky actions
- `USER` cannot reach shell, file, or code execution paths
- `GUEST` cannot reach APIs or mutate data
- rate limits match the four-tier policy
- WordPress and WooCommerce traffic resolves to the correct role

## Related Documentation

- [Security roles overview](./SECURITY_ROLES.md)
- [Security quick start](./SECURITY_QUICKSTART.md)
- [API access control](./API_ACCESS_CONTROL.md)
- [WordPress integration](./WORDPRESS_INTEGRATION.md)
