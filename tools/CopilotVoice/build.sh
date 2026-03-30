#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="CopilotVoice"
APP_BUNDLE="${SCRIPT_DIR}/${APP_NAME}.app"
BINARY="${APP_BUNDLE}/Contents/MacOS/${APP_NAME}"
INFO_PLIST_SRC="${SCRIPT_DIR}/Info.plist"
INFO_PLIST_DST="${APP_BUNDLE}/Contents/Info.plist"
PKGINFO_DST="${APP_BUNDLE}/Contents/PkgInfo"
SOURCE="${SCRIPT_DIR}/CopilotVoice.swift"
SDK_PATH="$(xcrun --show-sdk-path)"
ARCH="$(uname -m)"
TARGET="${ARCH}-apple-macos13.0"
RUN_AFTER_BUILD=0
SMOKE_TEST_AFTER_BUILD=0

for arg in "$@"; do
    case "$arg" in
        --run) RUN_AFTER_BUILD=1 ;;
        --smoke-test) SMOKE_TEST_AFTER_BUILD=1 ;;
        *)
            echo "Unknown argument: $arg" >&2
            exit 1
            ;;
    esac
done

mkdir -p "${APP_BUNDLE}/Contents/MacOS" "${APP_BUNDLE}/Contents/Resources"
cp "${INFO_PLIST_SRC}" "${INFO_PLIST_DST}"
printf 'APPL????' > "${PKGINFO_DST}"

echo "Building ${APP_BUNDLE}..."
xcrun swiftc \
  -module-name "${APP_NAME}" \
  -parse-as-library \
  -target "${TARGET}" \
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
defaults read "${APP_BUNDLE}/Contents/Info" CFBundleIdentifier >/dev/null 2>&1 || true

if [[ "${SMOKE_TEST_AFTER_BUILD}" -eq 1 ]]; then
    echo ""
    echo "Running self-test..."
    "${BINARY}" --self-test
fi

if [[ "${RUN_AFTER_BUILD}" -eq 1 ]]; then
    echo ""
    echo "Launching app..."
    open -n "${APP_BUNDLE}"
fi
