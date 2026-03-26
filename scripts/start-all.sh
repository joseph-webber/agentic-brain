#!/usr/bin/env bash
set -e

echo "🚀 Starting agentic-brain infrastructure..."
echo ""

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}📂 Working directory: ${SCRIPT_DIR}${NC}"
cd "$SCRIPT_DIR"

# === Check Docker Daemon ===
echo ""
echo -e "${BLUE}1️⃣  Checking Docker daemon...${NC}"
if ! docker ps > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker daemon is not running${NC}"
    echo "  Start Docker Desktop on Mac and try again"
    exit 1
fi
echo -e "${GREEN}✓ Docker daemon is running${NC}"

# === Check/Start Redis ===
echo ""
echo -e "${BLUE}2️⃣  Checking Redis...${NC}"
if docker ps | grep -q redis-brain; then
    echo -e "${GREEN}✓ Redis is already running (redis-brain)${NC}"
else
    if docker ps -a | grep -q redis-brain; then
        echo "  Starting existing redis-brain container..."
        docker start redis-brain > /dev/null
        sleep 2
    else
        echo "  Creating redis-brain container..."
        docker run -d \
            --name redis-brain \
            -p 6379:6379 \
            --restart always \
            redis:alpine > /dev/null
        sleep 2
    fi
    echo -e "${GREEN}✓ Redis started (port 6379)${NC}"
fi

# === Check/Start Neo4j ===
echo ""
echo -e "${BLUE}3️⃣  Checking Neo4j...${NC}"
if docker ps | grep -q neo4j-brain; then
    echo -e "${GREEN}✓ Neo4j is already running (neo4j-brain)${NC}"
else
    if docker ps -a | grep -q neo4j-brain; then
        echo "  Starting existing neo4j-brain container..."
        docker start neo4j-brain > /dev/null
        sleep 5
    else
        echo "  Creating neo4j-brain container..."
        docker run -d \
            --name neo4j-brain \
            -p 7474:7474 \
            -p 7687:7687 \
            --restart always \
            -e NEO4J_AUTH=none \
            -e NEO4J_PLUGINS='["apoc"]' \
            neo4j:latest > /dev/null
        sleep 5
    fi
    echo -e "${GREEN}✓ Neo4j started (ports 7474/7687)${NC}"
fi

# === Docker Compose Up ===
echo ""
echo -e "${BLUE}4️⃣  Starting docker-compose services...${NC}"
if [ -f docker-compose.yml ]; then
    docker-compose up -d 2>/dev/null || true
    sleep 5
    echo -e "${GREEN}✓ Docker Compose services started${NC}"
else
    echo -e "${YELLOW}⚠ docker-compose.yml not found, skipping Docker Compose${NC}"
fi

# === Health Checks ===
echo ""
echo -e "${BLUE}5️⃣  Verifying health checks...${NC}"

# Redis health
echo -n "  Checking Redis... "
if docker exec redis-brain redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC} (may still be starting)"
fi

# Neo4j health
echo -n "  Checking Neo4j... "
if curl -s http://localhost:7474 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC} (may still be starting)"
fi

# === Summary ===
echo ""
echo "=========================================="
echo -e "${GREEN}✅ Infrastructure is running!${NC}"
echo "=========================================="
echo ""
echo "Services available at:"
echo -e "  ${BLUE}Redis${NC}:        redis://localhost:6379"
echo -e "  ${BLUE}Neo4j HTTP${NC}:   http://localhost:7474"
echo -e "  ${BLUE}Neo4j Bolt${NC}:   bolt://localhost:7687"
echo -e "  ${BLUE}API${NC}:          http://localhost:8000 (after 'make up')"
echo ""
echo "Next steps:"
echo "  • Make:     cd $(dirname $SCRIPT_DIR) && make install"
echo "  • Test:     make test"
echo "  • Start API: make up"
echo "  • Logs:     make logs"
echo "=========================================="
echo ""

exit 0
