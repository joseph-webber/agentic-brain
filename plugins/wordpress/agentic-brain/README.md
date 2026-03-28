# Agentic Brain WordPress Plugin

WordPress and WooCommerce integration for the Agentic Brain backend.

This plugin adds:

- a floating AI chat widget
- AI-powered product search
- WooCommerce product sync
- WordPress post/page sync for RAG
- admin tools for connection testing and manual sync
- REST endpoints for chat, search, sync, and status

## Location

`plugins/wordpress/agentic-brain/`

## Quick start

1. Copy the plugin into `wp-content/plugins/agentic-brain/`.
2. Activate **Agentic Brain AI Chatbot** in WordPress.
3. Open **Settings → Agentic Brain**.
4. Enter your Agentic Brain backend URL.
5. Optionally enter an API key.
6. Save changes and run **Full Sync**.

## Main settings

- **API Endpoint URL**: required
- **API Key**: optional bearer token
- **Widget Position**: bottom-left or bottom-right
- **Primary Colour**: front-end accent colour
- **Welcome Message**: initial chat greeting
- **Show Widget On**: all pages, product pages only, or shortcode only
- **Auto-Sync Products**: real-time WooCommerce sync
- **Sync Posts & Pages**: include content in the RAG index

## Plugin REST endpoints

- `GET /wp-json/agentic-brain/v1/status`
- `POST /wp-json/agentic-brain/v1/chat`
- `POST /wp-json/agentic-brain/v1/search`
- `POST /wp-json/agentic-brain/v1/sync` (admin only)
- `POST /wp-json/agentic-brain/v1/connection-test` (admin only)

## Content and product sync

- Products sync on create/update/delete when WooCommerce is active.
- Posts and pages sync when `Sync Posts & Pages` is enabled.
- A daily scheduled hook, `agbrain_daily_sync`, performs a full refresh.
- Manual full sync is available from the settings screen.

## Shortcodes

- `[agentic_chat]`
- `[agentic_product_search]`

## Developer notes

Useful classes:

- `Agentic_Brain`
- `Agbrain_API_Client`
- `Agbrain_Product_Sync`
- `Agbrain_RAG_Sync`
- `Agentic_Brain_Hooks`

For full documentation, see [`docs/WORDPRESS_PLUGIN.md`](../../../docs/WORDPRESS_PLUGIN.md).
