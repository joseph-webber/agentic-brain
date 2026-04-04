# API Reference (MkDocs)

This page is the MkDocs-facing API reference.

For the audit-corrected human-readable reference, see [`API_REFERENCE.md`](./API_REFERENCE.md).

## Current endpoint inventory

- `GET /health`
- `POST /chat`
- `GET /chat/stream`
- `GET /session/{session_id}`
- `GET /session/{session_id}/messages`
- `DELETE /session/{session_id}`
- `DELETE /sessions`
- `GET /setup`
- `GET /setup/help/{provider}`
- `POST /auth/saml/login`
- `POST /auth/saml/acs`
- `GET /auth/saml/metadata`
- `GET /auth/sso/{provider}/login`
- `GET /auth/sso/{provider}/callback`
- `GET /dashboard`
- `GET /dashboard/api/stats`
- `GET /dashboard/api/health`
- `GET /dashboard/api/sessions`
- `DELETE /dashboard/api/sessions`
- `POST /dashboard/api/config`
- `POST /webhooks/woocommerce`

## Live schema

Use the running server for exact request and response schemas:

- `/docs`
- `/openapi.json`
