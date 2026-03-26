#!/usr/bin/env bash
#
# Quick Setup - Get agentic-brain infrastructure bulletproof in 5 minutes
#
# This script sets up:
# 1. Health monitoring with auto-restart
# 2. Auto-start daemon
# 3. Docker Compose with healthchecks
# 4. Mac LaunchAgent (optional)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════╗"
echo "║  agentic-brain Infrastructure Setup        ║"
echo "║  Making it BULLETPROOF ✓                   ║"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Check dependencies
echo -e "${BLUE}Checking dependencies...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "  Install Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi
echo -e "${GREEN}✓ Docker${NC}: $(docker --version)"

if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}⚠ docker-compose not found${NC}"
    echo "  Note: Docker Desktop includes docker-compose"
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}⚠ Python 3 not found${NC}"
    echo "  This is optional but recommended"
else
    echo -e "${GREEN}✓ Python${NC}: $(python3 --version)"
fi

echo ""

# Create logs directory
echo -e "${BLUE}Setting up directories...${NC}"
mkdir -p "$SCRIPT_DIR/logs"
echo -e "${GREEN}✓ Logs directory: $SCRIPT_DIR/logs${NC}"

# Make daemon script executable
echo -e "${BLUE}Setting up scripts...${NC}"
chmod +x "$SCRIPT_DIR/scripts/infra-daemon.sh"
echo -e "${GREEN}✓ Daemon script ready${NC}"

# Option to enable launchd
echo ""
echo -e "${BLUE}Infrastructure Daemon Options:${NC}"
echo ""
echo "The daemon continuously monitors and auto-restarts services."
echo "This is recommended for production environments."
echo ""

read -p "Enable auto-start daemon now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Starting daemon...${NC}"
    "$SCRIPT_DIR/scripts/infra-daemon.sh" start
    sleep 2
    "$SCRIPT_DIR/scripts/infra-daemon.sh" status
fi

echo ""

# Option for Mac LaunchAgent
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${BLUE}Mac LaunchAgent Setup:${NC}"
    echo ""
    echo "The LaunchAgent will start the daemon automatically on boot."
    echo ""
    
    read -p "Enable auto-start on Mac boot? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        PLIST_SRC="$SCRIPT_DIR/scripts/com.agentic-brain.infra-daemon.plist"
        PLIST_DST="$HOME/Library/LaunchAgents/com.agentic-brain.infra-daemon.plist"
        
        mkdir -p "$HOME/Library/LaunchAgents"
        cp "$PLIST_SRC" "$PLIST_DST"
        
        launchctl load "$PLIST_DST"
        
        echo -e "${GREEN}✓ LaunchAgent installed${NC}"
        echo "  Location: $PLIST_DST"
        echo "  Status: $(launchctl list | grep agentic-brain || echo 'loading...')"
    fi
    
    echo ""
fi

# Summary
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  ${GREEN}✓ Infrastructure Setup Complete!${NC}      ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

echo "Next steps:"
echo ""
echo "1. Start services:"
echo -e "   ${YELLOW}docker-compose up -d${NC}"
echo ""
echo "2. Check status:"
echo -e "   ${YELLOW}./scripts/infra-daemon.sh status${NC}"
echo ""
echo "3. View logs:"
echo -e "   ${YELLOW}./scripts/infra-daemon.sh logs${NC}"
echo ""
echo "4. Documentation:"
echo -e "   ${YELLOW}cat INFRASTRUCTURE.md${NC}"
echo ""
echo "For more info:"
echo "  • Daemon:  ./scripts/infra-daemon.sh --help"
echo "  • Docs:    INFRASTRUCTURE.md"
echo "  • Tests:   pytest tests/test_infrastructure.py -v"
echo ""
