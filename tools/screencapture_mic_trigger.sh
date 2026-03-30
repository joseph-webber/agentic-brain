#!/bin/bash
# screencapture_mic_trigger.sh
#
# ALTERNATIVE APPROACH: Use macOS's own screencapture tool to trigger
# the microphone permission dialog. screencapture -V records video+audio
# which forces a TCC prompt for microphone access.
#
# This attributes the request to screencapture (a system binary) which
# sidesteps Terminal's TCC status entirely.
#
# Use this if MicRequestApp.app doesn't work.

echo "Attempting to trigger mic permission via screencapture..."
echo "(A small recording will be attempted — you may see a 3-second countdown)"
echo ""

# -V N = record video for N seconds, -g = capture audio
# This WILL trigger the mic permission popup on notDetermined systems
OUTFILE="$(pwd)/mic_test_recording.mov"
screencapture -V 2 -g "$OUTFILE" 2>&1

STATUS=$?
echo ""
if [ $STATUS -eq 0 ] && [ -f "$OUTFILE" ]; then
    SIZE=$(stat -f%z "$OUTFILE" 2>/dev/null || echo 0)
    echo "✅ Recording saved: $OUTFILE (${SIZE} bytes)"
    echo "   Mic permission should now be granted."
    rm -f "$OUTFILE"
elif [ $STATUS -eq 0 ]; then
    echo "✅ screencapture completed"
else
    echo "⚠  screencapture exited with status $STATUS"
    echo "   This may mean permission was denied or user cancelled."
fi

echo ""
echo "Current permission status:"
swift -e "import AVFoundation; let s=AVCaptureDevice.authorizationStatus(for:.audio); switch s { case .authorized: print(\"✅ AUTHORIZED\"); case .denied: print(\"⛔ DENIED\"); case .notDetermined: print(\"⏳ NOT_DETERMINED\"); case .restricted: print(\"🔒 RESTRICTED\"); default: print(\"UNKNOWN\") }" 2>/dev/null
