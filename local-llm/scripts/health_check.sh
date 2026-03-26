#!/bin/bash
# =============================================================================
# Health Check - Quick verification that Ollama is healthy
# =============================================================================
# Run periodically via cron or manually
# Can auto-restart Ollama if it's down
#
# Usage: ./health_check.sh [--auto-restart] [--quiet]
# =============================================================================

API_URL="http://localhost:11434"
AUTO_RESTART=false
QUIET=false

# Parse args
for arg in "$@"; do
    case $arg in
        --auto-restart) AUTO_RESTART=true ;;
        --quiet) QUIET=true ;;
    esac
done

log() {
    if [ "$QUIET" = false ]; then
        echo "$1"
    fi
}

# Check API responding
check_api() {
    curl -s --max-time 5 "$API_URL/api/tags" > /dev/null 2>&1
    return $?
}

# Check process running
check_process() {
    pgrep -x "ollama" > /dev/null 2>&1 || pgrep -f "ollama serve" > /dev/null 2>&1
    return $?
}

# Main health check
main() {
    local status=0
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    log "[$timestamp] Health Check"
    
    # Check 1: Process
    if check_process; then
        log "  ✅ Process: Running"
    else
        log "  ❌ Process: Not running"
        status=1
    fi
    
    # Check 2: API
    if check_api; then
        log "  ✅ API: Responding"
        
        # Check 3: Models (only if API working)
        MODEL_COUNT=$(curl -s "$API_URL/api/tags" | grep -o '"name"' | wc -l | tr -d ' ')
        if [ "$MODEL_COUNT" -gt 0 ]; then
            log "  ✅ Models: $MODEL_COUNT available"
        else
            log "  ⚠️  Models: None installed"
        fi
    else
        log "  ❌ API: Not responding"
        status=1
    fi
    
    # Auto-restart if needed
    if [ $status -ne 0 ] && [ "$AUTO_RESTART" = true ]; then
        log ""
        log "  🔄 Attempting restart..."
        
        # Kill any zombie processes
        pkill -9 ollama 2>/dev/null || true
        sleep 2
        
        # Start Ollama
        ollama serve &>/dev/null &
        sleep 5
        
        if check_api; then
            log "  ✅ Restart successful"
            status=0
        else
            log "  ❌ Restart failed"
        fi
    fi
    
    return $status
}

main
exit $?
