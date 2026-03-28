# Commerce API Integration

Comprehensive documentation for the WooCommerce and WordPress API wrappers in `agentic_brain/commerce`. All examples are real Python calls against the wrapper methods.

> **Example conventions**
> - `woo` is an instance of `WooCommerceAPI`
> - `wp` is an instance of `WPAPIClient`
> - Examples use `await` and assume they run inside `async def main()` (or `asyncio.run(main())`).
> - WooCommerce also supports synchronous calls via the `.sync` proxy (shown where helpful).

---

## Authentication

### WooCommerce (REST v3)
The WooCommerce client uses HTTP Basic Auth with a **Consumer Key** and **Consumer Secret**.

```python
from agentic_brain.commerce.woo_api import WooCommerceAPI

woo = WooCommerceAPI(
    base_url="https://store.example",
    consumer_key="ck_123",
    consumer_secret="cs_456",
)
```

**Config notes**
- Base URL should be your store root (no trailing slash).
- API root becomes: `https://store.example/wp-json/wc/v3`.
- Async-first; use `woo.products.sync.list()` for synchronous usage.

### WordPress (REST v2)
The WordPress integration supports multiple authentication methods via `WordPressConfig`:

- **Application Password (Basic Auth)**: `username` + `application_password`
- **JWT**: `jwt_token` or `jwt_token_endpoint` + `username` + `user_password`
- **OAuth2 Client Credentials**: `oauth_client_id` + `oauth_client_secret` + `oauth_token_url`

```python
from agentic_brain.commerce.wordpress import WordPressConfig
from agentic_brain.commerce.wp_api.client import WPAPIClient

config = WordPressConfig(
    base_url="https://cms.example",
    username="editor",
    application_password="app_pass_123",
)
wp = WPAPIClient(config)
```

**JWT exchange example**
```python
config = WordPressConfig(
    base_url="https://cms.example",
    username="editor",
    user_password="account_password",
    jwt_token_endpoint="https://cms.example/wp-json/jwt-auth/v1/token",
)
wp = WPAPIClient(config)
```

**OAuth2 example**
```python
config = WordPressConfig(
    base_url="https://cms.example",
    oauth_client_id="client_id",
    oauth_client_secret="client_secret",
    oauth_token_url="https://cms.example/oauth/token",
    oauth_scope="read write",
)
wp = WPAPIClient(config)
```

---

## WooCommerce API

### Core Client Utilities
```python
# Raw request
payload = await woo.client.request("GET", "products")

# Paginated list
products = await woo.client.paginate("products", per_page=50)

# Batch operation
batch_result = await woo.client.batch(
    "products/batch",
    {"create": [{"name": "Notebook"}]},
)
```

### Products
```python
# List, retrieve, create, update, delete
products = await woo.products.list(status="publish")
product = await woo.products.retrieve(123)
created = await woo.products.create({"name": "Notebook", "regular_price": "19.99"})
updated = await woo.products.update(123, {"name": "Notebook Pro"})
deleted = await woo.products.delete(123, force=True)

# Batch
batch = await woo.products.batch(
    create=[{"name": "Sticker", "regular_price": "2.50"}],
    update=[{"id": 123, "name": "Notebook Plus"}],
    delete=[{"id": 456}],
)

# Variations
variations = await woo.products.list_variations(123)
variation = await woo.products.create_variation(123, {"regular_price": "24.99"})
variation = await woo.products.update_variation(123, 22, {"regular_price": "21.99"})
removed = await woo.products.delete_variation(123, 22, force=True)
variation_batch = await woo.products.batch_variations(
    123,
    create=[{"regular_price": "29.99"}],
    update=[{"id": 22, "regular_price": "19.99"}],
    delete=[{"id": 33}],
)

# Attributes & terms
attributes = await woo.products.list_attributes()
attribute = await woo.products.create_attribute({"name": "Size"})
attribute = await woo.products.update_attribute(10, {"name": "Size (Updated)"})
removed = await woo.products.delete_attribute(10)

terms = await woo.products.list_attribute_terms(10)
term = await woo.products.create_attribute_term(10, {"name": "Large"})
term = await woo.products.update_attribute_term(10, 55, {"name": "XL"})
removed = await woo.products.delete_attribute_term(10, 55)

# Categories
categories = await woo.products.list_categories()
category = await woo.products.create_category({"name": "Stationery"})
category = await woo.products.update_category(12, {"name": "Stationery & Gifts"})
removed = await woo.products.delete_category(12, force=True)
category_batch = await woo.products.batch_categories(
    create=[{"name": "Accessories"}],
    update=[{"id": 12, "name": "Office"}],
    delete=[{"id": 44}],
)

# Tags
tags = await woo.products.list_tags()
tag = await woo.products.create_tag({"name": "Premium"})
tag = await woo.products.update_tag(9, {"name": "Premium+"})
removed = await woo.products.delete_tag(9, force=True)
tag_batch = await woo.products.batch_tags(
    create=[{"name": "Limited"}],
    update=[{"id": 9, "name": "Limited 2026"}],
    delete=[{"id": 77}],
)

# Reviews
reviews = await woo.products.list_reviews()
review = await woo.products.create_review({"product_id": 123, "review": "Great!"})
review = await woo.products.update_review(88, {"review": "Updated review"})
removed = await woo.products.delete_review(88, force=True)
review_batch = await woo.products.batch_reviews(
    create=[{"product_id": 123, "review": "Love it"}],
    update=[{"id": 88, "review": "Even better"}],
    delete=[{"id": 90}],
)
```

### Orders
```python
orders = await woo.orders.list(status="processing")
order = await woo.orders.retrieve(1001)
created = await woo.orders.create({"customer_id": 44, "line_items": [{"product_id": 123, "quantity": 1}]})
updated = await woo.orders.update(1001, {"status": "completed"})
removed = await woo.orders.delete(1001, force=True)

order_batch = await woo.orders.batch(
    create=[{"customer_id": 44, "line_items": [{"product_id": 123, "quantity": 1}]}],
    update=[{"id": 1001, "status": "on-hold"}],
    delete=[{"id": 1002}],
)

# Notes
notes = await woo.orders.list_notes(1001)
note = await woo.orders.create_note(1001, {"note": "Packed", "customer_note": False})
removed = await woo.orders.delete_note(1001, 9)

# Refunds
refunds = await woo.orders.list_refunds(1001)
refund = await woo.orders.create_refund(1001, {"amount": "5.00", "reason": "Damaged"})
refund = await woo.orders.retrieve_refund(1001, 22)
removed = await woo.orders.delete_refund(1001, 22, force=True)
```

### Customers
```python
customers = await woo.customers.list(role="customer")
customer = await woo.customers.retrieve(44)
created = await woo.customers.create({"email": "user@example.com", "first_name": "Ava"})
updated = await woo.customers.update(44, {"last_name": "Lee"})
removed = await woo.customers.delete(44, force=True)

customer_batch = await woo.customers.batch(
    create=[{"email": "new@example.com"}],
    update=[{"id": 44, "first_name": "Ava"}],
    delete=[{"id": 45}],
)

downloads = await woo.customers.list_downloads(44)
```

### Coupons & Discounts
```python
coupons = await woo.coupons.list()
coupon = await woo.coupons.retrieve(5)
created = await woo.coupons.create({"code": "SAVE10", "amount": "10", "discount_type": "percent"})
updated = await woo.coupons.update(5, {"amount": "12"})
removed = await woo.coupons.delete(5, force=True)

coupon_batch = await woo.coupons.batch(
    create=[{"code": "SAVE5", "amount": "5"}],
    update=[{"id": 5, "amount": "15"}],
    delete=[{"id": 6}],
)
```

### Shipping Zones & Methods
```python
zones = await woo.shipping.list_zones()
zone = await woo.shipping.retrieve_zone(1)
created = await woo.shipping.create_zone({"name": "Domestic"})
updated = await woo.shipping.update_zone(1, {"name": "Australia"})
removed = await woo.shipping.delete_zone(1)

locations = await woo.shipping.list_zone_locations(1)
updated_locations = await woo.shipping.update_zone_locations(
    1,
    [{"code": "AU", "type": "country"}],
)

methods = await woo.shipping.list_zone_methods(1)
method = await woo.shipping.create_zone_method(1, {"method_id": "flat_rate"})
method = await woo.shipping.retrieve_zone_method(1, 22)
method = await woo.shipping.update_zone_method(1, 22, {"settings": {"cost": "10"}})
removed = await woo.shipping.delete_zone_method(1, 22)

all_methods = await woo.shipping.list_global_methods()
```

### Tax Rates
```python
classes = await woo.taxes.list_classes()
created_class = await woo.taxes.create_class({"name": "GST"})
removed_class = await woo.taxes.delete_class("gst")

rates = await woo.taxes.list_rates(country="AU")
rate = await woo.taxes.retrieve_rate(11)
created_rate = await woo.taxes.create_rate({"country": "AU", "rate": "10.0000", "name": "GST"})
updated_rate = await woo.taxes.update_rate(11, {"rate": "9.5000"})
removed_rate = await woo.taxes.delete_rate(11)
```

### Reports & Analytics
```python
sales = await woo.reports.sales(date_min="2024-01-01", date_max="2024-12-31")
top = await woo.reports.top_sellers()
customers_report = await woo.reports.customers()
order_totals = await woo.reports.orders_totals()
coupon_totals = await woo.reports.coupons_totals()
tax_report = await woo.reports.taxes()
tax_totals = await woo.reports.taxes_totals()
stock_report = await woo.reports.stock()
downloads_report = await woo.reports.downloads()
```

### Settings
```python
groups = await woo.settings.list_groups()
group = await woo.settings.retrieve_group("general")
options = await woo.settings.list_options("general")
updated = await woo.settings.update_option("general", "woocommerce_store_address", {"value": "123 Main"})

batch_update = await woo.settings.batch_update(
    "general",
    update=[{"id": "woocommerce_store_city", "value": "Adelaide"}],
)
```

### Payment Gateways
```python
gateways = await woo.payment_gateways.list()
gateway = await woo.payment_gateways.retrieve("cod")
updated = await woo.payment_gateways.update("cod", {"enabled": True})
```

### System Status
```python
status = await woo.system.status()
tools = await woo.system.tools()
ran = await woo.system.run_tool("clear_transients")
```

### Data (Countries, Currencies)
```python
countries = await woo.data.countries()
country = await woo.data.country("AU")
states = await woo.data.country_states("AU")
currencies = await woo.data.currencies()
continents = await woo.data.continents()
```

### Webhooks
```python
webhooks = await woo.webhooks.list()
webhook = await woo.webhooks.retrieve(7)
created = await woo.webhooks.create({
    "name": "Order created",
    "topic": "order.created",
    "delivery_url": "https://hooks.example/woo/orders",
    "status": "active",
})
updated = await woo.webhooks.update(7, {"status": "paused"})
removed = await woo.webhooks.delete(7, force=True)

webhook_batch = await woo.webhooks.batch(
    create=[{"name": "Refunds", "topic": "order.refunded", "delivery_url": "https://hooks.example/woo/refunds"}],
    update=[{"id": 7, "status": "active"}],
    delete=[{"id": 8}],
)

deliveries = await woo.webhooks.list_deliveries(7)
delivery = await woo.webhooks.retrieve_delivery(7, 55)
redelivered = await woo.webhooks.redeliver(7, 55)
```

---

## WordPress API

### Core Client Utilities
```python
# Build namespace URLs
acf_endpoint = wp.acf_url("posts/123")
custom_url = wp.build_namespace_url("wp/v2", "posts")

# Raw requests
payload = await wp.request("GET", "posts")
raw = await wp.request_raw("GET", "posts")

# Convenience HTTP helpers
posts = await wp.get("posts")
created = await wp.post("posts", json_body={"title": "Hello"})
updated = await wp.put("posts/123", json_body={"title": "Updated"})
patched = await wp.patch("posts/123", json_body={"status": "draft"})
removed = await wp.delete("posts/123", params={"force": "true"})

# GraphQL (WPGraphQL plugin required)
result = await wp.graphql_query("query { posts { nodes { title } } }")
```

### Posts & Pages
```python
# Posts
posts = await wp.posts.list(status="publish")
post = await wp.posts.get(123)
created = await wp.posts.create({"title": "Hello", "content": "World"})
updated = await wp.posts.update(123, {"title": "Updated"})
removed = await wp.posts.delete(123, force=True)

revisions = await wp.posts.list_revisions(123)
revision = await wp.posts.get_revision(123, 77)
removed_revision = await wp.posts.delete_revision(123, 77, force=True)

autosaves = await wp.posts.list_autosaves(123)
autosave = await wp.posts.get_autosave(123, 88)

meta = await wp.posts.update_meta(123, {"seo_title": "Hello"})
featured = await wp.posts.set_featured_media(123, 501)

# Pages
pages = await wp.pages.list(status="publish")
page = await wp.pages.get(55)
created = await wp.pages.create({"title": "About", "content": "Our story"})
updated = await wp.pages.update(55, {"title": "About Us"})
removed = await wp.pages.delete(55, force=True)

revisions = await wp.pages.list_revisions(55)
revision = await wp.pages.get_revision(55, 12)
removed_revision = await wp.pages.delete_revision(55, 12, force=True)

autosaves = await wp.pages.list_autosaves(55)
autosave = await wp.pages.get_autosave(55, 20)

meta = await wp.pages.update_meta(55, {"hero_title": "Welcome"})
featured = await wp.pages.set_featured_media(55, 501)
```

### Media
```python
media = await wp.media.list()
item = await wp.media.get(501)
uploaded = await wp.media.upload(
    file_name="hero.jpg",
    content=b"...bytes...",
    mime_type="image/jpeg",
    metadata={"title": "Hero Image"},
)
updated = await wp.media.update(501, {"title": "New Title"})
removed = await wp.media.delete(501, force=True)

sizes = await wp.media.get_sizes(501)
```

### Users & Authentication
```python
users = await wp.users.list()
user = await wp.users.get(10)
me = await wp.users.me()
created = await wp.users.create({"username": "ava", "email": "ava@example.com"})
updated = await wp.users.update(10, {"name": "Ava Lee"})
removed = await wp.users.delete(10, force=True, reassign=1)

roles = await wp.users.update_roles(10, ["editor"])
capabilities = await wp.users.update_capabilities(10, {"edit_posts": True})
```

### Comments
```python
comments = await wp.comments.list(status="approve")
comment = await wp.comments.get(200)
created = await wp.comments.create({"post": 123, "content": "Great post"})
updated = await wp.comments.update(200, {"content": "Updated comment"})
removed = await wp.comments.delete(200, force=True)

status = await wp.comments.update_status(200, "hold")
approved = await wp.comments.approve(200)
held = await wp.comments.hold(200)
spammed = await wp.comments.spam(200)
trashed = await wp.comments.trash(200)
untrashed = await wp.comments.untrash(200)
```

### Taxonomies (Categories, Tags, Custom Taxonomies)
```python
# Categories
categories = await wp.categories.list()
category = await wp.categories.get(5)
created = await wp.categories.create({"name": "News"})
updated = await wp.categories.update(5, {"name": "Latest News"})
removed = await wp.categories.delete(5, force=True)

# Tags
tags = await wp.tags.list()
tag = await wp.tags.get(9)
created = await wp.tags.create({"name": "Release"})
updated = await wp.tags.update(9, {"name": "Release 2026"})
removed = await wp.tags.delete(9, force=True)

# Custom taxonomies
all_taxonomies = await wp.taxonomies.list_taxonomies()
taxonomy = await wp.taxonomies.get_taxonomy("genre")
terms = await wp.taxonomies.list_terms("genre")
term = await wp.taxonomies.get_term("genre", 3)
created = await wp.taxonomies.create_term("genre", {"name": "Sci-Fi"})
updated = await wp.taxonomies.update_term("genre", 3, {"name": "Sci-Fi"})
removed = await wp.taxonomies.delete_term("genre", 3, force=True)
```

### Custom Post Types (and ACF)
```python
# Types
post_types = await wp.custom_post_types.list_types()
post_type = await wp.custom_post_types.get_type("product")

# Items
items = await wp.custom_post_types.list_items("product")
item = await wp.custom_post_types.get_item("product", 101)
created = await wp.custom_post_types.create_item("product", {"title": "Widget"})
updated = await wp.custom_post_types.update_item("product", 101, {"title": "Widget Pro"})
removed = await wp.custom_post_types.delete_item("product", 101, force=True)

# ACF fields (requires ACF REST API exposure)
acf = await wp.custom_post_types.get_acf_fields("product", 101)
acf = await wp.custom_post_types.update_acf_fields("product", 101, {"fields": {"spec": "New"}})
```

### Settings
```python
settings = await wp.settings.get_settings()
updated = await wp.settings.update_settings({"title": "New Site Title"})
```

### Blocks (Reusable Blocks, Patterns)
```python
block_types = await wp.blocks.list_block_types()
block_type = await wp.blocks.get_block_type("core/paragraph")

reusable = await wp.blocks.list_reusable_blocks()
block = await wp.blocks.get_reusable_block(12)
created = await wp.blocks.create_reusable_block({"title": "CTA", "content": "..."})
updated = await wp.blocks.update_reusable_block(12, {"title": "CTA Updated"})
removed = await wp.blocks.delete_reusable_block(12, force=True)

patterns = await wp.blocks.list_block_patterns()
pattern = await wp.blocks.get_block_pattern("core/hero")
pattern_categories = await wp.blocks.list_block_pattern_categories()

search_results = await wp.blocks.search_block_directory(search="gallery")
```

### Menus
```python
menus = await wp.menus.list_menus()
menu = await wp.menus.get_menu(5)
created = await wp.menus.create_menu({"name": "Main"})
updated = await wp.menus.update_menu(5, {"name": "Main Nav"})
removed = await wp.menus.delete_menu(5, force=True)

items = await wp.menus.list_menu_items(menu_id=5)
item = await wp.menus.get_menu_item(55)
created_item = await wp.menus.create_menu_item({"title": "Home", "url": "/"})
updated_item = await wp.menus.update_menu_item(55, {"title": "Homepage"})
removed_item = await wp.menus.delete_menu_item(55, force=True)

locations = await wp.menus.list_menu_locations()
```

### Search
```python
results = await wp.search.search("woocommerce", type="post")
```

### Plugins
```python
plugins = await wp.plugins.list()
plugin = await wp.plugins.get("woocommerce/woocommerce")
activated = await wp.plugins.activate("woocommerce/woocommerce")
deactivated = await wp.plugins.deactivate("woocommerce/woocommerce")
updated = await wp.plugins.update("woocommerce/woocommerce", {"status": "active"})
removed = await wp.plugins.delete("woocommerce/woocommerce", force=True)
```

### Themes
```python
themes = await wp.themes.list()
theme = await wp.themes.get("twentytwentysix")
activated = await wp.themes.activate("twentytwentysix")
active = await wp.themes.get_active()
```

---

## Error Handling

### WooCommerce
```python
from agentic_brain.commerce.woo_api import WooAPIError

try:
    product = await woo.products.retrieve(123)
except WooAPIError as exc:
    if exc.status == 404:
        print("Product not found")
    else:
        print(f"WooCommerce error: {exc.status} -> {exc.payload}")
```

### WordPress
```python
from agentic_brain.commerce.wordpress import WordPressAPIError

try:
    post = await wp.posts.get(123)
except WordPressAPIError as exc:
    if exc.status_code == 401:
        print("Auth failed; check credentials or token")
    else:
        print(f"WordPress error: {exc.status_code} -> {exc.payload}")
```

---

## Rate Limiting

### WordPress
The WordPress client has built-in rate limiting via `RateLimiter`. Configure limits in `WordPressConfig`:

```python
config = WordPressConfig(
    base_url="https://cms.example",
    username="editor",
    application_password="app_pass_123",
    rate_limit_per_minute=60,
    rate_limit_per_hour=2000,
    rate_limit_per_day=10000,
    cooldown_seconds=60,
)
wp = WPAPIClient(config)
```

The client automatically backs off on HTTP **429** responses.

### WooCommerce
WooCommerce requests raise `WooAPIError` for non-2xx responses. Implement backoff on **429**:

```python
import asyncio
from agentic_brain.commerce.woo_api import WooAPIError

async def safe_list():
    for attempt in range(3):
        try:
            return await woo.orders.list()
        except WooAPIError as exc:
            if exc.status != 429:
                raise
            await asyncio.sleep(2 * (attempt + 1))
```

---

## Webhooks (Real-Time Notifications)

### WooCommerce Webhooks
WooCommerce webhooks are fully supported via `WooCommerceAPI.webhooks`:

```python
created = await woo.webhooks.create({
    "name": "Order paid",
    "topic": "order.paid",
    "delivery_url": "https://hooks.example/woo/order-paid",
    "status": "active",
})

# Inspect delivery attempts
attempts = await woo.webhooks.list_deliveries(created["id"])
```

### WordPress Webhooks
WordPress does not expose native REST webhooks, so use a webhook plugin (e.g., WP Webhooks) or WPGraphQL subscriptions. The wrapper supports standard REST calls to any plugin endpoints via `wp.request`:

```python
payload = await wp.request(
    "POST",
    "wp-webhooks/v1/webhooks",
    json_body={"event": "post.updated", "target_url": "https://hooks.example/wp"},
)
```

---

## Synchronous Usage (WooCommerce)

```python
woo = WooCommerceAPI("https://store.example", "ck_123", "cs_456")
products = woo.products.sync.list(status="publish")
woo.close_sync()
```
