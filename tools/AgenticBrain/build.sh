#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "🔨 Building Agentic Brain..."

# Clean previous build
rm -rf AgenticBrain.app

# Compile Swift
swiftc -o AgenticBrain \
    -framework Cocoa \
    -framework AVFoundation \
    -framework Speech \
    -framework CoreAudio \
    -O \
    AgenticBrain.swift

# Create app bundle
mkdir -p AgenticBrain.app/Contents/MacOS
mkdir -p AgenticBrain.app/Contents/Resources
mv AgenticBrain AgenticBrain.app/Contents/MacOS/
cp Info.plist AgenticBrain.app/Contents/

# Sign the app (ad-hoc for local use)
codesign --force --deep --sign - AgenticBrain.app

echo "✅ Built AgenticBrain.app"
echo ""
echo "To run: open AgenticBrain.app"
echo "Or with Copilot: open AgenticBrain.app --args --copilot"
