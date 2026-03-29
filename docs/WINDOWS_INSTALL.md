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

### Installation Steps

**Step 1: Clone and Setup**

Open Git Bash and run:
```bash
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain/
./setup.sh
```

**Step 2: Configure Environment**

Copy the example environment file and configure it:
```bash
cp .env.dev.example .env.dev
```

Edit `.env.dev` with your settings (Neo4j password, Redis password, etc.).

**Step 3: Corporate Proxy Configuration (If Needed)**

If you're behind a corporate proxy and encounter SSL/certificate errors during Docker builds, the Dockerfile already includes trusted-host configuration for pip. No additional action needed.

**Step 4: Start Services**

```bash
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml up -d
```

**Step 5: Verify**

```bash
# Check containers are running
docker ps

# View logs
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml logs -f
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
