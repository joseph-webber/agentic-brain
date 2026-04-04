# WordPress Role Mapping for BrainChat

## Overview

BrainChat respects WordPress and WooCommerce role-based access control. The chatbot can only perform actions that the current platform state allows, and it does so through WordPress REST API or WooCommerce APIs rather than direct server or database access.

For guest sessions, the rule is context-aware: **GUEST mirrors what an unauthenticated visitor can do on the connected platform.** On WooCommerce that includes storefront and cart flows. On plain WordPress that means public content and other public interactions the site owner allows.

## How It Works

1. BrainChat checks whether the request is anonymous, guest-session based, or authenticated.
2. If the request is anonymous, BrainChat resolves it to `GUEST` and limits actions to public or guest-scoped APIs.
3. If the user is authenticated, WordPress returns the user's role.
4. BrainChat maps the WordPress role to a chatbot mode and API capability set.
5. BrainChat calls WordPress REST API or WooCommerce API with the appropriate token or guest session context.
6. WordPress or WooCommerce performs the final permission check on every request.

## BrainChat Mode Mapping

| WordPress or platform state | BrainChat mode | Brain runtime role | Access pattern |
| --- | --- | --- | --- |
| Unauthenticated visitor or WooCommerce guest session | GUEST | `guest` | Public WordPress content plus guest-scoped WooCommerce Store API actions |
| Subscriber | GUEST | `guest` | Conservative public-content assistance with no machine access |
| Customer | USER | `user` | Self-service commerce APIs |
| Contributor | USER | `user` | Draft content APIs |
| Author | USER | `user` | Own-content publishing APIs |
| Editor | POWER USER | `user` | Editorial APIs across site content |
| Shop Manager | POWER USER | `user` | WooCommerce management APIs |
| Administrator | SAFE_ADMIN by default; FULL_ADMIN only for owner-controlled sessions | `safe_admin` by default, `full_admin` for owner sessions, or downgraded `user` for API-only deployments | Full admin APIs if the owner explicitly allows them |

`POWER USER` is still API-only. It means broader WordPress or WooCommerce permissions, not shell or machine access.

## Security Principles

1. **No direct machine access**: customer, staff, and guest chatbots do not touch the server directly.
2. **API-first communication**: all operations go through WordPress REST API, WooCommerce REST API, or WooCommerce Store API.
3. **Token or session-based auth**: JWT, OAuth, nonce, application-password, cart token, or storefront session data carries identity and scope.
4. **WordPress and WooCommerce enforce permissions**: the chatbot proposes actions; the platform decides.
5. **Rate limiting applies twice**: chatbot rate limits and platform rate limits both protect the system.
6. **No direct DB writes**: even administrator flows should use supported APIs.

## Role Capabilities Matrix

### Unauthenticated Visitor or Guest Shopper → GUEST Mode

- ✅ Ask questions about public site content
- ✅ Read public posts, pages, categories, and tags
- ✅ Search products and public content
- ✅ Browse WooCommerce products
- ✅ Add items to a session cart
- ✅ View the current cart
- ✅ Select a shipping option for the current cart
- ✅ Apply coupons to the current cart
- ✅ Complete guest checkout if the store allows it
- ✅ Submit comments if the site allows anonymous comments
- ❌ Cannot access account-only or order-history data
- ❌ Cannot create or edit protected content
- ❌ Cannot access admin, staff, or machine-level capabilities

### Customer → USER Mode

- ✅ View own orders and order status
- ✅ Update own profile
- ✅ Ask product questions
- ✅ Get shipping or tracking info for own orders
- ✅ View own downloads
- ❌ Cannot view other customers' data
- ❌ Cannot modify products, pricing, or inventory

### Contributor → USER Mode

- ✅ Create draft posts
- ✅ Edit own drafts
- ✅ Ask for help writing content
- ❌ Cannot publish content
- ❌ Cannot edit another user's content

### Author → USER Mode

- ✅ Create and publish own posts
- ✅ Upload media
- ✅ Edit and delete own posts
- ❌ Cannot edit all site content
- ❌ Cannot manage categories or site settings

### Editor → POWER USER Mode

- ✅ Edit and publish posts across the site
- ✅ Manage pages, categories, and comments
- ✅ Review or update editorial content
- ❌ Cannot manage plugins or themes
- ❌ Cannot manage users or global settings

### Shop Manager → POWER USER Mode

- ✅ All customer capabilities
- ✅ View all orders
- ✅ Update products and inventory
- ✅ Process refunds
- ✅ View reports and today's sales
- ❌ Cannot manage users
- ❌ Cannot change site-wide WordPress settings

### Administrator → SAFE_ADMIN / FULL_ADMIN (Optional)

- ✅ Full WordPress admin API capabilities
- ✅ Maps to `safe_admin` by default
- ✅ May elevate to `full_admin` only for explicit owner-controlled sessions
- ✅ May enable YOLO-style automation if the site owner explicitly allows it
- ✅ Plugin, theme, user, and settings management through APIs
- ⚠️ Should still use supported APIs, not direct database access

## Representative API Families by Role

These are examples of the API families the chatbot should use.

| Role or state | Example API families |
| --- | --- |
| Guest session / Subscriber | `GET /wp-json/wp/v2/posts`, `GET /wp-json/wp/v2/pages`, `GET /wp-json/wp/v2/search`, `GET /wp-json/wc/store/v1/products`, `GET /wp-json/wc/store/v1/cart`, `POST /wp-json/wc/store/v1/cart/add-item`, `POST /wp-json/wc/store/v1/cart/apply-coupon`, `POST /wp-json/wc/store/v1/checkout` |
| Customer | `GET /wp-json/wc/v3/orders?customer=<self>`, `POST /wp-json/wp/v2/users/me` |
| Contributor | `POST /wp-json/wp/v2/posts` with `status=draft` |
| Author | `POST /wp-json/wp/v2/posts/<id>`, `POST /wp-json/wp/v2/media` |
| Editor | `POST /wp-json/wp/v2/pages/<id>`, `POST /wp-json/wp/v2/categories` |
| Shop Manager | `GET /wp-json/wc/v3/reports/sales`, `POST /wp-json/wc/v3/products/<id>`, `POST /wp-json/wc/v3/refunds` |
| Administrator | `POST /wp-json/wp/v2/settings`, `GET /wp-json/wp/v2/users`, plugin/theme endpoints |

## Real-World Chat Examples

### Example 1: Guest asks “Show me laptops under $1000”

**Platform state:** anonymous WooCommerce visitor

**Chatbot flow:**

1. Resolve the session to `GUEST`.
2. Call WooCommerce Store API product endpoints with public filters.
3. Return matching products and optional add-to-cart actions.

**Example API call**

```http
GET /wp-json/wc/store/v1/products?search=laptop&max_price=100000
```

**Allowed result**

- “Here are laptops under $1000 that are in stock right now.”

**Blocked result**

- The chatbot must not reveal private inventory notes, draft products, or another customer's cart.

### Example 2: Guest asks “Add this to my cart and use code SAVE10”

**Platform state:** anonymous WooCommerce visitor with a storefront session

**Chatbot flow:**

1. Resolve the session to `GUEST`.
2. Add the selected item to the current guest cart.
3. Apply the coupon to that same guest cart.
4. Return the updated cart summary.

**Example API calls**

```http
POST /wp-json/wc/store/v1/cart/add-item
POST /wp-json/wc/store/v1/cart/apply-coupon
```

**Allowed result**

- “Done — the item is in your cart and SAVE10 has been applied to this session.”

**Blocked result**

- The chatbot must not access saved payment methods, customer-only coupons, or another shopper's cart.

### Example 3: Customer asks “Where is my order?”

**User role:** `customer`

**Chatbot flow:**

1. Confirm the user is authenticated as the order owner.
2. Call WooCommerce orders API scoped to the current customer.
3. Return shipment state and tracking details if present.

**Example API call**

```http
GET /wp-json/wc/v3/orders?customer=123&orderby=date&order=desc
Authorization: Bearer <customer-token>
```

**Allowed result**

- “Your most recent order is `processing` and the tracking link is available.”

**Blocked result**

- The chatbot must not fetch or reveal another customer's order.

### Example 4: Shop manager asks “Show me today’s sales”

**User role:** `shop_manager`

**Chatbot flow:**

1. Confirm the session role is `shop_manager`.
2. Call a WooCommerce reports endpoint.
3. Summarize revenue, order count, refunds, and top products.

**Example API call**

```http
GET /wp-json/wc/v3/reports/sales?period=today
Authorization: Bearer <shop-manager-token>
```

**Allowed result**

- “Today’s gross sales are $4,820 across 37 orders.”

**Blocked result**

- The chatbot should not call plugin, theme, or user-management endpoints for a shop manager.

### Example 5: How BrainChat should call WordPress and WooCommerce APIs

BrainChat should act as a thin, role-aware client:

```python
from agentic_brain.integrations.wp_role_mapper import get_wordpress_role_profile

profile = get_wordpress_role_profile("customer")
token = "<jwt-or-oauth-token>"

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
}

if "view_own_orders" in profile.capabilities:
    # WooCommerce order lookup for the authenticated user
    response = await client.get(
        "/wp-json/wc/v3/orders",
        params={"customer": current_user_id},
        headers=headers,
    )
```

Key rules:

- use `/wp-json/wp/v2/...` for WordPress content and admin resources
- use `/wp-json/wc/v3/...` for authenticated WooCommerce management
- use `/wp-json/wc/store/v1/...` for guest storefront browsing, cart, coupon, shipping, and checkout flows
- never bypass WordPress permission checks with direct database or shell access

## Implementation Notes

- The reference mapper lives in `src/agentic_brain/integrations/wp_role_mapper.py`.
- The mapper normalizes raw WordPress role strings, resolves a primary role when multiple roles are present, and returns a BrainChat profile with:
  - chatbot mode
  - runtime security role
  - allowed capabilities
  - representative API families
- Administrators can be downgraded to non-admin chatbot handling when the site owner wants API-only guardrails without full automation.
- Anonymous storefront traffic should be resolved to `GUEST` even when there is no authenticated WordPress role attached.
