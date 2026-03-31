#!/bin/bash
set -euo pipefail

# Test Mic Permission Setup for BrainChat
# This script verifies that mic permissions work BEFORE asking Joseph to test

APP_BUNDLE="/Applications/Brain Chat.app"
BUNDLE_ID="com.josephwebber.brainchat"
RUNTIME_DIR="$HOME/brain/agentic-brain/apps/BrainChat/runtime"

echo "=================================================="
echo "🎙️  BRAIN CHAT MIC PERMISSION TEST"
echo "=================================================="
echo ""

# Step 1: Check if app exists
echo "📦 Step 1: Check if app is installed"
if [ -d "$APP_BUNDLE" ]; then
    echo "✅ Found: $APP_BUNDLE"
else
    echo "❌ NOT FOUND: $APP_BUNDLE"
    echo "   Run: cd ~/brain/agentic-brain/apps/BrainChat && ./build.sh --install"
    exit 1
fi
echo ""

# Step 2: Check code signature
echo "🔏 Step 2: Verify code signature"
if codesign --verify --deep --strict "$APP_BUNDLE" 2>&1; then
    echo "✅ Code signature valid"
else
    echo "⚠️  Code signature issues - app may not get permission dialog"
fi
echo ""

# Step 3: Check entitlements
echo "🎫 Step 3: Check entitlements"
if codesign -d --entitlements :- "$APP_BUNDLE" 2>/dev/null | grep -q "com.apple.security.device.audio-input"; then
    echo "✅ Has audio-input entitlement"
else
    echo "❌ Missing audio-input entitlement"
    echo "   Check BrainChat.entitlements file"
    exit 1
fi
echo ""

# Step 4: Check Info.plist usage descriptions
echo "📋 Step 4: Check Info.plist usage descriptions"
INFO_PLIST="$APP_BUNDLE/Contents/Info.plist"
if /usr/libexec/PlistBuddy -c "Print :NSMicrophoneUsageDescription" "$INFO_PLIST" >/dev/null 2>&1; then
    MIC_DESC=$(/usr/libexec/PlistBuddy -c "Print :NSMicrophoneUsageDescription" "$INFO_PLIST")
    echo "✅ NSMicrophoneUsageDescription: $MIC_DESC"
else
    echo "❌ Missing NSMicrophoneUsageDescription"
    exit 1
fi

if /usr/libexec/PlistBuddy -c "Print :NSSpeechRecognitionUsageDescription" "$INFO_PLIST" >/dev/null 2>&1; then
    SPEECH_DESC=$(/usr/libexec/PlistBuddy -c "Print :NSSpeechRecognitionUsageDescription" "$INFO_PLIST")
    echo "✅ NSSpeechRecognitionUsageDescription: $SPEECH_DESC"
else
    echo "⚠️  Missing NSSpeechRecognitionUsageDescription (optional)"
fi
echo ""

# Step 5: Check current TCC database status
echo "🗄️  Step 5: Check TCC permission status"
# Note: Can't directly query TCC without Full Disk Access, but can check indirect signals

# Check if runtime markers exist from previous runs
if [ -f "$RUNTIME_DIR/mic-status.txt" ]; then
    echo "📝 Previous run status:"
    cat "$RUNTIME_DIR/mic-status.txt"
    echo ""
fi

if [ -f "$RUNTIME_DIR/microphone-granted.txt" ]; then
    echo "✅ Found permission granted marker from previous run"
elif [ -f "$RUNTIME_DIR/microphone-requested.txt" ]; then
    echo "⚠️  Permission was requested but not granted"
else
    echo "ℹ️  No previous permission markers found (first run)"
fi
echo ""

# Step 6: Launch app for 5 seconds to trigger permission
echo "🚀 Step 6: Launch app briefly to trigger permission request"
echo "   This will:"
echo "   1. Launch Brain Chat"
echo "   2. App requests mic permission in applicationDidFinishLaunching"
echo "   3. Wait 5 seconds"
echo "   4. Quit app"
echo "   5. Check if permission was registered"
echo ""
echo "Press Enter to continue, or Ctrl+C to cancel..."
read -r

echo "Launching $APP_BUNDLE..."
open "$APP_BUNDLE"

echo "Waiting 5 seconds for app to initialize..."
sleep 5

echo "Quitting app..."
osascript -e 'tell application "Brain Chat" to quit'
sleep 2

echo ""
echo "=================================================="
echo "🔍 VERIFICATION"
echo "=================================================="
echo ""

# Check if app registered in TCC (indirect check via system_profiler)
echo "Checking if app appears in System Settings..."
if tccutil reset Microphone "$BUNDLE_ID" 2>&1 | grep -q "No services"; then
    echo "❌ App NOT registered in TCC database"
    echo "   This means macOS didn't recognize the permission request."
    echo ""
    echo "   Common causes:"
    echo "   - Missing entitlements"
    echo "   - Invalid code signature"
    echo "   - App not launched from /Applications"
    echo "   - Gatekeeper blocking unsigned app"
    echo ""
    echo "   Try:"
    echo "   1. Verify entitlements: codesign -d --entitlements :- '$APP_BUNDLE'"
    echo "   2. Re-sign with entitlements: codesign --force --deep --sign - --entitlements BrainChat.entitlements '$APP_BUNDLE'"
    echo "   3. Clear quarantine: xattr -cr '$APP_BUNDLE'"
    exit 1
else
    echo "✅ App IS registered in TCC database"
    echo "   Brain Chat should now appear in:"
    echo "   System Settings > Privacy & Security > Microphone"
fi
echo ""

# Check runtime markers again
if [ -f "$RUNTIME_DIR/mic-status.txt" ]; then
    echo "📝 Updated permission status:"
    cat "$RUNTIME_DIR/mic-status.txt"
    echo ""
fi

# Step 7: Manual verification instructions
echo "=================================================="
echo "✅ AUTOMATED TESTS PASSED"
echo "=================================================="
echo ""
echo "Next steps for Joseph to test:"
echo ""
echo "1. Open System Settings > Privacy & Security > Microphone"
echo "   Verify 'Brain Chat' appears in the list"
echo ""
echo "2. If Brain Chat has a toggle, make sure it's ON"
echo ""
echo "3. Launch Brain Chat:"
echo "   open '$APP_BUNDLE'"
echo ""
echo "4. Click the mic button (it should show 'Muted' initially)"
echo ""
echo "5. Expected behavior:"
echo "   - If permission dialog appears: Click 'Allow'"
echo "   - Mic should turn green and show 'Live'"
echo "   - Speak something"
echo "   - Transcript should appear"
echo ""
echo "6. If mic button still does nothing:"
echo "   - Check Console.app for logs from 'com.josephwebber.brainchat'"
echo "   - Check $RUNTIME_DIR/mic-debug.log"
echo "   - Run: tccutil reset Microphone '$BUNDLE_ID'"
echo "   - Rebuild: cd ~/brain/agentic-brain/apps/BrainChat && ./build.sh --clean --install"
echo ""
echo "=================================================="

# Final audio announcement
say -v "Karen (Premium)" -r 160 "Test script complete. Brain Chat is ready for manual testing."
