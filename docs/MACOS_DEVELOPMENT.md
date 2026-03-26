# 🍎 macOS Development Guide for Agentic Brain

**Complete setup and development guide for macOS (Intel & Apple Silicon M1/M2/M3/M4)**

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Development Environment](#development-environment)
4. [Running Services](#running-services)
5. [Development Workflow](#development-workflow)
6. [Testing](#testing)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Demo & Production Deployment](#demo--production-deployment)
9. [Troubleshooting](#troubleshooting)
10. [Performance Optimization](#performance-optimization)

---

## Prerequisites

### System Requirements

**macOS Version:**
- macOS 11 (Big Sur) or later
- macOS 12 (Monterey) recommended for M1/M2/M3
- macOS 13 (Ventura) or later for M3 Max/Ultra

**Hardware:**
- **RAM:** 8GB minimum, 16GB recommended
- **Storage:** 5GB free space for dependencies
- **Apple Silicon (M1-M4):** Full MLX GPU acceleration support
- **Intel:** Standard performance, no GPU acceleration

### Install Homebrew

```bash
# If you don't have Homebrew installed:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Add to PATH (Apple Silicon):
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Add to PATH (Intel):
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/usr/local/bin/brew shellenv)"
```

### Install Core Dependencies

```bash
# Python 3.11 or later (REQUIRED)
brew install python@3.11

# Verify Python version
python3 --version  # Should be 3.11.x or higher

# Git (if not already installed)
brew install git

# Optional but recommended: pyenv for managing Python versions
brew install pyenv
pyenv install 3.11.9
pyenv global 3.11.9

# Docker Desktop alternative: Colima (lightweight, no GUI)
brew install colima docker docker-compose

# Start Colima (if using)
colima start --cpu 4 --memory 8 --disk 50

# Verify Docker is working
docker --version
docker ps
```

### Install Optional Tools

```bash
# Node.js (if working on frontend/docs)
brew install node@20

# PostgreSQL client (for database tools)
brew install postgresql@15

# Redis CLI (for cache debugging)
brew install redis

# jq (JSON processor for debugging)
brew install jq

# htop (system monitoring)
brew install htop

# VS Code (recommended IDE)
brew install --cask visual-studio-code

# PyCharm Community Edition
brew install --cask pycharm-ce
```

---

## Quick Start (5 Minutes)

### 1. Clone Repository

```bash
# Clone via HTTPS
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain

# OR clone via SSH
git clone git@github.com:joseph-webber/agentic-brain.git
cd agentic-brain
```

### 2. Run Automated Setup

**Option A: Using setup script (RECOMMENDED)**

```bash
# Make script executable
chmod +x setup.sh

# Run full installation
./setup.sh -i

# This will:
# - Create Python virtual environment
# - Install all dependencies
# - Create .env from .env.example
# - Set up pre-commit hooks
# - Validate installation
```

**Option B: Manual setup**

```bash
# Create virtual environment
python3.11 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install in development mode with all extras
pip install -e ".[dev,api,llm,memory,redis,docs]"

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env  # or vim .env, or code .env
```

### 3. Configure Environment

**Minimal configuration for local development:**

```bash
# Edit .env file
nano .env

# Add at minimum:
# -----------------

# LLM Provider (choose ONE):
# Option 1: Local Ollama (free, private)
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_LLM_MODEL=llama3.2

# Option 2: OpenAI (paid, best quality)
OPENAI_API_KEY=sk-your-key-here
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o

# Option 3: Groq (free tier, fastest)
GROQ_API_KEY=your-groq-key
DEFAULT_LLM_PROVIDER=groq
DEFAULT_LLM_MODEL=llama-3.1-8b-instant

# Neo4j (optional - chat works without it!)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# API Server
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Session Storage (use memory for dev)
SESSION_BACKEND=memory

# Authentication (disabled for dev)
AUTH_ENABLED=false
```

### 4. Start Services (Optional)

**If using Neo4j, Redis, or Redpanda:**

```bash
# First, copy the environment template
cp .env.dev.example .env.dev

# Option A: Docker Compose (all services) - RECOMMENDED
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml up -d

# Option B: Individual services via Homebrew
# Neo4j
brew install neo4j
neo4j start

# Redis
brew services start redis

# Redpanda (Kafka alternative)
# Use Docker for Redpanda - no Homebrew formula
docker run -d --name redpanda \
  -p 9092:9092 -p 9644:9644 \
  redpandadata/redpanda:latest \
  redpanda start --smp 1
```

### 5. Install Ollama (Local LLM - RECOMMENDED)

```bash
# Download and install Ollama
brew install ollama

# Start Ollama service
brew services start ollama

# Pull a model
ollama pull llama3.2

# Verify it's working
curl http://localhost:11434/api/tags
```

### 6. Run the Application

```bash
# Activate virtual environment (if not already)
source .venv/bin/activate

# Start the API server
agentic-brain serve

# OR use uvicorn directly for hot reload
uvicorn agentic_brain.api.main:app --reload --host 0.0.0.0 --port 8000

# Access the application:
# - API:     http://localhost:8000
# - Docs:    http://localhost:8000/docs
# - Health:  http://localhost:8000/health
```

### 7. Verify Installation

```bash
# Run quick smoke test
agentic-brain health

# Run basic chat test (if LLM configured)
agentic-brain chat --message "Hello, are you working?"

# Run unit tests
pytest tests/unit -v

# Check API is responding
curl http://localhost:8000/health | jq
```

**🎉 You're ready to develop!**

---

## Development Environment

### IDE Setup

#### Visual Studio Code

```bash
# Install VS Code
brew install --cask visual-studio-code

# Open project
code .

# Recommended extensions (install via Extensions panel):
# - Python (ms-python.python)
# - Pylance (ms-python.vscode-pylance)
# - Black Formatter (ms-python.black-formatter)
# - Ruff (charliermarsh.ruff)
# - Docker (ms-azuretools.vscode-docker)
# - GitLens (eamodio.gitlens)
# - REST Client (humao.rest-client)
# - YAML (redhat.vscode-yaml)
```

**Recommended VS Code settings** (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": [
    "tests"
  ],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.tabSize": 4
  }
}
```

#### PyCharm Professional/Community

```bash
# Install PyCharm Community
brew install --cask pycharm-ce

# OR PyCharm Professional (paid)
brew install --cask pycharm

# Open project
open -a PyCharm agentic-brain

# Configure interpreter:
# 1. File → Settings → Project → Python Interpreter
# 2. Click gear icon → Add → Existing Environment
# 3. Select: /path/to/agentic-brain/.venv/bin/python
```

### Virtual Environment Management

**Activate/Deactivate:**

```bash
# Activate
source .venv/bin/activate

# Check active Python
which python3
# Should show: /path/to/agentic-brain/.venv/bin/python3

# Deactivate
deactivate
```

**Recreate if corrupted:**

```bash
# Remove old venv
rm -rf .venv

# Create new one
python3.11 -m venv .venv

# Activate and reinstall
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e ".[dev,api,llm,memory]"
```

### Environment Variables

**Environment profiles:**

| File | Purpose |
|------|---------|
| `.env.example` | Template with all options |
| `.env.dev` | Development defaults |
| `.env.test` | Test environment |
| `.env.prod` | Production settings |
| `.env.docker` | Docker deployment |
| `.env` | Your local config (gitignored) |

**Loading different profiles:**

```bash
# Development (default)
cp .env.dev .env

# Testing
cp .env.test .env

# Switch at runtime
export ENVIRONMENT=test
agentic-brain serve

# Or pass directly
ENVIRONMENT=prod agentic-brain serve
```

### Hot Reload Development

**API Development with auto-reload:**

```bash
# Start with hot reload (auto-restart on code changes)
uvicorn agentic_brain.api.main:app \
  --reload \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level debug

# Watch for changes in specific directories
uvicorn agentic_brain.api.main:app \
  --reload \
  --reload-dir src/agentic_brain/api \
  --reload-dir src/agentic_brain/agents
```

**Alternative: Use watchdog for custom scripts:**

```bash
# Install watchdog
pip install watchdog[watchmedo]

# Auto-run tests on file change
watchmedo shell-command \
  --patterns="*.py" \
  --recursive \
  --command='pytest tests/unit' \
  src/
```

---

## Running Services

### Neo4j (Graph Database)

**Option 1: Homebrew (Native, better performance)**

```bash
# Install
brew install neo4j

# Start service
neo4j start

# Stop service
neo4j stop

# Access browser: http://localhost:7474
# Default credentials: neo4j/neo4j (change on first login)

# Connect via Bolt: bolt://localhost:7687
```

**Option 2: Docker (Isolated, easier cleanup)**

```bash
# Run Neo4j in Docker
docker run -d \
  --name neo4j-dev \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  -e NEO4J_PLUGINS='["apoc"]' \
  -v neo4j_data:/data \
  neo4j:5.15-community

# View logs
docker logs -f neo4j-dev

# Stop and remove
docker stop neo4j-dev && docker rm neo4j-dev
```

**Neo4j Configuration:**

```bash
# Edit Neo4j config (Homebrew)
code /opt/homebrew/etc/neo4j/neo4j.conf

# Increase memory for development
dbms.memory.heap.initial_size=512m
dbms.memory.heap.max_size=2G
dbms.memory.pagecache.size=1G

# Enable APOC procedures
dbms.security.procedures.unrestricted=apoc.*
```

### Redis (Cache & Session Store)

**Option 1: Homebrew**

```bash
# Install
brew install redis

# Start as service (auto-start on boot)
brew services start redis

# OR run in foreground
redis-server

# Test connection
redis-cli ping
# Should respond: PONG

# Stop service
brew services stop redis
```

**Option 2: Docker**

```bash
# Run Redis in Docker
docker run -d \
  --name redis-dev \
  -p 6379:6379 \
  redis:7-alpine \
  redis-server --requirepass your-password

# Connect with CLI
docker exec -it redis-dev redis-cli -a your-password

# Stop and remove
docker stop redis-dev && docker rm redis-dev
```

**Redis CLI commands:**

```bash
# Connect
redis-cli -a your-password

# Check keys
KEYS *

# Get value
GET mykey

# Monitor all commands (debugging)
MONITOR

# Get info
INFO

# Flush all data (DANGER!)
FLUSHALL
```

### Redpanda (Kafka Alternative)

**Docker Only (no Homebrew formula):**

```bash
# Run Redpanda
docker run -d \
  --name redpanda-dev \
  -p 9092:9092 \
  -p 9644:9644 \
  redpandadata/redpanda:latest \
  redpanda start \
    --smp 1 \
    --memory 1G \
    --overprovisioned \
    --kafka-addr PLAINTEXT://0.0.0.0:9092 \
    --advertise-kafka-addr PLAINTEXT://localhost:9092

# Check cluster health
docker exec -it redpanda-dev rpk cluster health

# Create topic
docker exec -it redpanda-dev rpk topic create brain.events

# List topics
docker exec -it redpanda-dev rpk topic list

# Produce test message
echo "test message" | docker exec -i redpanda-dev rpk topic produce brain.events

# Consume messages
docker exec -it redpanda-dev rpk topic consume brain.events

# Stop and remove
docker stop redpanda-dev && docker rm redpanda-dev
```

### Docker Compose (All Services)

**Start all services at once:**

```bash
# Copy environment template (first time only)
cp .env.dev.example .env.dev

# Development mode (with hot reload)
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml up -d

# View logs
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml logs -f

# Check status
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml ps

# Stop all
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml down

# Stop and remove volumes (fresh start)
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml down -v
```

**Service URLs:**

- **Agentic Brain API:** http://localhost:8000
- **Neo4j Browser:** http://localhost:7474
- **Neo4j Bolt:** bolt://localhost:7687
- **Redis:** localhost:6379
- **Redpanda:** localhost:9092
- **Redpanda Admin:** http://localhost:9644

---

## Development Workflow

### Daily Development

```bash
# 1. Start your day
cd ~/brain/agentic-brain
source .venv/bin/activate

# 2. Update dependencies (if needed)
git pull
pip install -e ".[dev]"

# 3. Start services (if using Docker)
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml up -d

# 4. Start API with hot reload
uvicorn agentic_brain.api.main:app --reload

# 5. Open new terminal for testing
source .venv/bin/activate
pytest tests/unit -v --tb=short

# 6. Make changes, save, tests auto-run (with watchdog)

# 7. Commit your work
git add .
git commit -m "feat: add awesome feature"
git push
```

### Code Quality Tools

**Format code with Black:**

```bash
# Format all Python files
black src/ tests/

# Check what would be formatted (dry-run)
black --check src/ tests/

# Format single file
black src/agentic_brain/api/main.py
```

**Lint with Ruff:**

```bash
# Check all files
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/

# Check single file
ruff check src/agentic_brain/agents/base.py
```

**Type checking with mypy:**

```bash
# Check all files
mypy src/

# Check specific module
mypy src/agentic_brain/api/

# Ignore missing imports (for third-party libs)
mypy --ignore-missing-imports src/
```

**Pre-commit hooks:**

```bash
# Install pre-commit hooks (auto-runs before each commit)
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate

# Skip hooks for a commit (not recommended)
git commit --no-verify -m "skip hooks"
```

### Running Tests

**Unit tests (fast, no external services):**

```bash
# Run all unit tests
pytest tests/unit -v

# Run with coverage
pytest tests/unit --cov=agentic_brain --cov-report=html

# Run specific test file
pytest tests/unit/test_agents.py -v

# Run specific test
pytest tests/unit/test_agents.py::test_agent_creation -v

# Run in parallel (faster)
pytest tests/unit -n auto
```

**Integration tests (requires services):**

```bash
# Start services first
docker compose --env-file .env.dev -f docker/docker-compose.dev.yml up -d

# Run integration tests
pytest tests/integration -v -m integration

# Run with specific service
pytest tests/integration -v -m requires_neo4j
```

**E2E tests:**

```bash
# Run end-to-end tests
pytest tests/e2e -v -m e2e

# Skip slow tests
pytest tests/e2e -v -m "e2e and not slow"
```

### Debugging

**Python debugger (pdb):**

```python
# Add to your code
import pdb; pdb.set_trace()

# Or use breakpoint() (Python 3.7+)
breakpoint()
```

**VS Code debugging:**

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Agentic Brain API",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "agentic_brain.api.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000"
      ],
      "jinja": true,
      "justMyCode": false
    },
    {
      "name": "Python: Current Test",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": [
        "${file}",
        "-v"
      ],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

**API Request debugging:**

```bash
# Test with curl
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "session_id": "test-123"}'

# Test with HTTPie (prettier)
brew install httpie
http POST localhost:8000/api/v1/chat message="Hello!" session_id="test-123"

# Interactive API docs
open http://localhost:8000/docs
```

---

## Testing

### Test Organization

```
tests/
├── unit/              # Fast, no external deps
│   ├── test_agents.py
│   ├── test_llm.py
│   └── test_tools.py
├── integration/       # Requires services (Neo4j, Redis)
│   ├── test_neo4j_pool.py
│   ├── test_redis_cache.py
│   └── test_api_endpoints.py
├── e2e/              # Full system tests
│   └── test_user_workflows.py
└── conftest.py       # Shared fixtures
```

### Test Commands

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=agentic_brain --cov-report=html --cov-report=term

# Open coverage report in browser
open htmlcov/index.html

# Run only unit tests (fast)
pytest tests/unit -v

# Run only integration tests
pytest tests/integration -v -m integration

# Run tests matching pattern
pytest -k "test_agent" -v

# Run with live logging (see print statements)
pytest -v -s --log-cli-level=INFO

# Run in parallel (4 workers)
pytest -n 4

# Stop on first failure
pytest -x

# Re-run only failed tests
pytest --lf

# Show slowest 10 tests
pytest --durations=10
```

### Writing Tests

**Example unit test:**

```python
# tests/unit/test_example.py
import pytest
from agentic_brain.agents import Agent

def test_agent_creation():
    """Test that agent can be created with minimal config."""
    agent = Agent(name="TestAgent")
    assert agent.name == "TestAgent"
    assert agent.llm_provider is not None

def test_agent_responds():
    """Test that agent can generate a response."""
    agent = Agent(name="TestAgent")
    response = agent.run("Hello!")
    assert response is not None
    assert len(response) > 0

@pytest.mark.asyncio
async def test_async_agent():
    """Test async agent execution."""
    agent = Agent(name="AsyncAgent")
    response = await agent.arun("Hello!")
    assert response is not None
```

**Example integration test:**

```python
# tests/integration/test_neo4j.py
import pytest
from agentic_brain.database.neo4j_pool import Neo4jConnectionPool

@pytest.mark.requires_neo4j
def test_neo4j_connection(neo4j_pool):
    """Test Neo4j connection."""
    with neo4j_pool.get_session() as session:
        result = session.run("RETURN 1 as num")
        record = result.single()
        assert record["num"] == 1

@pytest.mark.requires_neo4j
def test_create_node(neo4j_pool):
    """Test creating a node in Neo4j."""
    with neo4j_pool.get_session() as session:
        session.run(
            "CREATE (n:TestNode {name: $name})",
            name="test"
        )
        result = session.run(
            "MATCH (n:TestNode {name: $name}) RETURN n",
            name="test"
        )
        assert result.single() is not None
```

---

## CI/CD Pipeline

### GitHub Actions Workflows

The project uses GitHub Actions for continuous integration and deployment:

| Workflow | File | Purpose |
|----------|------|---------|
| **CI** | `.github/workflows/ci.yml` | Tests, linting, security |
| **CD** | `.github/workflows/cd.yml` | Build and publish packages |
| **Docker** | `.github/workflows/docker-publish.yml` | Build container images |
| **Docs** | `.github/workflows/docs.yml` | Deploy documentation |
| **Release** | `.github/workflows/release.yml` | Create GitHub releases |

### Running Tests Locally (Match CI)

**Simulate CI environment:**

```bash
# Set CI environment variable
export CI=true
export GITHUB_ACTIONS=true

# Run full test suite like CI
pytest tests/ -v --cov=agentic_brain --cov-report=xml --cov-report=term

# Run with same markers as CI
pytest tests/ -v \
  -m "not skip_ci" \
  --ignore=tests/e2e \
  --maxfail=5

# Check code formatting
black --check src/ tests/

# Run linter
ruff check src/ tests/

# Type checking
mypy src/

# Security checks
pip install bandit safety
bandit -r src/
safety check
```

### Understanding CI Workflow

**CI Pipeline stages:**

1. **Checkout:** Clone repository
2. **Setup Python:** Install Python 3.11/3.12/3.13
3. **Install Dependencies:** `pip install -e ".[test]"`
4. **Run Linters:** Black, Ruff, mypy
5. **Run Tests:** pytest with coverage
6. **Upload Coverage:** Codecov (if configured)
7. **Security Scan:** Bandit, Safety
8. **Build Package:** `python -m build`

**View CI logs:**

```bash
# Install GitHub CLI
brew install gh

# Authenticate
gh auth login

# View recent workflow runs
gh run list

# View specific run
gh run view <run-id>

# Watch a run in real-time
gh run watch

# View logs for failed run
gh run view <run-id> --log-failed
```

### Debugging CI Failures

**Common issues and fixes:**

**1. Tests pass locally, fail in CI:**

```bash
# Run in clean environment
docker run -it --rm \
  -v $(pwd):/app \
  -w /app \
  python:3.11 \
  /bin/bash

# Inside container:
pip install -e ".[test]"
pytest tests/
```

**2. Import errors in CI:**

```bash
# Ensure package is installed properly
pip install -e .

# Check installed packages
pip list | grep agentic-brain

# Verify package structure
python -c "import agentic_brain; print(agentic_brain.__version__)"
```

**3. Timeout errors:**

```bash
# Add timeout to slow tests
@pytest.mark.timeout(60)
def test_slow_operation():
    pass

# Or skip in CI
@pytest.mark.skip_ci
def test_slow_integration():
    pass
```

**4. Environment variable issues:**

```bash
# Add to .github/workflows/ci.yml
env:
  NEO4J_URI: bolt://localhost:7687
  NEO4J_USER: neo4j
  NEO4J_PASSWORD: test-password
  REDIS_URL: redis://localhost:6379
```

### Pre-push Checklist

```bash
# Run this before pushing to avoid CI failures

# 1. Format code
black src/ tests/

# 2. Lint
ruff check --fix src/ tests/

# 3. Type check
mypy src/

# 4. Run tests
pytest tests/unit tests/integration -v

# 5. Check coverage
pytest --cov=agentic_brain --cov-report=term --cov-fail-under=80

# 6. Security scan
bandit -r src/

# 7. Build package
python -m build

# 8. Test installation
pip install dist/*.whl --force-reinstall

# 9. All good? Push!
git push
```

---

## Demo & Production Deployment

### Local Demo Mode

**Run a production-like demo locally:**

```bash
# 1. Use production config
cp .env.prod .env

# 2. Start all services
docker compose -f docker-compose.yml up -d

# 3. Initialize database
agentic-brain db init

# 4. Create demo data
agentic-brain demo seed

# 5. Start API in production mode
gunicorn agentic_brain.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000

# 6. Test it
curl http://localhost:8000/health

# 7. Stop demo
docker compose -f docker-compose.yml down
```

### GitHub Pages Deployment

**Documentation is auto-deployed on push to main:**

```bash
# Build docs locally to preview
mkdocs serve

# Open http://127.0.0.1:8000

# Build static site
mkdocs build

# Deploy manually (if needed)
mkdocs gh-deploy --force
```

**GitHub Pages URL:** https://joseph-webber.github.io/agentic-brain/

### Production Deployment Options

**1. Docker Deployment:**

```bash
# Build production image
docker build -t agentic-brain:latest .

# Run with docker compose
docker compose -f docker-compose.yml up -d

# View logs
docker compose logs -f agentic-brain
```

**2. Render.com (One-Click):**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/joseph-webber/agentic-brain)

**3. Heroku:**

```bash
# Install Heroku CLI
brew install heroku/brew/heroku

# Login
heroku login

# Create app
heroku create my-agentic-brain

# Set environment variables
heroku config:set OPENAI_API_KEY=sk-xxx
heroku config:set NEO4J_URI=bolt://...

# Deploy
git push heroku main

# Open app
heroku open
```

**4. Kubernetes (Advanced):**

```bash
# Apply manifests
kubectl apply -f k8s/

# Check status
kubectl get pods -n agentic-brain

# View logs
kubectl logs -f deployment/agentic-brain -n agentic-brain

# Access service
kubectl port-forward svc/agentic-brain 8000:8000 -n agentic-brain
```

---

## Troubleshooting

### Common Issues

**1. Virtual environment not activating:**

```bash
# Ensure you're in project directory
cd ~/brain/agentic-brain

# Check if .venv exists
ls -la .venv/

# If not, create it
python3.11 -m venv .venv

# Try activating again
source .venv/bin/activate
```

**2. ImportError: No module named 'agentic_brain':**

```bash
# Install in editable mode
pip install -e .

# Verify installation
pip list | grep agentic-brain

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

**3. Neo4j connection refused:**

```bash
# Check if Neo4j is running
neo4j status

# Start Neo4j
neo4j start

# Test connection with cypher-shell
cypher-shell -u neo4j -p your-password "RETURN 1;"

# Check .env settings
grep NEO4J .env
```

**4. Redis connection errors:**

```bash
# Check if Redis is running
redis-cli ping

# Start Redis
brew services start redis

# Check port
lsof -i :6379

# Test connection
redis-cli -h localhost -p 6379 PING
```

**5. Ollama not responding:**

```bash
# Check if Ollama is running
pgrep ollama

# Start Ollama
brew services start ollama

# Test API
curl http://localhost:11434/api/tags

# Pull model if missing
ollama pull llama3.2

# Check logs
tail -f ~/.ollama/logs/server.log
```

**6. Port already in use:**

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
uvicorn agentic_brain.api.main:app --port 8001
```

**7. M1/M2/M3 specific issues:**

```bash
# Install Rosetta 2 if needed (for Intel-only packages)
softwareupdate --install-rosetta

# Use ARM64 Python
which python3
# Should show /opt/homebrew/bin/python3

# For ML libraries, use MLX instead of CUDA
pip install mlx
```

### Getting Help

**Check logs:**

```bash
# Application logs
tail -f logs/agentic-brain.log

# Docker logs
docker compose logs -f

# System logs
log show --predicate 'process == "python3"' --last 5m
```

**Enable debug logging:**

```bash
# Set in .env
LOG_LEVEL=DEBUG

# Or pass at runtime
LOG_LEVEL=DEBUG agentic-brain serve
```

**Report issues:**

1. Check [existing issues](https://github.com/joseph-webber/agentic-brain/issues)
2. Create new issue with:
   - macOS version
   - Python version
   - Error messages
   - Steps to reproduce

---

## Performance Optimization

### Apple Silicon (M1/M2/M3/M4)

**Enable MLX GPU acceleration:**

```bash
# Install MLX
pip install mlx

# Verify GPU is available
python -c "import mlx.core as mx; print(mx.metal.is_available())"

# Use MLX for embeddings
export USE_MLX=true
export MLX_DEVICE=gpu
```

**Monitor GPU usage:**

```bash
# Install powermetrics (built-in)
sudo powermetrics --samplers gpu_power -i 1000

# Or use Activity Monitor
open /System/Applications/Utilities/Activity\ Monitor.app
# View → GPU History
```

### Memory Management

**Optimize Python memory:**

```bash
# Use memory profiling
pip install memory-profiler

# Profile a function
python -m memory_profiler script.py

# Monitor memory usage
htop
# Or: top -pid <python_pid>
```

**Configure Neo4j memory:**

```bash
# Edit neo4j.conf
dbms.memory.heap.initial_size=1G
dbms.memory.heap.max_size=4G
dbms.memory.pagecache.size=2G

# Restart Neo4j
neo4j restart
```

### Database Performance

**Neo4j query optimization:**

```cypher
// Create indexes for common queries
CREATE INDEX user_email IF NOT EXISTS FOR (u:User) ON (u.email);
CREATE INDEX message_timestamp IF NOT EXISTS FOR (m:Message) ON (m.timestamp);

// Analyze query performance
PROFILE MATCH (u:User)-[:SENT]->(m:Message) RETURN u, m;

// Check index usage
CALL db.indexes();
```

**Redis optimization:**

```bash
# Configure Redis for performance
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Enable persistence if needed
redis-cli CONFIG SET save "900 1 300 10"
```

### API Performance

**Use gunicorn with multiple workers:**

```bash
# Calculate workers: (2 × CPU cores) + 1
# For M1/M2 with 8 cores: (2 × 8) + 1 = 17 workers

gunicorn agentic_brain.api.main:app \
  --workers 17 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 100
```

**Enable response caching:**

```python
# In .env
CACHE_BACKEND=redis
CACHE_TTL=3600
CACHE_REDIS_URL=redis://localhost:6379/0
```

---

## Additional Resources

### Documentation

- [Main README](../README.md)
- [API Documentation](https://joseph-webber.github.io/agentic-brain/)
- [Contributing Guide](../CONTRIBUTING.md)
- [Security Policy](../SECURITY.md)

### Community

- [GitHub Discussions](https://github.com/joseph-webber/agentic-brain/discussions)
- [Discord Server](https://discord.gg/agentic-brain)
- [Twitter/X](https://twitter.com/agentic_brain)

### External Tools

- [Homebrew](https://brew.sh) - Package manager
- [Ollama](https://ollama.ai) - Local LLM runner
- [Neo4j](https://neo4j.com) - Graph database
- [Redis](https://redis.io) - Cache & message broker
- [Redpanda](https://redpanda.com) - Kafka alternative
- [Docker](https://www.docker.com) - Containerization
- [Colima](https://github.com/abiosoft/colima) - Docker runtime

---

## Changelog

- **2026-03-26:** Initial macOS development guide
- Version tracked with main project releases

---

**Questions?** Open an [issue](https://github.com/joseph-webber/agentic-brain/issues) or start a [discussion](https://github.com/joseph-webber/agentic-brain/discussions).

**Ready to contribute?** See [CONTRIBUTING.md](../CONTRIBUTING.md).
