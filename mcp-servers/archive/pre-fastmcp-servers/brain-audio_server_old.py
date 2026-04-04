#!/usr/bin/env python3
"""
Brain Audio MCP Server - Speech & Sound Tools
==============================================

All audio, speech, and accessibility tools.
Optimized for VoiceOver compatibility.

Tools: 9 essential audio tools
- Text-to-speech with multiple voices
- Sound effects (hero, glass, ping)
- Celebration and notification sounds
- VoiceOver formatting
- System audio control

Start: python server.py
"""

import json
import os
import subprocess
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.expanduser('~/brain'))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


server = Server("brain-audio")


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List audio/speech tools."""
    return [
        Tool(
            name="audio_speak",
            description="Speak text aloud (accessibility). Waits for completion.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to speak"},
                    "voice": {"type": "string", "description": "Voice: Samantha, Daniel, Zarvox"},
                    "rate": {"type": "integer", "description": "Speech rate 100-200"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="audio_announce",
            description="Make accessibility announcement with attention sound.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "importance": {"type": "string", "description": "normal, high, critical"}
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="audio_sound",
            description="Play a system sound.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sound": {"type": "string", "description": "hero, glass, ping, funk, basso, purr, pop"}
                },
                "required": ["sound"]
            }
        ),
        Tool(
            name="audio_celebrate",
            description="Play celebration with message.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "default": "Success!"},
                    "style": {"type": "string", "description": "simple or epic"}
                }
            }
        ),
        Tool(
            name="audio_notify",
            description="Play notification with message.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "urgency": {"type": "string", "description": "low, normal, high"}
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="audio_voiceover",
            description="Format text for VoiceOver (removes emoji, adds section markers).",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="audio_volume",
            description="Get or set system volume.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "get, set, mute, unmute"},
                    "level": {"type": "integer", "description": "Volume 0-100"}
                }
            }
        ),
        Tool(
            name="audio_devices",
            description="List audio input/output devices.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="audio_voices",
            description="List available voices and sounds.",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle audio tool calls."""
    try:
        result = await _execute_audio(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _execute_audio(name: str, args: Dict[str, Any]) -> Any:
    """Execute audio tools."""
    
    if name == "audio_speak":
        text = args["text"]
        voice = args.get("voice", "Samantha")
        rate = args.get("rate", 175)
        subprocess.run(["say", "-v", voice, "-r", str(rate), text])
        return {"spoken": text, "voice": voice}
    
    elif name == "audio_announce":
        msg = args["message"]
        importance = args.get("importance", "normal")
        subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
        subprocess.run(["say", "-v", "Samantha", msg])
        return {"announced": msg, "importance": importance}
    
    elif name == "audio_sound":
        sound = args["sound"]
        sound_map = {
            "hero": "/System/Library/Sounds/Hero.aiff",
            "glass": "/System/Library/Sounds/Glass.aiff",
            "ping": "/System/Library/Sounds/Ping.aiff",
            "funk": "/System/Library/Sounds/Funk.aiff",
            "basso": "/System/Library/Sounds/Basso.aiff",
            "purr": "/System/Library/Sounds/Purr.aiff",
            "pop": "/System/Library/Sounds/Pop.aiff",
        }
        path = sound_map.get(sound, sound_map["glass"])
        subprocess.run(["afplay", path])
        return {"played": sound}
    
    elif name == "audio_celebrate":
        msg = args.get("message", "Success!")
        subprocess.run(["afplay", "/System/Library/Sounds/Hero.aiff"])
        subprocess.run(["say", "-v", "Samantha", msg])
        return {"celebrated": msg}
    
    elif name == "audio_notify":
        msg = args["message"]
        urgency = args.get("urgency", "normal")
        sound = "Glass.aiff" if urgency == "normal" else "Funk.aiff"
        subprocess.run(["afplay", f"/System/Library/Sounds/{sound}"])
        subprocess.run(["say", "-v", "Samantha", msg])
        return {"notified": msg, "urgency": urgency}
    
    elif name == "audio_voiceover":
        import re
        text = args["text"]
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        text = re.sub(r'^#+\s*(.+)$', r'SECTION: \1', text, flags=re.MULTILINE)
        return {"formatted": text}
    
    elif name == "audio_volume":
        action = args.get("action", "get")
        if action == "get":
            result = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"], 
                                   capture_output=True, text=True)
            return {"volume": int(result.stdout.strip())}
        elif action == "set":
            level = args.get("level", 50)
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
            return {"volume": level}
        elif action == "mute":
            subprocess.run(["osascript", "-e", "set volume with output muted"])
            return {"muted": True}
        elif action == "unmute":
            subprocess.run(["osascript", "-e", "set volume without output muted"])
            return {"muted": False}
    
    elif name == "audio_devices":
        result = subprocess.run(
            ["system_profiler", "SPAudioDataType", "-json"],
            capture_output=True, text=True
        )
        return json.loads(result.stdout) if result.returncode == 0 else {"error": "Could not get devices"}
    
    elif name == "audio_voices":
        result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
        voices = [line.split()[0] for line in result.stdout.strip().split("\n")[:20]]
        sounds = ["hero", "glass", "ping", "funk", "basso", "purr", "pop"]
        return {"voices": voices, "sounds": sounds}
    
    return {"error": f"Unknown tool: {name}"}


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
