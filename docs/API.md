# Agentic Brain API Documentation

The **Agentic Brain API** is a production-ready orchestration platform for AI agents, providing GraphRAG memory, multi-LLM routing, and real-time chat capabilities.

## 📚 Interactive Documentation

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs) (Interactive testing)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc) (Clean reference)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

## 🔐 Authentication

Authentication is managed via `AUTH_ENABLED` environment variable. When enabled, all endpoints require a valid API key or JWT token.

### Headers
```http
Authorization: Bearer <your-token>
X-API-Key: <your-api-key>
```

## 🚀 Key Endpoints

### 1. Real-time Chat
Interact with the brain using LLMs and memory.

- **POST /chat**: Standard synchronous chat
- **GET /chat/stream**: Server-Sent Events (SSE) streaming
- **WS /ws/chat**: WebSocket for bidirectional streaming

**Example (Python):**
```python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    json={
        "message": "Hello brain, what do you know about Neo4j?",
        "session_id": "sess_123",
        "provider": "anthropic"
    }
)
print(response.json())
```

### 2. Session Management
Manage conversation history and context.

- **GET /session/{id}**: Get session metadata
- **GET /session/{id}/messages**: Retrieve chat history
- **DELETE /session/{id}**: Clear session context

### 3. System Health
Monitor the brain's vitals.

- **GET /health**: Detailed system status (Redis, Neo4j, LLMs)
- **GET /setup**: Diagnostic report for LLM providers

**Example (curl):**
```bash
curl http://localhost:8000/health
```

## ⚡ Rate Limits

- **Standard**: 60 requests per minute per IP
- **WebSocket**: No explicit limit, but connections are monitored
- **Headers**: Check `X-RateLimit-Limit` and `X-RateLimit-Remaining`

## 🛠️ SDKs & Tools

- **Python Client**: `agentic_brain.client` (Coming soon)
- **CLI**: `agentic-brain chat`

## 🎨 Customization

The API documentation features a custom dark theme matching the Agentic Brain branding.
CSS source: `src/agentic_brain/static/swagger-ui.css`

---
*Generated for Agentic Brain v1.0.0*
