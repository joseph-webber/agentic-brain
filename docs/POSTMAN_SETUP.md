# Postman Collection Setup Guide

## Overview

The **Agentic Brain API Postman Collection** (`postman_collection.json`) provides a complete, professionally-organized collection of all API endpoints with:

- ✅ Proper request methods and paths
- ✅ Example request bodies with JSON schemas
- ✅ Pre-configured headers (Content-Type, Authorization)
- ✅ Environment variables for easy configuration
- ✅ Detailed descriptions for each endpoint
- ✅ Organized into logical folders by category

## Quick Start

### 1. Import the Collection

1. Open **Postman** (or [download it](https://www.postman.com/downloads/))
2. Click the **Import** button (top-left)
3. Select **Upload Files** tab
4. Choose `postman_collection.json` from this directory
5. Click **Import**

### 2. Set Environment Variables

Once imported, configure these variables for your environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `base_url` | `http://localhost:8000` | Your API server URL |
| `api_key` | `` | Your API key (if required) |
| `session_id` | `sess_abc123` | Session ID for testing |
| `user_id` | `user_xyz789` | User ID for multi-user features |

**To set variables in Postman:**
1. Click the **Environment** button (🔧 icon, top-right)
2. Select or create an environment
3. Enter values for each variable
4. Click Save

## API Endpoints

The collection includes **13 endpoints** organized into 5 categories:

### 🏥 Health & Status (3 endpoints)

Monitor system health and configuration:

- **Health Check** - `GET /health`
  - Verify API is running and healthy
  - Get version, session count, Redis/LLM/Neo4j status
  - Used by monitoring systems and health probes

- **Setup Status** - `GET /setup`
  - Get current setup status and requirements
  - Check which LLM providers are configured

- **Setup Help** - `GET /setup/help/{provider}`
  - Get provider-specific setup instructions
  - Supports: `groq`, `openai`, `anthropic`, `ollama`

### 💬 Chat (3 endpoints)

Interact with the AI chat system:

- **Send Chat Message** - `POST /chat`
  - Send a user message and receive an AI response
  - **Body params:**
    - `message` (required): The user's message (1-32000 chars)
    - `session_id` (optional): Track conversation
    - `user_id` (optional): Multi-user support
    - `metadata` (optional): Additional context

- **Stream Chat Response** - `GET /chat/stream`
  - Real-time streaming using Server-Sent Events
  - Ideal for long responses
  - **Query params:** `message`, `session_id`, `user_id`

### 📝 Sessions (3 endpoints)

Manage conversation sessions:

- **Get Session** - `GET /session/{session_id}`
  - Retrieve session metadata
  - Get creation time, message count, last access

- **Get Session Messages** - `GET /session/{session_id}/messages`
  - Retrieve all messages in a session
  - Useful for conversation history and replay

- **Delete Session** - `DELETE /session/{session_id}`
  - Remove a session and all associated data
  - ⚠️ Destructive operation - cannot be undone

### 🔐 Authentication (3 endpoints)

Handle enterprise authentication:

- **SAML Login** - `POST /auth/saml/login`
  - Enterprise SAML 2.0 authentication
  - Works with Active Directory, Okta, etc.

- **SAML Metadata** - `GET /auth/saml/metadata`
  - Get service provider metadata
  - Share with identity providers for SSO setup

- **SSO Login** - `GET /auth/sso/{provider}/login`
  - Social login integration
  - Providers: `google`, `github`, `azure`, `okta`

### 🌐 WebSocket (1 endpoint)

Real-time bidirectional communication:

- **WebSocket Chat** - `ws://base_url/ws/chat`
  - Establish persistent connection for real-time chat
  - **Query params:** `session_id`, `user_id`
  - **Message format:**
    ```json
    {
      "message": "Your message here",
      "type": "chat",
      "metadata": {}
    }
    ```
  - Features: real-time delivery, auto-reconnect, presence tracking

## Usage Examples

### Example 1: Simple Chat Request

```bash
POST http://localhost:8000/chat
Content-Type: application/json

{
  "message": "What is machine learning?",
  "session_id": "session-001",
  "user_id": "user-001"
}
```

**Response:**
```json
{
  "response": "Machine learning is a subset of artificial intelligence...",
  "session_id": "session-001",
  "message_id": "msg_abc123",
  "timestamp": "2026-01-15T10:30:45.123456+00:00"
}
```

### Example 2: Stream Long Response

```bash
GET http://localhost:8000/chat/stream?message=Explain quantum computing&session_id=session-002
```

The response streams as Server-Sent Events:
```
data: {"chunk": "Quantum computing is..."}
data: {"chunk": " a computational model..."}
...
```

### Example 3: Retrieve Session History

```bash
GET http://localhost:8000/session/session-001/messages
Authorization: Bearer your_api_key
```

**Response:**
```json
[
  {
    "id": "msg_001",
    "message": "What is machine learning?",
    "response": "Machine learning is...",
    "timestamp": "2026-01-15T10:30:45.123456+00:00",
    "user_id": "user-001"
  },
  ...
]
```

## Authentication

### API Key Authentication

If your API requires authentication:

1. Add your API key to the `{{api_key}}` environment variable
2. In any request, enable the **Authorization** header (currently disabled)
3. The header will use: `Authorization: Bearer {{api_key}}`

### No Authentication

For development/local testing with no auth:
- Leave `{{api_key}}` empty
- Disable the **Authorization** header on requests

## Headers

All requests include these headers (customize as needed):

```
Content-Type: application/json
Authorization: Bearer {{api_key}}  [optional, enable in request]
```

For WebSocket and SSO endpoints, headers are handled automatically.

## Testing Workflow

### 1. Health Check
Start by verifying the API is healthy:
```
GET /health
```
Expected response: `{ "status": "healthy", ... }`

### 2. Send a Message
Test chat functionality:
```
POST /chat
{
  "message": "Hello, how are you?",
  "session_id": "test-session-1"
}
```

### 3. Retrieve Session
Check the conversation history:
```
GET /session/test-session-1/messages
```

### 4. Stream a Response
Test streaming for long responses:
```
GET /chat/stream?message=Tell me about AI&session_id=test-session-2
```

## Troubleshooting

### "Connection refused" error
- ✅ Verify `base_url` is correct (default: `http://localhost:8000`)
- ✅ Check that the API server is running
- ✅ Try `GET /health` to diagnose

### "Unauthorized" (401) error
- ✅ Check `{{api_key}}` is set if API requires authentication
- ✅ Verify token is not expired
- ✅ Ensure Authorization header is enabled

### WebSocket connection fails
- ✅ Use `ws://` (not `http://`) for WebSocket URLs
- ✅ Check `session_id` is valid
- ✅ Verify firewall allows WebSocket connections

### Empty response from chat
- ✅ Check LLM provider is configured (see `/health`)
- ✅ Verify API key for LLM provider (if required)
- ✅ Check message is not empty

## Advanced Features

### Custom Variables

Add your own variables for different environments:

1. Click **Environment** (🔧 icon)
2. Click **Edit** next to your environment
3. Add rows for new variables
4. Reference in requests with `{{variable_name}}`

Example:
```json
{
  "base_url_prod": "https://api.example.com",
  "api_key_prod": "your_prod_key"
}
```

### Pre-request Scripts

Automatically generate session IDs or handle authentication:

1. Select a request
2. Click **Pre-request Script** tab
3. Add JavaScript to modify the request

Example:
```javascript
// Generate random session ID
const sessionId = `session-${Date.now()}`;
pm.environment.set("session_id", sessionId);
```

### Tests

Validate responses automatically:

1. Select a request
2. Click **Tests** tab
3. Add assertions

Example:
```javascript
pm.test("Status is 200", function() {
  pm.response.to.have.status(200);
});

pm.test("Response has session_id", function() {
  pm.expect(pm.response.json()).to.have.property('session_id');
});
```

## API Documentation

For full OpenAPI documentation, visit:
```
http://localhost:8000/docs
http://localhost:8000/redoc
```

## Support

For issues or questions:
- 📖 Check the main API README
- 🐛 Report bugs on GitHub
- 💬 Join the community Discord

---

**Version:** 1.0.0  
**Last Updated:** 2026-01-15  
**Compatible with:** Postman 10.0+
