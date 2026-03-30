#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${SCRIPT_DIR}/VoiceDaemon"

swiftc -O \
  -parse-as-library \
  -framework Foundation \
  -framework AVFoundation \
  -o "${OUTPUT}" \
  "${SCRIPT_DIR}/main.swift" \
  "${SCRIPT_DIR}/AudioCapture.swift" \
  "${SCRIPT_DIR}/SpeechOutput.swift" \
  "${SCRIPT_DIR}/RedisClient.swift" \
  "${SCRIPT_DIR}/CopilotBridge.swift"

chmod +x "${OUTPUT}"

if command -v redis-cli >/dev/null 2>&1; then
  redis-cli -a "${REDISCLI_AUTH:-${REDIS_PASSWORD:-BrainRedis2026}}" \
    RPUSH voice:swift:events \
    "{\"event\":\"build_complete\",\"binary\":\"${OUTPUT}\",\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"}" >/dev/null 2>&1 || true
  redis-cli -a "${REDISCLI_AUTH:-${REDIS_PASSWORD:-BrainRedis2026}}" \
    SET voice:swift:build "${OUTPUT}" >/dev/null 2>&1 || true
fi

echo "Built ${OUTPUT}"
