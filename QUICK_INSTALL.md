# 🚀 Agentic Brain - Quick Install Guide

## 30-Second Installation

### macOS / Linux
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
```

### Windows PowerShell
```powershell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

**That's it!** Services will start automatically.

---

## ⏱️ What Happens

```
✅ Checks for Docker (installs if missing)
✅ Checks for Docker Compose
✅ Clones/updates agentic-brain repository
✅ Generates random, secure passwords
✅ Creates .env configuration file
✅ Pulls Docker images
✅ Starts all services
✅ Waits for services to be healthy
✅ Shows you the next steps
```

**Total time:** 1-2 minutes (first run)

---

## 🎯 Next Steps After Installation

### 1. Open Neo4j Browser
http://localhost:7474

### 2. Open API Documentation
http://localhost:8000/docs

### 3. Configure LLM (Optional)

Edit `.env` and uncomment one:
```bash
cd ~/agentic-brain
nano .env

# Uncomment ONE of these:
# GROQ_API_KEY=your-key-here
# OPENAI_API_KEY=your-key-here
# ANTHROPIC_API_KEY=your-key-here
```

### 4. Verify Everything Works
```bash
curl http://localhost:8000/health
```

---

## 🛠️ Common Commands

```bash
# View logs
docker compose logs -f

# Check service status
docker compose ps

# Stop services
docker compose down

# Start services again
docker compose up -d

# Restart a specific service
docker compose restart neo4j
```

---

## 🐛 Troubleshooting

### General

**Docker not running?**
```bash
# Mac: Start Docker Desktop
open -a Docker

# Linux: Start Docker service
sudo systemctl start docker

# Windows: Start Docker Desktop
# Click the Docker Desktop icon in Start Menu
```

**Port already in use?**
```bash
# Mac/Linux: Find what's using the port
lsof -i :8000

# Windows PowerShell: Find what's using the port
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess
```

**Need to see the logs?**
```bash
docker compose logs neo4j
docker compose logs redis
docker compose logs app
```

### Windows-Specific Issues

**PowerShell execution policy prevents install?**
```powershell
# Run PowerShell as Administrator, then:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# Then run the install command again
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
```

**WSL2 backend not installed?**
```powershell
# Install WSL2 (Windows Subsystem for Linux 2)
wsl --install
# Restart your computer, then start Docker Desktop
```

**Docker Desktop won't start?**
```powershell
# Check if Hyper-V is enabled (required for Docker)
Get-WindowsOptionalFeature -FeatureName Microsoft-Hyper-V -Online

# If not enabled, run as Administrator:
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
# Then restart your computer
```

**Line endings issue on Windows?**
```powershell
# If scripts fail with "line ending" errors:
git config --global core.autocrlf false
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain
./install.ps1
```

**"Command not recognized" errors?**
```powershell
# Ensure you're using PowerShell (not Command Prompt)
# Windows 11: Use Windows Terminal (recommended)
# Right-click and select "Open with Windows Terminal"
```

**Services starting but not healthy?**
```bash
# Check individual service status
docker compose ps

# Restart all services
docker compose down
docker compose up -d

# Wait 30 seconds for services to initialize
docker compose ps
```

---

## 📚 Full Documentation

See [INSTALL.md](./INSTALL.md) for complete details

See [INSTALLER_FEATURES.md](./INSTALLER_FEATURES.md) for technical details

---

## ✨ What You Get

- **Neo4j 2026.02.3-community** Graph Database → http://localhost:7474
- **GDS 2.27.0** Graph Data Science Library
- **Redis** Cache Layer → localhost:6379  
- **Redpanda** Message Queue → http://localhost:9644
- **API Server** → http://localhost:8000
- **Random passwords** generated and stored in .env
- **All dependencies** installed automatically

---

## 🔐 Security

- ✅ Random passwords for all services
- ✅ Passwords stored in .env (keep private!)
- ✅ Not committed to git
- ✅ One-line install is safe to run

---

## 💬 Questions?

- Check the logs: `docker compose logs -f`
- Read [INSTALL.md](./INSTALL.md)
- Visit the API docs: http://localhost:8000/docs
- Check GitHub Issues: https://github.com/joseph-webber/agentic-brain/issues

---

**You're all set! 🧠✨**
