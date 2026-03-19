"""
Agentic Brain CLI
=================

Command-line interface for agentic-brain with chat, server, and management commands.

Copyright (C) 2026 Joseph Webber
License: GPL-3.0-or-later

Usage:
    python -m agentic_brain.cli chat
    python -m agentic_brain.cli serve --port 8000
    python -m agentic_brain.cli init --name my-project
    python -m agentic_brain.cli schema
    python -m agentic_brain.cli install
    python -m agentic_brain.cli version
"""

import sys
import argparse
from typing import Optional

from agentic_brain import __version__
from . import commands


class ColoredFormatter(argparse.RawDescriptionHelpFormatter):
    """Formatter for colored help output when terminal supports it."""

    def __init__(self, prog, indent_increment=2, max_help_position=24, width=None):
        super().__init__(prog, indent_increment, max_help_position, width)
        # Check if terminal supports color
        self.supports_color = self._supports_color()

    def _supports_color(self) -> bool:
        """Check if the terminal supports color output."""
        import os

        # Check environment variables
        if os.environ.get("TERM") == "dumb":
            return False
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("FORCE_COLOR"):
            return True

        # Check if stdout is a TTY
        return sys.stdout.isatty()

    def start_section(self, heading: Optional[str]) -> None:
        """Override to add color to section headings."""
        if self.supports_color and heading:
            heading = f"\033[1m{heading}\033[0m"  # Bold
        super().start_section(heading)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="agentic",
        description="Agentic Brain - Lightweight AI Agent Framework",
        formatter_class=ColoredFormatter,
        epilog=(
            "Examples:\n"
            "  agentic chat                  Start interactive chat\n"
            "  agentic serve --port 8000    Start API server on port 8000\n"
            "  agentic init --name project  Initialize new project\n"
            "  agentic schema               Apply Neo4j schema\n"
            "  agentic version              Show version information"
        ),
    )

    # Global options
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show version and exit",
    )

    # Subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Chat command
    chat_parser = subparsers.add_parser(
        "chat",
        help="Start interactive chat session",
        formatter_class=ColoredFormatter,
        description="Start an interactive chat session with the agent",
    )
    chat_parser.add_argument(
        "--history",
        type=str,
        default=None,
        help="Load chat history from file",
    )
    chat_parser.add_argument(
        "--model",
        type=str,
        default="gpt-4",
        help="LLM model to use (default: gpt-4)",
    )
    chat_parser.add_argument(
        "--agent-name",
        type=str,
        default="assistant",
        help="Name of the agent (default: assistant)",
    )
    chat_parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable Neo4j memory integration",
    )
    chat_parser.set_defaults(func=commands.chat_command)

    # Serve command
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start API server",
        formatter_class=ColoredFormatter,
        description="Start the agentic-brain API server",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)",
    )
    serve_parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of worker processes (default: 4)",
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on file changes (development mode)",
    )
    serve_parser.set_defaults(func=commands.serve_command)

    # Init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize new project",
        formatter_class=ColoredFormatter,
        description="Initialize a new agentic-brain project",
    )
    init_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Project name",
    )
    init_parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Path to create project (default: current directory)",
    )
    init_parser.add_argument(
        "--skip-git",
        action="store_true",
        help="Skip git initialization",
    )
    init_parser.set_defaults(func=commands.init_command)

    # Schema command
    schema_parser = subparsers.add_parser(
        "schema",
        help="Apply Neo4j schema",
        formatter_class=ColoredFormatter,
        description="Apply or verify Neo4j database schema",
    )
    schema_parser.add_argument(
        "--uri",
        type=str,
        default="bolt://localhost:7687",
        help="Neo4j connection URI (default: bolt://localhost:7687)",
    )
    schema_parser.add_argument(
        "--username",
        type=str,
        default="neo4j",
        help="Neo4j username (default: neo4j)",
    )
    schema_parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Neo4j password (will prompt if not provided)",
    )
    schema_parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify schema without making changes",
    )
    schema_parser.set_defaults(func=commands.schema_command)

    # Install command
    install_parser = subparsers.add_parser(
        "install",
        help="Run installer",
        formatter_class=ColoredFormatter,
        description="Run the agentic-brain installer",
    )
    install_parser.add_argument(
        "--neo4j",
        action="store_true",
        help="Install Neo4j dependencies",
    )
    install_parser.add_argument(
        "--llm",
        action="store_true",
        help="Install LLM dependencies (OpenAI, etc.)",
    )
    install_parser.add_argument(
        "--all",
        action="store_true",
        help="Install all optional dependencies",
    )
    install_parser.set_defaults(func=commands.install_command)

    # Version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version information",
        formatter_class=ColoredFormatter,
        description="Display version and build information",
    )
    version_parser.set_defaults(func=commands.version_command)

    return parser


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # If no command specified, show help
    if not parsed_args.command:
        parser.print_help()
        return 0

    # Execute the command
    try:
        return parsed_args.func(parsed_args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        if parsed_args.verbose:
            # Show full traceback in verbose mode
            import traceback

            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
