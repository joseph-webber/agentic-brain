# 🚀 Agentic Brain API - Postman Collection

Professional, production-ready Postman collection for the **Agentic Brain API** with all endpoints, environment variables, example requests, and comprehensive documentation.

## 📦 What's Included

### Files

1. **postman_collection.json** (13 KB)
   - Complete API collection with 12 endpoints
   - Organized in 5 categories
   - Pre-configured environment variables
   - Example request bodies with JSON schemas
   - Professional descriptions for each endpoint

2. **POSTMAN_SETUP.md** (8.1 KB)
   - Detailed setup guide with step-by-step instructions
   - Usage examples and workflows
   - Troubleshooting guide
   - Advanced features (custom variables, pre-request scripts, tests)
   - Authentication methods

3. **POSTMAN_QUICK_REF.txt** (9.1 KB)
   - One-page quick reference card
   - All endpoints at a glance
   - Quick workflow guide
   - Common troubleshooting tips

## 🎯 Quick Start

### 1. Import into Postman

```bash
# In Postman:
1. Click Import button (top-left)
2. Upload: postman_collection.json
3. Click Import
```

### 2. Configure Environment

Set these variables for your environment:

```
base_url   = http://localhost:8000  (your API server)
api_key    = <leave empty for dev>  (your API key if required)
session_id = sess_abc123            (for testing)
user_id    = user_xyz789            (for testing)
```

### 3. Test Health Check

```
GET {{base_url}}/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "sessions_active": 5,
  ...
}
```

## 📋 API Endpoints Overview

### 🏥 Health & Status (3 endpoints)

- **GET /health** - Server health, version, active sessions
- **GET /setup** - Setup status and requirements
- **GET /setup/help/{provider}** - Provider-specific help (groq, openai, anthropic, ollama)

### 💬 Chat (2 endpoints)

- **POST /chat** - Send message, get response
  - Body: `{ message, session_id, user_id, metadata }`
  
- **GET /chat/stream** - Real-time streaming via SSE
  - Query: `?message=X&session_id=Y`

### 📝 Sessions (3 endpoints)

- **GET /session/{session_id}** - Session metadata
- **GET /session/{session_id}/messages** - Conversation history
- **DELETE /session/{session_id}** - Delete session (⚠️ destructive)

### 🔐 Authentication (3 endpoints)

- **POST /auth/saml/login** - Enterprise SAML authentication
- **GET /auth/saml/metadata** - SAML service provider metadata
- **GET /auth/sso/{provider}/login** - Social login (google, github, azure, okta)

### 🌐 WebSocket (1 endpoint)

- **WS /ws/chat** - Real-time bidirectional communication
  - Query: `?session_id=X&user_id=Y`
  - Message format: `{ message, type, metadata }`

## 🔑 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `base_url` | `http://localhost:8000` | API server URL |
| `api_key` | `` | API key (optional) |
| `session_id` | `sess_abc123` | Session ID for testing |
| `user_id` | `user_xyz789` | User ID for testing |

**Note:** Modify these for different environments (dev, staging, production).

## 📚 Documentation

For detailed information, see:

- **POSTMAN_SETUP.md** - Complete setup guide with examples
- **POSTMAN_QUICK_REF.txt** - One-page quick reference
- **postman_collection.json** - Collection metadata (all details are here)

## 🔐 Authentication

### For Local Development
- Leave `api_key` empty
- Disable Authorization header
- API will accept requests without authentication

### For Protected APIs
- Set `api_key` to your API key
- Enable Authorization header
- Format: `Bearer {{api_key}}`

### For Enterprise (SAML/SSO)
- Use `/auth/saml/login` endpoint
- Use `/auth/sso/{provider}/login` endpoint
- Follow OAuth/SAML flow in your frontend

## 💡 Common Workflows

### Send a Message
```
1. POST /chat
2. Include: message, session_id, user_id
3. Get: response, message_id, timestamp
```

### Get Conversation History
```
1. GET /session/{session_id}/messages
2. Get: array of all messages in session
```

### Stream Long Response
```
1. GET /chat/stream?message=...&session_id=...
2. Connect with SSE (Server-Sent Events)
3. Receive: streaming chunks of response
```

### Establish Real-Time Chat
```
1. WebSocket: ws://base_url/ws/chat?session_id=...
2. Send: JSON messages with { message, type, metadata }
3. Receive: Real-time responses
```

## ✅ Validation Checklist

Before deploying to production:

- [ ] Base URL points to correct server
- [ ] API key is set (if required)
- [ ] Health check returns 200 OK
- [ ] LLM provider is configured
- [ ] Database connections are valid
- [ ] WebSocket connections work
- [ ] Session management works
- [ ] Authentication methods are tested

## 🐛 Troubleshooting

### Connection Refused
```
❌ Error: Cannot connect to {{base_url}}
✅ Solution: 
   1. Check base_url in environment
   2. Verify API server is running
   3. Try: GET /health
```

### Unauthorized (401)
```
❌ Error: Unauthorized
✅ Solution:
   1. Check {{api_key}} is set
   2. Enable Authorization header
   3. Verify token not expired
```

### Empty Response
```
❌ Error: Response is empty or null
✅ Solution:
   1. Check LLM provider configured (GET /health)
   2. Verify LLM API key is valid
   3. Check message is not empty
```

### WebSocket Connection Fails
```
❌ Error: WebSocket connection failed
✅ Solution:
   1. Use ws:// not http://
   2. Check session_id is valid
   3. Verify firewall allows WebSocket
```

## 🚀 Advanced Usage

### Custom Pre-request Scripts

Automatically generate session IDs:

```javascript
const sessionId = `session-${Date.now()}`;
pm.environment.set("session_id", sessionId);
```

### Tests and Assertions

Validate responses:

```javascript
pm.test("Status is 200", function() {
  pm.response.to.have.status(200);
});

pm.test("Response has session_id", function() {
  pm.expect(pm.response.json()).to.have.property('session_id');
});
```

### Collection Runner

Run all requests in sequence:

```
1. Click Collection dropdown menu
2. Select "Run"
3. Configure iterations and delay
4. Click "Start Test Run"
```

## 📖 Full Documentation

For complete API documentation, visit:

```
Interactive: http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
```

## 🤝 Support

- 📧 Email: [support email]
- 💬 Discord: [Discord link]
- 🐛 Issues: [GitHub issues]
- 📚 Wiki: [Documentation wiki]

## 📄 License

Part of Agentic Brain API. Licensed under Apache 2.0.

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-15 | Initial release with 12 endpoints |

---

**Last Updated:** 2026-01-15  
**Compatible with:** Postman 10.0+, Python 3.11+, Node.js 18+  
**Status:** Production-Ready ✅
