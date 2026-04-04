#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Agentic Brain Contributors
#
# Create DMG installer for BrainChat macOS application
# Usage: ./create-dmg.sh

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
APP_BUNDLE="${BUILD_DIR}/Brain Chat.app"
TEMP_DIR="${BUILD_DIR}/.dmg-tmp"
DMG_FILENAME="${SCRIPT_DIR}/BrainChat-$(PlistBuddy -c 'Print CFBundleShortVersionString' "${SCRIPT_DIR}/Info.plist").dmg"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${GREEN}✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; exit 1; }

# Verify app bundle exists
if [ ! -d "$APP_BUNDLE" ]; then
    log_error "App bundle not found: $APP_BUNDLE"
fi

log_info "Creating DMG installer for BrainChat"
log_info "DMG output: $DMG_FILENAME"

# Clean up any existing temporary directory
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Create staging area for DMG contents
STAGE_DIR="${TEMP_DIR}/stage"
mkdir -p "$STAGE_DIR"

# Copy app bundle to staging
cp -R "$APP_BUNDLE" "$STAGE_DIR/"

# Create Applications symlink for drag-to-install
ln -s /Applications "$STAGE_DIR/Applications"

# Create a nice background image (if needed in future)
# For now, we'll create a simple one programmatically
create_background_image() {
    local bg_file="$TEMP_DIR/background.png"
    
    # Create a 1920x1200 background with gradient
    python3 << 'PYTHON'
import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw
    
    width, height = 1920, 1200
    
    # Create image with gradient background (macOS Monterey-inspired)
    image = Image.new('RGB', (width, height), color=(240, 240, 245))
    draw = ImageDraw.Draw(image)
    
    # Add subtle gradient effect
    for y in range(height):
        r = int(240 - (y / height) * 15)
        g = int(240 - (y / height) * 15)
        b = int(245 - (y / height) * 5)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Save background
    bg_path = os.environ.get('BG_FILE', '/tmp/background.png')
    image.save(bg_path)
    print(f"Background created: {bg_path}")
except ImportError:
    print("PIL not available, skipping background image")
PYTHON
}

# Try to create background (non-fatal if fails)
export BG_FILE="${TEMP_DIR}/background.png"
create_background_image || log_warn "Could not create background image"

# Create the DMG
log_info "Creating DMG archive..."

# Remove existing DMG if present
rm -f "$DMG_FILENAME"

# Create temporary sparse image
SPARSE_DMG="${TEMP_DIR}/BrainChat.sparseimage"
hdiutil create -volname "BrainChat" \
    -srcfolder "$STAGE_DIR" \
    -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" \
    -format UDSP \
    "$SPARSE_DMG"

# Convert to compressed DMG
log_info "Compressing DMG..."
hdiutil convert "$SPARSE_DMG" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "$DMG_FILENAME"

# Attach DMG to set visual appearance properties
log_info "Setting DMG appearance properties..."
MOUNT_POINT="/Volumes/BrainChat-$$"
hdiutil attach "$DMG_FILENAME" -mountpoint "$MOUNT_POINT" -nobrowse

# Create aliases using AppleScript for better icon placement
osascript << 'APPLESCRIPT' 2>/dev/null || true
tell application "Finder"
    tell disk "BrainChat"
        open
        delay 1
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {400, 100, 900, 550}
        set theViewOptions to the icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to 64
        set text size of theViewOptions to 12
        
        -- Position Brain Chat app
        set position of item "Brain Chat.app" of container window to {150, 100}
        
        -- Position Applications folder
        set position of item "Applications" of container window to {450, 100}
        
        -- Add custom background if available
        tell container window
            set background picture to file "POSIX file \"/private/tmp/background.png\"" as alias
        end tell
        
        close
        delay 1
    end tell
end tell
APPLESCRIPT

# Detach the DMG
hdiutil detach "$MOUNT_POINT" 2>/dev/null || true
sleep 1

# Verify DMG was created successfully
if [ ! -f "$DMG_FILENAME" ]; then
    log_error "Failed to create DMG file"
fi

# Get DMG file size
DMG_SIZE=$(du -h "$DMG_FILENAME" | cut -f1)
log_info "DMG created successfully: $DMG_FILENAME (${DMG_SIZE})"

# Clean up temporary files
rm -rf "$TEMP_DIR"

# Create checksum file
log_info "Creating checksum..."
shasum -a 256 "$DMG_FILENAME" > "${DMG_FILENAME}.sha256"
cat "${DMG_FILENAME}.sha256"

log_info "DMG installer ready for distribution"
log_info "To test: hdiutil attach '${DMG_FILENAME}'"
