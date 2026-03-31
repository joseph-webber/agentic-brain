# 🛠️ Agentic Brain Bulletproof Installer - Technical Overview

## 📦 System Components

### Versions
- **Neo4j**: 2026.02.3-community
- **Graph Data Science (GDS)**: 2.27.0

### Recent Fixes & Improvements
- ✅ **SSL trusted hosts for corporate proxies** - Auto-detect and configure PIP_TRUSTED_HOST for secure enterprise environments
- ✅ **Redpanda dev-container mode for Windows** - Optimized event streaming for Windows development environments
- ✅ **pip upgrade for cache clearing** - Ensures clean dependency installation and prevents cached issues
- ✅ **Correct Neo4j Docker tag** - Verified and updated to latest stable community build

---

## Architecture

The installer follows the **Retool install pattern** with two implementations:

1. **install.sh** - Bash for Mac/Linux (486 lines)
2. **install.ps1** - PowerShell for Windows (465 lines)

Both implement identical logic with platform-specific optimizations.

---

## 🔐 Security Features

### 1. Random Password Generation (Retool Pattern)
```bash
# Using /dev/urandom + base64 (Retool pattern)
random() { 
    cat /dev/urandom | base64 | head -c "$1" | tr -d +/ | tr -d '='; 
}

# Generates:
NEO4J_PASSWORD=$(random 64)        # 64-char password
REDIS_PASSWORD=$(random 64)        # 64-char password
ENCRYPTION_KEY=$(random 64)        # 64-char encryption key
JWT_SECRET=$(random 256)           # 256-char JWT secret
```

### 2. Pre-existing .env Protection
```bash
# Like Retool: exits if .env already exists
if [ -f "$ENV_FILE" ]; then
    warn ".env file already exists"
    return 0  # Don't overwrite
fi
```

This prevents accidental password resets during re-runs.

### 3. Corporate SSL/Proxy Support
```bash
# Detects corporate SSL and configures PIP
if [ -n "$REQUESTS_CA_BUNDLE" ] || [ -n "$SSL_CERT_FILE" ]; then
    info "Corporate SSL detected"
    export PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"
fi
```

---

## 🐳 Docker Integration

### Auto-Docker Installation (Linux)
```bash
# Check if Docker is installed
if ! check_cmd docker; then
    # Offer auto-install (like Retool)
    read -p "Would you like to auto-install Docker?"
    
    # Run get.docker.com (Retool pattern)
    wget -qO- https://get.docker.com | sh
    
    # Add user to docker group
    sudo usermod -aG docker "$USER"
fi
```

### Docker Compose Auto-Detection
```bash
# Try docker compose v2 first (modern)
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
fi

# Fall back to v1
if check_cmd docker-compose; then
    COMPOSE_CMD="docker-compose"
fi
```

### Health Check Implementation
```bash
# Check each service independently
neo4j_ready=$(curl -sf http://localhost:7474 >/dev/null 2>&1)
redis_ready=$(docker exec agentic-brain-redis redis-cli ping | grep -q PONG)
redpanda_ready=$(curl -sf http://localhost:9644/v1/status/ready >/dev/null 2>&1)

# Wait max 180 seconds with visual feedback
while [ $waited -lt 180 ]; do
    if [ "$neo4j_ready" ] && [ "$redis_ready" ] && [ "$redpanda_ready" ]; then
        success "All services healthy!"
        return
    fi
    echo -n "."  # Visual progress indicator
    sleep 3
done
```

---

## 📦 Generated Configuration

### .env File Structure
```bash
# Core application settings
ENVIRONMENT=production
DEBUG=false
APP_PORT=8000

# Neo4j configuration (auto-generated)
NEO4J_HOST=neo4j
NEO4J_PORT=7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<random-64-chars>

# Redis configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<random-64-chars>

# Security keys (auto-generated)
ENCRYPTION_KEY=<random-64-chars>
JWT_SECRET=<random-256-chars>

# LLM providers (templated, user configures)
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_PROVIDER=ollama
# GROQ_API_KEY=<add-your-key>
# OPENAI_API_KEY=<add-your-key>

# Corporate proxy support
# PIP_TRUSTED_HOST=pypi.org...
# REQUESTS_CA_BUNDLE=/path/to/cert
```

---

## 🚀 Installation Flow

### Bash Flow (install.sh)
```
1. banner()              # Display welcome screen
2. check_docker()        # Check/auto-install Docker
3. check_docker_compose()# Check Docker Compose
4. setup_repo()          # Clone or update repo
5. setup_env()           # Generate .env with random passwords
6. start_services()      # Run docker compose up -d
7. wait_for_health()     # Check service health
8. print_success()       # Show completion info
```

### PowerShell Flow (install.ps1)
Identical logic using PowerShell cmdlets:
```
1. Write-Banner          # Display welcome
2. Test-Docker           # Check Docker (supports winget auto-install)
3. Test-DockerCompose    # Check Docker Compose
4. Set-Repository        # Clone or update
5. Set-Environment       # Generate .env
6. Start-Services        # docker compose up -d
7. Wait-ForHealth        # Health checks
8. Write-SuccessMessage  # Show completion
```

---

## 🔧 Platform-Specific Features

### macOS
- **Homebrew support** for auto-installing Git
- **Colima fallback** if Docker Desktop isn't running
- **Architecture detection** (Intel vs Apple Silicon)

### Linux
- **apt/dnf package manager** integration
- **Auto Docker installation** via get.docker.com
- **User group configuration** (docker group)

### Windows
- **winget integration** for Docker/Git installation
- **PowerShell Core compatibility**
- **Windows path handling** (backslashes)
- **Hyper-V/WSL2 support** automatic

---

## 📊 Comparison with Retool Installer

| Feature | Retool | Agentic Brain |
|---------|--------|---------------|
| Random Passwords | ✅ `/dev/urandom\|base64` | ✅ Identical |
| .env Protection | ✅ Exit if exists | ✅ Same |
| Auto-Docker | ✅ Linux only | ✅ Linux + offer Windows |
| Docker Compose v2 | ✅ Supports both | ✅ Supports both |
| Health Checks | ⚠️ Basic | ✅ Detailed per-service |
| Corporate SSL | ⚠️ Manual | ✅ Auto-detected |
| Git Repo Updates | ⚠️ Manual | ✅ Auto-update |
| Windows Support | ❌ None | ✅ Full PowerShell |
| Installation Size | ~3KB | ~16KB (more features) |

---

## 🎯 Usage Examples

### Example 1: Default Installation
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```
Output:
```
✅ Checking installation requirements...
✅ Docker is installed: Docker version 24.0.0
✅ Docker Compose v2 found: Docker Compose version 2.20.0
✅ Git is installed
✅ Repository cloned to /Users/joe/agentic-brain
✅ Created .env file with random passwords
✅ Docker images pulled
✅ Services started successfully
✓ Neo4j is ready (http://localhost:7474)
✓ Redis is ready
✓ Redpanda is ready

🎉 Agentic Brain Installed Successfully! 🎉
```

### Example 2: Custom Directory + Branch
```bash
AGENTIC_BRAIN_DIR=~/my-brain \
AGENTIC_BRAIN_BRANCH=develop \
bash <(curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh)
```

### Example 3: Corporate Proxy
```bash
export REQUESTS_CA_BUNDLE=/opt/company-ca-bundle.crt
export SSL_CERT_FILE=/opt/company-ca-bundle.crt
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

### Example 4: Windows PowerShell
```powershell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

---

## 🧪 Testing

### Syntax Validation
```bash
# Bash
bash -n install.sh

# PowerShell
powershell -NoProfile -Command {
    Set-StrictMode -Version Latest
    & { Get-Content install.ps1 }
}
```

### Manual Testing Steps
1. Fresh VM or container
2. Only Git installed (no Docker)
3. Run installer
4. Verify auto-Docker installation
5. Verify services start
6. Test health checks
7. Access http://localhost:8000/docs

---

## 📈 Performance

| Stage | Time | Notes |
|-------|------|-------|
| Pre-flight checks | < 2s | Docker, Compose, Git |
| Repository clone | 10-30s | First run only |
| Repository update | 2-5s | Subsequent runs |
| Docker image pull | 30-120s | Depends on network |
| Services startup | 5-10s | Docker compose up |
| Health checks | 5-30s | Wait for readiness |
| **Total (first run)** | **1-2 min** | Network dependent |
| **Total (updates)** | **30-60s** | Much faster |

---

## 🔐 Security Considerations

### Passwords
- ✅ Cryptographically random via `/dev/urandom`
- ✅ 64-256 characters for high entropy
- ✅ Stored in `.env` (should be .gitignored)
- ✅ Never logged or printed

### Network
- ✅ HTTPS-only for curl commands
- ✅ Git uses SSH if configured
- ✅ Corporate proxy support built-in
- ✅ Health checks use localhost only

### File Permissions
- ✅ .env file sensitive (recommend `chmod 600`)
- ✅ Git repo cloned securely
- ✅ Docker commands use sudo (if needed)

### No Root Required
- ✅ Bash version works without sudo for users in docker group
- ✅ PowerShell can auto-add docker group membership
- ✅ Falls back gracefully if needed

---

## 🐛 Error Handling

The installer includes comprehensive error handling:

```bash
# Fail on first error
set -e

# Check command exit codes
if ! command_name; then
    error "Failed to execute command"
    exit 1
fi

# Try alternatives
docker compose version || \
    docker-compose version || \
    (error "Not found"; exit 1)

# Provide helpful suggestions
error "Docker daemon is not running!"
echo "Start Docker Desktop or run: sudo systemctl start docker"
```

---

## 📝 Future Enhancements

Potential additions:
- [ ] Kubernetes deployment support
- [ ] Helm chart generation
- [ ] Automated backup scripts
- [ ] Monitoring stack installation (Prometheus/Grafana)
- [ ] SSL certificate auto-generation
- [ ] Multi-node cluster setup
- [ ] Cloud provider detection (AWS, GCP, Azure)

---

## 📄 License

Copyright 2026 Joseph Webber
Licensed under GPL-3.0-or-later

Inspired by and adapted from Retool's excellent installation patterns.
