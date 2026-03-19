# Agentic Brain Chatbot API

FastAPI server for agentic-brain chatbot with real-time WebSocket support.

## Features

- **Production-Ready** - CORS enabled, comprehensive error handling, request validation
- **RESTful Endpoints** - Chat, session management, health checks
- **WebSocket Support** - Real-time bidirectional communication
- **Automatic Documentation** - OpenAPI (Swagger) & ReDoc
- **Session Tracking** - Multi-user support with session history
- **Pydantic Models** - Type-safe request/response validation

## API Endpoints

### Health Check

```http
GET /health
```

Returns server status and active session count.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-01T12:00:00Z",
  "sessions_active": 5
}
```

### Chat

```http
POST /chat
Content-Type: application/json

{
  "message": "What is the weather?",
  "session_id": "sess_abc123",
  "user_id": "user_xyz789"
}
```

**Response (200 OK):**
```json
{
  "response": "Echo: What is the weather?",
  "session_id": "sess_abc123",
  "timestamp": "2026-01-01T12:00:00Z",
  "message_id": "msg_def456"
}
```

### Session Management

#### Get Session Info

```http
GET /session/{session_id}
```

**Response (200 OK):**
```json
{
  "id": "sess_abc123",
  "message_count": 5,
  "created_at": "2026-01-01T10:00:00Z",
  "last_accessed": "2026-01-01T12:30:00Z",
  "user_id": "user_xyz789"
}
```

#### Get Session Messages

```http
GET /session/{session_id}/messages?limit=50
```

**Response (200 OK):**
```json
[
  {
    "id": "msg_abc123",
    "role": "user",
    "content": "Hello",
    "timestamp": "2026-01-01T10:05:00Z"
  },
  {
    "id": "msg_def456",
    "role": "assistant",
    "content": "Echo: Hello",
    "timestamp": "2026-01-01T10:05:01Z"
  }
]
```

#### Delete Session

```http
DELETE /session/{session_id}
```

**Response (204 No Content):** Empty

#### Clear All Sessions

```http
DELETE /sessions
```

**Response (204 No Content):** Empty

### WebSocket Chat

```
ws://localhost:8000/ws/chat
```

**Connection Flow:**

1. Client connects
2. Server sends connection confirmation:
   ```json
   {
     "type": "connection",
     "session_id": "sess_abc123",
     "message": "Connected to chatbot",
     "timestamp": "2026-01-01T12:00:00Z"
   }
   ```

3. Client sends message:
   ```json
   {
     "message": "Hello bot!"
   }
   ```

4. Server responds:
   ```json
   {
     "type": "message",
     "id": "msg_xyz789",
     "content": "Echo: Hello bot!",
     "timestamp": "2026-01-01T12:00:01Z"
   }
   ```

5. Server sends errors (if any):
   ```json
   {
     "type": "error",
     "error": "Empty message",
     "timestamp": "2026-01-01T12:00:02Z"
   }
   ```

## Installation

### Prerequisites

- Python 3.8+
- pip or poetry

### Required Dependencies

```bash
pip install fastapi uvicorn pydantic
```

### Optional Dependencies

```bash
# For development and testing
pip install pytest pytest-asyncio httpx
```

## Usage

### Running the Server

#### Method 1: Direct Python

```bash
cd /path/to/brain/agentic-brain/src
python3 -m agentic_brain.api.server
```

Server starts at `http://0.0.0.0:8000`

#### Method 2: Using the Run Function

```python
from agentic_brain.api import run_server

run_server(host="0.0.0.0", port=8000, reload=True)
```

#### Method 3: Using Uvicorn Directly

```bash
uvicorn agentic_brain.api.server:app --host 0.0.0.0 --port 8000 --reload
```

### Documentation

Once running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Python Usage

```python
from agentic_brain.api import app, ChatRequest, ChatResponse
from fastapi.testclient import TestClient

client = TestClient(app)

# Health check
response = client.get("/health")
print(response.json())

# Send chat message
response = client.post("/chat", json={
    "message": "Hello!",
    "user_id": "user_123"
})
chat_response = ChatResponse(**response.json())
print(f"Session: {chat_response.session_id}")
print(f"Response: {chat_response.response}")

# Get session info
session_id = chat_response.session_id
response = client.get(f"/session/{session_id}")
print(response.json())

# Get messages
response = client.get(f"/session/{session_id}/messages")
print(response.json())

# Delete session
response = client.delete(f"/session/{session_id}")
```

### WebSocket Usage (Python)

```python
import asyncio
import websockets
import json

async def test_websocket():
    async with websockets.connect("ws://localhost:8000/ws/chat") as websocket:
        # Receive connection confirmation
        response = await websocket.recv()
        print(f"Connected: {response}")
        
        # Send message
        await websocket.send(json.dumps({"message": "Hello bot!"}))
        
        # Receive response
        response = await websocket.recv()
        print(f"Response: {response}")

asyncio.run(test_websocket())
```

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Chat message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello!","user_id":"user_123"}'

# Get session info
curl http://localhost:8000/session/{session_id}

# Get messages
curl "http://localhost:8000/session/{session_id}/messages?limit=10"

# Delete session
curl -X DELETE http://localhost:8000/session/{session_id}

# WebSocket (requires wscat: npm install -g wscat)
wscat -c ws://localhost:8000/ws/chat
```

## Configuration

### CORS Origins

Default CORS origins are localhost and 127.0.0.1 on ports 3000 and 8000.

To customize:

```python
from agentic_brain.api import create_app

app = create_app(
    cors_origins=[
        "https://example.com",
        "https://app.example.com",
        "http://localhost:3000"
    ]
)
```

### Server Configuration

```python
from agentic_brain.api import run_server

run_server(
    host="127.0.0.1",
    port=8000,
    reload=True,  # Auto-reload on file changes
    log_level="debug"  # Logging level
)
```

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "Session not found",
  "detail": "Session ID sess_invalid does not exist",
  "status_code": 404
}
```

### Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 204 | No Content - Successful deletion |
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource not found |
| 422 | Unprocessable Entity - Validation error |
| 500 | Internal Server Error - Server error |

## Project Structure

```
agentic_brain/api/
├── __init__.py          # Package exports
├── models.py            # Pydantic models
└── server.py            # FastAPI application
```

### Models

- **ChatRequest** - Message input with optional session/user tracking
- **ChatResponse** - Bot response with metadata
- **SessionInfo** - Session statistics and metadata
- **ErrorResponse** - Standardized error format

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/

# Run with coverage
pytest --cov=agentic_brain.api tests/
```

### Code Style

- Follow PEP 8
- Use type hints throughout
- Document all public functions/classes
- Add docstrings to endpoints

### Adding Custom Endpoints

```python
from agentic_brain.api import app

@app.get("/custom")
async def custom_endpoint():
    """Your custom endpoint."""
    return {"message": "Hello!"}
```

## Performance Considerations

- **In-Memory Storage** - Current implementation uses Python dicts. For production with high load:
  - Migrate to Redis for session storage
  - Use PostgreSQL for message history
  - Implement caching layer

- **Scaling** - Consider:
  - Load balancing with multiple server instances
  - Message queue (RabbitMQ, Celery) for long-running tasks
  - Database optimization and indexing

## Security

- ✅ CORS enabled (configurable)
- ✅ Input validation (Pydantic)
- ✅ Error messages don't leak sensitive info
- ✅ Type safety throughout

Additional recommendations:
- Use HTTPS in production
- Implement authentication (JWT, OAuth2)
- Add rate limiting
- Enable GZIP compression
- Use environment variables for configuration

## License

GPL-3.0-or-later © 2026 Joseph Webber

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
