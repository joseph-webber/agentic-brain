# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
CLI commands for managing user regional preferences and learning
"""

import argparse
import json
import sys
from pathlib import Path

from agentic_brain.voice.user_regions import (
    get_region_stats,
    get_user_region_storage,
    set_user_region,
)


def region_set_command(args):
    """Set user region: agentic region set <city> [state]"""
    city = args.city
    state = args.state if hasattr(args, "state") else None

    print(f"Setting region to {city}...", file=sys.stderr)

    try:
        region = set_user_region(city, state)
        print(
            json.dumps(
                {
                    "status": "success",
                    "city": region.city,
                    "state": region.state,
                    "timezone": region.timezone,
                },
                indent=2,
            )
        )
    except Exception as e:
        print(
            json.dumps({"status": "error", "message": str(e)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(1)


def region_show_command(args):
    """Show current region: agentic region show"""
    storage = get_user_region_storage()
    region = storage.get_region()

    if not region:
        print(
            json.dumps(
                {
                    "status": "not_set",
                    "message": "No region configured. Use 'agentic region set' to configure.",
                },
                indent=2,
            )
        )
        sys.exit(1)

    print(
        json.dumps(
            {
                "status": "success",
                "city": region.city,
                "state": region.state,
                "country": region.country,
                "timezone": region.timezone,
                "expressions_count": len(storage.get_all_expressions()),
                "greetings": region.favorite_greetings[:3],
                "last_updated": region.last_updated,
            },
            indent=2,
        )
    )


def region_add_command(args):
    """Add custom expression: agentic region add <standard> <regional>"""
    standard = args.standard
    regional = args.regional

    storage = get_user_region_storage()
    storage.add_expression(standard, regional)

    print(
        json.dumps(
            {
                "status": "success",
                "added": {"standard": standard, "regional": regional},
            },
            indent=2,
        )
    )


def region_learn_command(args):
    """Show learned expressions: agentic region learn"""
    storage = get_user_region_storage()
    region = storage.get_region()

    if not region:
        print(
            json.dumps(
                {"status": "error", "message": "No region configured"}, indent=2
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    learned = region.learned_expressions
    custom = region.custom_expressions

    print(
        json.dumps(
            {
                "status": "success",
                "learned_expressions": learned,
                "custom_expressions": custom,
                "total": len(learned) + len(custom),
            },
            indent=2,
        )
    )


def region_stats_command(args):
    """Show learning statistics: agentic region stats"""
    stats = get_region_stats()
    storage = get_user_region_storage()

    top_expr = storage.get_top_expressions(limit=5)
    top_data = [{"word": w, "regional": r, "usage_count": c} for w, r, c in top_expr]

    print(
        json.dumps(
            {
                "status": "success",
                "stats": stats,
                "top_expressions": top_data,
            },
            indent=2,
        )
    )


def region_export_command(args):
    """Export config: agentic region export <file>"""
    filepath = Path(args.file) if hasattr(args, "file") else None

    if not filepath:
        # Use default
        filepath = Path.home() / ".agentic-brain" / "regions" / "export.json"

    storage = get_user_region_storage()

    if storage.export_config(filepath):
        print(
            json.dumps(
                {
                    "status": "success",
                    "exported_to": str(filepath),
                    "message": "Region configuration exported successfully",
                },
                indent=2,
            )
        )
    else:
        print(
            json.dumps({"status": "error", "message": "Export failed"}, indent=2),
            file=sys.stderr,
        )
        sys.exit(1)


def region_import_command(args):
    """Import config: agentic region import <file>"""
    filepath = Path(args.file)

    if not filepath.exists():
        print(
            json.dumps(
                {"status": "error", "message": f"File not found: {filepath}"}, indent=2
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    storage = get_user_region_storage()

    if storage.import_config(filepath):
        print(
            json.dumps(
                {
                    "status": "success",
                    "imported_from": str(filepath),
                    "message": "Region configuration imported successfully",
                },
                indent=2,
            )
        )
    else:
        print(
            json.dumps({"status": "error", "message": "Import failed"}, indent=2),
            file=sys.stderr,
        )
        sys.exit(1)


def region_history_command(args):
    """Show correction history: agentic region history"""
    storage = get_user_region_storage()

    history_type = args.type if hasattr(args, "type") else "both"

    limit = args.limit if hasattr(args, "limit") else 20

    result = {"status": "success"}

    if history_type in ["corrections", "both"]:
        result["corrections"] = storage.get_corrections_history(limit)

    if history_type in ["learnings", "both"]:
        result["learnings"] = storage.get_learnings_history(limit)

    print(json.dumps(result, indent=2))


def setup_region_parser(subparsers):
    """Set up region commands parser"""
    region_parser = subparsers.add_parser(
        "region", help="Manage user regional preferences"
    )

    region_subparsers = region_parser.add_subparsers(
        dest="region_command", required=True
    )

    # Set region
    set_parser = region_subparsers.add_parser("set", help="Set your city and region")
    set_parser.add_argument("city", help="City name (e.g., Adelaide)")
    set_parser.add_argument("state", nargs="?", help="State (e.g., South Australia)")
    set_parser.set_defaults(func=region_set_command)

    # Show region
    show_parser = region_subparsers.add_parser("show", help="Show current region")
    show_parser.set_defaults(func=region_show_command)

    # Add expression
    add_parser = region_subparsers.add_parser(
        "add", help="Add custom regional expression"
    )
    add_parser.add_argument("standard", help="Standard English term")
    add_parser.add_argument("regional", help="Regional variant")
    add_parser.set_defaults(func=region_add_command)

    # Learn
    learn_parser = region_subparsers.add_parser(
        "learn", help="Show learned expressions"
    )
    learn_parser.set_defaults(func=region_learn_command)

    # Stats
    stats_parser = region_subparsers.add_parser(
        "stats", help="Show learning statistics"
    )
    stats_parser.set_defaults(func=region_stats_command)

    # Export
    export_parser = region_subparsers.add_parser("export", help="Export region config")
    export_parser.add_argument(
        "file", nargs="?", help="Output file (default: export.json)"
    )
    export_parser.set_defaults(func=region_export_command)

    # Import
    import_parser = region_subparsers.add_parser("import", help="Import region config")
    import_parser.add_argument("file", help="Input file to import")
    import_parser.set_defaults(func=region_import_command)

    # History
    history_parser = region_subparsers.add_parser(
        "history", help="Show correction/learning history"
    )
    history_parser.add_argument(
        "--type",
        choices=["corrections", "learnings", "both"],
        default="both",
        help="Type of history to show",
    )
    history_parser.add_argument(
        "--limit", type=int, default=20, help="Number of items to show"
    )
    history_parser.set_defaults(func=region_history_command)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agentic Brain - Regional Commands")
    subparsers = parser.add_subparsers(dest="command")
    setup_region_parser(subparsers)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
