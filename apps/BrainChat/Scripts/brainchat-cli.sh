#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BRAINCHAT_RELEASE="$PROJECT_DIR/.build/release/BrainChat"
BRAINCHAT_DEBUG="$PROJECT_DIR/.build/debug/BrainChat"

if [[ -x "$BRAINCHAT_RELEASE" ]]; then
  BRAINCHAT="$BRAINCHAT_RELEASE"
elif [[ -x "$BRAINCHAT_DEBUG" ]]; then
  BRAINCHAT="$BRAINCHAT_DEBUG"
else
  echo "BrainChat binary not found. Build it with 'swift build -c release' first." >&2
  exit 1
fi

case "${1:-}" in
  send)
    shift
    "$BRAINCHAT" --send "$*"
    ;;
  listen)
    shift
    "$BRAINCHAT" --listen "$@"
    ;;
  speak)
    shift
    "$BRAINCHAT" --speak "$*"
    ;;
  ""|-h|--help|help)
    cat <<'EOF'
Usage: brainchat-cli.sh {send|listen|speak} [text]

Examples:
  brainchat-cli.sh send Hello Joseph
  brainchat-cli.sh speak Ready for work
  brainchat-cli.sh listen
EOF
    ;;
  *)
    echo "Usage: brainchat-cli.sh {send|listen|speak} [text]" >&2
    exit 1
    ;;
esac
