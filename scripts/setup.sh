#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MANAGER="${SCRIPT_DIR}/launchd-manager.py"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

success() {
    echo -e "${GREEN}✔${NC} $*"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $*"
}

error() {
    echo -e "${RED}✘${NC} $*" >&2
}

usage() {
    cat <<EOF
Agentic Brain launchd setup

Usage:
  ./scripts/setup.sh [install|uninstall|status|logs] [args...]

Commands:
  install      Validate environment, create directories, set permissions, install agents
  uninstall    Remove installed LaunchAgents
  status       Show launchd status for all agentic-brain services
  logs         Show recent launchd logs (pass through to launchd-manager.py)

Examples:
  ./scripts/setup.sh
  ./scripts/setup.sh install
  ./scripts/setup.sh status
  ./scripts/setup.sh logs --label daemon --lines 100
EOF
}

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        error "Missing required command: $cmd"
        exit 1
    fi
}

validate_environment() {
    info "Validating macOS launchd environment"

    if [[ "$(uname -s)" != "Darwin" ]]; then
        error "launchd setup is only supported on macOS"
        exit 1
    fi

    require_cmd launchctl
    require_cmd plutil
    require_cmd python3

    if [[ ! -d "${PROJECT_DIR}/launchd" ]]; then
        error "Missing launchd template directory: ${PROJECT_DIR}/launchd"
        exit 1
    fi

    if [[ ! -f "${PROJECT_DIR}/src/agentic_brain/api/server.py" ]]; then
        error "Could not find agentic-brain server source under ${PROJECT_DIR}/src"
        exit 1
    fi

    local runtime_python=""
    if [[ -x "${PROJECT_DIR}/.venv/bin/python" ]]; then
        runtime_python="${PROJECT_DIR}/.venv/bin/python"
    elif [[ -x "${PROJECT_DIR}/venv/bin/python" ]]; then
        runtime_python="${PROJECT_DIR}/venv/bin/python"
    else
        runtime_python="$(command -v python3)"
    fi

    if ! PYTHONPATH="${PROJECT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}" \
        "${runtime_python}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
        error "Python runtime at ${runtime_python} is missing FastAPI/Uvicorn dependencies"
        echo "    Install the project dependencies before enabling launchd services." >&2
        echo "    Example: ./setup.sh -i  (repo root installer)" >&2
        exit 1
    fi

    success "Environment validation passed"
}

create_directories() {
    info "Creating runtime directories"
    mkdir -p \
        "${PROJECT_DIR}/logs/launchd" \
        "${PROJECT_DIR}/backups/launchd" \
        "${PROJECT_DIR}/run/launchd" \
        "${HOME}/Library/LaunchAgents"
    success "Directories ready"
}

set_permissions() {
    info "Setting permissions"
    chmod 755 "${MANAGER}" "${SCRIPT_DIR}/setup.sh"
    chmod 644 "${PROJECT_DIR}"/launchd/*.plist
    success "Permissions updated"
}

install_launchd() {
    validate_environment
    create_directories
    set_permissions

    info "Installing launchd services"
    python3 "${MANAGER}" install
    success "Launchd services installed"
}

main() {
    local command="${1:-install}"
    shift || true

    case "${command}" in
        install)
            install_launchd
            ;;
        uninstall|status|logs)
            python3 "${MANAGER}" "${command}" "$@"
            ;;
        -h|--help|help)
            usage
            ;;
        *)
            error "Unknown command: ${command}"
            usage
            exit 1
            ;;
    esac
}

main "$@"
