#!/usr/bin/env bash
# setup.sh — One-time permission setup for VoiceInput
# Run from Terminal.app (Dock → Terminal, or Spotlight → Terminal)
# NOT from Copilot CLI or SSH — those sessions can't show TCC dialogs.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$SCRIPT_DIR/VoiceInput.app"

speak() { say -v "Karen (Premium)" "$1" -r 155 2>/dev/null || say "$1" -r 155; }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  VoiceInput — One-Time Permission Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

speak "Starting Voice Input permission setup."

# ── Check if already authorised ───────────────────────────────────────────────
MIC_STATUS=$(osascript -e '
use framework "AVFoundation"
return (current application'"'"'s AVCaptureDevice'"'"'s authorizationStatusForMediaType:"vide") as integer
' 2>/dev/null || echo "unknown")
echo "  (This script must be run from Terminal.app, not from SSH or Copilot CLI)"
echo ""

# ── Reset TCC so dialogs appear ───────────────────────────────────────────────
echo "  Resetting previous permission state…"
tccutil reset Microphone com.josephwebber.brain.voiceinput 2>/dev/null || true
tccutil reset SpeechRecognition com.josephwebber.brain.voiceinput 2>/dev/null || true

# ── Method 1: Try running the app from THIS terminal ─────────────────────────
echo "  Launching VoiceInput (30s window for permission dialogs)…"
echo ""
speak "Launching Voice Input. Two permission dialogs will appear. Press space or return to allow each one."

"$APP/Contents/MacOS/VoiceInput" 25 2>&1 &
APP_PID=$!

# Show countdown
for i in 25 20 15 10 5; do
    sleep 5
    if ! kill -0 "$APP_PID" 2>/dev/null; then break; fi
    echo "  Waiting… ${i}s remaining"
done
wait "$APP_PID" 2>/dev/null
EXIT=$?

echo ""
if [ "$EXIT" -eq 0 ] || [ "$EXIT" -eq 2 ]; then
    echo "  ✅ Permissions granted! VoiceInput is ready."
    speak "Voice Input is ready. You can now use it from Copilot CLI."
    echo ""
    echo "  Usage from Copilot CLI:"
    echo "    TEXT=\$($APP/Contents/MacOS/VoiceInput 10)"
    echo "    python3 $SCRIPT_DIR/voice_input.py 10"
else
    echo "  ✖  Permission dialogs may not have appeared."
    echo ""
    echo "  ── Manual grant (VoiceOver steps) ─────────────────────"
    echo "  1. Press Cmd+Space, type 'System Settings', press Return"
    echo "  2. VO+F to search, type 'Microphone', press Return"
    echo "  3. Find 'VoiceInput' in the list"
    echo "  4. Press Space to toggle it ON"
    echo "  5. Repeat for 'Speech Recognition' if asked"
    echo "  ───────────────────────────────────────────────────────"
    echo ""
    speak "Permission dialogs did not appear. Please open System Settings, go to Privacy and Security, then Microphone, and enable Voice Input manually."
    echo "  Opening System Settings › Microphone for you…"
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
    echo ""
    echo "  After granting access, test with:"
    echo "    $APP/Contents/MacOS/VoiceInput 5"
fi
