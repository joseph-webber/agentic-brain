# Agentic Brain API - Quick Start Guide

## Installation

### 1. Install the API module with dependencies

From the project root (`/Users/joe/brain/agentic-brain`):

```bash
# Install with API support
pip install -e ".[api]"

# Or install all dependencies (including dev, api, llm)
pip install -e ".[all]"
```

### 2. Verify installation

```bash
python3 -c "from agentic_brain.api import app; print('✓ FastAPI API installed successfully')"
```

## Running the Server

### Option 1: Direct Python

```bash
cd /Users/joe/brain/agentic-brain/src
python3 -m agentic_brain.api.server
```

Server will start at: **http://localhost:8000**

### Option 2: Using Uvicorn

```bash
cd /Users/joe/brain/agentic-brain
uvicorn agentic_brain.api.server:app --host 0.0.0.0 --port 8000 --reload
```

### Option 3: Development with auto-reload

```bash
cd /Users/joe/brain/agentic-brain
uvicorn agentic_brain.api.server:app --reload
```

## Accessing the API

Once the server is running:

### Interactive API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Health Check
```bash
curl http://localhost:8000/health
```

### Send a Chat Message
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello bot!"}'
```

## Testing

### Install test dependencies

```bash
pip install pytest pytest-asyncio httpx
```

### Run tests

```bash
# From project root
pytest agentic_brain/api/test_api.py -v

# Run with coverage
pytest agentic_brain/api/test_api.py --cov=agentic_brain.api -v
```

## WebSocket Testing

### Using wscat (Node.js)

```bash
# Install wscat
npm install -g wscat

# Connect to WebSocket
wscat -c ws://localhost:8000/ws/chat

# In the wscat terminal, send JSON:
{"message": "Hello bot!"}
```

### Using Python

Create `test_ws.py`:

```python
import asyncio
import json
import websockets

async def test():
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        # Receive connection confirmation
        msg = await ws.recv()
        print(f"Server: {msg}")
        
        # Send message
        await ws.send(json.dumps({"message": "Hello bot!"}))
        
        # Receive response
        response = await ws.recv()
        print(f"Response: {response}")

asyncio.run(test())
```

Then run:
```bash
pip install websockets
python3 test_ws.py
```

## Project Structure

```
agentic-brain/
├── src/agentic_brain/api/
│   ├── __init__.py        # Package exports
│   ├── models.py          # Pydantic models
│   ├── server.py          # FastAPI application
│   ├── test_api.py        # Test suite
│   └── README.md          # Full documentation
├── pyproject.toml         # Project configuration
└── README.md              # Main project README
```

## API Endpoints Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/chat` | Send message |
| GET | `/session/{id}` | Get session info |
| GET | `/session/{id}/messages` | Get session messages |
| DELETE | `/session/{id}` | Delete session |
| DELETE | `/sessions` | Clear all sessions |
| WS | `/ws/chat` | Real-time WebSocket chat |

## Troubleshooting

### ModuleNotFoundError: No module named 'fastapi'

Solution:
```bash
pip install -e ".[api]"
```

### Port already in use

Solution - Use a different port:
```bash
uvicorn agentic_brain.api.server:app --port 8001
```

### Connection refused on WebSocket

Make sure the server is running:
```bash
# In another terminal
uvicorn agentic_brain.api.server:app
```

## Next Steps

1. **Integrate with Chatbot Logic**
   - Replace the echo responses in `server.py` with actual chatbot logic
   - Update the `POST /chat` endpoint handler
   - Update the WebSocket message handler

2. **Add Persistence**
   - Replace in-memory sessions with database storage
   - Consider Redis for caching
   - Store message history in PostgreSQL

3. **Add Authentication**
   - Implement JWT token validation
   - Add user authentication endpoints
   - Restrict session access by user

4. **Production Deployment**
   - Use production ASGI server (Gunicorn + Uvicorn)
   - Add HTTPS/SSL certificates
   - Configure proper logging
   - Set up monitoring and alerting

## License

GPL-3.0-or-later © 2026 Joseph Webber
