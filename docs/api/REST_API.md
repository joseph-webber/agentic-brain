# REST API Reference

## Overview

The Agentic Brain provides a comprehensive REST API for building AI-powered applications. The API follows OpenAPI 3.0 specification and supports:

- Real-time chat with streaming responses
- Multi-tenant session management
- GraphRAG knowledge retrieval
- WebSocket connections for live updates
- Enterprise security and audit logging

## Base URL

```
http://localhost:8000
```

## Authentication

All API endpoints require Bearer token authentication:

```bash
Authorization: Bearer your-jwt-token-here
```

## Rate Limiting

API endpoints are rate-limited to **60 requests per minute** per IP address.

Response headers indicate rate limit status:
- `X-RateLimit-Limit`: 60
- `X-RateLimit-Remaining`: Number of requests remaining
- `X-RateLimit-Reset`: Unix timestamp of window reset

## Endpoints

### Chat

#### POST /chat

Send a message and receive a response.

**Request:**
```json
{
  "message": "What is machine learning?",
  "session_id": "sess_abc123",
  "user_id": "user_xyz789",
  "metadata": {
    "source": "web_ui",
    "language": "en"
  }
}
```

**Response (200 OK):**
```json
{
  "message": "Machine learning is a subset of artificial intelligence...",
  "session_id": "sess_abc123",
  "timestamp": "2026-04-05T20:00:00Z",
  "model": "llama3.1:8b",
  "usage": {
    "input_tokens": 15,
    "output_tokens": 120,
    "total_tokens": 135
  }
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| message | string | Yes | The user's message (1-32000 chars) |
| session_id | string | No | Session ID for conversation tracking |
| user_id | string | No | User ID for multi-user support |
| metadata | object | No | Optional metadata (max 10KB) |

**Status Codes:**
- `200 OK` - Message processed successfully
- `400 Bad Request` - Invalid request format
- `401 Unauthorized` - Missing/invalid authentication
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

---

#### GET /chat/stream

Stream chat responses in real-time using Server-Sent Events (SSE).

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| message | string | Yes | The user's message |
| session_id | string | No | Session ID |
| user_id | string | No | User ID |

**Example:**
```bash
curl -N "http://localhost:8000/chat/stream?message=Hello&session_id=sess_123"
```

**Response:**
```
data: {"delta": "Hello", "timestamp": "2026-04-05T20:00:00Z"}
data: {"delta": " there", "timestamp": "2026-04-05T20:00:01Z"}
data: [DONE]
```

---

### Sessions

#### POST /sessions

Create a new chat session.

**Request:**
```json
{
  "user_id": "user_xyz789",
  "metadata": {
    "client_type": "web",
    "timezone": "UTC+10:30"
  }
}
```

**Response (201 Created):**
```json
{
  "session_id": "sess_abc123",
  "created_at": "2026-04-05T20:00:00Z",
  "user_id": "user_xyz789"
}
```

---

#### GET /sessions/{session_id}

Retrieve session information.

**Response:**
```json
{
  "session_id": "sess_abc123",
  "user_id": "user_xyz789",
  "created_at": "2026-04-05T20:00:00Z",
  "message_count": 5,
  "last_message_at": "2026-04-05T20:05:00Z"
}
```

---

#### GET /sessions/{session_id}/messages

List messages in a session.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | integer | 50 | Max messages to return |
| offset | integer | 0 | Message offset |
| sort | string | desc | Sort order (asc/desc) |

**Response:**
```json
{
  "messages": [
    {
      "id": "msg_1",
      "role": "user",
      "content": "Hello",
      "timestamp": "2026-04-05T20:00:00Z"
    },
    {
      "id": "msg_2",
      "role": "assistant",
      "content": "Hi there!",
      "timestamp": "2026-04-05T20:00:01Z"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

---

#### DELETE /sessions/{session_id}

Delete a session and all associated messages.

**Response (204 No Content)**

---

### Health & Monitoring

#### GET /health

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "version": "3.1.0",
  "uptime_seconds": 3600,
  "timestamp": "2026-04-05T20:00:00Z",
  "components": {
    "redis": "healthy",
    "neo4j": "healthy",
    "gpu": "healthy"
  }
}
```

---

#### GET /health/ready

Readiness probe for Kubernetes/Docker.

**Response (200 OK or 503 Service Unavailable)**

---

#### GET /metrics

Get API metrics and statistics.

**Response:**
```json
{
  "requests_total": 10000,
  "requests_per_minute": 45,
  "average_response_time_ms": 150,
  "error_rate": 0.001,
  "sessions_active": 42,
  "tokens_processed": 500000
}
```

---

### RAG API

#### POST /rag/query

Query the knowledge graph using RAG.

**Request:**
```json
{
  "query": "What are the benefits of GraphRAG?",
  "top_k": 5,
  "filters": {
    "source": "documentation",
    "language": "en"
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "doc_123",
      "content": "GraphRAG provides...",
      "score": 0.95,
      "source": "documentation",
      "metadata": {}
    }
  ],
  "query_time_ms": 120
}
```

---

#### POST /rag/index

Index documents for RAG retrieval.

**Request:**
```json
{
  "documents": [
    {
      "id": "doc_1",
      "content": "Document content...",
      "metadata": {
        "source": "file",
        "tags": ["important"]
      }
    }
  ],
  "index_name": "my_docs"
}
```

**Response:**
```json
{
  "indexed": 1,
  "errors": 0,
  "index_name": "my_docs"
}
```

---

### Configuration API

#### GET /config

Get current configuration settings.

**Response:**
```json
{
  "llm": {
    "provider": "ollama",
    "model": "llama3.1:8b",
    "temperature": 0.7,
    "top_p": 0.9
  },
  "memory": {
    "type": "neo4j",
    "uri": "bolt://localhost:7687",
    "cache_enabled": true
  },
  "security": {
    "rate_limit": 60,
    "audit_enabled": true
  }
}
```

---

#### PATCH /config

Update configuration settings.

**Request:**
```json
{
  "llm.temperature": 0.5,
  "memory.cache_enabled": false
}
```

---

### Memory API

#### GET /memory/{session_id}

Retrieve conversation memory for a session.

**Response:**
```json
{
  "session_id": "sess_abc123",
  "memory_type": "neo4j",
  "entities": [
    {
      "id": "entity_1",
      "type": "PERSON",
      "name": "Alice",
      "mentions": 3
    }
  ],
  "relationships": [
    {
      "source": "entity_1",
      "target": "entity_2",
      "type": "KNOWS",
      "count": 1
    }
  ],
  "topics": ["AI", "machine learning"]
}
```

---

#### POST /memory/{session_id}/clear

Clear session memory.

**Response (204 No Content)**

---

## Error Responses

All errors follow this format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "validation details"
  },
  "timestamp": "2026-04-05T20:00:00Z"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| INVALID_REQUEST | 400 | Request validation failed |
| UNAUTHORIZED | 401 | Authentication failed |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource conflict |
| RATE_LIMITED | 429 | Rate limit exceeded |
| INTERNAL_ERROR | 500 | Server error |

---

## WebSocket API

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws?session_id=sess_abc123&token=your-token');

ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};
```

### Message Format

**Client → Server:**
```json
{
  "type": "message",
  "content": "Hello!",
  "session_id": "sess_abc123"
}
```

**Server → Client:**
```json
{
  "type": "message",
  "role": "assistant",
  "content": "Hi there!",
  "timestamp": "2026-04-05T20:00:00Z"
}
```

---

## SDKs & Client Libraries

Official SDKs are available for:
- **Python**: `agentic-brain`
- **JavaScript/TypeScript**: `@agentic-brain/client`
- **Go**: `github.com/agentic-brain/go-client`

See [Python SDK](./PYTHON_API.md) for detailed examples.

---

## Rate Limits

- General: 60 requests/minute per IP
- Chat: 30 requests/minute per session
- Streaming: No limit (connection-based)

Upgrade for higher limits or contact support.

---

## See Also

- [Python API Documentation](./PYTHON_API.md)
- [CLI Reference](./CLI_API.md)
- [Code Examples](./EXAMPLES.md)
- [API Security](../SECURITY.md)
