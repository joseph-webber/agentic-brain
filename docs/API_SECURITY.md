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

### Three Access Modes

#### 1. ADMIN MODE (Joseph's Default)
- ✅ Full machine access (YOLO, file system, shell)
- ✅ Can configure API integrations
- ✅ Can manage API keys
- ✅ Direct database access if needed
- ✅ Can access all external APIs
- **Use case**: System administration, development, debugging

#### 2. USER/CUSTOMER MODE (API-Only)
- ❌ **NO machine access at all**
- ✅ **ONLY API access through configured endpoints**
- ✅ WordPress REST API (limited by WP user role)
- ✅ WooCommerce REST API (limited by WC capabilities)
- ✅ Other configured APIs with appropriate scopes
- ✅ Can read time/date (harmless system info)
- **Use case**: Customer support chatbots, store assistants, content contributors

#### 3. GUEST MODE (Read-Only)
- ❌ NO machine access
- ✅ Read-only API access (public endpoints only)
- ✅ FAQ/help content only
- ✅ Very rate limited
- **Use case**: Anonymous website visitors, public help desk

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
