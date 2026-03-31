#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
# =============================================================================
# Agentic Brain - Bulletproof One-Line Installer
# Based on Retool install patterns
# =============================================================================
# Usage: curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.sh | bash
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/joseph-webber/agentic-brain.git"
INSTALL_DIR="${AGENTIC_BRAIN_DIR:-$HOME/agentic-brain}"
BRANCH="${AGENTIC_BRAIN_BRANCH:-main}"
ENV_FILE="$INSTALL_DIR/.env"

# Print banner
banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║             🧠 Agentic Brain Installer 🧠                     ║"
    echo "║                                                               ║"
    echo "║  Universal AI Brain with Neo4j, Redis & Redpanda             ║"
    echo "║                  (Bulletproof Edition)                        ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Logging functions
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

# Check if command exists
check_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# Random password generator (like Retool)
random() { 
    cat /dev/urandom | base64 | head -c "$1" | tr -d +/ | tr -d '='; 
}

# Random hex generator for JWT_SECRET (using openssl)
random_hex() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex "$1"
    else
        # Fallback if openssl not available
        random $((2 * $1))
    fi
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)  OS="macos" ;;
        Linux*)   OS="linux" ;;
        MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
        *)        OS="unknown" ;;
    esac
    echo "$OS"
}

# Auto-install Docker (Retool pattern)
auto_install_docker() {
    local os="$(detect_os)"
    
    if [ "$os" = "linux" ]; then
        if ! check_cmd wget; then
            error "wget is required to auto-install Docker. Please install it manually:"
            echo "  Ubuntu/Debian: sudo apt-get install -y wget"
            echo "  Or install Docker manually: https://docs.docker.com/install"
            exit 1
        fi
        
        info "Attempting to install Docker via get.docker.com..."
        if wget -qO- https://get.docker.com | sh; then
            success "Docker installed successfully"
            # Add user to docker group
            if check_cmd sudo; then
                info "Adding current user to docker group..."
                sudo usermod -aG docker "$USER" 2>/dev/null || true
                warn "You may need to log out and back in, or run: newgrp docker"
            fi
            return 0
        else
            error "Docker installation failed"
            echo "Please install Docker manually: https://docs.docker.com/install"
            exit 1
        fi
    elif [ "$os" = "macos" ]; then
        if ! check_cmd brew; then
            error "Homebrew is required. Install from: https://brew.sh"
            exit 1
        fi
        info "Installing Docker via Homebrew..."
        brew install --cask docker
        success "Docker installed. Please start Docker Desktop to continue."
        exit 1
    else
        error "Auto-install not supported for your OS"
        echo "Please install Docker manually: https://docs.docker.com/install"
        exit 1
    fi
}

# Check Docker installation
check_docker() {
    info "Checking Docker installation..."
    
    if ! check_cmd docker; then
        warn "Docker is not installed"
        read -p "  Would you like to auto-install Docker? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            auto_install_docker
        else
            error "Docker is required. Install from: https://docs.docker.com/install"
            exit 1
        fi
    fi
    
    # Check if Docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        error "Docker daemon is not running!"
        case "$(detect_os)" in
            macos)
                echo "Please start Docker Desktop, then run this script again"
                # Try Colima as fallback
                if check_cmd colima; then
                    warn "Attempting to start Colima..."
                    colima start 2>/dev/null || true
                    sleep 3
                    if docker info >/dev/null 2>&1; then
                        success "Colima started successfully"
                        return 0
                    fi
                fi
                ;;
            linux)
                echo "Run: sudo systemctl start docker"
                ;;
        esac
        exit 1
    fi
    
    success "Docker is installed: $(docker --version)"
}

# Check docker compose
check_docker_compose() {
    info "Checking Docker Compose..."
    
    # Try docker compose (v2) first
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
        success "Docker Compose v2 found: $(docker compose version | head -1)"
        return 0
    fi
    
    # Try docker-compose (v1)
    if check_cmd docker-compose; then
        COMPOSE_CMD="docker-compose"
        success "Docker Compose v1 found"
        return 0
    fi
    
    error "Docker Compose not found!"
    echo ""
    echo "Docker Desktop includes Compose by default."
    echo "Please ensure Docker Desktop is fully installed."
    echo "Or install manually: https://docs.docker.com/compose/install/"
    exit 1
}

# Clone or update repository
setup_repo() {
    info "Setting up repository..."
    
    if [ -d "$INSTALL_DIR/.git" ]; then
        info "Repository exists at $INSTALL_DIR, updating..."
        cd "$INSTALL_DIR"
        git fetch origin >/dev/null 2>&1
        git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH" >/dev/null 2>&1
        git pull origin "$BRANCH" --ff-only >/dev/null 2>&1 || {
            warn "Pull conflict, forcing reset to origin/$BRANCH"
            git reset --hard "origin/$BRANCH" >/dev/null 2>&1
        }
        success "Repository updated"
    else
        info "Cloning repository (this may take a minute)..."
        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" >/dev/null 2>&1
        cd "$INSTALL_DIR"
        success "Repository cloned to $INSTALL_DIR"
    fi
}

# Configure environment (Retool pattern)
setup_env() {
    info "Generating environment configuration..."
    
    # Check if .env already exists (Retool pattern: exit if it does)
    if [ -f "$ENV_FILE" ]; then
        warn ".env file already exists at $ENV_FILE"
        warn "Skipping environment setup to preserve existing configuration"
        return 0
    fi
    
    # Generate random passwords (Retool pattern)
    NEO4J_PASSWORD=$(random 64)
    REDIS_PASSWORD=$(random 64)
    ENCRYPTION_KEY=$(random 64)
    JWT_SECRET=$(random_hex 32)
    
    # Handle corporate SSL/proxy issues
    if [ -n "$REQUESTS_CA_BUNDLE" ] || [ -n "$SSL_CERT_FILE" ]; then
        info "Corporate SSL detected, configuring trusted hosts..."
        export PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"
    fi
    
    # Create .env file (like Retool)
    cat > "$ENV_FILE" << EOF
# ============================================================================
# Agentic Brain Configuration
# Generated by bulletproof installer on $(date)
# ============================================================================

# Core Application Settings
ENVIRONMENT=production
DEBUG=false
APP_PORT=8000

# ============================================================================
# Neo4j Graph Database
# ============================================================================
NEO4J_HOST=neo4j
NEO4J_PORT=7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=$NEO4J_PASSWORD
NEO4J_URI=bolt://neo4j:7687
NEO4J_ADMIN_USER=neo4j
NEO4J_ADMIN_PASSWORD=$NEO4J_PASSWORD

# ============================================================================
# Redis Cache
# ============================================================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=$REDIS_PASSWORD
REDIS_DB=0

# ============================================================================
# Redpanda Message Queue
# ============================================================================
REDPANDA_HOST=redpanda
REDPANDA_PORT=9092
REDPANDA_BROKERS=redpanda:9092

# ============================================================================
# Security & Encryption
# ============================================================================
# Key to encrypt/decrypt sensitive values in Neo4j
ENCRYPTION_KEY=$ENCRYPTION_KEY

# Key to sign JWT authentication tokens
JWT_SECRET=$JWT_SECRET

# ============================================================================
# LLM Provider Configuration
# Choose ONE provider and add your API key if needed
# ============================================================================

# Groq (Fastest, free tier available)
# GROQ_API_KEY=your-groq-key-here

# OpenAI (Best quality)
# OPENAI_API_KEY=your-openai-key-here

# Anthropic Claude (Great reasoning)
# ANTHROPIC_API_KEY=your-anthropic-key-here

# Local Ollama (Works offline, free)
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_LLM_MODEL=llama3.2

# ============================================================================
# Corporate Proxy / SSL Configuration
# ============================================================================
# Uncomment if behind corporate proxy with SSL inspection
# PIP_TRUSTED_HOST=pypi.org pypi.python.org files.pythonhosted.org
# REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
# SSL_CERT_FILE=/path/to/ca-bundle.crt

# ============================================================================
# Advanced Configuration (usually not needed)
# ============================================================================
LOG_LEVEL=INFO
TELEMETRY_ENABLED=true
METRICS_PORT=9090

# ============================================================================
# IMPORTANT: Customize before production deployment!
# 1. Change all passwords to strong, unique values
# 2. Add your LLM API key(s) if using cloud providers
# 3. Configure SSL certificates for HTTPS
# 4. Set up proper backups and monitoring
# ============================================================================
EOF
    
    success "Created .env file with random passwords"
    echo ""
    echo "  📝 .env file location: $ENV_FILE"
    echo "  🔐 Passwords generated: Neo4j, Redis, JWT, Encryption"
    echo ""
}


# Start services
start_services() {
    info "Starting Agentic Brain services..."
    cd "$INSTALL_DIR"
    
    # Start services with --build to ensure Dockerfile is executed
    # (instead of just pulling pre-built images)
    info "Building and starting services with: $COMPOSE_CMD up -d --build"
    if $COMPOSE_CMD up -d --build; then
        success "Services started successfully"
    else
        error "Failed to start services"
        error "Run: cd $INSTALL_DIR && $COMPOSE_CMD logs -f"
        exit 1
    fi
}

# Wait for health checks with detailed feedback
wait_for_health() {
    info "Waiting for services to become healthy..."
    
    local max_wait=180
    local waited=0
    local interval=3
    
    local neo4j_ready=false
    local redis_ready=false
    local redpanda_ready=false
    
    # Load REDIS_PASSWORD from .env if not already set
    if [ -z "$REDIS_PASSWORD" ] && [ -f "$ENV_FILE" ]; then
        REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2)
    fi
    REDIS_PASSWORD="${REDIS_PASSWORD:-BrainRedis2026}"
    
    echo ""
    while [ $waited -lt $max_wait ]; do
        # Check Neo4j (port 7687 or 7474 HTTP)
        if ! $neo4j_ready && curl -sf http://localhost:7474 >/dev/null 2>&1; then
            success "✓ Neo4j is ready (http://localhost:7474)"
            neo4j_ready=true
        fi
        
        # Check Redis
        if ! $redis_ready && docker exec agentic-brain-redis redis-cli -a "$REDIS_PASSWORD" ping >/dev/null 2>&1; then
            success "✓ Redis is ready"
            redis_ready=true
        fi
        
        # Check Redpanda
        if ! $redpanda_ready && curl -sf http://localhost:9644/v1/status/ready >/dev/null 2>&1; then
            success "✓ Redpanda is ready"
            redpanda_ready=true
        fi
        
        # All healthy?
        if $neo4j_ready && $redis_ready && $redpanda_ready; then
            echo ""
            return 0
        fi
        
        sleep $interval
        waited=$((waited + interval))
        echo -n "."
    done
    
    echo ""
    warn "Services are starting (may take a few more moments)..."
    info "Check status with: $COMPOSE_CMD ps"
    info "View logs with: $COMPOSE_CMD logs -f"
    return 0
}

# Print success message with all details
print_success() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║        🎉 Agentic Brain Installed Successfully! 🎉            ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${CYAN}📍 Service URLs:${NC}"
    echo "   • API Server:      http://localhost:8000"
    echo "   • API Docs:        http://localhost:8000/docs"
    echo "   • Neo4j Browser:   http://localhost:7474"
    echo "   • Redpanda UI:     http://localhost:9644"
    echo ""
    
    echo -e "${CYAN}🔐 Default Credentials:${NC}"
    echo "   • Neo4j User:      neo4j"
    echo "   • Neo4j Password:  (See $ENV_FILE)"
    echo "   • Redis Password:  (See $ENV_FILE)"
    echo ""
    
    echo -e "${CYAN}📂 Installation Directory:${NC}"
    echo "   $INSTALL_DIR"
    echo ""
    
    echo -e "${CYAN}🚀 Quick Commands:${NC}"
    echo "   cd $INSTALL_DIR"
    echo "   $COMPOSE_CMD logs -f          # View real-time logs"
    echo "   $COMPOSE_CMD ps               # Check service status"
    echo "   $COMPOSE_CMD down             # Stop services"
    echo "   $COMPOSE_CMD up -d            # Start services"
    echo ""
    
    echo -e "${CYAN}📝 Next Steps:${NC}"
    echo "   1. Review .env file: $ENV_FILE"
    echo "   2. Add your LLM API key if using cloud provider"
    echo "   3. Visit http://localhost:7474 to explore Neo4j"
    echo "   4. Visit http://localhost:8000/docs for API documentation"
    echo ""
    
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo "   • For local LLM: run 'ollama pull llama3.2'"
    echo "   • For production: change all passwords in .env"
    echo "   • Check logs if services don't start: $COMPOSE_CMD logs"
    echo ""
}

# Main installation flow
main() {
    banner
    
    echo ""
    info "Checking installation requirements..."
    
    # Pre-flight checks
    check_docker
    check_docker_compose
    
    # Check git
    if ! check_cmd git; then
        error "Git is not installed!"
        case "$(detect_os)" in
            macos)
                echo "Install with: brew install git"
                ;;
            linux)
                echo "Install with: sudo apt-get install git"
                ;;
        esac
        exit 1
    fi
    success "Git is installed"
    
    echo ""
    # Setup
    setup_repo
    cd "$INSTALL_DIR"
    setup_env
    
    echo ""
    # Start services
    start_services
    wait_for_health
    
    # Offer to set up local LLM
    echo ""
    echo "============================================"
    echo "  LOCAL LLM SETUP (OPTIONAL)"
    echo "============================================"
    echo ""
    echo "Would you like to set up Ollama for local LLM inference?"
    echo "This allows the brain to work without API keys."
    echo ""
    read -p "Install Ollama? [y/N] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Installing Ollama..."
        if command -v brew &> /dev/null; then
            brew install ollama
        else
            curl -fsSL https://ollama.com/install.sh | sh
        fi
        
        # Start and pull model
        ollama serve &> /dev/null &
        sleep 3
        info "Pulling default model (llama3.2:3b)..."
        ollama pull llama3.2:3b
        
        echo ""
        success "Ollama installed! The brain can now use local LLM."
    fi

    # Optional LLM API key setup
    echo ""
    echo "============================================"
    echo "  LLM API KEY SETUP (OPTIONAL)"
    echo "============================================"
    echo ""
    echo "Would you like to set up LLM API keys now? [y/N]"
    read -r SETUP_KEYS
    if [ "$SETUP_KEYS" = "y" ] || [ "$SETUP_KEYS" = "Y" ]; then
        if [ -f "./scripts/setup-keys.sh" ]; then
            bash ./scripts/setup-keys.sh
        else
            echo "Run 'bash scripts/setup-keys.sh' later to configure API keys."
        fi
    fi

    # Done!
    print_success
}

# Run main
main "$@"
