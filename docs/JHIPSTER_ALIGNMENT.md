# JHipster Alignment Strategy

> **Agentic Brain + JHipster = Enterprise-Grade AI Framework**

This document outlines how agentic-brain aligns with [JHipster](https://www.jhipster.tech/) patterns to provide a battle-tested, enterprise-ready AI framework.

## Why JHipster Alignment?

JHipster is the world's most popular full-stack generator with:
- **2.5+ million** annual downloads
- **20,000+** GitHub stars
- **10+ years** of production hardening
- **Apache 2.0** license (enterprise-friendly)

By aligning with JHipster patterns, agentic-brain gains:
1. **Proven architecture patterns** - battle-tested in thousands of enterprises
2. **Familiar conventions** - developers can onboard quickly
3. **Enterprise tooling** - CI/CD, Kubernetes, cloud deployment
4. **Community ecosystem** - blueprints, modules, extensions

## License Alignment

| Aspect | JHipster | Agentic Brain |
|--------|----------|---------------|
| License | Apache 2.0 | ✅ Apache 2.0 |
| NOTICE file | Required | ✅ Included |
| SPDX headers | Standard | ✅ All files |
| CI enforcement | Yes | ✅ GitHub Actions |

## Feature Alignment Matrix

### ✅ Already Aligned

| JHipster Feature | Agentic Brain Equivalent | Status |
|------------------|--------------------------|--------|
| Spring Security | `auth/` module with JWT, OAuth2, OIDC, LDAP, SAML | ✅ EXCEEDS |
| Spring Profiles | `config/settings.py` with environment detection | ✅ Complete |
| Liquibase Migrations | `migrations/` Neo4j schema versioning | ✅ Complete |
| Health Actuator | `health/` pluggable indicator framework | ✅ Complete |
| OpenAPI/Swagger | FastAPI auto-generated docs | ✅ Equivalent |
| Docker Compose | `docker/docker-compose.{dev,prod}.yml` | ✅ Complete |
| Kubernetes | `k8s/` deployment, service, ingress, configmap | ✅ Complete |
| Cloud Deployment | AWS ECS/EKS, Azure, GCP workflows | ✅ Complete |
| API Response | `ApiResponse` with pagination + HATEOAS | ✅ Complete |
| JWT Refresh | Family-based rotation with reuse detection | ✅ Complete |
| GitHub Actions CI | `.github/workflows/ci.yml` | ✅ Equivalent |
| SonarQube Analysis | Ruff + mypy + security scanning | ✅ Equivalent |
| JUnit/Jest Tests | pytest with 3,063+ tests | ✅ EXCEEDS |

### 🎯 Agentic Brain Exceeds JHipster

| Feature | JHipster | Agentic Brain |
|---------|----------|---------------|
| Database | SQL (PostgreSQL, MySQL) | ✅ Neo4j Graph + Vector Search |
| Async Support | Reactive optional | ✅ Native async/await throughout |
| AI Integration | None | ✅ 8 LLM providers, RAG, agents |
| Real-time | WebSocket manual | ✅ Firebase + WebSocket unified |
| Auth Providers | 5 options | ✅ 8 providers including LDAP/SAML |
| Observability | Prometheus/Grafana | ✅ OpenTelemetry native |
| Workflow Engine | None | ✅ Temporal.io compatible |

## Implementation Roadmap

### Phase 1: Foundation (✅ COMPLETE)
- [x] Apache 2.0 license switch
- [x] NOTICE file with attribution
- [x] SPDX headers on all files
- [x] CI license enforcement
- [x] Pre-commit hooks

### Phase 2: Configuration (✅ COMPLETE)
- [x] Pydantic Settings profiles (dev/staging/prod/test)
- [x] Environment-based configuration with `.env.{environment}`
- [x] Secrets management with SecretStr
- [x] Nested configuration groups (Neo4j, LLM, Security, Cache)

### Phase 3: API Standardization (✅ COMPLETE)
- [x] `ApiResponse` wrapper class with factory methods
- [x] `PaginationInfo` with automatic page calculation
- [x] Error response format
- [x] HATEOAS links support

### Phase 4: Deployment Templates (✅ COMPLETE)
- [x] Kubernetes manifests
  - Deployment with health probes (liveness, readiness, startup)
  - Service (ClusterIP/LoadBalancer)
  - Ingress with TLS
  - ConfigMap and Secret templates
- [x] Docker Compose variants
  - Development (hot reload, Neo4j, Redis)
  - Production (resource limits, health checks, nginx optional)
- [x] Cloud workflows
  - AWS ECS Fargate and EKS
  - Azure Container Apps
  - Google Cloud Run

### Phase 5: Enterprise Features (✅ COMPLETE)
- [x] JWT refresh token rotation with family-based reuse detection
- [x] Pluggable health indicators (Spring Boot Actuator style)
- [x] Database migration versioning (Liquibase inspired)
- [ ] Multi-tenancy patterns (future)

### Phase 6: Deep Integration (PLANNED)
- [ ] JHipster Blueprint for agentic-brain generation
- [ ] Shared authentication gateway
- [ ] JHipster Control Center integration
- [ ] Entity generator for Neo4j

## Patterns Adopted from JHipster

### 1. Project Structure

```
agentic-brain/
├── src/agentic_brain/
│   ├── api/           # REST controllers (like Spring @RestController)
│   ├── auth/          # Security (like Spring Security)
│   ├── config/        # Configuration (like @Configuration)
│   ├── domain/        # Entities (like JPA @Entity)
│   └── service/       # Business logic (like @Service)
├── tests/             # Tests (like src/test/java)
├── docker/            # Docker files (like src/main/docker)
└── .github/workflows/ # CI/CD (like .github or Jenkinsfile)
```

### 2. Configuration Management

**JHipster (Spring):**
```yaml
# application-dev.yml
spring:
  profiles: dev
  datasource:
    url: jdbc:postgresql://localhost:5432/app
```

**Agentic Brain (Pydantic):**
```python
# config/settings.py
class Settings(BaseSettings):
    environment: str = "dev"
    neo4j_uri: str = "bolt://localhost:7687"
    
    class Config:
        env_file = f".env.{os.getenv('ENVIRONMENT', 'dev')}"
```

### 3. API Response Format

**JHipster:**
```json
{
  "data": [...],
  "totalItems": 100,
  "totalPages": 10,
  "currentPage": 1
}
```

**Agentic Brain (planned):**
```python
class ApiResponse(BaseModel):
    success: bool
    data: Any
    errors: list[str] = []
    pagination: PaginationInfo | None = None
    _links: dict[str, str] = {}  # HATEOAS
```

### 4. Health Endpoint (with Pluggable Indicators)

**JHipster Actuator:**
```
GET /management/health
{
  "status": "UP",
  "components": {
    "db": {"status": "UP"},
    "diskSpace": {"status": "UP"}
  }
}
```

**Agentic Brain (`health/` module):**
```python
from agentic_brain.health import HealthIndicatorRegistry, HealthStatus

# Create and register indicators
registry = HealthIndicatorRegistry()

@registry.indicator("neo4j")
async def check_neo4j() -> Health:
    # Verify Neo4j connection
    result = await driver.verify_connectivity()
    return Health.up(response_time_ms=result.latency)

@registry.indicator("llm")
async def check_llm() -> Health:
    # Verify LLM provider
    provider = get_active_provider()
    return Health.up(provider=provider.name)

# Aggregate health check
health = await registry.check()
# Returns: {"status": "UP", "components": {"neo4j": {...}, "llm": {...}}}
```

### 5. JWT Refresh Token Rotation

**JHipster Pattern:**
- Access token: short-lived (15 minutes)
- Refresh token: long-lived (7 days), rotated on use
- Family-based reuse detection

**Agentic Brain (`auth/refresh_tokens.py`):**
```python
from agentic_brain.auth.refresh_tokens import RefreshTokenService, InMemoryRefreshTokenStore

store = InMemoryRefreshTokenStore()
service = RefreshTokenService(store=store)

# Create tokens
result = service.create_tokens(
    user_id="user123",
    user_login="alice@example.com",
    generate_access_token=lambda uid, ulogin: jwt.encode({"sub": uid}, SECRET)
)
# result.access_token, result.refresh_token

# Rotate on refresh (secure)
new_result = service.refresh(
    token=result.refresh_token,
    generate_access_token=my_generator
)
# Old token revoked, new tokens issued

# Reuse detection: If old token reused, entire family revoked
```

### 6. Database Migrations (Liquibase-style)

**JHipster uses Liquibase:**
```xml
<changeSet id="00000000000001" author="jhipster">
    <createIndex indexName="idx_user_email">
        <column name="email"/>
    </createIndex>
</changeSet>
```

**Agentic Brain (`migrations/` module):**
```python
from agentic_brain.migrations import MigrationRunner, CypherMigration

# Define migrations
migrations = [
    CypherMigration(
        version="0001",
        description="Create user indexes",
        author="joseph",
        up_cypher=["CREATE INDEX user_email IF NOT EXISTS FOR (u:User) ON (u.email)"]
    ),
    CypherMigration(
        version="0002",
        description="Add uniqueness constraint",
        author="joseph",
        up_cypher=["CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE"]
    )
]

# Run migrations
runner = MigrationRunner(driver=neo4j_driver, migrations=migrations)
await runner.run()
# Tracks applied migrations, checksums, execution time
```

### 7. Docker Compose

**JHipster pattern:**
```yaml
# docker-compose.yml
services:
  app:
    image: myapp:latest
    depends_on:
      - postgresql
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/management/health"]
      
  postgresql:
    image: postgres:15
    volumes:
      - postgres-data:/var/lib/postgresql/data
```

**Agentic Brain (planned):**
```yaml
# docker-compose.yml
services:
  agentic-brain:
    image: agentic-brain:latest
    depends_on:
      neo4j:
        condition: service_healthy
    environment:
      - ENVIRONMENT=prod
      - NEO4J_URI=bolt://neo4j:7687
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      
  neo4j:
    image: neo4j:5-community
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "$NEO4J_PASSWORD", "RETURN 1"]
```

### 6. Kubernetes Deployment

**JHipster pattern:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: myapp
          image: myapp:latest
          ports:
            - containerPort: 8080
          livenessProbe:
            httpGet:
              path: /management/health/liveness
              port: 8080
          readinessProbe:
            httpGet:
              path: /management/health/readiness
              port: 8080
          resources:
            limits:
              memory: "1Gi"
              cpu: "1"
```

## JHipster Integration Points

### 1. JHipster + Agentic Brain as Backend

JHipster can generate a frontend (React/Angular/Vue) that communicates with agentic-brain:

```bash
# Generate JHipster frontend
jhipster --skip-server --client-framework react

# Configure to call agentic-brain API
# src/main/webapp/app/config/constants.ts
export const SERVER_API_URL = 'http://localhost:8000';
```

### 2. Agentic Brain as JHipster Blueprint

Future: Create a JHipster blueprint that generates agentic-brain services:

```bash
# Future vision
jhipster --blueprints agentic-brain
# Generates: FastAPI + Neo4j + AI agents
```

### 3. Shared Authentication

Both use JWT with similar claims:

```python
# agentic-brain JWT compatible with JHipster
{
  "sub": "user@example.com",
  "auth": "ROLE_ADMIN,ROLE_USER",  # JHipster format
  "exp": 1234567890,
  "iat": 1234567800
}
```

## Contributing

When adding new features, consider:

1. **Does JHipster have this?** - Check jhipster.tech docs
2. **Can we align?** - Use similar patterns, names, conventions
3. **Document it** - Update this file with alignment details
4. **Test it** - Ensure compatibility with JHipster frontends

## Resources

- [JHipster Documentation](https://www.jhipster.tech/documentation-archive/)
- [JHipster GitHub](https://github.com/jhipster/generator-jhipster)
- [JHipster Blueprints](https://www.jhipster.tech/modules/creating-a-blueprint/)
- [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0)

---

*This document is part of the agentic-brain project, licensed under Apache 2.0.*

---

## 🔒 LOCKED DECISION: Blueprint Strategy

**Decision Date:** 2026-03-24  
**Decision Maker:** Joseph Webber

### Strategy
1. **NOW**: Finish agentic-brain core features
2. **NOW**: Align more Spring patterns to Python
3. **LATER**: Create JHipster Blueprints (after core is stable)

### Rationale
Blueprints are **code generators**. If created too early:
- They generate outdated code
- Every agentic-brain change requires blueprint updates
- Double maintenance burden

**Wait until agentic-brain is feature-complete, then blueprints will be perfect.**

### Blocked Until
- [ ] All core features implemented
- [ ] Test coverage > 95%
- [ ] API stable (no breaking changes planned)
- [ ] Documentation complete

*This decision is LOCKED. Do not start blueprint work until criteria met.*
