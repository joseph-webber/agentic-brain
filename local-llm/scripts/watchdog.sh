#!/bin/bash
# =============================================================================
# OLLAMA WATCHDOG - Military-Grade Reliability
# =============================================================================
# Runs every minute via cron/launchd
# Ensures Ollama is ALWAYS running and responsive
# =============================================================================

LOG="/tmp/ollama-watchdog.log"
API="http://localhost:11434"
MAX_LOG_SIZE=1048576  # 1MB

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

# Rotate log if too big
if [ -f "$LOG" ] && [ $(stat -f%z "$LOG" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]; then
    mv "$LOG" "$LOG.old"
fi

# Check 1: Is process running?
if ! pgrep -x "ollama" > /dev/null 2>&1; then
    log "❌ ALERT: Ollama process not running - RESTARTING"
    
    # Start fresh
    /opt/homebrew/bin/ollama serve &>/dev/null &
    sleep 5
    
    if pgrep -x "ollama" > /dev/null 2>&1; then
        log "✅ RECOVERED: Ollama restarted successfully"
    else
        log "❌ CRITICAL: Failed to restart Ollama"
        # Try launchctl as backup
        launchctl kickstart -k gui/$(id -u)/com.brain.ollama 2>/dev/null
    fi
    exit 0
fi

# Check 2: Is API responsive?
if ! curl -s --max-time 10 "$API/api/tags" > /dev/null 2>&1; then
    log "❌ ALERT: Ollama API not responding - attempting restart"
    
    # Get PIDs and stop them
    for pid in $(pgrep -x ollama); do
        kill -9 "$pid" 2>/dev/null
    done
    sleep 3
    
    /opt/homebrew/bin/ollama serve &>/dev/null &
    sleep 5
    
    if curl -s --max-time 10 "$API/api/tags" > /dev/null 2>&1; then
        log "✅ RECOVERED: Ollama API now responding"
    else
        log "❌ CRITICAL: Ollama API still not responding"
    fi
    exit 0
fi

# All good - silent success (don't spam log)
