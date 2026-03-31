# Agentic Brain API Documentation

The **Agentic Brain API** is a production-ready orchestration platform for AI agents, providing GraphRAG memory, multi-LLM routing, and real-time chat capabilities.

## 🚀 Quick Start

### Installation

```bash
pip install agentic-brain
```

### Basic Usage (Python)

```python
import agentic_brain

# Initialize the client
client = agentic_brain.Client(base_url="http://localhost:8000")

# Send a message
response = client.chat.send(
    message="What is GraphRAG?",
    session_id="sess_user_123"
)
print(response.response)
```

### Streaming Response (Python)

```python
# Stream a response
for chunk in client.chat.stream(
    message="Explain machine learning",
    provider="groq",
    model="mixtral-8x7b"
):
    print(chunk.token, end="", flush=True)
```

### WebSocket Chat (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat?token=your_jwt_token');

ws.onopen = () => {
  ws.send(JSON.stringify({
    message: "Tell me about AI",
    session_id: "sess_user_456"
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.token) {
    process.stdout.write(data.token);
  }
};
```

---

## 📚 Interactive Documentation

Access the API documentation at:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
  - Interactive endpoint testing
  - Request/response examples
  - Parameter validation
  
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
  - Clean, organized reference
  - Searchable documentation
  - Grouped by category

- **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
  - Raw OpenAPI 3.0 specification
  - Machine-readable format

---

## 🔐 Authentication

### Configuration

Enable authentication:

```bash
export AUTH_ENABLED=true
export API_KEYS=key1,key2,key3
export JWT_SECRET=your-secret-key
```

### Methods

**1. API Key (Header)**
```bash
curl -H "X-API-Key: your_api_key" http://localhost:8000/health
```

**2. API Key (Query Parameter)**
```bash
curl http://localhost:8000/health?api_key=your_api_key
```

**3. JWT Token**
```bash
curl -H "Authorization: Bearer eyJhbGc..." http://localhost:8000/health
```

**4. WebSocket JWT**
```javascript
ws = new WebSocket('ws://localhost:8000/ws/chat?token=your_jwt_token');
```

---

## 💬 Chat Endpoints

### Send Message (Sync)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is vector search?",
    "session_id": "sess_123",
    "user_id": "user_456"
  }'
```

**Response:**
```json
{
  "response": "Vector search is...",
  "session_id": "sess_123",
  "message_id": "msg_789",
  "timestamp": "2026-01-15T10:30:45.123Z"
}
```

### Stream Response (SSE)

```bash
curl -X GET 'http://localhost:8000/chat/stream?message=What%20is%20AI%3F&provider=ollama&model=llama3.1:8b' \
  -H "Authorization: Bearer your_token"
```

**Response (Server-Sent Events):**
```
data: {"token":"Machine","is_start":true,"is_end":false}
data: {"token":" learning","is_start":false,"is_end":false}
data: {"token":".","is_start":false,"is_end":true,"finish_reason":"stop"}
```

### WebSocket (Real-Time)

**Connect:**
```python
import websockets
import json

async def main():
    async with websockets.connect('ws://localhost:8000/ws/chat') as ws:
        await ws.send(json.dumps({"message": "Hello!"}))
        async for msg in ws:
            data = json.loads(msg)
            print(data['token'], end='', flush=True)
```

---

## 🗂️ Session Management

### Get Session Info

```bash
curl -X GET http://localhost:8000/session/sess_123 \
  -H "Authorization: Bearer your_token"
```

**Response:**
```json
{
  "id": "sess_123",
  "message_count": 14,
  "created_at": "2026-01-15T09:00:00.000Z",
  "last_accessed": "2026-01-15T10:30:45.123Z",
  "user_id": "user_456"
}
```

### Get Chat History

```bash
curl -X GET 'http://localhost:8000/session/sess_123/messages?limit=50' \
  -H "Authorization: Bearer your_token"
```

**Response:**
```json
[
  {
    "id": "msg_001",
    "role": "user",
    "content": "What is GraphRAG?",
    "timestamp": "2026-01-15T10:00:00.000Z"
  },
  {
    "id": "msg_002",
    "role": "assistant",
    "content": "GraphRAG is...",
    "timestamp": "2026-01-15T10:00:05.000Z"
  }
]
```

### Delete Session

```bash
curl -X DELETE http://localhost:8000/session/sess_123 \
  -H "Authorization: Bearer your_token"
```

---

## 🔧 Setup & Configuration

### Check LLM Providers

```bash
curl -X GET http://localhost:8000/setup
```

**Response:**
```json
{
  "status": "configured",
  "message": "✓ 3 provider(s) ready",
  "providers": {
    "available": [
      {"name": "groq", "reason": "API key configured"},
      {"name": "ollama", "reason": "Local server available"},
      {"name": "openai", "reason": "API key configured"}
    ],
    "unavailable": [
      {"name": "anthropic", "reason": "Missing API key"}
    ]
  }
}
```

### Get Provider Help

```bash
curl -X GET http://localhost:8000/setup/help/groq
```

---

## 📊 Health & Monitoring

### System Health

```bash
curl -X GET http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "sessions_active": 5,
  "redis": {"status": "ok", "available": true},
  "llm": {"provider": "groq", "status": "ok"},
  "neo4j": {"status": "configured"},
  "uptime": "2h 15m 30s"
}
```

### Infrastructure Health

```bash
curl -X GET http://localhost:8000/infra/health
```

**Response:**
```json
{
  "status": "healthy",
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
      "nodes": 1250
    },
    "redpanda": {
      "status": "ok",
      "available": true,
      "brokers": 3
    }
  }
}
```

### Kubernetes Probes

```bash
# Liveness
curl -X GET http://localhost:8000/healthz

# Readiness
curl -X GET http://localhost:8000/readyz
```

---

## 🔑 Authentication Endpoints

### SAML SSO

**Initiate:**
```bash
curl -X POST http://localhost:8000/auth/saml/login
```

**Callback:**
```bash
curl -X POST http://localhost:8000/auth/saml/acs \
  -d '{"saml_response": "..."}'
```

**Metadata:**
```bash
curl -X GET http://localhost:8000/auth/saml/metadata
```

### OAuth2/OIDC

**Get Authorization URL:**
```bash
curl -X GET 'http://localhost:8000/auth/sso/google/login'
```

**Handle Callback:**
```bash
curl -X GET 'http://localhost:8000/auth/sso/google/callback?code=4/0AX4X...'
```

**Supported Providers:** google, github, microsoft, okta, generic

---

## 📈 Rate Limiting

Rate limits are applied per IP/user:

| Type | Limit |
|------|-------|
| Anonymous | 60 req/min |
| Authenticated | 100 req/min |
| Login Attempts | 5 req/min |
| WebSocket | 50 msg/min |

**Response Headers:**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1234567890
```

**When Rate Limited:**
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## 🎯 Common Patterns

### Multi-turn Conversation

```python
session_id = "sess_" + str(uuid.uuid4())

# Turn 1
response1 = client.chat.send(
    message="What is machine learning?",
    session_id=session_id
)

# Turn 2 - context preserved
response2 = client.chat.send(
    message="How does supervised learning work?",
    session_id=session_id
)

# Retrieve history
history = client.session.get_messages(session_id)
```

### Streaming with Custom Provider

```python
for chunk in client.chat.stream(
    message="Generate a story",
    provider="anthropic",
    model="claude-3-opus-20240229",
    temperature=0.8
):
    print(chunk.token, end="", flush=True)
```

### Error Handling

```python
try:
    response = client.chat.send(message="Hello")
except agentic_brain.AuthenticationError:
    print("Invalid credentials")
except agentic_brain.RateLimitError:
    print("Rate limited, retry after 60s")
except agentic_brain.ValidationError as e:
    print(f"Invalid input: {e.detail}")
except Exception as e:
    print(f"Error: {e}")
```

---

## 🌐 Supported LLM Providers

| Provider | Status | Models |
|----------|--------|--------|
| **Ollama** | ✓ Local | llama3.1, mistral, llama2, etc. |
| **Groq** | ✓ Cloud | mixtral-8x7b, llama-2-70b |
| **OpenAI** | ✓ Cloud | gpt-4, gpt-3.5-turbo |
| **Anthropic** | ✓ Cloud | claude-3-opus, claude-3-sonnet |
| **Google** | ✓ Cloud | gemini-pro |
| **Together** | ✓ Cloud | Multiple open models |
| **OpenRouter** | ✓ Cloud | 200+ models |
| **xAI** | ✓ Cloud | grok-1 |

---

## 📋 API Features

✅ **Real-time Streaming** - SSE and WebSocket support  
✅ **Multi-LLM Routing** - Automatic provider fallback  
✅ **GraphRAG Memory** - Neo4j-backed knowledge graphs  
✅ **Session Management** - Persistent conversation history  
✅ **Enterprise Auth** - SAML, OAuth2, OIDC, JWT, API keys  
✅ **Rate Limiting** - Token bucket with per-IP/user limits  
✅ **Health Monitoring** - Kubernetes-ready probes  
✅ **Webhook Support** - WooCommerce integration  
✅ **Dashboard** - Admin interface for monitoring  

---

## 🚀 Deployment

### Docker

```bash
docker run -d \
  -p 8000:8000 \
  -e AUTH_ENABLED=true \
  -e JWT_SECRET=your-secret \
  agentic-brain:latest
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentic-brain
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentic-brain
  template:
    metadata:
      labels:
        app: agentic-brain
    spec:
      containers:
      - name: agentic-brain
        image: agentic-brain:latest
        ports:
        - containerPort: 8000
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## 🔗 Resources

- **API Reference:** [API_REFERENCE.md](./API_REFERENCE.md)
- **Full Endpoint Documentation:** [Swagger UI](http://localhost:8000/docs)
- **Architecture:** [NEO4J_ARCHITECTURE.md](./NEO4J_ARCHITECTURE.md)
- **Security:** [SECURITY.md](../SECURITY.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)
- **Examples:** [examples/](../examples/)

---

## ❓ FAQ

**Q: How do I enable authentication?**  
A: Set `AUTH_ENABLED=true` and configure API_KEYS or JWT_SECRET environment variables.

**Q: Which LLM provider should I use?**  
A: For local development, use Ollama. For production, use Groq (fast, free tier) or OpenAI.

**Q: How do I handle rate limits?**  
A: Check `X-RateLimit-Remaining` header. Wait `X-RateLimit-Reset` seconds before retrying.

**Q: Can I use WebSocket without authentication?**  
A: Yes, but production deployments require JWT tokens via query parameter or header.

**Q: How do I preserve conversation context?**  
A: Use the same `session_id` for multiple requests to maintain chat history.

---

*Documentation Version: 1.0.0 | Last Updated: 2026-01-15*
