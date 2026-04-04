# API-Based Security Architecture

**Created**: 2026-04-02  
**Author**: Joseph Webber  
**Status**: Implemented

## Joseph's Key Insight

Customer/User chatbots should **NOT** have direct machine access. Instead:

1. They should **ONLY** access external APIs (WordPress REST, WooCommerce REST, etc.)
2. Their permissions are controlled by the API's role system (WordPress roles, WooCommerce capabilities)
3. They are given API keys that match their role privileges
4. **No direct file system, shell, or machine access - only API access**

## Security Model

### Four Access Modes

#### 1. FULL_ADMIN (Joseph's Default)
- ✅ Full machine access (YOLO, file system, shell)
- ✅ Can configure API integrations
- ✅ Can manage API keys and secrets
- ✅ Can access all external APIs and infrastructure controls
- ✅ No role-level rate limit
- **Use case**: Ownership, recovery, system administration

#### 2. SAFE_ADMIN
- ✅ Machine access with safety guardrails and confirmations for risky actions
- ✅ Can configure project integrations and developer tooling
- ✅ Can access approved APIs for development and maintenance
- ❌ No unrestricted secrets access
- **Use case**: Trusted development, operations, maintenance

#### 3. USER (API-Only)
- ❌ **NO machine access at all**
- ✅ **ONLY authenticated API access through configured endpoints**
- ✅ WordPress REST API (limited by WP user role)
- ✅ WooCommerce REST API (limited by WC capabilities)
- ✅ Other configured APIs with appropriate scopes
- **Use case**: Customer support chatbots, store assistants, content contributors

#### 4. GUEST (Public / Guest-Scoped)
- ❌ No machine access
- ✅ Public and guest-scoped API access only
- ✅ FAQ/help content and public documentation
- ✅ Guest storefront/cart flows when the connected platform allows them
- ✅ Strict rate limiting
- **Use case**: Anonymous website visitors, guest shoppers, public help desk

## WordPress Role Mapping

| WordPress Role | Can Read | Can Write | Can Publish | Can Manage Users |
|---------------|----------|-----------|-------------|------------------|
| **Subscriber** | ✅ | ❌ | ❌ | ❌ |
| **Contributor** | ✅ | ✅ (drafts) | ❌ | ❌ |
| **Author** | ✅ | ✅ | ✅ (own posts) | ❌ |
| **Editor** | ✅ | ✅ | ✅ (all posts) | ❌ |
| **Administrator** | ✅ | ✅ | ✅ | ✅ |

## WooCommerce Role Mapping

| WooCommerce Role | View Products | View Orders | Manage Products | Manage Orders | View Reports |
|-----------------|---------------|-------------|-----------------|---------------|--------------|
| **Customer** | ✅ | ✅ (own only) | ❌ | ❌ | ❌ |
| **Shop Manager** | ✅ | ✅ (all) | ✅ | ✅ | ✅ |
| **Administrator** | ✅ | ✅ (all) | ✅ | ✅ | ✅ |

See full documentation in `docs/SECURITY_ROLES.md`.
