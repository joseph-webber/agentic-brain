# API Reference

This reference is aligned with the current FastAPI app in `src/agentic_brain/api/server.py` and `routes.py`.

## Base URLs

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## Implemented public endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | API health, provider, Redis, Neo4j, uptime |
| POST | `/chat` | Synchronous chat response |
| GET | `/chat/stream` | SSE token streaming |
| GET | `/session/{session_id}` | Session metadata |
| GET | `/session/{session_id}/messages` | Session messages |
| DELETE | `/session/{session_id}` | Delete one session |
| DELETE | `/sessions` | Clear all sessions |
| GET | `/setup` | LLM provider diagnostics |
| GET | `/setup/help/{provider}` | Provider-specific setup help |
| POST | `/auth/saml/login` | Generate SAML AuthnRequest |
| POST | `/auth/saml/acs` | Validate SAML response |
| GET | `/auth/saml/metadata` | Return SP metadata XML |
| GET | `/auth/sso/{provider}/login` | Generate OAuth/OIDC authorization URL |
| GET | `/auth/sso/{provider}/callback` | Exchange auth code for tokens |
| GET | `/dashboard` | Dashboard HTML |
| GET | `/dashboard/api/stats` | Dashboard stats JSON |
| GET | `/dashboard/api/health` | Dashboard health JSON |
| GET | `/dashboard/api/sessions` | Dashboard session listing |
| DELETE | `/dashboard/api/sessions` | Clear sessions from dashboard |
| POST | `/dashboard/api/config` | Accept runtime config update |
| POST | `/webhooks/woocommerce` | WooCommerce webhook receiver |

## `GET /health`

Response shape:

```json
{
  "status": "healthy",
  "version": "3.1.0",
  "timestamp": "2026-01-01T12:00:00Z",
  "sessions_active": 0,
  "redis": {"status": "ok", "available": true, "message": "Redis is healthy"},
  "llm": {"provider": "ollama", "status": "ok"},
  "neo4j": {"status": "configured", "message": "Optional - chat works without it"},
  "uptime": "0h 1m 30s"
}
```

## `POST /chat`

Request body:

```json
{
  "message": "Hello",
  "session_id": "optional_session",
  "user_id": "optional_user",
  "metadata": {"source": "web"}
}
```

Response:

```json
{
  "response": "Echo: Hello",
  "session_id": "sess_...",
  "timestamp": "2026-01-01T12:00:00Z",
  "message_id": "msg_..."
}
```

Notes:

- The current implementation returns an echo response.
- `message` is required and validated by Pydantic.
- HTTP rate limiting is implemented in-memory per client IP.

## `GET /chat/stream`

Query parameters:

- `message` (required)
- `session_id`
- `user_id`
- `provider` (default `ollama`)
- `model` (default `llama3.1:8b`)
- `temperature` (default `0.7`)

Example:

```bash
curl -N "http://127.0.0.1:8000/chat/stream?message=Hello&provider=ollama&model=llama3.1:8b"
```

The response is an SSE stream with `data:` lines that contain JSON token objects.

## Session endpoints

### `GET /session/{session_id}`
Returns a session record with `id`, `message_count`, `created_at`, `last_accessed`, and `user_id`.

### `GET /session/{session_id}/messages`
Optional query parameter: `limit` (default `50`, max `1000`). Returns a JSON array of message objects.

### `DELETE /session/{session_id}`
Returns:

```json
{
  "deleted": true,
  "message": "Session deleted successfully",
  "resource_id": "sess_..."
}
```

### `DELETE /sessions`
Returns:

```json
{
  "deleted": true,
  "message": "Cleared 3 sessions",
  "resource_id": "*"
}
```

## Setup and diagnostics

- `GET /setup` returns overall provider status plus a quick-start hint when nothing is configured.
- `GET /setup/help/{provider}` returns provider-specific instructions for `groq`, `ollama`, `openai`, `anthropic`, `google`, `xai`, `openrouter`, or `together`.

## Authentication helpers

The SAML and SSO routes are helper endpoints for integration and CI verification. They are present in the running app, but they only work when the corresponding provider settings are configured.

## Dashboard routes

The dashboard router is mounted automatically at `/dashboard`. Current JSON endpoints are:

- `GET /dashboard/api/stats`
- `GET /dashboard/api/health`
- `GET /dashboard/api/sessions`
- `DELETE /dashboard/api/sessions`
- `POST /dashboard/api/config` with body `{ "key": "...", "value": ... }`

## WooCommerce webhook

`POST /webhooks/woocommerce` requires the `X-WC-Webhook-Signature` header. Missing or invalid signatures are rejected before the route handler runs.

## Error handling

Common status codes:

- `200` successful JSON response
- `400` malformed request body or invalid SAML payload
- `401` invalid WooCommerce signature or auth failure
- `404` unknown session or provider
- `422` FastAPI validation error
- `429` in-memory HTTP rate limit exceeded
- `503` provider not configured

For live schema details, use `/openapi.json`.
