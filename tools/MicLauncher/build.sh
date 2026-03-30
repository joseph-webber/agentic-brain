#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${SCRIPT_DIR}/mic_launcher"
SOURCE="${SCRIPT_DIR}/main.swift"

echo "Building MicLauncher…"
swiftc -o "${OUTPUT}" "${SOURCE}"
chmod +x "${OUTPUT}"
echo "Built ${OUTPUT}"
