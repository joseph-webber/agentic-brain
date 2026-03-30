#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="KarenApp"
APP_DISPLAY_NAME="Karen Voice Chat"
BUNDLE_ID="com.josephwebber.brain.karenapp"
APP_BUNDLE="${SCRIPT_DIR}/${APP_NAME}.app"
BINARY="${APP_BUNDLE}/Contents/MacOS/${APP_NAME}"
INFO_PLIST="${APP_BUNDLE}/Contents/Info.plist"
PKGINFO="${APP_BUNDLE}/Contents/PkgInfo"
SDK_PATH="$(xcrun --show-sdk-path)"
SWIFT_SOURCES=(
  "${SCRIPT_DIR}/Sources/KarenApp/main.swift"
  "${SCRIPT_DIR}/Sources/KarenApp/KarenAppApp.swift"
  "${SCRIPT_DIR}/Sources/KarenApp/ContentView.swift"
  "${SCRIPT_DIR}/Sources/KarenApp/VoiceChatManager.swift"
)

mkdir -p "${APP_BUNDLE}/Contents/MacOS" "${APP_BUNDLE}/Contents/Resources"

cat > "${INFO_PLIST}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_DISPLAY_NAME}</string>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>Karen Voice Chat needs microphone access so Joseph can talk to Karen and hear spoken responses from the Python voice chat service.</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
PLIST

printf 'APPL????' > "${PKGINFO}"

echo "Validating Swift package manifest..."
swift package --package-path "${SCRIPT_DIR}" dump-package >/dev/null

echo "Building ${APP_BUNDLE}..."
xcrun swiftc \
  -module-name KarenApp \
  -target arm64-apple-macos13.0 \
  -sdk "${SDK_PATH}" \
  -O \
  -framework SwiftUI \
  -framework AppKit \
  -framework AVFoundation \
  -framework Combine \
  -emit-executable \
  "${SWIFT_SOURCES[@]}" \
  -o "${BINARY}"

chmod +x "${BINARY}"
xattr -cr "${APP_BUNDLE}"
codesign --force --deep --sign - "${APP_BUNDLE}"
codesign --verify --deep --strict "${APP_BUNDLE}"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "${APP_BUNDLE}" >/dev/null 2>&1 || true

if command -v redis-cli >/dev/null 2>&1; then
  redis-cli -a BrainRedis2026 RPUSH brain:karen_app:events "KarenApp build complete: ${APP_BUNDLE}" >/dev/null 2>&1 || true
fi

echo "Built ${APP_BUNDLE}"
defaults read "${INFO_PLIST%/Info.plist}/Info" CFBundleIdentifier >/dev/null 2>&1 || true
