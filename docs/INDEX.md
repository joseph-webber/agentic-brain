# 📚 Agentic Brain Documentation Index

> Complete API documentation for the production-ready AI orchestration platform

---

## 📖 API Documentation Files

### 1. **API.md** - Developer Guide
**Best for:** Getting started, quick examples, common patterns

**Contains:**
- 🚀 Quick start (Python, JavaScript)
- 💬 Chat endpoint examples
- 🗂️ Session management guide
- 🔐 Authentication setup
- 🎯 Common patterns (multi-turn, streaming, error handling)
- 🌐 Supported LLM providers
- �� Deployment guides (Docker, Kubernetes)
- ❓ FAQ

**Use when:** You want to start integrating quickly

---

### 2. **API_REFERENCE.md** - Technical Reference
**Best for:** Complete endpoint documentation, detailed specifications

**Contains:**
- 📋 Quick reference table (all 26+ endpoints)
- 🏥 Health & Monitoring endpoints (4)
- 💬 Chat endpoints (2)
- 🗂️ Session management (4)
- 🔌 WebSocket endpoint (1)
- 🔐 Authentication endpoints (5)
- 🛠️ Setup & Diagnostics (2)
- 📊 Dashboard endpoints (5)
- 🎁 Webhooks (1)

**For each endpoint:**
- Complete curl examples
- Request/response models
- Query/path parameters
- Status codes & errors
- Real-world JSON examples
- Rate limiting info

**Use when:** You need complete specification details

---

### 3. **API_DOCS_SUMMARY.md** - This Overview
**Best for:** Understanding what's documented, quality checklist

---

## 🔄 Documentation Quick Map

```
START HERE
    ↓
Choose your role:
    ├─ Developer? → Read API.md
    ├─ DevOps/Ops? → Check "Deployment" in API.md
    ├─ Integration? → Start API.md, then API_REFERENCE.md
    └─ Troubleshooting? → Check API_REFERENCE.md error section
```

---

## 🎯 By Task

### "I want to send a chat message"
1. Open **API.md** → "Chat Endpoints" section
2. Copy Python/JavaScript example
3. Replace message text
4. Run!

### "I need full endpoint details"
1. Open **API_REFERENCE.md**
2. Find endpoint in Quick Reference Table
3. Go to that section
4. Review all parameters and examples

### "I need to set up authentication"
1. **API.md** → "Authentication" section
2. Choose method (API Key, JWT, OAuth2, SAML)
3. Follow configuration steps
4. Test with curl example

### "How do I stream responses?"
1. **API.md** → "Chat Endpoints" → "Stream Response"
2. Use provided SSE or WebSocket example
3. Handle token events

### "I need to deploy this"
1. **API.md** → "Deployment" section
2. Choose Docker or Kubernetes
3. Copy configuration
4. Deploy!

### "What's the rate limit?"
1. **API_REFERENCE.md** → "⚡ Rate Limiting" section
2. Review limits per tier
3. Check response headers in examples

### "How do I handle errors?"
1. **API_REFERENCE.md** → "🚨 Error Handling" section
2. Review status codes table
3. Check endpoint for specific errors
4. See examples in endpoint section

---

## 📊 All Endpoints (26+)

### Health & Monitoring (4)
```
GET  /health              System status
GET  /infra/health        Component health (Redis, Neo4j, Redpanda)
GET  /healthz             Kubernetes liveness probe
GET  /readyz              Kubernetes readiness probe
```
→ See **API_REFERENCE.md** → Section "1️⃣ Health & Monitoring"

### Chat (2)
```
POST /chat                Synchronous message (request-response)
GET  /chat/stream         Streaming response (SSE)
```
→ See **API.md** → "Chat Endpoints" or **API_REFERENCE.md** → "2️⃣ Chat"

### Sessions (4)
```
GET  /session/{id}        Get session metadata
GET  /session/{id}/messages Get chat history
DELETE /session/{id}      Delete single session
DELETE /sessions          Clear all sessions (admin)
```
→ See **API.md** → "Session Management" or **API_REFERENCE.md** → "3️⃣ Sessions"

### WebSocket (1)
```
WS   /ws/chat             Real-time bidirectional streaming
```
→ See **API_REFERENCE.md** → "4️⃣ WebSocket"

### Authentication (5)
```
POST /auth/saml/login              Start SAML SSO
POST /auth/saml/acs                SAML callback
GET  /auth/saml/metadata           SAML metadata
GET  /auth/sso/{provider}/login    OAuth2/OIDC auth
GET  /auth/sso/{provider}/callback OAuth2/OIDC callback
```
→ See **API.md** → "Authentication" or **API_REFERENCE.md** → "5️⃣ Auth"

### Setup (2)
```
GET  /setup                        Provider configuration status
GET  /setup/help/{provider}        Provider setup instructions
```
→ See **API.md** → "Setup & Configuration" or **API_REFERENCE.md** → "6️⃣ Setup"

### Dashboard (5)
```
GET  /dashboard                    Admin dashboard HTML
GET  /dashboard/api/stats          System statistics
GET  /dashboard/api/health         Dashboard health
GET  /dashboard/api/sessions       List active sessions
DELETE /dashboard/api/sessions     Clear all sessions
```
→ See **API_REFERENCE.md** → "7️⃣ Dashboard"

### Webhooks (1)
```
POST /webhooks/woocommerce         WooCommerce events
```
→ See **API_REFERENCE.md** → "8️⃣ Webhooks"

---

## 🔐 Authentication (4 Methods)

### 1. API Key (Simplest)
```bash
curl -H "X-API-Key: your_key" http://localhost:8000/health
```

### 2. API Key Query Parameter
```bash
curl http://localhost:8000/health?api_key=your_key
```

### 3. JWT Token (Recommended)
```bash
curl -H "Authorization: Bearer token" http://localhost:8000/health
```

### 4. OAuth2/OIDC/SAML (Enterprise)
```bash
curl http://localhost:8000/auth/sso/google/login
```

→ See **API_REFERENCE.md** → "🔐 Authentication" for full details

---

## 📈 Rate Limits

| Type | Limit | Purpose |
|------|-------|---------|
| Anonymous | 60 req/min | Per IP address |
| Authenticated | 100 req/min | Per user |
| Login | 5 req/min | Brute force protection |
| WebSocket | 50 msg/min | Per connection |

→ See **API_REFERENCE.md** → "⚡ Rate Limiting"

---

## 🛠️ Supported LLM Providers

| Provider | Status | Model Examples |
|----------|--------|-----------------|
| Ollama | ✓ Local | llama3.1, mistral, llama2 |
| Groq | ✓ Cloud | mixtral-8x7b, llama-2-70b |
| OpenAI | ✓ Cloud | gpt-4, gpt-3.5-turbo |
| Anthropic | ✓ Cloud | claude-3-opus, claude-3-sonnet |
| Google | ✓ Cloud | gemini-pro |
| Together | ✓ Cloud | Multiple open models |
| OpenRouter | ✓ Cloud | 200+ models |
| xAI | ✓ Cloud | grok-1 |

→ See **API.md** → "Supported LLM Providers"

---

## 🚀 Deployment

### Docker
```bash
docker run -d -p 8000:8000 \
  -e AUTH_ENABLED=true \
  -e JWT_SECRET=your-secret \
  agentic-brain:latest
```

### Kubernetes
```yaml
deployment:
  replicas: 3
  livenessProbe: GET /healthz
  readinessProbe: GET /readyz
```

→ See **API.md** → "Deployment"

---

## 🔍 Interactive Documentation

Access at runtime:

- **Swagger UI:** http://localhost:8000/docs
  - Try endpoints interactively
  - See all parameters
  - Test live requests

- **ReDoc:** http://localhost:8000/redoc
  - Clean reference format
  - Searchable documentation
  - Grouped by category

- **OpenAPI Schema:** http://localhost:8000/openapi.json
  - Machine-readable specification
  - Use for code generation
  - Import to tools like Postman

---

## 📚 Learning Path

### 5-Minute Quick Start
1. Read **API.md** → "Quick Start"
2. Try `/chat` endpoint
3. Check response

### 20-Minute Introduction
1. Read **API.md** → "Chat Endpoints"
2. Try streaming example
3. Read session management
4. Try multi-turn conversation

### 1-Hour Deep Dive
1. Read **API_REFERENCE.md** → Quick Reference
2. Review each endpoint category
3. Study authentication options
4. Check rate limiting strategy
5. Review error codes
6. Plan deployment

### Full Mastery
1. Complete all sections
2. Test all endpoints in Swagger UI
3. Deploy locally with Docker
4. Set up authentication
5. Integrate with your application

---

## ❓ Common Questions

**Q: Where do I start?**  
A: Open **API.md** and read "Quick Start" section

**Q: How do I authenticate?**  
A: See **API_REFERENCE.md** → "🔐 Authentication"

**Q: How do I stream responses?**  
A: See **API.md** → "Chat Endpoints" → "Stream Response"

**Q: What's the rate limit?**  
A: See **API_REFERENCE.md** → "⚡ Rate Limiting"

**Q: How do I deploy?**  
A: See **API.md** → "🚀 Deployment"

**Q: Need full endpoint details?**  
A: Use **API_REFERENCE.md** Quick Reference Table

**Q: Need code examples?**  
A: Check **API.md** for Python, JavaScript, curl examples

**Q: Having issues?**  
A: Check **API_REFERENCE.md** → "🚨 Error Handling"

---

## 📞 Support & Resources

- **Source Code:** [GitHub](https://github.com/your-org/agentic-brain)
- **Issues:** [GitHub Issues](https://github.com/your-org/agentic-brain/issues)
- **Email:** support@agentic-brain.example.com
- **Slack:** [Community Slack](https://slack.agentic-brain.example.com)

---

## 📊 Documentation Stats

| Metric | Value |
|--------|-------|
| Total Lines | 1,643 |
| Code Examples | 50+ |
| Endpoints | 26+ |
| Auth Methods | 4 |
| LLM Providers | 8+ |
| Error Codes | 9 |
| Languages | 4 (Python, JavaScript, curl, YAML) |

---

**Documentation Version:** 1.0.0  
**Last Updated:** 2026-01-15  
**Status:** ✅ Production Ready

Start with **API.md** →
