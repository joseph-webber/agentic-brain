#!/bin/bash
# build_mic_app.sh — builds a real MicRequestApp.app bundle that requests
# macOS microphone permission and runs talk_to_karen.py inside the app process.
# Usage:
#   ./build_mic_app.sh
#   ./build_mic_app.sh --run
#   ./build_mic_app.sh --smoke-test
#   ./build_mic_app.sh --install
#   ./build_mic_app.sh --install --run

set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="MicRequestApp"
APP_BUNDLE="${TOOLS_DIR}/${APP_NAME}.app"
BINARY="${APP_BUNDLE}/Contents/MacOS/${APP_NAME}"
OBJC_SRC="${TOOLS_DIR}/${APP_NAME}.m"
ENTITLEMENTS="${TOOLS_DIR}/${APP_NAME}.entitlements"
INFO_PLIST_SRC="${TOOLS_DIR}/${APP_NAME}.Info.plist"
INFO_PLIST_DST="${APP_BUNDLE}/Contents/Info.plist"
PKGINFO_DST="${APP_BUNDLE}/Contents/PkgInfo"
INSTALL_DIR=""
RUN_AFTER_BUILD=0
SMOKE_TEST_AFTER_BUILD=0

for arg in "$@"; do
    case "$arg" in
        --run) RUN_AFTER_BUILD=1 ;;
        --smoke-test) SMOKE_TEST_AFTER_BUILD=1 ;;
        --install) INSTALL_DIR="/Applications" ;;
        --install-home) INSTALL_DIR="${HOME}/Applications" ;;
        *)
            echo "Unknown argument: $arg" >&2
            exit 1
            ;;
    esac
done

echo "═══════════════════════════════════════════════"
echo "  Building ${APP_NAME}.app"
echo "  macOS $(sw_vers -productVersion)"
echo "═══════════════════════════════════════════════"

# ── 1. Ensure bundle structure exists ──────────────────────────
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"
cp "${INFO_PLIST_SRC}" "${INFO_PLIST_DST}"
printf 'APPL????' > "${PKGINFO_DST}"

# ── 2. Compile Objective-C → binary inside the bundle ─────────
echo ""
echo "▶ Compiling Objective-C source with embedded Python…"
clang \
    -fobjc-arc \
    -O2 \
    -target arm64-apple-macos13.0 \
    -isysroot "$(xcrun --show-sdk-path)" \
    -framework Cocoa \
    -framework AVFoundation \
    $(python3-config --includes) \
    "${OBJC_SRC}" \
    -o "${BINARY}" \
    $(python3-config --ldflags --embed)

echo "  ✓ Binary compiled: ${BINARY}"

# ── 3. Ad-hoc sign with entitlements ───────────────────────────
# Ad-hoc signing (-) gives the binary a valid code signature
# without needing a Developer ID. macOS accepts this for local use.
# The entitlements embed com.apple.security.device.audio-input which
# allows TCC to attribute the mic request to this bundle, not Terminal.
echo ""
echo "▶ Code-signing (ad-hoc) with entitlements…"
xattr -cr "${APP_BUNDLE}"
codesign \
    --force \
    --deep \
    --sign - \
    --entitlements "${ENTITLEMENTS}" \
    --options runtime \
    "${APP_BUNDLE}"

echo "  ✓ Signed: $(codesign -dvv "${APP_BUNDLE}" 2>&1 | grep 'Authority\|TeamIdentifier\|Identifier' | head -3)"

# ── 4. Verify signature ────────────────────────────────────────
echo ""
echo "▶ Verifying signature…"
codesign --verify --deep --strict "${APP_BUNDLE}" && echo "  ✓ Signature valid"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "${APP_BUNDLE}" >/dev/null 2>&1 || true

# ── 5. Show bundle info ────────────────────────────────────────
echo ""
echo "▶ Bundle info:"
echo "  App:         ${APP_BUNDLE}"
echo "  Bundle ID:   $(defaults read "${APP_BUNDLE}/Contents/Info" CFBundleIdentifier 2>/dev/null || echo 'n/a')"
echo "  Mic desc:    $(defaults read "${APP_BUNDLE}/Contents/Info" NSMicrophoneUsageDescription 2>/dev/null || echo 'MISSING — BAD!')"

# ── 6. Quarantine removal (prevents Gatekeeper blocking) ───────
xattr -d com.apple.quarantine "${APP_BUNDLE}" 2>/dev/null || true

TARGET_APP="${APP_BUNDLE}"
if [[ -n "${INSTALL_DIR}" ]]; then
    echo ""
    echo "▶ Installing app bundle into ${INSTALL_DIR}…"
    mkdir -p "${INSTALL_DIR}"
    rm -rf "${INSTALL_DIR}/${APP_NAME}.app"
    cp -R "${APP_BUNDLE}" "${INSTALL_DIR}/${APP_NAME}.app"
    xattr -cr "${INSTALL_DIR}/${APP_NAME}.app"
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "${INSTALL_DIR}/${APP_NAME}.app" >/dev/null 2>&1 || true
    TARGET_APP="${INSTALL_DIR}/${APP_NAME}.app"
    echo "  ✓ Installed to ${TARGET_APP}"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ Build complete!"
echo ""
echo "  To run:  open '${TARGET_APP}'"
echo "           or: ./build_mic_app.sh --run"
echo "═══════════════════════════════════════════════"

# ── 7. Optional: launch immediately ───────────────────────────
if [[ "${RUN_AFTER_BUILD}" -eq 1 ]]; then
    echo ""
    echo "▶ Launching app…"
    open -n "${TARGET_APP}"
fi

if [[ "${SMOKE_TEST_AFTER_BUILD}" -eq 1 ]]; then
    echo ""
    echo "▶ Running smoke test…"
    open -W -n "${TARGET_APP}" --args --smoke-test
    echo "▶ Smoke test status:"
    cat "${TOOLS_DIR}/MicRequestApp.last_run.json"
fi
