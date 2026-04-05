# Context-Aware GUEST Role Implementation

## Overview

The GUEST security role has been redesigned to be **context-aware** - it mirrors what guest/unauthenticated users can actually do on the connected platform, rather than being hardcoded to "no API access".

**Key Insight**: GUEST should have access to API endpoints that the platform allows for unauthenticated users. This is not a hardcoded restriction but a context-dependent mapping.

## Philosophy

```
GUEST ≠ "No Access"
GUEST = "Public/Unauthenticated Access" (context-dependent)
```

Different platforms allow different guest capabilities:
- **WooCommerce**: Guests can browse products, add to cart, checkout
- **WordPress**: Guests can read public posts, view comments
- **Custom APIs**: Platform-specific public endpoints

## Implementation

### 1. Role Permissions (Updated)

**File**: `src/agentic_brain/security/roles.py`

Added three new permission flags to `RolePermissions`:

```python
@dataclass(frozen=True, slots=True)
class RolePermissions:
    # ... existing fields ...
    
    # API access - granular control based on authentication level
    can_access_guest_apis: bool          # Public/unauthenticated endpoints
    can_access_authenticated_apis: bool  # User-level endpoints
    can_access_admin_apis: bool          # Admin endpoints
```

### 2. GUEST Role Configuration

**Before** (incorrect):
```python
SecurityRole.GUEST: RolePermissions(
    can_access_apis=False,  # ❌ Wrong - too restrictive
    allowed_api_scopes=frozenset(),
    allowed_apis=frozenset(),
)
```

**After** (correct):
```python
SecurityRole.GUEST: RolePermissions(
    # Context-aware guest API access
    can_access_apis=True,                    # ✅ Guests CAN access APIs
    can_access_guest_apis=True,              # ✅ Public endpoints
    can_access_authenticated_apis=False,     # ❌ No user-level endpoints
    can_access_admin_apis=False,             # ❌ No admin endpoints
    allowed_api_scopes=frozenset({"read"}),  # Read-only for safety
    allowed_apis=frozenset({"woocommerce_store", "wordpress_public"}),
)
```

### 3. Role Permission Summary

| Role        | Guest APIs | Authenticated APIs | Admin APIs | Machine Access |
|-------------|------------|-------------------|------------|----------------|
| GUEST       | ✅ Yes      | ❌ No              | ❌ No       | ❌ No           |
| USER        | ✅ Yes      | ✅ Yes             | ❌ No       | ❌ No           |
| SAFE_ADMIN  | ✅ Yes      | ✅ Yes             | ❌ No       | ✅ Yes          |
| FULL_ADMIN  | ✅ Yes      | ✅ Yes             | ✅ Yes      | ✅ Yes          |

## WooCommerce Guest Capabilities

### What Guests CAN Do

**File**: `src/agentic_brain/integrations/woocommerce_guest.py`

#### 1. Browse Products (Public Access)
```python
# List products
products = await guest_api.browse_products(
    per_page=20,
    search="laptop",
    category=123,
    min_price=500,
    max_price=2000,
)

# Get product details
product = await guest_api.get_product(product_id=456)

# List categories
categories = await guest_api.list_categories()
```

#### 2. Shopping Cart (Session-Based, No Auth)
```python
# View cart
cart = await guest_api.get_cart()

# Add to cart
cart = await guest_api.add_to_cart(
    product_id=456,
    quantity=2,
)

# Update quantity
cart = await guest_api.update_cart_item(
    cart_item_key="abc123",
    quantity=3,
)

# Remove from cart
cart = await guest_api.remove_from_cart(cart_item_key="abc123")

# Apply coupon
cart = await guest_api.apply_coupon(coupon_code="SAVE10")
```

#### 3. Shipping
```python
# Get shipping rates
rates = await guest_api.get_shipping_rates()

# Select shipping method
cart = await guest_api.select_shipping_rate(
    package_id="0",
    rate_id="flat_rate:1",
)
```

#### 4. Guest Checkout (No Account Required)
```python
from agentic_brain.integrations import GuestCheckoutInfo

checkout_info = GuestCheckoutInfo(
    billing_first_name="John",
    billing_last_name="Doe",
    billing_email="john@example.com",
    billing_phone="+61400000000",
    billing_address_1="123 Main St",
    billing_city="Adelaide",
    billing_state="SA",
    billing_postcode="5000",
    billing_country="AU",
)

order = await guest_api.checkout_as_guest(
    checkout_info=checkout_info,
    payment_method="stripe",
    create_account=False,  # Guest checkout, no account
)
```

### What Guests CANNOT Do

❌ **View orders** (requires account/authentication)  
❌ **Access customer profile** (requires authentication)  
❌ **View order history** (requires authentication)  
❌ **Manage account** (requires authentication)  
❌ **Access admin endpoints** (requires admin role)

## WordPress Guest Capabilities

### What Guests CAN Do (Planned)

```python
# Read public posts
posts = await guest_api.list_public_posts()

# Read public pages
page = await guest_api.get_public_page(page_id=123)

# View comments
comments = await guest_api.get_comments(post_id=456)

# Submit comment (if allowed by settings)
comment = await guest_api.submit_comment(
    post_id=456,
    content="Great article!",
    author_name="John Doe",
    author_email="john@example.com",
)

# Search content
results = await guest_api.search_content(query="wordpress")
```

## API Endpoint Mapping

### WooCommerce Store API (Guest)

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/wp-json/wc/store/products` | GET | List products | ❌ No |
| `/wp-json/wc/store/products/{id}` | GET | Get product | ❌ No |
| `/wp-json/wc/store/cart` | GET | View cart | ❌ No (session) |
| `/wp-json/wc/store/cart/add-item` | POST | Add to cart | ❌ No (session) |
| `/wp-json/wc/store/cart/update-item` | POST | Update quantity | ❌ No (session) |
| `/wp-json/wc/store/cart/remove-item` | POST | Remove from cart | ❌ No (session) |
| `/wp-json/wc/store/cart/apply-coupon` | POST | Apply coupon | ❌ No (session) |
| `/wp-json/wc/store/checkout` | GET | Get checkout form | ❌ No (session) |
| `/wp-json/wc/store/checkout` | POST | Process order | ❌ No (session) |
| `/wp-json/wc/store/cart/shipping-rates` | GET | Get shipping rates | ❌ No (session) |

### WooCommerce REST API v3 (Authenticated)

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/wp-json/wc/v3/orders` | GET | List orders | ✅ Yes (Customer+) |
| `/wp-json/wc/v3/orders/{id}` | GET | Get order | ✅ Yes (Customer - own orders) |
| `/wp-json/wc/v3/customers/{id}` | GET | Get customer | ✅ Yes (Customer - own profile) |
| `/wp-json/wc/v3/products` | POST | Create product | ✅ Yes (Shop Manager+) |
| `/wp-json/wc/v3/products/{id}` | PUT | Update product | ✅ Yes (Shop Manager+) |
| `/wp-json/wc/v3/reports/sales` | GET | Sales reports | ✅ Yes (Shop Manager+) |

## Usage Examples

### Example 1: Guest Shopping Flow

```python
from agentic_brain.integrations import WooCommerceGuestAPI, GuestCheckoutInfo
from agentic_brain.security import SecurityRole, create_api_controller

# Create API controller with GUEST role
api_controller = create_api_controller(SecurityRole.GUEST)

# Create guest API client
guest_api = WooCommerceGuestAPI(
    store_url="https://example.com",
    api_controller=api_controller,
)

# 1. Browse products
laptops = await guest_api.browse_products(
    search="laptop",
    category=15,  # Electronics
    min_price=500,
)

# 2. Add to cart
cart = await guest_api.add_to_cart(
    product_id=laptops[0]["id"],
    quantity=1,
)

# 3. Get shipping rates
rates = await guest_api.get_shipping_rates()

# 4. Select shipping
cart = await guest_api.select_shipping_rate(
    package_id="0",
    rate_id=rates[0]["rates"][0]["rate_id"],
)

# 5. Apply coupon
cart = await guest_api.apply_coupon("WELCOME10")

# 6. Checkout as guest
checkout_info = GuestCheckoutInfo(
    billing_first_name="Jane",
    billing_last_name="Smith",
    billing_email="jane@example.com",
    billing_phone="+61400000000",
    billing_address_1="456 Oak Ave",
    billing_city="Melbourne",
    billing_state="VIC",
    billing_postcode="3000",
    billing_country="AU",
)

order = await guest_api.checkout_as_guest(
    checkout_info=checkout_info,
    payment_method="stripe",
)

print(f"Order created: {order['order_id']}")
```

### Example 2: Context-Aware Role Detection

```python
from agentic_brain.security import get_permissions, SecurityRole

# Check what each role can do
guest_perms = get_permissions(SecurityRole.GUEST)
user_perms = get_permissions(SecurityRole.USER)

print("GUEST capabilities:")
print(f"  Can access guest APIs: {guest_perms.can_access_guest_apis}")  # True
print(f"  Can access authenticated APIs: {guest_perms.can_access_authenticated_apis}")  # False
print(f"  Can access admin APIs: {guest_perms.can_access_admin_apis}")  # False
print(f"  Can access filesystem: {guest_perms.can_access_filesystem}")  # False

print("\nUSER capabilities:")
print(f"  Can access guest APIs: {user_perms.can_access_guest_apis}")  # True
print(f"  Can access authenticated APIs: {user_perms.can_access_authenticated_apis}")  # True
print(f"  Can access admin APIs: {user_perms.can_access_admin_apis}")  # False
print(f"  Can access filesystem: {user_perms.can_access_filesystem}")  # False
```

## Security Model

### Session-Based Cart (No Auth)

WooCommerce Store API uses **session-based carts** stored in browser cookies:

1. **First request**: Server generates session token
2. **Subsequent requests**: Session token in cookies identifies cart
3. **No account required**: Cart persists in session
4. **Guest checkout**: Order created without account (email receipt)

### Rate Limiting

All roles (including GUEST) are rate-limited:

| Role | Rate Limit |
|------|------------|
| GUEST | 10 req/min |
| USER | 60 req/min |
| SAFE_ADMIN | 1000 req/min |
| FULL_ADMIN | Unlimited |

### Security Boundaries

**GUEST role enforces**:
- ✅ Can access public/guest endpoints
- ✅ Read-only operations preferred
- ❌ NO authenticated user endpoints
- ❌ NO admin endpoints
- ❌ NO filesystem access
- ❌ NO code execution
- ❌ NO configuration access

**Platform enforces**:
- Cart isolation (session-based)
- Order visibility (authenticated users only)
- Customer data privacy (authentication required)
- Admin operations (admin role required)

## Testing

### Test File Structure

```
tests/
├── security/
│   └── test_guest_role.py         # GUEST role permissions tests
├── integrations/
│   ├── test_woocommerce_guest.py  # WooCommerce Guest API tests
│   └── test_wordpress_guest.py    # WordPress Guest API tests (planned)
```

### Example Tests

```python
# tests/security/test_guest_role.py

def test_guest_can_access_guest_apis():
    perms = get_permissions(SecurityRole.GUEST)
    assert perms.can_access_guest_apis is True
    assert perms.can_access_authenticated_apis is False
    assert perms.can_access_admin_apis is False

def test_guest_cannot_access_filesystem():
    perms = get_permissions(SecurityRole.GUEST)
    assert perms.can_access_filesystem is False
    assert perms.can_write_files is False
    assert perms.can_execute_shell is False

# tests/integrations/test_woocommerce_guest.py

async def test_guest_browse_products():
    api = create_guest_api_client(
        store_url="https://demo.woocommerce.com",
        api_controller=create_api_controller(SecurityRole.GUEST),
    )
    
    products = await api.browse_products(per_page=5)
    assert len(products) > 0
    assert "id" in products[0]
    assert "name" in products[0]

async def test_guest_add_to_cart():
    api = create_guest_api_client(...)
    
    cart = await api.add_to_cart(product_id=123, quantity=2)
    assert "items" in cart
    assert len(cart["items"]) == 1
```

## Migration Guide

### Updating Existing Code

**Before**:
```python
# Old assumption: GUEST = no API access
if role == SecurityRole.GUEST:
    return "No API access for guests"
```

**After**:
```python
# New: Check granular permissions
perms = get_permissions(role)

if perms.can_access_guest_apis:
    # Guest can access public endpoints
    return await guest_api.browse_products()
elif perms.can_access_authenticated_apis:
    # User can access authenticated endpoints
    return await user_api.list_orders()
else:
    return "No API access"
```

## Future Enhancements

### Planned Additions

1. **WordPress Guest API** (`wordpress_guest.py`)
   - Public posts/pages
   - Comment submission
   - Content search

2. **Custom Platform Support**
   - Generic guest endpoint registry
   - Platform detection
   - Auto-discovery of public endpoints

3. **Guest Session Management**
   - Session token persistence
   - Cart recovery
   - Anonymous user tracking (privacy-compliant)

4. **Analytics**
   - Guest browsing behavior
   - Conversion tracking (guest → customer)
   - Cart abandonment detection

## References

- **WooCommerce Store API**: https://github.com/woocommerce/woocommerce/tree/trunk/plugins/woocommerce/src/StoreApi
- **WordPress REST API**: https://developer.wordpress.org/rest-api/
- **Security Roles**: `src/agentic_brain/security/roles.py`
- **WooCommerce Integration**: `src/agentic_brain/integrations/woocommerce.py`
- **WooCommerce Guest**: `src/agentic_brain/integrations/woocommerce_guest.py`

---

**Last Updated**: 2026-04-02  
**Status**: ✅ Implemented  
**Author**: Security Team  
**Key Insight**: GUEST = Public/Unauthenticated Access (Context-Dependent)
