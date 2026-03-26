# Configuration Guide

Complete reference for all Agentic Brain configuration options.

---

## Configuration Precedence

Configuration is loaded in this order (later overrides earlier):

1. **Defaults** — Built-in sensible defaults
2. **Config file** — `config.yaml` or `config.json` (if present)
3. **Environment variables** — Overrides all other sources

---

## Environment Variables

### Neo4j Database

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | *(required)* | Neo4j password |

### LLM Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_LLM_PROVIDER` | `ollama` | Default provider: `ollama`, `openai`, `anthropic`, `openrouter` |
| `DEFAULT_LLM_MODEL` | `llama3.2` | Default model name |
| `OLLAMA_API_BASE` | `http://localhost:11434` | Ollama API endpoint |
| `OPENAI_API_KEY` | *(optional)* | OpenAI API key |
| `ANTHROPIC_API_KEY` | *(optional)* | Anthropic API key |
| `OPENROUTER_API_KEY` | *(optional)* | OpenRouter API key |

### API Server

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Server bind address |
| `API_PORT` | `8000` | Server port |
| `DASHBOARD_ENABLED` | `true` | Enable analytics dashboard |
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

### Session Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_BACKEND` | `memory` | Session storage: `memory` or `redis` |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `SESSION_MAX_AGE` | `3600` | Session timeout in seconds (1 hour) |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_ENABLED` | `false` | Enable authentication |
| `API_KEYS` | *(empty)* | Comma-separated valid API keys |
| `JWT_SECRET` | *(required if using JWT)* | JWT signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |

See [AUTHENTICATION.md](./AUTHENTICATION.md) for detailed auth setup.

### Audit Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIT_ENABLED` | `true` | Enable audit logging |
| `AUDIT_LOG_FILE` | *(stdout)* | Audit log file path |
| `AUDIT_LOG_LEVEL` | `INFO` | Audit log level |

### Firebase Transport (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `FIREBASE_DATABASE_URL` | *(optional)* | Firebase Realtime DB URL |
| `FIREBASE_CREDENTIALS` | *(optional)* | Path to Firebase credentials JSON |

---

## Example .env File

Create a `.env` file in your project root:

```bash
# Neo4j Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password

# LLM Providers
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_LLM_MODEL=llama3.2
OLLAMA_API_BASE=http://localhost:11434

# For cloud providers (uncomment as needed)
# OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# API Server
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Session Storage
SESSION_BACKEND=memory
SESSION_MAX_AGE=3600

# Authentication (optional - disabled by default)
AUTH_ENABLED=false
# API_KEYS=key1,key2,key3
# JWT_SECRET=your-secret-key-change-in-production

# Audit Logging
AUDIT_ENABLED=true
# AUDIT_LOG_FILE=/var/log/agentic-brain/audit.log

# Redis (if using redis session backend)
# SESSION_BACKEND=redis
# REDIS_URL=redis://localhost:6379
```

---

## Production Configuration

For production deployments, we recommend:

```bash
# Production .env
NEO4J_URI=bolt://neo4j-prod:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=${NEO4J_PASSWORD}  # From secrets manager

# Use OpenAI or Anthropic for production quality
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4-turbo
OPENAI_API_KEY=${OPENAI_API_KEY}  # From secrets manager

# Production server settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=WARNING

# Redis for multi-instance deployments
SESSION_BACKEND=redis
REDIS_URL=redis://redis-prod:6379
SESSION_MAX_AGE=7200

# Enable authentication
AUTH_ENABLED=true
API_KEYS=${API_KEYS}  # From secrets manager
JWT_SECRET=${JWT_SECRET}  # From secrets manager

# Audit logging to file
AUDIT_ENABLED=true
AUDIT_LOG_FILE=/var/log/agentic-brain/audit.log
AUDIT_LOG_LEVEL=INFO
```

---

## Programmatic Configuration

You can also configure components programmatically:

```python
from agentic_brain import Chatbot, ChatConfig, Neo4jMemory

# Configure memory
memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

# Configure chatbot
config = ChatConfig(
    max_history=200,
    temperature=0.7,
    persist_sessions=True,
    customer_isolation=True
)

bot = Chatbot("assistant", memory=memory, config=config)
```

### Streaming Configuration

```python
from agentic_brain.streaming import StreamingResponse

streamer = StreamingResponse(
    provider="ollama",
    model="llama3.1:8b",
    temperature=0.7,
    max_tokens=2048,
    system_prompt="You are a helpful assistant.",
    api_base="http://localhost:11434"
)
```

---

## Docker Compose Configuration

For Docker deployments, configuration is passed via environment:

```yaml
# docker-compose.yml
services:
  agentic-brain:
    image: agentic-brain:latest
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - DEFAULT_LLM_PROVIDER=ollama
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
      - SESSION_BACKEND=redis
      - REDIS_URL=redis://redis:6379
      - AUTH_ENABLED=true
      - API_KEYS=${API_KEYS}
```

---

## Configuration Validation

Validate your configuration on startup:

```python
from agentic_brain.config import validate_config

# Raises ConfigError if invalid
validate_config()
```

Or via CLI:

```bash
agentic-brain config validate
```

---

## Security Notes

1. **Never commit secrets** — Use environment variables or secrets managers
2. **Rotate API keys** — Regularly rotate `API_KEYS` and `JWT_SECRET`
3. **Use strong passwords** — `NEO4J_PASSWORD` should be cryptographically random
4. **Limit network exposure** — Bind to `127.0.0.1` if not using a reverse proxy

---

## See Also

- [AUTHENTICATION.md](./AUTHENTICATION.md) — Auth setup details
- [DEPLOYMENT.md](./DEPLOYMENT.md) — Production deployment guide
- [SECURITY.md](./SECURITY.md) — Security best practices

---

**Last Updated**: 2026-03-20
