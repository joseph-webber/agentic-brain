# 📖 API Reference - Agentic Brain

> **Production-ready orchestration platform for AI agents with GraphRAG memory, multi-LLM routing, and real-time chat**

**Latest Version:** 1.0.0  
**Base URL:** `http://localhost:8000`  
**Documentation:** [Swagger UI](http://localhost:8000/docs) | [ReDoc](http://localhost:8000/redoc)

---

## ⚠️ Implementation Status

This document reflects the **actual implemented endpoints** as of 2026. Endpoints marked with ❌ are documented for future implementation but **do not currently exist** in the codebase.

---

## 📋 Quick Reference Table

### ✅ Implemented Endpoints

| Category | Endpoint | Method | Purpose | Auth | Rate Limit |
|----------|----------|--------|---------|------|-----------|
| **Health** | `/health` | GET | System status | Optional | 60/min |
| **Chat** | `/chat` | POST | Synchronous message | Optional | 60/min |
| **Chat** | `/chat/stream` | GET | SSE streaming | Optional | 60/min |
| **Sessions** | `/session/{id}` | GET | Get session info | Optional | 60/min |
| **Sessions** | `/session/{id}/messages` | GET | Get chat history | Optional | 60/min |
| **Sessions** | `/session/{id}` | DELETE | Clear session | Optional | 60/min |
| **Sessions** | `/sessions` | DELETE | Clear all sessions | Admin | 60/min |
| **Setup** | `/setup` | GET | Provider config | Optional | 60/min |
| **Setup** | `/setup/help/{provider}` | GET | Setup guide | Optional | 60/min |
| **Auth** | `/auth/saml/login` | POST | SAML SSO | None | 5/min |
| **Auth** | `/auth/saml/acs` | POST | SAML ACS | None | 5/min |
| **Auth** | `/auth/saml/metadata` | GET | SAML metadata | None | 60/min |
| **Auth** | `/auth/sso/{provider}/login` | GET | OAuth2/OIDC | None | 5/min |
| **Auth** | `/auth/sso/{provider}/callback` | GET | OAuth callback | None | 5/min |

### ❌ TODO: Not Implemented

The following endpoints are **planned but not yet implemented**:

| Category | Endpoint | Method | Purpose | Status |
|----------|----------|--------|---------|--------|
| **Health** | `/infra/health` | GET | Detailed component health | TODO |
| **Health** | `/healthz` | GET | Kubernetes liveness | TODO |
| **Health** | `/readyz` | GET | Kubernetes readiness | TODO |
| **Health** | `/metrics` | GET | Prometheus metrics | TODO |
| **Health** | `/version` | GET | Version info | TODO |
| **Chat** | `/chat/complete` | POST | Message completion | TODO |
| **Chat** | `/chat/context` | POST | Add context | TODO |
| **Chat** | `/chat/models` | GET | List models | TODO |
| **WebSocket** | `/ws/chat` | WS | Real-time bidirectional | TODO |
| **WebSocket** | `/ws/events` | WS | Events stream | TODO |
| **Sessions** | `/sessions` | GET | List sessions | TODO |
| **Sessions** | `/session/{id}/export` | POST | Export session | TODO |
| **Sessions** | `/session/{id}/import` | POST | Import messages | TODO |
| **Sessions** | `/session/{id}/metadata` | PUT | Update metadata | TODO |
| **Auth** | `/auth/login` | POST | Username/password | TODO |
| **Auth** | `/auth/register` | POST | User registration | TODO |
| **Auth** | `/auth/logout` | POST | Logout | TODO |
| **Auth** | `/auth/token/refresh` | POST | Refresh JWT | TODO |
| **Auth** | `/auth/token/revoke` | POST | Revoke token | TODO |
| **Auth** | `/auth/me` | GET | Current user info | TODO |
| **Auth** | `/auth/mfa/setup` | POST | Setup 2FA | TODO |
| **Auth** | `/auth/mfa/verify` | POST | Verify MFA | TODO |
| **Auth** | `/auth/api-keys` | POST | Create API key | TODO |
| **Auth** | `/auth/api-keys` | GET | List API keys | TODO |
| **Auth** | `/auth/api-keys/{id}` | DELETE | Delete API key | TODO |
| **Setup** | `/setup/test/{provider}` | GET | Test connection | TODO |
| **Diagnostics** | `/diagnostics` | GET | System diagnostics | TODO |
| **Diagnostics** | `/logs` | GET | System logs | TODO |
| **Dashboard** | `/dashboard` | GET | Admin interface | TODO |
| **Dashboard** | `/dashboard/api/stats` | GET | System stats | TODO |
| **Dashboard** | `/dashboard/api/health` | GET | Dashboard health | TODO |
| **Dashboard** | `/dashboard/api/sessions` | GET | List sessions | TODO |
| **Dashboard** | `/dashboard/api/sessions` | DELETE | Clear sessions | TODO |
| **Dashboard** | `/dashboard/api/users` | GET | List users | TODO |
| **Dashboard** | `/dashboard/api/audit-log` | GET | Audit log | TODO |
| **Dashboard** | `/dashboard/api/backup` | POST | Create backup | TODO |
| **Dashboard** | `/dashboard/api/providers` | GET | Providers status | TODO |
| **Webhooks** | `/webhooks/woocommerce` | POST | WooCommerce events | TODO |
| **Webhooks** | `/webhooks/stripe` | POST | Stripe events | TODO |
| **Webhooks** | `/webhooks/github` | POST | GitHub events | TODO |
| **Webhooks** | `/webhooks` | GET | List webhooks | TODO |
| **Webhooks** | `/webhooks/test/{provider}` | POST | Test webhook | TODO |
| **Workflows** | `/workflows` | POST | Create workflow | TODO |
| **Workflows** | `/workflows` | GET | List workflows | TODO |
| **Workflows** | `/workflows/{id}` | GET | Get workflow | TODO |
| **Workflows** | `/workflows/{id}` | PUT | Update workflow | TODO |
| **Workflows** | `/workflows/{id}` | DELETE | Delete workflow | TODO |
| **Workflows** | `/workflows/{id}/executions` | GET | Workflow executions | TODO |
| **Workflows** | `/workflows/{id}/test` | POST | Test workflow | TODO |
| **Workflows** | `/workflows/{id}/enable` | POST | Enable workflow | TODO |
| **Workflows** | `/workflows/{id}/disable` | POST | Disable workflow | TODO |
| **Batch** | `/batch/create` | POST | Create batch | TODO |
| **Batch** | `/batch/{id}` | GET | Batch status | TODO |
| **Batch** | `/batch/{id}/results` | GET | Batch results | TODO |
| **Batch** | `/batch/{id}` | DELETE | Cancel batch | TODO |

---

## 🔐 Authentication

Agentic Brain supports multiple authentication mechanisms. Configuration via `AUTH_ENABLED` environment variable.

### 1. **API Key Authentication**

Use when `AUTH_ENABLED=true` and API keys are configured.

**Header Method:**
```bash
curl -H "X-API-Key: your_api_key" http://localhost:8000/health
```

**Query Parameter Method:**
```bash
curl http://localhost:8000/health?api_key=your_api_key
```

**Configuration:**
```bash
API_KEYS=key1,key2,key3
API_KEY_ROLES=key1:ROLE_ADMIN,ROLE_USER;key2:ROLE_USER
```

### 2. **JWT Token Authentication**

Use for stateless, scalable authentication.

**Header Method:**
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." http://localhost:8000/health
```

**Configuration:**
```bash
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
```

**JWT Claims:**
```json
{
  "sub": "user_123",
  "roles": ["ROLE_USER", "ROLE_ADMIN"],
  "exp": 1234567890
}
```

### 3. **WebSocket Authentication** (Production Required)

**Query Parameter:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat?token=your_jwt_token');
```

**Authorization Header:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat', {
  headers: { Authorization: 'Bearer your_jwt_token' }
});
```

### 4. **SAML/OAuth2/OIDC** (Enterprise)

See [Authentication Endpoints](#5️⃣-authentication-endpoints) section.

---

## ⚡ Rate Limiting

**Implementation:** Token bucket (deque-based in-memory)

**Default Limits:**
| User Type | Limit | Endpoint |
|-----------|-------|----------|
| Anonymous | 60 req/min | Per IP address |
| Authenticated | 100 req/min | Per user ID |
| Login Attempts | 5 req/min | Brute force protection |
| WebSocket | 50 msg/min | Per connection |

**Response Headers:**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1234567890
```

**When Rate Limited (429 Too Many Requests):**
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60,
  "detail": "Maximum 60 requests per minute exceeded"
}
```

---

## 1️⃣ Health & Monitoring Endpoints

### `GET /health` - System Health ✅

Quick system status check.

**Request:**
```bash
curl -X GET http://localhost:8000/health
```

**With Authentication:**
```bash
curl -X GET http://localhost:8000/health \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**With API Key:**
```bash
curl -X GET http://localhost:8000/health \
  -H "X-API-Key: your_api_key"
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-15T10:30:45.123Z",
  "sessions_active": 5,
  "redis": {
    "status": "ok",
    "available": true
  },
  "llm": {
    "provider": "groq",
    "status": "ok"
  },
  "neo4j": {
    "status": "configured"
  },
  "uptime": "2h 15m 30s"
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "error": "Neo4j connection failed",
  "timestamp": "2026-01-15T10:30:45.123Z"
}
```

---

### `GET /infra/health` - Detailed Component Health ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Comprehensive infrastructure health report with latency metrics.

**Request:**
```bash
curl -X GET http://localhost:8000/infra/health
```

**With Verbose Output:**
```bash
curl -X GET http://localhost:8000/infra/health \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -v
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-15T10:30:45.123Z",
  "components": {
    "redis": {
      "status": "ok",
      "available": true,
      "latency_ms": 1.2,
      "memory_mb": 45.3
    },
    "neo4j": {
      "status": "ok",
      "available": true,
      "latency_ms": 3.5,
      "nodes": 1250,
      "relationships": 5432
    },
    "redpanda": {
      "status": "ok",
      "available": true,
      "brokers": 3,
      "topics": 42
    }
  }
}
```

---

### `GET /healthz` - Kubernetes Liveness Probe ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Liveness check for Kubernetes deployments.

**Request:**
```bash
curl -X GET http://localhost:8000/healthz
```

**With Timeout (useful in CI/CD):**
```bash
curl -X GET http://localhost:8000/healthz \
  --max-time 5
```

**Response (200 OK):**
```
OK
```

---

### `GET /readyz` - Kubernetes Readiness Probe ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Readiness check for Kubernetes deployments (includes all dependencies).

**Request:**
```bash
curl -X GET http://localhost:8000/readyz
```

**Check Readiness Before Load Balancer Traffic:**
```bash
curl -X GET http://localhost:8000/readyz \
  --fail-with-body \
  --show-error
```

**Response (200 OK):**
```
READY
```

**Response (503 Service Unavailable):**
```
NOT_READY
```

---

### `GET /metrics` - Prometheus Metrics ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Export system metrics in Prometheus format for monitoring.

**Request:**
```bash
curl -X GET http://localhost:8000/metrics
```

**Example Response (text/plain):**
```
# HELP agentic_brain_sessions_active Active session count
# TYPE agentic_brain_sessions_active gauge
agentic_brain_sessions_active 12

# HELP agentic_brain_messages_total Total messages processed
# TYPE agentic_brain_messages_total counter
agentic_brain_messages_total 5420

# HELP agentic_brain_response_time_ms Response time in milliseconds
# TYPE agentic_brain_response_time_ms histogram
agentic_brain_response_time_ms_bucket{le="100"} 450
agentic_brain_response_time_ms_bucket{le="500"} 980
agentic_brain_response_time_ms_bucket{le="+Inf"} 1050
```

---

### `GET /version` - Get Version Info ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get detailed version and build information.

**Request:**
```bash
curl -X GET http://localhost:8000/version
```

**Response (200 OK):**
```json
{
  "version": "1.0.0",
  "build": "build-2026-01-15",
  "git_commit": "abc123def456",
  "git_branch": "main",
  "python_version": "3.11.0",
  "timestamp": "2026-01-15T10:30:45.123Z"
}
```

---

## 2️⃣ Chat Endpoints

### `POST /chat` - Synchronous Chat ✅

Send a message and receive a response synchronously.

**Simple Request (no auth):**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, how are you?"
  }'
```

**Full Request with all parameters:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "message": "What is GraphRAG?",
    "session_id": "sess_abc123",
    "user_id": "user_456",
    "metadata": {
      "source": "cli",
      "client_version": "1.0.0"
    }
  }'
```

**With API Key Authentication:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "message": "Tell me a joke",
    "session_id": "sess_xyz789"
  }'
```

**Request Model (actual implementation):**
```python
{
  "message": str,           # 1-32,000 characters (REQUIRED)
  "session_id": str | None, # Optional, alphanumeric with hyphens/underscores, max 64 chars
  "user_id": str | None,    # Optional, alphanumeric with hyphens/underscores, max 64 chars
  "metadata": dict | None   # Optional, custom metadata (max 10,000 chars when serialized)
}
```

> **Note:** The following parameters are NOT currently implemented in the ChatRequest model:
> `provider`, `model`, `temperature`, `max_tokens`. These are planned for future releases.
> To customize LLM behavior, use the `metadata` field or configure via environment variables.

**Response (200 OK):**
```json
{
  "response": "GraphRAG is a framework combining graph-based retrieval with RAG...",
  "session_id": "sess_abc123",
  "message_id": "msg_def456",
  "timestamp": "2026-01-15T10:30:45.123Z"
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "Validation failed",
  "detail": [
    {
      "field": "message",
      "message": "String must be between 1 and 32000 characters"
    }
  ]
}
```

**Error Response (401 Unauthorized):**
```json
{
  "error": "Authentication required",
  "detail": "Missing or invalid Authorization header"
}
```

**Error Response (429 Too Many Requests):**
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

### `GET /chat/stream` - Server-Sent Events (SSE) Streaming ✅

Stream responses in real-time using Server-Sent Events.

**Basic Streaming Request:**
```bash
curl -N "http://localhost:8000/chat/stream?message=What%20is%20AI%3F"
```

**With Full Parameters:**
```bash
curl -N "http://localhost:8000/chat/stream?message=What%20is%20AI%3F&session_id=sess_xyz&provider=ollama&model=llama3.1:8b&temperature=0.7" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Query Parameters (actual implementation):**
| Parameter | Type | Required | Description | Default | Range |
|-----------|------|----------|-------------|---------|-------|
| `message` | string | Yes | User message | - | 1-10,000 chars |
| `session_id` | string | No | Session identifier | Generated UUID | - |
| `user_id` | string | No | User identifier | - | - |
| `provider` | string | No | LLM provider | "ollama" | ollama, openai, anthropic |
| `model` | string | No | Model name | "llama3.1:8b" | Provider-specific |
| `temperature` | float | No | Sampling temperature | 0.7 | 0.0-2.0 |

> **Note:** `max_tokens` parameter is NOT currently implemented in the stream endpoint.

**Response (200 OK):**
```
data: {"token":"Machine","is_start":true,"is_end":false,"finish_reason":null,"metadata":{"session_id":"sess_xyz","message_id":"msg_123"}}
data: {"token":" learning","is_start":false,"is_end":false,"finish_reason":null,"metadata":{}}
data: {"token":" involves","is_start":false,"is_end":false,"finish_reason":null,"metadata":{}}
...
data: {"token":".","is_start":false,"is_end":true,"finish_reason":"stop","metadata":{}}
```

**Stream Event Model:**
```python
{
  "token": str,              # Token/chunk of response
  "is_start": bool,          # First token in sequence
  "is_end": bool,            # Last token (stream complete)
  "finish_reason": str,      # "stop", "length", "error", or null
  "metadata": dict           # Additional info
}
```

---

### `POST /chat/complete` - Message Completion ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get completions for partial messages.

**Planned Request:**
```bash
curl -X POST http://localhost:8000/chat/complete \
  -H "Content-Type: application/json" \
  -d '{
    "prefix": "The capital of France is",
    "session_id": "sess_abc123"
  }'
```

**Response (200 OK):**
```json
{
  "completion": "The capital of France is Paris, a city known for its art, architecture, and culture.",
  "session_id": "sess_abc123",
  "message_id": "msg_def456",
  "confidence": 0.95
}
```

---

### `POST /chat/context` - Add Context to Session ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Add context/instructions for the chat session.

**Request:**
```bash
curl -X POST http://localhost:8000/chat/context \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_abc123",
    "context": "You are a helpful AI assistant specializing in machine learning.",
    "role": "system"
  }'
```

**Response (200 OK):**
```json
{
  "session_id": "sess_abc123",
  "context_id": "ctx_789",
  "status": "added"
}
```

---

### `GET /chat/models` - Available Models ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

List all available LLM models.

**Request:**
```bash
curl -X GET http://localhost:8000/chat/models
```

**With Provider Filter:**
```bash
curl -X GET "http://localhost:8000/chat/models?provider=groq"
```

**Response (200 OK):**
```json
{
  "models": [
    {
      "name": "llama3.1:8b",
      "provider": "ollama",
      "context_window": 8192,
      "capabilities": ["chat", "reasoning"]
    },
    {
      "name": "mixtral-8x7b-32768",
      "provider": "groq",
      "context_window": 32768,
      "capabilities": ["chat", "function_calling"]
    }
  ],
  "default": "llama3.1:8b"
}
```

---

## 3️⃣ Session Management Endpoints

### `GET /session/{session_id}` - Get Session Info ✅

Retrieve metadata about a session.

**Request:**
```bash
curl -X GET http://localhost:8000/session/sess_abc123 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**With API Key:**
```bash
curl -X GET http://localhost:8000/session/sess_abc123 \
  -H "X-API-Key: your_api_key"
```

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string | Session identifier (UUID format) |

**Response (200 OK):**
```json
{
  "id": "sess_abc123",
  "message_count": 14,
  "created_at": "2026-01-15T09:00:00.000Z",
  "last_accessed": "2026-01-15T10:30:45.123Z",
  "user_id": "user_456",
  "provider": "ollama",
  "model": "llama3.1:8b",
  "metadata": {
    "source": "cli",
    "tags": ["test", "development"]
  }
}
```

**Error Response (404 Not Found):**
```json
{
  "error": "Session not found",
  "detail": "Session 'sess_abc123' does not exist or has expired"
}
```

---

### `GET /session/{session_id}/messages` - Get Chat History ✅

Retrieve all messages in a session with pagination.

**Request:**
```bash
curl -X GET 'http://localhost:8000/session/sess_abc123/messages?limit=50' \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**With Offset/Pagination:**
```bash
curl -X GET 'http://localhost:8000/session/sess_abc123/messages?limit=20&offset=40' \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Get Recent Messages Only:**
```bash
curl -X GET 'http://localhost:8000/session/sess_abc123/messages?limit=10' \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Query Parameters:**
| Parameter | Type | Default | Range |
|-----------|------|---------|-------|
| `limit` | integer | 50 | 1-1000 |
| `offset` | integer | 0 | >= 0 |

**Response (200 OK):**
```json
[
  {
    "id": "msg_001",
    "role": "user",
    "content": "What is GraphRAG?",
    "timestamp": "2026-01-15T10:00:00.000Z",
    "metadata": {}
  },
  {
    "id": "msg_002",
    "role": "assistant",
    "content": "GraphRAG combines graph-based retrieval with augmented generation...",
    "timestamp": "2026-01-15T10:00:05.000Z",
    "metadata": {
      "tokens": 187,
      "model": "llama3.1:8b"
    }
  }
]
```

**Error Response (404 Not Found):**
```json
{
  "error": "Session not found",
  "detail": "Session 'sess_abc123' does not exist"
}
```

---

### `DELETE /session/{session_id}` - Delete Session ✅

Clear a session and all its messages.

**Request:**
```bash
curl -X DELETE http://localhost:8000/session/sess_abc123 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**With Force Flag:**
```bash
curl -X DELETE http://localhost:8000/session/sess_abc123?force=true \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (204 No Content):**
```
(empty body)
```

**Error Response (404 Not Found):**
```json
{
  "error": "Session not found",
  "detail": "Session 'sess_abc123' does not exist"
}
```

---

### `DELETE /sessions` - Clear All Sessions ✅

**⚠️ Admin-only endpoint** - Remove all sessions from the system.

**Request:**
```bash
curl -X DELETE http://localhost:8000/sessions \
  -H "Authorization: Bearer admin_token"
```

**With Confirmation Header:**
```bash
curl -X DELETE http://localhost:8000/sessions \
  -H "Authorization: Bearer admin_token" \
  -H "X-Confirm: yes"
```

**Response (204 No Content):**
```
(empty body)
```

**Error Response (403 Forbidden):**
```json
{
  "error": "Insufficient permissions",
  "detail": "ROLE_ADMIN required for this operation"
}
```

---

### `GET /sessions` - List All Sessions ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get all active sessions (admin-only).

**Request:**
```bash
curl -X GET http://localhost:8000/sessions \
  -H "Authorization: Bearer admin_token"
```

**With Pagination:**
```bash
curl -X GET "http://localhost:8000/sessions?limit=20&offset=0" \
  -H "Authorization: Bearer admin_token"
```

**Filter by User:**
```bash
curl -X GET "http://localhost:8000/sessions?user_id=user_456" \
  -H "Authorization: Bearer admin_token"
```

**Response (200 OK):**
```json
{
  "sessions": [
    {
      "id": "sess_abc123",
      "user_id": "user_456",
      "created_at": "2026-01-15T09:00:00.000Z",
      "last_accessed": "2026-01-15T10:30:45.123Z",
      "message_count": 14
    },
    {
      "id": "sess_xyz789",
      "user_id": "user_789",
      "created_at": "2026-01-15T08:00:00.000Z",
      "last_accessed": "2026-01-15T10:20:00.000Z",
      "message_count": 5
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

---

### `POST /session/{session_id}/export` - Export Session ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Export a session as JSON or CSV.

**Request (JSON Format):**
```bash
curl -X POST http://localhost:8000/session/sess_abc123/export \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "json"
  }'
```

**Request (CSV Format):**
```bash
curl -X POST http://localhost:8000/session/sess_abc123/export \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "format": "csv"
  }' \
  -o session_export.csv
```

**Response (200 OK - JSON):**
```json
{
  "id": "sess_abc123",
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "What is GraphRAG?",
      "timestamp": "2026-01-15T10:00:00.000Z"
    }
  ],
  "metadata": {
    "created_at": "2026-01-15T09:00:00.000Z",
    "total_messages": 14
  }
}
```

---

### `POST /session/{session_id}/import` - Import Messages ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Import messages into a session.

**Request:**
```bash
curl -X POST http://localhost:8000/session/sess_abc123/import \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Hello"
      },
      {
        "role": "assistant",
        "content": "Hi there!"
      }
    ]
  }'
```

**Response (200 OK):**
```json
{
  "session_id": "sess_abc123",
  "imported_count": 2,
  "total_messages": 16
}
```

---

### `PUT /session/{session_id}/metadata` - Update Session Metadata ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Update metadata for a session.

**Request:**
```bash
curl -X PUT http://localhost:8000/session/sess_abc123/metadata \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tags": ["urgent", "customer-support"],
    "priority": "high",
    "custom_field": "custom_value"
  }'
```

**Response (200 OK):**
```json
{
  "session_id": "sess_abc123",
  "metadata": {
    "tags": ["urgent", "customer-support"],
    "priority": "high",
    "custom_field": "custom_value"
  }
}
```

---

## 4️⃣ WebSocket Endpoints

### `WS /ws/chat` - Real-Time Bidirectional Chat ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Establish a WebSocket connection for real-time streaming chat.

**Connection (cURL with websocat):**
```bash
# Install websocat: brew install websocat
websocat "ws://localhost:8000/ws/chat?token=YOUR_JWT_TOKEN"
# Then type JSON messages interactively
```

**Connection (Python):**
```python
import websockets
import json
import asyncio

async def chat():
    uri = "ws://localhost:8000/ws/chat?token=your_jwt_token"
    # Or with authentication:
    # uri = "ws://localhost:8000/ws/chat?api_key=your_api_key"
    
    async with websockets.connect(uri) as websocket:
        # Send a message
        message = {
            "message": "Tell me about vector databases",
            "session_id": "sess_abc123",
            "user_id": "user_456",
            "provider": "ollama",
            "model": "llama3.1:8b",
            "temperature": 0.7
        }
        await websocket.send(json.dumps(message))
        
        # Receive streamed response
        async for response in websocket:
            data = json.loads(response)
            if data.get("is_end"):
                print(f"\n[DONE] {data.get('finish_reason')}")
                break
            print(data.get("token"), end="", flush=True)

asyncio.run(chat())
```

**Connection (JavaScript/Node.js):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat?token=your_jwt_token');

ws.onopen = () => {
  console.log('Connected to WebSocket');
  ws.send(JSON.stringify({
    message: "What is a vector database?",
    session_id: "sess_abc123",
    provider: "ollama",
    model: "llama3.1:8b",
    temperature: 0.7
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.token) {
    process.stdout.write(data.token);
  }
  if (data.is_end) {
    console.log(`\n[Complete] ${data.finish_reason}`);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

**Connection (JavaScript/Fetch API):**
```javascript
async function connectWebSocket() {
  const ws = new WebSocket('ws://localhost:8000/ws/chat?token=your_jwt_token');
  
  ws.addEventListener('open', () => {
    ws.send(JSON.stringify({
      message: "Explain quantum computing",
      session_id: "sess_xyz789"
    }));
  });
  
  ws.addEventListener('message', (event) => {
    const response = JSON.parse(event.data);
    console.log('Token:', response.token);
  });
}
```

**Client Message Format:**
```json
{
  "message": "Your question here",
  "session_id": "sess_abc123",
  "user_id": "user_456",
  "provider": "ollama",
  "model": "llama3.1:8b",
  "temperature": 0.7,
  "max_tokens": 500
}
```

**Server Response Format (First Token):**
```json
{
  "token": "Machine",
  "is_start": true,
  "is_end": false,
  "finish_reason": null,
  "metadata": {
    "session_id": "sess_abc123",
    "message_id": "msg_def456"
  }
}
```

**Server Response Format (Middle Tokens):**
```json
{
  "token": " learning",
  "is_start": false,
  "is_end": false,
  "finish_reason": null,
  "metadata": {}
}
```

**Server Response After All Tokens:**
```json
{
  "token": "",
  "is_start": false,
  "is_end": true,
  "finish_reason": "stop",
  "metadata": {
    "session_id": "sess_abc123",
    "total_tokens": 187
  }
}
```

**Error Response:**
```json
{
  "error": "Invalid JSON in request",
  "token": "",
  "is_end": true,
  "finish_reason": "error"
}
```

---

### `WS /ws/events` - Real-Time Events Stream ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Subscribe to real-time events (sessions, messages, system).

**Connection (Python):**
```python
import websockets
import json
import asyncio

async def listen_events():
    async with websockets.connect("ws://localhost:8000/ws/events?token=your_jwt_token") as ws:
        # Subscribe to session events
        await ws.send(json.dumps({
            "action": "subscribe",
            "event_type": "session",
            "session_id": "sess_abc123"
        }))
        
        # Listen for events
        async for event_data in ws:
            event = json.loads(event_data)
            print(f"Event: {event['type']} - {event['payload']}")

asyncio.run(listen_events())
```

**Event Subscription Message:**
```json
{
  "action": "subscribe",
  "event_type": "session",
  "session_id": "sess_abc123"
}
```

**Example Event Response (New Message):**
```json
{
  "type": "message_created",
  "session_id": "sess_abc123",
  "message_id": "msg_001",
  "timestamp": "2026-01-15T10:30:45.123Z",
  "payload": {
    "role": "user",
    "content": "What is AI?"
  }
}
```

**Example Event Response (Session Updated):**
```json
{
  "type": "session_updated",
  "session_id": "sess_abc123",
  "timestamp": "2026-01-15T10:30:45.123Z",
  "payload": {
    "message_count": 14,
    "last_accessed": "2026-01-15T10:30:45.123Z"
  }
}
```

---

## 5️⃣ Authentication Endpoints

### `POST /auth/login` - Username/Password Login ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Basic authentication endpoint for username and password.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "secure_password"
  }'
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "user_123",
    "username": "user@example.com",
    "roles": ["ROLE_USER"]
  }
}
```

**Error Response (401 Unauthorized):**
```json
{
  "error": "Invalid credentials",
  "detail": "Username or password is incorrect"
}
```

---

### `POST /auth/register` - User Registration ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Register a new user account.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "secure_password123",
    "name": "John Doe",
    "organization": "Acme Corp"
  }'
```

**Response (201 Created):**
```json
{
  "id": "user_789",
  "email": "newuser@example.com",
  "name": "John Doe",
  "created_at": "2026-01-15T10:30:45.123Z"
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "Registration failed",
  "detail": "Email already registered"
}
```

---

### `POST /auth/token/refresh` - Refresh JWT Token ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get a new access token using a refresh token.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/token/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

---

### `POST /auth/token/revoke` - Revoke Token ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Revoke/invalidate an access token.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/token/revoke \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

**Response (204 No Content):**
```
(empty body)
```

---

### `POST /auth/logout` - Logout ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Invalidate the current session/token.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (204 No Content):**
```
(empty body)
```

---

### `POST /auth/saml/login` - Initiate SAML SSO ✅

Start a SAML single sign-on flow.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/saml/login \
  -H "Content-Type: application/json" \
  -d '{
    "relay_state": "return_url"
  }'
```

**Response (200 OK):**
```json
{
  "sso_url": "https://idp.example.com/sso?SAMLRequest=PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4...",
  "authn_request": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>...",
  "request_id": "_abc123xyz789"
}
```

---

### `POST /auth/saml/acs` - SAML Assertion Consumer Service ✅

Handle SAML authentication response from IdP.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/saml/acs \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'SAMLResponse=PHNhbWxwOlJlc3BvbnNlIHhtbG5zOnNhbWxwPSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6cHJvdG9jb2wiIHhtbG5zOnNhbWw9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphc3NlcnRpb24iIElEPSJfYWJjMTIzIiBWZXJzaW9uPSIyLjAiIElzc3VlSW5zdGFudD0iMjAyNi0wMS0xNVQxMDozMDo0NS4xMjNaIj4uLi48L3NhbWxwOlJlc3BvbnNlPg=='
```

**Response (200 OK - with Redirect):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "user": {
    "id": "user_789",
    "email": "user@example.com",
    "name": "John Doe",
    "roles": ["ROLE_USER"]
  },
  "relay_state": "return_url"
}
```

---

### `GET /auth/saml/metadata` - SAML Service Provider Metadata ✅

Get SP metadata for IdP configuration.

**Request:**
```bash
curl -X GET http://localhost:8000/auth/saml/metadata
```

**Response (200 OK):**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" 
                  entityID="https://agentic-brain.example.com/saml/metadata">
  <SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true"
                   protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <KeyDescriptor use="encryption">
      <KeyInfo xmlns="http://www.w3.org/2000/09/xmldsig#">
        <X509Data>
          <X509Certificate>...</X509Certificate>
        </X509Data>
      </KeyInfo>
    </KeyDescriptor>
    <SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                         Location="https://agentic-brain.example.com/auth/saml/sls" />
    <NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified</NameIDFormat>
    <AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                              Location="https://agentic-brain.example.com/auth/saml/acs"
                              index="0" isDefault="true" />
  </SPSSODescriptor>
</EntityDescriptor>
```

---

### `GET /auth/sso/{provider}/login` - OAuth2/OIDC Authorization ✅

Get authorization URL for OAuth2/OIDC login.

**Google OAuth2:**
```bash
curl -X GET 'http://localhost:8000/auth/sso/google/login?redirect_uri=http://localhost:3000/callback'
```

**GitHub OAuth2:**
```bash
curl -X GET 'http://localhost:8000/auth/sso/github/login?redirect_uri=http://localhost:3000/callback'
```

**Microsoft Azure AD:**
```bash
curl -X GET 'http://localhost:8000/auth/sso/microsoft/login?redirect_uri=http://localhost:3000/callback'
```

**Okta OIDC:**
```bash
curl -X GET 'http://localhost:8000/auth/sso/okta/login?redirect_uri=http://localhost:3000/callback'
```

**Supported Providers:**
- `google` - Google OAuth2
- `github` - GitHub OAuth2
- `microsoft` - Microsoft Azure AD
- `okta` - Okta OIDC
- `generic` - Generic OIDC provider

**Response (200 OK):**
```json
{
  "provider": "google",
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=123456.apps.googleusercontent.com&redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fcallback&response_type=code&scope=openid%20email%20profile&state=abc123xyz789",
  "state": "abc123xyz789"
}
```

---

### `GET /auth/sso/{provider}/callback` - OAuth2/OIDC Callback ✅

Handle OAuth2/OIDC callback from provider.

**Request:**
```bash
curl -X GET 'http://localhost:8000/auth/sso/google/callback?code=4/0AX4Xcg...&state=abc123xyz789'
```

**Query Parameters:**
| Parameter | Description |
|-----------|-------------|
| `code` | Authorization code from provider |
| `state` | State parameter (verification) |
| `error` | Error code if authentication failed |

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "id_token_payload": {
    "sub": "user_123",
    "email": "user@example.com",
    "email_verified": true,
    "name": "John Doe",
    "picture": "https://example.com/photo.jpg"
  },
  "user": {
    "id": "user_123",
    "email": "user@example.com",
    "name": "John Doe",
    "roles": ["ROLE_USER"]
  }
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "invalid_grant",
  "detail": "Authorization code has expired or is invalid"
}
```

---

### `GET /auth/me` - Get Current User Info ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get information about the currently authenticated user.

**Request:**
```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "id": "user_123",
  "username": "user@example.com",
  "email": "user@example.com",
  "name": "John Doe",
  "roles": ["ROLE_USER"],
  "created_at": "2026-01-01T00:00:00.000Z",
  "last_login": "2026-01-15T10:30:45.123Z",
  "mfa_enabled": false
}
```

---

### `POST /auth/mfa/setup` - Setup Two-Factor Authentication ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Initialize 2FA/MFA setup.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/mfa/setup \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "totp"
  }'
```

**Response (200 OK):**
```json
{
  "secret": "JBSWY3DPEBLW64TMMQ======",
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAADICAYAA...",
  "backup_codes": [
    "ABC123",
    "DEF456",
    "GHI789"
  ]
}
```

---

### `POST /auth/mfa/verify` - Verify MFA Code ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Verify MFA code during login.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/mfa/verify \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "code": "123456"
  }'
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer"
}
```

---

### `POST /auth/api-keys` - Create API Key ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Generate a new API key for programmatic access.

**Request:**
```bash
curl -X POST http://localhost:8000/auth/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key",
    "expires_in_days": 365,
    "scopes": ["chat:write", "session:read"]
  }'
```

**Response (201 Created):**
```json
{
  "id": "api_key_abc123",
  "name": "Production API Key",
  "key": "sk_live_abc123xyz789...",
  "created_at": "2026-01-15T10:30:45.123Z",
  "expires_at": "2027-01-15T10:30:45.123Z",
  "scopes": ["chat:write", "session:read"]
}
```

---

### `GET /auth/api-keys` - List API Keys ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

List all API keys for the current user.

**Request:**
```bash
curl -X GET http://localhost:8000/auth/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "api_keys": [
    {
      "id": "api_key_abc123",
      "name": "Production API Key",
      "last_used": "2026-01-15T10:30:45.123Z",
      "created_at": "2026-01-15T10:30:45.123Z"
    }
  ]
}
```

---

### `DELETE /auth/api-keys/{key_id}` - Delete API Key ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Revoke an API key.

**Request:**
```bash
curl -X DELETE http://localhost:8000/auth/api-keys/api_key_abc123 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (204 No Content):**
```
(empty body)
```

---

## 6️⃣ Setup & Diagnostics Endpoints

### `GET /setup` - Check LLM Provider Configuration ✅

Get the setup status and available LLM providers.

**Request:**
```bash
curl -X GET http://localhost:8000/setup
```

**With Authentication:**
```bash
curl -X GET http://localhost:8000/setup \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "status": "configured",
  "message": "✓ 3 provider(s) ready",
  "providers": {
    "available": [
      {
        "name": "groq",
        "reason": "API key configured",
        "models": ["mixtral-8x7b-32768", "llama2-70b-4096"]
      },
      {
        "name": "ollama",
        "reason": "Local server available",
        "models": ["llama3.1:8b", "llama3:70b", "mistral"]
      },
      {
        "name": "openai",
        "reason": "API key configured",
        "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
      }
    ],
    "unavailable": [
      {
        "name": "anthropic",
        "reason": "Missing API key - set ANTHROPIC_API_KEY"
      }
    ]
  },
  "setup_guide": "Configure providers via environment variables: GROQ_API_KEY, OPENAI_API_KEY, etc."
}
```

---

### `GET /setup/help/{provider}` - Provider Setup Instructions ✅

Get setup instructions for a specific provider.

**Request (Groq):**
```bash
curl -X GET http://localhost:8000/setup/help/groq
```

**Request (Ollama):**
```bash
curl -X GET http://localhost:8000/setup/help/ollama
```

**Request (OpenAI):**
```bash
curl -X GET http://localhost:8000/setup/help/openai
```

**Response (200 OK - Groq):**
```json
{
  "provider": "groq",
  "status": "configured",
  "instructions": "Groq API is configured and ready to use.",
  "environment_variables": {
    "GROQ_API_KEY": "Set to your Groq API key from https://console.groq.com"
  },
  "documentation_url": "https://console.groq.com/docs/models",
  "available_models": ["mixtral-8x7b-32768", "llama2-70b-4096"]
}
```

---

### `GET /setup/test/{provider}` - Test Provider Connection ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Test connection to a specific provider.

**Request:**
```bash
curl -X GET http://localhost:8000/setup/test/ollama
```

**With Custom Model:**
```bash
curl -X GET "http://localhost:8000/setup/test/groq?model=mixtral-8x7b-32768"
```

**Response (200 OK):**
```json
{
  "provider": "ollama",
  "status": "ok",
  "latency_ms": 125,
  "model": "llama3.1:8b",
  "test_message": "Hello! I'm working correctly.",
  "timestamp": "2026-01-15T10:30:45.123Z"
}
```

---

### `GET /diagnostics` - System Diagnostics ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get comprehensive system diagnostics information.

**Request:**
```bash
curl -X GET http://localhost:8000/diagnostics \
  -H "Authorization: Bearer admin_token"
```

**Response (200 OK):**
```json
{
  "timestamp": "2026-01-15T10:30:45.123Z",
  "system": {
    "python_version": "3.11.0",
    "platform": "darwin",
    "cpu_count": 8,
    "memory_total_gb": 16.0,
    "memory_available_gb": 12.3
  },
  "services": {
    "redis": {
      "status": "connected",
      "version": "7.0.0",
      "memory_used_mb": 45.3
    },
    "neo4j": {
      "status": "connected",
      "version": "5.0.0",
      "nodes": 1250,
      "relationships": 5432
    },
    "redpanda": {
      "status": "connected",
      "brokers": 3,
      "topics": 42
    }
  }
}
```

---

### `GET /logs` - Get System Logs ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Retrieve system logs with filtering.

**Request (Last 100 lines):**
```bash
curl -X GET 'http://localhost:8000/logs?limit=100' \
  -H "Authorization: Bearer admin_token"
```

**Request (Filter by Level):**
```bash
curl -X GET 'http://localhost:8000/logs?level=error&limit=50' \
  -H "Authorization: Bearer admin_token"
```

**Request (Filter by Time Range):**
```bash
curl -X GET 'http://localhost:8000/logs?since=2026-01-15T10:00:00Z&limit=200' \
  -H "Authorization: Bearer admin_token"
```

**Response (200 OK):**
```json
{
  "logs": [
    {
      "timestamp": "2026-01-15T10:30:45.123Z",
      "level": "INFO",
      "message": "Session created: sess_abc123",
      "source": "chat_handler"
    },
    {
      "timestamp": "2026-01-15T10:30:46.456Z",
      "level": "DEBUG",
      "message": "Groq API call: 125ms",
      "source": "groq_provider"
    }
  ],
  "total": 2,
  "limit": 100
}
```

---

## 7️⃣ Dashboard Endpoints

### `GET /dashboard` - Admin Dashboard ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Access the admin dashboard HTML interface.

**Request:**
```bash
curl -X GET http://localhost:8000/dashboard
```

**Response (200 OK):**
```html
<!DOCTYPE html>
<html>
  <head>
    <title>Agentic Brain Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    ...
  </head>
  <body>
    <div id="app"></div>
    <script src="/static/dashboard.js"></script>
  </body>
</html>
```

---

### `GET /dashboard/api/stats` - System Statistics ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get current system metrics and performance data.

**Request:**
```bash
curl -X GET http://localhost:8000/dashboard/api/stats
```

**With Specific Metrics:**
```bash
curl -X GET "http://localhost:8000/dashboard/api/stats?metrics=sessions,memory,cpu"
```

**Response (200 OK):**
```json
{
  "timestamp": "2026-01-15T10:30:45.123Z",
  "sessions_active": 12,
  "total_messages": 1250,
  "memory_usage_mb": 356.4,
  "memory_percent": 22.3,
  "uptime_seconds": 8145,
  "cpu_percent": 23.5,
  "requests_per_minute": 45,
  "average_response_time_ms": 125,
  "errors_last_hour": 2
}
```

---

### `GET /dashboard/api/health` - Dashboard Health Status ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get comprehensive health status for the dashboard.

**Request:**
```bash
curl -X GET http://localhost:8000/dashboard/api/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "neo4j_connected": true,
  "llm_provider_available": true,
  "memory_ok": true,
  "redis_connected": true,
  "redpanda_connected": true,
  "timestamp": "2026-01-15T10:30:45.123Z",
  "details": {
    "neo4j": {
      "latency_ms": 3.5,
      "status": "ok"
    },
    "redis": {
      "latency_ms": 1.2,
      "status": "ok"
    }
  }
}
```

---

### `GET /dashboard/api/sessions` - List Active Sessions ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get all currently active sessions with metadata.

**Request:**
```bash
curl -X GET 'http://localhost:8000/dashboard/api/sessions?limit=20'
```

**With Filtering:**
```bash
curl -X GET "http://localhost:8000/dashboard/api/sessions?limit=20&user_id=user_456"
```

**With Sorting:**
```bash
curl -X GET "http://localhost:8000/dashboard/api/sessions?limit=20&sort=last_accessed&order=desc"
```

**Response (200 OK):**
```json
{
  "sessions": [
    {
      "id": "sess_abc123",
      "user_id": "user_456",
      "created_at": "2026-01-15T09:00:00.000Z",
      "last_accessed": "2026-01-15T10:30:45.123Z",
      "message_count": 14,
      "status": "active"
    },
    {
      "id": "sess_xyz789",
      "user_id": "user_789",
      "created_at": "2026-01-15T08:00:00.000Z",
      "last_accessed": "2026-01-15T10:20:00.000Z",
      "message_count": 5,
      "status": "inactive"
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

---

### `DELETE /dashboard/api/sessions` - Clear All Sessions ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Remove all sessions (admin-only).

**Request:**
```bash
curl -X DELETE http://localhost:8000/dashboard/api/sessions \
  -H "Authorization: Bearer admin_token"
```

**With Confirmation:**
```bash
curl -X DELETE http://localhost:8000/dashboard/api/sessions \
  -H "Authorization: Bearer admin_token" \
  -H "X-Confirm: yes"
```

**Response (204 No Content):**
```
(empty body)
```

---

### `GET /dashboard/api/users` - List Users ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get all users (admin-only).

**Request:**
```bash
curl -X GET 'http://localhost:8000/dashboard/api/users?limit=50' \
  -H "Authorization: Bearer admin_token"
```

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": "user_123",
      "email": "user@example.com",
      "name": "John Doe",
      "created_at": "2026-01-01T00:00:00.000Z",
      "last_login": "2026-01-15T10:30:45.123Z",
      "roles": ["ROLE_USER"]
    }
  ],
  "total": 1
}
```

---

### `GET /dashboard/api/audit-log` - Audit Log ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get audit/activity logs.

**Request:**
```bash
curl -X GET 'http://localhost:8000/dashboard/api/audit-log?limit=100' \
  -H "Authorization: Bearer admin_token"
```

**Response (200 OK):**
```json
{
  "events": [
    {
      "timestamp": "2026-01-15T10:30:45.123Z",
      "user_id": "user_123",
      "action": "chat_message_sent",
      "resource": "sess_abc123",
      "details": {
        "message_length": 42,
        "model": "llama3.1:8b"
      }
    }
  ],
  "total": 1
}
```

---

### `POST /dashboard/api/backup` - Create Backup ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Trigger a system backup.

**Request:**
```bash
curl -X POST http://localhost:8000/dashboard/api/backup \
  -H "Authorization: Bearer admin_token" \
  -H "Content-Type: application/json" \
  -d '{
    "include_neo4j": true,
    "include_redis": true
  }'
```

**Response (200 OK):**
```json
{
  "backup_id": "backup_abc123",
  "status": "started",
  "timestamp": "2026-01-15T10:30:45.123Z"
}
```

---

### `GET /dashboard/api/providers` - LLM Providers Status ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get status of all LLM providers.

**Request:**
```bash
curl -X GET http://localhost:8000/dashboard/api/providers \
  -H "Authorization: Bearer admin_token"
```

**Response (200 OK):**
```json
{
  "providers": [
    {
      "name": "groq",
      "status": "ok",
      "models": 2,
      "latency_ms": 125,
      "last_checked": "2026-01-15T10:30:45.123Z"
    },
    {
      "name": "ollama",
      "status": "ok",
      "models": 3,
      "latency_ms": 85,
      "last_checked": "2026-01-15T10:30:45.123Z"
    }
  ]
}
```

---

## 8️⃣ Commerce/Webhooks Endpoints

### `POST /webhooks/woocommerce` - WooCommerce Events ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Receive and process WooCommerce events.

**Authentication:** HMAC-SHA256 signature verification

**Request Headers:**
```
X-WC-Webhook-Signature: base64_encoded_hmac
X-WC-Webhook-Topic: order.created
Content-Type: application/json
```

**Configuration:**
```bash
WOOCOMMERCE_WEBHOOK_SECRET=your_webhook_secret
# Or alternatively:
COMMERCE_WOOCOMMERCE_WEBHOOK_SECRET=your_webhook_secret
```

**Supported Events:**
| Event | Topic |
|-------|-------|
| Order Created | `order.created` |
| Order Updated | `order.updated` |
| Order Deleted | `order.deleted` |
| Product Created | `product.created` |
| Product Updated | `product.updated` |
| Product Deleted | `product.deleted` |
| Customer Created | `customer.created` |
| Customer Updated | `customer.updated` |

**Example Request - Order Created:**
```bash
curl -X POST http://localhost:8000/webhooks/woocommerce \
  -H "X-WC-Webhook-Signature: qS2qE4I3J5K8L2M9N1O5P7Q3R6S8T0U=" \
  -H "X-WC-Webhook-Topic: order.created" \
  -H "X-WC-Webhook-ID: 123456" \
  -H "X-WC-Webhook-Delivery-ID: abc123xyz" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 12345,
    "number": "100001",
    "status": "processing",
    "customer": {
      "id": 999,
      "email": "customer@example.com",
      "first_name": "John",
      "last_name": "Doe"
    },
    "total": "99.99",
    "currency": "USD",
    "line_items": [
      {
        "id": 1,
        "product_id": 100,
        "name": "Product Name",
        "quantity": 1,
        "price": "99.99"
      }
    ],
    "billing": {
      "first_name": "John",
      "last_name": "Doe",
      "address_1": "123 Main St",
      "city": "New York",
      "state": "NY",
      "postcode": "10001",
      "country": "US"
    }
  }'
```

**Example Request - Product Updated:**
```bash
curl -X POST http://localhost:8000/webhooks/woocommerce \
  -H "X-WC-Webhook-Signature: abc123..." \
  -H "X-WC-Webhook-Topic: product.updated" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 100,
    "name": "Product Name",
    "description": "Product description",
    "price": "99.99",
    "sku": "PROD-100",
    "stock_quantity": 50,
    "categories": [
      {
        "id": 10,
        "name": "Electronics"
      }
    ]
  }'
```

**Response (204 No Content):**
```
(empty body)
```

**Error Responses:**

```json
// Invalid signature (401)
{
  "error": "Invalid webhook signature",
  "detail": "HMAC verification failed"
}
```

```json
// Invalid payload (400)
{
  "error": "Invalid webhook payload",
  "detail": "Missing required fields: id, status"
}
```

```json
// Server error (500)
{
  "error": "Failed to process webhook",
  "detail": "Database connection error"
}
```

---

### `POST /webhooks/stripe` - Stripe Payment Events ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Receive and process Stripe webhook events.

**Request:**
```bash
curl -X POST http://localhost:8000/webhooks/stripe \
  -H "Stripe-Signature: t=1234567890,v1=abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "id": "evt_1234567890",
    "object": "event",
    "api_version": "2023-08-16",
    "created": 1234567890,
    "data": {
      "object": {
        "id": "ch_1234567890",
        "object": "charge",
        "amount": 9999,
        "currency": "usd",
        "status": "succeeded"
      }
    },
    "type": "charge.succeeded"
  }'
```

**Response (200 OK):**
```json
{
  "received": true,
  "event_id": "evt_1234567890"
}
```

---

### `POST /webhooks/github` - GitHub Events ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Receive and process GitHub webhook events.

**Request:**
```bash
curl -X POST http://localhost:8000/webhooks/github \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: sha256=abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "ref": "refs/heads/main",
    "before": "abc123...",
    "after": "def456...",
    "repository": {
      "id": 123456,
      "name": "agentic-brain",
      "full_name": "org/agentic-brain"
    },
    "pusher": {
      "name": "developer",
      "email": "dev@example.com"
    },
    "commits": [
      {
        "id": "def456...",
        "message": "Add new features"
      }
    ]
  }'
```

**Response (204 No Content):**
```
(empty body)
```

---

### `GET /webhooks` - List Active Webhooks ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

List all registered webhooks (admin-only).

**Request:**
```bash
curl -X GET http://localhost:8000/webhooks \
  -H "Authorization: Bearer admin_token"
```

**Response (200 OK):**
```json
{
  "webhooks": [
    {
      "id": "webhook_abc123",
      "provider": "woocommerce",
      "url": "http://localhost:8000/webhooks/woocommerce",
      "events": ["order.created", "order.updated"],
      "active": true,
      "created_at": "2026-01-01T00:00:00.000Z"
    },
    {
      "id": "webhook_def456",
      "provider": "stripe",
      "url": "http://localhost:8000/webhooks/stripe",
      "events": ["charge.succeeded"],
      "active": true,
      "created_at": "2026-01-01T00:00:00.000Z"
    }
  ]
}
```

---

### `POST /webhooks/test/{provider}` - Test Webhook ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Send a test webhook event.

**Request:**
```bash
curl -X POST http://localhost:8000/webhooks/test/woocommerce \
  -H "Authorization: Bearer admin_token" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "order.created"
  }'
```

**Response (200 OK):**
```json
{
  "status": "sent",
  "event_id": "test_abc123",
  "timestamp": "2026-01-15T10:30:45.123Z"
}
```

---

## 9️⃣ Workflows Endpoints

### `POST /workflows` - Create Workflow ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Create a new workflow definition.

**Request:**
```bash
curl -X POST http://localhost:8000/workflows \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Escalation",
    "description": "Route complex queries to human agents",
    "trigger": {
      "type": "chat",
      "condition": "sentiment == negative"
    },
    "steps": [
      {
        "id": "step1",
        "name": "Analyze Sentiment",
        "type": "ai",
        "config": {
          "model": "groq",
          "prompt": "Analyze sentiment..."
        }
      },
      {
        "id": "step2",
        "name": "Create Ticket",
        "type": "webhook",
        "config": {
          "url": "https://ticketing-system.example.com/api/tickets",
          "method": "POST"
        }
      }
    ],
    "enabled": true
  }'
```

**Response (201 Created):**
```json
{
  "id": "workflow_abc123",
  "name": "Customer Support Escalation",
  "status": "active",
  "created_at": "2026-01-15T10:30:45.123Z",
  "created_by": "user_123"
}
```

---

### `GET /workflows` - List Workflows ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get all workflows.

**Request:**
```bash
curl -X GET http://localhost:8000/workflows \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**With Filtering:**
```bash
curl -X GET "http://localhost:8000/workflows?status=active&limit=20"
```

**Response (200 OK):**
```json
{
  "workflows": [
    {
      "id": "workflow_abc123",
      "name": "Customer Support Escalation",
      "status": "active",
      "trigger": "chat",
      "created_at": "2026-01-15T10:30:45.123Z",
      "executions": 45
    }
  ],
  "total": 1
}
```

---

### `GET /workflows/{workflow_id}` - Get Workflow Details ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get detailed workflow information.

**Request:**
```bash
curl -X GET http://localhost:8000/workflows/workflow_abc123 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "id": "workflow_abc123",
  "name": "Customer Support Escalation",
  "description": "Route complex queries to human agents",
  "status": "active",
  "trigger": {
    "type": "chat",
    "condition": "sentiment == negative"
  },
  "steps": [
    {
      "id": "step1",
      "name": "Analyze Sentiment",
      "type": "ai",
      "config": {
        "model": "groq",
        "prompt": "Analyze sentiment..."
      }
    }
  ],
  "created_at": "2026-01-15T10:30:45.123Z",
  "last_modified": "2026-01-15T10:30:45.123Z"
}
```

---

### `PUT /workflows/{workflow_id}` - Update Workflow ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Update an existing workflow.

**Request:**
```bash
curl -X PUT http://localhost:8000/workflows/workflow_abc123 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Advanced Customer Support Escalation",
    "enabled": true
  }'
```

**Response (200 OK):**
```json
{
  "id": "workflow_abc123",
  "name": "Advanced Customer Support Escalation",
  "status": "updated",
  "last_modified": "2026-01-15T10:30:45.123Z"
}
```

---

### `DELETE /workflows/{workflow_id}` - Delete Workflow ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Delete a workflow.

**Request:**
```bash
curl -X DELETE http://localhost:8000/workflows/workflow_abc123 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (204 No Content):**
```
(empty body)
```

---

### `GET /workflows/{workflow_id}/executions` - List Workflow Executions ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get execution history of a workflow.

**Request:**
```bash
curl -X GET 'http://localhost:8000/workflows/workflow_abc123/executions?limit=50' \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "executions": [
    {
      "id": "exec_001",
      "workflow_id": "workflow_abc123",
      "status": "completed",
      "started_at": "2026-01-15T10:30:45.123Z",
      "completed_at": "2026-01-15T10:30:50.000Z",
      "duration_ms": 4877,
      "result": {
        "sentiment": "negative",
        "ticket_id": "TK-12345"
      }
    }
  ],
  "total": 45
}
```

---

### `POST /workflows/{workflow_id}/test` - Test Workflow ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Test a workflow with sample data.

**Request:**
```bash
curl -X POST http://localhost:8000/workflows/workflow_abc123/test \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "This is terrible! Your service is horrible.",
    "session_id": "sess_test123"
  }'
```

**Response (200 OK):**
```json
{
  "success": true,
  "execution_id": "test_exec_001",
  "steps_executed": 2,
  "result": {
    "sentiment": "negative",
    "escalation": true,
    "ticket_created": true
  },
  "duration_ms": 1250
}
```

---

### `POST /workflows/{workflow_id}/enable` - Enable Workflow ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Enable a workflow.

**Request:**
```bash
curl -X POST http://localhost:8000/workflows/workflow_abc123/enable \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "id": "workflow_abc123",
  "status": "enabled",
  "timestamp": "2026-01-15T10:30:45.123Z"
}
```

---

### `POST /workflows/{workflow_id}/disable` - Disable Workflow ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Disable a workflow.

**Request:**
```bash
curl -X POST http://localhost:8000/workflows/workflow_abc123/disable \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "id": "workflow_abc123",
  "status": "disabled",
  "timestamp": "2026-01-15T10:30:45.123Z"
}
```

---

## 1️⃣4️⃣ Batch Processing Endpoints

### `POST /batch/create` - Create Batch Job ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Submit a batch of requests for processing.

**Request:**
```bash
curl -X POST http://localhost:8000/batch/create \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {
        "id": "req_001",
        "message": "What is AI?"
      },
      {
        "id": "req_002",
        "message": "Explain machine learning"
      }
    ],
    "session_id": "sess_batch123"
  }'
```

**Response (201 Created):**
```json
{
  "batch_id": "batch_abc123",
  "status": "queued",
  "requests_count": 2,
  "created_at": "2026-01-15T10:30:45.123Z"
}
```

---

### `GET /batch/{batch_id}` - Get Batch Status ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get the status of a batch job.

**Request:**
```bash
curl -X GET http://localhost:8000/batch/batch_abc123 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "batch_id": "batch_abc123",
  "status": "processing",
  "requests_total": 2,
  "requests_completed": 1,
  "requests_pending": 1,
  "progress_percent": 50,
  "created_at": "2026-01-15T10:30:45.123Z",
  "estimated_completion": "2026-01-15T10:35:45.123Z"
}
```

---

### `GET /batch/{batch_id}/results` - Get Batch Results ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Get results of a completed batch job.

**Request:**
```bash
curl -X GET http://localhost:8000/batch/batch_abc123/results \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (200 OK):**
```json
{
  "batch_id": "batch_abc123",
  "status": "completed",
  "results": [
    {
      "id": "req_001",
      "response": "Artificial Intelligence (AI) is...",
      "status": "success",
      "timestamp": "2026-01-15T10:30:50.000Z"
    },
    {
      "id": "req_002",
      "response": "Machine learning is a subset of AI...",
      "status": "success",
      "timestamp": "2026-01-15T10:31:00.000Z"
    }
  ],
  "completed_at": "2026-01-15T10:31:05.000Z"
}
```

---

### `DELETE /batch/{batch_id}` - Cancel Batch ❌ TODO: Not Implemented

> **⚠️ This endpoint is documented for future implementation but does not currently exist.**

Cancel a batch job.

**Request:**
```bash
curl -X DELETE http://localhost:8000/batch/batch_abc123 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response (204 No Content):**
```
(empty body)
```

---

## 🚨 Error Handling

All endpoints follow consistent error response format:

**Standard Error Response:**
```json
{
  "error": "Error type",
  "detail": "Human-readable error message",
  "status_code": 400
}
```

**Validation Error Response (422):**
```json
{
  "error": "Validation failed",
  "detail": [
    {
      "field": "message",
      "type": "string_type",
      "message": "Input should be a valid string"
    }
  ]
}
```

**HTTP Status Codes:**

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Request succeeded |
| 204 | No Content | Successful deletion |
| 400 | Bad Request | Invalid message length |
| 401 | Unauthorized | Missing/invalid auth token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Session doesn't exist |
| 422 | Validation Error | Pydantic validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Internal exception |
| 503 | Service Unavailable | Critical dependency down |

---

## 🔒 Security & Headers

All responses include security headers:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

---

## 📚 SDK & Libraries

**Official Clients:**
- Python: `agentic_brain.client` (Coming soon)
- JavaScript/TypeScript: `agentic-brain-js` (Coming soon)

**Third-party Integrations:**
- LangChain support
- LlamaIndex support
- OpenAI-compatible SDK

---

## 🔗 References

- **Interactive Docs:** [Swagger UI](http://localhost:8000/docs)
- **API Schema:** [ReDoc](http://localhost:8000/redoc) | [OpenAPI JSON](http://localhost:8000/openapi.json)
- **Source Code:** [GitHub](https://github.com/your-org/agentic-brain)
- **Issues & Feedback:** [GitHub Issues](https://github.com/your-org/agentic-brain/issues)

---

*Documentation Version: 1.0.0 | Last Updated: 2026-01-15*
