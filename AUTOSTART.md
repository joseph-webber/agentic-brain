# Agentic Brain - Auto-Start Installation Guide (macOS)

## Quick Start

```bash
cd ~/brain/agentic-brain

# Install auto-start (safe to run multiple times)
scripts/install-autostart-mac.sh

# Check status
scripts/install-autostart-mac.sh --status

# Remove auto-start
scripts/install-autostart-mac.sh --uninstall
```

## What This Does

✅ **Automatic startup on login:**
- Colima (or Docker) starts automatically
- All agentic-brain services follow (Neo4j, Redis, Redpanda)
- Services are monitored and restarted if they crash

✅ **Smart features:**
- Idempotent (safe to run multiple times)
- Waits for Docker to be ready before starting services
- Low-priority background processes (won't slow down login)
- Comprehensive logging

✅ **Easy management:**
- Check status: `scripts/install-autostart-mac.sh --status`
- View logs: `tail -f /var/log/agentic-brain-services.log`
- Uninstall: `scripts/install-autostart-mac.sh --uninstall`

## Installation Files

```
scripts/
├── install-autostart-mac.sh              (Main installer script)
├── start-services.sh                     (Helper script - created by installer)
└── launchd/
    ├── com.agentic-brain.colima.plist    (Colima startup service)
    └── com.agentic-brain.services.plist  (Services startup service)
```

## How It Works

### 1. Installer Creates Launchd Services

The installer script:
- Creates plist files in `~/Library/LaunchAgents/`
- Each plist is registered with launchd
- Services automatically start at login

### 2. Colima Service (first)
- Starts Colima or Docker
- Runs with low priority (nice value 10)
- Restarts automatically if it crashes
- Logs to: `/var/log/agentic-brain-colima.log`

### 3. Services Service (after Docker is ready)
- Waits up to 30 seconds for Docker daemon
- Runs `docker compose up -d` in the project directory
- Starts all containers (Neo4j, Redis, Redpanda, API)
- Logs to: `/var/log/agentic-brain-services.log`

## Manual Control

```bash
# Start services immediately (without waiting for login)
launchctl start com.agentic-brain.colima
sleep 10
launchctl start com.agentic-brain.services

# Stop services
launchctl stop com.agentic-brain.services
launchctl stop com.agentic-brain.colima

# Check if running
launchctl list | grep com.agentic-brain

# View logs
tail -f /var/log/agentic-brain-colima.log
tail -f /var/log/agentic-brain-services.log

# Disable auto-start at login
launchctl unload ~/Library/LaunchAgents/com.agentic-brain.*.plist

# Re-enable auto-start at login
launchctl load ~/Library/LaunchAgents/com.agentic-brain.*.plist
```

## Troubleshooting

### Services not starting?

1. **Check if services are loaded:**
   ```bash
   launchctl list | grep com.agentic-brain
   ```

2. **Check logs:**
   ```bash
   tail -50 /var/log/agentic-brain-services.log
   ```

3. **Manually start and check:**
   ```bash
   launchctl start com.agentic-brain.colima
   sleep 10
   launchctl start com.agentic-brain.services
   
   # Wait a moment then check
   docker compose -f ~/brain/agentic-brain/docker-compose.yml ps
   ```

### Permission errors?

```bash
# Fix plist permissions
chmod 644 ~/Library/LaunchAgents/com.agentic-brain.*.plist

# Reload services
launchctl unload ~/Library/LaunchAgents/com.agentic-brain.colima.plist
launchctl load ~/Library/LaunchAgents/com.agentic-brain.colima.plist
```

### Colima not found?

```bash
# Make sure Colima is installed
which colima

# If not found, install it
brew install colima

# Or use Docker Desktop instead
brew install --cask docker
```

## Advanced: Customization

### Change log location

Edit `~/Library/LaunchAgents/com.agentic-brain.services.plist`:

```xml
<key>StandardOutPath</key>
<string>/path/to/your/logs/services.log</string>
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.agentic-brain.services.plist
launchctl load ~/Library/LaunchAgents/com.agentic-brain.services.plist
```

### Disable auto-restart

Edit the plist and change:
```xml
<key>KeepAlive</key>
<false/>
```

### Change environment variables

Edit `com.agentic-brain.services.plist` and add:
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>VARIABLE_NAME</key>
    <string>value</string>
</dict>
```

## Complete Uninstall

```bash
# Remove services
scripts/install-autostart-mac.sh --uninstall

# Clean up (optional)
rm -f ~/Library/LaunchAgents/com.agentic-brain.*.plist
rm -f /var/log/agentic-brain-*.log
```

## Integration with System Preferences

Once installed, services are managed by macOS launchd system:

- View in: **System Settings → General → Login Items**
  - Not shown directly, but services run automatically
- Can't disable via GUI, use: `launchctl unload ...` instead
- Services survive system restarts and user logouts

## Performance Impact

- **Memory**: ~50-100MB (Colima/Docker VM overhead)
- **CPU**: Minimal when idle (process sleeps)
- **Startup time**: +5-10 seconds to overall login time

Services start with low priority (nice=10) so they don't slow down your Mac.

## Related Documentation

- Full guide: `INSTALL.md`
- Troubleshooting: `INSTALL.md` - Troubleshooting section
- Docker setup: `DOCKER.md`
- Architecture: See `/scripts/README.md` for all available scripts

## Support

- Check logs: `/var/log/agentic-brain-*.log`
- Verify status: `scripts/install-autostart-mac.sh --status`
- Uninstall: `scripts/install-autostart-mac.sh --uninstall`
- Report issues: See project's issue tracker
