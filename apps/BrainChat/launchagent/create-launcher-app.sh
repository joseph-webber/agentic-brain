#!/bin/bash
# ================================================================
# CREATE BRAIN CHAT LAUNCHER AUTOMATOR APP
# ================================================================
# 
# This creates a simple .app that Joseph can double-click to launch
# Brain Chat with clean process ancestry (no SSH taint).
#
# Why this works:
#   - Automator apps run in GUI context (owned by loginwindow/Finder)
#   - When the Automator app launches Brain Chat, the "responsible process"
#     is the Automator app, NOT SSH
#   - TCC sees a GUI app and allows permission dialogs
#
# ================================================================

set -euo pipefail

APP_NAME="Launch Brain Chat"
APP_PATH="/Applications/${APP_NAME}.app"
SCRIPT_CONTENT='do shell script "open -a \"/Applications/Brain Chat.app\""'

echo "🧠 Creating '$APP_NAME' Automator app..."

# Create app structure
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Create Info.plist
cat > "$APP_PATH/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Launch Brain Chat</string>
    <key>CFBundleDisplayName</key>
    <string>Launch Brain Chat</string>
    <key>CFBundleIdentifier</key>
    <string>com.josephwebber.launchbrainchat</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
PLIST

# Create the launcher script
cat > "$APP_PATH/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash
# Clean launcher for Brain Chat - runs from GUI context
# This ensures TCC allows permission dialogs
open -a "/Applications/Brain Chat.app" --args --clean-launch
LAUNCHER

chmod +x "$APP_PATH/Contents/MacOS/launcher"

# Sign the app
codesign --force --deep --sign - "$APP_PATH"

# Register with Launch Services
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH" 2>/dev/null || true

echo "✅ Created: $APP_PATH"
echo ""
echo "📍 USAGE:"
echo "   1. Double-click 'Launch Brain Chat' in /Applications"
echo "   2. Or: Spotlight search 'Launch Brain Chat'"
echo "   3. Or: open -a 'Launch Brain Chat'"
echo ""
echo "🎤 The microphone permission dialog will appear when you"
echo "   click the mic button in Brain Chat!"
