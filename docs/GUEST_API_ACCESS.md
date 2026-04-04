# Guest API Access Guide

## Context-Aware Permissions

The `GUEST` role does not mean "no access." It means the chatbot can use whatever public or guest-scoped capabilities the connected platform exposes to unauthenticated visitors.

That keeps the assistant helpful for shoppers and readers while still blocking:

- shell commands
- file system access
- code execution
- privileged admin APIs
- authenticated customer data
- machine or infrastructure access

## WooCommerce Guest Capabilities

A chatbot running as `GUEST` on a WooCommerce site can help users:

- browse products: "Show me laptops under $1000"
- browse categories: "What do you have in camping gear?"
- add to cart: "Add this to my cart"
- view cart: "What's in my cart?"
- review shipping options: "What shipping methods are available?"
- apply coupons: "Use code SAVE10"
- checkout: "I want to buy these items"

These flows are guest-capable because they operate on the current storefront session rather than an authenticated customer account.

### Available API Endpoints

All WooCommerce Store API endpoints below are under `/wp-json/wc/store/v1/`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/products` | GET | Browse or search public products |
| `/products/categories` | GET | Browse public product categories |
| `/cart` | GET | View the current cart |
| `/cart/add-item` | POST | Add a product to the current cart |
| `/cart/update-item` | POST | Update quantity or variation in the cart |
| `/cart/remove-item` | POST | Remove an item from the cart |
| `/cart/apply-coupon` | POST | Apply a coupon to the current cart |
| `/cart/remove-coupon` | POST | Remove an applied coupon |
| `/cart/select-shipping-rate` | POST | Select a shipping option for the cart |
| `/checkout` | POST | Submit guest checkout data |

> Some write endpoints use a nonce or cart token for the current session. That is still compatible with `GUEST` because the scope remains the visitor's own cart only.

## WordPress Guest Capabilities

On a plain WordPress site, a `GUEST` chatbot can help users:

- read public posts and pages
- search public content
- browse categories and tags
- discover documentation and FAQ content
- submit comments if the site allows anonymous comments

### Representative WordPress Public Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/wp-json/wp/v2/posts` | GET | List public posts |
| `/wp-json/wp/v2/pages` | GET | List public pages |
| `/wp-json/wp/v2/search` | GET | Search public content |
| `/wp-json/wp/v2/categories` | GET | Browse categories |
| `/wp-json/wp/v2/tags` | GET | Browse tags |
| `/wp-json/wp/v2/comments` | POST | Submit a comment if public comments are enabled |

## Standalone (No Platform) Guest

If Agentic Brain is not connected to WordPress, WooCommerce, or another platform, `GUEST` falls back to public help behavior only:

- FAQ access
- help documentation
- setup guides
- user manuals
- basic troubleshooting

In standalone mode there is no guest shopping or platform API surface, so the chatbot should stay in read-only help flows.

## Implementation Rule of Thumb

When deciding whether `GUEST` may perform an action, ask:

1. Can an unauthenticated visitor do this on the connected platform?
2. Is the action limited to public data or the visitor's own guest session?
3. Does it avoid machine access, privileged APIs, and other users' data?

If the answer to all three is yes, it is usually a valid `GUEST` capability.

## Related Documentation

- [Security roles overview](./SECURITY_ROLES.md)
- [WordPress integration](./WORDPRESS_INTEGRATION.md)
- [WordPress role mapping](./WORDPRESS_ROLE_MAPPING.md)
