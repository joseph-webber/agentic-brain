# WordPress Role Mapping for BrainChat

## Overview

BrainChat respects WordPress and WooCommerce role-based access control. The chatbot can only perform actions that the authenticated WordPress user role allows, and it does so through WordPress REST API and WooCommerce REST API calls rather than direct server or database access.

## How It Works

1. User logs into WordPress or WooCommerce.
2. WordPress authenticates the session and returns the user's role.
3. BrainChat maps the WordPress role to a chatbot mode and API capability set.
4. BrainChat calls WordPress REST API or WooCommerce REST API with the user's token.
5. WordPress performs the final permission check on every request.

## BrainChat Mode Mapping

| WordPress role | BrainChat mode | Brain runtime role | Access pattern |
| --- | --- | --- | --- |
| Subscriber | GUEST | `guest` | Public content only |
| Customer | USER | `user` | Self-service commerce APIs |
| Contributor | USER | `user` | Draft content APIs |
| Author | USER | `user` | Own-content publishing APIs |
| Editor | POWER USER | `user` | Editorial APIs across site content |
| Shop Manager | POWER USER | `user` | WooCommerce management APIs |
| Administrator | ADMIN (optional) | `safe_admin` or downgraded `user` | Full admin APIs if owner allows |

`POWER USER` is still API-only. It means broader WordPress or WooCommerce permissions, not shell or machine access.

## Security Principles

1. **No direct machine access**: customer and staff chatbots do not touch the server directly.
2. **API-only communication**: all operations go through WordPress REST API or WooCommerce REST API.
3. **Token-based auth**: JWT, OAuth, nonce, or application-password flows carry the user's identity.
4. **WordPress enforces permissions**: the chatbot proposes actions; WordPress decides.
5. **Rate limiting applies twice**: chatbot rate limits and WordPress/WooCommerce rate limits both protect the system.
6. **No direct DB writes**: even administrator flows should use supported APIs.

## Role Capabilities Matrix

### Subscriber → GUEST Mode

- ✅ Ask questions about public site content
- ✅ Get help navigating the site
- ✅ Browse products and public documentation
- ❌ Cannot create or edit content
- ❌ Cannot access orders or purchases

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

### Administrator → ADMIN Mode (Optional)

- ✅ Full WordPress admin API capabilities
- ✅ May enable YOLO-style automation if the site owner explicitly allows it
- ✅ Plugin, theme, user, and settings management through APIs
- ⚠️ Should still use supported APIs, not direct database access

## Representative API Families by Role

These are examples of the API families the chatbot should use.

| Role | Example API families |
| --- | --- |
| Subscriber | `GET /wp-json/wp/v2/posts`, `GET /wp-json/wp/v2/pages`, `GET /wp-json/wc/store/v1/products` |
| Customer | `GET /wp-json/wc/v3/orders?customer=<self>`, `POST /wp-json/wp/v2/users/me` |
| Contributor | `POST /wp-json/wp/v2/posts` with `status=draft` |
| Author | `POST /wp-json/wp/v2/posts/<id>`, `POST /wp-json/wp/v2/media` |
| Editor | `POST /wp-json/wp/v2/pages/<id>`, `POST /wp-json/wp/v2/categories` |
| Shop Manager | `GET /wp-json/wc/v3/reports/sales`, `POST /wp-json/wc/v3/products/<id>`, `POST /wp-json/wc/v3/refunds` |
| Administrator | `POST /wp-json/wp/v2/settings`, `GET /wp-json/wp/v2/users`, plugin/theme endpoints |

## Real-World Chat Examples

### Example 1: Customer asks “Where is my order?”

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

### Example 2: Shop manager asks “Show me today’s sales”

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

### Example 3: How BrainChat should call WordPress and WooCommerce APIs

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
- use `/wp-json/wc/store/v1/...` for public storefront browsing when no login is required
- never bypass WordPress permission checks with direct database or shell access

## Implementation Notes

- The reference mapper lives in `src/agentic_brain/integrations/wp_role_mapper.py`.
- The mapper normalizes raw WordPress role strings, resolves a primary role when multiple roles are present, and returns a BrainChat profile with:
  - chatbot mode
  - runtime security role
  - allowed capabilities
  - representative API families
- Administrators can be downgraded to non-admin chatbot handling when the site owner wants API-only guardrails without full automation.
