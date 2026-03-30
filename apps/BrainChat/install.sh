#!/bin/bash
# install.sh - Build and install Brain Chat to /Applications
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🧠 Building Brain Chat..."
"$SCRIPT_DIR/build.sh" --clean --install

echo ""
echo "✅ Brain Chat installed to /Applications/Brain Chat.app"
echo "🚀 Launching..."
open "/Applications/Brain Chat.app"
