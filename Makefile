.PHONY: help install test lint format build up down logs health clean start stop restart

# Default target
help:
	@echo "agentic-brain infrastructure management"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Install & Development:"
	@echo "  install       - Install package in editable mode with all dependencies"
	@echo "  dev-install   - Install with dev/test dependencies"
	@echo "  all-install   - Install with ALL optional dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint          - Run ruff and mypy linting"
	@echo "  ruff          - Run ruff linting only"
	@echo "  mypy          - Run mypy type checking"
	@echo "  format        - Format code with black"
	@echo ""
	@echo "Testing:"
	@echo "  test          - Run pytest with coverage"
	@echo "  test-fast     - Run pytest without coverage"
	@echo "  test-watch    - Run pytest in watch mode"
	@echo ""
	@echo "Docker Management:"
	@echo "  build         - Build Docker image"
	@echo "  up            - Start all services (docker-compose up -d)"
	@echo "  down          - Stop all services (docker-compose down)"
	@echo "  logs          - View logs from all services (follow mode)"
	@echo "  logs-neo4j    - View Neo4j logs"
	@echo "  logs-redis    - View Redis logs"
	@echo "  logs-api      - View API logs"
	@echo ""
	@echo "Health & Monitoring:"
	@echo "  health        - Check all services health"
	@echo "  ps            - Show running containers"
	@echo ""
	@echo "Infrastructure:"
	@echo "  start-all     - Start Redis, Neo4j, and API server (Mac native + Docker)"
	@echo "  stop-all      - Stop all services"
	@echo "  restart       - Restart all services"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean         - Remove build artifacts, caches, and __pycache__"
	@echo "  clean-docker  - Remove stopped containers and unused images"
	@echo "  clean-all     - Full cleanup (code + Docker)"

# === Install Targets ===
install:
	pip install -e .

dev-install:
	pip install -e ".[dev,api,llm,memory,redis,observability]"

all-install:
	pip install -e ".[all]"

# === Linting & Formatting ===
lint: ruff mypy
	@echo "✓ All linting passed"

ruff:
	ruff check src/ tests/ --fix
	@echo "✓ Ruff check passed"

mypy:
	mypy src/ --ignore-missing-imports
	@echo "✓ MyPy check passed"

format:
	black src/ tests/
	@echo "✓ Code formatted with black"

# === Testing ===
test:
	pytest tests/ -v --cov=src/agentic_brain --cov-report=html --cov-report=term-missing

test-fast:
	pytest tests/ -v

test-watch:
	pytest-watch tests/ -v

# === Docker Targets ===
build:
	docker compose build 2>/dev/null || docker-compose build

up:
	@if [ -f docker-compose.yml ]; then \
		docker compose up -d 2>/dev/null || docker-compose up -d; \
		echo "Waiting for services to be healthy..."; \
		sleep 5; \
		make health; \
	else \
		echo "No docker-compose.yml found"; \
	fi

down:
	docker compose down 2>/dev/null || docker-compose down

logs:
	docker compose logs -f 2>/dev/null || docker-compose logs -f

logs-neo4j:
	docker logs -f neo4j-brain 2>/dev/null || echo "Neo4j container not running"

logs-redis:
	docker logs -f redis-brain 2>/dev/null || echo "Redis container not running"

logs-api:
	docker compose logs -f agentic-brain 2>/dev/null || docker-compose logs -f agentic-brain

ps:
	docker ps -f "name=brain" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"

# === Health Checks ===
health: .check-redis .check-neo4j .check-docker
	@echo "✓ All services healthy!"

.check-redis:
	@echo "Checking Redis..."
	@docker exec redis-brain redis-cli ping > /dev/null 2>&1 || \
	  docker exec agentic-brain-redis redis-cli ping > /dev/null 2>&1 || \
	  (echo "✗ Redis not responding"; exit 1)
	@echo "  ✓ Redis OK (port 6379)"

.check-neo4j:
	@echo "Checking Neo4j..."
	@curl -s http://localhost:7474 > /dev/null 2>&1 || \
	  (echo "✗ Neo4j not responding"; exit 1)
	@echo "  ✓ Neo4j OK (ports 7474/7687)"

.check-docker:
	@echo "Checking Docker daemon..."
	@docker ps > /dev/null 2>&1 || \
	  (echo "✗ Docker daemon not running"; exit 1)
	@echo "  ✓ Docker daemon running"

# === Infrastructure Management ===
start-all: up
	@echo ""
	@echo "=========================================="
	@echo "Infrastructure is running:"
	@echo "  Redis:   redis://localhost:6379"
	@echo "  Neo4j:   bolt://localhost:7687"
	@echo "  Browser: http://localhost:7474"
	@echo "  API:     http://localhost:8000"
	@echo "=========================================="

stop-all: down
	@echo "All services stopped"

restart: down up
	@echo "Services restarted"

# === Cleanup ===
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/
	@echo "✓ Code artifacts cleaned"

clean-docker:
	docker container prune -f
	docker image prune -f
	@echo "✓ Docker cleanup complete"

clean-all: clean clean-docker
	@echo "✓ Full cleanup complete"

# === Utility ===
.PHONY: .check-redis .check-neo4j .check-docker
