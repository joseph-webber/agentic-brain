# 🎤 Microphone Permission Fix - SOLUTION

## The Problem
Apps launched from SSH sessions inherit SSH process ancestry. macOS TCC blocks permission dialogs for any process with SSH in its ancestry chain.

## The Solution ✅

**Two options installed:**

### Option 1: LaunchAgent (Recommended)
```bash
# From any terminal (including SSH):
launchctl start com.josephwebber.brainchat.launcher

# Or use the wrapper:
brainchat-clean
```

### Option 2: Launcher App
```bash
# Spotlight search: "Launch Brain Chat"
# Or double-click in /Applications/Launch Brain Chat.app
# Or: open -a "Launch Brain Chat"
```

## Why This Works

✅ Brain Chat PID 6460 has **Parent PID: 1** (launchd)
✅ No SSH ancestry in the process tree
✅ TCC sees a GUI app launched from launchd
✅ Permission dialogs will appear!

## Files Installed

| File | Purpose |
|------|---------|
| `~/Library/LaunchAgents/com.josephwebber.brainchat.launcher.plist` | LaunchAgent that launches Brain Chat cleanly |
| `/Applications/Launch Brain Chat.app` | GUI app for clean launching |
| `~/bin/brainchat-clean` | Convenience wrapper script |

## Testing

1. Reset permissions: `tccutil reset Microphone com.josephwebber.brainchat`
2. Launch cleanly: `launchctl start com.josephwebber.brainchat.launcher`
3. Click mic button in Brain Chat
4. **Permission dialog should appear!**

## Key Insight

The `launchctl start` command tells launchd to run the job. Since launchd (PID 1) is the parent, there's no SSH ancestry. The `open -a` command in the LaunchAgent runs Brain Chat as a child of launchd, not as a child of our SSH session.
