#!/bin/bash
# Launch KarenLive menu bar app

APP_PATH="/Users/joe/brain/agentic-brain/tools/KarenLive/KarenLive.app"

# Kill any existing instance
pkill -f "KarenLive.app" 2>/dev/null

# Launch the app
open "$APP_PATH"

echo "KarenLive started - look for 🧠 in menu bar"
echo "Click the brain icon to start/stop listening"
