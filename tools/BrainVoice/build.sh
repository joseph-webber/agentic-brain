#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "🔨 Building Brain Voice..."

rm -rf BrainVoice.app

# Compile with -parse-as-library for @main
swiftc -o BrainVoice \
    -parse-as-library \
    -framework Cocoa \
    -framework AVFoundation \
    -framework Speech \
    -framework CoreAudio \
    -O \
    BrainVoice.swift 2>&1

# Create app bundle
mkdir -p BrainVoice.app/Contents/MacOS
mkdir -p BrainVoice.app/Contents/Resources
mv BrainVoice BrainVoice.app/Contents/MacOS/
cp Info.plist BrainVoice.app/Contents/

# Sign
codesign --force --deep --sign - BrainVoice.app

echo "✅ Built BrainVoice.app"
echo "Run: open BrainVoice.app"
