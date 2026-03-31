# Windows Installation Guide

Quick guide for installing Agentic Brain on Windows.

---

## 🚀 Recommended: Docker Method (Tested by Will)

This is the **simplest and most reliable** method for Windows users.

### Prerequisites

1. **Docker Desktop for Windows**
   - Download: https://www.docker.com/products/docker-desktop/
   - Install and ensure it's running (whale icon in system tray)

2. **Git Bash for Windows**
   - Download: https://github.com/git-for-windows/git/releases/download/v2.53.0.windows.2/Git-2.53.0.2-64-bit.exe
   - This provides a Unix-like shell for running setup scripts

3. **Python 3.10, 3.11, or 3.12** (NOT 3.13 or 3.14!)
   - Some dependencies like `rapidocr-onnxruntime` don't support Python 3.13+
   - Download Python 3.12: https://www.python.org/downloads/release/python-3129/

### Installation Steps

**Step 1: Clone and Setup**

Open Git Bash and run:
```bash
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain/
./setup.sh
```

**Step 2: Verify Environment Files Created**

The setup script should create these files automatically:
- `.env` - Main application config
- `.env.dev` - Docker dev config (REQUIRED for docker-compose.dev.yml)
- `.env.docker` - Docker production config

If `.env.dev` is missing, create it manually:
```bash
cp .env.dev.example .env.dev
```

**Step 3: Start Services**

```bash
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml up -d
```

**Step 4: Verify**

```bash
# Check containers are running
docker ps

# View logs
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml logs -f
```

---

## ⚠️ Common Issues and Fixes

### "NEO4J_PASSWORD must be set in .env.dev"

**Cause:** The `.env.dev` file doesn't exist or is empty.

**Fix:**
```bash
# Create from example
cp .env.dev.example .env.dev

# OR create manually with these contents:
cat > .env.dev << 'EOF'
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Brain2026
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=BrainRedis2026
ENVIRONMENT=dev
DEBUG=true
EOF
```

### "REDIS_PASSWORD must be set in .env.dev"

Same fix as above - the `.env.dev` file needs `REDIS_PASSWORD=BrainRedis2026`.

### "No matching distribution found for rapidocr-onnxruntime"

**Cause:** You're using Python 3.13 or 3.14, which is too new.

**Fix:** Install Python 3.12 instead:
```powershell
winget install Python.Python.3.12
```

Then recreate your virtualenv:
```bash
rm -rf .venv
python3.12 -m venv .venv
./setup.sh
```

### "Failed to read config: Unrecognized setting URI"

**Cause:** Neo4j container is receiving invalid environment variables.

**Fix:** Check your `.env.dev` file - make sure there's no `URI=` line without `NEO4J_` prefix:
```bash
# WRONG:
URI=bolt://localhost:7687

# CORRECT:
NEO4J_URI=bolt://localhost:7687
```

---

## Alternative: PowerShell Method

If you prefer not to use Docker:

```powershell
# Run in PowerShell (as Administrator recommended)
irm https://raw.githubusercontent.com/agentic-brain-project/agentic-brain/main/setup.ps1 | iex
```

Or clone and run:
```powershell
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain
.\setup.ps1
```

## Common Issues

### "Python was not found" Error

This usually means Windows is showing the Microsoft Store stub instead of real Python.

**Fix 1: Disable App Execution Aliases**
1. Open Windows Settings
2. Go to Apps > Apps & features > App execution aliases
3. Turn OFF "python.exe" and "python3.exe" (the ones pointing to Microsoft Store)

**Fix 2: Install Python Properly**
```powershell
# Using winget (recommended)
winget install Python.Python.3.12

# Or download from python.org
# Make sure to check "Add Python to PATH" during installation!
```

**Fix 3: Use py launcher**
```powershell
# Check if py launcher works
py -3 --version
```

### SSL Certificate Errors

If you see SSL/certificate errors, you have several options:

**Option 1: Generate Self-Signed Cert (Development)**
```powershell
# Install mkcert (easiest)
choco install mkcert
mkcert -install
mkcert localhost 127.0.0.1 ::1

# Or use OpenSSL
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

**Option 2: Configure in .env**
```env
SSL_ENABLED=true
SSL_CERT_FILE=C:\path\to\cert.pem
SSL_KEY_FILE=C:\path\to\key.pem
```

**Option 3: Skip SSL Verification (Development Only!)**
```env
SSL_VERIFY=false
```

**Option 4: Corporate CA Bundle**
If behind corporate proxy:
```env
REQUESTS_CA_BUNDLE=C:\path\to\corporate-ca-bundle.crt
```

### Ollama Connection Issues

If Ollama isn't connecting:

```powershell
# Check Ollama is running
ollama list

# Set correct host in .env
OLLAMA_HOST=http://localhost:11434
```

### Permission Errors

Run PowerShell as Administrator:
```powershell
Start-Process powershell -Verb runAs
```

Or set execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Installation Log

If something fails, check the log file:
```powershell
# Log is saved to temp folder
notepad $env:TEMP\agentic_brain_install_*.txt
```

## Verify Installation

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Test the installation
python -c "from agentic_brain import Agent; print('OK!')"

# Run the server
agentic-brain serve
```

## Getting Help

If you're still stuck:
1. Check the log file (see above)
2. Open an issue at https://github.com/agentic-brain-project/agentic-brain/issues
3. Include: Windows version, Python version, full error message
