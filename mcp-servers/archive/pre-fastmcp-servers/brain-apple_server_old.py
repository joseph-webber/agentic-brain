#!/usr/bin/env python3
"""Brain Apple MCP Server - Mac Integration Tools"""

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.expanduser("~/brain"))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("brain-apple")

TOOLS = [
    ("apple_hardware", "Mac hardware info", {}),
    ("apple_battery", "Battery status", {}),
    ("apple_wifi", "WiFi status", {}),
    ("apple_apps", "Running apps", {}),
    ("apple_launch", "Launch app", {"app": {"type": "string"}}),
    ("apple_quit", "Quit app", {"app": {"type": "string"}}),
    ("apple_clipboard", "Get/set clipboard", {"text": {"type": "string"}}),
    ("apple_screenshot", "Take screenshot", {"region": {"type": "string"}}),
    ("apple_volume", "Get/set volume", {"level": {"type": "integer"}}),
    ("apple_dark_mode", "Toggle dark mode", {"enable": {"type": "boolean"}}),
    (
        "apple_say",
        "Text to speech",
        {"text": {"type": "string"}, "voice": {"type": "string"}},
    ),
    ("apple_spotlight", "Search files", {"query": {"type": "string"}}),
    ("apple_weather", "Weather info", {"location": {"type": "string"}}),
    ("apple_system_info", "Full system info", {}),
]


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(name=n, description=d, inputSchema={"type": "object", "properties": p})
        for n, d, p in TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, args: Dict[str, Any]) -> List[TextContent]:
    try:
        if name == "apple_hardware":
            r = subprocess.run(
                ["system_profiler", "SPHardwareDataType", "-json"],
                capture_output=True,
                text=True,
            )
            result = json.loads(r.stdout) if r.returncode == 0 else {"error": "Failed"}
        elif name == "apple_battery":
            r = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
            result = {"battery": r.stdout.strip()}
        elif name == "apple_apps":
            r = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell app "System Events" to get name of every process whose background only is false',
                ],
                capture_output=True,
                text=True,
            )
            result = {"apps": r.stdout.strip().split(", ")}
        elif name == "apple_launch":
            subprocess.run(["open", "-a", args.get("app", "")])
            result = {"launched": args.get("app")}
        elif name == "apple_quit":
            subprocess.run(["osascript", "-e", f'tell app "{args.get("app")}" to quit'])
            result = {"quit": args.get("app")}
        elif name == "apple_clipboard":
            if "text" in args:
                subprocess.run(["pbcopy"], input=args["text"].encode())
                result = {"copied": args["text"][:50]}
            else:
                r = subprocess.run(["pbpaste"], capture_output=True, text=True)
                result = {"clipboard": r.stdout[:500]}
        elif name == "apple_volume":
            if "level" in args:
                subprocess.run(
                    ["osascript", "-e", f"set volume output volume {args['level']}"]
                )
                result = {"volume": args["level"]}
            else:
                r = subprocess.run(
                    ["osascript", "-e", "output volume of (get volume settings)"],
                    capture_output=True,
                    text=True,
                )
                result = {
                    "volume": (
                        int(r.stdout.strip()) if r.stdout.strip().isdigit() else 50
                    )
                }
        elif name == "apple_dark_mode":
            if "enable" in args:
                mode = "true" if args["enable"] else "false"
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        f'tell app "System Events" to tell appearance preferences to set dark mode to {mode}',
                    ]
                )
                result = {"dark_mode": args["enable"]}
            else:
                r = subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell app "System Events" to tell appearance preferences to get dark mode',
                    ],
                    capture_output=True,
                    text=True,
                )
                result = {"dark_mode": r.stdout.strip() == "true"}
        elif name == "apple_say":
            subprocess.run(
                ["say", "-v", args.get("voice", "Samantha"), args.get("text", "")]
            )
            result = {"said": args.get("text", "")[:50]}
        elif name == "apple_spotlight":
            r = subprocess.run(
                ["mdfind", args.get("query", ""), "-limit", "20"],
                capture_output=True,
                text=True,
            )
            result = {"files": r.stdout.strip().split("\n")[:20]}
        elif name == "apple_weather":
            r = subprocess.run(
                ["curl", "-s", f"wttr.in/{args.get('location', 'London')}?format=3"],
                capture_output=True,
                text=True,
            )
            result = {"weather": r.stdout.strip()}
        elif name == "apple_system_info":
            r = subprocess.run(
                ["system_profiler", "SPSoftwareDataType", "-json"],
                capture_output=True,
                text=True,
            )
            result = json.loads(r.stdout) if r.returncode == 0 else {"error": "Failed"}
        else:
            result = {"error": f"Unknown: {name}"}
        return [
            TextContent(type="text", text=json.dumps(result, indent=2, default=str))
        ]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
