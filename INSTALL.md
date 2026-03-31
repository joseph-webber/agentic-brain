# Complete Installation Guide

## Prerequisites

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
- **Git** (for cloning repository)
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 10GB free space
- **Ports**: 8000, 7474, 7687, 6379, 9092, 9644 must be available

## Quick Start: One-Liner Installers

Choose your platform and run the appropriate one-liner:

### 🐧 Linux / macOS (Bash)
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

### 💪 Windows (PowerShell - Run as Administrator)
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; iwr -useb https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

### 🪟 Windows (WSL2/Bash)
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

---

## Platform-Specific Installation

### macOS Installation

#### Prerequisites
```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Docker Desktop
brew install --cask docker

# Install Git
brew install git

# Install Ollama (optional, for local LLM)
brew install --cask ollama
```

#### Manual Installation
```bash
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Copy environment configuration
cp .env.example .env

# Start all services (with build)
docker compose up -d --build

# Wait for services to be ready (30-60 seconds)
sleep 30

# Verify installation
docker compose ps
```

---

### Linux Installation (Ubuntu/Debian)

#### Prerequisites
```bash
# Update package manager
sudo apt-get update

# Install Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add current user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose (usually comes with Docker Desktop, but on Linux)
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Git
sudo apt-get install -y git

# Install Ollama (optional, for local LLM)
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Manual Installation
```bash
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Copy environment configuration
cp .env.example .env

# Start all services (with build)
docker compose up -d --build

# Wait for services to be ready (30-60 seconds)
sleep 30

# Verify installation
docker compose ps
```

---

### Windows PowerShell Installation

#### Prerequisites (Run as Administrator)
```powershell
# Install Chocolatey (if not already installed)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install Docker Desktop
choco install docker-desktop -y

# Install Git
choco install git -y

# Install Ollama (optional, for local LLM)
choco install ollama -y

# Restart PowerShell or system for PATH updates
```

#### Manual Installation
```powershell
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Copy environment configuration
Copy-Item .env.example .env

# Start all services (with build)
docker compose up -d --build

# Wait for services to be ready (30-60 seconds)
Start-Sleep -Seconds 30

# Verify installation
docker compose ps
```

---

### Windows WSL2 + Bash Installation

#### Prerequisites
```bash
# Ensure WSL2 is installed and Docker Desktop is set to use WSL2 backend

# Inside WSL2 terminal:
sudo apt-get update
sudo apt-get install -y git

# Ollama support in WSL2 (optional)
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Manual Installation
```bash
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Copy environment configuration
cp .env.example .env

# Start all services (with build)
docker compose up -d --build

# Wait for services to be ready (30-60 seconds)
sleep 30

# Verify installation
docker compose ps
```

---

## Development Installation

For local development without Docker:

```bash
# Clone repository
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate  # Windows

# Install development dependencies
pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env

# Edit .env for local services (neo4j, redis, etc.)
# Then start services separately or use docker compose
docker compose up -d --build neo4j redis redpanda
```

---

## Services Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    Agentic Brain Stack                            │
├──────────────────────────────────────────────────────────────────┤
│  🧠 Agentic Brain API (FastAPI)              Port: 8000           │
│     └── /health, /docs, /dashboard, /ws/chat                     │
│        Backend: Python 3.11+ | FastAPI 0.109+                    │
├──────────────────────────────────────────────────────────────────┤
│  🗄️ Neo4j 2026.02.3 + GDS 2.27.0             Ports: 7474, 7687   │
│     └── Graph Database with GraphRAG support                     │
│        Browser: http://localhost:7474                            │
├──────────────────────────────────────────────────────────────────┤
│  🔴 Redis 7                                   Port: 6379          │
│     └── Cache, Sessions, Message Broker                          │
│        CLI: docker exec -it redis redis-cli                      │
├──────────────────────────────────────────────────────────────────┤
│  🐼 Redpanda (Kafka-compatible)              Ports: 9092, 9644   │
│     └── Event Bus, Message Streaming                             │
│        Console: http://localhost:8080                            │
├──────────────────────────────────────────────────────────────────┤
│  🦙 Ollama (Optional, Local LLM)             Port: 11434          │
│     └── Local model inference (llama2, mistral, etc.)            │
│        Models: docker exec -it ollama ollama list                │
└──────────────────────────────────────────────────────────────────┘
```

---

## Service Ports & Credentials Reference

| Service | Port(s) | Username | Password | URL |
|---------|---------|----------|----------|-----|
| **API** | 8000 | - | - | http://localhost:8000 |
| **API Docs** | 8000 | - | - | http://localhost:8000/docs |
| **Neo4j Browser** | 7474 | neo4j | Brain2026 | http://localhost:7474 |
| **Neo4j Bolt** | 7687 | neo4j | Brain2026 | bolt://localhost:7687 |
| **Redis** | 6379 | - | BrainRedis2026 | localhost:6379 |
| **Redpanda Broker** | 9092 | - | - | localhost:9092 |
| **Redpanda Console** | 9644 | - | - | http://localhost:9644 |
| **Redpanda UI** | 8080 | - | - | http://localhost:8080 |
| **Ollama API** | 11434 | - | - | http://localhost:11434 |

---

## Environment Variables

Create `.env` file in root directory (or use installer which generates it):

```bash
# ============================================
# Neo4j Configuration
# ============================================
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Brain2026
NEO4J_PROTOCOL=bolt

# ============================================
# Redis Configuration
# ============================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=BrainRedis2026
REDIS_DB=0

# ============================================
# Kafka/Redpanda Configuration
# ============================================
KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
KAFKA_TOPIC_PREFIX=brain

# ============================================
# Security & JWT
# ============================================
JWT_SECRET=your-random-secret-here-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# ============================================
# LLM Provider (choose one or more)
# ============================================
# GROQ_API_KEY=your-groq-api-key
# OPENAI_API_KEY=your-openai-api-key
# ANTHROPIC_API_KEY=your-anthropic-api-key
# OLLAMA_BASE_URL=http://ollama:11434

# ============================================
# Application Settings
# ============================================
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=development
```

---

## Ollama Setup (Local LLM Support)

### macOS
```bash
# Install Ollama
brew install --cask ollama

# Start Ollama service
ollama serve

# In another terminal, pull a model
ollama pull llama2              # 3.8GB
ollama pull mistral             # 4.1GB
ollama pull neural-chat         # 4.7GB

# List available models
ollama list
```

### Linux
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# In another terminal, pull a model
ollama pull llama2
ollama pull mistral
ollama pull neural-chat

# List available models
ollama list
```

### Windows (PowerShell)
```powershell
# Install Ollama
choco install ollama -y

# Start Ollama service
ollama serve

# In another PowerShell window, pull a model
ollama pull llama2
ollama pull mistral
ollama pull neural-chat

# List available models
ollama list
```

### Docker (all platforms)
```bash
# Pull Ollama image
docker pull ollama/ollama

# Start Ollama service
docker run -d \
  --name ollama \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama

# Pull models inside container
docker exec ollama ollama pull llama2
docker exec ollama ollama pull mistral

# Test it
curl http://localhost:11434/api/tags
```

---

## Verification: Test Each Service

### 1. Check All Containers Running
```bash
docker compose ps

# Expected output shows all containers in "Up" status
```

### 2. Test API Health
```bash
curl http://localhost:8000/health

# Expected: {"status":"healthy","timestamp":"2026-01-15T..."}
```

### 3. Test API Docs
```bash
# Open in browser
http://localhost:8000/docs
```

### 4. Test Neo4j
```bash
# Via Browser
open http://localhost:7474  # macOS
xdg-open http://localhost:7474  # Linux
start http://localhost:7474  # Windows

# Login: neo4j / Brain2026

# Via CLI
docker exec neo4j cypher-shell -u neo4j -p Brain2026 "RETURN 1"
```

### 5. Test Neo4j GDS Plugin
```bash
docker exec neo4j cypher-shell -u neo4j -p Brain2026 "RETURN gds.version()"

# Expected: Should return "2.27.0"
```

### 6. Test Redis
```bash
docker exec redis redis-cli -a BrainRedis2026 ping

# Expected: PONG
```

### 7. Test Redpanda
```bash
curl http://localhost:9644/v1/cluster/health

# Expected: JSON showing cluster health
```

### 8. Test Ollama (if installed)
```bash
curl http://localhost:11434/api/tags

# Expected: JSON list of available models
```

### 9. Full Health Check Script
```bash
#!/bin/bash
echo "🔍 Checking Agentic Brain Services..."
echo ""

echo "📦 Docker Containers:"
docker compose ps

echo ""
echo "🧠 API Health:"
curl -s http://localhost:8000/health | jq '.'

echo ""
echo "🗄️ Neo4j Status:"
docker exec neo4j cypher-shell -u neo4j -p Brain2026 "RETURN gds.version()" 2>/dev/null && echo "✅ Neo4j OK" || echo "❌ Neo4j Error"

echo ""
echo "🔴 Redis Status:"
docker exec redis redis-cli -a BrainRedis2026 ping 2>/dev/null && echo "✅ Redis OK" || echo "❌ Redis Error"

echo ""
echo "🐼 Redpanda Status:"
curl -s http://localhost:9644/v1/cluster/health | jq '.broker' && echo "✅ Redpanda OK" || echo "❌ Redpanda Error"

echo ""
echo "✅ All services checked!"
```

---

## Comprehensive Troubleshooting Guide

### Issue: SSL Certificate Errors

**Error Message:**
```
SSL: CERTIFICATE_VERIFY_FAILED
requests.exceptions.SSLError: HTTPSConnectionPool
```

**Solution:**
```bash
# Temporarily disable SSL verification (development only!)
export PYTHONHTTPSVERIFY=0

# Or configure pip to trust hosts
export PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"
export REQUESTS_CA_BUNDLE=""

# Then retry docker compose up
docker compose up -d --build
```

### Issue: Docker Daemon Not Running

**Error Message:**
```
Cannot connect to Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

**Solution:**
```bash
# macOS - Start Docker Desktop
open /Applications/Docker.app

# Linux - Start Docker service
sudo systemctl start docker
sudo systemctl enable docker  # Enable on boot

# Windows - Start Docker Desktop
# Open Docker Desktop application from Start Menu
```

### Issue: Port Already in Use

**Error Message:**
```
Error response from daemon: driver failed programming external connectivity
Bind for 0.0.0.0:8000 failed: port is already allocated
```

**Solution:**
```bash
# Find what's using the port (Linux/macOS)
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or change the port in docker-compose.yml
# Modify: ports: ["8001:8000"]

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Restart services
docker compose down
docker compose up -d --build
```

### Issue: Container Exits Immediately

**Error Message:**
```
docker compose up -d --build
# Container exits with exit code 1
```

**Solution:**
```bash
# Check logs
docker compose logs agentic-brain

# Common causes and fixes:
# 1. Missing dependencies
docker compose down -v
docker compose up -d --build

# 2. Database not ready
docker compose logs neo4j | tail -20
docker compose logs redis | tail -20

# 3. Clear all volumes and restart
docker compose down -v
docker system prune -f
docker compose up -d --build
```

### Issue: Redpanda AIO Error (Windows)

**Error Message:**
```
Redpanda failed to start - Admin server startup failed
```

**Solution:**
This is already fixed in our docker-compose.yml with `--mode=dev-container`. If still occurring:

```yaml
# In docker-compose.yml, ensure redpanda service has:
command: >
  redpanda start
  --mode=dev-container
  --kafka-addr 0.0.0.0:9092
  --advertised-kafka-addr redpanda:9092
```

### Issue: uvicorn Not Found / ModuleNotFoundError

**Error Message:**
```
ModuleNotFoundError: No module named 'uvicorn'
Application startup failed: [ImportError] _ssl.c:123: The handshake operation timed out
```

**Solution:**
```bash
# Rebuild without cache
docker compose build --no-cache agentic-brain

# Then restart
docker compose down
docker compose up -d --build

# Or manually in container
docker exec -it agentic-brain pip install --upgrade -r requirements.txt
```

### Issue: Neo4j GDS Plugin Not Loading

**Error Message:**
```
Unknown procedure: gds.version()
```

**Solution:**
```bash
# GDS is pre-installed in our custom image, but if missing:
docker exec -it neo4j cypher-shell -u neo4j -p Brain2026 \
  "CALL apoc.execute('GET http://security.neo4j.com/gds_downloads/v2.27.0/neo4j-graph-data-science-2.27.0.jar')"

# Or rebuild the image
docker compose build --no-cache neo4j
docker compose up -d neo4j

# Verify
docker exec neo4j cypher-shell -u neo4j -p Brain2026 "RETURN gds.version()"
```

### Issue: Redis Connection Refused

**Error Message:**
```
ConnectionRefusedError: [Errno 111] Connection refused
redis.exceptions.ConnectionError: Error -1 connecting to localhost:6379
```

**Solution:**
```bash
# Inside Docker, use service name not localhost
# .env file should have:
REDIS_HOST=redis  # NOT localhost
REDIS_PORT=6379

# If running outside Docker on host:
REDIS_HOST=localhost
REDIS_PORT=6379

# Test connection
docker exec redis redis-cli -a BrainRedis2026 ping

# If fails, restart Redis
docker compose restart redis
```

### Issue: Out of Memory

**Error Message:**
```
Cannot allocate memory
Process killed due to memory pressure
```

**Solution:**
```bash
# Increase Docker resources (Docker Desktop)
# Settings > Resources > Memory: Set to 4GB+

# Or prune unused resources
docker system prune -a

# Check current usage
docker stats

# Reduce resource load
docker compose down
docker compose up -d neo4j redis
# Start other services one by one
```

### Issue: Network Issues Between Services

**Error Message:**
```
Failed to resolve hostname 'neo4j'
Connection timed out
```

**Solution:**
```bash
# Ensure services are on the same network
docker network ls

# Rebuild with clean slate
docker compose down -v
docker network prune -f
docker compose up -d --build

# Test network connectivity
docker exec agentic-brain ping neo4j
docker exec agentic-brain ping redis
docker exec agentic-brain ping redpanda
```

### Issue: Permissions Denied (Linux)

**Error Message:**
```
permission denied while trying to connect to Docker daemon
```

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Apply group changes
newgrp docker

# Verify
docker ps

# Restart Docker
sudo systemctl restart docker
```

---

## Performance Tuning

### Recommended System Resources

| Component | Minimum | Recommended | Optimal |
|-----------|---------|------------|---------|
| **RAM** | 4GB | 8GB | 16GB+ |
| **CPU Cores** | 2 | 4 | 8+ |
| **Disk** | 10GB | 20GB | 50GB+ |
| **Network** | 1Mbps | 10Mbps | 100Mbps+ |

### Docker Resource Limits (docker-compose.yml)

```yaml
services:
  agentic-brain:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
  neo4j:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

---

## Updating Installation

### Check for Updates
```bash
cd agentic-brain
git status
git fetch origin
```

### Update Services
```bash
# Pull latest code
git pull origin main

# Rebuild all services
docker compose down
docker compose up -d --build

# Or just update specific service
docker compose build --no-cache agentic-brain
docker compose up -d --build agentic-brain
```

### Backup Before Updating
```bash
# Backup Neo4j database
docker exec neo4j bin/neo4j-admin database backup --to-path=/backups neo4j

# Backup Redis data
docker exec redis redis-cli -a BrainRedis2026 BGSAVE

# Backup docker volumes
docker run --rm -v neo4j_data:/data -v backup:/backup \
  alpine tar czf /backup/neo4j_backup.tar.gz -C /data .
```

---

## Next Steps

1. **Verify Installation**: Run verification commands above
2. **Configure LLM**: Add your API keys to `.env` file
3. **Explore API**: Visit http://localhost:8000/docs
4. **Check Neo4j**: Visit http://localhost:7474
5. **Read Documentation**: Check README.md and docs/ folder

## Getting Help

- 📚 **Documentation**: https://github.com/joseph-webber/agentic-brain/tree/main/docs
- 🐛 **Report Issues**: https://github.com/joseph-webber/agentic-brain/issues
- 💬 **Discussions**: https://github.com/joseph-webber/agentic-brain/discussions
- 📧 **Email**: support@agentic-brain.dev
