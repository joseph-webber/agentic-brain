# 🌐 WordPress / WooCommerce / Divi Integration

> **AI-powered experiences for the world's most popular CMS**

WordPress powers **43% of all websites**. WooCommerce powers **28% of all e-commerce**. Divi is the **#1 WordPress theme**. Agentic Brain integrates with all three.

---

## 🌟 Why WordPress + Agentic Brain?

| Platform | Market Share | What We Enable |
|----------|--------------|----------------|
| **WordPress** | 43% of web | AI content creation, SEO, chatbots |
| **WooCommerce** | 28% of e-commerce | Product recommendations, order support |
| **Divi** | 2M+ sites | Visual AI widgets, no-code integration |

---

## Overview

| Platform | Integration Type | Complexity | Status |
|----------|-----------------|------------|--------|
| **WordPress** | REST API | ⭐ Easy | ✅ Supported |
| **WooCommerce** | REST API + Webhooks | ⭐⭐ Medium | ✅ Supported |
| **Divi Theme** | JS Embed + Visual Builder | ⭐⭐ Medium | ✅ Supported |
| **Elementor** | Widget + Shortcode | ⭐⭐ Medium | ✅ Supported |
| **Gutenberg** | Block | ⭐ Easy | ✅ Supported |

## Quick Start

### 0. Headless CMS + RAG (Recommended)

Agentic Brain ships with two complementary WordPress integrations:

- **Headless CMS client (async)**: `agentic_brain.commerce.wordpress_cms.HeadlessCMS`
  - REST API v2 read/write
  - Gutenberg block parsing
  - ACF field preservation (when exposed via a plugin)
  - GraphQL queries via **WPGraphQL** (`/graphql`)
- **RAG loader (sync)**: `agentic_brain.rag.loaders.wordpress.WordPressLoader`
  - Loads posts/pages/custom post types into `LoadedDocument`
  - Preserves metadata + relationships
  - Incremental sync via `load_since()`

#### RAG ingestion example

```python
from datetime import datetime, timezone

from agentic_brain.rag.loaders.wordpress import WordPressLoader
from agentic_brain.rag.store import InMemoryDocumentStore

loader = WordPressLoader(
    site_url="https://example.com",
    username="wp-user",
    application_password="xxxx xxxx xxxx xxxx",
)

docs = loader.load_folder("posts")
store = InMemoryDocumentStore()

for doc in docs:
    store.add(doc.content, metadata=doc.metadata, doc_id=f"wordpress:{doc.source_id}")

# Incremental sync (modified since)
recent = loader.load_since(datetime.now(timezone.utc), endpoints=("posts", "pages"))
```

#### HeadlessCMS sync example

```python
from datetime import datetime, timezone

from agentic_brain.commerce.wordpress import WPAuth
from agentic_brain.commerce.wordpress_cms import HeadlessCMS
from agentic_brain.rag.store import InMemoryDocumentStore

store = InMemoryDocumentStore()

async def sync_wordpress():
    auth = WPAuth(base_url="https://example.com", username="wp-user")
    cms = HeadlessCMS(auth)
    await cms.sync_to_document_store(store, endpoints=("posts", "pages"), since=datetime(2026, 1, 1, tzinfo=timezone.utc))
```

### 1. WordPress REST API

WordPress 5.6+ includes Application Passwords for API authentication:

```python
from agentic_brain import Agent
import aiohttp
import base64

class WordPressAgent:
    def __init__(self, site_url: str, username: str, app_password: str):
        self.site_url = site_url.rstrip('/')
        self.auth = base64.b64encode(
            f"{username}:{app_password}".encode()
        ).decode()
        self.agent = Agent(name="wordpress-assistant")
    
    async def get_posts(self, per_page: int = 10) -> list:
        """Fetch recent posts from WordPress."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.site_url}/wp-json/wp/v2/posts",
                params={"per_page": per_page},
                headers={"Authorization": f"Basic {self.auth}"}
            ) as response:
                return await response.json()
    
    async def create_post(self, title: str, content: str, status: str = "draft") -> dict:
        """Create a new WordPress post."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.site_url}/wp-json/wp/v2/posts",
                json={"title": title, "content": content, "status": status},
                headers={"Authorization": f"Basic {self.auth}"}
            ) as response:
                return await response.json()
```

### 2. WooCommerce Integration

WooCommerce uses OAuth 1.0a or Consumer Key/Secret authentication:

```python
from agentic_brain import Agent
from agentic_brain.business import Order, Product, Customer
import aiohttp
import hashlib
import hmac
import time
import urllib.parse

class WooCommerceAgent:
    def __init__(self, site_url: str, consumer_key: str, consumer_secret: str):
        self.site_url = site_url.rstrip('/')
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.agent = Agent(name="woocommerce-assistant")
    
    def _get_auth_params(self) -> dict:
        """Generate OAuth 1.0a parameters."""
        return {
            "consumer_key": self.consumer_key,
            "consumer_secret": self.consumer_secret,
        }
    
    async def get_orders(self, status: str = "any", per_page: int = 20) -> list[Order]:
        """Fetch orders from WooCommerce."""
        params = self._get_auth_params()
        params.update({"status": status, "per_page": per_page})
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.site_url}/wp-json/wc/v3/orders",
                params=params
            ) as response:
                data = await response.json()
                return [Order.from_dict(o) for o in data]
    
    async def get_products(self, category: str = None, per_page: int = 20) -> list[Product]:
        """Fetch products from WooCommerce."""
        params = self._get_auth_params()
        params["per_page"] = per_page
        if category:
            params["category"] = category
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.site_url}/wp-json/wc/v3/products",
                params=params
            ) as response:
                data = await response.json()
                return [Product.from_dict(p) for p in data]
    
    async def get_order_status(self, order_id: int) -> dict:
        """Get status of a specific order."""
        params = self._get_auth_params()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.site_url}/wp-json/wc/v3/orders/{order_id}",
                params=params
            ) as response:
                return await response.json()
```

### 3. Divi Theme Integration

Embed the Agentic Brain chat widget in any Divi site:

#### Method A: JavaScript Embed (Easiest)

Add to Divi → Theme Options → Integration → Add code to `<head>`:

```html
<script src="https://your-agentic-brain-server.com/chat-widget.js"></script>
<script>
  AgenticBrain.init({
    apiEndpoint: 'https://your-agentic-brain-server.com',
    chatbotId: 'your-bot-id',
    position: 'bottom-right',
    matchTheme: true  // Auto-matches Divi colors
  });
</script>
```

#### Method B: Shortcode

Use the Divi Code Module with shortcode:

```
[agentic_chat position="floating" height="500px"]
```

#### Method C: WordPress Plugin

Install the Agentic Brain WordPress plugin for full Theme Customizer integration:

1. Download `agentic-brain-wordpress.zip`
2. WordPress Admin → Plugins → Add New → Upload
3. Activate plugin
4. Appearance → Customize → Agentic Brain
5. Enter API endpoint and chatbot ID
6. Enable chat widget

## API Endpoints Reference

### WordPress REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/wp-json/wp/v2/posts` | GET | List posts |
| `/wp-json/wp/v2/posts` | POST | Create post |
| `/wp-json/wp/v2/posts/{id}` | PUT | Update post |
| `/wp-json/wp/v2/pages` | GET | List pages |
| `/wp-json/wp/v2/media` | GET/POST | Media library |
| `/wp-json/wp/v2/categories` | GET | List categories |
| `/wp-json/wp/v2/tags` | GET | List tags |
| `/wp-json/wp/v2/users` | GET | List users |
| `/wp-json/wp/v2/search` | GET | Search content |

### WooCommerce REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/wp-json/wc/v3/orders` | GET | List orders |
| `/wp-json/wc/v3/orders/{id}` | GET | Single order |
| `/wp-json/wc/v3/products` | GET | List products |
| `/wp-json/wc/v3/products/{id}` | GET | Single product |
| `/wp-json/wc/v3/customers` | GET | List customers |
| `/wp-json/wc/v3/customers/{id}` | GET | Single customer |
| `/wp-json/wc/v3/reports/sales` | GET | Sales reports |
| `/wp-json/wc/v3/reports/top_sellers` | GET | Top sellers |
| `/wp-json/wc-analytics/reports/revenue` | GET | Revenue analytics |

## Authentication Methods

### 1. Application Passwords (Recommended for WordPress)

WordPress 5.6+ built-in feature:
1. Users → Your Profile → Application Passwords
2. Create new password
3. Use Basic Auth: `Authorization: Basic base64(username:app_password)`

### 2. WooCommerce API Keys

1. WooCommerce → Settings → Advanced → REST API
2. Add Key → Set permissions (Read/Write)
3. Use Consumer Key + Secret in requests

### 3. JWT Authentication (Optional)

For SPAs requiring token-based auth:
1. Install JWT Auth plugin
2. POST to `/wp-json/jwt-auth/v1/token`
3. Use Bearer token in subsequent requests

## Chatbot Use Cases

### Customer Service Bot (ROI: $50-100K/year)

Handles 70-80% of common inquiries:
- Order status checks
- Product availability
- Return/refund requests
- Shipping information

```python
# Example: Customer service chatbot
from agentic_brain import Agent

agent = Agent(
    name="customer-service",
    system_prompt="""You are a helpful customer service assistant.
    You can check order status, find products, and answer questions.
    Always be polite and helpful.""",
    tools=[
        get_order_status,
        search_products,
        get_shipping_info,
        create_support_ticket
    ]
)
```

### Inventory Manager Bot (ROI: $20-50K/year)

Prevents stockouts and automates reordering:
- Low stock alerts
- Reorder recommendations
- Supplier notifications

### Sales Analytics Bot (ROI: $10-30K/year)

Real-time business insights:
- Daily/weekly/monthly reports
- Top product analysis
- Customer segmentation

## Security Best Practices

1. **Always use HTTPS** - Never send credentials over HTTP
2. **Limit API permissions** - Use read-only when possible
3. **Rotate credentials** - Change API keys periodically
4. **Rate limiting** - WooCommerce: ~120 requests/minute
5. **Webhook verification** - Validate webhook signatures
6. **Input sanitization** - Never trust user input

## Example: Full WooCommerce Chatbot

See `examples/20_wordpress_assistant.py` for a complete implementation.

```python
# Quick example
import asyncio
from woocommerce_agent import WooCommerceAgent

async def main():
    agent = WooCommerceAgent(
        site_url="https://your-store.com",
        consumer_key="ck_xxxxx",
        consumer_secret="cs_xxxxx"
    )
    
    # Handle customer query
    response = await agent.chat(
        "What's the status of order #1234?"
    )
    print(response)

asyncio.run(main())
```

---

## 🎨 Divi Theme Deep Integration

Divi is the world's most popular WordPress theme with 2M+ active sites. Agentic Brain provides native integration with Divi's Visual Builder.

### Divi Visual Builder Module

Add AI chat directly in the Visual Builder:

1. **Install Plugin**: Upload `agentic-brain-divi.zip`
2. **Open Visual Builder**: Edit any page
3. **Add Module**: Search for "Agentic Brain Chat"
4. **Configure**: Set API endpoint, style, position

```
┌─────────────────────────────────────────┐
│  Divi Visual Builder                     │
├─────────────────────────────────────────┤
│  ┌───────────────────────────────────┐  │
│  │     🧠 Agentic Brain Chat         │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │ API Endpoint: [_________]   │  │  │
│  │  │ Chatbot ID:   [_________]   │  │  │
│  │  │ Position:     [Floating ▼]  │  │  │
│  │  │ ☑ Match Divi Colors         │  │  │
│  │  │ ☑ Enable Voice              │  │  │
│  │  │ Theme:        [Dark    ▼]   │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Divi Module Options

| Option | Values | Description |
|--------|--------|-------------|
| **Position** | `floating`, `inline`, `fullpage` | Widget placement |
| **Match Colors** | `true/false` | Auto-match Divi color palette |
| **Theme** | `light`, `dark`, `auto` | Chat widget theme |
| **Voice** | `true/false` | Enable voice input/output |
| **Height** | `300px-800px` | Widget height (inline only) |
| **Welcome** | Custom text | Initial greeting message |

### Divi Shortcodes

Use in any Divi Text or Code module:

```html
<!-- Basic Chat Widget -->
[agentic_chat]

<!-- Floating Widget -->
[agentic_chat position="floating" theme="dark"]

<!-- Inline Widget with Custom Height -->
[agentic_chat position="inline" height="500px" voice="true"]

<!-- Product Recommendations (WooCommerce) -->
[agentic_recommendations limit="4" style="grid"]

<!-- AI Search Box -->
[agentic_search placeholder="Ask anything about our products..."]

<!-- AI FAQ -->
[agentic_faq category="shipping" max="10"]
```

### Divi Theme Customizer Integration

Full integration with WordPress Customizer:

1. **Appearance → Customize → Agentic Brain**
2. Configure global settings:
   - Default API endpoint
   - Default chatbot ID
   - Global position preference
   - Color overrides
   - Voice settings

### Divi Child Theme CSS

Style the chat widget to match your Divi theme:

```css
/* Match Divi's primary color */
.agentic-chat-container {
    --ab-primary: var(--divi-primary-color, #2ea3f2);
    --ab-text: var(--divi-text-color, #333);
    --ab-bg: var(--divi-bg-color, #fff);
}

/* Divi-style buttons */
.agentic-chat-send-btn {
    background: var(--ab-primary);
    border-radius: 3px;
    font-family: inherit;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* Match Divi's animations */
.agentic-chat-container {
    transition: all 0.3s ease-in-out;
}

/* Floating button style */
.agentic-chat-trigger {
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    border-radius: 50%;
}
```

### Divi Builder Layouts

Pre-built Divi layouts with AI integration:

**1. Customer Support Page**
```
[Full Width Header]
     ↓
[2 Column: FAQ + Chat Widget]
     ↓
[Contact Form with AI Pre-fill]
```

**2. Product Page Enhancement**
```
[Product Gallery]
     ↓
[AI Product Q&A Widget]
     ↓
[AI-Powered Related Products]
```

**3. Landing Page Chatbot**
```
[Hero Section]
     ↓
[Inline Chat: "Tell me what you're looking for"]
     ↓
[AI-Recommended Content Grid]
```

---

## 🛒 WooCommerce AI Features

### AI Product Recommendations

```python
from agentic_brain.commerce import ProductRecommender

recommender = ProductRecommender(
    woocommerce_url="https://store.com",
    consumer_key="ck_xxx",
    consumer_secret="cs_xxx"
)

# Get recommendations for user
recs = await recommender.get_recommendations(
    user_id=123,
    context="browsing_category:electronics",
    limit=4
)

# Render as shortcode
# [agentic_recommendations user_id="123" limit="4"]
```

### AI-Powered Search

```html
<!-- Replace WooCommerce search -->
<form class="agentic-search-form">
    <input type="text" 
           placeholder="Describe what you're looking for..."
           data-agentic-search="true"
           data-store-url="https://store.com">
</form>

<script>
AgenticBrain.search.init({
    endpoint: 'https://your-api.com',
    woocommerce: true,
    semantic: true,  // AI understanding, not just keywords
    showImages: true
});
</script>
```

### Order Tracking Chatbot

```python
@agent.tool
async def track_order(order_id: str) -> dict:
    """Look up order status for customer."""
    order = await woo.get_order(order_id)
    return {
        "status": order.status,
        "tracking": order.tracking_number,
        "eta": order.estimated_delivery,
        "items": [item.name for item in order.items]
    }

# Customer: "Where's my order #1234?"
# Agent: "Your order #1234 is currently 'shipped' and should arrive by Friday."
```

---

## 🤖 AI Content Generation

### WordPress Auto-Blogging

```python
from agentic_brain import Agent
from agentic_brain.content import ContentGenerator

generator = ContentGenerator(
    wordpress_url="https://blog.com",
    username="admin",
    app_password="xxxx"
)

# Generate and publish blog post
post = await generator.create_post(
    topic="10 Tips for Better SEO in 2024",
    style="informative",
    length="1500 words",
    include_images=True,
    seo_keywords=["SEO tips", "search optimization"],
    status="draft"  # Review before publishing
)
```

### SEO Meta Generation

```python
from agentic_brain.seo import MetaGenerator

meta = MetaGenerator()

# Generate SEO meta for existing content
for post in await wp.get_posts(status="publish"):
    if not post.yoast_meta:
        seo = await meta.generate(
            title=post.title,
            content=post.content,
            target_keyword=post.primary_keyword
        )
        await wp.update_post(post.id, {
            "yoast_title": seo.title,
            "yoast_description": seo.description,
            "yoast_keywords": seo.keywords
        })
```

---

## 💰 ROI Calculator

| Use Case | Setup Time | Annual Savings |
|----------|------------|----------------|
| **Customer Service Bot** | 2 hours | $50-100K (reduces support tickets 70%) |
| **Product Recommendations** | 1 hour | $20-50K (increases AOV 15-25%) |
| **Inventory Alerts** | 30 min | $10-30K (prevents stockouts) |
| **AI Content Generation** | 1 hour | $20-40K (reduces writing costs) |
| **Order Tracking Bot** | 1 hour | $15-25K (reduces "where's my order" calls) |

**Total Potential ROI: $115-245K/year** for a mid-size WooCommerce store.

---

## 📱 Mobile & PWA Support

The chat widget is fully responsive and PWA-ready:

```javascript
// Service worker caching for offline chat
AgenticBrain.init({
    pwa: true,
    offlineMessage: "You're offline. Messages will be sent when you reconnect.",
    cacheResponses: true
});
```

---

## 🔒 Security Best Practices

1. **Always use HTTPS** - Never send credentials over HTTP
2. **Limit API permissions** - Use read-only when possible
3. **Rotate credentials** - Change API keys periodically
4. **Rate limiting** - WooCommerce: ~120 requests/minute
5. **Webhook verification** - Validate webhook signatures
6. **Input sanitization** - Never trust user input
7. **CSP Headers** - Allow chat widget domain

```php
// wp-config.php - Security headers
header("Content-Security-Policy: script-src 'self' https://your-agentic-brain.com");
```

---

## 🚀 Production Deployment

### Performance Tips

```php
// functions.php - Only load on pages that need it
function load_agentic_brain() {
    if (is_product() || is_checkout() || is_page('support')) {
        wp_enqueue_script('agentic-brain', 'https://cdn.agentic-brain.com/widget.js');
    }
}
add_action('wp_enqueue_scripts', 'load_agentic_brain');
```

### CDN Configuration

```nginx
# Nginx - Cache static assets
location /wp-content/plugins/agentic-brain/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

## 📚 Resources

- [WordPress REST API Handbook](https://developer.wordpress.org/rest-api/)
- [WooCommerce REST API Docs](https://woocommerce.github.io/woocommerce-rest-api-docs/)
- [Divi Developer Documentation](https://www.elegantthemes.com/documentation/developers/)
- [Divi Module Development](https://www.elegantthemes.com/documentation/developers/divi-module/)
- [Agentic Brain Examples](../../examples/)

---

## 🆚 Comparison: WordPress AI Solutions

| Feature | Agentic Brain | ChatGPT Plugin | Tidio | Intercom |
|---------|---------------|----------------|-------|----------|
| **WooCommerce Native** | ✅ Full | ⚠️ Limited | ⚠️ Basic | ⚠️ Basic |
| **Divi Integration** | ✅ Visual Builder | ❌ None | ❌ None | ❌ None |
| **Self-Hosted** | ✅ Yes | ❌ Cloud only | ❌ Cloud | ❌ Cloud |
| **GraphRAG** | ✅ Neo4j | ❌ None | ❌ None | ❌ None |
| **Voice** | ✅ 180+ | ❌ None | ❌ None | ⚠️ Limited |
| **Offline** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Price** | Open Source | $20/mo+ | $29/mo+ | $74/mo+ |

---

## Support

For WordPress integration support:
- GitHub Issues: [agentic-brain/issues](https://github.com/agentic-brain-project/agentic-brain/issues)
- Documentation: [docs/integrations/](.)

---

*WordPress + WooCommerce + Divi + Agentic Brain = AI-powered web experiences for everyone.*
