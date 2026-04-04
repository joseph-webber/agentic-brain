# Tutorial 5: Production Deployment

**Objective:** Deploy Agentic Brain to production with Docker, scaling, monitoring, and security best practices.

**Time:** 20 minutes  
**Difficulty:** Advanced  
**Prerequisites:** Completed Tutorials 1-4, Docker installed

---

## What You'll Build

A production-ready deployment with:
- Docker containerization
- Docker Compose for local stack
- Kubernetes manifests (optional)
- Health checks and monitoring
- Proper logging and tracing
- Security hardening
- Auto-scaling configuration

---

## Prerequisites

```bash
# Check Docker installation
docker --version   # 20.10+
docker-compose --version  # 1.29+

# Optional: Kubernetes
kubectl version --client  # For K8s deployment
```

---

## Part 1: Docker Container

Create `Dockerfile`:

```dockerfile
# Dockerfile - Multi-stage build for production

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /home/botuser/.local

# Copy application code
COPY --chown=botuser:botuser . .

# Set environment variables
ENV PATH=/home/botuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER botuser

# Expose ports
EXPOSE 8000

# Run application
CMD ["python", "-m", "agentic_brain.api"]
```

---

## Part 2: Docker Compose Stack

Create `docker-compose.yml`:

```yaml
version: '3.9'

services:
  # Neo4j Graph Database
  neo4j:
    image: neo4j:5-enterprise
    container_name: agentic_brain_neo4j
    environment:
      NEO4J_AUTH: neo4j/change_me_in_production
      NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
      NEO4J_dbms_memory_pagecache_size: 2G
      NEO4J_dbms_memory_heap_initial_size: 2G
      NEO4J_dbms_memory_heap_max_size: 2G
    ports:
      - "7687:7687"  # Bolt
      - "7474:7474"  # Browser
    volumes:
      - neo4j_data:/var/lib/neo4j/data
      - neo4j_logs:/var/lib/neo4j/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7474"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - agentic_network
    restart: unless-stopped

  # Redis for session storage
  redis:
    image: redis:7-alpine
    container_name: agentic_brain_redis
    command: redis-server --requirepass change_me_in_production
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - agentic_network
    restart: unless-stopped

  # Ollama for local LLM inference (optional)
  ollama:
    image: ollama/ollama:latest
    container_name: agentic_brain_ollama
    environment:
      OLLAMA_HOST: 0.0.0.0:11434
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - agentic_network
    restart: unless-stopped
    # Pre-pull model on startup
    # command: ollama pull mistral

  # Main application
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: agentic_brain_api
    environment:
      # Database
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USERNAME: neo4j
      NEO4J_PASSWORD: change_me_in_production
      
      # Cache
      REDIS_URL: redis://:change_me_in_production@redis:6379/0
      
      # LLM
      LLM_PROVIDER: ollama
      LLM_MODEL: mistral
      OLLAMA_HOST: http://ollama:11434
      
      # API
      API_HOST: 0.0.0.0
      API_PORT: 8000
      
      # Logging
      LOG_LEVEL: INFO
      DEBUG: "false"
      
      # Security
      CORS_ORIGINS: "http://localhost:3000,http://localhost:8080"
      API_KEY_REQUIRED: "true"
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src  # For development
      - ./logs:/app/logs
    depends_on:
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - agentic_network
    restart: unless-stopped

  # Optional: Prometheus for metrics
  prometheus:
    image: prom/prometheus:latest
    container_name: agentic_brain_prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - agentic_network
    restart: unless-stopped

  # Optional: Grafana for dashboards
  grafana:
    image: grafana/grafana:latest
    container_name: agentic_brain_grafana
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_INSTALL_PLUGINS: grafana-piechart-panel
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - prometheus
    networks:
      - agentic_network
    restart: unless-stopped

volumes:
  neo4j_data:
    driver: local
  neo4j_logs:
    driver: local
  redis_data:
    driver: local
  ollama_models:
    driver: local
  prometheus_data:
    driver: local
  grafana_data:
    driver: local

networks:
  agentic_network:
    driver: bridge
```

---

## Part 3: Environment Configuration

Create `.env.production`:

```bash
# Database
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=YOUR_SECURE_PASSWORD_HERE

# Cache
REDIS_URL=redis://:YOUR_SECURE_PASSWORD_HERE@redis:6379/0

# LLM Configuration
LLM_PROVIDER=ollama
LLM_MODEL=mistral
OLLAMA_HOST=http://ollama:11434

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_KEY_REQUIRED=true

# Security
SECRET_KEY=YOUR_SECRET_KEY_HERE
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Logging
LOG_LEVEL=INFO
DEBUG=false
LOG_FILE=/var/log/agentic-brain/app.log

# Monitoring
ENABLE_TELEMETRY=true
TELEMETRY_ENDPOINT=http://otel-collector:4317

# Performance
MAX_WORKERS=4
POOL_SIZE=20
TIMEOUT_SECONDS=30
```

---

## Part 4: Production Deployment Steps

### Step 1: Build and Start Services

```bash
# Build image
docker-compose build

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# Check logs
docker-compose logs -f api
```

**Expected Output:**
```
NAME                           STATUS
agentic_brain_neo4j           Up (healthy)
agentic_brain_redis           Up (healthy)
agentic_brain_ollama          Up (healthy)
agentic_brain_api             Up (healthy)
```

### Step 2: Verify Connectivity

```bash
# Test API health
curl http://localhost:8000/health

# Expected: {"status": "ok", "version": "0.1.0"}

# Test Neo4j
docker exec agentic_brain_neo4j cypher-shell -u neo4j -p "password" "RETURN 'connected'"

# Expected: "connected"

# Check Redis
docker exec agentic_brain_redis redis-cli ping

# Expected: PONG
```

### Step 3: Initial Configuration

```bash
# Create initial admin user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "secure_password",
    "role": "admin"
  }'

# Get API key
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "secure_password"
  }'
```

---

## Part 5: Kubernetes Deployment (Optional)

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentic-brain-api
  namespace: default
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
  selector:
    matchLabels:
      app: agentic-brain-api
  template:
    metadata:
      labels:
        app: agentic-brain-api
    spec:
      containers:
      - name: api
        image: your-registry/agentic-brain:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: NEO4J_URI
          valueFrom:
            configMapKeyRef:
              name: agentic-config
              key: neo4j-uri
        - name: NEO4J_PASSWORD
          valueFrom:
            secretKeyRef:
              name: agentic-secrets
              key: neo4j-password
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: logs
          mountPath: /var/log/agentic-brain
      volumes:
      - name: logs
        emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: agentic-brain-api
spec:
  selector:
    app: agentic-brain-api
  ports:
  - port: 80
    targetPort: 8000
    name: http
  type: LoadBalancer

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agentic-brain-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agentic-brain-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

Deploy to Kubernetes:
```bash
# Create ConfigMap and Secrets
kubectl create configmap agentic-config \
  --from-literal=neo4j-uri=bolt://neo4j:7687

kubectl create secret generic agentic-secrets \
  --from-literal=neo4j-password=YOUR_PASSWORD

# Deploy
kubectl apply -f k8s/deployment.yaml

# Monitor
kubectl rollout status deployment/agentic-brain-api
kubectl logs -f deployment/agentic-brain-api
```

---

## Part 6: Monitoring and Logging

Create `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'agentic-brain'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
```

Create health check endpoint in your app:

```python
from fastapi import FastAPI
import psutil

app = FastAPI()

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/ready")
async def ready():
    """Readiness probe."""
    try:
        # Check Neo4j
        result = await memory.execute("RETURN 1")
        # Check Redis
        await cache.ping()
        return {"ready": True}
    except Exception as e:
        return {"ready": False, "error": str(e)}, 503

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return {
        "api_calls_total": 12345,
        "avg_response_time_ms": 145,
        "neo4j_connections": 5,
        "redis_connections": 3
    }
```

---

## Part 7: Security Checklist

### 🔐 Production Security

```bash
# 1. Change default passwords
# Edit .env.production with strong passwords

# 2. Enable HTTPS
# Use nginx or cloud load balancer for SSL/TLS

# 3. Set up firewall rules
# Only expose API port (8000) to users
# Neo4j, Redis, Ollama on internal network only

# 4. Enable authentication
API_KEY_REQUIRED=true
JWT_SECRET=your_long_random_secret_key

# 5. Rate limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# 6. CORS configuration
CORS_ORIGINS=https://yourdomain.com

# 7. Regular backups
docker-compose exec neo4j neo4j-admin database backup \
  --backup-dir=/var/lib/neo4j/backups \
  --database=neo4j

# 8. Log aggregation
# Forward logs to ELK, Datadog, CloudWatch, etc.
```

---

## Part 8: Monitoring Dashboard

Access Grafana: `http://localhost:3000` (admin/admin)

Create dashboard with queries:
```promql
# API response time
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Neo4j connections
neo4j_db_connections

# Redis memory usage
redis_memory_used_bytes
```

---

## Troubleshooting

### ❌ "Container won't start"

```bash
# Check logs
docker-compose logs api

# Common issues:
# 1. Port already in use: lsof -i :8000
# 2. Missing environment variables: docker-compose config
# 3. Neo4j not ready: docker-compose logs neo4j
```

### ❌ "Neo4j authentication fails"

```bash
# Reset Neo4j password
docker-compose down
rm -rf volumes/neo4j_data/*
docker-compose up

# Or update password:
docker exec agentic_brain_neo4j cypher-shell -u neo4j \
  ALTER USER neo4j SET PASSWORD 'newpassword'
```

### ❌ "High memory usage"

```bash
# Adjust JVM settings in docker-compose.yml
NEO4J_dbms_memory_heap_max_size: 1G  # Reduce from 2G

# Check top processes
docker stats
```

---

## ✅ Deployment Checklist

Before going to production:

- ✅ All passwords changed from defaults
- ✅ SSL/TLS certificates configured
- ✅ Firewalls and security groups set up
- ✅ Database backups automated
- ✅ Monitoring and alerting configured
- ✅ Rate limiting enabled
- ✅ CORS configured for your domain
- ✅ Health checks passing
- ✅ Logs aggregated
- ✅ Load balancing configured
- ✅ Auto-scaling policies set
- ✅ Disaster recovery tested

---

## 🚀 Production Deployment Patterns

### Pattern 1: Blue-Green Deployment

```bash
# Deploy new version to "green" environment
docker-compose -f docker-compose.green.yml up -d

# Test thoroughly
curl http://localhost:8001/health

# Switch traffic
# (Update nginx/load balancer config)

# Keep blue running for quick rollback
```

### Pattern 2: Canary Deployment

```bash
# Route 10% traffic to new version
# Monitor for errors
# Gradually increase to 100%
# Rollback if issues detected
```

### Pattern 3: Zero-Downtime Updates

```yaml
# In docker-compose.yml, set:
deploy:
  replicas: 3
  update_config:
    parallelism: 1
    delay: 10s
```

---

## 📚 Additional Resources

- [Docker best practices](https://docs.docker.com/develop/dev-best-practices/)
- [Kubernetes deployment guide](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Security hardening](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [Monitoring with Prometheus](https://prometheus.io/docs/)

---

## ✅ What You've Learned

- ✅ Create production Docker images
- ✅ Use Docker Compose for local development
- ✅ Deploy to Kubernetes with auto-scaling
- ✅ Set up health checks and monitoring
- ✅ Implement security best practices
- ✅ Configure logging and metrics
- ✅ Handle zero-downtime deployments

---

## 🎉 Congratulations!

You've completed all 5 tutorials! You now know how to:

1. ✅ Build a basic chatbot (Tutorial 1)
2. ✅ Integrate persistent memory (Tutorial 2)
3. ✅ Ground responses in documents (Tutorial 3)
4. ✅ Serve multiple customers safely (Tutorial 4)
5. ✅ Deploy to production (Tutorial 5)

**Next Steps:**
- Deploy your chatbot to production
- Monitor performance and user feedback
- Iterate and improve based on real usage
- Check out [Advanced Topics](../../README.md) for scaling patterns

---

**Need help?** See the [main README](../../README.md) or check the [troubleshooting guide](../TROUBLESHOOTING.md)

Happy deploying! 🚀
