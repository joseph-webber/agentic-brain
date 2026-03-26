# Agentic Brain Installation Options

Choose your installation method based on your environment:

| Method | Best For | Difficulty | Time |
|--------|----------|------------|------|
| **WSL (Recommended for Windows)** | Windows users, enterprise | ⭐ Easy | 10 min |
| **Docker** | Any OS, isolated setup | ⭐ Easy | 5 min |
| **Native Windows** | Windows without WSL/Docker | ⭐⭐ Medium | 15 min |
| **Native Linux/Mac** | Linux, macOS users | ⭐ Easy | 5 min |

---

## Option 1: WSL (Windows Subsystem for Linux) - RECOMMENDED FOR WINDOWS

WSL gives you a real Linux environment inside Windows. No Python path issues, no SSL headaches.

### Step 1: Install WSL (One-time setup)

Open **PowerShell as Administrator** and run:

```powershell
wsl --install
```

This installs Ubuntu by default. **Restart your computer when prompted.**

### Step 2: Open WSL and Install Agentic Brain

After restart, open "Ubuntu" from the Start menu, then run:

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install -y python3 python3-pip python3-venv git

# Clone and install
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain
./setup.sh
```

### Step 3: Run Agentic Brain

```bash
# Activate the virtual environment
source .venv/bin/activate

# Start the server
agentic-brain serve
```

Access at: http://localhost:8000

### WSL Tips

```powershell
# From PowerShell - check WSL status
wsl --status

# List installed distros
wsl --list --verbose

# Enter WSL
wsl

# Access Windows files from WSL
cd /mnt/c/Users/YourName/

# Access WSL files from Windows
# Open File Explorer and go to: \\wsl$\Ubuntu\home\
```

---

## Option 2: Docker - EASIEST FOR ANY OS

Docker runs everything in containers. No local Python needed.

### Prerequisites

Install Docker Desktop:
- **Windows**: https://docs.docker.com/desktop/install/windows-install/
- **Mac**: https://docs.docker.com/desktop/install/mac-install/
- **Linux**: https://docs.docker.com/engine/install/

### Quick Start

```bash
# Clone the repo
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Start everything (Neo4j + Agentic Brain)
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

Access at: http://localhost:8000

### Docker with Ollama (Local LLM)

```bash
# Install Ollama first (see ollama.com)
ollama pull llama3.2

# Then start agentic-brain - it connects to host Ollama automatically
docker-compose up -d
```

### Stop/Restart

```bash
# Stop
docker-compose down

# Stop and delete data (fresh start)
docker-compose down -v

# Restart
docker-compose restart
```

---

## Option 3: Native Windows (Without WSL/Docker)

If you can't use WSL or Docker, use native Windows installation.

### Prerequisites

1. **Install Python 3.10+**
   ```powershell
   winget install Python.Python.3.12
   ```
   
2. **Disable Windows Store Python aliases**
   - Settings > Apps > App execution aliases
   - Turn OFF python.exe and python3.exe

3. **Install Git**
   ```powershell
   winget install Git.Git
   ```

### Install Agentic Brain

```powershell
# Clone repo
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Run installer
.\setup.ps1
```

Or use the one-liner:
```powershell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/setup.ps1 | iex
```

### Troubleshooting Windows

See [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md) for common issues.

---

## Option 4: Native Linux/Mac

### Prerequisites

- Python 3.10+ 
- Git

### Install

```bash
# Clone
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Run installer
./setup.sh

# Or manually
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
```

---

## After Installation

### Verify Installation

```bash
# Activate venv (if not using Docker)
source .venv/bin/activate  # Linux/Mac/WSL
.\.venv\Scripts\Activate.ps1  # Windows

# Test import
python -c "from agentic_brain import Agent; print('OK!')"

# Start server
agentic-brain serve
```

### Configure LLM Provider

Edit `.env` file:

```env
# Option A: Ollama (local, free)
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434

# Option B: OpenAI
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key

# Option C: Anthropic Claude
DEFAULT_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
```

### Install Ollama (Recommended)

Ollama runs LLMs locally - free and private.

```bash
# Install (all platforms)
curl -fsSL https://ollama.com/install.sh | sh

# Or on Windows
winget install Ollama.Ollama

# Pull a model
ollama pull llama3.2

# Verify
ollama list
```

---

## Corporate/Enterprise Notes

### Behind a Proxy

```bash
# Set proxy environment variables
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
export NO_PROXY=localhost,127.0.0.1

# For pip
pip install --proxy http://proxy.company.com:8080 -e ".[all]"
```

### SSL Certificate Issues

If your company intercepts SSL:

```bash
# Option 1: Add corporate CA bundle
export REQUESTS_CA_BUNDLE=/path/to/corporate-ca-bundle.crt

# Option 2: Disable SSL verify (development only!)
export SSL_VERIFY=false
```

### Firewall Ports

Ensure these ports are open:
- 8000: Agentic Brain API
- 7687: Neo4j Bolt (if using Neo4j)
- 7474: Neo4j Browser (if using Neo4j)
- 11434: Ollama (if using local LLM)

---

## Getting Help

1. Check the [troubleshooting docs](WINDOWS_INSTALL.md)
2. Open an issue: https://github.com/joseph-webber/agentic-brain/issues
3. Include: OS version, Python version, full error message, install log
