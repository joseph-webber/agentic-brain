# Agentic Brain Installation Guide

> **Version**: 2.12.0 | **Python**: 3.11+ | **Last Updated**: March 2026

Enterprise-grade AI Agent Platform with GraphRAG, Multi-LLM support, and 155+ RAG loaders.

---

## Table of Contents

- [Quick Install (Recommended)](#quick-install-recommended)
- [Platform-Specific Setup](#platform-specific-setup)
- [Docker Installation](#docker-installation)
- [Development Setup](#development-setup)
- [Optional Dependencies](#optional-dependencies)
- [Corporate/Proxy Environments](#corporateproxy-environments)
- [Troubleshooting](#troubleshooting)
- [Verifying Installation](#verifying-installation)

---

## Quick Install (Recommended)

### Using pipx (All Platforms) ⭐ Best Practice

**pipx is the modern, PEP 668-compliant way to install Python CLI tools.**

Each tool gets its own isolated virtual environment, avoiding dependency conflicts.

```bash
# Install pipx first (if not already installed)
# macOS
brew install pipx

# Ubuntu/Debian
sudo apt install pipx

# Windows (PowerShell as Admin)
python -m pip install --user pipx

# Ensure pipx is in your PATH
pipx ensurepath
```

Then install Agentic Brain:

```bash
# Basic installation
pipx install agentic-brain

# With Neo4j memory support (recommended for production)
pipx install "agentic-brain[memory]"

# With API server
pipx install "agentic-brain[api]"

# Full installation with all features
pipx install "agentic-brain[all]"
```

**Available commands after install:**
- `agentic-brain` - Full command
- `agentic` - Short alias
- `ab` - Shortest alias

### Using pip (Virtual Environment)

If you prefer traditional pip, **always use a virtual environment**:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate     # Windows

# Install
pip install agentic-brain

# With extras
pip install "agentic-brain[memory,api,llm]"
```

### Using uv (Ultra-fast Alternative)

[uv](https://github.com/astral-sh/uv) is a fast Rust-based Python package installer:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install agentic-brain
uv pip install agentic-brain

# Or create a managed environment
uv venv
source .venv/bin/activate
uv pip install "agentic-brain[all]"
```

---

## Platform-Specific Setup

### macOS

#### Prerequisites

```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11+
brew install python@3.12

# Install pipx (recommended)
brew install pipx
pipx ensurepath

# For voice synthesis (optional)
# macOS has built-in 'say' command - no additional setup needed
```

#### Apple Silicon (M1/M2/M3) GPU Acceleration

```bash
# Install with MLX support for Apple Silicon
pipx install "agentic-brain[mlx]"

# Or if using pip
pip install "agentic-brain[mlx]"
```

#### Install Agentic Brain

```bash
pipx install "agentic-brain[memory,api]"
```

#### Optional: Docker for Services

```bash
# Install Docker Desktop
brew install --cask docker

# Or use Colima (lightweight alternative)
brew install colima docker docker-compose
colima start
```

---

### Windows

#### Prerequisites

1. **Install Python 3.11+**
   - Download from [python.org](https://www.python.org/downloads/)
   - ✅ Check "Add Python to PATH" during installation
   - ✅ Check "Install pip"

2. **Install Git** (optional but recommended)
   - Download from [git-scm.com](https://git-scm.com/download/win)

3. **Open PowerShell as Administrator**

#### Install pipx

```powershell
# Install pipx
python -m pip install --user pipx
python -m pipx ensurepath

# Restart PowerShell, then verify
pipx --version
```

#### Install Agentic Brain

```powershell
# Basic installation
pipx install agentic-brain

# With features
pipx install "agentic-brain[memory,api]"
```

#### Alternative: Git Bash

If you prefer a Unix-like environment:

```bash
# In Git Bash
python -m pip install --user pipx
python -m pipx ensurepath
pipx install agentic-brain
```

#### Docker Desktop (Optional)

1. Download [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
2. Enable WSL 2 backend during installation
3. Restart your computer

---

### Linux (Ubuntu/Debian)

#### Prerequisites

```bash
# Update package list
sudo apt update

# Install Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip

# Install pipx (Ubuntu 23.04+ / Debian 12+)
sudo apt install pipx
pipx ensurepath

# For older systems, install pipx via pip
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

#### Install Agentic Brain

```bash
pipx install "agentic-brain[memory,api]"
```

#### Voice Synthesis Dependencies

```bash
# For pyttsx3 (espeak backend)
sudo apt install espeak libespeak1

# For festival TTS (alternative)
sudo apt install festival
```

---

### Linux (Fedora/RHEL/CentOS)

#### Prerequisites

```bash
# Fedora
sudo dnf install python3.11 python3-pip pipx

# RHEL/CentOS 8+
sudo dnf install python39 python39-pip
pip3 install --user pipx

# Add to PATH
pipx ensurepath
```

#### Install Agentic Brain

```bash
pipx install "agentic-brain[memory,api]"
```

---

### Linux (Arch/Manjaro)

```bash
# Install prerequisites
sudo pacman -S python python-pipx

# Install agentic-brain
pipx install "agentic-brain[memory,api]"
```

---

## Docker Installation

### Quick Start with Docker

```bash
# Pull the latest image
docker pull josephwebber/agentic-brain:latest

# Run with default settings
docker run -p 8000:8000 josephwebber/agentic-brain

# Run with environment variables
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e NEO4J_URI=bolt://host.docker.internal:7687 \
  josephwebber/agentic-brain
```

### Docker Compose (Recommended for Production)

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  agentic-brain:
    image: josephwebber/agentic-brain:latest
    ports:
      - "8000:8000"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=your_password
      - REDIS_URL=redis://redis:6379
    depends_on:
      - neo4j
      - redis

  neo4j:
    image: neo4j:5.18-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/your_password
    volumes:
      - neo4j_data:/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  neo4j_data:
  redis_data:
```

Run with:

```bash
docker-compose up -d
```

### Building from Source

```bash
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain
docker build -t agentic-brain .
docker run -p 8000:8000 agentic-brain
```

---

## Development Setup

### Clone and Install for Development

```bash
# Clone the repository
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev,test,memory,api]"

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/agentic_brain --cov-report=html

# Run specific test categories
pytest -m unit        # Fast unit tests
pytest -m integration # Integration tests
```

### Code Quality

```bash
# Format code
black src tests
ruff check src tests --fix

# Type checking
mypy src
```

---

## Optional Dependencies

Install additional features as needed:

| Extra | Purpose | Install Command |
|-------|---------|-----------------|
| `memory` | Neo4j persistence | `pipx install "agentic-brain[memory]"` |
| `api` | FastAPI server | `pipx install "agentic-brain[api]"` |
| `llm` | OpenAI/Anthropic clients | `pipx install "agentic-brain[llm]"` |
| `redis` | Redis caching | `pipx install "agentic-brain[redis]"` |
| `mlx` | Apple Silicon acceleration | `pipx install "agentic-brain[mlx]"` |
| `embeddings` | Local embeddings (torch) | `pipx install "agentic-brain[embeddings]"` |
| `vectordb` | Vector databases | `pipx install "agentic-brain[vectordb]"` |
| `enterprise` | LDAP/SAML/MFA | `pipx install "agentic-brain[enterprise]"` |
| `observability` | OpenTelemetry | `pipx install "agentic-brain[observability]"` |
| `firebase` | Firebase integration | `pipx install "agentic-brain[firebase]"` |
| `all` | Everything | `pipx install "agentic-brain[all]"` |

**Combine multiple extras:**

```bash
pipx install "agentic-brain[memory,api,llm,redis]"
```

---

## Corporate/Proxy Environments

### Pip Configuration for Proxies

Create or edit `~/.pip/pip.conf` (Linux/macOS) or `%APPDATA%\pip\pip.ini` (Windows):

```ini
[global]
proxy = http://proxy.company.com:8080
trusted-host = 
    pypi.org
    pypi.python.org
    files.pythonhosted.org

[install]
trusted-host = 
    pypi.org
    pypi.python.org
    files.pythonhosted.org
```

### Environment Variables for Proxy

```bash
# Linux/macOS
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
export NO_PROXY=localhost,127.0.0.1,.internal.company.com

# Windows PowerShell
$env:HTTP_PROXY = "http://proxy.company.com:8080"
$env:HTTPS_PROXY = "http://proxy.company.com:8080"
```

### SSL Certificate Issues

If you encounter SSL certificate errors behind a corporate firewall:

```bash
# Option 1: Use trusted hosts (temporary)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org agentic-brain

# Option 2: Add corporate CA certificate
pip config set global.cert /path/to/corporate-ca-bundle.crt

# Option 3: Disable SSL verification (NOT RECOMMENDED for production)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org agentic-brain
```

### Using Private PyPI Mirror

```bash
# Configure private index
pip config set global.index-url https://pypi.company.com/simple/
pip config set global.extra-index-url https://pypi.org/simple/

# Or install directly
pip install --index-url https://pypi.company.com/simple/ agentic-brain
```

### Air-Gapped Installation

For systems without internet access:

```bash
# On a connected machine: download packages
pip download -d ./packages "agentic-brain[memory,api]"

# Transfer ./packages directory to air-gapped system

# On air-gapped system: install from local files
pip install --no-index --find-links=./packages agentic-brain
```

---

## Troubleshooting

### Common Errors and Solutions

#### PEP 668: "externally-managed-environment" Error

**Problem**: Modern Linux distributions protect system Python.

```
error: externally-managed-environment
```

**Solution**: Use pipx (recommended) or a virtual environment:

```bash
# Recommended: Use pipx
pipx install agentic-brain

# Alternative: Use virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install agentic-brain

# NOT RECOMMENDED (breaks system Python)
# pip install --break-system-packages agentic-brain
```

#### "command not found: agentic-brain"

**Problem**: PATH not configured properly.

**Solution**:

```bash
# Ensure pipx path is added
pipx ensurepath

# Restart your terminal or run
source ~/.bashrc  # or ~/.zshrc
```

#### Neo4j Connection Failed

**Problem**: Can't connect to Neo4j database.

**Solution**:

```bash
# Check Neo4j is running
docker ps | grep neo4j

# Start Neo4j if not running
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.18-community

# Test connection
curl http://localhost:7474
```

#### Python Version Mismatch

**Problem**: Agentic Brain requires Python 3.11+

```
ERROR: agentic-brain requires Python >=3.11
```

**Solution**:

```bash
# Check your Python version
python3 --version

# Install Python 3.11+ 
# macOS
brew install python@3.12

# Ubuntu
sudo apt install python3.12

# Use pyenv for version management
curl https://pyenv.run | bash
pyenv install 3.12
pyenv global 3.12
```

#### Voice Synthesis Not Working (Linux)

**Problem**: pyttsx3 can't find espeak.

**Solution**:

```bash
# Install espeak
sudo apt install espeak libespeak1

# Or use gTTS (cloud-based fallback)
pip install gTTS
```

#### Docker Permission Denied

**Problem**: Can't run Docker commands.

**Solution**:

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run
newgrp docker
```

#### ImportError: No module named 'agentic_brain'

**Problem**: Package not installed correctly or wrong environment.

**Solution**:

```bash
# Check if installed
pip list | grep agentic

# Verify virtual environment is activated
which python  # Should show .venv path

# Reinstall
pip install --force-reinstall agentic-brain
```

---

## Verifying Installation

After installation, verify everything works:

```bash
# Check version
agentic-brain --version

# Or use short alias
ab --version

# Show help
agentic-brain --help

# Test basic functionality
agentic-brain health

# Start interactive mode
agentic-brain chat
```

### Quick Health Check

```bash
# Check all components
agentic-brain doctor
```

### Environment Info

```bash
# Show system information
agentic-brain info

# Expected output:
# Agentic Brain v2.12.0
# Python: 3.12.x
# Platform: macOS-14.x-arm64 / Linux-6.x-x86_64 / Windows-10
# Neo4j: Connected / Not configured
# Redis: Connected / Not configured
```

---

## Next Steps

After installation:

1. **Quick Start Guide**: `docs/QUICKSTART.md`
2. **Configuration**: `docs/configuration.md`
3. **API Reference**: `docs/API_REFERENCE.md`
4. **LLM Setup**: `docs/LLM_GUIDE.md`

---

## Getting Help

- **Documentation**: [docs/INDEX.md](INDEX.md)
- **GitHub Issues**: [github.com/agentic-brain-project/agentic-brain/issues](https://github.com/agentic-brain-project/agentic-brain/issues)
- **Discussions**: [github.com/agentic-brain-project/agentic-brain/discussions](https://github.com/agentic-brain-project/agentic-brain/discussions)

---

*Last updated: March 2026*
