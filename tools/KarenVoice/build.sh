#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="KarenVoice"
APP_BUNDLE="${SCRIPT_DIR}/${APP_NAME}.app"
BINARY="${APP_BUNDLE}/Contents/MacOS/${APP_NAME}"
INFO_PLIST_DEST="${APP_BUNDLE}/Contents/Info.plist"
PKGINFO="${APP_BUNDLE}/Contents/PkgInfo"
SDK_PATH="$(xcrun --show-sdk-path)"
SOURCE="${SCRIPT_DIR}/KarenVoice.swift"
INFO_PLIST_SOURCE="${SCRIPT_DIR}/Info.plist"

rm -rf "${APP_BUNDLE}"
mkdir -p "${APP_BUNDLE}/Contents/MacOS" "${APP_BUNDLE}/Contents/Resources"
cp "${INFO_PLIST_SOURCE}" "${INFO_PLIST_DEST}"
printf 'APPL????' > "${PKGINFO}"

xcrun swiftc \
  -module-name KarenVoice \
  -target arm64-apple-macos13.0 \
  -sdk "${SDK_PATH}" \
  -O \
  -framework AppKit \
  -framework AVFoundation \
  -framework Speech \
  -emit-executable \
  "${SOURCE}" \
  -o "${BINARY}"

chmod +x "${BINARY}"
xattr -cr "${APP_BUNDLE}"
codesign --force --deep --sign - "${APP_BUNDLE}"
codesign --verify --deep --strict "${APP_BUNDLE}"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "${APP_BUNDLE}" >/dev/null 2>&1 || true

echo "Built ${APP_BUNDLE}"
echo "Run: ${BINARY}"
