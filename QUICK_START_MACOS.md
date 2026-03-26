# 🚀 Quick Start - macOS

**Get running in 5 minutes on macOS (M1/M2/M3 or Intel)**

## Prerequisites

```bash
# Install Homebrew (if not already)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11+
brew install python@3.11

# Install Docker (optional - for Neo4j/Redis)
brew install colima docker docker-compose
colima start
```

## Install & Run

```bash
# 1. Clone repo
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# 2. Run automated setup
./setup.sh -i

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install Ollama (local LLM - free!)
brew install ollama
brew services start ollama
ollama pull llama3.2

# 5. Configure (minimal)
cp .env.example .env
# Edit .env: Set OLLAMA_BASE_URL=http://localhost:11434

# 6. Start API
agentic-brain serve

# 7. Open browser
open http://localhost:8000/docs
```

## Test It

```bash
# Health check
curl http://localhost:8000/health

# Chat test
agentic-brain chat --message "Hello!"

# Run tests
pytest tests/unit -v
```

## Next Steps

- **Full Guide:** [docs/MACOS_DEVELOPMENT.md](docs/MACOS_DEVELOPMENT.md)
- **API Docs:** http://localhost:8000/docs
- **Main README:** [README.md](README.md)

## Common Commands

```bash
# Activate venv
source .venv/bin/activate

# Start API with hot reload
uvicorn agentic_brain.api.main:app --reload

# Run tests
pytest tests/ -v

# Format code
black src/ tests/

# Start services (Docker)
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

## Troubleshooting

**Port 8000 in use?**
```bash
lsof -i :8000
# Note the PID, then: kill -9 <PID>
```

**Ollama not responding?**
```bash
brew services restart ollama
ollama pull llama3.2
```

**Import errors?**
```bash
pip install -e .
```

---

**Need help?** Check [docs/MACOS_DEVELOPMENT.md](docs/MACOS_DEVELOPMENT.md) for complete guide.
