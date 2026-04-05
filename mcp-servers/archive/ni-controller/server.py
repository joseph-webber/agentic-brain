#!/usr/bin/env python3
"""
Native Instruments Plugin Controller MCP Server
================================================

MCP server that exposes NI VST plugins (Massive, Kontakt, etc.) to Claude.

Tools:
- ni_scan: Scan for installed NI plugins
- ni_load: Load a plugin
- ni_preset: Load a preset
- ni_note: Play a note
- ni_chord: Play a chord
- ni_pattern: Play a DnB pattern
- ni_render: Render to file
- ni_params: Get/set plugin parameters
"""

import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add brain to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import our NI modules
from tools.ni_plugin_discovery import scan_ni_plugins, get_plugin_by_name, PluginInfo
from tools.ni_plugin_loader import NIPluginLoader
from tools.ni_midi_controller import MIDIController, PatternFactory
from tools.ni_audio_engine import AudioEngine

# Global state
_loaded_plugins: Dict[str, NIPluginLoader] = {}
_audio_engine: Optional[AudioEngine] = None


def get_engine() -> AudioEngine:
    """Get or create the audio engine singleton."""
    global _audio_engine
    if _audio_engine is None:
        _audio_engine = AudioEngine()
    return _audio_engine


# Create server
server = Server("ni-controller")


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available NI controller tools."""
    return [
        Tool(
            name="ni_scan",
            description="Scan for installed Native Instruments VST3/AU plugins",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="ni_load",
            description="Load a Native Instruments plugin by name (e.g., 'Massive', 'Kontakt')",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Plugin name to load"}
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="ni_note",
            description="Play a single note on a loaded plugin",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin": {
                        "type": "string",
                        "description": "Plugin name (default: Massive)",
                        "default": "Massive",
                    },
                    "note": {
                        "type": "integer",
                        "description": "MIDI note number (0-127, e.g., 36=C1, 48=C2, 60=C3)",
                    },
                    "velocity": {
                        "type": "integer",
                        "description": "Velocity (0-127)",
                        "default": 100,
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration in seconds",
                        "default": 1.0,
                    },
                },
                "required": ["note"],
            },
        ),
        Tool(
            name="ni_chord",
            description="Play a chord on a loaded plugin",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin": {
                        "type": "string",
                        "description": "Plugin name",
                        "default": "Massive",
                    },
                    "notes": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of MIDI note numbers",
                    },
                    "velocity": {
                        "type": "integer",
                        "description": "Velocity",
                        "default": 100,
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration in seconds",
                        "default": 1.5,
                    },
                },
                "required": ["notes"],
            },
        ),
        Tool(
            name="ni_pattern",
            description="Play a DnB bassline pattern (roller, halfstep, neurofunk)",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin": {
                        "type": "string",
                        "description": "Plugin name",
                        "default": "Massive",
                    },
                    "style": {
                        "type": "string",
                        "description": "Pattern style: roller, halfstep, neurofunk",
                        "default": "roller",
                    },
                    "bars": {
                        "type": "integer",
                        "description": "Number of bars",
                        "default": 4,
                    },
                    "bpm": {
                        "type": "integer",
                        "description": "Tempo in BPM",
                        "default": 174,
                    },
                    "root": {
                        "type": "integer",
                        "description": "Root note",
                        "default": 33,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="ni_preset",
            description="Load a preset file (.vstpreset, .nmsv)",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin": {
                        "type": "string",
                        "description": "Plugin name",
                        "default": "Massive",
                    },
                    "preset_path": {
                        "type": "string",
                        "description": "Path to preset file",
                    },
                },
                "required": ["preset_path"],
            },
        ),
        Tool(
            name="ni_params",
            description="Get or set plugin parameters",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin": {
                        "type": "string",
                        "description": "Plugin name",
                        "default": "Massive",
                    },
                    "action": {
                        "type": "string",
                        "description": "list, get, or set",
                        "default": "list",
                    },
                    "param": {
                        "type": "string",
                        "description": "Parameter name (for get/set)",
                    },
                    "value": {
                        "type": "number",
                        "description": "Value to set (for set action)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="ni_render",
            description="Render audio to a WAV file",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin": {
                        "type": "string",
                        "description": "Plugin name",
                        "default": "Massive",
                    },
                    "note": {
                        "type": "integer",
                        "description": "MIDI note to render",
                        "default": 36,
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration in seconds",
                        "default": 2.0,
                    },
                    "output": {
                        "type": "string",
                        "description": "Output path",
                        "default": "/tmp/ni_render.wav",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="ni_status",
            description="Get status of loaded plugins and audio engine",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> List[TextContent]:
    """Handle tool calls."""

    try:
        if name == "ni_scan":
            return await handle_scan()
        elif name == "ni_load":
            return await handle_load(arguments.get("name", "Massive"))
        elif name == "ni_note":
            return await handle_note(
                arguments.get("plugin", "Massive"),
                arguments.get("note", 36),
                arguments.get("velocity", 100),
                arguments.get("duration", 1.0),
            )
        elif name == "ni_chord":
            return await handle_chord(
                arguments.get("plugin", "Massive"),
                arguments.get("notes", [36, 43, 48]),
                arguments.get("velocity", 100),
                arguments.get("duration", 1.5),
            )
        elif name == "ni_pattern":
            return await handle_pattern(
                arguments.get("plugin", "Massive"),
                arguments.get("style", "roller"),
                arguments.get("bars", 4),
                arguments.get("bpm", 174),
                arguments.get("root", 33),
            )
        elif name == "ni_preset":
            return await handle_preset(
                arguments.get("plugin", "Massive"), arguments.get("preset_path", "")
            )
        elif name == "ni_params":
            return await handle_params(
                arguments.get("plugin", "Massive"),
                arguments.get("action", "list"),
                arguments.get("param"),
                arguments.get("value"),
            )
        elif name == "ni_render":
            return await handle_render(
                arguments.get("plugin", "Massive"),
                arguments.get("note", 36),
                arguments.get("duration", 2.0),
                arguments.get("output", "/tmp/ni_render.wav"),
            )
        elif name == "ni_status":
            return await handle_status()
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]


async def handle_scan() -> List[TextContent]:
    """Scan for NI plugins."""
    plugins = scan_ni_plugins()

    lines = ["🔍 **Native Instruments Plugins Found:**\n"]
    for p in plugins:
        lines.append(f"- **{p.name}** ({p.format}) - {p.plugin_type}")

    if not plugins:
        lines.append("No NI plugins found. Check installation.")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_load(name: str) -> List[TextContent]:
    """Load a plugin by name."""
    global _loaded_plugins

    # Check if already loaded
    if name.lower() in [k.lower() for k in _loaded_plugins.keys()]:
        return [TextContent(type="text", text=f"✅ {name} already loaded")]

    # Find the plugin
    plugin_info = get_plugin_by_name(name)
    if not plugin_info:
        return [
            TextContent(
                type="text",
                text=f"❌ Plugin '{name}' not found. Run ni_scan to see available plugins.",
            )
        ]

    # Load it
    loader = NIPluginLoader(plugin_info.path)
    _loaded_plugins[plugin_info.name] = loader

    return [
        TextContent(
            type="text",
            text=f"✅ Loaded **{plugin_info.name}** ({len(loader.get_parameters())} parameters)",
        )
    ]


def get_or_load_plugin(name: str) -> NIPluginLoader:
    """Get a loaded plugin or load it."""
    global _loaded_plugins

    # Case-insensitive lookup
    for k, v in _loaded_plugins.items():
        if k.lower() == name.lower():
            return v

    # Try to load it
    plugin_info = get_plugin_by_name(name)
    if plugin_info:
        loader = NIPluginLoader(plugin_info.path)
        _loaded_plugins[plugin_info.name] = loader
        return loader

    raise ValueError(f"Plugin '{name}' not found")


async def handle_note(
    plugin: str, note: int, velocity: int, duration: float
) -> List[TextContent]:
    """Play a single note."""
    loader = get_or_load_plugin(plugin)
    engine = get_engine()

    audio = loader.render_note(note, velocity, duration)
    engine.play(audio, blocking=True)

    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    note_name = note_names[note % 12] + str(note // 12 - 1)

    return [
        TextContent(
            type="text",
            text=f"🎵 Played {note_name} (MIDI {note}) on {plugin} for {duration}s",
        )
    ]


async def handle_chord(
    plugin: str, notes: List[int], velocity: int, duration: float
) -> List[TextContent]:
    """Play a chord."""
    loader = get_or_load_plugin(plugin)
    engine = get_engine()

    audio = loader.render_chord(notes, velocity, duration)
    engine.play(audio, blocking=True)

    return [TextContent(type="text", text=f"🎹 Played chord {notes} on {plugin}")]


async def handle_pattern(
    plugin: str, style: str, bars: int, bpm: int, root: int
) -> List[TextContent]:
    """Play a DnB pattern."""
    loader = get_or_load_plugin(plugin)
    engine = get_engine()

    # Generate pattern based on style
    if style == "halfstep":
        midi = PatternFactory.dnb_bassline(bars=bars, bpm=bpm, style="halfstep")
    elif style == "neurofunk":
        midi = PatternFactory.dnb_bassline(bars=bars, bpm=bpm, style="neurofunk")
    else:
        midi = PatternFactory.dnb_bassline(bars=bars, bpm=bpm, style="roller")

    messages = midi.get_messages()
    duration = messages[-1][1] + 0.5 if messages else 2.0

    audio = loader.render_midi(messages, duration=duration)
    engine.play(audio, blocking=True)

    return [
        TextContent(
            type="text",
            text=f"🔊 Played {bars}-bar {style} pattern at {bpm} BPM on {plugin}",
        )
    ]


async def handle_preset(plugin: str, preset_path: str) -> List[TextContent]:
    """Load a preset."""
    loader = get_or_load_plugin(plugin)

    path = Path(preset_path).expanduser()
    if not path.exists():
        return [TextContent(type="text", text=f"❌ Preset not found: {preset_path}")]

    loader.load_preset(str(path))
    return [TextContent(type="text", text=f"✅ Loaded preset: {path.name}")]


async def handle_params(
    plugin: str, action: str, param: Optional[str], value: Optional[float]
) -> List[TextContent]:
    """Handle parameter operations."""
    loader = get_or_load_plugin(plugin)
    params = loader.get_parameters()

    if action == "list":
        lines = [f"🎛️ **{plugin} Parameters** ({len(params)} total):\n"]
        for name, val in list(params.items())[:20]:  # First 20
            lines.append(f"- {name}")
        if len(params) > 20:
            lines.append(f"\n... and {len(params) - 20} more")
        return [TextContent(type="text", text="\n".join(lines))]

    elif action == "get" and param:
        val = loader.get_parameter(param)
        return [TextContent(type="text", text=f"🎛️ {param} = {val}")]

    elif action == "set" and param and value is not None:
        loader.set_parameter(param, value)
        return [TextContent(type="text", text=f"✅ Set {param} = {value}")]

    return [
        TextContent(
            type="text",
            text="Invalid params action. Use: list, get <param>, set <param> <value>",
        )
    ]


async def handle_render(
    plugin: str, note: int, duration: float, output: str
) -> List[TextContent]:
    """Render to file."""
    loader = get_or_load_plugin(plugin)
    engine = get_engine()

    audio = loader.render_note(note, 100, duration)
    engine.export_wav(audio, output)

    return [TextContent(type="text", text=f"✅ Rendered to {output}")]


async def handle_status() -> List[TextContent]:
    """Get status."""
    global _loaded_plugins, _audio_engine

    lines = ["🎹 **NI Controller Status**\n"]

    # Loaded plugins
    lines.append(f"**Loaded Plugins:** {len(_loaded_plugins)}")
    for name, loader in _loaded_plugins.items():
        params = loader.get_parameters()
        lines.append(f"  - {name}: {len(params)} parameters")

    # Audio engine
    if _audio_engine:
        lines.append(f"\n**Audio Engine:** Active ({_audio_engine.sample_rate}Hz)")
    else:
        lines.append("\n**Audio Engine:** Not initialized")

    # Available plugins
    plugins = scan_ni_plugins()
    lines.append(f"\n**Available NI Plugins:** {len(plugins)}")
    for p in plugins:
        status = "✅" if p.name in _loaded_plugins else "⚪"
        lines.append(f"  {status} {p.name} ({p.format})")

    return [TextContent(type="text", text="\n".join(lines))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
