#!/bin/bash
# =============================================================================
# Smoke Test - Verify each model can generate responses
# =============================================================================
# Tests that models are actually working, not just installed.
# Run after bootstrap_test.sh passes.
#
# Usage: ./smoke_test.sh [--all | --model MODEL_NAME]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_URL="http://localhost:11434"
TIMEOUT=120  # Seconds per model test

# Colors
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    NC=''
fi

log_pass() { echo -e "${GREEN}✅ PASS${NC}: $1"; }
log_fail() { echo -e "${RED}❌ FAIL${NC}: $1"; }
log_warn() { echo -e "${YELLOW}⚠️  WARN${NC}: $1"; }
log_info() { echo -e "${BLUE}ℹ️  INFO${NC}: $1"; }
log_test() { echo -e "${CYAN}🧪 TEST${NC}: $1"; }

echo "=========================================="
echo "🦙 OLLAMA SMOKE TEST"
echo "=========================================="
echo ""

# Check API is running
if ! curl -s --max-time 5 "$API_URL/api/tags" > /dev/null 2>&1; then
    log_fail "Ollama API not responding!"
    echo "   Run bootstrap_test.sh first."
    exit 1
fi

log_pass "API is responding"
echo ""

# Get list of models
MODELS_JSON=$(curl -s "$API_URL/api/tags")
MODELS=$(echo "$MODELS_JSON" | grep -o '"name":"[^"]*"' | sed 's/"name":"//g; s/"//g')

if [ -z "$MODELS" ]; then
    log_fail "No models installed!"
    echo "   Install with: ollama pull llama3.2:3b"
    exit 1
fi

# Filter models if specified
if [ "$1" == "--model" ] && [ -n "$2" ]; then
    MODELS="$2"
fi

# Count models
MODEL_COUNT=$(echo "$MODELS" | wc -l | tr -d ' ')
log_info "Testing $MODEL_COUNT model(s)"
echo ""

PASSED=0
FAILED=0

# Test each model
for MODEL in $MODELS; do
    echo "----------------------------------------"
    log_test "Model: $MODEL"
    
    # Measure response time
    START_TIME=$(date +%s.%N)
    
    # Send test prompt
    RESPONSE=$(curl -s --max-time $TIMEOUT "$API_URL/api/generate" \
        -d "{\"model\":\"$MODEL\",\"prompt\":\"Say hello in exactly 3 words.\",\"stream\":false}" 2>&1)
    
    END_TIME=$(date +%s.%N)
    DURATION=$(echo "$END_TIME - $START_TIME" | bc 2>/dev/null || echo "?")
    
    # Check response
    if echo "$RESPONSE" | grep -q '"done":true'; then
        # Extract the actual response text
        RESPONSE_TEXT=$(echo "$RESPONSE" | grep -o '"response":"[^"]*"' | head -1 | sed 's/"response":"//g; s/"//g' | head -c 100)
        
        log_pass "Response received in ${DURATION}s"
        echo "   Response: \"$RESPONSE_TEXT\""
        ((PASSED++))
        
        # Performance warning
        if [ "${DURATION%.*}" -gt 30 ]; then
            log_warn "Slow response (>30s) - model may not be cached"
        fi
    else
        log_fail "No valid response"
        
        # Check for common errors
        if echo "$RESPONSE" | grep -qi "not found"; then
            echo "   Error: Model not found (may need to pull)"
        elif echo "$RESPONSE" | grep -qi "timeout"; then
            echo "   Error: Request timed out (model too large?)"
        elif echo "$RESPONSE" | grep -qi "memory"; then
            echo "   Error: Out of memory"
        else
            echo "   Response: $(echo "$RESPONSE" | head -c 200)"
        fi
        ((FAILED++))
    fi
    echo ""
done

# Summary
echo "=========================================="
echo "SMOKE TEST SUMMARY"
echo "=========================================="
echo -e "  ${GREEN}Passed${NC}: $PASSED"
echo -e "  ${RED}Failed${NC}: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL MODELS WORKING${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME MODELS FAILED${NC}"
    exit 1
fi
