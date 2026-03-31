# Complete Installation Guide

## Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Git
- 4GB RAM minimum, 8GB recommended

## Installation Methods

### Method 1: One-Liner Install (Easiest)

**Mac/Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

**Windows PowerShell (Admin):**
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

### Method 2: Manual Docker Install

```bash
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain
cp .env.example .env
docker compose up -d --build
```

### Method 3: Development Install

```bash
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

## Services Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Agentic Brain Stack                       │
├─────────────────────────────────────────────────────────────┤
│  🧠 Agentic Brain API (FastAPI)         Port: 8000          │
│     └── /health, /docs, /dashboard, /ws/chat                │
├─────────────────────────────────────────────────────────────┤
│  🗄️ Neo4j 2026.02.3 + GDS 2.27.0        Ports: 7474, 7687   │
│     └── Graph Database with GraphRAG support                │
├─────────────────────────────────────────────────────────────┤
│  🔴 Redis 7                              Port: 6379          │
│     └── Cache, Sessions, Message Broker                     │
├─────────────────────────────────────────────────────────────┤
│  🐼 Redpanda                             Ports: 9092, 9644   │
│     └── Kafka-compatible Event Bus                          │
└─────────────────────────────────────────────────────────────┘
```

## Default Credentials

| Service | Username | Password | Port |
|---------|----------|----------|------|
| Neo4j | neo4j | Brain2026 | 7474, 7687 |
| Redis | - | BrainRedis2026 | 6379 |
| JWT | - | (auto-generated) | - |

## Environment Variables

Create `.env` file (or use installer which generates it):

```bash
# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Brain2026

# Redis  
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=BrainRedis2026

# Kafka
KAFKA_BOOTSTRAP_SERVERS=redpanda:9092

# Security
JWT_SECRET=your-random-secret-here

# LLM (pick one)
GROQ_API_KEY=your-key
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key
```

## Verifying Installation

```bash
# Check all containers running
docker compose ps

# Test API
curl http://localhost:8000/health

# Test Neo4j
curl http://localhost:7474

# Test Redis
docker exec agentic-brain-redis redis-cli -a BrainRedis2026 ping

# Test Redpanda
curl http://localhost:9644/v1/cluster/health

# Test GDS Plugin (in Neo4j Browser)
RETURN gds.version()  # Should return "2.27.0"
```

## Corporate Network / SSL Issues

The installer handles SSL certificate issues automatically. If you still have problems:

```bash
# Set these environment variables
export PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"
export REQUESTS_CA_BUNDLE=""
```

## Troubleshooting

### Container Won't Start
```bash
docker compose logs [container-name]
docker compose down -v
docker compose up -d --build
```

### Neo4j GDS Not Loading
The GDS 2.27.0 plugin is pre-installed in our custom Dockerfile.neo4j image.

### Windows Redpanda AIO Error
Our docker-compose.yml includes `--mode=dev-container` to fix this.

### Redis Connection Refused
Make sure REDIS_HOST=redis (not localhost) in Docker environment.
