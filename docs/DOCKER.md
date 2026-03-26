# Docker Infrastructure Guide

## Overview

Rock-solid Docker infrastructure for agentic-brain with multi-stage builds, comprehensive testing, and production-ready orchestration.

## 🏗️ Architecture

### Production Stack
```
┌─────────────────────────────────────────────────────────┐
│                   Agentic Brain API                      │
│                  (Multi-stage Build)                     │
│                   Port: 8000                             │
└──────────────┬──────────────┬───────────────────────────┘
               │              │
       ┌───────▼─────┐   ┌────▼─────┐   ┌──────────────┐
       │   Neo4j     │   │  Redis   │   │  Redpanda    │
       │   5.15      │   │  7.x     │   │  (Kafka)     │
       │  Port 7687  │   │ Port 6379│   │  Port 9092   │
       └─────────────┘   └──────────┘   └──────────────┘
```

## 📦 Files

### Core Files
- **`Dockerfile`** - Production multi-stage build (Python 3.12, non-root user)
- **`Dockerfile.test`** - Testing image with test dependencies
- **`docker-compose.yml`** - Production orchestration
- **`docker-compose.test.yml`** - CI/CD testing stack
- **`.dockerignore`** - Build optimization (excludes venv, cache, etc.)

### Scripts
- **`scripts/docker/build.sh`** - Build production image
- **`scripts/docker/test.sh`** - Run tests in Docker
- **`scripts/docker/dev.sh`** - Start dev environment

## 🚀 Quick Start

### Development

```bash
# Start all services (Neo4j, Redis, Redpanda, API)
./scripts/docker/dev.sh --detach

# View logs
./scripts/docker/dev.sh --logs

# Check status
./scripts/docker/dev.sh --status

# Stop everything
./scripts/docker/dev.sh --stop
```

### Building

```bash
# Build production image
./scripts/docker/build.sh

# Build with no cache
./scripts/docker/build.sh --no-cache

# Build and tag
./scripts/docker/build.sh --tag v1.0.0

# Build and push to registry
./scripts/docker/build.sh --tag v1.0.0 --push
```

### Testing

```bash
# Run tests in Docker (clean environment)
./scripts/docker/test.sh

# Rebuild test image and run
./scripts/docker/test.sh --rebuild

# Run in background
./scripts/docker/test.sh --detach
```

## 🏭 Production Deployment

### Using Docker Compose

```bash
# Set environment variables
cp .env.example .env
# Edit .env with production credentials

# Start production stack
docker compose up -d

# Check health
docker compose ps
docker compose logs -f agentic-brain

# Scale API instances
docker compose up -d --scale agentic-brain=3
```

### Manual Container Run

```bash
# Build
docker build -t agentic-brain:latest .

# Run with environment
docker run -d \
  --name agentic-brain \
  -p 8000:8000 \
  -e NEO4J_URI=bolt://neo4j:7687 \
  -e NEO4J_PASSWORD=secret \
  -e REDIS_URL=redis://:secret@redis:6379 \
  -e KAFKA_BOOTSTRAP_SERVERS=redpanda:9092 \
  --restart unless-stopped \
  agentic-brain:latest
```

## 🏗️ Multi-Stage Build

### Stage 1: Builder
- Installs build tools (gcc, git)
- Builds Python wheels
- Creates optimized wheel directory

### Stage 2: Production
- Minimal Python 3.12 slim base
- Only runtime dependencies (curl, ca-certificates)
- Installs pre-built wheels
- Non-root user (uid 1000)
- Health check included

**Benefits:**
- **50-70% smaller** image size
- **No build tools** in production
- **Security hardened** (non-root, minimal attack surface)
- **Faster deployment** (smaller image to pull)

## 🔒 Security Features

### Image Security
✅ Non-root user (uid 1000)  
✅ No build tools in production image  
✅ Minimal base image (python:3.12-slim)  
✅ Health checks configured  
✅ Read-only root filesystem compatible  

### Network Security
✅ Internal Docker network isolation  
✅ Exposed ports: only 8000 (API)  
✅ Service-to-service: internal network only  

### Data Security
✅ Persistent volumes for data  
✅ No credentials in Dockerfile  
✅ Environment-based configuration  

## 🧪 Testing in CI/CD

### GitHub Actions Workflow

The CI pipeline (`ci.yml`) includes a Docker test job:

```yaml
docker-test:
  runs-on: ubuntu-latest
  steps:
    - Build test image
    - Start services (Neo4j, Redis, Redpanda)
    - Wait for health checks
    - Run pytest in container
    - Upload results
```

### Test Compose Features

- **tmpfs volumes** - Fast, ephemeral storage for tests
- **Smaller resource limits** - Optimized for CI (512M memory)
- **Quick health checks** - Faster startup (5s intervals)
- **Clean isolation** - Each test run is pristine

### Running Locally

```bash
# Exactly like CI
docker compose -f docker-compose.test.yml run --rm test

# Interactive debugging
docker compose -f docker-compose.test.yml run --rm --entrypoint bash test
```

## 📊 Service Details

### Neo4j (Graph Database)

```yaml
Image: neo4j:5.15-community
Ports: 7474 (HTTP), 7687 (Bolt)
Plugins: APOC
Memory: 1G heap max (prod), 512M (test)
Health: cypher-shell connectivity
Volume: agentic_brain_neo4j_data
```

**Access:**
- Browser: http://localhost:7474
- Credentials: neo4j / $NEO4J_PASSWORD

### Redis (Cache/Queue)

```yaml
Image: redis:7-alpine
Port: 6379
Persistence: AOF (appendonly yes)
Security: Password protected
Health: redis-cli ping
Volume: agentic_brain_redis_data
```

**Features:**
- Persistent storage (AOF)
- Password authentication
- Used for: caching, task queues, session storage

### Redpanda (Event Streaming)

```yaml
Image: redpandadata/redpanda:latest
Ports: 9092 (Kafka), 8081 (Schema), 8082 (REST), 9644 (Admin)
Memory: 1G (prod), 512M (test)
Health: rpk cluster health
Volume: agentic_brain_redpanda_data
```

**Features:**
- Kafka-compatible API
- Schema registry
- REST API (Pandaproxy)
- Lightweight (no JVM)

**Use cases:**
- Event sourcing
- Audit logs
- Agent communication
- Real-time data streaming

### Agentic Brain API

```yaml
Build: Multi-stage Dockerfile
Port: 8000
User: agentic (uid 1000)
Health: /health endpoint (30s interval)
Restart: always
```

**Environment Variables:**
```bash
NEO4J_URI=bolt://neo4j:7687
REDIS_URL=redis://:password@redis:6379/0
KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_HOST=http://host.docker.internal:11434
```

## 🔧 Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs agentic-brain

# Check health
docker compose ps

# Inspect container
docker inspect agentic-brain-api
```

### Service Dependencies

```bash
# Verify Neo4j is accessible
docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD "RETURN 1"

# Verify Redis
docker compose exec redis redis-cli -a $REDIS_PASSWORD ping

# Verify Redpanda
docker compose exec redpanda rpk cluster health
```

### Performance Issues

```bash
# Check resource usage
docker stats

# View container processes
docker compose top

# Increase resources in docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
```

### Network Issues

```bash
# Inspect network
docker network inspect agentic-brain-network

# Test connectivity between services
docker compose exec agentic-brain curl http://redis:6379
docker compose exec agentic-brain nc -zv neo4j 7687
```

## 📈 Production Best Practices

### 1. Resource Limits

Always set resource limits in production:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '1'
      memory: 1G
```

### 2. Health Checks

All services have health checks configured. Monitor with:

```bash
docker compose ps
```

### 3. Logging

Configure logging drivers:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 4. Backups

Backup volumes regularly:

```bash
# Backup Neo4j
docker compose exec neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j.dump

# Backup Redis
docker compose exec redis redis-cli --rdb /data/backup.rdb
```

### 5. Updates

Update images safely:

```bash
# Pull latest images
docker compose pull

# Recreate containers (zero-downtime with proper health checks)
docker compose up -d --no-deps --build agentic-brain
```

### 6. Monitoring

Integrate with monitoring tools:
- Prometheus + Grafana
- Datadog
- New Relic
- ELK Stack

Health endpoint: `GET /health`

## 🌍 Cloud Deployment

### AWS ECS

```bash
# Build for ECR
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REGISTRY
docker build -t $ECR_REGISTRY/agentic-brain:latest .
docker push $ECR_REGISTRY/agentic-brain:latest
```

### Google Cloud Run

```bash
# Build for GCR
gcloud builds submit --tag gcr.io/$PROJECT_ID/agentic-brain
gcloud run deploy agentic-brain --image gcr.io/$PROJECT_ID/agentic-brain --platform managed
```

### Azure Container Instances

```bash
# Build for ACR
az acr build --registry $ACR_NAME --image agentic-brain:latest .
az container create --resource-group $RG --name agentic-brain --image $ACR_NAME.azurecr.io/agentic-brain:latest
```

### Kubernetes (Helm)

See `helm/` directory for Kubernetes deployment charts.

## 🔍 Advanced Topics

### Custom Networks

```bash
# Create custom network
docker network create --driver bridge agentic-network

# Use in docker-compose.yml
networks:
  default:
    external:
      name: agentic-network
```

### Secrets Management

```bash
# Use Docker secrets (Swarm mode)
echo "my_password" | docker secret create neo4j_password -

# Reference in compose
secrets:
  neo4j_password:
    external: true
```

### Multi-Architecture Builds

```bash
# Build for ARM64 + AMD64
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t agentic-brain:latest --push .
```

## 📚 References

- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Health Checks](https://docs.docker.com/engine/reference/builder/#healthcheck)

## 🆘 Support

- **Issues**: https://github.com/joseph-webber/agentic-brain/issues
- **Discussions**: https://github.com/joseph-webber/agentic-brain/discussions
- **Email**: joseph.webber@me.com

---

**Built with ❤️ for reliable, production-grade AI infrastructure**
