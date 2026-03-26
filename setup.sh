#!/bin/bash
#
# Agentic Brain Setup Script
# Based on Freqtrade's legendary installer pattern
#
# Usage:
#   ./setup.sh -i         Install (fresh setup)
#   ./setup.sh -u         Update (git pull + reinstall)
#   ./setup.sh -r         Reset (hard reset + clean install)
#   ./setup.sh -c         Config (create new config)
#   ./setup.sh -h         Help
#
# Supports: macOS (M1/M2/Intel), Debian/Ubuntu, RedHat/CentOS/Fedora
#

set -e

# ============================================================
# Configuration
# ============================================================
VENV_DIR=".venv"
PYTHON_MIN_VERSION="3.10"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESET_BRANCH="main"

# ============================================================
# Colors and formatting
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ============================================================
# Helper functions
# ============================================================

# Cross-platform virtualenv activation (Windows Git Bash compatibility)
activate_venv() {
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        # Windows Git Bash / Cygwin uses Scripts/activate
        source "$VENV_DIR/Scripts/activate"
    else
        # macOS / Linux uses bin/activate
        source "$VENV_DIR/bin/activate"
    fi
}

echo_block() {
    local color="$1"
    shift
    echo ""
    echo -e "${color}============================================================${NC}"
    echo -e "${color}${BOLD}$*${NC}"
    echo -e "${color}============================================================${NC}"
    echo ""
}

echo_info() {
    echo -e "${BLUE}ℹ ${NC}$*"
}

echo_success() {
    echo -e "${GREEN}✔ ${NC}$*"
}

echo_warning() {
    echo -e "${YELLOW}⚠ ${NC}$*"
}

echo_error() {
    echo -e "${RED}✘ ${NC}$*"
}

echo_step() {
    echo -e "${CYAN}→ ${NC}$*"
}

# ============================================================
# OS Detection
# ============================================================
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS_TYPE="macos"
        # Detect ARM vs Intel
        if [[ "$(uname -m)" == "arm64" ]]; then
            ARCH="arm64"
            echo_info "Detected: macOS Apple Silicon (M1/M2/M3)"
        else
            ARCH="x86_64"
            echo_info "Detected: macOS Intel"
        fi
    elif [[ -f /etc/debian_version ]]; then
        OS_TYPE="debian"
        ARCH="$(uname -m)"
        # Check if running in WSL
        if grep -qi microsoft /proc/version 2>/dev/null; then
            echo_info "Detected: WSL (Windows Subsystem for Linux) - Ubuntu/Debian"
        else
            echo_info "Detected: Debian/Ubuntu Linux"
        fi
    elif [[ -f /etc/redhat-release ]]; then
        OS_TYPE="redhat"
        ARCH="$(uname -m)"
        echo_info "Detected: RedHat/CentOS/Fedora Linux"
    elif [[ -f /etc/arch-release ]]; then
        OS_TYPE="arch"
        ARCH="$(uname -m)"
        echo_info "Detected: Arch Linux"
    elif grep -qi microsoft /proc/version 2>/dev/null; then
        # WSL without standard distro files
        OS_TYPE="debian"
        ARCH="$(uname -m)"
        echo_info "Detected: WSL (Windows Subsystem for Linux)"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ -n "$WINDIR" ]]; then
        OS_TYPE="windows"
        ARCH="$(uname -m)"
        echo_warning "Detected: Windows (Git Bash/MSYS/Cygwin)"
        echo_info "For best results on Windows, use setup.ps1 or WSL"
    else
        OS_TYPE="linux"
        ARCH="$(uname -m)"
        echo_info "Detected: Generic Linux"
    fi
}

# ============================================================
# Python Detection
# ============================================================
detect_python() {
    echo_step "Detecting Python installation..."
    
    # Check for uv first (faster)
    if command -v uv &> /dev/null; then
        UV_AVAILABLE=true
        echo_success "uv found (fast mode available)"
    else
        UV_AVAILABLE=false
    fi
    
    # Try common Python binaries
    for py in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$py" &> /dev/null; then
            PY_VERSION=$("$py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            PY_MAJOR=$("$py" -c 'import sys; print(sys.version_info.major)')
            PY_MINOR=$("$py" -c 'import sys; print(sys.version_info.minor)')
            
            if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 10 ]]; then
                PYTHON_BIN="$py"
                echo_success "Found Python $PY_VERSION at $(which "$py")"
                return 0
            fi
        fi
    done
    
    echo_error "Python 3.10+ not found!"
    echo_info "Please install Python 3.10 or higher:"
    case "$OS_TYPE" in
        macos)
            echo "    brew install python@3.12"
            ;;
        debian)
            echo "    sudo apt install python3.12 python3.12-venv python3.12-dev"
            ;;
        redhat)
            echo "    sudo dnf install python3.12 python3.12-devel"
            ;;
        *)
            echo "    Visit https://python.org/downloads"
            ;;
    esac
    exit 1
}

# ============================================================
# Check required tools
# ============================================================
check_required_tools() {
    echo_step "Checking required tools..."
    local missing=()
    
    for tool in git curl; do
        if ! command -v "$tool" &> /dev/null; then
            missing+=("$tool")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo_error "Missing required tools: ${missing[*]}"
        echo_info "Please install them first:"
        case "$OS_TYPE" in
            macos)
                echo "    brew install ${missing[*]}"
                ;;
            debian)
                echo "    sudo apt install ${missing[*]}"
                ;;
            redhat)
                echo "    sudo dnf install ${missing[*]}"
                ;;
        esac
        exit 1
    fi
    
    echo_success "All required tools found"
}

# ============================================================
# Install system dependencies
# ============================================================
install_system_deps() {
    echo_block "$PURPLE" "Installing System Dependencies"
    
    case "$OS_TYPE" in
        macos)
            echo_step "Installing macOS dependencies via Homebrew..."
            if ! command -v brew &> /dev/null; then
                echo_error "Homebrew not found. Install it first:"
                echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
                exit 1
            fi
            
            # Core dependencies
            brew install openssl readline sqlite3 xz zlib 2>/dev/null || true
            
            # Optional but recommended
            if [[ "$ARCH" == "arm64" ]]; then
                echo_info "Apple Silicon detected - Metal GPU acceleration available"
            fi
            echo_success "macOS dependencies installed"
            ;;
            
        debian)
            echo_step "Installing Debian/Ubuntu dependencies..."
            sudo apt-get update
            sudo apt-get install -y \
                build-essential \
                libssl-dev \
                libffi-dev \
                python3-dev \
                python3-pip \
                python3-venv \
                git \
                curl
            echo_success "Debian dependencies installed"
            ;;
            
        redhat)
            echo_step "Installing RedHat/CentOS/Fedora dependencies..."
            if command -v dnf &> /dev/null; then
                PKG_MGR="dnf"
            else
                PKG_MGR="yum"
            fi
            sudo $PKG_MGR install -y \
                gcc \
                gcc-c++ \
                make \
                openssl-devel \
                libffi-devel \
                python3-devel \
                python3-pip \
                git \
                curl
            echo_success "RedHat dependencies installed"
            ;;
            
        arch)
            echo_step "Installing Arch dependencies..."
            sudo pacman -S --noconfirm \
                base-devel \
                openssl \
                python \
                python-pip \
                git \
                curl
            echo_success "Arch dependencies installed"
            ;;
            
        *)
            echo_warning "Unknown OS - skipping system deps (install manually if needed)"
            ;;
    esac
}

# ============================================================
# Create/recreate virtualenv
# ============================================================
setup_virtualenv() {
    echo_block "$BLUE" "Setting Up Virtual Environment"
    
    cd "$SCRIPT_DIR"
    
    # Remove existing venv if resetting
    if [[ "$RESET_VENV" == "true" && -d "$VENV_DIR" ]]; then
        echo_step "Removing existing virtualenv..."
        rm -rf "$VENV_DIR"
    fi
    
    # Create virtualenv
    if [[ ! -d "$VENV_DIR" ]]; then
        echo_step "Creating virtualenv in $VENV_DIR..."
        
        if [[ "$UV_AVAILABLE" == "true" ]]; then
            echo_info "Using uv for fast venv creation"
            uv venv "$VENV_DIR" --python "$PYTHON_BIN"
        else
            "$PYTHON_BIN" -m venv "$VENV_DIR"
        fi
        
        echo_success "Virtualenv created"
    else
        echo_info "Virtualenv already exists"
    fi
    
    # Activate virtualenv (cross-platform)
    activate_venv
    
    # Upgrade pip
    echo_step "Upgrading pip..."
    if [[ "$UV_AVAILABLE" == "true" ]]; then
        uv pip install --upgrade pip wheel setuptools
    else
        pip install --upgrade pip wheel setuptools
    fi
    
    echo_success "Virtualenv ready"
}

# ============================================================
# Install Python dependencies
# ============================================================
install_python_deps() {
    echo_block "$GREEN" "Installing Python Dependencies"
    
    cd "$SCRIPT_DIR"
    activate_venv
    
    # Install from pyproject.toml with extras
    echo_step "Installing agentic-brain with all extras..."
    
    if [[ "$UV_AVAILABLE" == "true" ]]; then
        echo_info "Using uv for fast installation"
        uv pip install -e ".[all,dev]"
    else
        # Standard pip
        pip install -e ".[all,dev]"
    fi
    
    echo_success "Python dependencies installed"
    
    # Show installed version
    local VERSION=$(pip show agentic-brain 2>/dev/null | grep "^Version:" | cut -d' ' -f2)
    if [[ -n "$VERSION" ]]; then
        echo_info "Installed agentic-brain version: $VERSION"
    fi
}

# ============================================================
# Install UI (if available)
# ============================================================
install_ui() {
    echo_block "$CYAN" "Installing UI Dashboard"
    
    # Check if there's a UI installation command
    if python -c "from agentic_brain.cli import install_ui" 2>/dev/null; then
        echo_step "Installing UI dashboard..."
        python -m agentic_brain.cli install-ui || true
        echo_success "UI installation attempted"
    else
        echo_info "No UI installer found - skipping"
    fi
}

# ============================================================
# Generate config
# ============================================================
generate_config() {
    echo_block "$YELLOW" "Configuration Setup"
    
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            echo_step "Creating .env from example..."
            cp .env.example .env
            echo_success ".env file created"
            echo_info "Edit .env to add your API keys and settings"
        else
            echo_step "Creating minimal .env..."
            cat > .env << 'EOF'
# Agentic Brain Configuration
# Generated by setup.sh

# LLM Provider (ollama, openai, anthropic, openrouter)
AGENTIC_LLM_PROVIDER=ollama
AGENTIC_LLM_MODEL=llama3.2:3b

# Optional: OpenAI
# OPENAI_API_KEY=sk-...

# Optional: Anthropic
# ANTHROPIC_API_KEY=sk-ant-...

# Optional: OpenRouter
# OPENROUTER_API_KEY=sk-or-...

# Optional: Neo4j (memory)
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=password

# API Server
AGENTIC_HOST=0.0.0.0
AGENTIC_PORT=8000
EOF
            echo_success ".env file created with defaults"
        fi
    else
        echo_info ".env already exists - keeping existing config"
    fi
}

# ============================================================
# Git update
# ============================================================
git_update() {
    echo_block "$PURPLE" "Updating from Git"
    
    cd "$SCRIPT_DIR"
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        echo_warning "You have uncommitted changes"
        echo_info "Stashing changes..."
        git stash push -m "setup.sh auto-stash $(date +%Y%m%d_%H%M%S)"
    fi
    
    # Pull latest
    echo_step "Pulling latest changes..."
    git pull origin "$RESET_BRANCH"
    
    echo_success "Git update complete"
}

# ============================================================
# Git reset
# ============================================================
git_reset() {
    echo_block "$RED" "Hard Reset to origin/$RESET_BRANCH"
    
    cd "$SCRIPT_DIR"
    
    echo_warning "This will DISCARD all local changes!"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo_info "Reset cancelled"
        return
    fi
    
    echo_step "Fetching latest..."
    git fetch origin
    
    echo_step "Hard resetting to origin/$RESET_BRANCH..."
    git reset --hard "origin/$RESET_BRANCH"
    
    echo_step "Cleaning untracked files..."
    git clean -fd
    
    echo_success "Repository reset complete"
}

# ============================================================
# Show post-install message
# ============================================================
show_post_install() {
    echo_block "$GREEN" "🎉 Installation Complete!"
    
    echo -e "${BOLD}Activate the environment:${NC}"
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        echo -e "    ${CYAN}source $VENV_DIR/Scripts/activate${NC}"
    else
        echo -e "    ${CYAN}source $VENV_DIR/bin/activate${NC}"
    fi
    echo ""
    
    echo -e "${BOLD}Quick Start:${NC}"
    echo -e "    ${CYAN}agentic-brain --help${NC}          Show all commands"
    echo -e "    ${CYAN}agentic-brain chat${NC}            Start interactive chat"
    echo -e "    ${CYAN}agentic-brain serve${NC}           Start API server"
    echo ""
    
    echo -e "${BOLD}Configuration:${NC}"
    echo -e "    Edit ${CYAN}.env${NC} to configure API keys and settings"
    echo ""
    
    if [[ "$OS_TYPE" == "macos" && "$ARCH" == "arm64" ]]; then
        echo -e "${BOLD}🍎 Apple Silicon Detected:${NC}"
        echo -e "    Metal GPU acceleration is automatically enabled"
        echo ""
    fi
    
    echo -e "${BOLD}Documentation:${NC}"
    echo -e "    ${CYAN}https://github.com/ecomlounge/brain${NC}"
    echo ""
}

# ============================================================
# Show help
# ============================================================
show_help() {
    echo ""
    echo -e "${BOLD}Agentic Brain Setup Script${NC}"
    echo ""
    echo "Usage: ./setup.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -i, --install     Fresh installation (default)"
    echo "  -u, --update      Update (git pull + reinstall deps)"
    echo "  -r, --reset       Hard reset and clean install"
    echo "  -c, --config      Generate/regenerate config files"
    echo "  -d, --deps-only   Install system dependencies only"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./setup.sh -i            # Fresh install"
    echo "  ./setup.sh -u            # Pull latest and update"
    echo "  ./setup.sh -r            # Nuclear option - reset everything"
    echo ""
}

# ============================================================
# Main installation routine
# ============================================================
do_install() {
    echo_block "$GREEN" "🧠 Agentic Brain Installation"
    
    detect_os
    detect_python
    check_required_tools
    install_system_deps
    
    RESET_VENV="false"
    setup_virtualenv
    install_python_deps
    install_ui
    generate_config
    
    show_post_install
}

# ============================================================
# Update routine
# ============================================================
do_update() {
    echo_block "$BLUE" "🔄 Agentic Brain Update"
    
    detect_os
    detect_python
    
    git_update
    
    # Keep existing venv, just update packages
    RESET_VENV="false"
    setup_virtualenv
    install_python_deps
    
    show_post_install
}

# ============================================================
# Reset routine
# ============================================================
do_reset() {
    echo_block "$RED" "🔥 Agentic Brain Reset"
    
    detect_os
    detect_python
    
    git_reset
    
    # Recreate venv from scratch
    RESET_VENV="true"
    setup_virtualenv
    install_python_deps
    generate_config
    
    show_post_install
}

# ============================================================
# Parse arguments and run
# ============================================================
main() {
    cd "$SCRIPT_DIR"
    
    case "${1:-}" in
        -i|--install|"")
            do_install
            ;;
        -u|--update)
            do_update
            ;;
        -r|--reset)
            do_reset
            ;;
        -c|--config)
            generate_config
            ;;
        -d|--deps-only)
            detect_os
            install_system_deps
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main
main "$@"
