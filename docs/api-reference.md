# API Reference

Complete REST API documentation for Agentic Brain.

---

## Base URL

```
http://localhost:8000
```

---

## Authentication

When `AUTH_ENABLED=true`, all endpoints require authentication.

### API Key

```bash
# Header
curl -H "X-API-Key: your-api-key" http://localhost:8000/chat

# Query parameter
curl "http://localhost:8000/chat?api_key=your-api-key"
```

### JWT Token

```bash
curl -H "Authorization: Bearer eyJhbG..." http://localhost:8000/chat
```

See [AUTHENTICATION.md](./AUTHENTICATION.md) for setup details.

---

## Rate Limiting

- **Limit**: 60 requests per minute per IP address
- **Window**: Rolling 60-second window
- **Response**: `429 Too Many Requests` when exceeded

```json
{
  "detail": "Rate limit exceeded. Maximum 60 requests per minute allowed."
}
```

---

## Endpoints

### Health Check

#### `GET /health`

Check API server health status.

**Response**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-20T10:30:45.123456+00:00",
  "sessions_active": 5
}
```

**Example**

```bash
curl http://localhost:8000/health
```

---

### Chat

#### `POST /chat`

Send a message and receive a response.

**Request Body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | User message (1-10000 chars) |
| `session_id` | string | No | Session ID (auto-generated if omitted) |
| `user_id` | string | No | User identifier for analytics |

**Request**

```json
{
  "message": "What is artificial intelligence?",
  "session_id": "sess_abc123",
  "user_id": "user_456"
}
```

**Response**

```json
{
  "response": "Artificial intelligence (AI) is...",
  "session_id": "sess_abc123",
  "message_id": "msg_xyz789",
  "timestamp": "2026-03-20T10:30:45.123456+00:00",
  "metadata": {}
}
```

**Example**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "session_id": "sess_123"}'
```

**Errors**

| Status | Description |
|--------|-------------|
| `400` | Invalid message (empty or too long) |
| `401` | Authentication required (if enabled) |
| `422` | Validation error |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

---

### Streaming Chat

#### `GET /chat/stream`

Stream chat response using Server-Sent Events (SSE).

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `message` | string | Yes | - | User message (1-10000 chars) |
| `session_id` | string | No | Auto | Session ID |
| `user_id` | string | No | - | User identifier |
| `provider` | string | No | `ollama` | LLM provider |
| `model` | string | No | `llama3.1:8b` | Model name |
| `temperature` | float | No | `0.7` | Sampling temperature (0.0-2.0) |

**Response (Server-Sent Events)**

```
event: stream
data: {"token": "Hello", "is_start": true, "is_end": false}

event: stream
data: {"token": " there", "is_start": false, "is_end": false}

event: stream
data: {"token": "!", "is_start": false, "is_end": true, "finish_reason": "stop"}
```

**Token Object**

| Field | Type | Description |
|-------|------|-------------|
| `token` | string | Token text |
| `is_start` | boolean | True for first token |
| `is_end` | boolean | True for final token |
| `finish_reason` | string | `"stop"`, `"length"`, or `"error"` |
| `metadata` | object | Additional data (provider, model) |

**Example (curl)**

```bash
curl "http://localhost:8000/chat/stream?message=What%20is%20AI?"
```

**Example (JavaScript)**

```javascript
const eventSource = new EventSource(
  '/chat/stream?message=' + encodeURIComponent('What is AI?')
);

eventSource.onmessage = (event) => {
  const token = JSON.parse(event.data);
  document.body.textContent += token.token;
  
  if (token.is_end) {
    eventSource.close();
  }
};

eventSource.onerror = () => {
  eventSource.close();
};
```

---

### Sessions

#### `GET /sessions`

List all active sessions.

**Response**

```json
{
  "sessions": [
    {
      "id": "sess_abc123",
      "user_id": "user_456",
      "created_at": "2026-03-20T10:00:00+00:00",
      "last_accessed": "2026-03-20T10:30:00+00:00",
      "message_count": 15
    }
  ]
}
```

---

#### `GET /session/{session_id}`

Get session details.

**Response**

```json
{
  "id": "sess_abc123",
  "user_id": "user_456",
  "created_at": "2026-03-20T10:00:00+00:00",
  "last_accessed": "2026-03-20T10:30:00+00:00",
  "message_count": 15
}
```

**Errors**

| Status | Description |
|--------|-------------|
| `404` | Session not found |

---

#### `GET /session/{session_id}/messages`

Get conversation history for a session.

**Response**

```json
{
  "session_id": "sess_abc123",
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "Hello!",
      "timestamp": "2026-03-20T10:00:00+00:00"
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": "Hi there! How can I help you?",
      "timestamp": "2026-03-20T10:00:01+00:00"
    }
  ]
}
```

---

#### `DELETE /session/{session_id}`

Delete a specific session.

**Response**

```json
{
  "deleted": true,
  "session_id": "sess_abc123"
}
```

---

#### `DELETE /sessions`

Delete all sessions (admin endpoint).

**Response**

```json
{
  "deleted_count": 42
}
```

---

### WebSocket

#### `WS /ws/chat`

WebSocket endpoint for bidirectional chat.

**Connect**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');
```

**Send Message**

```json
{
  "message": "What is AI?",
  "session_id": "sess_123",
  "user_id": "user_456",
  "provider": "ollama",
  "model": "llama3.1:8b",
  "temperature": 0.7
}
```

**Receive Response (streaming)**

```json
{
  "token": "Artificial",
  "is_start": true,
  "is_end": false,
  "finish_reason": null,
  "metadata": {
    "provider": "ollama",
    "model": "llama3.1:8b"
  }
}
```

**Example (JavaScript)**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onopen = () => {
  ws.send(JSON.stringify({
    message: "What is AI?",
    session_id: "sess_123"
  }));
};

ws.onmessage = (event) => {
  const token = JSON.parse(event.data);
  console.log(token.token);
};
```

---

## Response Codes

| Code | Description |
|------|-------------|
| `200` | Success |
| `400` | Bad request (validation error) |
| `401` | Unauthorized (auth enabled) |
| `403` | Forbidden (insufficient permissions) |
| `404` | Not found |
| `422` | Unprocessable entity |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

---

## Error Format

All errors return JSON:

```json
{
  "detail": "Error message here"
}
```

Validation errors include field details:

```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Pagination

Endpoints that return lists support pagination:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `limit` | `50` | Max items to return |
| `offset` | `0` | Items to skip |

---

## See Also

- [STREAMING.md](./STREAMING.md) — Detailed streaming documentation
- [AUTHENTICATION.md](./AUTHENTICATION.md) — Auth setup
- [api/index.md](./api/index.md) — Core module API reference

---

**Last Updated**: 2026-03-20
