#!/usr/bin/env bash
# build.sh — Compile and bundle VoiceInput.app
# Usage: ./build.sh
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="VoiceInput"
APP_DIR="$SCRIPT_DIR/$APP_NAME.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
SDK_PATH="$(xcrun --sdk macosx --show-sdk-path)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔨  Building $APP_NAME"
echo "  SDK: $SDK_PATH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Clean ──────────────────────────────────────────────────────────────────
echo "  Cleaning previous build…"
rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR"

# ── Compile ────────────────────────────────────────────────────────────────
echo "  Compiling Swift source…"
swiftc \
    -O \
    -swift-version 5 \
    -sdk "$SDK_PATH" \
    -target arm64-apple-macosx13.0 \
    -framework AVFoundation \
    -framework Speech \
    -framework AppKit \
    -framework Foundation \
    "$SCRIPT_DIR/main.swift" \
    -o "$MACOS_DIR/$APP_NAME"

echo "  ✅  Binary compiled: $MACOS_DIR/$APP_NAME"

# ── Bundle resources ───────────────────────────────────────────────────────
cp "$SCRIPT_DIR/Info.plist" "$CONTENTS_DIR/Info.plist"
printf 'APPL????' > "$CONTENTS_DIR/PkgInfo"
echo "  ✅  Bundle structure created"

# ── Ad-hoc code sign ───────────────────────────────────────────────────────
echo "  Signing (ad-hoc)…"
codesign \
    --force \
    --deep \
    --sign - \
    --entitlements "$SCRIPT_DIR/VoiceInput.entitlements" \
    "$APP_DIR"

echo "  ✅  Signed"

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎤  $APP_NAME.app ready!"
echo ""
echo "  FIRST RUN (triggers permission dialogs):"
echo "    open \"$APP_DIR\""
echo ""
echo "  CLI usage:"
echo "    \"$MACOS_DIR/$APP_NAME\" [timeout_seconds]"
echo ""
echo "  Shell capture example:"
echo "    TEXT=\$(\"$MACOS_DIR/$APP_NAME\" 10) && echo \"You said: \$TEXT\""
echo ""
echo "  Python usage:"
echo "    python3 \"$SCRIPT_DIR/voice_input.py\" [timeout_seconds]"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
