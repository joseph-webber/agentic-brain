# Environment Setup Guide

## Overview

The agentic-brain system requires environment variables to configure API keys, service connections, and runtime behavior. Environment variables are loaded from `.env` files in the working directory or `.env.docker` for containerized deployments.

**Key principles:**
- Never commit real credentials to version control
- Use `.env` for local development
- Use `.env.docker` for Docker containers
- Use `.env.example` as a template for new developers
- Use placeholders and verify they are never replaced with real keys before committing

---

## File Locations

| File | Purpose | Environment | Who Edits |
|------|---------|-------------|-----------|
| `.env` | Local development credentials | Linux/macOS/Windows | Developer (local only) |
| `.env.docker` | Docker container secrets | Docker/Docker Compose | DevOps/Developer |
| `.env.example` | Template (committed to git) | N/A | Git repository |
| `.env.production` | Production settings (NOT committed) | Production servers | DevOps only |

---

## Quick Start

### 1. Initialize .env Files

```bash
# Copy template for local development
cp .env.example .env

# Copy template for Docker
cp .env.docker.example .env.docker
```

### 2. Add API Keys

Edit `.env` and `.env.docker` with your actual credentials:

```bash
# Local development
nano .env

# Docker containers
nano .env.docker
```

### 3. Verify Configuration

```bash
# Check .env can be loaded (don't echo keys!)
python -c "from dotenv import load_dotenv; load_dotenv('.env'); print('✓ .env loaded successfully')"

# Docker: verify inside container
docker compose exec brain python -c "from dotenv import load_dotenv; load_dotenv(); print('✓ Docker .env loaded')"
```

---

## Core System Variables

### Brain Services

```ini
# Neo4j Graph Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-neo4j-password-here

# Redis (for caching and queues)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password-here
REDIS_DB=0

# Event Bus (Redpanda/Kafka)
REDPANDA_BROKERS=localhost:9092
REDPANDA_TOPIC_PREFIX=brain

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/brain_db
```

### System Settings

```ini
# Environment type
ENVIRONMENT=development  # development, staging, production

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json  # json or text

# API Port
API_PORT=8000
API_HOST=0.0.0.0

# Worker threads
NUM_WORKERS=4
```

---

## LLM Providers

### Free Providers (Recommended to Start)

#### Ollama (Local, No Key Required)
**Best for:** Local development, offline work, zero cost

```ini
# Local Ollama server (no API key needed)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=neural-chat  # or mistral, llama2, neural-chat

# Useful for testing without cloud costs
ENABLE_LOCAL_LLM=true
```

**Setup:**
```bash
# macOS
brew install ollama
ollama serve

# Or visit https://ollama.ai for other platforms
```

#### Groq (Fastest Free Tier)
**Best for:** Speed, high throughput, free tier sufficient for most uses

- **Sign up:** https://console.groq.com
- **Rate limits:** Free tier allows reasonable throughput
- **Models:** llama2-70b, mixtral-8x7b

```ini
GROQ_API_KEY=gsk_your-40-char-key-here
GROQ_MODEL=llama2-70b-4096
```

#### Google Gemini (1M Tokens/Day Free)
**Best for:** Light usage, free tier, document analysis

- **Sign up:** https://aistudio.google.com/apikey
- **Create API key** for free tier access
- **Rate limit:** 1M tokens/day (free), 10K RPM

```ini
GOOGLE_API_KEY=AIza-your-39-char-key-here
GOOGLE_MODEL=gemini-pro
```

---

### Paid Providers

#### OpenAI (GPT-4, GPT-3.5)
**Best for:** Advanced reasoning, GPT-4 access

- **Sign up:** https://platform.openai.com/account/api-keys
- **Billing:** Pay-as-you-go, set usage limits
- **Models:** gpt-4, gpt-4-turbo, gpt-3.5-turbo

```ini
OPENAI_API_KEY=sk-your-48-char-key-here
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_ORG_ID=org-your-id-here  # Optional: for org access
```

#### Anthropic Claude (Advanced Reasoning)
**Best for:** Long contexts, complex reasoning, safety-focused

- **Sign up:** https://console.anthropic.com/keys
- **Billing:** Pay-as-you-go with monthly billing
- **Models:** claude-opus-4, claude-sonnet, claude-haiku

```ini
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-opus-4
```

#### xAI Grok (Early Access)
**Best for:** Twitter context integration, experimental models

- **Sign up:** https://console.x.ai/
- **Note:** Requires early access approval
- **Models:** grok-1

```ini
XAI_API_KEY=xai-your-key-here
XAI_MODEL=grok-1
```

---

## LLM Selection Configuration

### Primary Provider Selection

```ini
# Which provider to use by default
PRIMARY_LLM_PROVIDER=groq  # groq, openai, anthropic, google, ollama, xai

# Fallback chain (tries providers in order)
FALLBACK_LLM_PROVIDERS=groq,google,ollama

# Enable/disable providers
ENABLE_GROQ=true
ENABLE_OPENAI=false
ENABLE_ANTHROPIC=false
ENABLE_GOOGLE=true
ENABLE_OLLAMA=true
ENABLE_XAI=false

# Default model timeout (seconds)
LLM_TIMEOUT=30
```

### Temperature and Parameters

```ini
# Generation parameters
LLM_TEMPERATURE=0.7          # 0.0 (deterministic) to 1.0 (creative)
LLM_MAX_TOKENS=2000          # Maximum response length
LLM_TOP_P=0.9                # Nucleus sampling
LLM_FREQUENCY_PENALTY=0.0    # Penalize repetition
```

---

## Docker-Specific Settings

When running in Docker containers via `docker-compose.yml`, use `.env.docker` with these service hostnames:

```ini
# Neo4j in Docker network
NEO4J_URI=bolt://neo4j:7687

# Redis in Docker network
REDIS_HOST=redis
REDIS_PORT=6379

# Redpanda in Docker network
REDPANDA_BROKERS=redpanda:9092

# PostgreSQL in Docker network
DATABASE_URL=postgresql://brain:brain_password@postgres:5432/brain_db

# Ollama (runs on host network, or separate container)
OLLAMA_BASE_URL=http://ollama:11434

# Service discovery
ENABLE_SERVICE_DISCOVERY=true
DOCKER_INTERNAL_NETWORK=agentic-brain-network
```

### Docker Compose Network

```yaml
# docker-compose.yml excerpt
networks:
  agentic-brain-network:
    driver: bridge

services:
  neo4j:
    networks:
      - agentic-brain-network
    
  redis:
    networks:
      - agentic-brain-network
    
  brain:
    networks:
      - agentic-brain-network
    env_file:
      - .env.docker
```

---

## SSL/Corporate Proxy Settings

### SSL Certificate Verification

```ini
# For self-signed certificates or corporate proxies
SSL_VERIFY=false                          # Disable SSL verification (⚠️ security risk)
PYTHONHTTPSVERIFY=0                       # Python-specific
NODE_TLS_REJECT_UNAUTHORIZED=0            # Node.js-specific

# Better: Use custom CA certificate
SSL_CA_BUNDLE=/path/to/ca-bundle.crt
REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
CURL_CA_BUNDLE=/path/to/ca-bundle.crt
```

### Proxy Configuration

```ini
# HTTP Proxy
HTTP_PROXY=http://proxy.company.com:8080
HTTPS_PROXY=http://proxy.company.com:8080
NO_PROXY=localhost,127.0.0.1,.internal.company.com

# SOCKS5 Proxy
ALL_PROXY=socks5://proxy.company.com:1080
```

---

## Complete .env Template

```ini
# ============================================
# BRAIN SYSTEM CONFIGURATION
# ============================================

ENVIRONMENT=development
LOG_LEVEL=INFO
API_PORT=8000

# ============================================
# DATABASE & CACHING
# ============================================

NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=change-me-in-production

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

DATABASE_URL=postgresql://brain:brain@localhost:5432/brain_db

# ============================================
# LLM PROVIDER SELECTION
# ============================================

PRIMARY_LLM_PROVIDER=groq

# Free Providers
GROQ_API_KEY=gsk_your-key-here
GOOGLE_API_KEY=AIza-your-key-here
OLLAMA_BASE_URL=http://localhost:11434

# Paid Providers (optional)
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
XAI_API_KEY=xai-your-key-here

# LLM Settings
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
LLM_TIMEOUT=30

# ============================================
# OPTIONAL: INTEGRATIONS
# ============================================

# GitHub
GITHUB_TOKEN=ghp_your-token-here
GITHUB_OWNER=your-org
GITHUB_REPO=your-repo

# Slack
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_SIGNING_SECRET=your-secret-here

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password-here

# ============================================
# SECURITY (Local Dev Only)
# ============================================

# ⚠️ NEVER use these in production
ENVIRONMENT=development
DEBUG=true
```

---

## Verification Commands

### Test LLM Connectivity

```bash
# Test Groq
python -c "from groq import Groq; Groq(api_key='$GROQ_API_KEY').chat.completions.create(model='llama2-70b-4096', messages=[{'role': 'user', 'content': 'test'}])" && echo "✓ Groq works"

# Test OpenAI
python -c "import openai; openai.api_key='$OPENAI_API_KEY'; openai.ChatCompletion.create(model='gpt-3.5-turbo', messages=[{'role': 'user', 'content': 'test'}])" && echo "✓ OpenAI works"

# Test Ollama
curl http://localhost:11434/api/generate -d '{"model":"neural-chat","prompt":"test"}' && echo "✓ Ollama works"

# Test Google
python -c "import google.generativeai as genai; genai.configure(api_key='$GOOGLE_API_KEY'); genai.GenerativeModel('gemini-pro').generate_content('test')" && echo "✓ Google works"
```

### Test Database Connectivity

```bash
# Neo4j
python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('$NEO4J_URI', auth=('$NEO4J_USERNAME', '$NEO4J_PASSWORD')); driver.verify_connectivity(); print('✓ Neo4j connected')"

# Redis
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping

# PostgreSQL
psql "$DATABASE_URL" -c "SELECT version();" && echo "✓ PostgreSQL connected"
```

### Test Docker Environment

```bash
# Load and verify .env.docker
docker compose config

# Check all services are running
docker compose ps

# Test from inside container
docker compose exec brain python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('✓ All env vars loaded')"
```

---

## Troubleshooting

### API Key Not Working

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Invalid API key | Verify key in console, regenerate if needed |
| `403 Forbidden` | Key lacks permissions | Check API key scope/permissions in provider console |
| `429 Too Many Requests` | Rate limit hit | Implement exponential backoff, check tier limits |
| `Connection refused` | Service unreachable | Verify host/port, check firewall, ensure service is running |

### .env File Not Loading

```bash
# Check file exists and is readable
ls -la .env

# Verify format (no spaces around =)
cat .env | grep -E '^[A-Z_]+='

# Check for BOM or encoding issues
file .env  # Should show "ASCII text" or "UTF-8 Unicode text"

# Force UTF-8 encoding
iconv -f iso-8859-1 -t utf-8 .env > .env.fixed && mv .env.fixed .env
```

### Docker Container Can't Connect to Service

```bash
# Check network connectivity
docker compose exec brain ping neo4j

# Verify hostname resolution
docker compose exec brain getent hosts neo4j

# Check service is running
docker compose logs neo4j

# Inspect network
docker network inspect agentic-brain-network
```

### SSL Certificate Errors

```bash
# Update certificate bundle
pip install --upgrade certifi

# For Python (Linux)
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# For Python (macOS)
/Applications/Python\ 3.*/Install\ Certificates.command

# Verify certificate chain
openssl s_client -connect api.openai.com:443 -showcerts
```

### LLM Timeout Issues

```ini
# Increase timeout
LLM_TIMEOUT=60

# Add retry logic
MAX_RETRIES=3
RETRY_BACKOFF_MS=1000
```

---

## Security Best Practices

### ✅ DO:

- ✅ Use `.env.example` as a template (committed to git)
- ✅ Add `.env` and `.env.docker` to `.gitignore`
- ✅ Rotate API keys regularly
- ✅ Use read-only API keys where possible
- ✅ Restrict API key permissions to minimum needed
- ✅ Use environment-specific keys (dev/staging/prod)
- ✅ Store production credentials in secure secret manager (AWS Secrets Manager, HashiCorp Vault, etc.)

### ❌ DON'T:

- ❌ Commit `.env` files to git
- ❌ Use the same key in development and production
- ❌ Commit API keys in code or comments
- ❌ Pass API keys as command-line arguments
- ❌ Log or print API keys
- ❌ Disable SSL verification in production
- ❌ Share `.env` files via email or chat

---

## Production Deployment

For production environments, **never commit `.env` files**. Instead, use a secure secret manager:

### AWS Secrets Manager

```python
import json
import boto3

client = boto3.client('secretsmanager')
secret = json.loads(client.get_secret_value(SecretId='agentic-brain')['SecretString'])
os.environ.update(secret)
```

### HashiCorp Vault

```bash
# Fetch secrets at startup
vault kv get -format=json secret/agentic-brain | jq '.data.data' > /run/secrets/.env.json
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: brain-secrets
type: Opaque
stringData:
  OPENAI_API_KEY: sk-your-key-here
  GROQ_API_KEY: gsk_your-key-here
---
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: brain
    envFrom:
    - secretRef:
        name: brain-secrets
```

---

## Next Steps

1. **Copy template files:**
   ```bash
   cp .env.example .env
   cp .env.docker.example .env.docker
   ```

2. **Add API keys** (follow verification commands above)

3. **Start development:**
   ```bash
   # Local
   python -m brain.main
   
   # Docker
   docker compose up -d
   ```

4. **Join the team** - share your setup questions in #dev-setup

---

## Support

- **Issues?** Check `.env.example` for current template
- **Lost API key?** Regenerate in provider console
- **Docker errors?** Review `docker compose logs`
- **Questions?** Ask in #agentic-brain channel
