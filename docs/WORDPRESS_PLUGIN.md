# Agentic Brain WordPress Plugin

Agentic Brain is a WordPress and WooCommerce integration for connecting a site to an Agentic Brain backend. The plugin provides a floating AI chat widget, AI-powered product search, content and product sync for RAG, admin tools, and a small REST API surface for the front end and site administrators.

**Plugin path:** `plugins/wordpress/agentic-brain/`

## Architecture at a glance

| File | Responsibility |
| --- | --- |
| `agentic-brain.php` | Bootstrap, activation defaults, cron scheduling, WooCommerce checks, singleton startup |
| `includes/class-agentic-brain.php` | Main orchestrator for shortcodes, blocks, REST routes, and shared services |
| `includes/class-admin.php` | Top-level admin menu, dashboard, sync submenu, analytics placeholder |
| `includes/class-admin-settings.php` | Settings registration, sanitisation, asset loading, settings page wiring |
| `includes/class-rest-api.php` | Lightweight plugin status endpoint |
| `includes/class-api-client.php` | HTTP client for the Agentic Brain backend |
| `includes/class-product-sync.php` | WooCommerce product sync, delete handling, batch/full sync |
| `includes/class-hooks.php` | Order/customer event forwarding to the backend |

## Installation

### Requirements

- WordPress 6.0+
- PHP 8.0+
- WooCommerce is optional, but required for product sync and AI product search
- A reachable Agentic Brain backend URL

### Install from source

1. Copy `plugins/wordpress/agentic-brain/` into `wp-content/plugins/agentic-brain/`.
2. In WordPress admin, open **Plugins**.
3. Activate **Agentic Brain AI Chatbot**.
4. Open **Settings → Agentic Brain** or **Agentic Brain → Settings**.
5. Enter the backend URL in **API Endpoint URL**.
6. Optionally add a bearer token in **API Key**.
7. Save changes.
8. Optionally click **Run Full Sync Now** to seed the backend with products, posts, and pages.

### What happens on activation

On activation the plugin:

- creates default options such as widget position and welcome message
- schedules a daily WP-Cron event on `agbrain_daily_sync`
- leaves WooCommerce optional; if WooCommerce is missing, the plugin still loads but product features stay inactive

## Configuration

The plugin stores its configuration in WordPress options using the `agbrain_*` prefix.

| Option | Default | Meaning |
| --- | --- | --- |
| `agbrain_api_url` | `''` | Base URL for the Agentic Brain backend |
| `agbrain_api_key` | `''` | Optional bearer token used on backend requests |
| `agbrain_widget_position` | `bottom-right` | Floating widget location: `bottom-right` or `bottom-left` |
| `agbrain_primary_color` | `#6C63FF` | Accent colour used by the front-end widget |
| `agbrain_enabled_on` | `all` | Where the floating widget renders: `all`, `products`, or `none` |
| `agbrain_woo_auto_sync` | `yes` | Whether WooCommerce product changes are pushed automatically |
| `agbrain_sync_posts` | `yes` | Whether posts and pages are synced into the knowledge base |
| `agbrain_welcome_message` | `Hi! How can I help you today?` | Greeting shown when the chat opens |
| `agbrain_last_sync` | unset | Timestamp of the latest full/content sync |
| `agbrain_last_product_sync` | unset | Timestamp of the latest product sync |

### Settings page sections

#### Connection

- **API Endpoint URL**: required for all backend communication. The plugin trims trailing slashes and appends its own endpoint paths.
- **API Key (optional)**: sent as `Authorization: Bearer <token>` when present.
- **Test Connection**: sends a POST request to the plugin endpoint `/wp-json/agentic-brain/v1/connection-test`, which then probes the backend health endpoints.

The client tests these backend URLs in order until one responds successfully:

- `/api/health`
- `/health`
- `/api/status`

#### Appearance

- **Widget Position**: controls the floating chat bubble location.
- **Primary Colour**: used to build CSS variables for the widget and action buttons.
- **Welcome Message**: localised into the chat UI and also used by the `[agentic_chat]` shortcode default.
- **Show Widget On**:
  - `all`: render in the footer on every page
  - `products`: render only on WooCommerce single-product pages
  - `none`: disable the floating widget completely; shortcodes and blocks still work

#### Content Sync

- **Auto-Sync Products**: when enabled, product create/update/delete events push changes immediately.
- **Sync Posts & Pages**: when enabled, published posts and pages are included in full sync and incremental save/delete sync.

### Sanitisation rules

`Agbrain_Admin_Settings::sanitize_field()` applies these rules:

- valid URLs are normalised with `esc_url_raw()`
- 6-digit hex colours are preserved
- everything else is stored with `sanitize_text_field()`

## REST API endpoints

The plugin exposes endpoints under the namespace `agentic-brain/v1`.

### Public endpoints

These use `permission_callback => __return_true`, so they can be called by the front end without authentication.

| Method | Route | Purpose | Input |
| --- | --- | --- | --- |
| `GET` | `/wp-json/agentic-brain/v1/status` | Returns plugin status for admin/dashboard/front-end checks | none |
| `POST` | `/wp-json/agentic-brain/v1/chat` | Proxies a chat message to the backend | `message`, optional `session_id`, optional `context` |
| `POST` | `/wp-json/agentic-brain/v1/search` | Proxies AI product search to the backend | `query`, optional `limit` |

#### `GET /status`

Returns:

```json
{
  "version": "1.0.0",
  "api_configured": true,
  "has_woocommerce": true,
  "site_url": "https://example.com",
  "last_sync": "2026-03-28 10:00:00"
}
```

#### `POST /chat`

Request body example:

```json
{
  "message": "Do you have waterproof hiking boots?",
  "session_id": "session-123",
  "context": {
    "campaign": "spring-sale"
  }
}
```

The plugin enriches the request with WordPress context such as:

- `source: wordpress`
- `site_url`
- `current_url`
- `locale`
- `user_type` (`guest`, `customer`, or `admin`)
- `current_product` details on WooCommerce product pages

Response handling notes:

- empty `message` returns HTTP `400`
- backend errors return HTTP `502`
- if the backend responds with `text` but not `reply`, the plugin maps it to `reply`
- product payloads are enriched with WooCommerce data such as permalink, price, image URL, stock, and AJAX add-to-cart support

#### `POST /search`

Request body example:

```json
{
  "query": "lightweight rain jacket",
  "limit": 6
}
```

Response handling notes:

- empty `query` returns HTTP `400`
- backend errors return HTTP `502`
- product results are normalised against live WooCommerce product data when possible

### Admin-only endpoints

These require a logged-in admin with `manage_options` capability.

| Method | Route | Purpose | Input |
| --- | --- | --- | --- |
| `POST` | `/wp-json/agentic-brain/v1/sync` | Triggers a full products + posts/pages sync | none |
| `POST` | `/wp-json/agentic-brain/v1/connection-test` | Tests backend connectivity with ad-hoc credentials | `api_url`, optional `api_key` |

Admin JavaScript calls these endpoints with the `X-WP-Nonce` header.

## Backend endpoints the plugin expects

The WordPress plugin is a client of the Agentic Brain service. It expects these backend routes to exist:

| Backend route | Used by |
| --- | --- |
| `/api/chat` | chat proxy |
| `/api/search` | AI product search |
| `/api/documents/ingest` | product and content sync |
| `/api/documents/delete` | delete/unpublish sync |
| `/api/events/order-status` | WooCommerce order status events |
| `/api/events/customer-registered` | customer registration events |
| `/api/health`, `/health`, `/api/status` | connection tests |

Headers automatically sent by `Agbrain_API_Client`:

- `Accept: application/json`
- `Content-Type: application/json`
- `X-Source: wordpress-plugin`
- `X-Site-Url: <home_url()>`
- `Authorization: Bearer <token>` when an API key is configured

## Product sync

`Agbrain_Product_Sync` handles WooCommerce catalogue ingestion.

### Automatic product sync

When WooCommerce is available, the plugin registers these listeners:

- `save_post_product`
- `woocommerce_update_product`
- `woocommerce_new_product`
- `before_delete_post`

Automatic sync flow:

1. A product is created or updated.
2. The plugin checks `agbrain_woo_auto_sync`.
3. Revisions and autosaves are ignored.
4. Published products are converted into backend documents.
5. The document is posted to `/api/documents/ingest` with `type=product`.
6. On success, `_agbrain_last_synced` post meta and `agbrain_last_product_sync` are updated.
7. If a product becomes unpublished or is deleted, `/api/documents/delete` is called.

### Full sync

`Agbrain_Product_Sync::full_sync()`:

- batches products in groups of 50
- fetches published products with `wc_get_products()`
- converts each product into a document payload
- sends each batch with `sync_mode=full`
- updates `agbrain_last_product_sync` when complete

### Product document shape

Each product document includes:

- `source_id`
- `type`
- `title`
- `content`
- `short_desc`
- `url` / `permalink`
- `image_url`
- `price`, `regular_price`, `sale_price`, `currency`
- stock status fields
- `sku`
- `categories`, `tags`
- flattened attribute labels/values
- `updated_at`
- `add_to_cart_url`
- `cart_supported`

### Content sync alongside product sync

Although product sync is WooCommerce-specific, the plugin also runs content sync through `Agbrain_RAG_Sync`:

- published `post` and `page` records are ingested
- save/delete events are mirrored to the backend when `agbrain_sync_posts=yes`
- the scheduled daily job `agbrain_daily_sync` triggers a full product + content sync

## Hooks & filters

### Custom hook exposed by the plugin

| Type | Hook | Purpose |
| --- | --- | --- |
| action | `agbrain_daily_sync` | Daily scheduled full sync for products and content |

Example:

```php
add_action('agbrain_daily_sync', function () {
    // Run your own nightly job alongside Agentic Brain.
});
```

### Core WordPress/WooCommerce hooks the plugin uses

These are useful when you need to coordinate custom behaviour with the plugin.

| Hook | Registered in | Purpose |
| --- | --- | --- |
| `plugins_loaded` | `agentic-brain.php` | loads translations and boots the singleton |
| `admin_notices` | `agentic-brain.php` | shows WooCommerce warning notice |
| `before_woocommerce_init` | `agentic-brain.php` | declares HPOS compatibility |
| `rest_api_init` | `class-agentic-brain.php`, `class-rest-api.php` | registers plugin REST routes |
| `init` | `class-agentic-brain.php` | registers Gutenberg blocks |
| `admin_menu` | `class-admin.php`, `class-admin-settings.php` | adds top-level and settings menus |
| `admin_init` | `class-admin-settings.php` | registers settings |
| `admin_enqueue_scripts` | `class-admin-settings.php` | loads settings JS/CSS |
| `wp_enqueue_scripts` | `class-chatbot.php` | loads front-end widget assets |
| `wp_footer` | `class-chatbot.php` | renders the floating widget |
| `save_post_product` | `class-product-sync.php` | incremental product sync |
| `woocommerce_update_product` | `class-product-sync.php` | incremental product sync |
| `woocommerce_new_product` | `class-product-sync.php` | incremental product sync |
| `before_delete_post` | `class-product-sync.php`, `class-rag-sync.php` | removes deleted products/posts/pages from the backend |
| `save_post` | `class-rag-sync.php` | incremental post/page sync |
| `woocommerce_order_status_changed` | `class-hooks.php` | sends order status events to the backend |
| `user_register` | `class-hooks.php` | sends customer registration events |

### Filters

The plugin currently defines one plugin-specific filter registration:

| Filter | Purpose |
| --- | --- |
| `plugin_action_links_` . `AGBRAIN_PLUGIN_BASENAME` | Adds a **Settings** link on the Plugins screen |

As of this version, the plugin does **not** expose custom `apply_filters()` extension points for payload mutation. If you need custom payload shaping, the safest approach is to wrap or replace sync behaviour in your own plugin using WordPress hooks and the public classes documented below.

## Admin interface

The plugin provides both a dedicated top-level menu and a conventional Settings entry.

### Admin pages

| Page | Slug | What it shows |
| --- | --- | --- |
| **Agentic Brain** | `agentic-brain-dashboard` | high-level connection status, WooCommerce status, last sync |
| **Agentic Brain → Settings** | `agentic-brain` | all connection, appearance, and sync settings |
| **Agentic Brain → Sync** | `agentic-brain-sync` | reuses the settings page markup as a dedicated sync submenu |
| **Agentic Brain → Analytics** | `agentic-brain-analytics` | placeholder analytics message for future backend metrics |
| **Settings → Agentic Brain** | `agentic-brain` | duplicate entry for discoverability |

### Screenshot descriptions

Use these descriptions if you later add actual screenshots to the repo or WordPress.org assets.

1. **Dashboard overview**: a WordPress admin page with a brain icon heading, followed by a short description and a simple status list showing whether the API is configured, whether WooCommerce is active, and the last sync time.
2. **Settings page**: a clean settings form with Connection, Appearance, and Content Sync sections, a primary Save Changes button, a secondary Test Connection button, and a coloured status banner above the form.
3. **Sync tools**: the lower half of the settings page showing “Last full sync”, “Last product sync”, and a “Run Full Sync Now” button with live status messaging.
4. **Shortcodes table**: a two-column table documenting `[agentic_chat]` and `[agentic_product_search]` for content editors.
5. **Analytics page**: a placeholder admin screen that states future support for chat volume, intents, and conversion analytics once a backend is connected.

> Note: admin CSS/JavaScript is currently enqueued on the `settings_page_agentic-brain` hook, so the most complete interactive experience is on **Settings → Agentic Brain**. The dedicated **Sync** submenu reuses the same template but may not receive the same scripted enhancements unless the enqueue logic is broadened in a future update.

### Front-end UI notes

The chat widget is designed with accessibility in mind:

- the launcher has `aria-expanded` and `aria-controls`
- the chat window uses `role="dialog"`
- messages are announced via a live region (`role="log"`, `aria-live="polite"`)
- the input has a screen-reader label
- search results use `role="region"` and `aria-live="polite"`

## Troubleshooting

### WooCommerce warning appears in admin

**Symptom:** A yellow admin notice says WooCommerce is not active.

**Cause:** The plugin is running without WooCommerce.

**Fix:** Install and activate WooCommerce if you want product sync and AI product search. The plugin can still be used for chat plus post/page sync without it.

### Test Connection fails

**Symptom:** The connection banner shows a failure or the button reports a network error.

**Checks:**

1. Confirm `agbrain_api_url` starts with `http://` or `https://`.
2. Confirm the backend is reachable from the WordPress server.
3. Verify the API key if your backend requires bearer auth.
4. Confirm one of `/api/health`, `/health`, or `/api/status` exists.

### Chat/search returns HTTP 502

**Symptom:** Front-end requests fail even though the plugin is active.

**Cause:** The WordPress plugin reached the backend, but the backend returned an error status.

**Fix:** Inspect backend logs for `/api/chat`, `/api/search`, `/api/documents/ingest`, or `/api/documents/delete` failures.

### Widget does not appear

**Checks:**

- `Show Widget On` may be set to `Disabled (shortcode only)`
- `Show Widget On` may be `WooCommerce Product Pages Only` and you are not on a product page
- theme templates might omit `wp_footer()`; the floating widget depends on it

### Product sync is not running

**Checks:**

- WooCommerce must be active
- `Auto-Sync Products` must be enabled
- only published products are ingested
- autosaves and revisions are ignored by design
- deleted/unpublished products are removed from the backend instead of ingested

### Posts and pages are not syncing

**Checks:**

- `Sync Posts & Pages` must be enabled
- only published `post` and `page` types are included
- custom post types are not synced by default

### Daily sync never fires

**Cause:** WP-Cron depends on site traffic unless a real cron job triggers `wp-cron.php`.

**Fix:**

- make sure the plugin was activated successfully so `agbrain_daily_sync` was scheduled
- consider configuring a server cron that calls WordPress cron regularly
- trigger a manual sync from admin as a fallback

### Admin sync button does nothing

**Checks:**

- ensure you are logged in as a user with `manage_options`
- confirm REST API requests are not blocked by a security plugin
- check browser console/network tab for failures on `/wp-json/agentic-brain/v1/sync`
- if you opened **Agentic Brain → Sync**, retry from **Settings → Agentic Brain** because the current admin asset enqueue condition targets the settings-page hook

## Developer guide

### Lifecycle summary

1. `agentic-brain.php` loads all classes and registers activation/deactivation hooks.
2. On `plugins_loaded`, translations load and `Agentic_Brain::instance()` boots the plugin.
3. The singleton creates:
   - `Agbrain_API_Client`
   - `Agbrain_Product_Sync`
   - `Agbrain_RAG_Sync`
   - `Agentic_Brain_Admin` (admin only)
   - `Agbrain_Chatbot`
   - `Agentic_Brain_Hooks`
   - `Agentic_Brain_REST_API`
4. Shortcodes, blocks, and REST routes are then registered.

### Reusing the API client

You can talk to the backend directly from another plugin:

```php
$client = new Agbrain_API_Client();
$result = $client->post('/api/chat', [
    'message' => 'Hello from a custom plugin',
    'context' => ['source' => 'custom-extension'],
]);
```

Or use the orchestrator helper:

```php
$response = Agentic_Brain::call_backend('/api/events/custom', [
    'event' => 'something-happened',
]);
```

### Ingesting custom content

If you want to sync a custom document type, follow the same document shape used by product/content sync:

```php
$client = new Agbrain_API_Client();
$client->ingest_documents([
    [
        'source_id' => 'faq-42',
        'type' => 'faq',
        'title' => 'Returns policy',
        'content' => 'Items can be returned within 30 days.',
        'url' => home_url('/returns-policy/'),
        'updated_at' => current_time('c'),
    ],
], 'content', [
    'sync_mode' => 'custom',
]);
```

### Adding your own scheduled work

The plugin schedules `agbrain_daily_sync`. You can attach follow-up work to the same event, or schedule your own event separately.

```php
add_action('agbrain_daily_sync', function () {
    error_log('Agentic Brain sync completed; now running extension job.');
});
```

### Extending the admin experience

Because the settings screen is a conventional WordPress options page, you can:

- add adjacent admin pages on `admin_menu`
- register your own settings on `admin_init`
- add UI that calls the plugin REST endpoints using `X-WP-Nonce`

### Adding your own REST routes

The plugin already uses the `agentic-brain/v1` namespace. To avoid collisions, register custom routes under your own namespace or use a distinct path.

```php
add_action('rest_api_init', function () {
    register_rest_route('my-plugin/v1', '/agentic-brain-report', [
        'methods' => 'GET',
        'callback' => function () {
            return ['ok' => true];
        },
        'permission_callback' => '__return_true',
    ]);
});
```

### Shortcodes and blocks

Available shortcodes:

- `[agentic_chat]`
- `[agentic_product_search]`

Supported shortcode attributes:

| Shortcode | Attributes |
| --- | --- |
| `[agentic_chat]` | `welcome`, `height` |
| `[agentic_product_search]` | `placeholder`, `limit` |

Registered dynamic blocks:

- `agentic-brain/chat`
- `agentic-brain/product-search`

### Current extension limits

As shipped, the plugin has a clean but intentionally small public surface:

- no custom filter hooks for altering request/response payloads
- posts/pages only for content sync; custom post types need custom code
- analytics page is a placeholder and does not yet fetch metrics
- `class-rest-api.php` only exposes `/status`; chat/search/sync/connection-test live in the main orchestrator

If you want richer extensibility, the next logical enhancements would be custom filters around sync payloads, block registration metadata, and admin dashboard metrics providers.
