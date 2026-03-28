# Commerce Chatbot

The commerce chatbot stack in `src/agentic_brain/commerce/chatbot/` gives you a chat-first interface for WooCommerce stores and WordPress content. It combines storefront support, store admin workflows, content discovery, analytics, and embeddable widgets so the same system can answer customer questions, help staff manage the store, and surface business insights.

## Overview

The commerce chatbot can act as several focused bots:

- **WooCommerce Bot** for products, orders, returns, refunds, price updates, low-stock checks, recommendations, gift searches, and product comparisons.
- **WordPress Content Bot** for searching posts, pages, categories, tags, and optional WooCommerce products from a single chat prompt.
- **WordPress Content/Admin Bot** for creating draft posts, scheduling content, reviewing pending comments, and updating pages.
- **Analytics Bot** for turning raw WooCommerce orders and conversation logs into sales dashboards, top-product insights, conversion reporting, customer lifetime value, and RAG-friendly documents.
- **Embeddable chat surfaces** for WordPress, WooCommerce blocks, Elementor, and accessible front-end widgets.
- **Integration helpers** for session-aware app integration with Redis-backed context and optional RAG augmentation.

Out of the box, the main commerce chatbot supports different audiences via `CommerceUserType`:

- `admin` - store operations and management
- `customer` - account and order support
- `guest` - pre-purchase shopping help

## Natural Language Queries

Here are representative queries the commerce-aware chatbot stack can support.

| Query | Capability | Notes |
| --- | --- | --- |
| `What products do we have under $50?` | Budget / gift search | Supported by `WooCommerceChatbot` via budget-aware product filtering. |
| `Show me orders from last week` | Order and reporting query | Best handled by analytics/reporting integration using WooCommerce order data for time-based summaries. |
| `What's our best selling product?` | Sales analytics | Supported by `WooCommerceAnalytics.top_products_by_revenue()` and its RAG/dashboard outputs. |
| `Create a 20% coupon for summer` | Admin promotion workflow | Use a custom admin intent backed by the WooCommerce coupons API to add coupon creation via chat. |

Additional built-in examples from the current rule-based bots and tests include:

- `Show me today's sales`
- `What products are low on stock?`
- `Update product Blue Ocean Hoodie price to $99`
- `Where's my order #123?`
- `Show me my purchase history`
- `Recommend products like my last purchase`
- `Do you have this in blue?`
- `Help me find a gift under $50`
- `Compare "Blue Ocean Hoodie" and "Premium Travel Mug"`
- `What's your return policy?`
- `Find articles about cats`
- `What's new on the blog?`
- `list categories`
- `list tags`
- `Create a new draft post about test`
- `Schedule post for tomorrow`
- `Show me pending comments`
- `Update page About with <p>Hi</p>`

The WordPress chat features are demonstrated in `tests/test_wp_chat.py`, and WooCommerce flows are covered in `tests/test_woo_chatbot.py` and `tests/test_chatbot_advanced.py`.

## WordPress Content Bot

`WPContentBot` is a read-oriented assistant for WordPress and optional WooCommerce catalog discovery.

### What it does

- Searches WordPress **posts** by topic
- Searches WordPress **pages** when enabled
- Optionally searches WooCommerce **products** alongside posts/pages
- Shows **latest blog posts**
- Lists **categories** and **tags**
- Browses content by **category** or **tag**

### Typical usage

It is a good fit for:

- help centres
- blog assistants
- content-heavy stores
- headless WordPress front ends
- hybrid blog + store experiences

### Tested capabilities

From `tests/test_wp_chat.py`:

- `Find articles about cats` returns matching posts and matching products
- `What's new on the blog?` returns recent published posts
- `list categories` returns category summaries
- `list tags` returns tag summaries

## WooCommerce Bot

`WooCommerceChatbot` is the main commerce conversation engine. It combines rule-based intent detection with store data and returns a structured `ChatbotReply` containing:

- `message` - natural-language answer
- `cards` - product/order cards for UI rendering
- `actions` - follow-up UI actions when needed
- `metadata` - structured details for APIs, logs, or dashboards

### Built-in admin flows

- show today's sales
- find low-stock products
- process refunds
- update product prices

### Built-in customer flows

- track an order
- show purchase history
- recommend products based on context or last purchase
- start a return/refund conversation

### Built-in guest flows

- check product availability
- answer return-policy questions
- suggest gifts under a budget
- compare products side by side

### Supporting helpers

The commerce chatbot package also includes helpers you can compose into richer flows:

- `ProductAdvisor` for comparisons, availability messages, size recommendations, and alternatives
- `OrderSupport` for return eligibility, modification checks, shipping updates, and ETA estimation
- `CartAssistant` for cart totals, coupon application, and recovery suggestions
- `ChatbotPersonalization` for personas, purchase-history analysis, browsing behaviour, recommendations, and dynamic pricing suggestions
- `ChatbotAIFeatures` for sentiment, urgency, language detection, translation, and handoff summaries
- `UnifiedInbox` plus channel adapters for WhatsApp, SMS, Instagram DM, and Facebook Messenger

## Analytics Bot

There is no single monolithic `AnalyticsBot` class; instead, the analytics capability is built from two complementary pieces.

### 1. Store analytics via `WooCommerceAnalytics`

Use this when you want analytics derived from WooCommerce orders/products.

It supports:

- sales reports by day, week, or month
- top products by revenue or quantity
- customer lifetime value
- inventory alerts
- order funnel and conversion rates
- dashboard-friendly JSON structures
- RAG-friendly documents for question answering

This is the layer that enables questions like:

- `What's our best selling product?`
- `What were our top selling products last month?`
- `Which customers have the highest lifetime value?`
- `Show me low-stock items`

### 2. Conversation analytics via `ChatbotAnalyticsDashboard`

Use this when you want insight into chatbot performance itself.

It computes:

- total, resolved, and escalated conversations
- average messages per conversation
- first-response time
- common question topics
- conversion rate and attributed revenue
- customer satisfaction and sentiment mix
- peak support hours

This is useful for prompts such as:

- `What are customers asking about most?`
- `How many conversations escalated this week?`
- `What's our conversion rate from chat?`

## Integration

You can use the commerce chatbot in your own app at several levels.

### Direct class usage

Use the individual bots directly if you already control request routing:

- `WooCommerceChatbot` for store conversations
- `WPContentBot` for content discovery
- `WPAdminBot` for authenticated admin actions
- `WooCommerceAnalytics` and `ChatbotAnalyticsDashboard` for analytics

### Session-aware integration

`ChatbotIntegrator` wraps `WooCommerceChatbot` with:

- Redis-backed session persistence
- context reconstruction with `CommerceContext`
- a hook point for RAG-backed retrieval
- a single `process_message()` entry point for app integration

### Front-end embedding

The package includes accessible rendering helpers and generated WordPress plugin assets:

- `render_chat_widget_html()`
- `render_wordpress_shortcode()`
- `render_woocommerce_block()`
- `generate_wp_widget_plugin()`
- `generate_wp_hooks_plugin()`

These are designed for keyboard accessibility and screen-reader compatibility, with ARIA labels, focus states, and live regions covered in tests.

## Customization

The chatbot stack is intentionally modular, so adding new capabilities is straightforward.

### Add a new commerce intent

To support a new admin or customer command:

1. Extend `CommerceIntent` in `intents.py`
2. Add keywords and entity extraction rules in `CommerceIntentDetector`
3. Implement a handler in `WooCommerceChatbot`
4. Connect the handler to the intent dispatch map
5. Add tests for both detection and response formatting

This is the recommended path for commands like:

- `Create a 20% coupon for summer`
- `Pause all out-of-stock ads`
- `List orders from last week`

### Add new data-backed workflows

You can wire the chatbot to:

- WooCommerce coupons, customers, reports, and settings APIs
- WordPress posts, pages, comments, and taxonomies
- RAG indices for semantic commerce search
- custom CRM, ERP, or shipping systems

### Tune behaviour for your business

You can customize:

- low-stock threshold
- policy text via `policy_provider`
- currency defaults
- result counts for WordPress bots
- widget colours, labels, and greeting text
- personalization and pricing heuristics
- analytics dashboards and RAG documents

## Code Examples

### 1. Customer support with `WooCommerceChatbot`

```python
from agentic_brain.commerce.chatbot import (
    CommerceContext,
    CommerceUserType,
    WooCommerceChatbot,
)

chatbot = WooCommerceChatbot(woo_agent, store_name="Agentic Outfitters")
context = CommerceContext(user_type=CommerceUserType.CUSTOMER, customer_id=99)

reply = await chatbot.handle_message(
    "Where's my order #123?",
    user_type=CommerceUserType.CUSTOMER,
    context=context,
)

print(reply.message)
print(reply.cards)
```

### 2. WordPress content search via chat

```python
from agentic_brain.commerce.chatbot import WPContentBot, WPContentBotConfig

bot = WPContentBot(
    wp_client,
    woo=woo_agent,
    config=WPContentBotConfig(max_results=3),
)

response = await bot.handle("Find articles about cats")
print(response)
```

### 3. WordPress admin actions via chat

```python
from agentic_brain.commerce.chatbot import WPAdminBot, WPAdminBotConfig

bot = WPAdminBot(admin_api, config=WPAdminBotConfig(default_schedule_hour=9))

created = await bot.handle("Create a new draft post about summer sale", session_id="editor-1")
print(created)

scheduled = await bot.handle("Schedule post for tomorrow", session_id="editor-1")
print(scheduled)
```

### 4. Store analytics for conversational answers

```python
from datetime import UTC, datetime
from agentic_brain.commerce.analytics import WooCommerceAnalytics

analytics = WooCommerceAnalytics(api=woo_api, default_currency="USD")
start = datetime(2026, 2, 1, tzinfo=UTC)
end = datetime(2026, 2, 3, tzinfo=UTC)

top_products = analytics.top_products_by_revenue(start, end, limit=5)
for product in top_products:
    print(product.name, product.revenue)

sales = analytics.daily_sales(start, end)
dashboard = analytics.format_sales_dashboard(sales)
print(dashboard["cards"])
```

### 5. Chatbot performance analytics

```python
from agentic_brain.commerce.chatbot import ChatbotAnalyticsDashboard

dashboard = ChatbotAnalyticsDashboard()
snapshot = dashboard.build_dashboard(conversations)

print(snapshot["conversation_metrics"])
print(snapshot["common_questions"])
print(snapshot["conversion_tracking"])
```

### 6. Accessible storefront widget

```python
from agentic_brain.commerce.chatbot import ChatWidgetConfig, render_chat_widget_html

config = ChatWidgetConfig(
    api_endpoint="/api/chatbot",
    store_name="Agentic Outfitters",
)
html = render_chat_widget_html(config)
```

### 7. WordPress plugin generation

```python
from agentic_brain.commerce.chatbot import (
    WordPressChatWidgetConfig,
    WordPressHookConfig,
    generate_wp_hooks_plugin,
    generate_wp_widget_plugin,
)

widget_files = generate_wp_widget_plugin(
    WordPressChatWidgetConfig(api_url="https://example.com/api/chat")
)
hook_files = generate_wp_hooks_plugin(
    WordPressHookConfig(webhook_url="https://example.com/webhooks/wordpress")
)
```

## Implementation Notes

Relevant source files:

- `src/agentic_brain/commerce/chatbot/woo_chatbot.py`
- `src/agentic_brain/commerce/chatbot/intents.py`
- `src/agentic_brain/commerce/chatbot/integration.py`
- `src/agentic_brain/commerce/chatbot/analytics_dashboard.py`
- `src/agentic_brain/commerce/chatbot/chatbot/wp_content_bot.py`
- `src/agentic_brain/commerce/chatbot/chatbot/wp_admin_bot.py`
- `src/agentic_brain/commerce/chatbot/chatbot/wp_widget.py`
- `src/agentic_brain/commerce/chatbot/chatbot/wp_hooks.py`
- `src/agentic_brain/commerce/analytics.py`

Key tests demonstrating capabilities:

- `tests/test_wp_chat.py`
- `tests/test_woo_chatbot.py`
- `tests/test_chatbot_advanced.py`
- `tests/test_commerce_analytics.py`
