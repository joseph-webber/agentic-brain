#!/bin/bash
set -euo pipefail

APP_NAME="Brain Chat"
BUILD_DIR="$(cd "$(dirname "$0")" && pwd)/build"
APP_BUNDLE="${BUILD_DIR}/${APP_NAME}.app"
INSTALL_PATH="/Applications/${APP_NAME}.app"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

SWIFT_FILES=(
    "${SRC_DIR}/APIKeyManager.swift"
    "${SRC_DIR}/AppTypes.swift"
    "${SRC_DIR}/ClaudeAPI.swift"
    "${SRC_DIR}/OpenAIAPI.swift"
    "${SRC_DIR}/OllamaAPI.swift"
    "${SRC_DIR}/GrokClient.swift"
    "${SRC_DIR}/GeminiClient.swift"
    "${SRC_DIR}/CopilotClient.swift"
    "${SRC_DIR}/AirPodsManager.swift"
    "${SRC_DIR}/AudioSession.swift"
    "${SRC_DIR}/SpatialAudio.swift"
    "${SRC_DIR}/WhisperEngines.swift"
    "${SRC_DIR}/FasterWhisperBridge.swift"
    "${SRC_DIR}/SpeechEngineSelector.swift"
    "${SRC_DIR}/SpeechManager.swift"
    "${SRC_DIR}/VoiceManager.swift"
    "${SRC_DIR}/VoiceBridge.swift"
    "${SRC_DIR}/CopilotVoiceRouter.swift"
    "${SRC_DIR}/BridgeDaemon.swift"
    "${SRC_DIR}/LLMRouter.swift"
    "${SRC_DIR}/LLMSelector.swift"
    "${SRC_DIR}/ConversationView.swift"
    "${SRC_DIR}/SettingsView.swift"
    "${SRC_DIR}/ContentView.swift"
    "${SRC_DIR}/BrainChat.swift"
)

DO_INSTALL=false
DO_RUN=false
DO_CLEAN=false
for arg in "$@"; do
    case "$arg" in
        --install) DO_INSTALL=true ;;
        --run) DO_RUN=true ;;
        --clean) DO_CLEAN=true ;;
        --help|-h)
            echo "Usage: $0 [--install] [--run] [--clean]"
            exit 0 ;;
    esac
done

if $DO_CLEAN; then
    rm -rf "${BUILD_DIR}"
fi

mkdir -p "${APP_BUNDLE}/Contents/MacOS" "${APP_BUNDLE}/Contents/Resources"
cp "${SRC_DIR}/Info.plist" "${APP_BUNDLE}/Contents/"
echo -n "APPL????" > "${APP_BUNDLE}/Contents/PkgInfo"

swiftc \
    -o "${APP_BUNDLE}/Contents/MacOS/BrainChat" \
    -target arm64-apple-macosx14.0 \
    -sdk "$(xcrun --show-sdk-path)" \
    -framework SwiftUI \
    -framework AppKit \
    -framework Speech \
    -framework AVFoundation \
    -framework Foundation \
    -framework Network \
    -framework CryptoKit \
    -framework Security \
    -swift-version 6 \
    -O \
    -whole-module-optimization \
    -parse-as-library \
    "${SWIFT_FILES[@]}"

# Code sign the app bundle with ad-hoc signature, entitlements, and sealed resources
# This is required for microphone permission to work on macOS
ENTITLEMENTS="${SRC_DIR}/BrainChat.entitlements"
if [ -f "$ENTITLEMENTS" ]; then
    codesign --force --deep --sign - --entitlements "$ENTITLEMENTS" "${APP_BUNDLE}"
    echo "Signed with entitlements: $ENTITLEMENTS"
else
    echo "WARNING: No entitlements file found at $ENTITLEMENTS"
    codesign --force --deep --sign - "${APP_BUNDLE}"
fi

if $DO_INSTALL; then
    rm -rf "${INSTALL_PATH}"
    cp -R "${APP_BUNDLE}" "${INSTALL_PATH}"
fi

if $DO_RUN; then
    open "${INSTALL_PATH}"
fi

echo "built ${APP_BUNDLE}"
