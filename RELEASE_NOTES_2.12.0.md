# Agentic Brain v2.12.0 — Release Notes

Release date: 2026-03-26

## Highlights

- **WooCommerce integration**: new async-first `WooCommerceAgent` with full CRUD for products, orders, and customers.
- **WordPress plugin support**: WordPress REST client + helpers to generate drop-in widget/hooks plugins and chat widget configuration.
- **Demo environment**: end-to-end demo stack (WordPress + WooCommerce + API) with one-command setup/verify/cleanup scripts.
- **Docker deployment**: dev/test/prod Compose files plus demo Compose for consistent local and hosted deployments.

## What’s New

### 🛍️ Commerce Module (`agentic_brain.commerce`)

- `WooCommerceAgent` for WooCommerce REST API (products, orders, customers)
- Sync wrappers for non-async usage
- `search_products(query)` for RAG ingestion / retrieval
- Pydantic v2 models: `WooProduct`, `WooOrder`, `WooCustomer`, `WooOrderItem`, `WooCoupon`, and more
- `WordPressClient` for WordPress REST API (posts, pages, media, auth)
- `WooCommerceChatbot` for admin/customer/guest storefront flows
- WordPress plugin helpers:
  - `generate_wp_widget_plugin`
  - `generate_wp_hooks_plugin`
  - `WordPressChatWidgetConfig`
- `WooCommerceAnalytics` for sales/funnel/CLV/inventory reporting
- `CommerceHub` facades for payments/shipping/inventory/webhooks

### 🎪 Demo Environment (`demo/`)

- Demo stack via `demo/docker-compose.demo.yml`
- Scripts:
  - `demo/setup-demo.sh`
  - `demo/verify-demo.sh`
  - `demo/cleanup-demo.sh`
- GitHub Actions demo workflow: `.github/workflows/demo.yml` (can trigger on release publish)

### 🐳 Docker Deployment

- Root Compose files: `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.test.yml`
- Deployment profiles in `docker/` (including a demo compose)
- Environment templates (`.env.*.example`) and Docker deployment documentation

### 📚 RAG Improvements

- `WooCommerceLoader` added to `agentic_brain.rag.loaders` for bulk ingestion
- Graph ingest accuracy improvements
- More resilient `add_to_graph()` error handling with structured fallback

## Fixes & Quality

- Fixed missing exports for `WooCommerceAgent` / `WooBaseModel` in `commerce/__init__.py` and package root `__init__.py`
- Updated package description to reflect **verified 155+** RAG loader classes
- Documentation accuracy updates (SOC 2 “Ready”, not “Certified”) and formatting fixes

## Upgrade Notes

- If you rely on durable workflows, ensure dependencies are up to date (Temporal compatibility and related tooling may require additional extras depending on your use case).

## Quick Links

- Changelog: `CHANGELOG.md`
- Demo: `demo/README.md`
- Docker docs: `docs/DOCKER.md` and `DOCKER_DEPLOYMENT_SETUP.md`
