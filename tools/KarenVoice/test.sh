#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_BUNDLE="${SCRIPT_DIR}/KarenVoice.app"
BINARY="${APP_BUNDLE}/Contents/MacOS/KarenVoice"
PLIST="${APP_BUNDLE}/Contents/Info.plist"

"${SCRIPT_DIR}/build.sh" >/dev/null

/usr/bin/plutil -extract NSMicrophoneUsageDescription raw -o - "${PLIST}" >/dev/null
/usr/bin/plutil -extract NSSpeechRecognitionUsageDescription raw -o - "${PLIST}" >/dev/null
codesign --verify --deep --strict "${APP_BUNDLE}" >/dev/null

printf 'bundle-ok\n'
printf 'binary-ok\n'
printf 'codesign-ok\n'
printf 'info-plist-ok\n'
