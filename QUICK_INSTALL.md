# Quick Install

Pick your platform and run one command:

## Mac/Linux
```bash
curl -fsSL https://raw.githubusercontent.com/agentic-brain-project/agentic-brain/main/install.sh | bash
```

## Windows PowerShell
```powershell
iwr -useb https://raw.githubusercontent.com/agentic-brain-project/agentic-brain/main/install.ps1 | iex
```

## Windows Bash/WSL
```bash
curl -fsSL https://raw.githubusercontent.com/agentic-brain-project/agentic-brain/main/install.sh | bash
```

## Docker Manual
```bash
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain
docker compose up -d --build
```

## Verify Installation

```bash
curl http://localhost:8000/health
```

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| API Docs | http://localhost:8000/docs | Interactive API explorer |
| Dashboard | http://localhost:8000/dashboard | Brain dashboard |
| Neo4j | http://localhost:7474 | Graph database browser |
| API Health | http://localhost:8000/health | Service health check |

## Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| Neo4j | neo4j | Brain2026 |
| Redis | (none) | BrainRedis2026 |

## Common Issues

### SSL Errors
```bash
export PIP_TRUSTED_HOST="files.pythonhosted.org pypi.python.org pypi.org"
```

### Rebuild All Services
```bash
docker compose down -v && docker compose up -d --build
```

### Check Service Status
```bash
docker compose ps
```
