# API Documentation Summary

## Audited source of truth

The API documentation was reconciled against these implementation files:

- `src/agentic_brain/api/server.py`
- `src/agentic_brain/api/routes.py`
- `src/agentic_brain/api/websocket.py`
- `src/agentic_brain/commerce/webhooks.py`
- `src/agentic_brain/dashboard/app.py`

## Current public surface

- 21 implemented HTTP paths
- 1 WebSocket path
- OpenAPI snapshot refreshed in `docs/openapi.json`

## Primary docs

- `API.md` — integration guide
- `API_REFERENCE.md` — endpoint inventory and response shapes
- `WEBSOCKET_API.md` — WebSocket auth, payloads, and error frames

## Verification completed during the audit

- `/health` response shape
- `/chat` request/response flow
- session deletion endpoints
- `/setup` and `/setup/help/{provider}`
- WebSocket invalid JSON and missing-message error frames
- WooCommerce webhook signature rejection behavior
