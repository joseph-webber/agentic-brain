#!/usr/bin/env bash
# ============================================================================
# Docker Dev Script - Start development environment
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Agentic Brain - Dev Environment   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo

cd "$PROJECT_ROOT"

# Parse arguments
BUILD=false
DETACH=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --build)
      BUILD=true
      shift
      ;;
    --detach|-d)
      DETACH=true
      shift
      ;;
    --stop)
      echo -e "${YELLOW}→ Stopping services...${NC}"
      docker compose down
      echo -e "${GREEN}✓ Services stopped${NC}"
      exit 0
      ;;
    --logs)
      docker compose logs -f
      exit 0
      ;;
    --status)
      docker compose ps
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Usage: $0 [--build] [--detach|-d] [--stop] [--logs] [--status]"
      exit 1
      ;;
  esac
done

# Check for .env file
if [ ! -f .env ]; then
  echo -e "${YELLOW}⚠ No .env file found${NC}"
  if [ -f .env.example ]; then
    echo -e "${BLUE}→ Creating .env from .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env file${NC}"
    echo -e "${YELLOW}⚠ Please review and update .env with your settings${NC}"
  fi
fi

# Build if requested
if [ "$BUILD" = true ]; then
  echo -e "${BLUE}→ Building images...${NC}"
  docker compose build
fi

# Start services
echo -e "${BLUE}→ Starting services...${NC}"
if [ "$DETACH" = true ]; then
  docker compose up -d
  
  # Wait for health checks
  echo -e "${YELLOW}→ Waiting for services to be healthy...${NC}"
  sleep 5
  docker compose ps
  
  echo
  echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║   Services Started!                  ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
  echo
  echo -e "${BLUE}Services:${NC}"
  echo "  • Agentic Brain API: http://localhost:8000"
  echo "  • Neo4j Browser:     http://localhost:7474"
  echo "  • Redis:             localhost:6379"
  echo "  • Redpanda:          localhost:9092"
  echo "  • Firebase UI:       http://localhost:4000"
  echo
  echo -e "${YELLOW}View logs:${NC} docker compose logs -f"
  echo -e "${YELLOW}Stop:${NC}      docker compose down"
else
  docker compose up
fi
