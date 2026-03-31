#!/bin/bash
# Apply the mic permission fix to BrainChat

set -euo pipefail

cd ~/brain/agentic-brain/apps/BrainChat

echo "🎙️  APPLYING MIC PERMISSION FIX TO BRAINCHAT"
echo "=================================================="
echo ""

# Show what was changed
echo "✅ Changes applied:"
echo ""
echo "1. SpeechManager.swift:"
echo "   - Added isMicrophoneAuthorized() method"
echo "   - Added requestMicrophonePermissionWithCompletion() method"
echo "   - These provide proper async permission handling like KarenVoice"
echo ""
echo "2. ContentView.swift:"
echo "   - Fixed toggleMic() to request permission BEFORE starting"
echo "   - Added completion handler to wait for user's choice"
echo "   - Removed auto-request on app launch (prevents race condition)"
echo ""
echo "3. Key difference from before:"
echo "   OLD: Request async, check sync → race condition"
echo "   NEW: Request with completion, wait, then start → no race"
echo ""

# Clean build
echo "🧹 Cleaning old build..."
rm -rf build
rm -rf "$HOME/brain/agentic-brain/apps/BrainChat/runtime"
mkdir -p "$HOME/brain/agentic-brain/apps/BrainChat/runtime"

# Build with fresh code
echo "🔨 Building with fixed code..."
./build.sh --install

echo ""
echo "=================================================="
echo "✅ BUILD COMPLETE"
echo "=================================================="
echo ""
echo "Next: Run the test script to verify:"
echo "  ./test_mic_permission.sh"
echo ""
echo "Or launch manually:"
echo "  open /Applications/Brain\\ Chat.app"
echo ""
echo "Then click the mic button - permission dialog should appear!"
echo ""

say -v "Karen (Premium)" -r 160 "Build complete! Ready to test the mic button."
