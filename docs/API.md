# API Developer Guide

This guide covers the currently implemented HTTP and WebSocket interfaces.

## Start the server

```bash
ab serve --host 127.0.0.1 --port 8000
```

Useful URLs:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`
- `http://127.0.0.1:8000/health`

## Core HTTP flow

### Send a chat request

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

### Continue a session

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me more", "session_id": "sess_replace_me"}'
```

### Inspect a session

```bash
curl http://127.0.0.1:8000/session/sess_replace_me
curl http://127.0.0.1:8000/session/sess_replace_me/messages?limit=25
```

### Delete a session

```bash
curl -X DELETE http://127.0.0.1:8000/session/sess_replace_me
curl -X DELETE http://127.0.0.1:8000/sessions
```

## Streaming

### SSE

```bash
curl -N "http://127.0.0.1:8000/chat/stream?message=Hello&provider=ollama&model=llama3.1:8b"
```

### WebSocket

`/ws/chat` requires a JWT by default. Connect with:

- `?token=<jwt>`
- `Authorization: Bearer <jwt>`
- `Sec-WebSocket-Protocol: <jwt>`

See `WEBSOCKET_API.md` for message and error formats.

## Setup and diagnostics

```bash
curl http://127.0.0.1:8000/setup
curl http://127.0.0.1:8000/setup/help/groq
```

## Enterprise helper routes

The following routes are present for integration and CI verification:

- `/auth/saml/login`
- `/auth/saml/acs`
- `/auth/saml/metadata`
- `/auth/sso/{provider}/login`
- `/auth/sso/{provider}/callback`

They require environment-specific configuration before they are useful in production.

## Dashboard

The API mounts a dashboard router automatically:

- `GET /dashboard`
- `GET /dashboard/api/stats`
- `GET /dashboard/api/health`
- `GET /dashboard/api/sessions`
- `DELETE /dashboard/api/sessions`
- `POST /dashboard/api/config`

## Security notes

- HTTP request validation is handled by FastAPI/Pydantic.
- Chat and SSE routes use in-memory rate limiting.
- WebSocket auth uses JWT.
- WooCommerce webhooks require `X-WC-Webhook-Signature`.

For the full path list, use `API_REFERENCE.md` or `/openapi.json`.
