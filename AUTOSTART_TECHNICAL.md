# Agentic Brain - Auto-Start Technical Documentation

## Architecture Overview

The auto-start system uses macOS launchd to manage two services:

```
┌─────────────────────────────────────────────────────────────┐
│                    macOS System (launchd)                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  User Login Event                                             │
│        ↓                                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Service 1: com.agentic-brain.colima                │   │
│  │ Action: /usr/local/bin/colima start --quiet        │   │
│  │ Priority: low (nice=10)                            │   │
│  │ KeepAlive: YES (restart on crash)                  │   │
│  │ Throttle: 10 seconds                               │   │
│  │ Logs: /var/log/agentic-brain-colima.log            │   │
│  └─────────────────────────────────────────────────────┘   │
│        ↓ (after ~30 seconds, Docker ready)                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Service 2: com.agentic-brain.services              │   │
│  │ Action: /bin/bash -c /usr/local/bin/...            │   │
│  │ Script: start-services.sh                          │   │
│  │ Priority: low (nice=10)                            │   │
│  │ KeepAlive: YES (restart on crash)                  │   │
│  │ Throttle: 10 seconds                               │   │
│  │ Logs: /var/log/agentic-brain-services.log          │   │
│  └─────────────────────────────────────────────────────┘   │
│        ↓                                                      │
│  docker-compose up -d (Neo4j, Redis, Redpanda, API)         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
~/brain/agentic-brain/
├── scripts/
│   ├── install-autostart-mac.sh         ← Main installer (executable)
│   ├── start-services.sh                ← Created by installer (executable)
│   └── launchd/
│       ├── com.agentic-brain.colima.plist         ← Colima service
│       └── com.agentic-brain.services.plist       ← Services service
│
├── AUTOSTART.md                         ← Quick reference guide
├── INSTALL.md                           ← Updated with auto-start section
└── docker-compose.yml                   ← Services to start

~/Library/LaunchAgents/                 ← User login services (installed here)
├── com.agentic-brain.colima.plist      ← Symlink/copy of colima.plist
└── com.agentic-brain.services.plist    ← Symlink/copy of services.plist

/var/log/
├── agentic-brain-colima.log            ← Colima startup logs
└── agentic-brain-services.log          ← Services startup logs
```

## Plist File Format

### com.agentic-brain.colima.plist

```xml
<dict>
    <key>Label</key>
    <string>com.agentic-brain.colima</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/colima</string>
        <string>start</string>
        <string>--quiet</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>  <!-- Restart on crash only -->
    </dict>
    
    <key>ThrottleInterval</key>
    <integer>10</integer>  <!-- Wait 10s before restart -->
    
    <key>Nice</key>
    <integer>10</integer>  <!-- Low priority (don't slow down login) -->
</dict>
```

**Key Properties:**
- **Label**: Unique identifier for the service
- **ProgramArguments**: Command to run (array format)
- **RunAtLoad**: Start when launchd loads the plist (on login)
- **KeepAlive**: 
  - `<false/>` = don't restart if exits normally
  - `<dict><key>SuccessfulExit</key><false/></dict>` = restart only on crash
- **ThrottleInterval**: Minimum time between restart attempts
- **Nice**: Priority level (10 = lower priority, won't slow down system)

### com.agentic-brain.services.plist

Similar structure but runs the start-services.sh script instead.

## Installation Process

When you run `scripts/install-autostart-mac.sh`:

### 1. Prerequisites Check
```bash
# Verify macOS
uname -s =~ darwin*

# Check for Docker/Colima
which docker || which colima

# Verify docker-compose.yml exists
test -f docker-compose.yml
```

### 2. Create Plist Files
- Reads templates from `scripts/launchd/`
- Creates with correct paths baked in
- Sets file permissions to 644 (readable by launchd)

### 3. Install to LaunchAgents
```bash
cp scripts/launchd/com.agentic-brain.*.plist \
   ~/Library/LaunchAgents/
```

### 4. Load Services
```bash
launchctl load ~/Library/LaunchAgents/com.agentic-brain.colima.plist
launchctl load ~/Library/LaunchAgents/com.agentic-brain.services.plist
```

### 5. Verify Installation
```bash
launchctl list | grep com.agentic-brain
```

## Service Startup Sequence

### Colima Service Startup

1. **launchd detects** user login
2. **Loads** `com.agentic-brain.colima.plist`
3. **Runs** `/usr/local/bin/colima start --quiet`
4. **Colima** starts Docker VM (takes ~20-30 seconds)
5. **Docker daemon** becomes available at `/var/run/docker.sock`

### Services Startup (triggered by start-services.sh)

The `start-services.sh` script:

```bash
#!/bin/bash

# 1. Wait for Docker daemon (up to 30 seconds)
while ! docker ps &>/dev/null; do
    if [ $elapsed -ge 30 ]; then
        log "ERROR: Docker not available"
        exit 1
    fi
    sleep 1
    ((elapsed++))
done

# 2. Check docker-compose.yml exists
test -f docker-compose.yml

# 3. Ensure .env file exists
test -f .env || cp .env.example .env

# 4. Start services
docker compose up -d

# 5. Wait for services to be healthy
docker compose ps --services --filter "status=running"
```

**Exit codes:**
- 0 = Success (keep running or exit cleanly)
- Non-zero = Failure (launchd will restart after throttle interval)

## Idempotency

The installer is idempotent because:

1. **Unloads existing services first**
   ```bash
   launchctl unload plist 2>/dev/null || true
   ```

2. **Overwrites plist files**
   - New plists replace old ones
   - Same content means no-op on re-run

3. **Loads services**
   - Loading already-loaded service is a no-op
   - launchctl returns error but script continues

4. **Verification is non-destructive**
   - Only checks status, doesn't modify anything

## Logging

### Log Rotation

Logs are written to:
- `/var/log/agentic-brain-colima.log`
- `/var/log/agentic-brain-services.log`

**No automatic rotation** - manually clean up if needed:
```bash
rm -f /var/log/agentic-brain-*.log
```

### Log Format

Colima logs:
```
[2026-01-15 08:30:45] Colima started on 2026-01-15T08:30:45Z
```

Services logs:
```
[2026-01-15 08:30:45] Waiting for Docker daemon...
[2026-01-15 08:30:45] Docker daemon ready after 0s
[2026-01-15 08:30:45] Starting agentic-brain services...
[2026-01-15 08:30:47] agentic-brain-1  Running
[2026-01-15 08:30:47] neo4j-1          Running
[2026-01-15 08:30:47] redis-1          Running
[2026-01-15 08:30:47] redpanda-1       Running
[2026-01-15 08:30:47] Services running: 4/4
```

## Advanced Configuration

### Disable Auto-Restart

Edit `~/Library/LaunchAgents/com.agentic-brain.services.plist`:

```xml
<key>KeepAlive</key>
<false/>  <!-- Don't restart on failure -->
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.agentic-brain.services.plist
launchctl load ~/Library/LaunchAgents/com.agentic-brain.services.plist
```

### Custom Docker Command

Edit `com.agentic-brain.colima.plist`:

```xml
<key>ProgramArguments</key>
<array>
    <string>/Applications/Docker.app/Contents/Resources/docker/bin/docker-compose</string>
    <string>...</string>
</array>
```

### Custom Service Environment

Add to plist:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>CUSTOM_VAR</key>
    <string>value</string>
    <key>PATH</key>
    <string>/custom/path:/usr/local/bin:/usr/bin</string>
</dict>
```

### Change Log Location

Edit plist:

```xml
<key>StandardOutPath</key>
<string>/custom/path/colima.log</string>
<key>StandardErrorPath</key>
<string>/custom/path/colima.log</string>
```

## Troubleshooting

### How launchd fails (and how we handle it)

| Issue | Symptom | Solution |
|-------|---------|----------|
| Plist malformed | launchctl load fails | Validate XML, check paths |
| File permissions | Permission denied | `chmod 644 *.plist` |
| Path doesn't exist | Command not found | Fix ProgramArguments path |
| Process hangs | Service doesn't complete | Add timeout, check logs |
| Docker not ready | Docker connection refused | Wait loop in start-services.sh |
| Port in use | Bind failed | Kill conflicting process, change port |

### Debug launchd

```bash
# Check service status
launchctl list com.agentic-brain.services

# Output format: 
# {
#   "Label" = "com.agentic-brain.services";
#   "LimitLoadToSessionType" = "Aqua";
#   "OnDemand" = 0;
#   "PID" = 0;           # 0 = not running
#   "ProcessType" = "Background";
#   "Program" = "/bin/bash";
#   "ProgramArguments" = (...)
#   "StandardErrorPath" = "/var/log/agentic-brain-services.log";
#   "StandardOutPath" = "/var/log/agentic-brain-services.log";
#   "TimeOut" = 20;
# }

# Manually trigger service
launchctl start com.agentic-brain.services

# Force unload (even if running)
launchctl unload -w ~/Library/LaunchAgents/com.agentic-brain.services.plist

# Reload
launchctl load ~/Library/LaunchAgents/com.agentic-brain.services.plist
```

### Check Docker path

```bash
which docker
which colima
which docker-compose

# Add to PATH if needed
export PATH="/usr/local/bin:$PATH"
```

## Security Considerations

1. **No root required**
   - Services run as user (not sudo)
   - LaunchAgent (user login) not LaunchDaemon (system)

2. **Plist permissions**
   - Owned by user
   - Readable by launchd
   - Not writable by others

3. **Script security**
   - Shell script in user directory
   - User owns the script
   - No eval or dynamic code execution

4. **Sensitive data**
   - Passwords in .env file (user-only readable)
   - Logs contain service output (check /var/log permissions)

## Performance Characteristics

### Startup Time
```
Login Event
    ↓
Colima starts: ~20-30 seconds
    ↓
Docker available: ~30 seconds total
    ↓
Services start: ~5-10 seconds
    ↓
All services ready: ~30-40 seconds total from login
```

### Resource Usage
- **Memory**: ~100-200MB (Colima VM overhead)
- **CPU**: Intensive during startup, idle afterward
- **Disk**: Minimal (plist files ~3KB)
- **Network**: None (local only)

### Optimization
- Set `Nice` to 10 (lower priority)
- Services start after user's other login items
- Won't block user from using Mac during startup

## Future Enhancements

Potential improvements to the auto-start system:

1. **Health checks**
   - Monitor container health
   - Restart unhealthy containers

2. **Log rotation**
   - Automatic cleanup of old logs
   - Archive to dated files

3. **Metrics collection**
   - Track startup times
   - Alert on slow startups

4. **Configuration UI**
   - GUI to enable/disable services
   - Monitor real-time status

5. **Integration with other tools**
   - Homebrew uninstall cleanup
   - Rosetta 2 compatibility (Apple Silicon)
   - Multi-user support

## References

- [launchd Documentation](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [Property List Format](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/PropertyLists/UnderstandXMLPlist/UnderstandXMLPlist.html)
- [macOS Startup Sequence](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/Introduction.html)
