# ✅ macOS Developer Checklist

**Quick reference for setting up Agentic Brain development on macOS**

---

## Initial Setup (One-time)

### System Prerequisites

- [ ] macOS 11+ installed
- [ ] At least 8GB RAM (16GB recommended)
- [ ] 5GB free disk space
- [ ] Xcode Command Line Tools installed: `xcode-select --install`

### Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

- [ ] Homebrew installed
- [ ] Added to PATH (check: `brew --version`)

### Install Core Tools

```bash
brew install python@3.11 git
```

- [ ] Python 3.11+ installed (check: `python3 --version`)
- [ ] Git installed (check: `git --version`)

### Install Optional Tools

```bash
# Docker alternative (lightweight)
brew install colima docker docker-compose

# Node.js (for docs)
brew install node@20

# Development tools
brew install redis postgresql@15 jq htop

# IDE (choose one)
brew install --cask visual-studio-code  # OR
brew install --cask pycharm-ce
```

- [ ] Docker/Colima installed (if using containers)
- [ ] IDE installed (VS Code or PyCharm)
- [ ] Redis CLI installed (optional)

---

## Project Setup

### Clone & Install

```bash
# Clone repository
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# Run automated setup
./setup.sh -i

# OR manual setup:
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e ".[dev,api,llm,memory]"
```

- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Can activate venv: `source .venv/bin/activate`

### Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit with your settings
nano .env  # or code .env
```

**Required settings:**

- [ ] `DEFAULT_LLM_PROVIDER` set (ollama, openai, groq, etc.)
- [ ] LLM API key configured (if not using Ollama)
- [ ] `API_HOST` and `API_PORT` set

**Optional settings:**

- [ ] Neo4j credentials (if using graph database)
- [ ] Redis URL (if using cache)
- [ ] Auth settings (if enabling authentication)

### Install Ollama (Local LLM)

```bash
brew install ollama
brew services start ollama
ollama pull llama3.2
```

- [ ] Ollama installed
- [ ] Service running (check: `curl http://localhost:11434/api/tags`)
- [ ] Model downloaded

---

## Verify Installation

### Quick Tests

```bash
# Activate venv
source .venv/bin/activate

# Check health
agentic-brain health

# Test chat
agentic-brain chat --message "Hello!"

# Run unit tests
pytest tests/unit -v

# Check API
curl http://localhost:8000/health
```

- [ ] Health check passes
- [ ] Chat responds
- [ ] Unit tests pass
- [ ] Can import package: `python -c "import agentic_brain"`

---

## Development Tools Setup

### VS Code

**Extensions to install:**

- [ ] Python (ms-python.python)
- [ ] Pylance (ms-python.vscode-pylance)
- [ ] Black Formatter (ms-python.black-formatter)
- [ ] Ruff (charliermarsh.ruff)
- [ ] Docker (ms-azuretools.vscode-docker)
- [ ] GitLens (eamodio.gitlens)

**Settings (.vscode/settings.json):**

- [ ] Python interpreter set to `.venv/bin/python`
- [ ] Format on save enabled
- [ ] Linting enabled

### PyCharm

- [ ] Interpreter configured (File → Settings → Project → Python Interpreter)
- [ ] Docker plugin enabled (if using containers)
- [ ] pytest as test runner

### Pre-commit Hooks

```bash
pre-commit install
pre-commit run --all-files
```

- [ ] Pre-commit hooks installed
- [ ] All hooks pass

---

## Services (Optional)

### Neo4j

**Option 1: Homebrew**
```bash
brew install neo4j
neo4j start
```

**Option 2: Docker**
```bash
docker run -d --name neo4j-dev \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.15-community
```

- [ ] Neo4j running
- [ ] Can access: http://localhost:7474
- [ ] Bolt connection works: `bolt://localhost:7687`

### Redis

**Option 1: Homebrew**
```bash
brew services start redis
```

**Option 2: Docker**
```bash
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine
```

- [ ] Redis running
- [ ] Can connect: `redis-cli ping` → PONG

### Redpanda (Docker only)

```bash
docker run -d --name redpanda-dev \
  -p 9092:9092 -p 9644:9644 \
  redpandadata/redpanda:latest \
  redpanda start --smp 1
```

- [ ] Redpanda running
- [ ] Health check passes: `docker exec redpanda-dev rpk cluster health`

### Docker Compose (All services)

```bash
docker-compose -f docker-compose.dev.yml up -d
```

- [ ] All services started
- [ ] Can view logs: `docker-compose logs -f`

---

## Daily Development

### Start Day

- [ ] Activate venv: `source .venv/bin/activate`
- [ ] Update code: `git pull`
- [ ] Update deps (if needed): `pip install -e ".[dev]"`
- [ ] Start services: `docker-compose -f docker-compose.dev.yml up -d`
- [ ] Start API: `uvicorn agentic_brain.api.main:app --reload`

### Before Committing

- [ ] Format code: `black src/ tests/`
- [ ] Lint: `ruff check --fix src/ tests/`
- [ ] Type check: `mypy src/`
- [ ] Run tests: `pytest tests/unit -v`
- [ ] Pre-commit hooks pass

### Before Pushing

- [ ] All tests pass: `pytest tests/`
- [ ] Coverage adequate: `pytest --cov=agentic_brain --cov-fail-under=80`
- [ ] Build succeeds: `python -m build`
- [ ] No security issues: `bandit -r src/`

---

## Troubleshooting

### Common Issues

**Can't activate venv:**
```bash
# Recreate it
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Import errors:**
```bash
pip install -e .
python -c "import agentic_brain; print(agentic_brain.__version__)"
```

**Port 8000 in use:**
```bash
lsof -i :8000
# Note PID, then kill it
```

**Ollama not responding:**
```bash
brew services restart ollama
ollama pull llama3.2
curl http://localhost:11434/api/tags
```

**Neo4j connection failed:**
```bash
neo4j status
neo4j start
cypher-shell -u neo4j -p password "RETURN 1;"
```

**Redis connection failed:**
```bash
brew services start redis
redis-cli ping
```

---

## Performance (M1/M2/M3/M4)

### Enable MLX GPU Acceleration

```bash
pip install mlx
export USE_MLX=true
export MLX_DEVICE=gpu
```

- [ ] MLX installed
- [ ] GPU available: `python -c "import mlx.core as mx; print(mx.metal.is_available())"`

### Monitor Performance

```bash
# GPU usage
sudo powermetrics --samplers gpu_power -i 1000

# Memory
htop

# Process monitoring
top
```

---

## Resources

- **Main README:** [README.md](README.md)
- **Full Developer Guide:** [docs/MACOS_DEVELOPMENT.md](docs/MACOS_DEVELOPMENT.md)
- **Quick Start:** [QUICK_START_MACOS.md](QUICK_START_MACOS.md)
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **API Docs:** http://localhost:8000/docs

---

## Help & Support

- **GitHub Issues:** https://github.com/joseph-webber/agentic-brain/issues
- **Discussions:** https://github.com/joseph-webber/agentic-brain/discussions
- **Discord:** https://discord.gg/agentic-brain

---

**Last Updated:** 2026-03-26
