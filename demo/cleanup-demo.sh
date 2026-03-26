#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Agentic Brain Demo Cleanup                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Confirm cleanup
echo -e "${YELLOW}⚠️  This will remove all demo data and containers!${NC}"
echo -e "${YELLOW}   Press Ctrl+C to cancel, or Enter to continue...${NC}"
read

echo -e "\n${BLUE}▶ Stopping all demo containers...${NC}"
docker-compose -f docker-compose.demo.yml down -v

echo -e "\n${BLUE}▶ Removing demo volumes...${NC}"
docker volume rm agentic-brain_demo-db-data 2>/dev/null || true
docker volume rm agentic-brain_demo-wp-data 2>/dev/null || true
docker volume rm agentic-brain_demo-neo4j-data 2>/dev/null || true
docker volume rm agentic-brain_demo-neo4j-logs 2>/dev/null || true
docker volume rm agentic-brain_demo-redis-data 2>/dev/null || true
docker volume rm agentic-brain_demo-api-logs 2>/dev/null || true

echo -e "\n${BLUE}▶ Pruning unused Docker resources...${NC}"
docker system prune -f

echo -e "\n✅ ${BLUE}Cleanup complete!${NC}"
echo -e "   Run ${YELLOW}./setup-demo.sh${NC} to start fresh.\n"
