# 🏗️ JHipster Integration

> **Enterprise-Grade AI Applications in Minutes, Not Months**

JHipster is the world's most popular full-stack application generator with 2.5+ million annual downloads. Agentic Brain brings JHipster's battle-tested enterprise patterns to AI development, giving you production-ready infrastructure from day one.

---

## 🎯 What JHipster Brings

### The Problem: AI Projects Start from Scratch

Every AI project reinvents:
- Authentication (JWT, OAuth2, LDAP...)
- API design (pagination, error handling...)
- Configuration management (dev/staging/prod...)
- Deployment (Docker, Kubernetes, cloud...)
- Monitoring (health checks, metrics...)

Weeks of boilerplate before writing a single AI feature.

### The Solution: Enterprise Patterns That Work

JHipster represents **10+ years of enterprise Java wisdom**, distilled into generators and patterns. Agentic Brain adopts these patterns for Python AI projects:

| JHipster Pattern | Agentic Brain Equivalent | Benefit |
|------------------|--------------------------|---------|
| Spring Security | `auth/` module | JWT, OAuth2, OIDC, LDAP, SAML |
| Spring Profiles | `config/settings.py` | Environment-based config |
| Liquibase | `migrations/` | Neo4j schema versioning |
| Actuator | `health/` | Pluggable health checks |
| Spring Data | `domain/` | Entity models |
| Docker Compose | `docker/` | Dev/prod compose files |
| Kubernetes | `k8s/` | Production manifests |

---

## 🧠 How Agentic Brain Integrates

### 1. Configuration Management (Spring Profiles Style)

```python
from agentic_brain.config import settings

# Automatic environment detection
# Reads from: .env.dev, .env.staging, .env.prod

print(settings.environment)        # "dev", "staging", "prod"
print(settings.neo4j.uri)          # bolt://localhost:7687
print(settings.llm.default_model)  # "gpt-4o"
print(settings.security.jwt_secret) # SecretStr (never logged)
```

**File Structure:**
```
.env.dev       # Development settings
.env.staging   # Staging settings  
.env.prod      # Production settings (never commit!)
.env.test      # Test settings
```

### 2. API Response Format (JHipster Standard)

```python
from agentic_brain.api import ApiResponse, PaginationInfo

# Consistent response format across all endpoints
response = ApiResponse.success(
    data=agents,
    pagination=PaginationInfo(
        total_items=150,
        page=1,
        items_per_page=20,
    ),
    links={
        "self": "/api/agents?page=1",
        "next": "/api/agents?page=2",
        "last": "/api/agents?page=8",
    }
)

# Output:
# {
#   "success": true,
#   "data": [...],
#   "pagination": {
#     "totalItems": 150,
#     "totalPages": 8,
#     "currentPage": 1,
#     "itemsPerPage": 20
#   },
#   "_links": {
#     "self": "/api/agents?page=1",
#     "next": "/api/agents?page=2"
#   }
# }
```

### 3. Health Checks (Spring Actuator Style)

```python
from agentic_brain.health import HealthIndicatorRegistry, Health

registry = HealthIndicatorRegistry()

@registry.indicator("neo4j")
async def check_neo4j() -> Health:
    """Check Neo4j connectivity."""
    try:
        await driver.verify_connectivity()
        return Health.up(response_time_ms=15)
    except Exception as e:
        return Health.down(error=str(e))

@registry.indicator("llm")
async def check_llm() -> Health:
    """Check LLM provider availability."""
    provider = get_active_provider()
    return Health.up(provider=provider.name, model=provider.model)

@registry.indicator("rag")
async def check_rag() -> Health:
    """Check RAG pipeline readiness."""
    index_count = await neo4j.count_vectors()
    return Health.up(indexed_documents=index_count)

# Aggregate health check
health = await registry.check()
# {
#   "status": "UP",
#   "components": {
#     "neo4j": {"status": "UP", "details": {"response_time_ms": 15}},
#     "llm": {"status": "UP", "details": {"provider": "openai"}},
#     "rag": {"status": "UP", "details": {"indexed_documents": 50000}}
#   }
# }
```

### 4. Database Migrations (Liquibase Style)

```python
from agentic_brain.migrations import MigrationRunner, CypherMigration

migrations = [
    CypherMigration(
        version="0001",
        description="Create user indexes",
        author="joseph",
        up_cypher=[
            "CREATE INDEX user_email IF NOT EXISTS FOR (u:User) ON (u.email)",
            "CREATE INDEX user_id IF NOT EXISTS FOR (u:User) ON (u.id)",
        ],
        down_cypher=[
            "DROP INDEX user_email IF EXISTS",
            "DROP INDEX user_id IF EXISTS",
        ],
    ),
    CypherMigration(
        version="0002",
        description="Add vector index for embeddings",
        author="joseph",
        up_cypher=[
            """
            CREATE VECTOR INDEX document_embeddings IF NOT EXISTS
            FOR (d:Document) ON (d.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
            """
        ],
    ),
]

# Run migrations (tracks applied, checksums, execution time)
runner = MigrationRunner(driver=neo4j_driver, migrations=migrations)
await runner.run()
```

### 5. JWT with Refresh Token Rotation

```python
from agentic_brain.auth import RefreshTokenService, create_access_token

# JHipster-compatible JWT claims
token = create_access_token(
    user_id="user123",
    user_login="alice@example.com",
    roles=["ROLE_ADMIN", "ROLE_USER"],  # JHipster format
)

# Family-based refresh token rotation (reuse detection)
service = RefreshTokenService()

# Initial login
tokens = service.create_tokens(
    user_id="user123",
    user_login="alice@example.com",
)
# tokens.access_token, tokens.refresh_token

# Refresh (old token revoked, new tokens issued)
new_tokens = service.refresh(tokens.refresh_token)

# If old token reused (stolen?), entire family revoked!
try:
    service.refresh(tokens.refresh_token)  # Old token
except TokenReusedException:
    # Alert security team!
    pass
```

---

## 💡 Example: Generate a Complete AI App

### Vision: JHipster Blueprint for Agentic Brain

```bash
# Future command (blueprint in development)
jhipster --blueprints agentic-brain

? What is the application name? my-ai-app
? Which AI providers? OpenAI, Anthropic, Local (Ollama)
? Enable RAG pipeline? Yes
? Vector database? Neo4j (with vector search)
? Authentication type? JWT with refresh tokens
? Include example agents? Yes

Generating...
✅ FastAPI application structure
✅ Neo4j schema and migrations
✅ RAG pipeline with hardware acceleration
✅ JWT authentication with refresh tokens
✅ Health checks and monitoring
✅ Docker Compose (dev + prod)
✅ Kubernetes manifests
✅ GitHub Actions CI/CD
✅ Example chatbot agent
✅ Example document processor agent

Your AI application is ready!
cd my-ai-app && docker compose up
```

### Current: Manual Setup with JHipster Patterns

```python
# main.py - Production-ready from start
from fastapi import FastAPI
from agentic_brain import Agent
from agentic_brain.config import settings
from agentic_brain.health import create_health_routes
from agentic_brain.durability import create_dashboard_routes
from agentic_brain.api import error_handler

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
)

# JHipster-style health endpoints
app.include_router(create_health_routes())

# Workflow dashboard
app.include_router(create_dashboard_routes())

# Global error handling
app.add_exception_handler(Exception, error_handler)

# Your AI agent
agent = Agent(
    name="assistant",
    llm=settings.llm.default_model,
)

@app.post("/api/chat")
async def chat(message: str):
    response = await agent.chat(message)
    return ApiResponse.success(data={"response": response})
```

---

## 🏢 Enterprise Features Comparison

| Feature | JHipster (Java) | Agentic Brain (Python) | Status |
|---------|-----------------|------------------------|--------|
| **Authentication** | | | |
| JWT | ✅ | ✅ | Complete |
| OAuth2/OIDC | ✅ | ✅ | Complete |
| LDAP | ✅ | ✅ | Complete |
| SAML | ❌ | ✅ | **Exceeds** |
| API Keys | ❌ | ✅ | **Exceeds** |
| **Configuration** | | | |
| Profiles (dev/prod) | ✅ | ✅ | Complete |
| Secrets management | ✅ | ✅ | Complete |
| Environment files | ✅ | ✅ | Complete |
| **API Design** | | | |
| Pagination | ✅ | ✅ | Complete |
| HATEOAS links | ✅ | ✅ | Complete |
| Error format | ✅ | ✅ | Complete |
| OpenAPI docs | ✅ | ✅ | Complete |
| **Deployment** | | | |
| Docker Compose | ✅ | ✅ | Complete |
| Kubernetes | ✅ | ✅ | Complete |
| AWS/Azure/GCP | ✅ | ✅ | Complete |
| **Monitoring** | | | |
| Health checks | ✅ | ✅ | Complete |
| Metrics | ✅ | ✅ | Complete |
| Tracing | ✅ | ✅ | Complete |
| **AI Features** | | | |
| LLM integration | ❌ | ✅ | **Unique** |
| RAG pipeline | ❌ | ✅ | **Unique** |
| Agent framework | ❌ | ✅ | **Unique** |
| Durable workflows | ❌ | ✅ | **Unique** |

---

## 🐳 Docker Compose Templates

### Development

```yaml
# docker-compose.dev.yml
services:
  agentic-brain:
    build: .
    volumes:
      - .:/app  # Hot reload
    environment:
      - ENVIRONMENT=dev
      - NEO4J_URI=bolt://neo4j:7687
    ports:
      - "8000:8000"
    depends_on:
      neo4j:
        condition: service_healthy

  neo4j:
    image: neo4j:5-community
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc"]
    ports:
      - "7474:7474"
      - "7687:7687"
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "password", "RETURN 1"]
```

### Production

```yaml
# docker-compose.prod.yml
services:
  agentic-brain:
    image: ghcr.io/my-org/agentic-brain:latest
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 2G
          cpus: "2"
    environment:
      - ENVIRONMENT=prod
      - NEO4J_URI=bolt://neo4j-cluster:7687
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## ☸️ Kubernetes Manifests

```yaml
# k8s/deployment.yaml
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
    spec:
      containers:
        - name: agentic-brain
          image: ghcr.io/my-org/agentic-brain:latest
          ports:
            - containerPort: 8000
          livenessProbe:
            httpGet:
              path: /health/liveness
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health/readiness
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2"
          envFrom:
            - configMapRef:
                name: agentic-brain-config
            - secretRef:
                name: agentic-brain-secrets
```

---

## 🔥 Why This Matters

### Before (Without JHipster Patterns)

Week 1: "Let me figure out JWT..."
Week 2: "How do config files work again?"
Week 3: "Docker is hard..."
Week 4: "Kubernetes YAML is painful..."
Week 5: "Finally writing AI code!"

### After (With Agentic Brain + JHipster Patterns)

Day 1: `pip install agentic-brain`
Day 1: "My AI agent is live with auth, health checks, and K8s ready!"

### Real-World Impact

| Task | Without JHipster Patterns | With Agentic Brain |
|------|--------------------------|-------------------|
| Setup auth | 2-3 weeks | 5 minutes |
| Add health checks | 1 week | Already included |
| Docker + K8s | 2 weeks | Pre-built templates |
| API pagination | 3 days | `PaginationInfo()` |
| Config management | 1 week | `settings.py` |
| **Total infrastructure** | **8-10 weeks** | **1 day** |

---

## 🚀 Getting Started

### Use JHipster Frontend with Agentic Brain Backend

```bash
# Generate JHipster React frontend
jhipster --skip-server --client-framework react

# Configure API endpoint
echo "SERVER_API_URL=http://localhost:8000" >> .env

# Start Agentic Brain backend
cd ../agentic-brain
docker compose up

# Start JHipster frontend
cd ../jhipster-app
npm start
```

### Use Agentic Brain as Complete Stack

```bash
# Clone starter template
git clone https://github.com/agentic-brain-project/agentic-brain-starter
cd agentic-brain-starter

# Start everything
docker compose up

# API: http://localhost:8000
# Docs: http://localhost:8000/docs
# Health: http://localhost:8000/health
# Neo4j: http://localhost:7474
```

---

## 📚 Resources

- [JHipster Alignment Strategy](../JHIPSTER_ALIGNMENT.md) - Full alignment details
- [JHipster Documentation](https://www.jhipster.tech/)
- [Enterprise Deployment Guide](../ENTERPRISE.md)
- [Security Best Practices](../SECURITY.md)

---

*Agentic Brain + JHipster: Enterprise-grade AI, Python-native, production-ready.*
