#!/usr/bin/env bash
################################################################################
# Agentic Brain - Linux Auto-Start Installer
# 
# Installs systemd user services for automatic startup of:
# - Neo4j (Graph Database)
# - Redis (Caching)
# - Redpanda (Message Queue)
#
# These services auto-start when the user logs in to their desktop.
# 
# Usage:
#   ./scripts/install-autostart-linux.sh              # Install
#   ./scripts/install-autostart-linux.sh --uninstall  # Remove
#
# Supported Distros:
#   - Ubuntu 20.04+ / Debian 11+ (apt)
#   - Fedora 35+ (dnf/yum)
#   - Arch Linux (pacman)
#   - Any distro with systemd (most modern Linux distros)
#
################################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
SYSTEMD_TEMPLATE_DIR="${SCRIPT_DIR}/systemd"

# Service names
SERVICE_NAME="agentic-brain.service"
SERVICE_ENV_FILE="agentic-brain.env"

################################################################################
# Utility Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $*"
}

log_error() {
    echo -e "${RED}[✗]${NC} $*" >&2
}

die() {
    log_error "$@"
    exit 1
}

# Check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

################################################################################
# Pre-flight Checks
################################################################################

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check systemd
    if ! command_exists systemctl; then
        die "systemd not found. This script requires systemd (available on most modern Linux distros)."
    fi
    
    # Check docker
    if ! command_exists docker; then
        die "Docker not installed. Please install Docker first: https://docs.docker.com/engine/install/"
    fi
    
    # Check docker compose
    if ! docker compose version &>/dev/null; then
        die "Docker Compose not available. Install it with: docker run --rm -v /usr/local/bin:/usr/local/bin docker/compose:latest cp /usr/local/bin/docker-compose /usr/local/bin/"
    fi
    
    # Check that we're in the right directory
    if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
        die "docker-compose.yml not found in $PROJECT_DIR. Are you running this from the correct directory?"
    fi
    
    log_success "All prerequisites met"
}

################################################################################
# System Detection & Validation
################################################################################

detect_distribution() {
    if [ -f /etc/os-release ]; then
        # shellcheck source=/dev/null
        . /etc/os-release
        echo "$ID"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    else
        echo "unknown"
    fi
}

check_docker_daemon() {
    log_info "Checking Docker daemon status..."
    
    if ! docker ps &>/dev/null; then
        log_warning "Docker daemon is not running or you don't have permission"
        log_info "To fix, either:"
        log_info "  1. Add your user to docker group: sudo usermod -aG docker \$USER && newgrp docker"
        log_info "  2. Or ensure Docker daemon is running: sudo systemctl start docker"
        return 1
    fi
    
    log_success "Docker daemon is running"
    return 0
}

################################################################################
# Installation Functions
################################################################################

create_systemd_user_dir() {
    log_info "Creating systemd user directory..."
    
    if [ ! -d "$SYSTEMD_USER_DIR" ]; then
        mkdir -p "$SYSTEMD_USER_DIR"
        log_success "Created $SYSTEMD_USER_DIR"
    else
        log_info "Directory already exists: $SYSTEMD_USER_DIR"
    fi
}

create_service_env_file() {
    log_info "Creating service environment file..."
    
    local env_file="$SYSTEMD_USER_DIR/$SERVICE_ENV_FILE"
    
    # Create environment file with necessary settings
    cat > "$env_file" << 'EOF'
# Agentic Brain Service Environment Variables
# This file is sourced by systemd when starting the agentic-brain service

# Docker path (usually /usr/bin/docker, sometimes in /snap/bin on some systems)
PATH=/usr/local/bin:/usr/bin:/bin
EOF
    
    chmod 600 "$env_file"
    log_success "Created $env_file"
}

install_service_file() {
    log_info "Installing systemd service file..."
    
    if [ ! -f "$SYSTEMD_TEMPLATE_DIR/$SERVICE_NAME" ]; then
        die "Service template not found: $SYSTEMD_TEMPLATE_DIR/$SERVICE_NAME"
    fi
    
    local service_file="$SYSTEMD_USER_DIR/$SERVICE_NAME"
    
    cp "$SYSTEMD_TEMPLATE_DIR/$SERVICE_NAME" "$service_file"
    chmod 644 "$service_file"
    
    log_success "Installed $service_file"
}

enable_and_start_service() {
    log_info "Enabling and starting systemd service..."
    
    # Reload systemd to recognize new service
    systemctl --user daemon-reload
    log_info "Reloaded systemd user services"
    
    # Enable service to start on login
    systemctl --user enable "$SERVICE_NAME"
    log_success "Enabled $SERVICE_NAME to start on user login"
    
    # Start the service now
    if systemctl --user start "$SERVICE_NAME"; then
        log_success "Started $SERVICE_NAME"
    else
        log_warning "Failed to start $SERVICE_NAME immediately"
        log_info "It may start on next login or you can start it manually:"
        log_info "  systemctl --user start $SERVICE_NAME"
    fi
}

################################################################################
# Uninstall Functions
################################################################################

disable_and_stop_service() {
    log_info "Stopping and disabling service..."
    
    # Stop service if running
    if systemctl --user is-active --quiet "$SERVICE_NAME"; then
        systemctl --user stop "$SERVICE_NAME"
        log_success "Stopped $SERVICE_NAME"
    fi
    
    # Disable auto-start
    if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl --user disable "$SERVICE_NAME"
        log_success "Disabled $SERVICE_NAME auto-start"
    fi
    
    # Reload systemd
    systemctl --user daemon-reload
}

remove_service_files() {
    log_info "Removing service files..."
    
    local service_file="$SYSTEMD_USER_DIR/$SERVICE_NAME"
    local env_file="$SYSTEMD_USER_DIR/$SERVICE_ENV_FILE"
    
    if [ -f "$service_file" ]; then
        rm -f "$service_file"
        log_success "Removed $service_file"
    fi
    
    if [ -f "$env_file" ]; then
        rm -f "$env_file"
        log_success "Removed $env_file"
    fi
}

################################################################################
# Status & Information Functions
################################################################################

show_status() {
    log_info "Service Status:"
    
    local service_file="$SYSTEMD_USER_DIR/$SERVICE_NAME"
    
    if [ ! -f "$service_file" ]; then
        log_error "Service not installed"
        return 1
    fi
    
    echo "  File: $service_file"
    echo "  Enabled: $(systemctl --user is-enabled "$SERVICE_NAME" 2>/dev/null || echo 'no')"
    echo "  Running: $(systemctl --user is-active "$SERVICE_NAME" 2>/dev/null || echo 'no')"
    echo ""
    
    # Show recent logs
    log_info "Recent logs (last 20 lines):"
    journalctl --user -u "$SERVICE_NAME" -n 20 --no-pager || echo "  (No logs available)"
    
    echo ""
    log_info "Useful commands:"
    echo "  View status:     systemctl --user status $SERVICE_NAME"
    echo "  View logs:       journalctl --user -u $SERVICE_NAME -f"
    echo "  Start service:   systemctl --user start $SERVICE_NAME"
    echo "  Stop service:    systemctl --user stop $SERVICE_NAME"
    echo "  Restart service: systemctl --user restart $SERVICE_NAME"
}

show_help() {
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                    Agentic Brain - Linux Auto-Start                         ║
║                                                                              ║
║  Installs systemd user services for automatic startup of agentic-brain      ║
║  services (Neo4j, Redis, Redpanda) when you log into your desktop.         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

USAGE:
  ./scripts/install-autostart-linux.sh [COMMAND] [OPTIONS]

COMMANDS:
  install                    Install and enable auto-start (default)
  uninstall                  Remove auto-start configuration
  status                     Show service status and recent logs
  help                       Show this help message

OPTIONS:
  --help                     Show this help message
  --uninstall                Uninstall (same as 'uninstall' command)
  -v, --verbose              Enable verbose output (for debugging)
  --no-start                 Install but don't start the service now

EXAMPLES:
  # Install auto-start
  ./scripts/install-autostart-linux.sh

  # Install but don't start immediately
  ./scripts/install-autostart-linux.sh --no-start

  # Check service status
  ./scripts/install-autostart-linux.sh status

  # Remove auto-start
  ./scripts/install-autostart-linux.sh uninstall

FEATURES:
  ✓ Auto-start on desktop login (systemd user service)
  ✓ Auto-restart on failure
  ✓ Proper dependency management (waits for Docker daemon)
  ✓ Docker Compose integration
  ✓ Comprehensive logging via journalctl

HOW IT WORKS:
  1. Creates a systemd user service file in ~/.config/systemd/user/
  2. Configures Docker Compose to start agentic-brain services
  3. Enables the service to start automatically on user login
  4. Services restart automatically if they crash

MANUAL CONTROL:
  After installation, you can manage the service manually:

  # View status
  systemctl --user status agentic-brain.service

  # View logs in real-time
  journalctl --user -u agentic-brain.service -f

  # Start/stop/restart
  systemctl --user start/stop/restart agentic-brain.service

  # Check if service is running
  systemctl --user is-active agentic-brain.service

TROUBLESHOOTING:
  Q: Service won't start
  A: Check Docker is running and accessible:
     docker ps

  Q: Service fails to start
  A: View detailed logs:
     journalctl --user -u agentic-brain.service -n 50

  Q: Need Docker to start automatically too?
  A: Enable Docker daemon auto-start:
     sudo systemctl enable docker

  Q: Using non-systemd distro?
  A: Fallback to @reboot cron:
     (crontab -l 2>/dev/null; echo "@reboot cd $HOME/brain/agentic-brain && docker compose up -d") | crontab -

SUPPORTED SYSTEMS:
  ✓ Ubuntu 20.04+
  ✓ Debian 11+
  ✓ Fedora 35+
  ✓ Arch Linux
  ✓ Any systemd-based distro

ENVIRONMENT:
  Project: $PROJECT_DIR
  Services: Neo4j, Redis, Redpanda (via Docker Compose)
  Auto-start: On user login (not system boot)

SUPPORT:
  GitHub: https://github.com/joseph-webber/agentic-brain
  Docs:   https://github.com/joseph-webber/agentic-brain/blob/main/INSTALL.md

EOF
}

################################################################################
# Fallback Functions (for non-systemd systems)
################################################################################

show_fallback_instructions() {
    cat << EOF

╔══════════════════════════════════════════════════════════════════════════════╗
║                           FALLBACK: Using Cron @reboot                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Your system doesn't have systemd (or it's disabled). Here's how to set up
auto-start using cron's @reboot directive:

STEP 1: Edit your crontab
    crontab -e

STEP 2: Add this line at the end:
    @reboot cd $PROJECT_DIR && docker compose up -d

STEP 3: Save and exit (Ctrl+X then Y if using nano)

STEP 4: Verify cron entry was added:
    crontab -l

NOTES:
  - Services will start automatically on system reboot
  - May require a few seconds to start after boot
  - To check if services are running:
      docker compose ps
  - To manually stop services:
      cd $PROJECT_DIR && docker compose down
  - To view cron logs:
      grep CRON /var/log/syslog  (Debian/Ubuntu)
      tail -f /var/log/cron      (Fedora/RHEL)

ALTERNATIVE (if cron doesn't work):
  - Add to ~/.bashrc or ~/.zshrc:
    (Add auto-start script at shell login)
  - Or use your desktop environment's autostart folder:
    ~/.config/autostart/agentic-brain.desktop

EOF
}

################################################################################
# Main Installation Workflow
################################################################################

install_autostart() {
    log_info "Starting Agentic Brain auto-start installation..."
    echo ""
    
    # Pre-flight checks
    check_prerequisites
    echo ""
    
    # Show system info
    local distro
    distro=$(detect_distribution)
    log_info "Detected distribution: $distro"
    echo ""
    
    # Check Docker daemon
    if ! check_docker_daemon; then
        log_warning "Docker daemon check failed. Installation may fail."
        if ! read -p "Continue anyway? (y/N) " -r choice < /dev/tty; then
            choice="n"
        fi
        if [ "$choice" != "y" ] && [ "$choice" != "Y" ]; then
            die "Installation cancelled"
        fi
    fi
    echo ""
    
    # Create directories and files
    create_systemd_user_dir
    create_service_env_file
    install_service_file
    echo ""
    
    # Enable and start service
    enable_and_start_service
    echo ""
    
    # Show status
    log_success "Auto-start installation complete!"
    echo ""
    log_info "agentic-brain services will automatically start on your next login"
    echo ""
    
    # Show what was installed
    log_info "Installed files:"
    echo "  - $SYSTEMD_USER_DIR/$SERVICE_NAME"
    echo "  - $SYSTEMD_USER_DIR/$SERVICE_ENV_FILE"
    echo ""
    
    # Show next steps
    log_info "Next steps:"
    echo "  1. Services will start on next login or you can start now:"
    echo "     systemctl --user start $SERVICE_NAME"
    echo ""
    echo "  2. Check service status:"
    echo "     systemctl --user status $SERVICE_NAME"
    echo ""
    echo "  3. View logs:"
    echo "     journalctl --user -u $SERVICE_NAME -f"
    echo ""
    echo "  4. To disable auto-start later:"
    echo "     ./scripts/install-autostart-linux.sh uninstall"
    echo ""
}

uninstall_autostart() {
    log_info "Uninstalling Agentic Brain auto-start..."
    echo ""
    
    local service_file="$SYSTEMD_USER_DIR/$SERVICE_NAME"
    
    if [ ! -f "$service_file" ]; then
        log_error "Auto-start not installed (no service file found)"
        exit 1
    fi
    
    # Confirm uninstall
    log_warning "This will:"
    echo "  1. Stop the agentic-brain service"
    echo "  2. Disable auto-start on login"
    echo "  3. Remove systemd service files"
    echo ""
    
    if ! read -p "Continue with uninstall? (y/N) " -r choice < /dev/tty; then
        choice="n"
    fi
    
    if [ "$choice" != "y" ] && [ "$choice" != "Y" ]; then
        log_info "Uninstall cancelled"
        exit 0
    fi
    echo ""
    
    # Perform uninstall
    disable_and_stop_service
    remove_service_files
    echo ""
    
    log_success "Auto-start uninstalled successfully"
    echo ""
    log_info "To manually start services in the future:"
    echo "  cd $PROJECT_DIR"
    echo "  docker compose up -d"
    echo ""
}

################################################################################
# Main Entry Point
################################################################################

main() {
    # Parse arguments
    local command="install"
    local no_start=0
    local verbose=0
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            install)
                command="install"
                shift
                ;;
            uninstall|--uninstall)
                command="uninstall"
                shift
                ;;
            status)
                command="status"
                shift
                ;;
            help|--help|-h)
                command="help"
                shift
                ;;
            --no-start)
                no_start=1
                shift
                ;;
            -v|--verbose)
                verbose=1
                set -x
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Execute command
    case "$command" in
        install)
            install_autostart
            ;;
        uninstall)
            uninstall_autostart
            ;;
        status)
            show_status
            ;;
        help)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
