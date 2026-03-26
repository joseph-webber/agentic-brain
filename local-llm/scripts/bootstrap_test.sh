#!/bin/bash
# =============================================================================
# Bootstrap Test - Verify Ollama is properly installed and running
# =============================================================================
# This is the FIRST test to run. If this fails, nothing else will work.
# Run this after installation and after every reboot.
#
# Exit codes:
#   0 = All checks passed
#   1 = Critical failure (Ollama not working)
#   2 = Warning (working but suboptimal)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERBOSE=${VERBOSE:-0}
PASSED=0
FAILED=0
WARNINGS=0

# Colors (if terminal supports)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

log_pass() { echo -e "${GREEN}✅ PASS${NC}: $1"; ((PASSED++)); }
log_fail() { echo -e "${RED}❌ FAIL${NC}: $1"; ((FAILED++)); }
log_warn() { echo -e "${YELLOW}⚠️  WARN${NC}: $1"; ((WARNINGS++)); }
log_info() { echo -e "${BLUE}ℹ️  INFO${NC}: $1"; }

echo "=========================================="
echo "🦙 OLLAMA BOOTSTRAP TEST"
echo "=========================================="
echo ""

# -----------------------------------------------------------------------------
# Test 1: Ollama Binary Exists
# -----------------------------------------------------------------------------
echo "1. Checking Ollama installation..."

if command -v ollama &> /dev/null; then
    OLLAMA_PATH=$(which ollama)
    log_pass "Ollama binary found: $OLLAMA_PATH"
    
    # Get version
    VERSION=$(ollama --version 2>/dev/null || echo "unknown")
    log_info "Version: $VERSION"
else
    log_fail "Ollama not installed!"
    echo ""
    echo "   Install with: curl -fsSL https://ollama.ai/install.sh | sh"
    echo ""
    exit 1
fi

# -----------------------------------------------------------------------------
# Test 2: Ollama Process Running
# -----------------------------------------------------------------------------
echo ""
echo "2. Checking Ollama process..."

if pgrep -x "ollama" > /dev/null || pgrep -f "ollama serve" > /dev/null; then
    OLLAMA_PID=$(pgrep -x "ollama" 2>/dev/null || pgrep -f "ollama serve" | head -1)
    log_pass "Ollama process running (PID: $OLLAMA_PID)"
else
    log_fail "Ollama process not running!"
    echo ""
    echo "   Start with: ollama serve &"
    echo "   Or run: ./scripts/setup_autostart.sh"
    echo ""
    
    # Try to start it
    echo "   Attempting to start Ollama..."
    ollama serve &>/dev/null &
    sleep 3
    
    if pgrep -x "ollama" > /dev/null; then
        log_warn "Started Ollama manually (not auto-starting)"
    else
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# Test 3: API Responding
# -----------------------------------------------------------------------------
echo ""
echo "3. Checking API endpoint..."

API_URL="http://localhost:11434"
MAX_RETRIES=5
RETRY_DELAY=2

for i in $(seq 1 $MAX_RETRIES); do
    if curl -s --max-time 5 "$API_URL/api/tags" > /dev/null 2>&1; then
        log_pass "API responding at $API_URL"
        break
    fi
    
    if [ $i -eq $MAX_RETRIES ]; then
        log_fail "API not responding at $API_URL"
        echo "   Check logs: cat /tmp/ollama.error.log"
        exit 1
    fi
    
    log_info "Waiting for API... (attempt $i/$MAX_RETRIES)"
    sleep $RETRY_DELAY
done

# -----------------------------------------------------------------------------
# Test 4: Models Available
# -----------------------------------------------------------------------------
echo ""
echo "4. Checking available models..."

MODELS_JSON=$(curl -s "$API_URL/api/tags" 2>/dev/null)
MODEL_COUNT=$(echo "$MODELS_JSON" | grep -o '"name"' | wc -l | tr -d ' ')

if [ "$MODEL_COUNT" -gt 0 ]; then
    log_pass "$MODEL_COUNT model(s) available"
    
    # List models
    echo ""
    echo "   Available models:"
    echo "$MODELS_JSON" | grep -o '"name":"[^"]*"' | sed 's/"name":"//g; s/"//g' | while read model; do
        echo "     - $model"
    done
else
    log_warn "No models installed!"
    echo "   Install with: ollama pull llama3.2:3b"
fi

# -----------------------------------------------------------------------------
# Test 5: Auto-Start Configured
# -----------------------------------------------------------------------------
echo ""
echo "5. Checking auto-start configuration..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    PLIST="$HOME/Library/LaunchAgents/com.ollama.serve.plist"
    
    if [ -f "$PLIST" ]; then
        if launchctl list 2>/dev/null | grep -q "com.ollama.serve"; then
            log_pass "LaunchAgent configured and loaded"
        else
            log_warn "LaunchAgent exists but not loaded"
            echo "   Load with: launchctl load $PLIST"
        fi
    else
        log_warn "No LaunchAgent configured (won't auto-start on boot)"
        echo "   Configure with: ./scripts/setup_autostart.sh"
    fi
else
    # Linux
    if systemctl is-enabled ollama &>/dev/null; then
        log_pass "systemd service enabled"
    else
        log_warn "systemd service not enabled"
        echo "   Enable with: sudo systemctl enable ollama"
    fi
fi

# -----------------------------------------------------------------------------
# Test 6: GPU/Accelerator Detection
# -----------------------------------------------------------------------------
echo ""
echo "6. Checking hardware acceleration..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - Check for Apple Silicon
    CHIP=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")
    
    if echo "$CHIP" | grep -qi "Apple"; then
        log_pass "Apple Silicon detected: $CHIP (Metal acceleration)"
    else
        log_info "Intel Mac detected (no GPU acceleration)"
    fi
else
    # Linux - Check for NVIDIA
    if command -v nvidia-smi &>/dev/null; then
        GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
        if [ -n "$GPU" ]; then
            log_pass "NVIDIA GPU detected: $GPU"
        else
            log_warn "nvidia-smi found but no GPU detected"
        fi
    else
        log_info "No NVIDIA GPU detected (using CPU)"
    fi
fi

# -----------------------------------------------------------------------------
# Test 7: Memory Check
# -----------------------------------------------------------------------------
echo ""
echo "7. Checking system memory..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    TOTAL_RAM_BYTES=$(sysctl -n hw.memsize)
    TOTAL_RAM_GB=$((TOTAL_RAM_BYTES / 1024 / 1024 / 1024))
else
    TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
fi

if [ "$TOTAL_RAM_GB" -ge 16 ]; then
    log_pass "${TOTAL_RAM_GB}GB RAM (recommended for 8B models)"
elif [ "$TOTAL_RAM_GB" -ge 8 ]; then
    log_warn "${TOTAL_RAM_GB}GB RAM (sufficient for 3B models only)"
else
    log_fail "${TOTAL_RAM_GB}GB RAM (may struggle with LLMs)"
fi

# -----------------------------------------------------------------------------
# Test 8: Disk Space
# -----------------------------------------------------------------------------
echo ""
echo "8. Checking disk space..."

OLLAMA_DIR="$HOME/.ollama"
if [[ "$OSTYPE" == "darwin"* ]]; then
    AVAILABLE_GB=$(df -g "$HOME" | tail -1 | awk '{print $4}')
else
    AVAILABLE_GB=$(df -BG "$HOME" | tail -1 | awk '{print $4}' | tr -d 'G')
fi

if [ "$AVAILABLE_GB" -ge 50 ]; then
    log_pass "${AVAILABLE_GB}GB available (plenty of space)"
elif [ "$AVAILABLE_GB" -ge 20 ]; then
    log_warn "${AVAILABLE_GB}GB available (may fill up with multiple models)"
else
    log_fail "${AVAILABLE_GB}GB available (low disk space!)"
fi

# Check models directory size
if [ -d "$OLLAMA_DIR/models" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MODELS_SIZE=$(du -sh "$OLLAMA_DIR/models" 2>/dev/null | cut -f1)
    else
        MODELS_SIZE=$(du -sh "$OLLAMA_DIR/models" 2>/dev/null | cut -f1)
    fi
    log_info "Models directory: $MODELS_SIZE"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=========================================="
echo "BOOTSTRAP TEST SUMMARY"
echo "=========================================="
echo -e "  ${GREEN}Passed${NC}:   $PASSED"
echo -e "  ${RED}Failed${NC}:   $FAILED"
echo -e "  ${YELLOW}Warnings${NC}: $WARNINGS"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}❌ BOOTSTRAP FAILED${NC}"
    echo "   Fix the failures above before proceeding."
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  BOOTSTRAP PASSED WITH WARNINGS${NC}"
    echo "   Ollama is working but could be improved."
    exit 2
else
    echo -e "${GREEN}✅ BOOTSTRAP PASSED${NC}"
    echo "   Ollama is properly configured and ready!"
    exit 0
fi
