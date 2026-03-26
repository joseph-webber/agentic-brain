#!/usr/bin/env bash
# ============================================================================
# Docker Test Script - Run tests in Docker
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
echo -e "${BLUE}║   Agentic Brain - Docker Tests      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo

cd "$PROJECT_ROOT"

# Parse arguments
REBUILD=false
VERBOSE=false
DETACH=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --rebuild)
      REBUILD=true
      shift
      ;;
    --verbose|-v)
      VERBOSE=true
      shift
      ;;
    --detach|-d)
      DETACH=true
      shift
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Clean up any existing test containers
echo -e "${YELLOW}→ Cleaning up old test containers...${NC}"
docker compose -f docker-compose.test.yml down -v 2>/dev/null || true

# Build if requested
if [ "$REBUILD" = true ]; then
  echo -e "${BLUE}→ Rebuilding test image...${NC}"
  docker compose -f docker-compose.test.yml build
fi

# Start services
echo -e "${BLUE}→ Starting test services...${NC}"
docker compose -f docker-compose.test.yml up -d neo4j redis redpanda

# Wait for services to be healthy
echo -e "${YELLOW}→ Waiting for services to be ready...${NC}"
for service in neo4j redis redpanda; do
  echo -n "  Waiting for ${service}..."
  timeout=60
  until docker compose -f docker-compose.test.yml exec -T "$service" echo "ready" &>/dev/null || [ $timeout -eq 0 ]; do
    sleep 1
    ((timeout--))
  done
  if [ $timeout -eq 0 ]; then
    echo -e " ${RED}✗ timeout${NC}"
    docker compose -f docker-compose.test.yml logs "$service"
    exit 1
  fi
  echo -e " ${GREEN}✓${NC}"
done

# Run tests
echo -e "${BLUE}→ Running tests...${NC}"
echo

if [ "$DETACH" = true ]; then
  docker compose -f docker-compose.test.yml up -d test
  echo -e "${YELLOW}Tests running in background. Check logs with:${NC}"
  echo "  docker compose -f docker-compose.test.yml logs -f test"
else
  docker compose -f docker-compose.test.yml run --rm test || {
    echo -e "${RED}✗ Tests failed${NC}"
    docker compose -f docker-compose.test.yml down -v
    exit 1
  }
  
  echo
  echo -e "${GREEN}✓ All tests passed!${NC}"
fi

# Cleanup
if [ "$DETACH" = false ]; then
  echo -e "${YELLOW}→ Cleaning up...${NC}"
  docker compose -f docker-compose.test.yml down -v
fi

echo
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Tests Complete!                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
