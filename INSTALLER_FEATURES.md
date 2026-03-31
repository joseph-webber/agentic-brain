# Installer Features

## Platform Support Matrix

| Platform | Installer | Status |
|----------|-----------|--------|
| Windows PowerShell | install.ps1, setup.ps1 | ✅ Full Support |
| Windows Bash/WSL | install.sh, setup.sh | ✅ Full Support |
| macOS | install.sh, setup.sh | ✅ Full Support |
| Linux | install.sh, setup.sh | ✅ Full Support |
| Docker | docker-compose.yml | ✅ Full Support |

## Core Features

### Automatic Docker Image Building
- Automatic Docker image building with `--build` flag
- Detects Docker and Docker Compose installation
- Provides installation instructions if missing
- Verifies Docker Compose v2 availability
- Supports multi-platform builds (amd64, arm64)

### Random Password Generation
- Random Neo4j password (32 chars)
- Random Redis password (32 chars)  
- Random JWT secret (64 chars hex)
- Uses cryptographically secure generation (openssl rand or system GUID)
- Stored securely in .env file

### SSL Bypass for Corporate Networks
- Automatically adds `--trusted-host` flags to all pip commands
- Uses `curl -k` for downloads when needed
- Works in corporate proxy environments
- Handles self-signed certificate chains
- Optional SSL verification bypass per environment

### Universal Ollama Installer
- Detects and installs Ollama if not present
- Works across all platforms (macOS, Linux, Windows/WSL)
- Configurable models (default: llama2)
- Optional installation (can skip with flags)
- Auto-detection of existing Ollama instances

### Health Checks for All Services
- Neo4j availability check
- Redis connectivity verification
- Redpanda broker status
- agentic-brain API readiness
- Automatic restart on health check failure

### Service Status Verification
- Real-time service status monitoring
- Dependency wait loops with configurable timeouts
- Detailed health check logs
- Error reporting with diagnostic information
- Safe shutdown and cleanup procedures

## What Gets Installed

### agentic-brain Package
- Python application package
- uvicorn ASGI server
- FastAPI web framework
- All dependencies automatically installed
- Ready for API requests immediately after startup

### Neo4j 2026.02.3 with GDS 2.27.0
- Community Edition database
- Graph Data Science plugin v2.27.0
- APOC library for graph procedures
- Configured with optimized memory settings
- Built-in web console (port 7474)

### Redis
- Redis 7 Alpine image
- Password authentication enabled
- AOF persistence for data durability
- Configured as default cache backend
- Automatic memory management

### Redpanda (Kafka-Compatible)
- Event streaming platform
- Dev mode for full compatibility
- Optimized for Windows environments
- Topic auto-creation enabled
- Built-in Schema Registry support

### Ollama (Optional)
- Large Language Model runtime
- Cross-platform support (macOS, Linux, Windows/WSL)
- Pre-configured with default models
- Optional dependency (can be skipped)
- GPU acceleration support where available

## Service Configuration

| Service | Version | Port | Features |
|---------|---------|------|----------|
| Neo4j | 2026.02.3-community | 7474/7687 | GDS 2.27.0, APOC plugins, web UI |
| Redis | 7-alpine | 6379 | Password auth, AOF persistence, memory limits |
| Redpanda | latest | 9092/29092 | Dev mode, auto topic creation, schema registry |
| agentic-brain | auto | 8000 | FastAPI, uvicorn, health checks |
| Ollama | latest | 11434 | Optional, GPU support, model management |

## Usage - Identical Experience Across All Platforms

### One-Liner Installation (Recommended)

**macOS & Linux (bash):**
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

**Windows PowerShell:**
```powershell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

**Windows Bash/WSL:**
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh)"
```

### Installation Commands Comparison

| Action | macOS/Linux | Windows PowerShell | Windows Bash/WSL |
|--------|-------------|-------------------|------------------|
| **Basic Install** | `./install.sh` | `.\install.ps1` | `bash install.sh` |
| **Skip Docker Check** | `SKIP_DOCKER_CHECK=1 ./install.sh` | `$env:SKIP_DOCKER_CHECK=1; .\install.ps1` | `SKIP_DOCKER_CHECK=1 bash install.sh` |
| **Custom Directory** | `INSTALL_DIR=/opt/brain ./install.sh` | `$env:INSTALL_DIR='C:\brain'; .\install.ps1` | `INSTALL_DIR=/opt/brain bash install.sh` |
| **Verbose Mode** | `DEBUG=1 ./install.sh` | `$env:DEBUG=1; .\install.ps1` | `DEBUG=1 bash install.sh` |
| **Build Images** | `BUILD=1 ./install.sh` | `$env:BUILD=1; .\install.ps1` | `BUILD=1 bash install.sh` |
| **Skip Ollama** | `SKIP_OLLAMA=1 ./install.sh` | `$env:SKIP_OLLAMA=1; .\install.ps1` | `SKIP_OLLAMA=1 bash install.sh` |

### Advanced Setup with setup.sh/setup.ps1

The setup scripts provide additional configuration options:

**macOS/Linux:**
```bash
./setup.sh --memory 4g --cpu-limit 2 --no-ollama
```

**Windows PowerShell:**
```powershell
.\setup.ps1 -Memory 4GB -CpuLimit 2 -NoOllama
```

**Windows Bash/WSL:**
```bash
bash setup.sh --memory 4g --cpu-limit 2 --no-ollama
```

### Environment Variables

All platforms support these environment variables for customization:

```bash
# Core Settings
INSTALL_DIR          # Installation directory (default: current)
BUILD                # Build Docker images (default: 0)
SKIP_DOCKER_CHECK    # Skip Docker availability check (default: 0)
SKIP_OLLAMA          # Skip optional Ollama installation (default: 0)
DEBUG                # Enable verbose output (default: 0)

# Service Configuration
NEO4J_PASSWORD       # Custom Neo4j password (auto-generated if not set)
REDIS_PASSWORD       # Custom Redis password (auto-generated if not set)
JWT_SECRET           # Custom JWT secret (auto-generated if not set)

# Resource Limits
MEMORY_LIMIT         # Docker memory limit (default: 4g)
CPU_LIMIT            # Docker CPU limit (default: 2)
```

## Post-Install Verification

Works identically on all platforms:

```bash
# Check all services running
docker compose ps

# View service logs
docker compose logs -f

# Test API health
curl http://localhost:8000/health

# Access Neo4j browser
# Open in browser: http://localhost:7474

# Verify Redis connection
redis-cli -a $REDIS_PASSWORD ping

# Check Redpanda status
docker compose exec redpanda rpk cluster status

# Verify GDS plugin in Neo4j
# In Neo4j browser: RETURN gds.version()
```

## Installation Output Example

All platforms display similar installation progress:

```
✓ Checking Docker installation
✓ Verifying Docker Compose v2
✓ Generating random passwords
✓ Creating .env configuration
✓ Building Docker images (if --build flag used)
✓ Starting services...
  - Neo4j (7474)
  - Redis (6379)
  - Redpanda (9092)
  - agentic-brain (8000)
✓ Running health checks
✓ Installation complete!

Access your services:
  - API: http://localhost:8000
  - Neo4j: http://localhost:7474 (neo4j/[generated-password])
  - Redis: localhost:6379 (password: [generated-password])
  - Redpanda: localhost:9092
```

## Troubleshooting

### All Platforms
- **Docker not found**: Install Docker Desktop (macOS/Windows) or Docker CE (Linux)
- **Port already in use**: Change port mappings in docker-compose.yml or use `PORTS` env var
- **SSL certificate errors**: Use `SKIP_SSL=1` flag (use with caution in corporate environments)
- **Out of memory**: Increase Docker memory limit with `MEMORY_LIMIT` variable

### Platform-Specific
- **Windows PowerShell**: May require `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned`
- **WSL2**: Use WSL2 backend (not WSL1) for optimal Docker performance
- **macOS**: Ensure Docker Desktop has sufficient CPU and memory allocation
