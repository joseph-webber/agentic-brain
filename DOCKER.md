# Docker Guide

## Quick Start
```bash
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain
docker compose up -d --build
```

## Services
- agentic-brain: Main API server (port 8000)
- neo4j: Graph database (ports 7474, 7687) 
- redis: Cache (port 6379)
- redpanda: Event streaming (ports 9092, 9644)
- ollama: Local LLM (port 11434, optional)

## Commands
```bash
docker compose up -d --build      # Start with build
docker compose ps                  # Check status
docker compose logs -f             # View logs
docker compose down                # Stop
docker compose down -v             # Stop + remove data
docker compose --profile ollama up -d --build  # Include Ollama
```

## Rebuild from Scratch
```bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

## Environment Variables
List key env vars from docker-compose.yml

## Troubleshooting
Common Docker issues and fixes
