#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Brain Chat"
EXECUTABLE_NAME="BrainChat"
BUILD_DIR="$SCRIPT_DIR/build"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
APPLICATIONS_APP="/Applications/$APP_NAME.app"
ENTITLEMENTS="$SCRIPT_DIR/entitlements.plist"

# Find Developer ID Application certificate for code signing
DEVELOPER_ID=$(security find-identity -v -p codesigning 2>/dev/null | grep "Developer ID Application" | head -1 | sed 's/.*"\(.*\)"/\1/' || true)

if [ -z "$DEVELOPER_ID" ]; then
    # Fallback to Apple Development if no Developer ID
    DEVELOPER_ID=$(security find-identity -v -p codesigning 2>/dev/null | grep "Apple Development" | head -1 | sed 's/.*"\(.*\)"/\1/' || true)
fi

if [ -n "$DEVELOPER_ID" ]; then
    echo "✅ Found signing identity: $DEVELOPER_ID"
else
    echo "⚠️  No code signing identity found - app will be unsigned"
fi

mkdir -p "$MACOS_DIR"
mkdir -p "$CONTENTS_DIR/Resources"

# Snapshot BrainChat.swift to avoid mid-build mutations from other processes.
SNAPSHOT="$BUILD_DIR/BrainChat_snapshot.swift"
cp "$SCRIPT_DIR/BrainChat.swift" "$SNAPSHOT"

# Inject copilot routing into processInput methods.
# The extensions provide tryHandleCopilotInput() which returns true if handled.
# We add a call at the start of each processInput.
PATCHED="$BUILD_DIR/BrainChat_patched.swift"
cp "$SNAPSHOT" "$PATCHED"

# Patch 1: Terminal processInput — inject after function signature
# Look for "private func processInput(_ text: String) {" and add copilot check on next meaningful line
python3 -c "
import re
with open('$PATCHED') as f: c = f.read()

# Inject into FIRST processInput (TerminalChatController)
old1 = 'private func processInput(_ text: String) {'
idx1 = c.find(old1)
if idx1 != -1:
    insert_pos = idx1 + len(old1)
    c = c[:insert_pos] + '\n        if tryHandleCopilotInput(text) { return }' + c[insert_pos:]

# Inject into SECOND processInput (AppDelegate) — find from the end
idx2 = c.rfind(old1)
if idx2 != -1 and idx2 != idx1:
    insert_pos = idx2 + len(old1)
    c = c[:insert_pos] + '\n        if tryHandleCopilotInput(text) { return }' + c[insert_pos:]

# Inject copilot cleanup into shutdown/terminate
# Terminal shutdown
old_shutdown = 'shuttingDown = true'
idx_s = c.find(old_shutdown)
if idx_s != -1:
    insert_pos = idx_s + len(old_shutdown)
    c = c[:insert_pos] + '; cleanupCopilotSession()' + c[insert_pos:]

# AppDelegate terminate
old_term = 'func applicationWillTerminate(_ notification: Notification) {'
idx_t = c.find(old_term)
if idx_t != -1:
    insert_pos = idx_t + len(old_term)
    c = c[:insert_pos] + '\n        cleanupCopilotSession()' + c[insert_pos:]

with open('$PATCHED', 'w') as f: f.write(c)
print('Patches applied')
"

# Merge extension files with patched main source.
MERGED="$BUILD_DIR/BrainChatMerged.swift"
{
    for ext in "$SCRIPT_DIR"/GHCopilotBridge.swift "$SCRIPT_DIR"/CopilotIntegration.swift; do
        [ -f "$ext" ] && cat "$ext" && printf '\n'
    done
    cat "$PATCHED"
} > "$MERGED"

swiftc \
  -O \
  -framework Cocoa \
  -framework Speech \
  -framework AVFoundation \
  -module-name BrainChat \
  "$MERGED" \
  -o "$MACOS_DIR/$EXECUTABLE_NAME"

cp "$SCRIPT_DIR/Info.plist" "$CONTENTS_DIR/Info.plist"
cp "$SCRIPT_DIR/BrainChat.sdef" "$CONTENTS_DIR/Resources/BrainChat.sdef"
chmod +x "$MACOS_DIR/$EXECUTABLE_NAME"

# Code sign the app bundle before copying to Applications
if [ -n "$DEVELOPER_ID" ]; then
    echo "🔏 Signing app with: $DEVELOPER_ID"
    
    # Sign with entitlements for microphone, network, etc.
    codesign --force --deep --options runtime \
        --entitlements "$ENTITLEMENTS" \
        --sign "$DEVELOPER_ID" \
        "$APP_BUNDLE"
    
    echo "🔍 Verifying signature..."
    codesign --verify --verbose "$APP_BUNDLE"
    
    # Check Gatekeeper assessment
    if spctl --assess --verbose "$APP_BUNDLE" 2>&1; then
        echo "✅ Gatekeeper: App is properly signed"
    else
        echo "⚠️  Gatekeeper check failed (may need notarization for distribution)"
    fi
fi

rm -rf "$APPLICATIONS_APP"
ditto "$APP_BUNDLE" "$APPLICATIONS_APP"

# Re-sign in Applications folder if we have a signing identity
if [ -n "$DEVELOPER_ID" ]; then
    echo "🔏 Signing installed app..."
    codesign --force --deep --options runtime \
        --entitlements "$ENTITLEMENTS" \
        --sign "$DEVELOPER_ID" \
        "$APPLICATIONS_APP"
    
    echo "✅ Code signing complete"
fi

echo "Built: $APP_BUNDLE"
echo "Installed: $APPLICATIONS_APP"
