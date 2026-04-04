#!/bin/bash
# Quick startup script for WebSocket PTY Bridge Server

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if websockets is installed
if ! python3 -c "import websockets" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip3 install -r "$SCRIPT_DIR/requirements.txt"
fi

# Parse arguments
HOST="${1:-0.0.0.0}"
PORT="${2:-8765}"
LOG_LEVEL="${3:-INFO}"

echo ""
echo "🚀 Starting WebSocket PTY Bridge Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Host:  $HOST"
echo "  Port:  $PORT"
echo "  Level: $LOG_LEVEL"
echo ""
echo "📖 Documentation: file://$SCRIPT_DIR/README.md"
echo ""
echo "To connect:"
echo "  1. Open your browser"
echo "  2. Navigate to: file://$SCRIPT_DIR/client.html"
echo "  3. Or serve via HTTP and visit: http://localhost:3000/client.html"
echo ""
echo "Server logs below:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run server
cd "$SCRIPT_DIR"
python3 server.py --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL"
