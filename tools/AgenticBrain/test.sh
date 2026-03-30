#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "🧪 Testing Agentic Brain..."

PASS=0
FAIL=0

# Test 1: Build exists
if [[ -d "AgenticBrain.app" ]]; then
    echo "✅ App bundle exists"
    ((PASS++))
else
    echo "❌ App bundle missing - run ./build.sh first"
    ((FAIL++))
fi

# Test 2: Binary exists and is executable
if [[ -x "AgenticBrain.app/Contents/MacOS/AgenticBrain" ]]; then
    echo "✅ Binary is executable"
    ((PASS++))
else
    echo "❌ Binary not executable"
    ((FAIL++))
fi

# Test 3: Info.plist has required keys
if plutil -lint AgenticBrain.app/Contents/Info.plist &>/dev/null; then
    echo "✅ Info.plist is valid"
    ((PASS++))
else
    echo "❌ Info.plist is invalid"
    ((FAIL++))
fi

# Test 4: Microphone permission key exists
if grep -q "NSMicrophoneUsageDescription" AgenticBrain.app/Contents/Info.plist; then
    echo "✅ Microphone permission configured"
    ((PASS++))
else
    echo "❌ Missing NSMicrophoneUsageDescription"
    ((FAIL++))
fi

# Test 5: Speech recognition key exists  
if grep -q "NSSpeechRecognitionUsageDescription" AgenticBrain.app/Contents/Info.plist; then
    echo "✅ Speech recognition permission configured"
    ((PASS++))
else
    echo "❌ Missing NSSpeechRecognitionUsageDescription"
    ((FAIL++))
fi

# Test 6: Code signature valid
if codesign -v AgenticBrain.app 2>/dev/null; then
    echo "✅ Code signature valid"
    ((PASS++))
else
    echo "❌ Code signature invalid"
    ((FAIL++))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"

if [[ $FAIL -eq 0 ]]; then
    echo "�� All tests passed!"
    exit 0
else
    echo "💥 Some tests failed"
    exit 1
fi
