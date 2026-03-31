# Troubleshooting Guide

## Common Issues

### SSL Certificate Errors

**Symptom:**
```
SSL: CERTIFICATE_VERIFY_FAILED - self-signed certificate in certificate chain
```

**Cause:** Corporate SSL inspection proxies intercepting SSL/TLS connections

**Solution:**

1. Set environment variables:
```bash
export PYTHONHTTPSVERIFY=0
export SSL_VERIFY=false
```

2. For pip installations, use trusted-host flags:
```bash
export PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org [package]
```

3. Or during install script:
```bash
PYTHONHTTPSVERIFY=0 SSL_VERIFY=false pip install -r requirements.txt
```

4. Add to .env.local:
```
PYTHONHTTPSVERIFY=0
SSL_VERIFY=false
```

---

### Docker Issues

**"Cannot connect to Docker daemon"**

**Symptom:**
```
Cannot connect to Docker daemon. Is the docker daemon running on this host?
```

**Solution:**
- Start Docker Desktop (macOS/Windows)
- Or start Docker daemon on Linux: `sudo systemctl start docker`

---

**"no matching manifest for windows/amd64"**

**Symptom:**
```
no matching manifest for windows/amd64 in the manifest list entries
```

**Cause:** Using Docker Desktop on Windows without WSL2 backend

**Solution:**
- Open Docker Desktop Settings → General → Enable "Use WSL 2 based engine"
- Rebuild images: `docker compose build --no-cache`

---

**Port Conflicts**

**Symptom:**
```
bind: address already in use
```

**Solution:**
1. Find process using port (e.g., port 8000):
```bash
# macOS/Linux
lsof -i :8000

# Windows
netstat -ano | findstr :8000
```

2. Kill the process:
```bash
# macOS/Linux
kill -9 <PID>

# Windows
taskkill /PID <PID> /F
```

3. Or change ports in .env:
```
API_PORT=8001
REDIS_PORT=6380
NEO4J_PORT=7688
```

---

### Build Issues

**"uvicorn not found"**

**Symptom:**
```
ModuleNotFoundError: No module named 'uvicorn'
```

**Solution:**
```bash
docker compose build --no-cache agentic-brain
docker compose up -d agentic-brain
```

---

**"agentic-brain command not found"**

**Symptom:**
```
command not found: agentic-brain
```

**Cause:** Image not rebuilt after code changes

**Solution:**
```bash
docker compose up -d --build agentic-brain
```

Always use the `--build` flag when deploying code changes!

---

**Image Not Building / Old Images Causing Issues**

**Symptom:**
```
Docker build fails or old code still running
```

**Solution:**
1. Remove old images:
```bash
docker compose down
docker system prune -a --volumes
```

2. Rebuild from scratch:
```bash
docker compose build --no-cache
docker compose up -d
```

3. Or selective rebuild:
```bash
docker rmi agentic-brain-neo4j
docker compose build neo4j
```

---

### Service Issues

**Neo4j Won't Start**

**Symptom:**
```
neo4j: Database is not available
```

**Solution:**
1. Remove volumes and rebuild:
```bash
docker compose down -v neo4j
docker compose build neo4j
docker compose up -d neo4j
```

2. Wait 30-60 seconds for initialization

3. Verify: `docker compose logs neo4j | tail -50`

---

**Redis Connection Refused**

**Symptom:**
```
Error 111 connecting to localhost:6379. Connection refused.
```

**Cause:** App trying to connect to localhost instead of Docker network

**Solution:** Ensure .env has:
```
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=BrainRedis2026
```

Not `localhost` or `127.0.0.1`!

Verify with:
```bash
docker compose exec redis redis-cli -a BrainRedis2026 ping
```

---

**Redpanda AIO Error (Windows)**

**Symptom:**
```
Could not initialize seastar: std::runtime_error (AIO requirements)
```

**Cause:** Windows Docker Desktop doesn't support Linux AIO

**Solution:** Already fixed in docker-compose.yml:
```yaml
redpanda:
  command:
    - redpanda
    - start
    - --mode=dev-container  # Enables dev-container mode
```

No action needed - already configured!

---

**API Returns 500 Errors**

**Symptom:**
```
HTTP 500 Internal Server Error
```

**Solution:**
1. Check logs:
```bash
docker compose logs agentic-brain | tail -100
docker compose logs -f agentic-brain  # Follow in real-time
```

2. Verify all services are running:
```bash
docker compose ps
```

3. Test individual services:
```bash
curl http://localhost:8000/health
docker compose exec redis redis-cli ping
docker compose exec neo4j cypher-shell "RETURN 1"
```

4. Check database connections in logs for specific errors

---

### Ollama Issues

**"ollama not found"**

**Symptom:**
```
command not found: ollama
```

**Solution:**

Install Ollama:
- **macOS:** `brew install ollama`
- **Windows:** `winget install ollama` or download from https://ollama.ai
- **Linux:** `curl -fsSL https://ollama.ai/install.sh | sh`

---

**Connection Refused on Port 11434**

**Symptom:**
```
Error: Connection refused / Cannot connect to ollama:11434
```

**Solution:**
1. Start Ollama:
```bash
ollama serve
```

2. Or run in background (macOS):
```bash
launchctl start ollama
```

3. Verify it's running:
```bash
curl http://localhost:11434
```

---

**Model Not Found / "pull llama3.2:3b" Required**

**Symptom:**
```
Error: Model 'llama3.2:3b' not found
```

**Solution:**
```bash
ollama pull llama3.2:3b
ollama pull mistral  # or other models you need
ollama list          # verify installed models
```

Models are stored in ~/.ollama/models

---

### Other Common Issues

**GDS Plugin Not Found**

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

**FastAPI ASGI Error**

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

**JWT_SECRET Not Configured**

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

## Full Reset Commands

### Standard Clean Reinstall

Complete wipe and rebuild:

```bash
# Stop all containers
docker compose down -v

# Remove all images and volumes
docker system prune -a --volumes

# Remove any local venv
rm -rf .venv venv

# Rebuild everything
docker compose build --no-cache
docker compose up -d

# Verify services
docker compose ps
```

### SSL Bypass Reinstall

For corporate environments with SSL inspection:

```bash
# Set SSL bypass environment variables
export PYTHONHTTPSVERIFY=0
export SSL_VERIFY=false
export PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"

# Clean slate
docker compose down -v
docker system prune -a --volumes

# Rebuild with SSL bypass
PYTHONHTTPSVERIFY=0 SSL_VERIFY=false docker compose build --no-cache
docker compose up -d

# Add to .env for persistence
cat >> .env << EOF
PYTHONHTTPSVERIFY=0
SSL_VERIFY=false
PIP_TRUSTED_HOST=pypi.org pypi.python.org files.pythonhosted.org
EOF
```

### Selective Service Reset

Reset individual services without full rebuild:

```bash
# Reset just Neo4j
docker compose down neo4j
docker volume rm agentic-brain-neo4j_data
docker compose build neo4j
docker compose up -d neo4j

# Reset just Redis
docker compose down redis
docker compose build redis
docker compose up -d redis

# Reset just API
docker compose down agentic-brain
docker compose build agentic-brain
docker compose up -d agentic-brain

# Reset just Ollama/LLMs
docker compose down ollama
docker compose up -d ollama
```

---

## Diagnostic Commands

### Container Status & Logs

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
docker compose logs -f agentic-brain  # Follow specific service

# View last N lines
docker compose logs --tail 100 agentic-brain

# Check container health
docker inspect agentic-brain-neo4j | grep -A 10 Health
```

### Service Health Tests

```bash
# API Health
curl http://localhost:8000/health
curl http://localhost:8000/docs  # Swagger UI

# Neo4j Web UI
curl http://localhost:7474

# Redis Connectivity
docker compose exec redis redis-cli -a BrainRedis2026 ping
docker compose exec redis redis-cli -a BrainRedis2026 COMMAND COUNT

# Redpanda Cluster Health
curl http://localhost:9644/v1/cluster/health

# Ollama Status
curl http://localhost:11434
ollama list
```

### Database Queries

```bash
# Neo4j - Execute query
docker compose exec neo4j cypher-shell "RETURN 1"
docker compose exec neo4j cypher-shell "SHOW DATABASES"
docker compose exec neo4j cypher-shell "CALL dbms.listActiveProcedures()"

# Redis - Get info
docker compose exec redis redis-cli -a BrainRedis2026 INFO
docker compose exec redis redis-cli -a BrainRedis2026 DBSIZE
docker compose exec redis redis-cli -a BrainRedis2026 KEYS '*'
```

### System Information

```bash
# Docker system info
docker system df  # Disk usage
docker system df -v  # Verbose

# Container resource usage
docker stats

# Image details
docker image ls
docker image inspect agentic-brain:latest

# Network inspection
docker network ls
docker network inspect agentic-brain-dev_default
```

### Troubleshooting Deep Dive

```bash
# Get full error details from service
docker compose logs --timestamps agentic-brain

# Check environment variables inside container
docker compose exec agentic-brain env

# Test connectivity between services
docker compose exec agentic-brain curl redis:6379
docker compose exec agentic-brain curl neo4j:7687
docker compose exec agentic-brain curl http://ollama:11434

# Shell into container for debugging
docker compose exec agentic-brain /bin/bash
docker compose exec neo4j /bin/bash
```

---

## Getting Help

### Quick Troubleshooting Steps

1. **Check status:** `docker compose ps`
2. **Check logs:** `docker compose logs -f`
3. **Verify configuration:** Ensure .env has all required variables
4. **Test connectivity:** Use diagnostic commands above
5. **Try clean restart:** `docker compose down -v && docker compose up -d --build`

### When to Use Full Reset Commands

- SSL/Certificate errors → Use "SSL Bypass Reinstall"
- Multiple services failing → Use "Standard Clean Reinstall"
- Single service broken → Use "Selective Service Reset"
- Stuck in bad state → Full reset with `docker system prune -a --volumes`

### Common Environment Variables Checklist

```bash
# Core services
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=BrainRedis2026
NEO4J_URI=bolt://neo4j:7687
NEO4J_PASSWORD=neo4j

# API/Security
JWT_SECRET=your-secret-key
API_PORT=8000
DEBUG=false

# SSL (if needed)
PYTHONHTTPSVERIFY=0
SSL_VERIFY=false

# Ollama
OLLAMA_HOST=http://ollama:11434
```

### Getting Help

1. Check relevant section in this guide
2. Run diagnostic commands to gather logs
3. Collect: `docker compose ps` + `docker compose logs --tail 200`
4. Open issue: https://github.com/joseph-webber/agentic-brain/issues
5. Include: error message, logs, steps to reproduce, environment (Windows/macOS/Linux)

---

**Last Updated:** 2026-03-26
**Version:** 3.1.0+

