# 🧠 Agentic Brain - Complete Installation Guide

**Enterprise-grade installation for Mac, Linux, and Windows with production-ready setup.**

## Quick Start

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

---

## 🏗️ System Architecture

The installation deploys a complete AI agent infrastructure:

| Component | Version | Role |
|-----------|---------|------|
| **Neo4j** | 2026.02.3-community | Knowledge graph & memory system |
| **Neo4j GDS** | 2.27.0 | Graph algorithms & ML pipeline |
| **Redpanda** | Latest AIO | Event streaming & message broker |
| **Redis** | Latest | Cache & session store |
| **Docker** | 20.10+ | Container orchestration |
| **Docker Compose** | v2 | Multi-container coordination |

---

## ✨ Features

The bulletproof installer includes:

- ✅ **Auto-detects and installs Docker** if missing (Linux only)
- ✅ **Docker Compose v2 support** with v1 fallback
- ✅ **Neo4j 2026.02.3-community** with GDS 2.27.0 pre-configured
- ✅ **Generates random, secure passwords** (Retool pattern)
- ✅ **Comprehensive .env configuration** with all required variables
- ✅ **Corporate SSL/proxy support** with certificate handling
- ✅ **Health checks** for all services (Neo4j, GDS, Redis, Redpanda)
- ✅ **Detailed status output** with emoji feedback
- ✅ **Works offline** after initial clone
- ✅ **Git-aware** - updates existing installations
- ✅ **Platform-specific optimizations** (macOS, Linux, Windows)

---

## 📋 What Gets Installed

After running the installer, you'll have:

```
agentic-brain/
├── .env                          # Generated with random passwords + versions
├── docker-compose.yml            # Neo4j, GDS, Redis, Redpanda
├── Dockerfile.neo4j              # Neo4j with GDS plugin
├── src/                          # Application code
├── docs/                         # Documentation
├── scripts/                      # Utility scripts
└── ...                           # All other repo files
```

**Services started:**
- **Neo4j** (2026.02.3-community) → http://localhost:7474
  - Browser: http://localhost:7474/browser
  - Bolt protocol: bolt://localhost:7687
- **Neo4j GDS** (2.27.0) → Integrated with Neo4j
  - Graph algorithms & ML framework
  - In-memory analytics
- **Redis** (Latest) → localhost:6379
  - Cache layer
  - Session storage
- **Redpanda** (Latest AIO) → http://localhost:9644
  - Event streaming
  - Message broker
  - Schema registry
- **API Server** → http://localhost:8000
  - FastAPI with auto-docs
  - Health checks
  - Metrics

---

## 🔐 Security

The installer follows the **Retool install pattern**:

1. **Random Passwords**: Uses `/dev/urandom | base64` to generate:
   - Neo4j password (64 chars)
   - Redis password (64 chars)
   - JWT secret (256 chars)
   - Encryption key (64 chars)

2. **Pre-existing .env Protection**: Like Retool, exits if `.env` already exists to protect existing configurations

3. **Corporate SSL Support**: Automatically configures SSL certificates if behind a proxy:
   ```bash
   export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
   export SSL_CERT_FILE=/path/to/ca-bundle.crt
   export PIP_CERT=/path/to/ca-bundle.crt
   ```

4. **Secure Defaults**: All services bound to localhost; adjust docker-compose.yml for remote access

---

---

## 🛠️ Detailed Installation Requirements

### macOS

**Minimum:**
- macOS 11+
- 8GB RAM (16GB recommended for GDS)
- 20GB free disk space
- Internet connection (for initial download)

**Required Software:**
```bash
# Check Git
git --version

# Check Docker
docker --version
docker compose version

# Install via Homebrew if missing:
brew install git
brew install docker
```

**Intel vs Apple Silicon:**
- Apple Silicon (M1/M2/M3): Native support, all images compatible
- Intel (x86): Standard Docker support

**Installation:**
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

### Linux (Ubuntu/Debian)

**Minimum:**
- Ubuntu 20.04+ or Debian 11+
- 4GB RAM (8GB+ recommended for GDS)
- 20GB free disk space
- Sudo privileges (for Docker installation)

**Required Software:**
```bash
# Update package manager
sudo apt-get update

# Install Git
sudo apt-get install -y git

# Install Docker (auto-detected by installer)
# OR manually:
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (skip sudo for docker commands)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker run hello-world
```

**Installation:**
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

### Linux (RHEL/CentOS/Fedora)

**Minimum:**
- RHEL 8+ / CentOS 8+ / Fedora 33+
- 4GB RAM (8GB+ recommended for GDS)
- 20GB free disk space
- Sudo privileges

**Required Software:**
```bash
# Install Git
sudo dnf install -y git

# Install Docker
sudo dnf install -y docker
sudo systemctl enable docker
sudo systemctl start docker

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker run hello-world
```

**Installation:**
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

### Windows 10/11

**Minimum:**
- Windows 10 21H2+ or Windows 11
- 8GB RAM (16GB recommended for GDS)
- 25GB free disk space
- Virtualization enabled in BIOS
- Administrator privileges

**Required Software:**
```powershell
# Install via winget (Windows 10/11 v2004+)
winget install Git.Git
winget install Docker.DockerDesktop

# OR download manually:
# - Git: https://git-scm.com/download/win
# - Docker Desktop: https://www.docker.com/products/docker-desktop

# Verify
git --version
docker --version
docker compose version
```

**WSL2 Backend (Recommended):**
- Docker Desktop → Settings → General → Use the WSL 2 based engine
- Install WSL2: `wsl --install`

**Installation (PowerShell as Administrator):**
```powershell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

---

## 🐳 Docker Requirements

### Docker Versions

| Component | Minimum Version | Recommended |
|-----------|-----------------|-------------|
| Docker Engine | 20.10.0 | 24.0+ |
| Docker Compose | 2.0.0 | 2.20+ |
| Docker API | v1.41 | Latest |

### Check Your Versions

```bash
# Docker Engine version
docker --version

# Docker Compose version
docker compose version

# API version (should be ≥ 1.41)
docker version --format '{{.Server.APIVersion}}'
```

### Upgrade Docker

**macOS (via Homebrew):**
```bash
brew upgrade docker
```

**Linux (Ubuntu):**
```bash
# Follow official Docker install for latest
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**Windows:**
- Open Docker Desktop → Settings → Check for Updates

### Docker Compose Behavior

- **Docker Compose v2**: Installed with Docker Desktop (recommended)
- **Docker Compose v1**: Legacy `docker-compose` command
  - Installer detects and uses v2 if available
  - Falls back to v1 if v2 not found
  - Both work; v2 has better error reporting

### Disk Space Requirements

After installation with all services running:

```
Neo4j database:        2-5GB (grows with data)
GDS memory cache:      2-4GB (in-memory graphs)
Redpanda (AIO):        1-2GB (message buffer)
Redis cache:           500MB-1GB
Docker overlay:        500MB
Total estimated:       6-15GB
```

**Check available space:**
```bash
# Mac/Linux
df -h

# Windows
Get-Volume
```

### Network Configuration

**Default Ports (must be available):**
```
7474  - Neo4j Browser (HTTP)
7687  - Neo4j Bolt (protocol)
9644  - Redpanda Console (HTTP)
6379  - Redis
8000  - API Server
```

**Check port availability:**
```bash
# Mac/Linux
lsof -i :7474
lsof -i :6379

# Windows
Get-NetTCPConnection -LocalPort 7474
Get-NetTCPConnection -LocalPort 6379
```

**Change ports (if needed):**
Edit `docker-compose.yml` and change port mappings before first run.

---

---

## 📱 Installation Methods

### Method 1: One-Line Install (Recommended)

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

**Windows PowerShell (Run as Administrator):**
```powershell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

### Method 2: Clone & Install

**macOS / Linux:**
```bash
# Clone repository
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Run installer
./install.sh
```

**Windows PowerShell (Run as Administrator):**
```powershell
# Clone repository
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Run installer
.\install.ps1
```

### Method 3: Custom Installation Directory

**macOS / Linux:**
```bash
# Set custom directory before running installer
AGENTIC_BRAIN_DIR=~/my-projects/brain \
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

**Windows PowerShell:**
```powershell
$env:AGENTIC_BRAIN_DIR = "C:\projects\brain"
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

### Method 4: Specific Branch

**macOS / Linux:**
```bash
# Install from develop branch
AGENTIC_BRAIN_BRANCH=develop \
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

**Windows PowerShell:**
```powershell
$env:AGENTIC_BRAIN_BRANCH = "develop"
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

---

## ✅ Verify Installation

### Check All Services Running

```bash
# Navigate to installation directory
cd ~/agentic-brain  # or your custom path

# View running containers
docker compose ps

# Expected output:
# NAME          STATUS      PORTS
# neo4j         Up          0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp
# redis         Up          0.0.0.0:6379->6379/tcp
# redpanda      Up          0.0.0.0:9644->9644/tcp
# api           Up          0.0.0.0:8000->8000/tcp
```

### Test Neo4j Connection

```bash
# Test Neo4j HTTP endpoint
curl -u neo4j:$(grep NEO4J_PASSWORD .env | cut -d= -f2) \
  http://localhost:7474/db/neo4j/cypher

# Expected: Connection successful or auth prompt

# Open Neo4j Browser
open http://localhost:7474  # macOS
xdg-open http://localhost:7474  # Linux
start http://localhost:7474  # Windows PowerShell
```

### Test Neo4j GDS

```bash
# Check GDS version in Neo4j Browser
# Paste into query editor:
RETURN gds.version()

# Expected output: Should show 2.27.0
```

### Test Redis Connection

```bash
# Check Redis
redis-cli ping

# Expected output: PONG
```

### Test Redpanda

```bash
# View Redpanda Console
open http://localhost:9644  # macOS
xdg-open http://localhost:9644  # Linux
start http://localhost:9644  # Windows PowerShell

# Or test via CLI
docker compose exec redpanda rpk topic list
```

### Test API Server

```bash
# Health check
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs  # macOS
xdg-open http://localhost:8000/docs  # Linux
start http://localhost:8000/docs  # Windows PowerShell
```

---

## 📝 Post-Installation Configuration

### 1. Review Environment Variables

```bash
# View all configured variables
cat .env

# Key variables to check:
# - NEO4J_PASSWORD (randomly generated, 64 chars)
# - REDIS_PASSWORD (randomly generated, 64 chars)
# - JWT_SECRET (256 chars)
# - ENCRYPTION_KEY (64 chars)
# - All service versions
```

### 2. Add LLM API Keys (Optional)

If using cloud-based LLMs:

```bash
# Edit .env
nano .env  # Mac/Linux
# OR
notepad .env  # Windows

# Uncomment and set ONE provider:
# GROQ_API_KEY=gsk_...
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# TOGETHER_API_KEY=...

# Restart services
docker compose restart api
```

### 3. Set Up Local LLM (Optional)

For offline/free LLM inference:

```bash
# Install Ollama
# macOS: https://ollama.ai
# Linux: curl https://ollama.ai/install.sh | sh
# Windows: https://ollama.ai/download/windows

# Pull a model
ollama pull llama3.2

# Verify
curl http://localhost:11434/api/tags
```

### 4. Configure Logging

```bash
# View service logs
docker compose logs -f neo4j      # Neo4j logs
docker compose logs -f api        # API logs
docker compose logs -f redpanda   # Redpanda logs

# Save logs to file
docker compose logs > service-logs.txt

# Filter logs by time
docker compose logs --since 10m   # Last 10 minutes
```

### 5. Network Access (Optional)

To access services remotely, edit `docker-compose.yml`:

```yaml
# BEFORE (localhost only):
ports:
  - "127.0.0.1:7474:7474"

# AFTER (all interfaces):
ports:
  - "7474:7474"

# Then restart:
docker compose down
docker compose up -d
```

⚠️ **Security Warning**: Only do this on trusted networks. Use firewall rules to restrict access.

---

## 🔧 Comprehensive Troubleshooting Guide

### 🔒 SSL Certificate Errors (Corporate Proxy)

**Symptoms:**
```
SSL: CERTIFICATE_VERIFY_FAILED
SSL_ERROR_RX_RECORD_TOO_LONG
CERTIFICATE_VERIFY_FAILED (urlopen error)
Trust the self-signed certificate
```

**Root Cause:**
Corporate proxies intercept HTTPS traffic and replace certificates with self-signed ones.

**Solution 1: Set SSL Environment Variables (Recommended)**

```bash
# macOS / Linux
# 1. Obtain your corporate CA certificate
# Ask IT for the certificate in .pem or .crt format
# Example: /etc/ssl/certs/corporate-ca.pem

# 2. Set environment variables BEFORE running installer
export REQUESTS_CA_BUNDLE=/path/to/corporate-ca.pem
export SSL_CERT_FILE=/path/to/corporate-ca.pem
export PIP_CERT=/path/to/corporate-ca.pem

# 3. Run installer
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash

# 4. Verify - these should be in .env
grep CA_BUNDLE .env
grep SSL_CERT .env
```

**Windows PowerShell (Run as Administrator):**
```powershell
# 1. Get certificate path (ask your IT department)
# Example: C:\certs\corporate-ca.pem

# 2. Set environment variables
$env:REQUESTS_CA_BUNDLE = "C:\certs\corporate-ca.pem"
$env:SSL_CERT_FILE = "C:\certs\corporate-ca.pem"
$env:PIP_CERT = "C:\certs\corporate-ca.pem"

# 3. Run installer
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex

# 4. Verify - these should be in .env
Select-String "CA_BUNDLE|SSL_CERT" .env
```

**Solution 2: Configure Docker Daemon**

If Docker itself is failing:

```bash
# macOS: Edit Docker Desktop settings
# Preferences → Docker Engine → Add to daemon.json:
{
  "insecure-registries": ["your-corp-registry.com"],
  "cafile": "/path/to/corporate-ca.pem"
}

# Linux: Edit /etc/docker/daemon.json
sudo nano /etc/docker/daemon.json
# Add above configuration
sudo systemctl restart docker

# Windows: Docker Desktop → Settings → Docker Engine
# Add above configuration
```

**Solution 3: Verify Certificate Installation**

```bash
# macOS: Add to Keychain
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain /path/to/corporate-ca.pem

# Linux: Add to system CA store
sudo cp /path/to/corporate-ca.pem /usr/local/share/ca-certificates/
sudo update-ca-certificates

# Windows: Add to system certificate store
Import-Certificate -FilePath "C:\certs\corporate-ca.pem" \
  -CertStoreLocation "Cert:\LocalMachine\Root"
```

**Solution 4: Bypass (Not Recommended - Last Resort)**

```bash
# Mac/Linux
export REQUESTS_CA_BUNDLE=""
export SSL_VERIFY=false

# Windows
$env:REQUESTS_CA_BUNDLE = ""
$env:SSL_VERIFY = "false"

# ⚠️ WARNING: This disables all certificate verification
# Only use for testing, NEVER in production
```

---

### 🪟 Redpanda AIO Errors on Windows

**Symptoms:**
```
docker: Error response from daemon: Mounts denied
Volume mount denied
Permission denied /var/lib/redpanda
redpanda: cannot open shared object file
```

**Root Cause 1: WSL2 Path Issues**

WSL2 paths need proper formatting for Docker volumes.

**Solution:**
```bash
# Verify WSL2 is enabled
wsl --list -v

# If not running Ubuntu-20.04 or higher, update:
wsl --update

# Test WSL2 integration with Docker
docker run -it ubuntu:latest bash

# Edit docker-compose.yml - change volume paths
# FROM:
# - /var/lib/redpanda:/var/lib/redpanda

# TO (Windows path):
# - C:\Docker\redpanda:/var/lib/redpanda

# Restart services
docker compose down
docker compose up -d
```

**Root Cause 2: Redpanda AIO Memory Requirements**

Redpanda requires 2GB+ RAM; default Docker Desktop limit may be too low.

**Solution:**
```powershell
# Increase Docker Desktop memory allocation
# Settings → Resources → Memory
# Set to 8GB or higher (recommend 16GB total)

# Restart Docker Desktop after changing

# Verify
docker stats
```

**Root Cause 3: Incompatible Redpanda Version**

**Solution:**
```bash
# Check Redpanda version in docker-compose.yml
grep -A2 "image.*redpanda" docker-compose.yml

# Use stable version (AIO available for 24.1+)
image: redpanda:v24.1.10-alpine

# Recreate Redpanda container
docker compose down redpanda
docker compose up -d redpanda

# Verify startup
docker compose logs redpanda
```

**Root Cause 4: Volume Permission Issues**

**Solution (Windows):**
```powershell
# Verify Docker has permissions to data directories
# Settings → Resources → File Sharing
# Make sure installation directory is shared

# Alternative: Use named volumes (more reliable on Windows)
# Edit docker-compose.yml:

volumes:
  redpanda_data:
    driver: local

services:
  redpanda:
    volumes:
      - redpanda_data:/var/lib/redpanda

# Restart
docker compose down -v
docker compose up -d
```

---

### 🔄 Neo4j GDS Compatibility Issues

**Symptoms:**
```
GDS not found
Unknown function: gds.*
GDS plugin failed to load
Procedure not registered
```

**Root Cause 1: GDS Version Mismatch**

GDS 2.27.0 requires specific Neo4j versions.

**Solution:**
```bash
# Verify versions match:
# Neo4j 2026.02.3-community requires GDS 2.27.0

# Check current versions in docker-compose.yml
grep -E "image.*neo4j:|GDS" docker-compose.yml

# Expected:
# image: neo4j:2026.02.3-community
# NEO4J_PLUGINS=["graph-data-science"]
# NEO4J_GDS_VERSION=2.27.0

# If versions mismatch, update docker-compose.yml and recreate:
docker compose down neo4j
docker image rm neo4j:old-version
docker compose up -d neo4j

# Wait 30-60 seconds for Neo4j to start
docker compose logs -f neo4j
```

**Root Cause 2: GDS Plugin Not Installing**

**Solution:**
```bash
# Check Neo4j logs for GDS startup
docker compose logs neo4j | grep -i "gds\|plugin"

# Expected: "GDS 2.27.0 loaded successfully" or similar

# If GDS didn't load, rebuild container with fresh volume:
docker compose down neo4j
docker volume rm agentic-brain_neo4j_data
docker compose up -d neo4j

# Monitor startup (5-10 minutes)
docker compose logs -f neo4j

# Verify GDS in Neo4j Browser (http://localhost:7474)
# Query: RETURN gds.version()
```

**Root Cause 3: Insufficient Memory for GDS**

GDS loads graphs into memory; low memory = failures.

**Solution:**
```bash
# Increase Docker memory allocation
# macOS/Windows: Docker Desktop → Settings → Resources
# Increase to 8GB+ (recommend 16GB for production)

# Linux: Docker already has access to system RAM
# But verify available memory:
free -h

# Check Neo4j memory settings in docker-compose.yml
# Should have (or add):
environment:
  NEO4J_server_memory_heap_initial_size: 2g
  NEO4J_server_memory_heap_max_size: 4g
  NEO4J_server_memory_pagecache_size: 2g

# Update and restart
docker compose down neo4j
docker compose up -d neo4j
```

**Root Cause 4: License Restrictions**

GDS has evaluation & licensing tiers.

**Solution:**
```bash
# Community edition has evaluation features
# For unlimited use, verify your GDS license tier

# Check license in Neo4j Browser:
# CALL gds.license.state()

# For production, contact Neo4j sales if needed
```

**Verify GDS Installation:**
```bash
# Test in Neo4j Browser (http://localhost:7474)
# Enter credentials (neo4j / password from .env)

# Run these queries:
RETURN gds.version()
CALL gds.list()
CALL gds.graph.list()

# Expected: Version 2.27.0, algorithm list, etc.
```

---

### 🐍 Python/pip Cache Issues

**Symptoms:**
```
pip._vendor.urllib3.exceptions.InvalidURL
Could not find a version that satisfies the requirement
ERROR: pip's dependency resolver does not work
```

**Root Cause 1: Corrupted pip Cache**

**Solution:**
```bash
# macOS/Linux
# Clear pip cache
pip cache purge

# Or manually remove
rm -rf ~/.cache/pip

# Windows PowerShell
# Remove cache
pip cache purge
# Or manually
Remove-Item -Recurse -Force $env:APPDATA\pip\cache

# Reinstall requirements
pip install --no-cache-dir -r requirements.txt
```

**Root Cause 2: pip Version Mismatch**

**Solution:**
```bash
# Upgrade pip
pip install --upgrade pip

# macOS/Linux
python -m pip install --upgrade pip

# Windows PowerShell
python -m pip install --upgrade pip

# Verify version
pip --version
# Expected: pip 24.0+ (21.0+ minimum)
```

**Root Cause 3: Virtual Environment Issues**

**Solution:**
```bash
# macOS/Linux
# Delete old venv
rm -rf venv/

# Create fresh venv
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install --no-cache-dir -r requirements.txt

# Windows PowerShell
# Delete old venv
Remove-Item -Recurse -Force venv

# Create fresh venv
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install requirements
pip install --no-cache-dir -r requirements.txt
```

**Root Cause 4: SSL Issues During pip Install**

**Solution:**
```bash
# Use certificate environment variables (see SSL section above)
export REQUESTS_CA_BUNDLE=/path/to/ca.pem
export PIP_CERT=/path/to/ca.pem

# Install with explicit cert
pip install --cert /path/to/ca.pem -r requirements.txt

# Or disable verification (NOT RECOMMENDED)
pip install --trusted-host pypi.org --trusted-host pypi.python.org -r requirements.txt
```

**Root Cause 5: Incompatible Python Version**

**Solution:**
```bash
# Check Python version
python --version

# Required: Python 3.9+
# Recommended: Python 3.11+

# If old Python, install via Homebrew (macOS)
brew install python@3.11

# Or via system package manager (Linux)
sudo apt-get install python3.11

# For Windows: Download from python.org or use Windows Store
```

---

### 🚫 Docker Daemon Not Running

**Symptoms:**
```
Cannot connect to Docker daemon
Docker daemon is not running
/var/run/docker.sock: no such file or directory
```

**macOS:**
```bash
# Start Docker Desktop
open -a Docker

# Or use Colima (lightweight alternative)
colima start

# Verify
docker ps
```

**Linux:**
```bash
# Start Docker service
sudo systemctl start docker

# Enable on boot
sudo systemctl enable docker

# Verify
sudo systemctl status docker
docker ps

# If still failing, check socket
ls -la /var/run/docker.sock
```

**Windows PowerShell:**
```powershell
# Start Docker Desktop
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# Wait 30 seconds for startup, then verify
docker ps
```

---

### 🔌 Services Not Starting

**Symptoms:**
```
Container exited with code 1
Service failed to start
Health check failed
```

**Solution:**
```bash
# View detailed logs
docker compose logs -f

# Check individual service
docker compose logs neo4j
docker compose logs redis
docker compose logs redpanda

# Restart services
docker compose restart

# Full restart (preserves data)
docker compose down
docker compose up -d

# Verify all running
docker compose ps
```

---

### 🚪 Port Already in Use

**Symptoms:**
```
Bind for 0.0.0.0:7474 failed: port is already allocated
Cannot start service: Ports already in use
```

**Find What's Using Port:**

```bash
# macOS/Linux
lsof -i :7474    # Neo4j
lsof -i :6379    # Redis
lsof -i :9644    # Redpanda

# Windows PowerShell
Get-NetTCPConnection -LocalPort 7474
Get-NetTCPConnection -LocalPort 6379
```

**Solutions:**

```bash
# Option 1: Stop the conflicting service
# Find PID from lsof output, then:
kill -9 <PID>

# Option 2: Change ports in docker-compose.yml
# Edit and change port mappings, e.g.:
# ports:
#   - "7475:7474"  (use 7475 instead of 7474)

docker compose down
docker compose up -d

# Option 3: Kill all Docker containers and start fresh
docker compose down -v  # Removes all volumes too!
docker compose up -d
```

---

### ⚠️ Disk Space Issues

**Symptoms:**
```
No space left on device
Cannot write to database
Redpanda: insufficient disk space
```

**Check Disk Space:**
```bash
# macOS/Linux
df -h

# Windows PowerShell
Get-Volume

# Check Docker disk usage
docker system df
```

**Clean Up Docker:**
```bash
# Remove unused images/volumes
docker system prune

# Or more aggressive
docker system prune -a --volumes

# But this will require reinstallation
```

**Increase Allocation:**

```bash
# macOS/Windows Docker Desktop
# Settings → Resources → Disk Image Size
# Increase to 50GB+

# Linux: No limit (uses host filesystem)
# Just clean up unused files
```

---

### 🌐 Network / Firewall Issues

**Symptoms:**
```
Unable to reach API server
Neo4j browser won't connect
Services unreachable from other machines
```

**Verify Services Binding:**
```bash
# macOS/Linux
netstat -tlnp | grep -E "7474|6379|9644|8000"

# Windows PowerShell
netstat -ano | findstr /R "7474|6379|9644|8000"
```

**Check Firewall (macOS):**
```bash
# View firewall status
sudo pfctl -s all

# Allow Docker ports
sudo pfctl -f /etc/pf.conf
```

**Check Firewall (Linux):**
```bash
# UFW
sudo ufw allow 7474
sudo ufw allow 6379
sudo ufw allow 9644
sudo ufw allow 8000

# iptables
sudo iptables -A INPUT -p tcp --dport 7474 -j ACCEPT
```

**Check Firewall (Windows):**
```powershell
# View firewall status
Get-NetFirewallProfile

# Allow ports (Run as Administrator)
New-NetFirewallRule -DisplayName "Neo4j" -Direction Inbound -LocalPort 7474 -Protocol tcp -Action Allow
New-NetFirewallRule -DisplayName "Redis" -Direction Inbound -LocalPort 6379 -Protocol tcp -Action Allow
```

---

### 📊 Performance Issues / Slow Startup

**Symptoms:**
```
Services take 10+ minutes to start
High CPU usage
Memory pressure warnings
GDS graphs slow to load
```

**Check Resource Usage:**
```bash
# Real-time monitoring
docker stats

# Historical logs
docker compose logs neo4j | grep -i "memory\|cpu\|started"
```

**Increase Allocations:**

```bash
# Edit docker-compose.yml - increase memory limits
services:
  neo4j:
    environment:
      NEO4J_server_memory_heap_initial_size: 2g
      NEO4J_server_memory_heap_max_size: 4g
    deploy:
      resources:
        limits:
          memory: 6g

  redpanda:
    deploy:
      resources:
        limits:
          memory: 2g

# Restart with new limits
docker compose down
docker compose up -d
```

**Optimize Storage:**
```bash
# Use SSD instead of HDD (if possible)
# Check storage performance:
# macOS/Linux
iostat -d 1

# Windows
wmic logicaldisk list brief
```

---

### 🆘 Getting Help

If none of the above solutions work:

1. **Collect diagnostic information:**
   ```bash
   # Create diagnostics bundle
   docker compose logs > logs.txt
   docker compose ps > status.txt
   docker system df > disk.txt
   env | grep -E "NEO4J|REDIS|REDPANDA|SSL|PROXY" > env.txt
   
   # Windows also collect:
   wsl -l -v > wsl-status.txt
   ```

2. **Check logs for exact error:**
   ```bash
   docker compose logs neo4j | tail -50
   docker compose logs api | tail -50
   ```

3. **Open GitHub issue:** https://github.com/joseph-webber/agentic-brain/issues
   - Include diagnostic files (sanitize passwords)
   - Include platform/version information
   - Include exact error messages

---

## 🔄 Updating Existing Installation

The installer detects existing installations and handles updates intelligently:

```bash
# Run installer again
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash

# Installer will:
# 1. Detect existing .env (preserves it)
# 2. Fetch latest code from origin
# 3. Check for service updates
# 4. Restart updated services
# 5. Run health checks
```

**Updating Specific Services:**

```bash
# Update Neo4j to latest 2026.02.3
docker compose down neo4j
docker pull neo4j:2026.02.3-community
docker compose up -d neo4j

# Update GDS plugin
# (Automatically included with Neo4j image)

# Update other services
docker compose pull
docker compose up -d
```

**Data Preservation:**

```bash
# All data is preserved in Docker volumes:
docker volume ls

# To backup before updating:
docker compose exec neo4j neo4j-admin dump --to-stdout > neo4j-backup.dump
```

---

## 🏗️ Advanced Configuration

### Production Deployment

**1. Generate Strong Passwords:**

```bash
# macOS/Linux
head -c 32 /dev/urandom | base64  # 64-char password

# Windows PowerShell
[System.Convert]::ToBase64String((1..32 | ForEach-Object { [byte](Get-Random -Min 0 -Max 256) }))
```

**2. Use Environment Variables:**

```bash
# Create .env.prod with production values
cp .env .env.prod
nano .env.prod

# Use strong passwords:
NEO4J_PASSWORD=<strong-random-password>
REDIS_PASSWORD=<strong-random-password>
JWT_SECRET=<very-long-random-string>
ENCRYPTION_KEY=<strong-random-password>

# Use prod environment
export $(cat .env.prod | xargs)
docker compose up -d
```

**3. Enable HTTPS:**

```bash
# Add SSL certificates to docker-compose.yml
services:
  api:
    environment:
      SSL_CERT_FILE: /run/secrets/cert.pem
      SSL_KEY_FILE: /run/secrets/key.pem

secrets:
  cert.pem:
    file: /path/to/certificate.pem
  key.pem:
    file: /path/to/private.key
```

**4. Configure Monitoring:**

```bash
# Add observability stack (optional)
# Prometheus, Grafana, etc.
# See deployment/docker-compose.monitor.yml
```

**5. Set Resource Limits:**

```yaml
# In docker-compose.yml, add deploy limits:
services:
  neo4j:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 6G
        reservations:
          cpus: '1'
          memory: 3G
```

**6. Configure Backups:**

```bash
# Neo4j automated backups
docker compose exec neo4j neo4j-admin dump --to-stdout > backups/neo4j-$(date +%Y%m%d).dump

# Or use backup service
# See docker-compose.yml for backup configuration
```

### High Availability Setup

For multiple nodes (advanced):

```bash
# Use Neo4j cluster docker-compose configuration
# See deployment/ directory for HA setup
docker compose -f docker-compose.ha.yml up -d

# Configure clustering
# Neo4j handles replication automatically
```

### Custom Networking

```yaml
# Use custom network instead of default
networks:
  brain:
    driver: bridge
    ipam:
      config:
        - subnet: 172.25.0.0/16

services:
  neo4j:
    networks:
      - brain
```

---

## 🔒 Security Hardening

### 1. Secure Password Storage

```bash
# Never commit .env to Git
grep -q ".env" .gitignore || echo ".env" >> .gitignore
git add .gitignore && git commit -m "Ensure .env not tracked"

# Protect .env file permissions
chmod 600 .env

# Use secret management (production)
# AWS Secrets Manager
# HashiCorp Vault
# GitHub Secrets
```

### 2. Enable Authentication

```bash
# Neo4j authentication (default: enabled)
docker compose exec neo4j cypher-shell -u neo4j -p $(grep NEO4J_PASSWORD .env | cut -d= -f2)

# Redis authentication
redis-cli -a $(grep REDIS_PASSWORD .env | cut -d= -f2) ping

# API authentication (JWT)
# See API_KEY in .env
```

### 3. Network Isolation

```yaml
# Only expose necessary ports
services:
  neo4j:
    ports:
      - "127.0.0.1:7474:7474"  # Localhost only
      # Don't expose 7687 (bolt) externally

  redis:
    ports:
      - "127.0.0.1:6379:6379"  # Localhost only
```

### 4. Disable Unnecessary Features

```bash
# In .env, disable unused plugins
NEO4J_PLUGINS=["graph-data-science"]  # Only needed plugin

# For Neo4j, disable APOC if not needed
# Edit Dockerfile.neo4j to remove unnecessary extensions
```

### 5. Regular Updates

```bash
# Check for updates monthly
docker pull neo4j:2026.02.3-community
docker pull redpanda:latest
docker pull redis:latest

# Test updates in non-prod first
# Then roll to production
```

---

## 📊 Monitoring & Maintenance

### System Health

```bash
# Check all services
docker compose ps

# CPU/Memory usage
docker stats

# Disk usage
docker system df

# Network connectivity
docker network inspect agentic-brain_default
```

### Service Logs

```bash
# Real-time logs
docker compose logs -f

# Last N minutes
docker compose logs --since 10m

# Last N lines
docker compose logs --tail 100

# Specific service
docker compose logs neo4j
```

### Neo4j Health

```bash
# In Neo4j Browser (http://localhost:7474):
CALL dbms.virtualDatabase.status()
RETURN *

# Check GDS
CALL gds.list()

# Check transactions
CALL dbms.listConnections()
```

### Performance Tuning

```bash
# For production, tune Neo4j
# In docker-compose.yml:
environment:
  NEO4J_server_memory_heap_initial_size: 4g
  NEO4J_server_memory_heap_max_size: 8g
  NEO4J_server_memory_pagecache_size: 4g

# Then restart:
docker compose restart neo4j
```

---

## 📋 Upgrade Procedures

### Version Check

```bash
# Current installed versions
docker compose ps --quiet | xargs docker inspect --format='{{.Config.Image}}'

# Expected:
# neo4j:2026.02.3-community
# redpanda:latest (or specific version)
# redis:latest (or specific version)
```

### Upgrade Neo4j

```bash
# Backup first (important!)
docker compose exec neo4j neo4j-admin dump --to-stdout > backup-before-upgrade.dump

# Stop Neo4j
docker compose down neo4j

# Update docker-compose.yml with new version
# image: neo4j:2026.02.3-community

# Pull new image
docker pull neo4j:2026.02.3-community

# Start with upgrade
docker compose up -d neo4j

# Monitor startup (may take 10+ minutes)
docker compose logs -f neo4j

# Verify
docker compose exec neo4j cypher-shell "RETURN gds.version()"
```

### Upgrade GDS

```bash
# GDS upgrades with Neo4j
# Update NEO4J_GDS_VERSION in docker-compose.yml

# GDS 2.27.0 compatible with Neo4j 2026.02.3

# Restart Neo4j to load new GDS
docker compose restart neo4j

# Verify
docker compose exec neo4j cypher-shell "RETURN gds.version()"
```

### Verify No Data Loss

```bash
# After upgrade, verify data
docker compose exec neo4j cypher-shell "MATCH (n) RETURN count(n) as node_count"

# Should show your data is intact
```

---

## 🧹 Maintenance Tasks

### Daily

```bash
# Monitor logs for errors
docker compose logs --since 1h | grep -i error

# Check disk usage
docker system df
```

### Weekly

```bash
# Backup Neo4j
docker compose exec neo4j neo4j-admin dump --to-stdout > weekly-backup.dump

# Clean old logs
docker system prune -f

# Check for available updates
docker pull neo4j:2026.02.3-community
docker image ls
```

### Monthly

```bash
# Full system check
docker system df
docker stats
docker compose ps

# Review logs for patterns
docker compose logs --since 30d | grep -i warning

# Update all images
docker compose pull
docker compose up -d
```

### Quarterly

```bash
# Test disaster recovery
# Try to restore from backup
# Verify backup integrity

# Performance analysis
# Review query logs in Neo4j
# Check GDS algorithm performance

# Security audit
# Review .env permissions
# Check for exposed ports
# Review access logs
```

---

## 🔐 Backup & Recovery

### Create Backups

```bash
# Full Neo4j backup (with data)
docker compose exec neo4j neo4j-admin dump \
  --database neo4j \
  --to-stdout > backups/neo4j-full-$(date +%Y%m%d).dump

# Incremental backup (if configured)
docker compose exec neo4j neo4j-admin backup \
  --to-path /var/backups
```

### Restore from Backup

```bash
# Stop services
docker compose down

# Restore database
docker compose exec neo4j neo4j-admin load \
  --from-path /var/backups/neo4j-full-20260101.dump \
  --database neo4j

# Restart
docker compose up -d

# Verify
docker compose exec neo4j cypher-shell "MATCH (n) RETURN count(n)"
```

### Cloud Backups

```bash
# Upload to AWS S3
aws s3 cp backups/neo4j-full-$(date +%Y%m%d).dump \
  s3://my-backup-bucket/neo4j/

# Upload to Google Cloud Storage
gsutil cp backups/neo4j-full-$(date +%Y%m%d).dump \
  gs://my-backup-bucket/neo4j/

# Automated daily backup
# Add to crontab:
# 0 2 * * * cd ~/agentic-brain && \
#   docker compose exec neo4j neo4j-admin dump --database neo4j --to-stdout > \
#   backups/neo4j-$(date +\%Y\%m\%d).dump && \
#   aws s3 cp backups/neo4j-$(date +\%Y\%m\%d).dump s3://backup-bucket/
```

---

## 📚 Documentation & Resources

### Official Documentation

- **Neo4j Docs**: https://neo4j.com/docs/
  - Neo4j Operations Manual: https://neo4j.com/docs/operations-manual/2026.02/
  - Cypher Query Language: https://neo4j.com/docs/cypher-manual/current/
- **Neo4j GDS Docs**: https://neo4j.com/docs/graph-data-science/2.27/
  - Algorithm Reference: https://neo4j.com/docs/graph-data-science/2.27/algorithms/
  - ML Pipeline: https://neo4j.com/docs/graph-data-science/2.27/machine-learning/
- **Docker Docs**: https://docs.docker.com/
  - Docker Compose: https://docs.docker.com/compose/
  - Docker Networking: https://docs.docker.com/network/
- **Redpanda Docs**: https://docs.redpanda.com/
- **Redis Docs**: https://redis.io/documentation
- **FastAPI Docs**: https://fastapi.tiangolo.com/

### API Documentation

Once installed, access:
- **Interactive API Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc Docs**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Repository Resources

- **GitHub Issues**: https://github.com/joseph-webber/agentic-brain/issues
- **GitHub Discussions**: https://github.com/joseph-webber/agentic-brain/discussions
- **Pull Requests**: https://github.com/joseph-webber/agentic-brain/pulls
- **Releases**: https://github.com/joseph-webber/agentic-brain/releases

### Tutorials & Guides

- **Getting Started**: See README.md in repository root
- **Quick Start**: See QUICKSTART_API.md
- **Docker Guide**: See DOCKER_SETUP_COMPLETE.md
- **Neo4j Tutorial**: Neo4j Browser includes interactive tutorials
- **GDS Tutorials**: https://neo4j.com/docs/graph-data-science/2.27/model-training/

---

## ❓ FAQ

**Q: Where are my passwords stored?**
A: In `.env` file in the installation directory. Keep this secure and never commit to Git.

**Q: How much disk space do I need?**
A: Minimum 20GB initially. Neo4j database grows with data. Allocate 50+ GB for production.

**Q: Can I run on Raspberry Pi?**
A: Not recommended. Minimum requirements are higher than Pi can support.

**Q: How do I access services from another machine?**
A: Edit `docker-compose.yml` - change port bindings from `127.0.0.1:port` to `0.0.0.0:port`. Then use firewall rules to restrict access.

**Q: What if I lose my .env file?**
A: Passwords are lost. Services won't start without .env. Keep secure backups of .env.

**Q: Can I upgrade Neo4j to a newer version?**
A: Yes, but ensure GDS 2.27.0 compatibility. Always backup first.

**Q: How do I use multiple Neo4j databases?**
A: By default, `neo4j` database is used. Create additional databases via Neo4j Browser.

**Q: Is GDS included free?**
A: GDS has evaluation features. See license status: `CALL gds.license.state()` in Neo4j Browser.

**Q: What LLM providers are supported?**
A: Groq, OpenAI, Anthropic, Together, and local Ollama. Set API keys in .env.

**Q: Can I use this in production?**
A: Yes, with proper configuration. See "Production Deployment" section above. Follow security hardening steps.

---

## 🎓 Learning Resources

### Neo4j Learning

- **GraphAcademy**: https://graphacademy.neo4j.com/ (Free courses)
  - Neo4j Fundamentals
  - Cypher Query Language
  - Graph Data Science
  - Application Development
- **Interactive Sandbox**: https://sandbox.neo4j.com/

### Docker Learning

- **Play with Docker**: https://labs.play-with-docker.com/
- **Docker Official Tutorial**: https://docker-101.github.io/docker-101/

### Graph Data Science

- **Stanford CS224W**: http://web.stanford.edu/class/cs224w/ (Graph Neural Networks)
- **Neo4j GDS Blog**: https://neo4j.com/blog/graph-data-science/
- **Algorithm Papers**: https://neo4j.com/docs/graph-data-science/2.27/algorithms/

---

## 🤝 Support & Community

### Getting Help

1. **Check this guide first** - Ctrl+F or Cmd+F to search
2. **Check GitHub Issues** - Your problem might be solved
3. **Ask in Discussions** - Community forum
4. **Open an Issue** - If no answer found

### Reporting Issues

When opening an issue, include:
1. Your platform (macOS/Linux/Windows)
2. Version information (from error messages)
3. Steps to reproduce
4. Full error messages or logs (sanitized of passwords)
5. Diagnostic bundle (see Troubleshooting section)

### Contributing

- Report bugs and request features on GitHub
- Submit pull requests with improvements
- Help others in Discussions
- Write documentation/tutorials

---

## 📄 License & Legal

**Agentic Brain** - Copyright 2026 Joseph Webber
Licensed under GPL-3.0-or-later

See LICENSE file for full terms.

### Third-Party Licenses

- **Neo4j**: See https://neo4j.com/licensing/ (Server: AGPL-3.0, Client: Apache-2.0)
- **Redpanda**: See https://github.com/redpanda-data/redpanda/blob/dev/COPYING (Redpanda License)
- **Redis**: See https://redis.io/topics/license (Redis Source Available License)
- **Docker**: See https://www.docker.com/legal/docker-software-end-user-license-agreement/
- **FastAPI**: See https://github.com/tiangolo/fastapi (MIT License)

---

## 🚀 Next Steps After Installation

### Immediate (Day 1)

1. ✅ **Verify all services running**
   ```bash
   docker compose ps
   ```

2. ✅ **Test Neo4j connection**
   ```bash
   open http://localhost:7474
   ```

3. ✅ **Review .env configuration**
   ```bash
   cat .env | grep -v "^#"
   ```

4. ✅ **Add LLM API keys (if using cloud)**
   ```bash
   nano .env
   # Uncomment and set API_KEY variables
   ```

### Short-term (First Week)

1. 📖 **Read the README** - Understand core concepts
2. 🔐 **Review Security** - Change default passwords, set up backups
3. 📊 **Explore Neo4j** - Load sample data, write test queries
4. 🧪 **Test API** - Call endpoints, understand responses
5. 🎓 **Take Neo4j Training** - GraphAcademy courses

### Medium-term (First Month)

1. 🏗️ **Understand Architecture** - How services communicate
2. 📈 **Load Your Data** - Import domain data into Neo4j
3. 🤖 **Configure LLM** - Set up preferred AI model
4. 🧠 **Train GDS Models** - Use graph algorithms
5. 🚀 **Deploy First Agent** - Create agentic application

### Long-term (Production)

1. 🔒 **Harden Security** - Production-grade setup
2. 📊 **Set Up Monitoring** - Track performance
3. 💾 **Automate Backups** - Daily backup to cloud
4. 📈 **Optimize Performance** - GDS model tuning
5. 🌍 **Scale Infrastructure** - High availability setup

---

## 💡 Tips & Tricks

### Quick Commands

```bash
# After cd'ing to installation directory:

# View real-time logs
docker compose logs -f

# View logs for one service
docker compose logs -f neo4j

# Monitor resource usage
docker stats

# Enter Neo4j shell
docker compose exec neo4j cypher-shell

# Full system restart (careful!)
docker compose restart

# Stop everything
docker compose down

# Start everything
docker compose up -d

# Remove everything (WARNING: deletes data)
docker compose down -v
```

### Neo4j Browser Shortcuts

- **Ctrl+Enter** / **Cmd+Enter**: Run query
- **Ctrl+Space**: Query autocomplete
- **:play intro**: Interactive tutorial
- **:play apoc**: APOC library introduction
- **MATCH (n) RETURN count(n)**: Count all nodes

### Performance Optimization

```bash
# Neo4j GDS best practices:
# 1. Use native projections for better performance
# 2. Run algorithms on projections, not raw graphs
# 3. Cache results for reuse
# 4. Use implicit filtering in projections
# 5. Monitor memory with CALL gds.listProgress()

# See: https://neo4j.com/docs/graph-data-science/2.27/performance/
```

### Debugging Tips

```bash
# Check service connectivity
docker compose exec neo4j ping redis
docker compose exec api ping neo4j

# View network details
docker network inspect agentic-brain_default

# Check resource limits
docker compose config | grep -A5 "resources:"

# Trace network traffic
docker compose logs --since 5m | grep -i error
```

---

## 🎉 Congratulations!

You've successfully set up a production-grade agentic brain infrastructure.

**You now have:**
- ✅ Neo4j 2026.02.3-community with GDS 2.27.0
- ✅ Event streaming with Redpanda
- ✅ Caching with Redis
- ✅ REST API with FastAPI
- ✅ Knowledge graph for AI agents
- ✅ Enterprise-grade architecture

**Start building:** Create agents, load data, train models, and deploy to production.

For questions or issues, check the troubleshooting guide above or open a GitHub issue.

---

**Happy Brain Building! 🧠🚀**

*Last Updated: 2026*
*Maintained by: Joseph Webber*
*Repository: https://github.com/joseph-webber/agentic-brain*
