#!/usr/bin/env python3
"""
Brain Apple MCP Server (FastMCP version)
========================================

Mac system integration tools.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.expanduser('~/brain'))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("brain-apple")


def run_osascript(script: str) -> str:
    """Run AppleScript and return result."""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip()


@mcp.tool()
def apple_hardware() -> dict:
    """Get Mac hardware info."""
    result = subprocess.run(["system_profiler", "SPHardwareDataType", "-json"], capture_output=True, text=True)
    return json.loads(result.stdout) if result.returncode == 0 else {"error": "Failed"}


@mcp.tool()
def apple_battery() -> dict:
    """Get battery status."""
    result = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
    return {"battery": result.stdout.strip()}


@mcp.tool()
def apple_wifi() -> dict:
    """Get WiFi status."""
    result = subprocess.run(
        ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
        capture_output=True, text=True
    )
    return {"wifi": result.stdout.strip()}


@mcp.tool()
def apple_apps() -> dict:
    """List running applications."""
    apps = run_osascript('tell application "System Events" to get name of every process whose background only is false')
    return {"apps": apps.split(", ")}


@mcp.tool()
def apple_launch(app: str) -> dict:
    """Launch an application."""
    subprocess.run(["open", "-a", app])
    return {"launched": app}


@mcp.tool()
def apple_quit(app: str) -> dict:
    """Quit an application."""
    run_osascript(f'tell application "{app}" to quit')
    return {"quit": app}


@mcp.tool()
def apple_clipboard(text: str = None) -> dict:
    """Get or set clipboard content."""
    if text:
        subprocess.run(["pbcopy"], input=text.encode())
        return {"copied": text[:100]}
    else:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
        return {"clipboard": result.stdout[:500]}


@mcp.tool()
def apple_screenshot(region: str = "full") -> dict:
    """Take a screenshot. Region: full, selection, window."""
    import time
    filename = f"~/Desktop/screenshot_{int(time.time())}.png"
    if region == "selection":
        subprocess.run(["screencapture", "-i", os.path.expanduser(filename)])
    elif region == "window":
        subprocess.run(["screencapture", "-w", os.path.expanduser(filename)])
    else:
        subprocess.run(["screencapture", os.path.expanduser(filename)])
    return {"saved": filename}


@mcp.tool()
def apple_volume(level: int = None) -> dict:
    """Get or set system volume (0-100)."""
    if level is not None:
        subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
        return {"volume": level}
    else:
        result = run_osascript("output volume of (get volume settings)")
        return {"volume": int(result) if result else 0}


@mcp.tool()
def apple_dark_mode(enable: bool = None) -> dict:
    """Toggle or check dark mode status."""
    if enable is not None:
        mode = "true" if enable else "false"
        run_osascript(f'tell app "System Events" to tell appearance preferences to set dark mode to {mode}')
        return {"dark_mode": enable}
    else:
        result = run_osascript('tell app "System Events" to tell appearance preferences to get dark mode')
        return {"dark_mode": result == "true"}


@mcp.tool()
def apple_say(text: str, voice: str = "Samantha", rate: int = 175) -> dict:
    """Speak text with system voice."""
    subprocess.run(["say", "-v", voice, "-r", str(rate), text])
    return {"spoken": text, "voice": voice}


@mcp.tool()
def apple_brightness(level: int = None) -> dict:
    """Get or set display brightness (0-100)."""
    if level is not None:
        brightness = level / 100.0
        run_osascript(f'tell application "System Events" to set value of slider 1 of group 1 of window "Display" of application process "System Preferences" to {brightness}')
        return {"brightness": level}
    return {"brightness": "use System Preferences"}


@mcp.tool()
def apple_notification(title: str, message: str, sound: bool = True) -> dict:
    """Show macOS notification."""
    sound_part = 'sound name "Glass"' if sound else ''
    run_osascript(f'display notification "{message}" with title "{title}" {sound_part}')
    return {"notified": title}


if __name__ == "__main__":
    print("🍎 Brain Apple MCP Server (FastMCP) starting...")
    mcp.run()
