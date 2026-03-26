=== Agentic Brain — AI Chat & Product Search ===
Contributors: josephwebber
Tags: ai, chatbot, woocommerce, search, rag, product-search, assistant
Requires at least: 6.0
Tested up to: 6.8
Requires PHP: 8.0
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Connect your WordPress/WooCommerce store to an Agentic Brain AI backend for intelligent chat, product search, and RAG-powered content.

== Description ==

**Agentic Brain** turns your WordPress site into an AI-powered storefront.

Connect to your own Agentic Brain backend and give your visitors:

* **AI Chat Widget** — a floating chat bubble that answers questions using your products, posts, and pages as context.
* **AI Product Search** — semantic search that understands *intent*, not just keywords.  "Something warm for winter" returns jackets, not keyword matches.
* **RAG Sync** — your WooCommerce catalogue and WordPress content are automatically pushed to the Agentic Brain knowledge base so the AI always has fresh data.
* **Gutenberg Blocks & Shortcodes** — embed the chat or search anywhere with `[agentic_chat]` and `[agentic_product_search]`.

= Why Agentic Brain? =

* **Your data stays yours** — the backend runs wherever you choose (self-hosted, Docker, cloud).
* **Real-time sync** — product updates are pushed instantly, no cron lag.
* **Fully accessible** — WCAG 2.1 AA keyboard navigation, ARIA roles, screen-reader labels on every element.
* **Mobile-first** — responsive chat window that works beautifully on phones.
* **WooCommerce HPOS compatible** — tested with High-Performance Order Storage.

= Requirements =

* A running [Agentic Brain](https://github.com/ecomlounge/agentic-brain) backend instance.
* WordPress 6.0+ and PHP 8.0+.
* WooCommerce 7.0+ (optional — plugin works without it for content-only sites).

== Installation ==

1. Download the plugin ZIP from [GitHub Releases](https://github.com/ecomlounge/agentic-brain/releases) or clone the repo into `wp-content/plugins/`.
2. Activate the plugin through the **Plugins** menu in WordPress.
3. Go to **Settings → Agentic Brain**.
4. Enter the **API Endpoint URL** where your Agentic Brain backend is running.
5. Enter the **API Key** (generate one in the backend admin).
6. Click **Save Changes**.
7. (Optional) Click **Sync Now** to push all products and posts to the AI.

= Using the Chat Widget =

The floating chat bubble appears automatically on every page (configurable).

You can also embed it inline with:

`[agentic_chat welcome="Ask me anything!" height="500px"]`

= Using AI Product Search =

Add the search bar to any page:

`[agentic_product_search placeholder="Find the perfect product…" limit="8"]`

= Gutenberg Blocks =

Two blocks are registered:

* **Agentic Brain Chat** — inline chat widget.
* **Agentic Brain Product Search** — AI-powered search bar.

== Frequently Asked Questions ==

= Where does the AI processing happen? =

All AI inference happens on your Agentic Brain backend — the plugin only relays messages and syncs data via a REST API. No data is sent to third-party AI services by the plugin itself.

= Does it work without WooCommerce? =

Yes. Without WooCommerce the product sync is skipped, but the chat widget and content sync (posts/pages) work perfectly.

= Is it accessible? =

Yes. Every interactive element has ARIA labels, keyboard focus indicators, and screen-reader text. The widget is tested with VoiceOver and NVDA.

= Can I customise the colours? =

Yes — go to **Settings → Agentic Brain → Appearance** and pick any accent colour with the colour picker.

= How often does sync happen? =

* **Real-time** — on every product create/update and post save.
* **Daily** — a full sync runs once a day via WP-Cron as a safety net.
* **Manual** — click "Sync Now" in settings whenever you want.

= What REST endpoints does the plugin expose? =

* `POST /wp-json/agentic-brain/v1/chat` — public, proxies to backend.
* `POST /wp-json/agentic-brain/v1/search` — public, proxies to backend.
* `POST /wp-json/agentic-brain/v1/sync` — admin only, triggers full sync.

== Screenshots ==

1. The floating chat widget on a WooCommerce product page.
2. AI-generated product cards displayed inline in the chat.
3. The admin settings page with connection status indicator.
4. AI product search shortcode embedded on a landing page.
5. Mobile view of the chat window.

== Changelog ==

= 1.0.0 =
* Initial release.
* Floating chat widget with product card support.
* AI-powered product search shortcode & Gutenberg block.
* WooCommerce product sync (real-time + daily cron).
* WordPress post/page sync for content-based RAG.
* Admin settings page with connection health check.
* Full i18n support with .pot file.
* WCAG 2.1 AA accessibility throughout.
* WooCommerce HPOS compatibility declared.

== Upgrade Notice ==

= 1.0.0 =
First release — install and connect to your Agentic Brain backend to get started.
