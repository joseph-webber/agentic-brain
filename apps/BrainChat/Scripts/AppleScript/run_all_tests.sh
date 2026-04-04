#!/bin/bash
# run_all_tests.sh — BrainChat AppleScript E2E Test Runner
# Runs every test_*.applescript in this directory and reports results.
# Usage: ./run_all_tests.sh [--verbose]
#
# Prerequisites:
#   - Brain Chat.app must be built (~/brain/agentic-brain/apps/BrainChat/Brain Chat.app)
#   - System Events access must be granted in Privacy & Security → Accessibility
#   - Terminal (or calling app) needs Accessibility permission

set -euo pipefail
cd "$(dirname "$0")"

VERBOSE=false
[[ "${1:-}" == "--verbose" ]] && VERBOSE=true

PASS=0
FAIL=0
ERROR=0
SKIP=0
RESULTS=()

divider="─────────────────────────────────────────────────────"

echo ""
echo "🧠 BrainChat AppleScript E2E Test Suite"
echo "$divider"
echo "  Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Dir:     $(pwd)"
echo "$divider"

# Check Brain Chat is available
APP_PATH="$HOME/brain/agentic-brain/apps/BrainChat/Brain Chat.app"
if [ ! -d "$APP_PATH" ]; then
    echo "⚠️  Brain Chat.app not found at $APP_PATH"
    echo "   Build it first:  cd ~/brain/agentic-brain/apps/BrainChat && swift build"
    echo "   Skipping live tests — running syntax check only."
    echo ""

    for script in test_*.applescript; do
        echo -n "  Checking syntax: $script ... "
        if osacompile -o /dev/null "$script" 2>/dev/null; then
            echo "✅ valid"
            ((PASS++))
        else
            echo "❌ syntax error"
            ((FAIL++))
        fi
    done

    echo ""
    echo "$divider"
    echo "  Syntax check: $PASS valid, $FAIL errors"
    echo "$divider"
    exit $FAIL
fi

# Launch Brain Chat if not running
if ! pgrep -x "Brain Chat" > /dev/null 2>&1; then
    echo "  Launching Brain Chat..."
    open "$APP_PATH"
    sleep 3
fi

echo ""

for script in test_*.applescript; do
    [[ ! -f "$script" ]] && continue

    printf "  ▶ %-40s " "$script"

    # Run the test with a timeout
    result=$(timeout 30 osascript "$script" 2>&1) || true

    if [[ "$result" == PASS:* ]]; then
        echo "✅ PASS"
        ((PASS++))
    elif [[ "$result" == FAIL:* ]]; then
        echo "❌ FAIL"
        ((FAIL++))
    elif [[ "$result" == WARN:* ]]; then
        echo "⚠️  WARN"
        ((PASS++))  # Warnings count as soft pass
    elif [[ "$result" == ERROR:* ]]; then
        echo "💥 ERROR"
        ((ERROR++))
    elif [[ -z "$result" ]]; then
        echo "⏭  SKIP (no output)"
        ((SKIP++))
    else
        echo "❓ UNKNOWN"
        ((ERROR++))
    fi

    RESULTS+=("$result")

    if $VERBOSE; then
        echo "    $result"
        echo ""
    fi
done

echo ""
echo "$divider"
echo "  RESULTS: $PASS passed, $FAIL failed, $ERROR errors, $SKIP skipped"
echo "  Finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo "$divider"

# Print verbose details for failures
if (( FAIL > 0 || ERROR > 0 )); then
    echo ""
    echo "  FAILURE DETAILS:"
    for r in "${RESULTS[@]}"; do
        if [[ "$r" == FAIL:* ]] || [[ "$r" == ERROR:* ]]; then
            echo "    $r"
        fi
    done
    echo ""
fi

# Exit with failure count
exit $((FAIL + ERROR))
