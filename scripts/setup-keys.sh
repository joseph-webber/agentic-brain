#!/bin/bash

################################################################################
# API Keys Setup Helper for Brain
################################################################################
# This is an INTERACTIVE setup script to help you configure API keys for the
# Brain system. It will:
#   1. Ask you for API keys (with helpful explanations)
#   2. Create .env files for local development and Docker
#   3. Auto-detect the best default provider based on your keys
#   4. Offer to restart Docker containers
#
# IMPORTANT: This script uses PLACEHOLDERS ONLY. No real keys are stored here.
# All keys are entered directly by you during setup.
#
# Works on: Mac, Linux, Windows (Git Bash)
################################################################################

set -euo pipefail

# Color definitions for cross-platform compatibility
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Detect OS for cross-platform compatibility
OS_TYPE=$(uname -s)
case "$OS_TYPE" in
  Darwin*) OS="Mac" ;;
  Linux*) OS="Linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS="Windows" ;;
  *) OS="Unknown" ;;
esac

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_DOCKER_FILE="$PROJECT_ROOT/.env.docker"

################################################################################
# Helper Functions
################################################################################

print_header() {
  echo ""
  echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║${NC}         API Keys Setup Helper for Brain System              ${CYAN}║${NC}"
  echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
  echo ""
}

print_section() {
  echo ""
  echo -e "${BLUE}► $1${NC}"
}

print_info() {
  echo -e "${CYAN}ℹ $1${NC}"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
  echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
  echo -e "${RED}✗ $1${NC}"
}

prompt_key() {
  local provider_name="$1"
  local provider_code="$2"
  local is_free="$3"
  local docs_url="$4"
  local description="$5"

  echo ""
  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}$provider_name${NC}"
  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  
  if [ "$is_free" = "free" ]; then
    echo -e "${GREEN}💰 FREE${NC} - No cost"
  else
    echo -e "${YELLOW}💵 PAID${NC} - Requires subscription or credits"
  fi
  
  echo -e "📖 ${description}"
  echo -e "🔗 Get API Key: ${docs_url}"
  echo ""
  
  read -p "$(echo -e ${CYAN}Enter your ${provider_name} API key${NC} [press Enter to skip]: )" api_key

  if [ -z "$api_key" ]; then
    return 1
  else
    echo "$api_key"
    return 0
  fi
}

save_env_file() {
  local filepath="$1"
  local content="$2"
  
  if [ -f "$filepath" ]; then
    print_warning "File exists: $filepath"
    read -p "Overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      print_info "Skipped: $filepath"
      return
    fi
  fi
  
  echo "$content" > "$filepath"
  print_success "Created: $filepath"
}

################################################################################
# Main Script
################################################################################

print_header

# Initialize variables
OLLAMA_KEY=""
GROQ_KEY=""
GOOGLE_GEMINI_KEY=""
OPENAI_KEY=""
ANTHROPIC_KEY=""
XAI_KEY=""
DEFAULT_PROVIDER=""
PROVIDED_COUNT=0

print_section "API Keys Configuration"
print_info "You'll be prompted for each API key. You can skip any by pressing Enter."
echo ""

# 1. Ollama (Local, Free)
if key=$(prompt_key "Ollama" "OLLAMA" "free" "https://ollama.ai" "Free, runs locally on your machine"); then
  OLLAMA_KEY="$key"
  ((PROVIDED_COUNT++))
  DEFAULT_PROVIDER="ollama"
  print_success "Ollama key configured"
fi

# 2. Groq (Free)
if key=$(prompt_key "Groq" "GROQ" "free" "https://console.groq.com" "Free cloud API with fast inference"); then
  GROQ_KEY="$key"
  ((PROVIDED_COUNT++))
  DEFAULT_PROVIDER="groq"
  print_success "Groq key configured"
fi

# 3. Google Gemini (Free tier available)
if key=$(prompt_key "Google Gemini" "GOOGLE_GEMINI" "free" "https://aistudio.google.com/apikey" "Free tier available, Google AI Studio"); then
  GOOGLE_GEMINI_KEY="$key"
  ((PROVIDED_COUNT++))
  DEFAULT_PROVIDER="google"
  print_success "Google Gemini key configured"
fi

# 4. OpenAI (Paid)
if key=$(prompt_key "OpenAI" "OPENAI" "paid" "https://platform.openai.com/api-keys" "GPT-4, GPT-3.5 - requires credits"); then
  OPENAI_KEY="$key"
  ((PROVIDED_COUNT++))
  DEFAULT_PROVIDER="openai"
  print_success "OpenAI key configured"
fi

# 5. Anthropic (Paid)
if key=$(prompt_key "Anthropic" "ANTHROPIC" "paid" "https://console.anthropic.com" "Claude API - requires subscription"); then
  ANTHROPIC_KEY="$key"
  ((PROVIDED_COUNT++))
  DEFAULT_PROVIDER="anthropic"
  print_success "Anthropic key configured"
fi

# 6. xAI Grok (Paid)
if key=$(prompt_key "xAI Grok" "XAI" "paid" "https://console.x.ai" "Grok API - requires subscription"); then
  XAI_KEY="$key"
  ((PROVIDED_COUNT++))
  DEFAULT_PROVIDER="xai"
  print_success "xAI Grok key configured"
fi

# Check if at least one key was provided
if [ $PROVIDED_COUNT -eq 0 ]; then
  print_error "No API keys provided. Exiting."
  exit 1
fi

################################################################################
# Create .env file (local development)
################################################################################

print_section "Creating .env (Local Development)"

ENV_CONTENT="# Brain System - Local Development Environment
# Generated by setup-keys.sh

# API Keys
OLLAMA_API_KEY='$OLLAMA_KEY'
GROQ_API_KEY='$GROQ_KEY'
GOOGLE_GEMINI_API_KEY='$GOOGLE_GEMINI_KEY'
OPENAI_API_KEY='$OPENAI_KEY'
ANTHROPIC_API_KEY='$ANTHROPIC_KEY'
XAI_API_KEY='$XAI_KEY'

# Default Provider (auto-detected)
DEFAULT_LLM_PROVIDER='$DEFAULT_PROVIDER'

# Local Services
REDIS_HOST=localhost
REDIS_PORT=6379
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434

# Environment
NODE_ENV=development
LOG_LEVEL=debug
"

save_env_file "$ENV_FILE" "$ENV_CONTENT"

################################################################################
# Create .env.docker file (Docker environment)
################################################################################

print_section "Creating .env.docker (Docker Environment)"

ENV_DOCKER_CONTENT="# Brain System - Docker Environment
# Generated by setup-keys.sh

# API Keys (same as local)
OLLAMA_API_KEY='$OLLAMA_KEY'
GROQ_API_KEY='$GROQ_KEY'
GOOGLE_GEMINI_API_KEY='$GOOGLE_GEMINI_KEY'
OPENAI_API_KEY='$OPENAI_KEY'
ANTHROPIC_API_KEY='$ANTHROPIC_KEY'
XAI_API_KEY='$XAI_KEY'

# Default Provider (auto-detected)
DEFAULT_LLM_PROVIDER='$DEFAULT_PROVIDER'

# Docker Services (internal hostnames)
REDIS_HOST=redis
REDIS_PORT=6379
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Ollama (via host.docker.internal for Mac/Windows, localhost for Linux)
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Environment
NODE_ENV=production
LOG_LEVEL=info
"

save_env_file "$ENV_DOCKER_FILE" "$ENV_DOCKER_CONTENT"

################################################################################
# Docker Container Management
################################################################################

print_section "Docker Container Management"

if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
  echo ""
  read -p "$(echo -e ${CYAN}Do you want to restart Docker containers?${NC} (y/N): )" -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Restarting Docker containers..."
    cd "$PROJECT_ROOT"
    if [ -f "docker-compose.yml" ]; then
      docker-compose down
      docker-compose up -d
      print_success "Docker containers restarted"
    else
      print_warning "docker-compose.yml not found in $PROJECT_ROOT"
    fi
  fi
else
  print_warning "Docker or Docker Compose not installed. Skipping container restart."
fi

################################################################################
# Summary
################################################################################

print_section "Setup Complete! 🎉"

echo ""
echo -e "${CYAN}✓ Configuration Summary:${NC}"
echo ""
echo "  Environment Files Created:"
echo "    • Local:  $ENV_FILE"
echo "    • Docker: $ENV_DOCKER_FILE"
echo ""
echo "  API Keys Configured:"
[ -n "$OLLAMA_KEY" ] && echo "    ✓ Ollama (Local)"
[ -n "$GROQ_KEY" ] && echo "    ✓ Groq"
[ -n "$GOOGLE_GEMINI_KEY" ] && echo "    ✓ Google Gemini"
[ -n "$OPENAI_KEY" ] && echo "    ✓ OpenAI"
[ -n "$ANTHROPIC_KEY" ] && echo "    ✓ Anthropic"
[ -n "$XAI_KEY" ] && echo "    ✓ xAI Grok"
echo ""
echo "  Default Provider: ${GREEN}$DEFAULT_PROVIDER${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Review the .env files to verify settings"
echo "  2. Keep API keys secure - never commit .env files to git"
echo "  3. Run: docker-compose up -d (to start services)"
echo "  4. Test your setup by running the brain"
echo ""
echo -e "${YELLOW}Security Reminder:${NC}"
echo "  • .env files contain API keys - handle with care"
echo "  • Add .env and .env.docker to .gitignore"
echo "  • Never share your API keys with anyone"
echo "  • Rotate keys regularly for security"
echo ""

print_success "Setup complete! Happy coding! 🚀"
echo ""
