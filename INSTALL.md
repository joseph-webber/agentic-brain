# 🧠 Agentic Brain - Bulletproof Installer

**One-line installation for Mac, Linux, and Windows.**

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

## ✨ Features

The bulletproof installer includes:

- ✅ **Auto-detects and installs Docker** if missing (Linux only)
- ✅ **Docker Compose v1 & v2 support**
- ✅ **Generates random, secure passwords** (Retool pattern)
- ✅ **Comprehensive .env configuration** with all required variables
- ✅ **Corporate SSL/proxy support** with PIP_TRUSTED_HOST
- ✅ **Health checks** for all services (Neo4j, Redis, Redpanda)
- ✅ **Detailed status output** with emoji feedback
- ✅ **Works offline** after initial clone
- ✅ **Git-aware** - updates existing installations

---

## 📋 What Gets Installed

After running the installer, you'll have:

```
agentic-brain/
├── .env                          # Generated with random passwords
├── docker-compose.yml            # Neo4j, Redis, Redpanda
├── src/                          # Application code
├── docs/                         # Documentation
└── ...                           # All other repo files
```

**Services started:**
- **Neo4j** (Graph Database) → http://localhost:7474
- **Redis** (Cache) → localhost:6379
- **Redpanda** (Message Queue) → http://localhost:9644
- **API Server** → http://localhost:8000

---

## 🔐 Security

The installer follows the **Retool install pattern**:

1. **Random Passwords**: Uses `/dev/urandom | base64` to generate:
   - Neo4j password (64 chars)
   - Redis password (64 chars)
   - JWT secret (256 chars)
   - Encryption key (64 chars)

2. **Pre-existing .env Protection**: Like Retool, exits if `.env` already exists to protect existing configurations

3. **Corporate SSL Support**: Automatically configures `PIP_TRUSTED_HOST` if behind a proxy:
   ```bash
   export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
   export SSL_CERT_FILE=/path/to/ca-bundle.crt
   ```

---

## 🛠️ Installation Requirements

### Mac/Linux
- **Git** (for cloning)
- **Docker** (auto-installed on Linux if missing)
- **Docker Compose** (included with Docker Desktop)

### Windows
- **Git** (winget: `winget install Git.Git`)
- **Docker Desktop** (winget: `winget install Docker.DockerDesktop`)
- **PowerShell 5.0+** (built-in on Windows 10+)

---

## 📱 Installation Options

### Option 1: One-Line Install (Recommended)
```bash
# Mac/Linux
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

### Option 2: Clone First, Then Install
```bash
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain
./install.sh          # Mac/Linux
# OR
.\install.ps1         # Windows
```

### Option 3: Custom Installation Directory
```bash
# Mac/Linux
AGENTIC_BRAIN_DIR=~/my-brain bash <(curl -fsSL https://..../install.sh)

# Windows
$env:AGENTIC_BRAIN_DIR = "C:\brain"
irm https://..../install.ps1 | iex
```

---

## ✅ Post-Installation

After successful installation, you'll see:

```
╔═══════════════════════════════════════════════════════════════╗
║        🎉 Agentic Brain Installed Successfully! 🎉            ║
╚═══════════════════════════════════════════════════════════════╝

📍 Service URLs:
   • API Server:      http://localhost:8000
   • API Docs:        http://localhost:8000/docs
   • Neo4j Browser:   http://localhost:7474
   • Redpanda UI:     http://localhost:9644

🔐 Default Credentials:
   • Neo4j User:      neo4j
   • Neo4j Password:  (See .env)
   • Redis Password:  (See .env)

📂 Installation Directory:
   /Users/joe/agentic-brain

🚀 Quick Commands:
   cd /Users/joe/agentic-brain
   docker compose logs -f      # View logs
   docker compose ps           # Check status
   docker compose down         # Stop services
   docker compose up -d        # Start services
```

### Next Steps:

1. **Review Configuration**
   ```bash
   cat .env
   ```

2. **Add LLM API Key** (if using cloud provider)
   ```bash
   # Edit .env and uncomment ONE provider:
   nano .env
   
   # GROQ_API_KEY=your-key
   # OPENAI_API_KEY=your-key
   # ANTHROPIC_API_KEY=your-key
   ```

3. **Test the Installation**
   ```bash
   # Visit in browser
   http://localhost:7474          # Neo4j
   http://localhost:8000/docs     # API docs
   
   # Or test with curl
   curl http://localhost:8000/health
   ```

4. **Set Up Local LLM** (Optional)
   ```bash
   ollama pull llama3.2
   ```

---

## 🐛 Troubleshooting

### Docker daemon not running
```bash
# Mac: Start Docker Desktop
open -a Docker

# Or use Colima (auto-detected)
colima start

# Linux: Start Docker service
sudo systemctl start docker
```

### Services not starting
```bash
# Check logs
cd ~/agentic-brain
docker compose logs -f

# Restart services
docker compose down
docker compose up -d
```

### Port already in use
```bash
# Find what's using port 8000, 6379, 7474, etc.
lsof -i :8000      # Mac/Linux
Get-NetTCPConnection -LocalPort 8000  # Windows
```

### Corporate proxy issues
Set environment variables before running installer:
```bash
export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
export SSL_CERT_FILE=/path/to/ca-bundle.crt
curl -fsSL https://..../install.sh | bash
```

### Git not found
```bash
# Mac
brew install git

# Linux (Ubuntu/Debian)
sudo apt-get install git

# Windows
winget install Git.Git
```

---

## 🔄 Updating Existing Installation

The installer detects existing installations and updates them:

```bash
# Run installer again
curl -fsSL https://..../install.sh | bash

# It will:
# 1. Detect existing repo
# 2. Fetch latest from origin
# 3. Preserve existing .env
# 4. Restart services
```

---

## 🏗️ Advanced Configuration

### Using a Different Branch
```bash
# Mac/Linux
AGENTIC_BRAIN_BRANCH=develop bash <(curl -fsSL https://..../install.sh)

# Windows
$env:AGENTIC_BRAIN_BRANCH = "develop"
irm https://..../install.ps1 | iex
```

### Production Deployment
1. **Generate strong passwords** (don't use defaults)
   ```bash
   cat /dev/urandom | base64 | head -c 64  # Mac/Linux
   ```

2. **Use environment variables**
   ```bash
   export NEO4J_PASSWORD="your-strong-password"
   export REDIS_PASSWORD="your-strong-password"
   ```

3. **Enable HTTPS** - Configure SSL certificates in docker-compose.yml

4. **Set up monitoring** - Configure observability stack

---

## 🔒 Password Storage

Passwords are stored in `.env` - **KEEP THIS FILE SECURE**:

```bash
# Recommended: Only owner can read
chmod 600 .env

# Recommended: Add to .gitignore (already done)
echo ".env" >> .gitignore

# Never commit .env to version control
git status
```

---

## 📚 Documentation

- [API Documentation](http://localhost:8000/docs)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [Agentic Brain Repository](https://github.com/joseph-webber/agentic-brain)

---

## 🤝 Support

Having issues? Check:

1. **Logs**: `docker compose logs -f`
2. **Status**: `docker compose ps`
3. **GitHub Issues**: https://github.com/joseph-webber/agentic-brain/issues
4. **Documentation**: See repo README.md

---

## 📄 License

Agentic Brain - Copyright 2026 Joseph Webber
Licensed under GPL-3.0-or-later

---

**🚀 Happy Brain Building! 🚀**
