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

mkdir -p "$MACOS_DIR"

swiftc \
  -O \
  -framework Cocoa \
  -framework Speech \
  -framework AVFoundation \
  -module-name BrainChat \
  "$SCRIPT_DIR/BrainChat.swift" \
  -o "$MACOS_DIR/$EXECUTABLE_NAME"

cp "$SCRIPT_DIR/Info.plist" "$CONTENTS_DIR/Info.plist"
chmod +x "$MACOS_DIR/$EXECUTABLE_NAME"
rm -rf "$APPLICATIONS_APP"
ditto "$APP_BUNDLE" "$APPLICATIONS_APP"

echo "Built: $APP_BUNDLE"
echo "Installed: $APPLICATIONS_APP"
