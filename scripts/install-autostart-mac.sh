#!/bin/bash

################################################################################
# Agentic Brain - macOS Auto-Start Installer
################################################################################
# This script sets up launchd services to auto-start agentic-brain on login:
# 1. Colima (Docker Desktop alternative) on startup
# 2. All agentic-brain services (Neo4j, Redis, Redpanda) via docker-compose
#
# Usage:
#   ./install-autostart-mac.sh              # Install auto-start
#   ./install-autostart-mac.sh --uninstall  # Remove auto-start
#   ./install-autostart-mac.sh --verify     # Verify installation
#
# Safe to run multiple times (idempotent)
################################################################################

set -u

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
LAUNCHD_DIR="$SCRIPT_DIR/launchd"
PLIST_DIR="$HOME/Library/LaunchAgents"

# Service identifiers
COLIMA_PLIST_ID="com.agentic-brain.colima"
SERVICES_PLIST_ID="com.agentic-brain.services"

# plist file paths
COLIMA_PLIST="$LAUNCHD_DIR/$COLIMA_PLIST_ID.plist"
SERVICES_PLIST="$LAUNCHD_DIR/$SERVICES_PLIST_ID.plist"

COLIMA_INSTALLED_PLIST="$PLIST_DIR/$COLIMA_PLIST_ID.plist"
SERVICES_INSTALLED_PLIST="$PLIST_DIR/$SERVICES_PLIST_ID.plist"

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

log_success() {
    echo -e "${GREEN}✓ ${NC}$1"
}

log_warn() {
    echo -e "${YELLOW}⚠ ${NC}$1"
}

log_error() {
    echo -e "${RED}✗ ${NC}$1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if macOS
    if [[ ! "$OSTYPE" == "darwin"* ]]; then
        log_error "This script is for macOS only"
        exit 1
    fi
    
    # Check for Docker or Colima
    if ! command -v docker &> /dev/null && ! command -v colima &> /dev/null; then
        log_warn "Neither Docker nor Colima found"
        log_warn "Install one of:"
        log_warn "  - Docker Desktop: https://www.docker.com/products/docker-desktop"
        log_warn "  - Colima: brew install colima"
        return 1
    fi
    
    # Check for docker-compose in project
    if [[ ! -f "$PROJECT_ROOT/docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found in $PROJECT_ROOT"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
    return 0
}

ensure_launchd_dir() {
    if [[ ! -d "$LAUNCHD_DIR" ]]; then
        log_info "Creating launchd directory: $LAUNCHD_DIR"
        mkdir -p "$LAUNCHD_DIR"
        log_success "Created launchd directory"
    fi
}

ensure_plist_dir() {
    if [[ ! -d "$PLIST_DIR" ]]; then
        log_info "Creating LaunchAgents directory: $PLIST_DIR"
        mkdir -p "$PLIST_DIR"
        log_success "Created LaunchAgents directory"
    fi
}

create_colima_plist() {
    log_info "Creating Colima plist: $COLIMA_PLIST"
    
    cat > "$COLIMA_PLIST" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Service identifier -->
    <key>Label</key>
    <string>com.agentic-brain.colima</string>
    
    <!-- Program to run -->
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/colima</string>
        <string>start</string>
        <string>--quiet</string>
    </array>
    
    <!-- Run on startup -->
    <key>RunAtLoad</key>
    <true/>
    
    <!-- Restart if exits unexpectedly -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <!-- Standard output/error logging -->
    <key>StandardOutPath</key>
    <string>/var/log/agentic-brain-colima.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/agentic-brain-colima.log</string>
    
    <!-- Wait before restarting -->
    <key>ThrottleInterval</key>
    <integer>10</integer>
    
    <!-- Set nice value (low priority) -->
    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
EOF
    
    chmod 644 "$COLIMA_PLIST"
    log_success "Created Colima plist"
}

create_services_plist() {
    log_info "Creating services plist: $SERVICES_PLIST"
    
    cat > "$SERVICES_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Service identifier -->
    <key>Label</key>
    <string>com.agentic-brain.services</string>
    
    <!-- Program to run -->
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>$SCRIPT_DIR/start-services.sh</string>
    </array>
    
    <!-- Run on startup -->
    <key>RunAtLoad</key>
    <true/>
    
    <!-- Restart if exits unexpectedly -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <!-- Standard output/error logging -->
    <key>StandardOutPath</key>
    <string>/var/log/agentic-brain-services.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/agentic-brain-services.log</string>
    
    <!-- Wait before restarting -->
    <key>ThrottleInterval</key>
    <integer>10</integer>
    
    <!-- Set working directory -->
    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT</string>
    
    <!-- Set nice value (low priority) -->
    <key>Nice</key>
    <integer>10</integer>
</dict>
</plist>
EOF
    
    chmod 644 "$SERVICES_PLIST"
    log_success "Created services plist"
}

create_start_services_script() {
    log_info "Creating start-services helper script"
    
    local START_SCRIPT="$SCRIPT_DIR/start-services.sh"
    
    cat > "$START_SCRIPT" << 'SCRIPT_EOF'
#!/bin/bash
# Helper script to start all agentic-brain services
# Called by launchd

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/var/log/agentic-brain-services.log"

# Log output
exec 1>>"$LOG_FILE" 2>&1

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Wait for Docker to be ready (max 30 seconds)
wait_for_docker() {
    local max_wait=30
    local elapsed=0
    
    log "Waiting for Docker daemon..."
    
    while ! docker ps &>/dev/null; do
        if [ $elapsed -ge $max_wait ]; then
            log "ERROR: Docker daemon not available after ${max_wait}s"
            exit 1
        fi
        
        sleep 1
        ((elapsed++))
    done
    
    log "Docker daemon ready after ${elapsed}s"
}

# Start docker-compose services
start_services() {
    log "Starting agentic-brain services..."
    
    cd "$PROJECT_ROOT" || exit 1
    
    # Check if docker-compose.yml exists
    if [[ ! -f "docker-compose.yml" ]]; then
        log "ERROR: docker-compose.yml not found in $PROJECT_ROOT"
        exit 1
    fi
    
    # Ensure .env file exists
    if [[ ! -f ".env" ]]; then
        log "Creating .env from .env.example"
        cp .env.example .env 2>/dev/null || true
    fi
    
    # Start services in detached mode
    log "Running: docker compose up -d"
    docker compose up -d 2>&1 | while IFS= read -r line; do
        log "$line"
    done
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log "Services started successfully"
        
        # Wait for services to be healthy (max 60 seconds)
        log "Waiting for services to be ready..."
        sleep 5
        
        # Check if containers are running
        running=$(docker compose ps --services --filter "status=running" | wc -l)
        total=$(docker compose config --services | wc -l)
        
        log "Services running: $running/$total"
    else
        log "ERROR: Failed to start services"
        exit 1
    fi
}

main() {
    log "=========================================="
    log "Agentic Brain Service Startup"
    log "=========================================="
    
    wait_for_docker
    start_services
    
    log "Startup complete"
}

main "$@"
SCRIPT_EOF
    
    chmod 755 "$START_SCRIPT"
    log_success "Created start-services script: $START_SCRIPT"
}

install_plists() {
    log_info "Installing launchd plists..."
    
    ensure_plist_dir
    
    # Unload existing plists if present
    if launchctl list "$COLIMA_PLIST_ID" &>/dev/null; then
        log_info "Unloading existing Colima service"
        launchctl unload "$COLIMA_INSTALLED_PLIST" 2>/dev/null || true
    fi
    
    if launchctl list "$SERVICES_PLIST_ID" &>/dev/null; then
        log_info "Unloading existing services"
        launchctl unload "$SERVICES_INSTALLED_PLIST" 2>/dev/null || true
    fi
    
    # Copy plists to LaunchAgents
    log_info "Copying plists to $PLIST_DIR"
    cp "$COLIMA_PLIST" "$COLIMA_INSTALLED_PLIST"
    cp "$SERVICES_PLIST" "$SERVICES_INSTALLED_PLIST"
    
    chmod 644 "$COLIMA_INSTALLED_PLIST"
    chmod 644 "$SERVICES_INSTALLED_PLIST"
    
    log_success "Copied plists"
    
    # Load plists
    log_info "Loading launchd services..."
    
    if launchctl load "$COLIMA_INSTALLED_PLIST"; then
        log_success "Loaded Colima service"
    else
        log_error "Failed to load Colima service"
        return 1
    fi
    
    if launchctl load "$SERVICES_INSTALLED_PLIST"; then
        log_success "Loaded services"
    else
        log_error "Failed to load services"
        return 1
    fi
}

uninstall_plists() {
    log_info "Uninstalling launchd plists..."
    
    # Unload services
    if launchctl list "$COLIMA_PLIST_ID" &>/dev/null; then
        log_info "Unloading Colima service"
        launchctl unload "$COLIMA_INSTALLED_PLIST"
        log_success "Unloaded Colima service"
    fi
    
    if launchctl list "$SERVICES_PLIST_ID" &>/dev/null; then
        log_info "Unloading services"
        launchctl unload "$SERVICES_INSTALLED_PLIST"
        log_success "Unloaded services"
    fi
    
    # Remove plist files
    if [[ -f "$COLIMA_INSTALLED_PLIST" ]]; then
        rm -f "$COLIMA_INSTALLED_PLIST"
        log_success "Removed Colima plist"
    fi
    
    if [[ -f "$SERVICES_INSTALLED_PLIST" ]]; then
        rm -f "$SERVICES_INSTALLED_PLIST"
        log_success "Removed services plist"
    fi
}

verify_installation() {
    log_info "Verifying installation..."
    
    local status_ok=true
    
    # Check Colima service
    if launchctl list "$COLIMA_PLIST_ID" &>/dev/null; then
        log_success "Colima service is loaded"
    else
        log_warn "Colima service is not loaded"
        status_ok=false
    fi
    
    # Check services
    if launchctl list "$SERVICES_PLIST_ID" &>/dev/null; then
        log_success "Services are loaded"
    else
        log_warn "Services are not loaded"
        status_ok=false
    fi
    
    # Check Docker
    if docker ps &>/dev/null; then
        log_success "Docker is running"
    else
        log_warn "Docker is not running"
        status_ok=false
    fi
    
    # Check if containers are running
    if docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -q "agentic-brain\|neo4j\|redis\|redpanda"; then
        log_success "Agentic Brain services are running"
    else
        log_warn "Agentic Brain services are not running (may still be starting)"
    fi
    
    # Show logs
    if [[ -f /var/log/agentic-brain-services.log ]]; then
        log_info "Last 10 lines of service log:"
        tail -10 /var/log/agentic-brain-services.log | sed 's/^/  /'
    fi
    
    if $status_ok; then
        log_success "Verification passed"
        return 0
    else
        log_warn "Some services may not be running yet. Check logs:"
        log_warn "  tail -f /var/log/agentic-brain-services.log"
        return 0
    fi
}

show_status() {
    log_info "Checking current status..."
    echo ""
    
    if launchctl list "$COLIMA_PLIST_ID" &>/dev/null; then
        echo -e "${GREEN}✓${NC} Colima auto-start is ENABLED"
    else
        echo -e "${RED}✗${NC} Colima auto-start is DISABLED"
    fi
    
    if launchctl list "$SERVICES_PLIST_ID" &>/dev/null; then
        echo -e "${GREEN}✓${NC} Services auto-start is ENABLED"
    else
        echo -e "${RED}✗${NC} Services auto-start is DISABLED"
    fi
    
    echo ""
    
    if docker ps &>/dev/null; then
        echo -e "${GREEN}✓${NC} Docker is running"
        echo ""
        log_info "Running containers:"
        docker ps --format "table {{.Names}}\t{{.Status}}" | sed 's/^/  /'
    else
        echo -e "${RED}✗${NC} Docker is not running"
    fi
    
    echo ""
    log_info "Log files:"
    echo "  Colima:   /var/log/agentic-brain-colima.log"
    echo "  Services: /var/log/agentic-brain-services.log"
}

show_help() {
    cat << EOF
${BLUE}Agentic Brain - macOS Auto-Start Installer${NC}

${YELLOW}Usage:${NC}
  $0 [OPTION]

${YELLOW}Options:${NC}
  (no option)     Install/update auto-start services
  --uninstall     Remove auto-start services
  --verify        Verify installation
  --status        Show current status
  --help          Show this help message

${YELLOW}Examples:${NC}
  # Install auto-start
  $0

  # Check if installed
  $0 --status

  # Remove auto-start
  $0 --uninstall

${YELLOW}What this does:${NC}
  1. Creates launchd services that run at login
  2. Auto-starts Colima (Docker alternative) on login
  3. Auto-starts all agentic-brain services (Neo4j, Redis, Redpanda)
  4. Monitors and restarts services if they crash

${YELLOW}Log files:${NC}
  /var/log/agentic-brain-colima.log    - Colima startup logs
  /var/log/agentic-brain-services.log  - Services startup logs

${YELLOW}Uninstall:${NC}
  Services can be uninstalled with: $0 --uninstall
  Or manually: launchctl unload ~/Library/LaunchAgents/com.agentic-brain.*.plist

EOF
}

################################################################################
# Main
################################################################################

main() {
    local action="${1:-install}"
    
    case "$action" in
        --help|-h)
            show_help
            exit 0
            ;;
        --uninstall)
            log_info "Uninstalling auto-start services..."
            uninstall_plists
            log_success "Auto-start services removed"
            exit 0
            ;;
        --verify)
            check_prerequisites || exit 1
            verify_installation
            exit 0
            ;;
        --status)
            show_status
            exit 0
            ;;
        install)
            log_info "Installing agentic-brain auto-start..."
            echo ""
            
            check_prerequisites || exit 1
            ensure_launchd_dir
            create_colima_plist
            create_services_plist
            create_start_services_script
            install_plists || exit 1
            
            echo ""
            log_success "Auto-start installation complete!"
            echo ""
            
            log_info "Next steps:"
            echo "  1. Services will start automatically on next login"
            echo "  2. For immediate startup, run: launchctl start com.agentic-brain.colima"
            echo "  3. Then run: launchctl start com.agentic-brain.services"
            echo ""
            
            verify_installation
            
            echo ""
            log_info "Useful commands:"
            echo "  Check status:  $0 --status"
            echo "  View logs:     tail -f /var/log/agentic-brain-services.log"
            echo "  Stop services: docker compose -f $PROJECT_ROOT/docker-compose.yml down"
            echo "  Remove auto-start: $0 --uninstall"
            echo ""
            ;;
        *)
            log_error "Unknown option: $action"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
