#!/bin/bash
# =============================================================================
# Performance Test - Measure response times and throughput
# =============================================================================
# Tests response latency for warm vs cold models
# Important for understanding client experience
#
# Usage: ./performance_test.sh [MODEL_NAME]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_URL="http://localhost:11434"
DEFAULT_MODEL="llama3.2:3b"
TEST_MODEL="${1:-$DEFAULT_MODEL}"

# Colors
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

log_pass() { echo -e "${GREEN}✅${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
log_info() { echo -e "${BLUE}ℹ️${NC} $1"; }

measure_time() {
    local start=$(date +%s.%N)
    eval "$1" > /dev/null 2>&1
    local end=$(date +%s.%N)
    echo "$end - $start" | bc
}

echo "=========================================="
echo "🦙 OLLAMA PERFORMANCE TEST"
echo "=========================================="
echo ""
echo "Model: $TEST_MODEL"
echo ""

# Check API
if ! curl -s --max-time 5 "$API_URL/api/tags" > /dev/null 2>&1; then
    echo "❌ Ollama API not responding!"
    exit 1
fi

# Check model exists
if ! curl -s "$API_URL/api/tags" | grep -q "\"$TEST_MODEL\""; then
    echo "❌ Model '$TEST_MODEL' not found!"
    echo "   Available models:"
    curl -s "$API_URL/api/tags" | grep -o '"name":"[^"]*"' | sed 's/"name":"//g; s/"//g' | sed 's/^/     - /'
    exit 1
fi

# -----------------------------------------------------------------------------
# Test 1: Cold Start (model not loaded)
# -----------------------------------------------------------------------------
echo "----------------------------------------"
echo "1. COLD START TEST"
echo "   (Unloading model first...)"
echo ""

# Unload all models
curl -s -X DELETE "$API_URL/api/models/unload" > /dev/null 2>&1 || true
sleep 2

# Time cold start
log_info "Starting cold request..."
COLD_START=$(date +%s.%N)

COLD_RESPONSE=$(curl -s --max-time 180 "$API_URL/api/generate" \
    -d "{\"model\":\"$TEST_MODEL\",\"prompt\":\"Hi\",\"stream\":false}")

COLD_END=$(date +%s.%N)
COLD_TIME=$(echo "$COLD_END - $COLD_START" | bc)

if echo "$COLD_RESPONSE" | grep -q '"done":true'; then
    echo "   Cold start time: ${COLD_TIME}s"
    
    if [ "${COLD_TIME%.*}" -le 10 ]; then
        log_pass "Excellent (<10s)"
    elif [ "${COLD_TIME%.*}" -le 30 ]; then
        log_warn "Acceptable (10-30s)"
    else
        log_warn "Slow (>30s) - consider smaller model or more RAM"
    fi
else
    echo "   ❌ Cold start failed"
    echo "   $COLD_RESPONSE"
fi

# -----------------------------------------------------------------------------
# Test 2: Warm Responses
# -----------------------------------------------------------------------------
echo ""
echo "----------------------------------------"
echo "2. WARM RESPONSE TEST"
echo "   (Model should be loaded now)"
echo ""

WARM_TIMES=()
NUM_TESTS=5

for i in $(seq 1 $NUM_TESTS); do
    START=$(date +%s.%N)
    
    RESPONSE=$(curl -s --max-time 60 "$API_URL/api/generate" \
        -d "{\"model\":\"$TEST_MODEL\",\"prompt\":\"Count to 3\",\"stream\":false}")
    
    END=$(date +%s.%N)
    TIME=$(echo "$END - $START" | bc)
    
    if echo "$RESPONSE" | grep -q '"done":true'; then
        WARM_TIMES+=("$TIME")
        echo "   Request $i: ${TIME}s"
    else
        echo "   Request $i: FAILED"
    fi
done

# Calculate average
if [ ${#WARM_TIMES[@]} -gt 0 ]; then
    SUM=0
    for t in "${WARM_TIMES[@]}"; do
        SUM=$(echo "$SUM + $t" | bc)
    done
    AVG=$(echo "scale=2; $SUM / ${#WARM_TIMES[@]}" | bc)
    
    echo ""
    echo "   Average warm response: ${AVG}s"
    
    if [ "${AVG%.*}" -le 2 ]; then
        log_pass "Excellent (<2s average)"
    elif [ "${AVG%.*}" -le 5 ]; then
        log_pass "Good (2-5s average)"
    else
        log_warn "Slow (>5s average)"
    fi
fi

# -----------------------------------------------------------------------------
# Test 3: Token Generation Speed
# -----------------------------------------------------------------------------
echo ""
echo "----------------------------------------"
echo "3. TOKEN GENERATION SPEED"
echo ""

log_info "Generating 100 tokens..."
START=$(date +%s.%N)

RESPONSE=$(curl -s --max-time 120 "$API_URL/api/generate" \
    -d "{\"model\":\"$TEST_MODEL\",\"prompt\":\"Write a short story about a robot.\",\"stream\":false,\"options\":{\"num_predict\":100}}")

END=$(date +%s.%N)
TIME=$(echo "$END - $START" | bc)

if echo "$RESPONSE" | grep -q '"done":true'; then
    # Extract token count from response
    EVAL_COUNT=$(echo "$RESPONSE" | grep -o '"eval_count":[0-9]*' | grep -o '[0-9]*')
    
    if [ -n "$EVAL_COUNT" ] && [ "$EVAL_COUNT" -gt 0 ]; then
        TOKENS_PER_SEC=$(echo "scale=1; $EVAL_COUNT / $TIME" | bc)
        echo "   Generated: $EVAL_COUNT tokens"
        echo "   Time: ${TIME}s"
        echo "   Speed: ${TOKENS_PER_SEC} tokens/second"
        
        if [ "${TOKENS_PER_SEC%.*}" -ge 30 ]; then
            log_pass "Excellent (≥30 tok/s)"
        elif [ "${TOKENS_PER_SEC%.*}" -ge 15 ]; then
            log_pass "Good (15-30 tok/s)"
        else
            log_warn "Slow (<15 tok/s)"
        fi
    else
        echo "   Time: ${TIME}s (token count not available)"
    fi
else
    echo "   ❌ Generation failed"
fi

# -----------------------------------------------------------------------------
# Test 4: Memory Usage
# -----------------------------------------------------------------------------
echo ""
echo "----------------------------------------"
echo "4. MEMORY USAGE"
echo ""

# Check what's loaded
LOADED=$(curl -s "$API_URL/api/ps" 2>/dev/null)

if [ -n "$LOADED" ]; then
    echo "   Currently loaded models:"
    echo "$LOADED" | grep -o '"name":"[^"]*"' | sed 's/"name":"//g; s/"//g' | while read model; do
        SIZE=$(echo "$LOADED" | grep -o "\"$model\"[^}]*\"size\":[0-9]*" | grep -o '"size":[0-9]*' | grep -o '[0-9]*')
        if [ -n "$SIZE" ]; then
            SIZE_GB=$(echo "scale=2; $SIZE / 1024 / 1024 / 1024" | bc)
            echo "     - $model (${SIZE_GB}GB)"
        else
            echo "     - $model"
        fi
    done
else
    echo "   (Unable to get loaded models info)"
fi

# System memory
if [[ "$OSTYPE" == "darwin"* ]]; then
    TOTAL_GB=$(sysctl -n hw.memsize | awk '{print $1/1024/1024/1024}')
    log_info "System RAM: ${TOTAL_GB}GB"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "=========================================="
echo "PERFORMANCE SUMMARY"
echo "=========================================="
echo ""
echo "Model: $TEST_MODEL"
echo ""
echo "┌─────────────────┬────────────────┐"
echo "│ Metric          │ Result         │"
echo "├─────────────────┼────────────────┤"
printf "│ Cold Start      │ %-14s │\n" "${COLD_TIME}s"
printf "│ Warm Average    │ %-14s │\n" "${AVG}s"
if [ -n "$TOKENS_PER_SEC" ]; then
    printf "│ Tokens/sec      │ %-14s │\n" "${TOKENS_PER_SEC}"
fi
echo "└─────────────────┴────────────────┘"
echo ""

# Performance rating
echo "PERFORMANCE RATING:"
if [ "${COLD_TIME%.*}" -le 10 ] && [ "${AVG%.*}" -le 3 ]; then
    echo -e "${GREEN}⭐⭐⭐ EXCELLENT${NC}"
    echo "   Ready for production use."
elif [ "${COLD_TIME%.*}" -le 30 ] && [ "${AVG%.*}" -le 5 ]; then
    echo -e "${GREEN}⭐⭐ GOOD${NC}"
    echo "   Acceptable for most use cases."
else
    echo -e "${YELLOW}⭐ NEEDS IMPROVEMENT${NC}"
    echo "   Consider:"
    echo "   - Using a smaller model (llama3.2:3b)"
    echo "   - Adding more RAM"
    echo "   - Keeping model warm with keep_alive"
fi
