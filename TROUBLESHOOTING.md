# Troubleshooting Guide

## Common Issues

### SSL Certificate Errors

**Symptom:**
```
SSL: CERTIFICATE_VERIFY_FAILED - self-signed certificate in certificate chain
```

**Cause:** Corporate proxy or SSL inspection

**Solution:** Already handled in installers. If still occurring:
```bash
export PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org [package]
```

---

### Redis Connection Refused

**Symptom:**
```
Error 111 connecting to localhost:6379. Connection refused.
```

**Cause:** App trying to connect to localhost instead of Docker network

**Solution:** Ensure .env has:
```
REDIS_HOST=redis
```
Not `localhost`!

---

### Neo4j Not Connected

**Symptom:**
```
Neo4j: ⚠️ Not connected (optional)
```

**Cause:** Neo4j still starting or wrong URI

**Solution:** 
1. Wait 30 seconds for Neo4j to initialize
2. Check .env has `NEO4J_URI=bolt://neo4j:7687`
3. Verify: `docker compose logs neo4j`

---

### GDS Plugin Not Found

**Symptom:**
```
No compatible graph-data-science plugin found
```

**Cause:** Old Neo4j image without GDS pre-installed

**Solution:** Rebuild with our custom Dockerfile:
```bash
docker compose down -v
docker compose build --no-cache neo4j
docker compose up -d
```

---

### Redpanda AIO Error (Windows)

**Symptom:**
```
Could not initialize seastar: std::runtime_error (AIO requirements)
```

**Cause:** Windows Docker Desktop doesn't support Linux AIO

**Solution:** Already fixed in docker-compose.yml:
```yaml
command:
  - redpanda
  - start
  - --mode=dev-container  # This fixes it
```

---

### FastAPI ASGI Error

**Symptom:**
```
FastAPI.__call__() missing 3 required positional arguments
```

**Cause:** Wrong uvicorn factory configuration

**Solution:** Fixed in v3.1.0. Update:
```bash
git pull
docker compose down
docker compose up -d --build
```

---

### JWT_SECRET Not Configured

**Symptom:**
```
CRITICAL: JWT_SECRET not configured!
```

**Cause:** Missing environment variable

**Solution:** Add to .env:
```
JWT_SECRET=your-super-secret-key-change-in-production
```
Or reinstall to auto-generate.

---

## Diagnostic Commands

```bash
# Check all container status
docker compose ps

# View logs for specific service
docker compose logs neo4j
docker compose logs redis
docker compose logs redpanda
docker compose logs agentic-brain

# Follow logs in real-time
docker compose logs -f

# Check container health
docker inspect agentic-brain-neo4j | grep -A 10 Health

# Test services individually
curl http://localhost:8000/health
curl http://localhost:7474
docker exec agentic-brain-redis redis-cli -a BrainRedis2026 ping
curl http://localhost:9644/v1/cluster/health

# Full restart
docker compose down -v
docker compose up -d --build
```

## Getting Help

1. Check logs: `docker compose logs`
2. Verify .env file has all required variables
3. Try clean restart: `docker compose down -v && docker compose up -d --build`
4. Open issue: https://github.com/joseph-webber/agentic-brain/issues

Commit: "docs: Create comprehensive TROUBLESHOOTING guide"
