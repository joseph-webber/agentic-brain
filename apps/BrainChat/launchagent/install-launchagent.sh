#!/bin/bash
# ================================================================
# BRAIN CHAT - MICROPHONE PERMISSION FIX INSTALLER
# ================================================================
# 
# This script installs a LaunchAgent that enables Brain Chat to
# request microphone permissions properly.
#
# THE PROBLEM:
#   When Brain Chat is launched from an SSH session (like Copilot CLI),
#   macOS TCC (Transparency, Consent & Control) blocks permission dialogs.
#   The log shows: "Policy disallows prompt for Sub:{/usr/libexec/sshd-keygen-wrapper}"
#
# THE SOLUTION:
#   A LaunchAgent that runs from launchd (clean process ancestry).
#   When triggered, it opens Brain Chat with no SSH taint.
#
# USAGE:
#   ./install-launchagent.sh        # Install and load
#   ./install-launchagent.sh --test # Install, load, and launch
#
# ================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="${SCRIPT_DIR}/com.brainchat.app.launcher.plist"
PLIST_DEST="${HOME}/Library/LaunchAgents/com.brainchat.app.launcher.plist"
LABEL="com.brainchat.app.launcher"

echo "🧠 Brain Chat - Microphone Permission Fix"
echo "=========================================="

# Check if app is installed
if [[ ! -d "/Applications/Brain Chat.app" ]]; then
    echo "❌ Error: /Applications/Brain Chat.app not found"
    echo "   Please run 'cd ~/brain/agentic-brain/apps/BrainChat && ./build.sh --install' first"
    exit 1
fi

# Check if source plist exists
if [[ ! -f "$PLIST_SRC" ]]; then
    echo "❌ Error: LaunchAgent plist not found at $PLIST_SRC"
    exit 1
fi

# Unload existing if present
echo "📦 Unloading existing LaunchAgent (if any)..."
launchctl bootout gui/$(id -u)/$LABEL 2>/dev/null || true
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Copy plist
echo "📋 Installing LaunchAgent..."
cp "$PLIST_SRC" "$PLIST_DEST"
chmod 644 "$PLIST_DEST"

# Validate plist syntax
echo "✅ Validating plist..."
if ! plutil -lint "$PLIST_DEST" >/dev/null; then
    echo "❌ Error: Invalid plist syntax"
    exit 1
fi

# Load the LaunchAgent
echo "🔄 Loading LaunchAgent..."
launchctl load "$PLIST_DEST"

# Verify it's loaded
if launchctl list | grep -q "$LABEL"; then
    echo "✅ LaunchAgent installed and loaded!"
    echo ""
    echo "📍 Plist location: $PLIST_DEST"
    echo ""
    echo "🎯 USAGE:"
    echo "   Launch Brain Chat (clean):  launchctl start $LABEL"
    echo "   Or use the wrapper:         brainchat-clean"
    echo ""
else
    echo "❌ Error: LaunchAgent failed to load"
    exit 1
fi

# Create convenient wrapper script
WRAPPER="${HOME}/bin/brainchat-clean"
echo "📝 Creating wrapper script at $WRAPPER..."
mkdir -p "${HOME}/bin"
cat > "$WRAPPER" << 'EOF'
#!/bin/bash
# Launch Brain Chat with clean process ancestry (for TCC permissions)
launchctl start com.brainchat.app.launcher
echo "✅ Brain Chat launching from launchd (clean ancestry)"
echo "   Microphone permission dialog should appear on first use."
EOF
chmod +x "$WRAPPER"

# Test launch if requested
if [[ "${1:-}" == "--test" ]]; then
    echo ""
    echo "🧪 Launching Brain Chat (test mode)..."
    sleep 1
    launchctl start "$LABEL"
    echo "✅ Check if Brain Chat opened and permission dialog appeared"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "🎤 TO GET MICROPHONE PERMISSION DIALOG:"
echo "   1. Run: launchctl start $LABEL"
echo "   2. Or run: brainchat-clean"
echo "   3. Click the microphone button in Brain Chat"
echo "   4. macOS permission dialog should appear!"
