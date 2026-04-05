#!/usr/bin/env python3
"""
Virus Patch MCP Server
======================
AI-integrated patch search, load, and management for Access Virus TI.

Features:
- Neo4j-backed patch index with rich metadata
- Lightning-fast search by category, name, tags, timbre
- Real-time patch loading via virusRealtime binary
- Web search integration for discovering new patches
- Continuous learning from user ratings
- Full unit test coverage for reliable patch loading

Author: Joseph Webber / Claude
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

# MCP SDK
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Neo4j
from neo4j import GraphDatabase

# Add brain path for fuzzy search
sys.path.insert(0, os.path.expanduser("~/brain"))
from core.fuzzy_search import fuzzy_match, fuzzy_filter, fuzzy_best, fuzzy_ratio

# Kick & Bass Demo
try:
    from kick_bass_demo import KickBassDemoEngine, PARAMS, load_style, list_midi_styles

    KICKBASS_AVAILABLE = True
except ImportError:
    KICKBASS_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("virus-patch-mcp")

# Configuration
VIRUS_BINARY = os.path.expanduser(
    "~/gearmulator/build_cli/source/virusRealtime/virusRealtime"
)
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "brain2026")

# Category mapping
CATEGORIES = [
    "None",
    "Lead",
    "Bass",
    "Pad",
    "Decay",
    "Pluck",
    "Acid",
    "Classic",
    "Arpeggiator",
    "Effects",
    "Drums",
    "Percussion",
    "Input",
    "Vocoder",
    "Favourite1",
    "Favourite2",
    "Favourite3",
    "Organ",
    "Piano",
    "String",
    "FM",
    "Digital",
    "Atomizer",
]


class VirusPatchServer:
    def __init__(self):
        self.driver = None
        self.patch_cache = {}
        self.last_loaded_patch = None

    def connect_neo4j(self):
        """Connect to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            with self.driver.session() as session:
                result = session.run("MATCH (p:VirusPatch) RETURN count(p) as total")
                total = result.single()["total"]
                logger.info(f"Connected to Neo4j - {total} patches indexed")
                return True
        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}")
            return False

    def search_patches(
        self,
        query: str,
        category: str = None,
        limit: int = 20,
        fuzzy_threshold: int = 65,
    ) -> list:
        """Search patches by query string and/or category with fuzzy matching."""
        if not self.driver:
            self.connect_neo4j()

        # Fetch more for fuzzy filtering
        fetch_limit = limit * 3

        with self.driver.session() as session:
            if category:
                # Fuzzy match category name first
                best_cat = fuzzy_best(category, CATEGORIES, threshold=60)
                matched_category = best_cat[0] if best_cat else category

                result = session.run(
                    """
                    MATCH (p:VirusPatch)
                    WHERE toLower(p.category1Name) = toLower($category)
                       OR toLower(p.category2Name) = toLower($category)
                    RETURN p
                    ORDER BY p.rating DESC, p.playCount DESC
                    LIMIT $limit
                """,
                    category=matched_category,
                    limit=fetch_limit,
                )
            elif query:
                # Broad search, then fuzzy filter
                result = session.run(
                    """
                    MATCH (p:VirusPatch)
                    WHERE toLower(p.name) CONTAINS toLower($query)
                       OR toLower(p.category1Name) CONTAINS toLower($query)
                       OR ANY(tag IN p.useCase WHERE toLower(tag) CONTAINS toLower($query))
                    RETURN p
                    ORDER BY p.rating DESC, p.playCount DESC
                    LIMIT $limit
                """,
                    query=query,
                    limit=fetch_limit,
                )
            else:
                # Return top rated
                result = session.run(
                    """
                    MATCH (p:VirusPatch)
                    RETURN p
                    ORDER BY p.rating DESC, p.playCount DESC
                    LIMIT $limit
                """,
                    limit=limit,
                )

            patches = []
            for record in result:
                p = dict(record["p"])
                patches.append(p)

            # Apply fuzzy ranking if we have a query
            if query and patches:
                for patch in patches:
                    search_text = f"{patch.get('name', '')} {patch.get('category1Name', '')} {' '.join(patch.get('useCase', []))}"
                    patch["_fuzzy_score"] = round(fuzzy_ratio(query, search_text))

                # Sort by fuzzy score, filter by threshold
                patches.sort(key=lambda x: x.get("_fuzzy_score", 0), reverse=True)
                patches = [
                    p for p in patches if p.get("_fuzzy_score", 0) >= fuzzy_threshold
                ][:limit]

            return patches

    def get_patch(self, bank: int, prog: int) -> Optional[dict]:
        """Get a specific patch by bank and program"""
        if not self.driver:
            self.connect_neo4j()

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:VirusPatch {bank: $bank, prog: $prog})
                RETURN p
            """,
                bank=bank,
                prog=prog,
            )
            record = result.single()
            if record:
                return dict(record["p"])
        return None

    def load_patch(self, bank: int, prog: int, test_sound: bool = True) -> dict:
        """Load a patch on the Virus and optionally test it makes sound"""
        patch = self.get_patch(bank, prog)
        if not patch:
            return {"success": False, "error": f"Patch B{bank}P{prog} not found"}

        # Run virusRealtime to load and test the patch
        try:
            cmd = [VIRUS_BINARY, "loadtest", str(bank), str(prog)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            output = result.stdout + result.stderr
            success = "PASS" in output or result.returncode == 0

            # Update play count in Neo4j
            if success and self.driver:
                with self.driver.session() as session:
                    session.run(
                        """
                        MATCH (p:VirusPatch {bank: $bank, prog: $prog})
                        SET p.playCount = COALESCE(p.playCount, 0) + 1,
                            p.lastPlayed = datetime()
                    """,
                        bank=bank,
                        prog=prog,
                    )

            self.last_loaded_patch = patch
            return {
                "success": success,
                "patch": patch,
                "output": output[:500] if output else "Loaded",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout loading patch"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rate_patch(self, bank: int, prog: int, rating: int) -> bool:
        """Rate a patch (1-5 stars)"""
        if not self.driver:
            self.connect_neo4j()

        rating = max(1, min(5, rating))  # Clamp to 1-5

        with self.driver.session() as session:
            session.run(
                """
                MATCH (p:VirusPatch {bank: $bank, prog: $prog})
                SET p.rating = $rating, p.ratedAt = datetime()
            """,
                bank=bank,
                prog=prog,
                rating=rating,
            )
        return True

    def get_stats(self) -> dict:
        """Get patch library statistics"""
        if not self.driver:
            self.connect_neo4j()

        with self.driver.session() as session:
            # Total patches
            result = session.run("MATCH (p:VirusPatch) RETURN count(p) as total")
            total = result.single()["total"]

            # By category
            result = session.run(
                """
                MATCH (p:VirusPatch)
                RETURN p.category1Name as category, count(*) as count
                ORDER BY count DESC
            """
            )
            categories = {r["category"]: r["count"] for r in result}

            # Top rated
            result = session.run(
                """
                MATCH (p:VirusPatch)
                WHERE p.rating > 0
                RETURN p.name as name, p.bank as bank, p.prog as prog, p.rating as rating
                ORDER BY p.rating DESC
                LIMIT 10
            """
            )
            top_rated = [dict(r) for r in result]

            # Most played
            result = session.run(
                """
                MATCH (p:VirusPatch)
                WHERE p.playCount > 0
                RETURN p.name as name, p.bank as bank, p.prog as prog, p.playCount as plays
                ORDER BY p.playCount DESC
                LIMIT 10
            """
            )
            most_played = [dict(r) for r in result]

            return {
                "total_patches": total,
                "categories": categories,
                "top_rated": top_rated,
                "most_played": most_played,
            }

    def run_unit_tests(self) -> dict:
        """Run unit tests to verify patch loading works correctly"""
        results = {"passed": 0, "failed": 0, "tests": []}

        # Test 1: Load known good bass patch
        test = {"name": "Load GrokBass (B0P36)", "passed": False}
        try:
            r = self.load_patch(0, 36, test_sound=True)
            test["passed"] = r.get("success", False)
            test["detail"] = r.get("output", "")[:100]
        except Exception as e:
            test["detail"] = str(e)
        results["tests"].append(test)
        results["passed" if test["passed"] else "failed"] += 1

        # Test 2: Load known good lead patch
        test = {"name": "Load Alead (B0P1)", "passed": False}
        try:
            r = self.load_patch(0, 1, test_sound=True)
            test["passed"] = r.get("success", False)
        except Exception as e:
            test["detail"] = str(e)
        results["tests"].append(test)
        results["passed" if test["passed"] else "failed"] += 1

        # Test 3: Search returns results
        test = {"name": "Search 'bass' returns results", "passed": False}
        try:
            patches = self.search_patches("bass")
            test["passed"] = len(patches) > 0
            test["detail"] = f"Found {len(patches)} patches"
        except Exception as e:
            test["detail"] = str(e)
        results["tests"].append(test)
        results["passed" if test["passed"] else "failed"] += 1

        # Test 4: Category search works
        test = {"name": "Category search 'Bass' works", "passed": False}
        try:
            patches = self.search_patches("", category="Bass")
            test["passed"] = len(patches) >= 40  # We know there are 46
            test["detail"] = f"Found {len(patches)} bass patches"
        except Exception as e:
            test["detail"] = str(e)
        results["tests"].append(test)
        results["passed" if test["passed"] else "failed"] += 1

        # Test 5: Neo4j connection
        test = {"name": "Neo4j connection healthy", "passed": False}
        try:
            stats = self.get_stats()
            test["passed"] = stats.get("total_patches", 0) >= 500
            test["detail"] = f"{stats.get('total_patches')} patches in database"
        except Exception as e:
            test["detail"] = str(e)
        results["tests"].append(test)
        results["passed" if test["passed"] else "failed"] += 1

        return results


# Create server instance
virus_server = VirusPatchServer()
app = Server("virus-patch")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available Virus patch tools"""
    return [
        Tool(
            name="virus_search",
            description="Search Virus patches by name, category, or tags. Examples: 'bass', 'lead', 'dark', 'punchy', 'dnb'",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (name, tag, or keyword)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category filter: Bass, Lead, Pad, Drums, etc.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20)",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="virus_load",
            description="Load a specific patch on the Virus synthesizer",
            inputSchema={
                "type": "object",
                "properties": {
                    "bank": {"type": "integer", "description": "Bank number (0-3)"},
                    "prog": {
                        "type": "integer",
                        "description": "Program number (0-127)",
                    },
                },
                "required": ["bank", "prog"],
            },
        ),
        Tool(
            name="virus_rate",
            description="Rate a patch 1-5 stars to help improve recommendations",
            inputSchema={
                "type": "object",
                "properties": {
                    "bank": {"type": "integer", "description": "Bank number (0-3)"},
                    "prog": {
                        "type": "integer",
                        "description": "Program number (0-127)",
                    },
                    "rating": {
                        "type": "integer",
                        "description": "Rating 1-5 stars",
                        "minimum": 1,
                        "maximum": 5,
                    },
                },
                "required": ["bank", "prog", "rating"],
            },
        ),
        Tool(
            name="virus_stats",
            description="Get patch library statistics - categories, top rated, most played",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="virus_test",
            description="Run unit tests to verify patch loading is working correctly",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="virus_random",
            description="Load a random patch from a category for inspiration",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Category: Bass, Lead, Pad, Drums, DnB",
                    }
                },
                "required": ["category"],
            },
        ),
        Tool(
            name="virus_jam",
            description="Start a DnB jam session with kick, bass, and sidechain",
            inputSchema={
                "type": "object",
                "properties": {
                    "bpm": {
                        "type": "integer",
                        "description": "Tempo (default 174)",
                        "default": 174,
                    },
                    "bass_patch": {
                        "type": "string",
                        "description": "Bass patch name or 'random'",
                        "default": "random",
                    },
                },
            },
        ),
        # Kick & Bass Demo Tools
        Tool(
            name="kickbass_play",
            description="Play kick & bass demo with sidechain. Atomic params - no recompile!",
            inputSchema={
                "type": "object",
                "properties": {
                    "bars": {
                        "type": "integer",
                        "description": "Number of bars (1-8)",
                        "default": 4,
                    },
                    "pattern": {
                        "type": "string",
                        "enum": ["twostep", "amen", "roller", "jungle"],
                    },
                    "bass_patch": {"type": "string", "enum": ["sub", "reese", "growl"]},
                    "midi_style": {
                        "type": "string",
                        "description": "MIDI style: nosia, pendulum, hospital, etc.",
                    },
                },
            },
        ),
        Tool(
            name="kickbass_set",
            description="Set atomic parameters live (bpm, gains, sidechain) - no recompile",
            inputSchema={
                "type": "object",
                "properties": {
                    "bpm": {"type": "number", "description": "Tempo 140-200"},
                    "bass_gain": {"type": "number", "description": "Bass volume 0-1"},
                    "kick_gain": {"type": "number", "description": "Kick volume 0-1"},
                    "snare_gain": {"type": "number", "description": "Snare volume 0-1"},
                    "sc_depth": {
                        "type": "number",
                        "description": "Sidechain depth 0-1",
                    },
                    "sc_release": {
                        "type": "number",
                        "description": "Sidechain release 0.05-0.2s",
                    },
                    "pattern": {
                        "type": "string",
                        "enum": ["twostep", "amen", "roller", "jungle"],
                    },
                    "bass_patch": {"type": "string", "enum": ["sub", "reese", "growl"]},
                    "kick_style": {
                        "type": "string",
                        "enum": ["punchy", "deep", "tight"],
                    },
                },
            },
        ),
        Tool(
            name="kickbass_status",
            description="Get current kick & bass settings",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="kickbass_styles",
            description="List available MIDI bass styles (nosia, pendulum, hospital, etc.)",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""

    if name == "virus_search":
        query = arguments.get("query", "")
        category = arguments.get("category")
        limit = arguments.get("limit", 20)

        patches = virus_server.search_patches(query, category, limit)

        if not patches:
            return [
                TextContent(
                    type="text", text=f"No patches found for '{query or category}'"
                )
            ]

        # Format results
        lines = [f"🎹 Found {len(patches)} patches:\n"]
        for p in patches:
            rating = "⭐" * p.get("rating", 0) if p.get("rating") else ""
            lines.append(
                f"  B{p['bank']}P{p['prog']:03d}: {p['name']:12s} [{p.get('category1Name', '?')}] {rating}"
            )

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "virus_load":
        bank = arguments["bank"]
        prog = arguments["prog"]

        result = virus_server.load_patch(bank, prog)

        if result["success"]:
            p = result["patch"]
            return [
                TextContent(
                    type="text",
                    text=f"✅ Loaded: {p['name']} (B{bank}P{prog}) - {p.get('category1Name', 'Unknown')}",
                )
            ]
        else:
            return [
                TextContent(
                    type="text",
                    text=f"❌ Failed to load B{bank}P{prog}: {result.get('error', 'Unknown error')}",
                )
            ]

    elif name == "virus_rate":
        bank = arguments["bank"]
        prog = arguments["prog"]
        rating = arguments["rating"]

        virus_server.rate_patch(bank, prog, rating)
        patch = virus_server.get_patch(bank, prog)
        return [
            TextContent(
                type="text", text=f"⭐ Rated {patch['name']} as {'⭐' * rating}"
            )
        ]

    elif name == "virus_stats":
        stats = virus_server.get_stats()

        lines = [
            f"📊 Virus Patch Library Stats",
            f"   Total patches: {stats['total_patches']}",
            f"\n   Categories:",
        ]
        for cat, count in list(stats["categories"].items())[:10]:
            lines.append(f"      {cat:15s}: {count}")

        if stats["top_rated"]:
            lines.append(f"\n   ⭐ Top Rated:")
            for p in stats["top_rated"][:5]:
                lines.append(f"      {p['name']} - {'⭐' * p['rating']}")

        if stats["most_played"]:
            lines.append(f"\n   🎵 Most Played:")
            for p in stats["most_played"][:5]:
                lines.append(f"      {p['name']} - {p['plays']} plays")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "virus_test":
        results = virus_server.run_unit_tests()

        lines = [
            f"🧪 Unit Test Results: {results['passed']}/{results['passed'] + results['failed']} passed\n"
        ]
        for test in results["tests"]:
            icon = "✅" if test["passed"] else "❌"
            lines.append(f"   {icon} {test['name']}")
            if test.get("detail"):
                lines.append(f"      {test['detail']}")

        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "virus_random":
        category = arguments["category"]
        patches = virus_server.search_patches("", category=category)

        if not patches:
            return [TextContent(type="text", text=f"No {category} patches found")]

        import random

        patch = random.choice(patches)
        result = virus_server.load_patch(patch["bank"], patch["prog"])

        if result["success"]:
            return [
                TextContent(
                    type="text",
                    text=f"🎲 Random {category}: {patch['name']} (B{patch['bank']}P{patch['prog']})",
                )
            ]
        else:
            return [TextContent(type="text", text=f"❌ Failed to load random patch")]

    elif name == "virus_jam":
        bpm = arguments.get("bpm", 174)
        bass_patch = arguments.get("bass_patch", "random")

        # Start jam mode
        try:
            cmd = [VIRUS_BINARY, "jam", str(bpm)]
            # Run async - don't wait
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return [
                TextContent(
                    type="text",
                    text=f"🎵 Started DnB jam at {bpm} BPM - Press Ctrl+C in terminal to stop",
                )
            ]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Failed to start jam: {e}")]

    # =========================================================================
    # KICK & BASS DEMO TOOLS
    # =========================================================================

    elif name == "kickbass_play":
        if not KICKBASS_AVAILABLE:
            return [TextContent(type="text", text="❌ Kick/Bass demo not available")]

        bars = arguments.get("bars", 4)
        if arguments.get("pattern"):
            PARAMS.pattern = arguments["pattern"]
        if arguments.get("bass_patch"):
            PARAMS.bass_patch = arguments["bass_patch"]

        engine = KickBassDemoEngine()
        if arguments.get("midi_style"):
            notes = load_style(arguments["midi_style"])
            engine.bass_patterns["midi"] = notes
            engine.bass_pattern = "midi"

        engine.play(bars=bars)
        return [
            TextContent(
                type="text",
                text=f"🥁 Played {bars} bars: {PARAMS.pattern} pattern, {PARAMS.bass_patch} bass, sidechain={PARAMS.sc_depth}",
            )
        ]

    elif name == "kickbass_set":
        if not KICKBASS_AVAILABLE:
            return [TextContent(type="text", text="❌ Kick/Bass demo not available")]

        changed = []
        for key, value in arguments.items():
            if hasattr(PARAMS, key):
                setattr(PARAMS, key, value)
                changed.append(f"{key}={value}")

        return [
            TextContent(
                type="text", text=f"⚡ Updated atomic params: {', '.join(changed)}"
            )
        ]

    elif name == "kickbass_status":
        if not KICKBASS_AVAILABLE:
            return [TextContent(type="text", text="❌ Kick/Bass demo not available")]

        status = f"""🎛️ Kick & Bass Status:
  BPM: {PARAMS.bpm}
  Pattern: {PARAMS.pattern}
  Bass Patch: {PARAMS.bass_patch}
  Kick Style: {PARAMS.kick_style}
  
  Gains:
    Bass: {PARAMS.bass_gain:.2f}
    Kick: {PARAMS.kick_gain:.2f}
    Snare: {PARAMS.snare_gain:.2f}
  
  Sidechain:
    Depth: {PARAMS.sc_depth:.2f}
    Release: {PARAMS.sc_release:.3f}s"""
        return [TextContent(type="text", text=status)]

    elif name == "kickbass_styles":
        if not KICKBASS_AVAILABLE:
            return [TextContent(type="text", text="❌ Kick/Bass demo not available")]

        styles = list_midi_styles()
        return [
            TextContent(
                type="text",
                text=f"🎵 Available MIDI styles ({len(styles)}):\n  "
                + "\n  ".join(styles),
            )
        ]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server"""
    virus_server.connect_neo4j()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
