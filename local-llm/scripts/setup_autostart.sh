#!/bin/bash
# =============================================================================
# Ollama Auto-Start Setup Script
# =============================================================================
# Creates LaunchAgent for macOS or systemd service for Linux
# Ensures Ollama starts on boot and stays running
#
# Usage: ./setup_autostart.sh [--warm-model MODEL_NAME]
# =============================================================================

set -e

WARM_MODEL="${1:-llama3.2:3b}"  # Default warm model
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🦙 OLLAMA AUTO-START SETUP"
echo "=========================="
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "📍 Detected: macOS"
elif [[ -f /etc/systemd/system/ollama.service ]] || command -v systemctl &> /dev/null; then
    OS="linux"
    echo "📍 Detected: Linux (systemd)"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

# Check Ollama installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not installed!"
    echo "   Install with: curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
fi
echo "✅ Ollama installed: $(ollama --version 2>/dev/null || echo 'version unknown')"

# Find Ollama binary
OLLAMA_BIN=$(which ollama)
echo "✅ Ollama binary: $OLLAMA_BIN"

# =============================================================================
# macOS Setup (LaunchAgent)
# =============================================================================
if [[ "$OS" == "macos" ]]; then
    LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$LAUNCH_AGENT_DIR/com.ollama.serve.plist"
    WARMUP_PLIST="$LAUNCH_AGENT_DIR/com.ollama.warmup.plist"
    
    mkdir -p "$LAUNCH_AGENT_DIR"
    
    # Create main Ollama service
    echo ""
    echo "📝 Creating LaunchAgent for Ollama..."
    cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.serve</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>$OLLAMA_BIN</string>
        <string>serve</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>ThrottleInterval</key>
    <integer>5</integer>
    
    <key>StandardOutPath</key>
    <string>/tmp/ollama.log</string>
    
    <key>StandardErrorPath</key>
    <string>/tmp/ollama.error.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>OLLAMA_KEEP_ALIVE</key>
        <string>1h</string>
        <key>OLLAMA_MAX_LOADED_MODELS</key>
        <string>2</string>
    </dict>
</dict>
</plist>
EOF
    echo "✅ Created: $PLIST_FILE"
    
    # Create warmup script
    WARMUP_SCRIPT="$SCRIPT_DIR/warmup_model.sh"
    echo ""
    echo "📝 Creating warm-up script..."
    cat > "$WARMUP_SCRIPT" << EOF
#!/bin/bash
# Warm up the default model after Ollama starts
# This keeps the model loaded in RAM for instant responses

WARM_MODEL="$WARM_MODEL"
MAX_WAIT=60
WAITED=0

echo "[\$(date)] Waiting for Ollama to be ready..."

# Wait for Ollama to be ready
while ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
    WAITED=\$((WAITED + 2))
    if [ \$WAITED -ge \$MAX_WAIT ]; then
        echo "[\$(date)] Timeout waiting for Ollama"
        exit 1
    fi
done

echo "[\$(date)] Ollama ready, warming up \$WARM_MODEL..."

# Send a warmup request with long keep-alive
RESPONSE=\$(curl -s http://localhost:11434/api/generate \
    -d "{\"model\":\"\$WARM_MODEL\",\"prompt\":\"warmup\",\"stream\":false,\"keep_alive\":\"24h\"}")

if echo "\$RESPONSE" | grep -q '"done":true'; then
    echo "[\$(date)] ✅ \$WARM_MODEL is warm and ready!"
else
    echo "[\$(date)] ⚠️ Warmup may have failed: \$RESPONSE"
fi
EOF
    chmod +x "$WARMUP_SCRIPT"
    echo "✅ Created: $WARMUP_SCRIPT"
    
    # Create warmup LaunchAgent
    echo ""
    echo "📝 Creating warmup LaunchAgent..."
    cat > "$WARMUP_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.warmup</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>$WARMUP_SCRIPT</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>StartInterval</key>
    <integer>3600</integer>
    
    <key>StandardOutPath</key>
    <string>/tmp/ollama-warmup.log</string>
    
    <key>StandardErrorPath</key>
    <string>/tmp/ollama-warmup.error.log</string>
</dict>
</plist>
EOF
    echo "✅ Created: $WARMUP_PLIST"
    
    # Unload existing agents
    echo ""
    echo "🔄 Loading LaunchAgents..."
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    launchctl unload "$WARMUP_PLIST" 2>/dev/null || true
    
    # Load new agents
    launchctl load "$PLIST_FILE"
    echo "✅ Loaded com.ollama.serve"
    
    sleep 3
    launchctl load "$WARMUP_PLIST"
    echo "✅ Loaded com.ollama.warmup"
    
    # Verify
    echo ""
    echo "🔍 Verifying setup..."
    sleep 3
    
    if launchctl list | grep -q "com.ollama.serve"; then
        echo "✅ Ollama service is running"
    else
        echo "⚠️ Ollama service may not be running"
    fi
    
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama API is responding"
    else
        echo "⚠️ Ollama API not yet responding (may need a moment)"
    fi

# =============================================================================
# Linux Setup (systemd)
# =============================================================================
elif [[ "$OS" == "linux" ]]; then
    echo ""
    echo "📝 Configuring systemd service..."
    
    # Enable the service
    sudo systemctl enable ollama
    echo "✅ Enabled ollama.service"
    
    # Start if not running
    if ! systemctl is-active --quiet ollama; then
        sudo systemctl start ollama
        echo "✅ Started ollama.service"
    else
        echo "✅ Ollama already running"
    fi
    
    # Create warmup service
    WARMUP_SERVICE="/etc/systemd/system/ollama-warmup.service"
    WARMUP_SCRIPT="/usr/local/bin/ollama-warmup.sh"
    
    echo ""
    echo "📝 Creating warmup script..."
    sudo tee "$WARMUP_SCRIPT" > /dev/null << EOF
#!/bin/bash
sleep 10
curl -s http://localhost:11434/api/generate \
    -d '{"model":"$WARM_MODEL","prompt":"warmup","stream":false,"keep_alive":"24h"}'
EOF
    sudo chmod +x "$WARMUP_SCRIPT"
    echo "✅ Created: $WARMUP_SCRIPT"
    
    echo ""
    echo "📝 Creating warmup service..."
    sudo tee "$WARMUP_SERVICE" > /dev/null << EOF
[Unit]
Description=Ollama Model Warmup
After=ollama.service
Requires=ollama.service

[Service]
Type=oneshot
ExecStart=$WARMUP_SCRIPT
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable ollama-warmup
    sudo systemctl start ollama-warmup
    echo "✅ Warmup service configured"
fi

# =============================================================================
# Final Summary
# =============================================================================
echo ""
echo "========================================"
echo "✅ AUTO-START SETUP COMPLETE"
echo "========================================"
echo ""
echo "Configuration:"
echo "  • Ollama will start automatically on boot"
echo "  • Warm model: $WARM_MODEL (pre-loaded for fast response)"
echo "  • Keep-alive: 1 hour (model stays in RAM)"
echo ""
echo "Logs:"
echo "  • Ollama: /tmp/ollama.log"
echo "  • Errors: /tmp/ollama.error.log"
echo "  • Warmup: /tmp/ollama-warmup.log"
echo ""
echo "Commands:"
echo "  • Check status: curl http://localhost:11434/api/tags"
echo "  • View loaded: ollama ps"
echo "  • Test model:  ollama run $WARM_MODEL"
echo ""
echo "To test auto-start: Reboot and run ./scripts/bootstrap_test.sh"
