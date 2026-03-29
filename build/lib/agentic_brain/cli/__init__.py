# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Agentic Brain CLI — The Universal AI Platform
==============================================

Command-line interface for agentic-brain with chat, server, and management commands.

**Install. Run. Create.** Zero to AI in 60 seconds.

Copyright (C) 2024-2026 Joseph Webber
License: Apache-2.0

Usage:
    agentic check                  Check LLM provider setup
    agentic chat                   Start interactive chat
    agentic serve --port 8000      Start API server
    agentic init --name project    Initialize new project
    agentic schema                 Apply Neo4j schema
    agentic benchmark              Benchmark LLM models
    agentic version                Show version info
"""

import argparse
import os
import sys
from typing import Optional

from agentic_brain import __version__

from . import commands
from .greet_command import register_greet_command
from .voice_commands import register_voice_commands

# Lazy import temporal_commands to avoid requiring temporalio
try:
    from .temporal_commands import register_temporal_commands

    HAS_TEMPORAL = True
except ImportError:
    HAS_TEMPORAL = False
    register_temporal_commands = None


# Environment variable defaults
def _env_default(key: str, default: str) -> str:
    """Get value from environment variable or use default."""
    return os.environ.get(key, default)


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
        description="Agentic Brain — The Universal AI Platform. Install. Run. Create.",
        formatter_class=ColoredFormatter,
        epilog=(
            "Quick Start:\n"
            "  agentic check                  Verify LLM providers are configured\n"
            "  agentic chat                   Start interactive AI chat session\n"
            "  agentic models                 List all 20+ available models\n"
            "  agentic model CL2              Get Claude Haiku details\n"
            "  agentic switch L1              Set fast local model as default\n"
            "  agentic test-model GR          Test Groq connectivity\n"
            "  agentic serve --port 8000      Launch production API server\n"
            "  agentic init --name my-app     Scaffold new AI project\n"
            "  agentic schema                 Apply Neo4j knowledge graph\n"
            "  agentic version                Show version and build info\n\n"
            "From Grandmother to Enterprise. Zero to AI in 60 seconds.\n"
            "Documentation: https://github.com/joseph-webber/agentic-brain"
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

    # Voice commands (critical for accessibility)
    register_voice_commands(subparsers)
    register_greet_command(subparsers)

    # Register Temporal commands (if available)
    if HAS_TEMPORAL:
        register_temporal_commands(subparsers)

    # Check command (new - for provider diagnosis)
    check_parser = subparsers.add_parser(
        "check",
        help="Diagnose LLM provider configuration",
        formatter_class=ColoredFormatter,
        description="Verify which LLM providers are available and properly configured. Run this first!",
        aliases=["doctor"],  # Also works as 'agentic doctor'
    )
    check_parser.set_defaults(func=commands.check_command)

    # Setup-help command (new - for detailed provider setup)
    setup_help_parser = subparsers.add_parser(
        "setup-help",
        help="Get setup instructions for a provider",
        formatter_class=ColoredFormatter,
        description="Get detailed setup instructions for a specific LLM provider",
    )
    setup_help_parser.add_argument(
        "provider",
        type=str,
        choices=[
            "groq",
            "ollama",
            "openai",
            "anthropic",
            "google",
            "xai",
            "openrouter",
            "together",
        ],
        help="Provider to get setup help for",
    )
    setup_help_parser.set_defaults(func=commands.setup_help_command)

    # Chat command
    chat_parser = subparsers.add_parser(
        "chat",
        help="Start AI chat session",
        formatter_class=ColoredFormatter,
        description="Launch an interactive AI chat session with memory and context",
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
        default=_env_default("AGENTIC_MODEL", "gpt-4"),
        help="LLM model to use (env: AGENTIC_MODEL, default: gpt-4)",
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
        help="Launch production API server",
        formatter_class=ColoredFormatter,
        description="Start the Agentic Brain REST API and WebSocket server for production deployments",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default=_env_default("AGENTIC_HOST", "127.0.0.1"),
        help="Server host (env: AGENTIC_HOST, default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=int(_env_default("AGENTIC_PORT", "8000")),
        help="Server port (env: AGENTIC_PORT, default: 8000)",
    )
    serve_parser.add_argument(
        "--workers",
        type=int,
        default=int(_env_default("AGENTIC_WORKERS", "4")),
        help="Number of worker processes (env: AGENTIC_WORKERS, default: 4)",
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
        help="Scaffold new AI project",
        formatter_class=ColoredFormatter,
        description="Initialize a new Agentic Brain project with best-practice structure",
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
        help="Apply Neo4j knowledge graph schema",
        formatter_class=ColoredFormatter,
        description="Apply or verify Neo4j database schema for GraphRAG memory",
    )
    schema_parser.add_argument(
        "--uri",
        type=str,
        default=_env_default("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j connection URI (env: NEO4J_URI, default: bolt://localhost:7687)",
    )
    schema_parser.add_argument(
        "--username",
        type=str,
        default=_env_default("NEO4J_USERNAME", "neo4j"),
        help="Neo4j username (env: NEO4J_USERNAME, default: neo4j)",
    )
    schema_parser.add_argument(
        "--password",
        type=str,
        default=os.environ.get("NEO4J_PASSWORD"),
        help="Neo4j password (env: NEO4J_PASSWORD, will prompt if not provided)",
    )
    schema_parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify schema without making changes",
    )
    schema_parser.set_defaults(func=commands.schema_command)

    # Setup command (enhanced installer)
    setup_parser = subparsers.add_parser(
        "setup",
        help="Run enhanced setup wizard",
        formatter_class=ColoredFormatter,
        description="Interactive setup wizard with environment detection, user profile, and health checks",
    )
    setup_parser.add_argument(
        "--non-interactive",
        "-y",
        action="store_true",
        help="Run without prompts (use defaults)",
    )
    setup_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output (accessibility)",
    )
    setup_parser.set_defaults(func=commands.setup_command)

    # Persona Install command (persona-driven setup)
    persona_parser = subparsers.add_parser(
        "persona",
        help="Run persona-driven installer",
        formatter_class=ColoredFormatter,
        description=(
            "Persona-driven setup that generates everything from a single choice. "
            "Pick Professional, Technical, Creative, Accessibility, Research, or Minimal. "
            "ADL and all config files are generated automatically."
        ),
    )
    persona_parser.add_argument(
        "--persona",
        type=str,
        choices=[
            "professional",
            "technical",
            "creative",
            "accessibility",
            "research",
            "minimal",
        ],
        help="Pre-select a persona (skips interactive menu)",
    )
    persona_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Generate config without prompts (requires --persona)",
    )
    persona_parser.set_defaults(func=commands.persona_install_command)

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

    # Benchmark command
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Benchmark LLM performance",
        formatter_class=ColoredFormatter,
        description="Benchmark LLM models for latency, throughput, and token performance metrics",
    )
    benchmark_parser.add_argument(
        "--models",
        type=str,
        default="llama3.2:3b",
        help="Comma-separated list of models to benchmark (default: llama3.2:3b)",
    )
    benchmark_parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=10,
        help="Number of iterations per model (default: 10)",
    )
    benchmark_parser.add_argument(
        "--warmup",
        type=int,
        default=2,
        help="Number of warmup iterations (default: 2)",
    )
    benchmark_parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Custom prompt to use for benchmarking",
    )
    benchmark_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (JSON format)",
    )
    benchmark_parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format (default: table)",
    )
    benchmark_parser.add_argument(
        "--ollama-host",
        type=str,
        default=_env_default("OLLAMA_HOST", "http://localhost:11434"),
        help="Ollama API host (env: OLLAMA_HOST, default: http://localhost:11434)",
    )
    benchmark_parser.add_argument(
        "--no-streaming",
        action="store_true",
        help="Skip streaming benchmark",
    )
    benchmark_parser.set_defaults(func=commands.benchmark_command)

    # Neo4j command group
    neo4j_parser = subparsers.add_parser(
        "neo4j",
        help="Manage Neo4j database",
        formatter_class=ColoredFormatter,
        description="Neo4j database management commands",
    )
    neo4j_subparsers = neo4j_parser.add_subparsers(
        dest="neo4j_command", help="Neo4j command"
    )

    # neo4j status
    neo4j_status = neo4j_subparsers.add_parser(
        "status",
        help="Check if Neo4j is running",
        formatter_class=ColoredFormatter,
    )
    neo4j_status.set_defaults(func=commands.neo4j_status_command)

    # neo4j start
    neo4j_start = neo4j_subparsers.add_parser(
        "start",
        help="Start Neo4j with Docker",
        formatter_class=ColoredFormatter,
    )
    neo4j_start.set_defaults(func=commands.neo4j_start_command)

    # neo4j stop
    neo4j_stop = neo4j_subparsers.add_parser(
        "stop",
        help="Stop the Neo4j container",
        formatter_class=ColoredFormatter,
    )
    neo4j_stop.set_defaults(func=commands.neo4j_stop_command)

    # neo4j restart
    neo4j_restart = neo4j_subparsers.add_parser(
        "restart",
        help="Restart Neo4j",
        formatter_class=ColoredFormatter,
    )
    neo4j_restart.set_defaults(func=commands.neo4j_restart_command)

    # Models command - list all available models
    models_parser = subparsers.add_parser(
        "models",
        help="List all available LLM models",
        formatter_class=ColoredFormatter,
        description="Display all available models with their codes, speeds, and costs",
    )
    models_parser.set_defaults(func=commands.models_command)

    # Region command - manage user regional preferences and learning
    from .region_commands import setup_region_parser

    setup_region_parser(subparsers)

    # ADL command group
    adl_parser = subparsers.add_parser(
        "adl",
        help="Agentic Definition Language (ADL)",
        formatter_class=ColoredFormatter,
        description=(
            "Work with Agentic Definition Language (ADL) files to "
            "configure your entire Agentic Brain instance from a single DSL."
        ),
    )
    adl_subparsers = adl_parser.add_subparsers(dest="adl_command", help="ADL command")

    # agentic adl init
    adl_init = adl_subparsers.add_parser(
        "init",
        help="Create an ADL template (brain.adl)",
        formatter_class=ColoredFormatter,
    )
    adl_init.add_argument(
        "-f",
        "--file",
        dest="file",
        type=str,
        default="brain.adl",
        help="Path to ADL file to create (default: brain.adl)",
    )
    adl_init.set_defaults(func=commands.adl_init_command)

    # agentic adl validate
    adl_validate = adl_subparsers.add_parser(
        "validate",
        help="Validate an ADL file",
        formatter_class=ColoredFormatter,
    )
    adl_validate.add_argument(
        "-f",
        "--file",
        dest="file",
        type=str,
        default="brain.adl",
        help="Path to ADL file (default: brain.adl)",
    )
    adl_validate.set_defaults(func=commands.adl_validate_command)

    # agentic adl generate
    adl_generate = adl_subparsers.add_parser(
        "generate",
        help="Generate config from ADL",
        formatter_class=ColoredFormatter,
    )
    adl_generate.add_argument(
        "-f",
        "--file",
        dest="file",
        type=str,
        default="brain.adl",
        help="Path to ADL file (default: brain.adl)",
    )
    adl_generate.add_argument(
        "-o",
        "--output",
        dest="output",
        type=str,
        default=None,
        help="Output directory for generated artefacts (default: ADL directory)",
    )
    adl_generate.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing generated files",
    )
    adl_generate.set_defaults(func=commands.adl_generate_command)

    # agentic adl import jdl
    adl_import = adl_subparsers.add_parser(
        "import",
        help="Import configuration from other DSLs (e.g., JHipster JDL)",
        formatter_class=ColoredFormatter,
    )
    adl_import.add_argument(
        "source",
        type=str,
        choices=["jdl"],
        help="Source format to import (currently only 'jdl')",
    )
    adl_import.add_argument(
        "-i",
        "--input",
        dest="input",
        type=str,
        default="app.jdl",
        help="Path to source file (default: app.jdl)",
    )
    adl_import.add_argument(
        "-f",
        "--file",
        dest="file",
        type=str,
        default="brain.adl",
        help="Output ADL file (default: brain.adl)",
    )
    adl_import.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing ADL file if present",
    )
    adl_import.set_defaults(func=commands.adl_import_command)

    # Model command - get info about specific model
    model_parser = subparsers.add_parser(
        "model",
        help="Get information about a specific model",
        formatter_class=ColoredFormatter,
        description="Display detailed information about a specific model by its code",
    )
    model_parser.add_argument(
        "code",
        type=str,
        help="Model code (e.g., L1, CL2, OP, GR)",
    )
    model_parser.set_defaults(func=commands.model_command)

    # Switch command - set default model
    switch_parser = subparsers.add_parser(
        "switch",
        help="Set the default model",
        formatter_class=ColoredFormatter,
        description="Set the default LLM model and save to config file",
    )
    switch_parser.add_argument(
        "code",
        type=str,
        help="Model code (e.g., L1, CL2, OP, GR)",
    )
    switch_parser.set_defaults(func=commands.switch_command)

    # Test-model command - test if a model works
    test_model_parser = subparsers.add_parser(
        "test-model",
        help="Test if a model responds correctly",
        formatter_class=ColoredFormatter,
        description="Send a test prompt to verify a model is working",
    )
    test_model_parser.add_argument(
        "code",
        type=str,
        help="Model code (e.g., L1, CL2, OP, GR)",
    )
    test_model_parser.set_defaults(func=commands.test_model_command)

    # Version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version information",
        formatter_class=ColoredFormatter,
        description="Display version and build information",
    )
    version_parser.set_defaults(func=commands.version_command)

    # Topic governance command group
    topics_parser = subparsers.add_parser(
        "topics",
        help="Audit and govern topic nodes",
        formatter_class=ColoredFormatter,
        description="Topic governance commands for soft-capped GraphRAG topic hubs",
    )
    topics_subparsers = topics_parser.add_subparsers(
        dest="topics_command", help="Topic governance command"
    )

    topics_audit_parser = topics_subparsers.add_parser(
        "audit",
        help="Run the quarterly topic governance audit",
        formatter_class=ColoredFormatter,
        description=(
            "Inspect topic growth, orphan nodes, and duplicate topics so the "
            "graph stays discoverable and below the soft cap."
        ),
    )
    topics_audit_parser.add_argument(
        "--uri",
        type=str,
        default=_env_default("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j connection URI (env: NEO4J_URI, default: bolt://localhost:7687)",
    )
    topics_audit_parser.add_argument(
        "--username",
        type=str,
        default=_env_default("NEO4J_USER", "neo4j"),
        help="Neo4j username (env: NEO4J_USER, default: neo4j)",
    )
    topics_audit_parser.add_argument(
        "--password",
        type=str,
        default=os.environ.get("NEO4J_PASSWORD"),
        help="Neo4j password (env: NEO4J_PASSWORD)",
    )
    topics_audit_parser.add_argument(
        "--database",
        type=str,
        default=_env_default("NEO4J_DATABASE", "neo4j"),
        help="Neo4j database name (env: NEO4J_DATABASE, default: neo4j)",
    )
    topics_audit_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum merge suggestions to include (default: 10)",
    )
    topics_audit_parser.add_argument(
        "--format",
        type=str,
        choices=["markdown", "text", "json"],
        default="markdown",
        help="Report output format (default: markdown)",
    )
    topics_audit_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional output path for the generated audit report",
    )
    topics_audit_parser.set_defaults(func=commands.topics_audit_command)

    # New-config command (interactive configuration wizard)
    from .new_config import new_config_command

    new_config_parser = subparsers.add_parser(
        "new-config",
        help="Interactive configuration wizard",
        formatter_class=ColoredFormatter,
        description="Create a new configuration file with interactive prompts",
    )
    new_config_parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Output path for config.json (default: ./config.json)",
    )
    new_config_parser.add_argument(
        "-y",
        "--non-interactive",
        action="store_true",
        help="Use defaults without prompting",
    )
    new_config_parser.set_defaults(func=new_config_command)

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


__all__ = [
    "create_parser",
    "main",
    "ColoredFormatter",
]


if __name__ == "__main__":
    sys.exit(main())
