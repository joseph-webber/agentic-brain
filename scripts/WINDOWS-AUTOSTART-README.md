# Windows Auto-Start Installation Guide

This directory contains scripts to set up automatic startup of agentic-brain services on Windows.

## Files

- **install-autostart-windows.ps1** - PowerShell script (main installer)
- **install-autostart-windows.bat** - Batch wrapper (user-friendly entry point)

## Quick Start

### Recommended: Using Batch File

1. Open **Command Prompt** or **PowerShell** as Administrator
2. Navigate to the agentic-brain root directory
3. Run:
   ```batch
   scripts\install-autostart-windows.bat
   ```

That's it! Services will now auto-start on login.

### Alternative: Using PowerShell

```powershell
# Run as Administrator
cd path\to\agentic-brain
.\scripts\install-autostart-windows.ps1
```

## What It Does

The installer script performs these actions:

### 1. Docker Desktop Auto-Start
- Enables "Start Docker Desktop when you log in" setting
- Uses Windows Registry to configure auto-start
- Verified installation path: `C:\Program Files\Docker\Docker\`

### 2. Services Auto-Start
- Creates Windows Task Scheduler tasks to start services
- Waits for Docker daemon to be ready (retry logic included)
- Starts `docker compose up -d` automatically
- Monitors service startup with health checks

### 3. Logging
- Logs startup events to: `%APPDATA%\AgenticBrain\docker-startup.log`
- Useful for troubleshooting auto-start issues

## Features

✅ **Automatic Recovery** - Retries Docker connection up to 30 times (60 seconds total)
✅ **Smart Detection** - Detects if services are already running
✅ **Admin Enforcement** - Requires Administrator rights for Task Scheduler
✅ **WSL2 Compatible** - Works with Docker Desktop using WSL2 backend
✅ **Clean Uninstall** - `-Uninstall` parameter removes all tasks and registry entries
✅ **Logging** - Writes detailed logs for troubleshooting

## Uninstall

To remove auto-start and return to manual startup:

```batch
scripts\install-autostart-windows.bat uninstall
```

Or with PowerShell:
```powershell
.\scripts\install-autostart-windows.ps1 -Uninstall
```

## Troubleshooting

### Services Don't Auto-Start After Login

1. **Check Task Scheduler:**
   ```powershell
   # View all tasks
   Get-ScheduledTask | Where-Object { $_.TaskName -like "*AgenticBrain*" }
   
   # Check last result
   Get-ScheduledTask -TaskName "AgenticBrain-StartServices" | Get-ScheduledTaskInfo
   ```

2. **Check logs:**
   ```powershell
   # View startup logs (live updates with -Tail)
   Get-Content "$env:APPDATA\AgenticBrain\docker-startup.log" -Tail 50 -Wait
   ```

3. **Manual test:**
   ```powershell
   # Manually run the task to see any errors
   Start-ScheduledTask -TaskName "AgenticBrain-StartServices"
   Start-Sleep -Seconds 30
   docker compose ps
   ```

### "Administrator Rights Required" Error

The script must be run as Administrator to create Task Scheduler tasks.

**Solution:**
1. Right-click Command Prompt or PowerShell
2. Select "Run as administrator"
3. Run the script again

### Docker Desktop Not Found

The installer checks for Docker Desktop installation.

**Solution:**
1. Download Docker Desktop: https://www.docker.com/products/docker-desktop
2. Install and restart computer
3. Run the installer script again

### Services Start But Show Unhealthy

Check if Docker Desktop has sufficient resources allocated:

1. Open Docker Desktop → Settings
2. Go to Resources tab
3. Increase:
   - **CPUs**: At least 2
   - **Memory**: At least 4GB
   - **Disk Image Size**: At least 50GB

### Task Scheduler Task Keeps Failing

Check the startup script logs:

```powershell
Get-Content "$env:APPDATA\AgenticBrain\docker-startup.log"
```

Common issues:
- Docker Desktop not running
- Insufficient disk space
- Port conflicts (7474, 7687, 6379, 9092, 8000)
- Corrupted docker-compose.yml

## Manual Task Scheduler Setup

If the installer fails, you can manually create tasks:

1. **Open Task Scheduler:**
   ```
   taskschd.msc
   ```

2. **Create "AgenticBrain-StartServices" task:**
   - **Trigger:** At logon (your username)
   - **Action:** Start program
   - **Program:** `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
   - **Arguments:** 
     ```
     -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\path\to\agentic-brain\scripts\start-agentic-services.ps1"
     ```
   - **Settings:** 
     - ✅ "Run with highest privileges"
     - ✅ "Run only when user is logged in"
     - ✅ "If task is already running, do not start new instance"

3. **Create "AgenticBrain-StartServices-Startup" task (optional):**
   - Same as above but trigger at system startup instead of logon

## Performance Impact

Auto-start tasks have minimal performance impact:
- Run in background (hidden window)
- Only execute on login/startup
- Subsequent checks exit immediately if services already running
- No continuous monitoring or scheduled retries

## Security Considerations

**Local System:**
- Tasks run as your user account (not SYSTEM)
- Requires Administrator privileges for setup
- No remote access or network exposure
- Registry modifications are local only

**Environment Variables:**
- Neo4j password: Configured in `.env` file
- Redis: No password for local dev
- Ensure `.env` is in `.gitignore` (never commit secrets)

## Environment

The auto-start uses your project's `.env` configuration:
- Services use settings from `.env.docker` or `.env`
- Custom ports can be configured in `.env`
- Default ports: API=8000, Neo4j=7687, Redis=6379, Redpanda=9092

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs: `$env:APPDATA\AgenticBrain\docker-startup.log`
3. Test manually: `docker compose ps`
4. Check Docker Desktop status in System Tray

---

**Last Updated:** 2024
**Compatibility:** Windows 10 (Build 19041+) and Windows 11
**Requirements:** Docker Desktop 4.0+, PowerShell 5.0+
