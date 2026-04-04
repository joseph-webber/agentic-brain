#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Agentic Brain Contributors
#
# Create appcast.xml for Sparkle auto-updates
# Generates update metadata from GitHub releases

set -euo pipefail

REPO_OWNER="${1:-getagentic}"
REPO_NAME="${2:-brain}"
OUTPUT_FILE="${3:-appcast.xml}"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*"; }

log_info "Generating appcast.xml for Sparkle auto-updates"

# Fetch latest BrainChat release info
log_info "Fetching latest release from GitHub..."

RELEASE_DATA=$(curl -s "https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest" \
    -H "Accept: application/vnd.github.v3+json")

if [ -z "$RELEASE_DATA" ] || echo "$RELEASE_DATA" | grep -q '"message"'; then
    log_warn "Could not fetch release data, creating template"
    RELEASE_DATA="{}"
fi

# Extract release info
TAG=$(echo "$RELEASE_DATA" | grep '"tag_name"' | cut -d'"' -f4 || echo "v1.2.0")
VERSION="${TAG#v}"
RELEASE_DATE=$(date -u +"%a, %d %b %Y %T %z")
RELEASE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${TAG}"

# Find DMG asset
DMG_ASSET=$(echo "$RELEASE_DATA" | grep -o '"browser_download_url":"[^"]*\.dmg"' | head -1 | cut -d'"' -f4 || echo "")

cat > "$OUTPUT_FILE" << 'APPCAST'
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <title>BrainChat</title>
    <link>https://github.com/getagentic/brain</link>
    <description>macOS AI Chat Application with Voice</description>
    <language>en-us</language>
APPCAST

# Generate items for recent releases
echo "$RELEASE_DATA" | while IFS= read -r line; do
    if echo "$line" | grep -q '"tag_name"'; then
        TAG=$(echo "$line" | cut -d'"' -f4)
        VERSION="${TAG#v}"
        
        cat >> "$OUTPUT_FILE" << ITEM

    <item>
      <title>BrainChat $VERSION</title>
      <description>
        <![CDATA[
          BrainChat $VERSION is now available.
          
          <h2>Features</h2>
          <ul>
            <li>🧠 Multi-LLM support (Claude, Groq, OpenAI, Grok, Gemini, Ollama)</li>
            <li>🎤 Advanced speech recognition with Whisper</li>
            <li>🔐 4-tier security model</li>
            <li>📝 Full AppleScript support</li>
            <li>⚡ Optimized for Apple Silicon</li>
          </ul>
        ]]>
      </description>
      <pubDate>$(date -u +"%a, %d %b %Y %T %z")</pubDate>
      <sparkle:version>$VERSION</sparkle:version>
      <sparkle:shortVersionString>$VERSION</sparkle:shortVersionString>
      <enclosure url="$RELEASE_URL/BrainChat-$VERSION.dmg"
                 sparkle:version="$VERSION"
                 sparkle:shortVersionString="$VERSION"
                 type="application/x-dmg"
                 length="0" />
    </item>
ITEM
    fi
done

cat >> "$OUTPUT_FILE" << 'APPCAST'
  </channel>
</rss>
APPCAST

log_info "Appcast generated: $OUTPUT_FILE"
log_info "Add this to your Info.plist:"
echo "  <key>SUFeedURL</key>"
echo "  <string>https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main/apps/BrainChat/appcast.xml</string>"
