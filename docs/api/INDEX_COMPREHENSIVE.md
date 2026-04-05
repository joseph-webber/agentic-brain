# Comprehensive API Documentation

Welcome to the complete Agentic Brain API documentation. This is a world-class reference for all APIs with examples, specifications, and best practices.

## 📚 Documentation Files

| Document | Purpose | Audience |
|----------|---------|----------|
| **[REST_API.md](./REST_API.md)** | Complete HTTP/REST endpoint reference | Web/Mobile developers |
| **[PYTHON_API.md](./PYTHON_API.md)** | Python SDK and library reference | Python developers |
| **[CLI_API.md](./CLI_API.md)** | Command-line interface reference | DevOps/CLI users |
| **[EXAMPLES.md](./EXAMPLES.md)** | Complete working code examples | All developers |
| **[index.md](./index.md)** | Module-based API organization | Architecture overview |

---

## 🚀 Quick Navigation

### By Use Case

**Building a Chat Application?**
1. Start: [REST_API.md - Chat Endpoints](./REST_API.md#chat)
2. Code: [EXAMPLES.md - Basic Chat](./EXAMPLES.md#basic-chat)
3. Learn: [PYTHON_API.md - Agent Class](./PYTHON_API.md#agent-class)

**Building with Python?**
1. Start: [PYTHON_API.md - Quick Start](./PYTHON_API.md#quick-start)
2. Code: [EXAMPLES.md - Python Examples](./EXAMPLES.md#basic-chat)
3. Advanced: [PYTHON_API.md - Custom Agents](./PYTHON_API.md#advanced-custom-agents)

**Using Command Line?**
1. Start: [CLI_API.md - Usage](./CLI_API.md#usage)
2. Examples: [CLI_API.md - Examples](./CLI_API.md#examples)
3. Config: [CLI_API.md - Configuration File](./CLI_API.md#configuration-file)

**Building Real-Time Features?**
1. WebSocket: [REST_API.md - WebSocket API](./REST_API.md#websocket-api)
2. Streaming: [REST_API.md - Streaming](./REST_API.md#get-chatsstream)
3. Code: [EXAMPLES.md - WebSocket](./EXAMPLES.md#websocket)

**Retrieval-Augmented Generation (RAG)?**
1. Concepts: [REST_API.md - RAG API](./REST_API.md#rag-api)
2. Code: [EXAMPLES.md - RAG Examples](./EXAMPLES.md#rag-retrieval-augmented-generation)
3. Advanced: [PYTHON_API.md - Memory API](./PYTHON_API.md#memory-api)

---

## 📖 All APIs at a Glance

### Core APIs
- **Chat**: Send/receive messages, streaming responses
- **Sessions**: Manage conversations and session state
- **Memory**: Query knowledge graphs and conversation context
- **RAG**: Retrieve contextual information from documents
- **Config**: Manage agent and system configuration
- **Health**: Monitor system status and metrics

### Real-Time APIs
- **WebSocket**: Bidirectional real-time communication
- **SSE**: Server-Sent Events for streaming responses

### Supporting APIs
- **Authentication**: Bearer token and JWT support
- **Rate Limiting**: 60 requests/minute per IP
- **Error Handling**: Standardized error responses

---

## 🔑 Key Concepts

### Authentication
All endpoints require Bearer token authentication:
```bash
Authorization: Bearer your-jwt-token
```

### Rate Limiting
```
General: 60 requests/minute
Chat: 30 requests/minute per session
Streaming: No limit
```

### Response Format
```json
{
  "data": {},
  "timestamp": "2026-04-05T20:00:00Z"
}
```

### Error Format
```json
{
  "error": "error_code",
  "message": "Human-readable message",
  "timestamp": "2026-04-05T20:00:00Z"
}
```

---

## 💡 Getting Help

### By Question

**"How do I get started?"**
→ [Quick Start Guide](./PYTHON_API.md#quick-start)

**"Show me working code"**
→ [Code Examples](./EXAMPLES.md)

**"What are all the REST endpoints?"**
→ [REST API Reference](./REST_API.md)

**"How do I use the command line?"**
→ [CLI Reference](./CLI_API.md)

**"What's the Python API?"**
→ [Python SDK Reference](./PYTHON_API.md)

**"How do I test my code?"**
→ [Testing Examples](./EXAMPLES.md#testing)

**"I'm getting an error"**
→ [Error Codes](./REST_API.md#error-responses)

---

## 🎯 Learning Path

### Beginner (30 minutes)
1. Read: [Quick Start](./PYTHON_API.md#quick-start)
2. Run: [Basic Chat Example](./EXAMPLES.md#basic-chat)
3. Explore: Interactive Swagger UI at `/docs`

### Intermediate (2-3 hours)
1. Learn: [Sessions & Memory](./EXAMPLES.md#sessions--memory)
2. Code: [REST API Examples](./EXAMPLES.md#rest-api)
3. Build: Simple chatbot with memory

### Advanced (full day)
1. Study: [Custom Agents](./EXAMPLES.md#advanced-custom-agent)
2. Implement: RAG with document indexing
3. Deploy: Production API server

---

## ⚙️ Configuration

### Environment Variables
```bash
AGENTIC_LLM_PROVIDER=ollama
AGENTIC_LLM_MODEL=llama3.1:8b
AGENTIC_MEMORY_URI=bolt://localhost:7687
```

### Configuration File
```yaml
llm:
  provider: ollama
  model: llama3.1:8b
  temperature: 0.7

memory:
  type: neo4j
  uri: bolt://localhost:7687
```

### Programmatic
```python
config = Settings(
    llm=LLMSettings(provider="ollama", model="llama3.1:8b"),
    memory=MemorySettings(type="neo4j", uri="bolt://localhost:7687")
)
```

---

## 🧪 Testing

### Local Development
```bash
agentic server --reload
# Server at http://localhost:8000
# Swagger at http://localhost:8000/docs
# ReDoc at http://localhost:8000/redoc
```

### Health Check
```bash
curl http://localhost:8000/health
```

### Example Request
```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

---

## 📚 Advanced Topics

### Async Programming
See [PYTHON_API.md - Async/Await Patterns](./PYTHON_API.md#asyncawait-patterns)

### Error Handling
See [EXAMPLES.md - Error Handling](./EXAMPLES.md#error-handling)

### Performance
See [PYTHON_API.md - Performance Tips](./PYTHON_API.md#performance-tips)

### Testing
See [EXAMPLES.md - Testing](./EXAMPLES.md#testing)

---

## 📋 API Compliance

✅ OpenAPI 3.0 compliant  
✅ RESTful design principles  
✅ Comprehensive error handling  
✅ Rate limit headers  
✅ Security (Bearer tokens)  
✅ Type hints (Python)  

---

## 📞 Support

- **Issue**: Report at [GitHub Issues](https://github.com/agentic-brain/issues)
- **Question**: Ask at [GitHub Discussions](https://github.com/agentic-brain/discussions)
- **Security**: Report at security@agentic-brain.dev

---

## 📄 License

All documentation and APIs are under [Apache License 2.0](../../LICENSE)

---

**Last Updated**: April 5, 2026  
**Status**: Production Ready  
**Version**: 3.1.0

---

**Tip**: This is the comprehensive index. For quick reference, see individual files:
- [REST_API.md](./REST_API.md) - REST endpoints
- [PYTHON_API.md](./PYTHON_API.md) - Python SDK
- [CLI_API.md](./CLI_API.md) - Command line
- [EXAMPLES.md](./EXAMPLES.md) - Code examples
