# Installer Features

## Platform Support

| Platform | Installer | Status |
|----------|-----------|--------|
| macOS (Intel/M1/M2/M3) | install.sh | ✅ Fully tested |
| Linux (Ubuntu/Debian/Fedora) | install.sh | ✅ Fully tested |
| Windows 10/11 | install.ps1 | ✅ Fully tested |
| WSL2 | install.sh | ✅ Fully tested |

## Features

### Automatic Docker Detection
- Checks if Docker is installed and running
- Provides installation instructions if missing
- Verifies Docker Compose v2 availability

### Secure Password Generation
- Random Neo4j password (32 chars)
- Random Redis password (32 chars)  
- Random JWT secret (64 chars hex)
- Uses openssl rand -hex or system GUID

### SSL Certificate Handling
- Automatically adds --trusted-host flags to all pip commands
- Uses curl -k for downloads when needed
- Works in corporate proxy environments
- Handles self-signed certificate chains

### Environment Setup
- Creates .env file with all required variables
- Sets correct Docker hostnames (redis, neo4j, redpanda)
- Configures all service connections
- Preserves existing .env if present

### Service Configuration

| Service | Version | Features |
|---------|---------|----------|
| Neo4j | 2026.02.3-community | GDS 2.27.0, APOC plugins |
| Redis | 7-alpine | Password auth, AOF persistence |
| Redpanda | latest | Dev mode for Windows compatibility |

### Health Checks
- All services have Docker health checks
- agentic-brain waits for dependencies
- Automatic restart on failure

## Usage

### One-Liner (Recommended)

**Mac/Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

**Windows PowerShell:**
```powershell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

### With Options

```bash
# Skip Docker check
SKIP_DOCKER_CHECK=1 ./install.sh

# Custom install directory
INSTALL_DIR=/opt/agentic-brain ./install.sh

# Verbose mode
DEBUG=1 ./install.sh
```

## What Gets Created

```
agentic-brain/
├── .env                 # Generated with random passwords
├── docker-compose.yml   # Full stack configuration
├── Dockerfile          # Main app image
├── Dockerfile.neo4j    # Neo4j + GDS image
└── src/                # Application source
```

## Post-Install Verification

```bash
# All services running?
docker compose ps

# API responding?
curl http://localhost:8000/health

# Neo4j browser
open http://localhost:7474

# GDS plugin loaded?
# In Neo4j browser: RETURN gds.version()
```
