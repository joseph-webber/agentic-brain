#!/bin/bash
# CI/CD Code Signing Verification Script
# Run this after building any macOS Swift app to verify code signing is correct
# 
# Usage: ./verify-code-signing.sh /path/to/App.app
#
# Exit codes:
#   0 = All checks passed
#   1 = Code signing check failed
#   2 = Info.plist check failed
#   3 = Build script check failed

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

APP_PATH="${1:-/Applications/Brain Chat.app}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🔐 Verifying Code Signing for: $APP_PATH"
echo "=================================================="

# Check 1: App exists
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}❌ FAIL: App not found at $APP_PATH${NC}"
    exit 1
fi
echo -e "${GREEN}✓ App bundle exists${NC}"

# Check 2: App is code signed
if ! codesign --verify --verbose=2 "$APP_PATH" 2>&1; then
    echo -e "${RED}❌ FAIL: App is not properly code signed${NC}"
    echo "Fix: Add 'codesign --force --deep --sign - \"\$APP_BUNDLE\"' to build.sh"
    exit 1
fi
echo -e "${GREEN}✓ App is code signed${NC}"

# Check 3: Has sealed resources
SIGNING_INFO=$(codesign -dvvv "$APP_PATH" 2>&1)
if ! echo "$SIGNING_INFO" | grep -q "Sealed Resources"; then
    echo -e "${RED}❌ FAIL: App missing sealed resources${NC}"
    echo "Fix: Use 'codesign --force --deep --sign -' (not just --sign -)"
    exit 1
fi
echo -e "${GREEN}✓ Has sealed resources${NC}"

# Check 4: Has bundle identifier
if ! echo "$SIGNING_INFO" | grep -q "Identifier="; then
    echo -e "${RED}❌ FAIL: Missing bundle identifier${NC}"
    exit 1
fi

BUNDLE_ID=$(echo "$SIGNING_INFO" | grep "Identifier=" | head -1 | cut -d= -f2)
if [[ ! "$BUNDLE_ID" == *.* ]]; then
    echo -e "${YELLOW}⚠ WARNING: Bundle identifier '$BUNDLE_ID' should be reverse-DNS format${NC}"
fi
echo -e "${GREEN}✓ Has bundle identifier: $BUNDLE_ID${NC}"

# Check 5: Info.plist has privacy keys
INFO_PLIST="$APP_PATH/Contents/Info.plist"
if [ ! -f "$INFO_PLIST" ]; then
    echo -e "${RED}❌ FAIL: Info.plist not found${NC}"
    exit 2
fi

# Check for NSMicrophoneUsageDescription
if ! /usr/libexec/PlistBuddy -c "Print :NSMicrophoneUsageDescription" "$INFO_PLIST" 2>/dev/null; then
    echo -e "${RED}❌ FAIL: Missing NSMicrophoneUsageDescription in Info.plist${NC}"
    echo "This is REQUIRED for microphone access!"
    exit 2
fi
echo -e "${GREEN}✓ Has NSMicrophoneUsageDescription${NC}"

# Check for NSSpeechRecognitionUsageDescription
if ! /usr/libexec/PlistBuddy -c "Print :NSSpeechRecognitionUsageDescription" "$INFO_PLIST" 2>/dev/null; then
    echo -e "${YELLOW}⚠ WARNING: Missing NSSpeechRecognitionUsageDescription${NC}"
fi

# Check 6: Build script has codesign (if we can find it)
BUILD_SCRIPT=""
APP_NAME=$(basename "$APP_PATH" .app)
POSSIBLE_SCRIPTS=(
    "$SCRIPT_DIR/../build.sh"
    "$SCRIPT_DIR/build.sh"
    "./build.sh"
)

for script in "${POSSIBLE_SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        BUILD_SCRIPT="$script"
        break
    fi
done

if [ -n "$BUILD_SCRIPT" ]; then
    if ! grep -q "codesign" "$BUILD_SCRIPT"; then
        echo -e "${RED}❌ FAIL: build.sh missing codesign command${NC}"
        echo "Add this line after swiftc: codesign --force --deep --sign - \"\$APP_BUNDLE\""
        exit 3
    fi
    echo -e "${GREEN}✓ build.sh includes codesign${NC}"
else
    echo -e "${YELLOW}⚠ Could not find build.sh to verify${NC}"
fi

# Check 7: Executable exists and is ARM64
# Get the executable name from Info.plist
EXEC_NAME=$(/usr/libexec/PlistBuddy -c "Print :CFBundleExecutable" "$INFO_PLIST" 2>/dev/null || echo "")
EXECUTABLE="$APP_PATH/Contents/MacOS/$EXEC_NAME"

if [ ! -f "$EXECUTABLE" ]; then
    # Find any executable in MacOS folder
    EXECUTABLE=$(find "$APP_PATH/Contents/MacOS" -type f -perm +111 2>/dev/null | head -1)
fi

if [ -f "$EXECUTABLE" ]; then
    if file "$EXECUTABLE" | grep -q "arm64"; then
        echo -e "${GREEN}✓ Executable is ARM64 (Apple Silicon)${NC}"
    else
        echo -e "${YELLOW}⚠ Executable may not be ARM64${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Could not find executable to verify${NC}"
fi

echo ""
echo "=================================================="
echo -e "${GREEN}✅ All code signing checks passed!${NC}"
echo ""
echo "The app should now:"
echo "  • Appear in System Settings > Privacy > Microphone"
echo "  • Show permission dialog when microphone is accessed"
echo "  • Work with AVCaptureDevice.requestAccess(for: .audio)"
exit 0
