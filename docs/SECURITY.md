# Security Guide

This guide documents security controls that are implemented in the current repository, plus a short list of items that still require environment-specific hardening.

## Implemented controls

### HTTP API

- request validation via FastAPI and Pydantic
- optional HTTP authentication through the API auth stack
- in-memory per-IP rate limiting for chat and streaming routes
- security headers middleware
- audit middleware for request and error logging

### WebSocket API

- JWT authentication enforced by default in `api/websocket_auth.py`
- token accepted via query parameter, `Authorization` header, or subprotocol header
- invalid or missing tokens close the connection with WebSocket policy-violation code `1008`

### WooCommerce webhook security

`POST /webhooks/woocommerce` is protected by HMAC-SHA256 signature verification using `X-WC-Webhook-Signature`.

### SAML and OAuth helper endpoints

The SAML and SSO endpoints exist for integration and CI verification. They depend on provider configuration and should not be treated as a full identity platform on their own.

## Production checklist

- set a strong `JWT_SECRET`
- enable only the LLM providers you intend to use
- configure Redis and Neo4j credentials explicitly
- terminate TLS in front of the API
- restrict dashboard access at the network or reverse-proxy layer
- rotate API keys and provider secrets

## Environment variables commonly used for security

```bash
JWT_SECRET=replace-me
AUTH_ENABLED=true
API_KEYS=key1,key2
API_KEY_ROLES=key1:ROLE_ADMIN;key2:ROLE_USER
SAML_IDP_ENTITY_ID=...
SAML_IDP_SSO_URL=...
SAML_IDP_CERTIFICATE=...
```

## Known limitations

- HTTP rate limiting is currently in-memory, not distributed
- dashboard endpoints are mounted automatically and should be protected by deployment policy
- WebSocket auth requires a valid JWT secret to be meaningful in production

## Related docs

- `API_REFERENCE.md`
- `WEBSOCKET_API.md`
- `SECURITY_HARDENING.md`
- `SECURITY_ROLES.md`
- `SECURITY_QUICKSTART.md`
- `SECURITY_IMPLEMENTATION.md`
