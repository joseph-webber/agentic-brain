#!/bin/bash
# Brain Chat Mic Button Test Runner
# Runs the AppleScript automation test and displays results

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULT_FILE="$SCRIPT_DIR/runtime/automation-test-result.txt"
SCRIPT_FILE="$SCRIPT_DIR/test-mic-automation.scpt"

echo "🎤 Brain Chat Mic Button Automation Test"
echo "========================================"
echo ""

# Ensure runtime directory exists
mkdir -p "$SCRIPT_DIR/runtime"

# Check if Brain Chat is installed
if [ ! -d "/Applications/Brain Chat.app" ]; then
    # Check in build location
    if [ -d "$SCRIPT_DIR/build/Release/Brain Chat.app" ]; then
        echo "📦 Found Brain Chat in build directory"
        APP_PATH="$SCRIPT_DIR/build/Release/Brain Chat.app"
    else
        echo "⚠️  Brain Chat.app not found in /Applications or build directory"
        echo "    Please build and install the app first:"
        echo "    cd $SCRIPT_DIR && xcodebuild -project BrainChat.xcodeproj -scheme BrainChat -configuration Release"
        exit 1
    fi
else
    APP_PATH="/Applications/Brain Chat.app"
    echo "✅ Found Brain Chat at: $APP_PATH"
fi

# Check accessibility permissions
echo ""
echo "📋 Checking accessibility permissions..."
echo "   (This script requires System Events accessibility access)"

# Run the AppleScript
echo ""
echo "🚀 Running automation test..."
echo ""

# Execute the AppleScript and capture result
RESULT=$(osascript "$SCRIPT_FILE" 2>&1) || true

echo "Test execution completed."
echo ""

# Display results
if [ -f "$RESULT_FILE" ]; then
    echo "📄 Test Results:"
    echo "========================================"
    cat "$RESULT_FILE"
    echo "========================================"
else
    echo "⚠️  No result file generated"
    echo "Script output: $RESULT"
fi

echo ""
echo "Script return value: $RESULT"
