# Quick Install Guide

## One-Liner Install (Recommended)

### Mac/Linux
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

### Windows PowerShell (Run as Administrator)
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

## What Gets Installed

| Service | Port | Purpose |
|---------|------|---------|
| Agentic Brain | 8000 | Main AI API |
| Neo4j + GDS 2.27.0 | 7474, 7687 | Graph Database with GraphRAG |
| Redis | 6379 | Cache & Sessions |
| Redpanda | 9092 | Event Bus (Kafka-compatible) |

## Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| Neo4j | neo4j | Brain2026 |
| Redis | - | BrainRedis2026 |

## After Installation

```bash
# Check all services
docker compose ps

# View logs
docker compose logs -f

# Access services
open http://localhost:8000/docs      # API Docs
open http://localhost:8000/dashboard # Dashboard
open http://localhost:7474           # Neo4j Browser
```

## Troubleshooting

### SSL Certificate Errors (Corporate Networks)
The installer automatically handles SSL certificate issues with --trusted-host flags.

### Windows AIO Errors
Redpanda runs in dev-container mode to avoid AIO issues on Windows.

### Service Not Starting
```bash
docker compose down -v
docker compose up -d --build
docker compose logs [service-name]
```
