# WordPress Integration

## Overview

WordPress and WooCommerce integrations must follow the canonical four-tier security model:

1. **FULL_ADMIN** - unrestricted owner access
2. **SAFE_ADMIN** - trusted developer access with guardrails
3. **USER** - authenticated customer API access
4. **GUEST** - context-aware anonymous access that mirrors public WordPress and WooCommerce guest permissions

This keeps storefront support useful without exposing machine access or privileged business endpoints.

## Role Mapping

| WordPress audience | Canonical role | Allowed behavior |
| --- | --- | --- |
| Platform owner/administrator | `FULL_ADMIN` | Unrestricted platform control |
| Developer or trusted maintainer | `SAFE_ADMIN` | Integration work, diagnostics, and maintenance |
| Logged-in customer | `USER` | Approved authenticated WordPress and WooCommerce API calls |
| Anonymous visitor or WooCommerce guest shopper | `GUEST` | Public WordPress content plus guest-scoped WooCommerce Store API actions |

## Customer vs Visitor Behavior

### WordPress Customer (USER mode)

USER mode is for authenticated customers.

Examples:

- **"Where is my order?"** → Calls WooCommerce customer API
- **"Update my address"** → Calls WordPress REST API
- **"Show my downloads"** → Calls WooCommerce downloads endpoint

Requirements:

- customer identity must be verified
- requests must be scoped to the current customer
- every API call should be audited
- no shell, code execution, or file system access is allowed

### Website Visitor (GUEST mode)

GUEST mode is for anonymous visitors and guest shoppers.

Examples:

- **"Show me laptops under $1000"** → Uses public WooCommerce product browsing
- **"Add this to my cart"** → Uses a guest cart endpoint for the current session
- **"What are the shipping options?"** → Uses guest shipping-rate flows
- **"Use code SAVE10"** → Applies a coupon to the current guest cart
- **"How do I install this?"** → Shows setup guide
- **"Find blog posts about backups"** → Searches public WordPress content

Requirements:

- only use public or guest-scoped platform capabilities
- do not expose account, order-history, or private content
- do not allow code execution, file access, or machine access
- do not treat GUEST as an authenticated customer role

## WooCommerce Guest Shopping Capabilities

A chatbot running as `GUEST` on a WooCommerce site can help users:

- browse products and categories
- search the catalog using public filters
- add items to a session cart
- review and update the current cart
- inspect guest shipping options after address entry
- apply or remove coupons on the current cart
- complete guest checkout when the store permits it

### WooCommerce Store API endpoints for guests

These endpoints are designed for storefront and guest-session use under `/wp-json/wc/store/v1/`.

| Endpoint | Method | Guest use |
| --- | --- | --- |
| `/products` | GET | Browse or search public products |
| `/products/categories` | GET | Browse public product categories |
| `/cart` | GET | View the current guest cart |
| `/cart/add-item` | POST | Add an item to the guest cart |
| `/cart/update-item` | POST | Change quantity or variation in the guest cart |
| `/cart/remove-item` | POST | Remove an item from the guest cart |
| `/cart/apply-coupon` | POST | Apply a coupon to the current cart |
| `/cart/remove-coupon` | POST | Remove an applied coupon |
| `/cart/select-shipping-rate` | POST | Select a shipping method for the current cart |
| `/checkout` | POST | Submit guest checkout data and place an order |

> Some Store API write operations use a session nonce or cart token, but they remain guest-capable because they operate only on the current storefront session.

## WordPress Guest Content Capabilities

On a plain WordPress site, `GUEST` can mirror what an unauthenticated visitor can do, such as:

- read public posts and pages
- search public content
- browse public categories and tags
- submit comments if anonymous comments are enabled
- follow help, FAQ, and setup documentation

Representative public endpoints include:

- `GET /wp-json/wp/v2/posts`
- `GET /wp-json/wp/v2/pages`
- `GET /wp-json/wp/v2/search`
- `GET /wp-json/wp/v2/categories`
- `GET /wp-json/wp/v2/tags`
- `POST /wp-json/wp/v2/comments` when the site explicitly allows it

## What GUEST Cannot Access

GUEST users cannot:

- execute any code
- access machine resources
- call privileged admin APIs
- access authenticated customer endpoints
- modify another user's data
- view private posts, orders, downloads, or account details

## Recommended Integration Pattern

### Public website widget

Resolve anonymous traffic to `GUEST` and serve:

- public product discovery
- guest cart and checkout help
- product FAQ
- setup content
- troubleshooting guides
- public documentation and blog content

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
| WordPress/WooCommerce APIs | ✅ | ✅ | ✅ approved authenticated only | ⚠️ Public or guest-scoped only |
| LLM chat | ✅ | ✅ | ✅ | ⚠️ limited |
| Public help content | ✅ | ✅ | ✅ | ✅ |

## Implementation Guidance

- map WordPress auth state to one canonical role before handling the request
- resolve anonymous or storefront guest sessions to `GUEST`
- keep USER flows strictly authenticated and API-based
- keep GUEST flows limited to public content and guest-scoped Store API operations
- reserve YOLO and machine access for SAFE_ADMIN and FULL_ADMIN only
- reserve unrestricted ownership actions for FULL_ADMIN only

## Related Documentation

- [Security roles overview](./SECURITY_ROLES.md)
- [Guest API access guide](./GUEST_API_ACCESS.md)
- [API access control](./API_ACCESS_CONTROL.md)
- [Security implementation details](./SECURITY_IMPLEMENTATION.md)
