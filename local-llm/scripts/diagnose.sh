#!/bin/bash
# =============================================================================
# Full Diagnostic - Comprehensive system report for troubleshooting
# =============================================================================
# Run this when something isn't working to gather all relevant info
#
# Usage: ./diagnose.sh [--save]
# =============================================================================

SAVE_REPORT=false
if [ "$1" = "--save" ]; then
    SAVE_REPORT=true
    REPORT_FILE="/tmp/ollama-diagnostic-$(date +%Y%m%d-%H%M%S).txt"
fi

output() {
    if [ "$SAVE_REPORT" = true ]; then
        echo "$1" | tee -a "$REPORT_FILE"
    else
        echo "$1"
    fi
}

section() {
    output ""
    output "============================================"
    output "$1"
    output "============================================"
}

echo "🦙 OLLAMA FULL DIAGNOSTIC"
echo ""

if [ "$SAVE_REPORT" = true ]; then
    echo "Saving report to: $REPORT_FILE"
    echo ""
fi

# System Info
section "SYSTEM INFORMATION"

output "Date: $(date)"
output "OS: $(uname -s) $(uname -r)"

if [[ "$OSTYPE" == "darwin"* ]]; then
    output "macOS: $(sw_vers -productVersion)"
    output "Chip: $(sysctl -n machdep.cpu.brand_string)"
    output "RAM: $(($(sysctl -n hw.memsize) / 1024 / 1024 / 1024))GB"
else
    output "Kernel: $(uname -r)"
    output "RAM: $(free -h | grep Mem | awk '{print $2}')"
fi

output "Disk Free: $(df -h ~ | tail -1 | awk '{print $4}')"

# Ollama Installation
section "OLLAMA INSTALLATION"

if command -v ollama &> /dev/null; then
    output "✅ Ollama installed: $(which ollama)"
    output "Version: $(ollama --version 2>/dev/null || echo 'unknown')"
else
    output "❌ Ollama not installed"
fi

# Process Status
section "PROCESS STATUS"

if pgrep -x "ollama" > /dev/null; then
    output "✅ Ollama process running"
    output ""
    output "Process details:"
    ps aux | grep -E "PID|ollama" | grep -v grep
else
    output "❌ Ollama process not running"
fi

# API Status
section "API STATUS"

API_URL="http://localhost:11434"

if curl -s --max-time 5 "$API_URL/api/tags" > /dev/null 2>&1; then
    output "✅ API responding at $API_URL"
else
    output "❌ API not responding"
    
    # Check port
    output ""
    output "Port 11434 status:"
    lsof -i :11434 2>/dev/null || output "  (no process on port)"
fi

# Models
section "INSTALLED MODELS"

MODELS=$(curl -s "$API_URL/api/tags" 2>/dev/null)

if [ -n "$MODELS" ]; then
    output "$(echo "$MODELS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for m in data.get('models', []):
        size_gb = m.get('size', 0) / 1024 / 1024 / 1024
        print(f\"  - {m['name']}: {size_gb:.1f}GB\")
except:
    print('  (unable to parse)')
" 2>/dev/null || echo "  (unable to parse)")"
else
    output "  (unable to get model list)"
fi

# Loaded Models
section "CURRENTLY LOADED MODELS"

LOADED=$(curl -s "$API_URL/api/ps" 2>/dev/null)

if [ -n "$LOADED" ] && echo "$LOADED" | grep -q "models"; then
    output "$(echo "$LOADED" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('models'):
        for m in data['models']:
            size_gb = m.get('size', 0) / 1024 / 1024 / 1024
            print(f\"  - {m['name']}: {size_gb:.1f}GB in RAM\")
    else:
        print('  (no models loaded)')
except:
    print('  (unable to parse)')
" 2>/dev/null || echo "  (unable to parse)")"
else
    output "  (no models currently loaded)"
fi

# Memory Usage
section "MEMORY USAGE"

if [[ "$OSTYPE" == "darwin"* ]]; then
    output "$(vm_stat | head -10)"
else
    output "$(free -h)"
fi

# Auto-Start Configuration
section "AUTO-START CONFIGURATION"

if [[ "$OSTYPE" == "darwin"* ]]; then
    PLIST="$HOME/Library/LaunchAgents/com.ollama.serve.plist"
    
    if [ -f "$PLIST" ]; then
        output "✅ LaunchAgent exists: $PLIST"
        
        if launchctl list 2>/dev/null | grep -q "com.ollama.serve"; then
            output "✅ LaunchAgent is loaded"
        else
            output "❌ LaunchAgent not loaded"
        fi
    else
        output "❌ No LaunchAgent configured"
    fi
else
    if systemctl is-enabled ollama &>/dev/null; then
        output "✅ systemd service enabled"
    else
        output "❌ systemd service not enabled"
    fi
fi

# Logs
section "RECENT LOGS"

if [ -f /tmp/ollama.log ]; then
    output "Last 20 lines of /tmp/ollama.log:"
    output ""
    tail -20 /tmp/ollama.log
else
    output "(no log file at /tmp/ollama.log)"
fi

if [ -f /tmp/ollama.error.log ]; then
    output ""
    output "Last 10 lines of /tmp/ollama.error.log:"
    output ""
    tail -10 /tmp/ollama.error.log
fi

# Quick Test
section "QUICK RESPONSE TEST"

output "Testing llama3.2:3b (if available)..."

TEST_START=$(date +%s)
TEST_RESPONSE=$(curl -s --max-time 60 "$API_URL/api/generate" \
    -d '{"model":"llama3.2:3b","prompt":"Say OK","stream":false}' 2>&1)
TEST_END=$(date +%s)
TEST_TIME=$((TEST_END - TEST_START))

if echo "$TEST_RESPONSE" | grep -q '"done":true'; then
    output "✅ Model responded in ${TEST_TIME}s"
else
    output "❌ Model test failed: $(echo "$TEST_RESPONSE" | head -c 200)"
fi

# Environment
section "ENVIRONMENT VARIABLES"

output "OLLAMA_HOST: ${OLLAMA_HOST:-'(not set)'}"
output "OLLAMA_KEEP_ALIVE: ${OLLAMA_KEEP_ALIVE:-'(not set)'}"
output "OLLAMA_MAX_LOADED_MODELS: ${OLLAMA_MAX_LOADED_MODELS:-'(not set)'}"
output "OLLAMA_NUM_PARALLEL: ${OLLAMA_NUM_PARALLEL:-'(not set)'}"

# Summary
section "SUMMARY"

ISSUES=0

if ! command -v ollama &> /dev/null; then
    output "❌ Ollama not installed"
    ((ISSUES++))
fi

if ! pgrep -x "ollama" > /dev/null; then
    output "❌ Ollama not running"
    ((ISSUES++))
fi

if ! curl -s --max-time 5 "$API_URL/api/tags" > /dev/null 2>&1; then
    output "❌ API not responding"
    ((ISSUES++))
fi

if [ $ISSUES -eq 0 ]; then
    output ""
    output "✅ No critical issues detected"
else
    output ""
    output "❌ Found $ISSUES issue(s)"
fi

if [ "$SAVE_REPORT" = true ]; then
    echo ""
    echo "Report saved to: $REPORT_FILE"
fi
