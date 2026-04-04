# API-Based Security Architecture

**Status**: ✅ Implemented  
**Version**: 1.0.0  
**Date**: 2026-04-02

## Overview

This implements Joseph's key security insight:

> **Customer/User chatbots should ONLY access external APIs, not have direct machine access.**

## Key Principle

- **ADMIN MODE**: Full machine access (shell, files, database) + API access
- **USER/CUSTOMER MODE**: **API-ONLY** (WordPress, WooCommerce, etc.) - NO machine access
- **GUEST MODE**: Read-only API access only

## Architecture

```
┌─────────────────────────────────────────┐
│ Chatbot (ADMIN/USER/GUEST)              │
├─────────────────────────────────────────┤
│ API Access Controller                    │
│ - Permission enforcement                 │
│ - Rate limiting                          │
│ - Audit logging                          │
├─────────────────────────────────────────┤
│ External APIs                            │
│ - WordPress REST API                     │
│ - WooCommerce REST API                   │
│ - Other configured APIs                  │
├─────────────────────────────────────────┤
│ Protected Resources                      │
│ - Database                               │
│ - File System                            │
└─────────────────────────────────────────┘
```

## Files Created

### Core Security
- `src/agentic_brain/security/api_access.py` - API access controller
- `src/agentic_brain/security/roles.py` - Updated with API permissions

### Integrations
- `src/agentic_brain/integrations/wordpress.py` - WordPress REST API
- `src/agentic_brain/integrations/woocommerce.py` - WooCommerce REST API

### Documentation
- `docs/API_SECURITY.md` - Quick reference
- `docs/SECURITY_ROLES.md` - Full documentation (backed up old version)

### Tests
- `tests/security/test_api_access.py` - 21 comprehensive tests (all passing ✅)

### Examples
- `examples/api_security_demo.py` - Runnable demonstration

## Usage

### WordPress Customer Support Bot

```python
from agentic_brain.integrations import create_wordpress_client, WordPressRole
from agentic_brain.security.roles import SecurityRole

# Create chatbot with WordPress AUTHOR role
wp_client = create_wordpress_client(
    site_url="https://example.com",
    username="chatbot",
    app_password="xxxx xxxx xxxx xxxx",
    wp_role=WordPressRole.AUTHOR,
    chatbot_role=SecurityRole.USER,  # API-ONLY
)

# Can create and publish posts
await wp_client.create_post(title="Help Article", content="...")

# Cannot access file system ❌
# Cannot run shell commands ❌
```

### WooCommerce Customer Assistant

```python
from agentic_brain.integrations import create_woocommerce_client, WooCommerceRole

# Create chatbot for customer #42
wc_client = create_woocommerce_client(
    site_url="https://shop.example.com",
    consumer_key="ck_xxxxx",
    consumer_secret="cs_xxxxx",
    wc_role=WooCommerceRole.CUSTOMER,
    chatbot_role=SecurityRole.USER,
    customer_id=42,  # CRITICAL: Can only see THIS customer's orders
)

# Can view own orders
orders = await wc_client.list_orders()  # Only customer #42's orders

# Cannot view other customers' orders
await wc_client.list_orders(customer=99)  # ❌ SecurityViolation
```

## Security Features

### 1. Role-Based Access Control

| Role | Machine Access | API Access | Use Case |
|------|----------------|------------|----------|
| **ADMIN** | ✅ Full | ✅ Full | System administration |
| **USER** | ❌ None | ✅ Scoped | Customer chatbots |
| **DEVELOPER** | ✅ Limited | ✅ Full | Development |
| **GUEST** | ❌ None | ✅ Read-only | Public help desk |

### 2. API Scopes

- **PUBLIC**: Unauthenticated read access
- **READ**: Authenticated read (GET)
- **WRITE**: Create/update (POST, PUT, PATCH)
- **DELETE**: Delete operations
- **ADMIN**: Administrative operations

### 3. Rate Limiting

```python
endpoint = APIEndpoint(
    name="wordpress",
    rate_limit=60,  # 60 requests per minute
)
```

### 4. Audit Logging

All API calls are logged:
- Timestamp
- User role
- API called
- Method (GET/POST/DELETE)
- Path
- Success/failure
- Error details

### 5. Permission Enforcement

Three layers of security:
1. **Chatbot role** (ADMIN/USER/GUEST)
2. **API controller** (scopes, rate limits)
3. **External API** (WordPress/WooCommerce roles)

## WordPress Roles

| Role | Read | Write | Publish | Manage Users |
|------|------|-------|---------|--------------|
| Subscriber | ✅ | ❌ | ❌ | ❌ |
| Contributor | ✅ | ✅ Drafts | ❌ | ❌ |
| Author | ✅ | ✅ | ✅ Own | ❌ |
| Editor | ✅ | ✅ | ✅ All | ❌ |
| Administrator | ✅ | ✅ | ✅ | ✅ |

## WooCommerce Roles

| Role | View Products | View Orders | Manage Products | Manage Orders |
|------|---------------|-------------|-----------------|---------------|
| Customer | ✅ | ✅ Own only | ❌ | ❌ |
| Shop Manager | ✅ | ✅ All | ✅ | ✅ |
| Administrator | ✅ | ✅ All | ✅ | ✅ |

## Testing

Run all tests:

```bash
cd /Users/joe/brain/agentic-brain
source .venv_agentic/bin/activate
python -m pytest tests/security/test_api_access.py -v
```

**Result**: 21 tests, all passing ✅

Run example demo:

```bash
python examples/api_security_demo.py
```

## Benefits

1. **Security**: Customers can't access what they shouldn't
2. **Simplicity**: One security model (the API's own roles)
3. **Auditability**: All access is logged
4. **Rate Limiting**: Prevents abuse
5. **Isolation**: Each customer only sees their data
6. **No Machine Access**: Can't harm the system

## Future Enhancements

- [ ] OAuth 2.0 flow support
- [ ] Webhook integrations
- [ ] API response caching
- [ ] Multi-tenancy support
- [ ] Usage analytics
- [ ] Cost tracking

## Migration

### Before (Insecure)
```python
# Direct database access ❌
cursor.execute("SELECT * FROM wp_posts WHERE ...")
```

### After (Secure)
```python
# WordPress REST API ✅
posts = await wp_client.list_posts(status="publish")
```

## Key Takeaways

✅ USER/CUSTOMER = **API-ONLY** (no shell, no files, no YOLO)  
✅ API keys are scoped to minimum required access  
✅ WordPress/WooCommerce roles enforce permissions  
✅ All access is logged for auditing  
✅ Rate limiting prevents abuse  
✅ Customers can only see their own data  

---

**Remember**: The chatbot doesn't bypass API permissions - it operates within the API's role system.
