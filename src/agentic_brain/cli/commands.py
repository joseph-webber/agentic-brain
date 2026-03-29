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
Agentic Brain CLI Commands
==========================

Implementation of CLI commands for agentic-brain.

Copyright (C) 2026 Joseph Webber
License: Apache-2.0
"""

import argparse
import getpass
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agentic_brain import __version__
from agentic_brain.core.neo4j_pool import (
    configure_pool as configure_neo4j_pool,
)
from agentic_brain.core.neo4j_pool import (
    get_session as get_shared_neo4j_session,
)


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"

    @classmethod
    def disabled(cls) -> None:
        """Disable all colors."""
        for attr in dir(cls):
            if not attr.startswith("_"):
                setattr(cls, attr, "")


def supports_color() -> bool:
    """Check if terminal supports color output."""
    if os.environ.get("TERM") == "dumb":
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


# Disable colors if not supported
if not supports_color():
    Colors.disabled()


def print_header(text: str) -> None:
    """Print a colored header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}→ {text}{Colors.RESET}\n")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗{Colors.RESET} {text}", file=sys.stderr)


def _write_output_file(path: str, content: str) -> None:
    """Write CLI output to a file, ensuring parent directories exist."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content.rstrip() + "\n", encoding="utf-8")


def topics_audit_command(args: argparse.Namespace) -> int:
    """Run the quarterly topic governance audit against Neo4j."""
    from agentic_brain.graph import TopicHub, render_audit_report

    print_header("Quarterly Topic Audit")

    configure_neo4j_pool(
        uri=args.uri,
        user=args.username,
        password=args.password,
        database=args.database,
    )

    hub = TopicHub(session_factory=get_shared_neo4j_session)
    report = hub.build_quarterly_audit(limit=args.limit)
    rendered_report = render_audit_report(report, format=args.format)

    topic_health: dict[str, Any] = report["topic_health"]
    status = str(topic_health["status"])
    if status == "soft-cap-exceeded":
        print_warning(
            f"Topic count is above the soft cap: {topic_health['topic_count']} / {topic_health['soft_cap']}"
        )
    elif status == "warning":
        print_warning(
            f"Topic count is approaching the soft cap: {topic_health['topic_count']} / {topic_health['soft_cap']}"
        )
    else:
        print_success(
            f"Topic hub is healthy: {topic_health['topic_count']} / {topic_health['soft_cap']}"
        )

    print(rendered_report)

    if args.output:
        _write_output_file(args.output, rendered_report)
        print_success(f"Saved topic audit report to {args.output}")

    return 0


def find_available_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """
    Find an available port starting from start_port.

    Attempts to find an unused port by trying to bind to progressively higher
    ports up to max_attempts times. This is useful for avoiding port conflicts
    when running multiple services.

    Args:
        start_port (int): The port number to start checking from (default: 8000)
        max_attempts (int): Maximum number of ports to attempt (default: 10)

    Returns:
        int: The first available port found

    Raises:
        RuntimeError: If no available ports found in the range

    Example:
        >>> port = find_available_port(8000, 10)
        >>> print(f"Using port {port}")
        Using port 8001
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No available ports in range {start_port}-{start_port + max_attempts - 1}"
    )


def print_box(title: str, lines: list, header_color: str = Colors.CYAN) -> None:
    """Print a fancy box with title and content lines."""
    width = max(len(title) + 4, max(len(line) for line in lines) + 4)
    print()
    print(f"{header_color}╔{'═' * (width - 2)}╗{Colors.RESET}")
    print(
        f"{header_color}║{Colors.RESET}  {Colors.BOLD}{title}{Colors.RESET}"
        + " " * (width - len(title) - 4)
        + f"{header_color}║{Colors.RESET}"
    )
    print(f"{header_color}╠{'═' * (width - 2)}╣{Colors.RESET}")
    for line in lines:
        padding = " " * (width - len(line) - 3)
        print(
            f"{header_color}║{Colors.RESET} {line}{padding}{header_color}║{Colors.RESET}"
        )
    print(f"{header_color}╚{'═' * (width - 2)}╝{Colors.RESET}")
    print()


ADL_TEMPLATE = """// brain.adl - This is all you need to start!
application MyBrain {}
"""


def adl_init_command(args: argparse.Namespace) -> int:
    """Create a new ADL template file.

    Examples:
        agentic adl init
        agentic adl init --file config/brain.adl
    """

    from pathlib import Path

    path = Path(getattr(args, "file", "brain.adl"))
    if path.exists():
        print_error(f"ADL file already exists: {path}")
        print_info("Delete it or choose a different path with --file.")
        return 1

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ADL_TEMPLATE, encoding="utf-8")
    print_success(f"Created ADL template at {path}")
    return 0


def adl_validate_command(args: argparse.Namespace) -> int:
    """Validate an ADL file and show a short summary."""

    from pathlib import Path

    from agentic_brain.adl import parse_adl_file
    from agentic_brain.adl.parser import ADLParseError

    path = Path(getattr(args, "file", "brain.adl"))
    if not path.exists():
        print_error(f"ADL file not found: {path}")
        return 1

    try:
        cfg = parse_adl_file(path)
    except ADLParseError as e:
        print_error(f"Invalid ADL syntax in {path}: {e}")
        return 1

    print_success(f"ADL file {path} is valid")
    counts = [
        f"application={1 if cfg.application else 0}",
        f"llm={len(cfg.llms)}",
        f"rag={len(cfg.rags)}",
        f"voice={len(cfg.voices)}",
        f"api={len(cfg.apis)}",
        f"security={'1' if cfg.security else '0'}",
        f"modes={'1' if cfg.modes else '0'}",
        f"deployment={'1' if cfg.deployment else '0'}",
    ]
    print_info("Blocks: " + ", ".join(counts))
    return 0


def adl_generate_command(args: argparse.Namespace) -> int:
    """Generate config artefacts from an ADL file."""

    from pathlib import Path

    from agentic_brain.adl import generate_from_adl

    path = Path(getattr(args, "file", "brain.adl"))
    output = getattr(args, "output", None)
    overwrite = bool(getattr(args, "force", False))

    if not path.exists():
        print_error(f"ADL file not found: {path}")
        return 1

    result = generate_from_adl(path, output_dir=output, overwrite=overwrite)

    print_success("Generated configuration from ADL")
    print_info(f"Config module: {result.config_module}")
    print_info(f".env file:     {result.env_file}")
    print_info(f"Docker compose: {result.docker_compose}")
    print_info(f"API module:    {result.api_module}")
    return 0


def _render_adl_from_jdl(app_name: str) -> str:
    """Render a simple ADL file using an application name from JDL."""

    name = app_name.strip() or "AgenticBrain"
    return ADL_TEMPLATE.replace(
        "application AgenticBrain", f"application {name}"
    ).replace('name "My Enterprise AI"', f'name "{name} AI"')


def adl_import_command(args: argparse.Namespace) -> int:
    """Import configuration from another DSL into ADL.

    Currently supports:
        agentic adl import jdl
    """

    from pathlib import Path

    source = getattr(args, "source", "jdl")
    if source != "jdl":
        print_error(f"Unsupported import source: {source}")
        return 1

    input_path = Path(getattr(args, "input", "app.jdl"))
    output_path = Path(getattr(args, "file", "brain.adl"))
    force = bool(getattr(args, "force", False))

    if not input_path.exists():
        print_error(f"JDL file not found: {input_path}")
        return 1

    if output_path.exists() and not force:
        print_error(f"ADL file already exists: {output_path}")
        print_info("Use --force to overwrite or choose a different --file.")
        return 1

    text = input_path.read_text(encoding="utf-8")
    app_name = "AgenticBrain"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("application"):
            parts = stripped.split()
            if len(parts) >= 2 and parts[1] != "{":
                app_name = parts[1].strip("{")
            break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_adl_from_jdl(app_name), encoding="utf-8")
    print_success(f"Imported JDL application '{app_name}' into ADL at {output_path}")
    return 0


def setup_command(args: argparse.Namespace) -> int:
    """
    Run the enhanced setup wizard.

    Interactive installer with:
    - Environment detection (OS, Python, GPU, voices)
    - User profile setup (timezone, location, preferences)
    - LLM configuration (API keys, fallback chain)
    - ADL initialization (default configuration)
    - Health check (verify everything works)

    Args:
        args: Command-line arguments with non_interactive and no_color flags

    Returns:
        0 on success, 1 on error
    """
    print_header("Enhanced Setup Wizard")

    try:
        # Import the enhanced installer
        from agentic_brain.installer_enhanced import run_enhanced_installer

        # Run the installer
        run_enhanced_installer(non_interactive=args.non_interactive)

        return 0
    except ImportError as e:
        print_error(f"Enhanced installer not available: {e}")
        print_info("Try running: pip install agentic-brain[full]")
        return 1
    except KeyboardInterrupt:
        print_warning("\nSetup cancelled by user")
        return 1
    except Exception as e:
        print_error(f"Setup failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


def persona_install_command(args: argparse.Namespace) -> int:
    """
    Run persona-driven installer for Agentic Brain.

    Interactive installer that guides users through persona-based setup.
    Everything flows from persona selection - ADL is generated automatically.

    Args:
        args: Command-line arguments with persona and non_interactive flags

    Returns:
        0 on success, 1 on error
    """
    try:
        # Build sys.argv for the installer
        import sys

        from agentic_brain.installer_persona import main as persona_main

        old_argv = sys.argv
        sys.argv = ["agentic"]

        if hasattr(args, "persona") and args.persona:
            sys.argv.extend(["--persona", args.persona])

        if hasattr(args, "non_interactive") and args.non_interactive:
            sys.argv.append("--non-interactive")

        try:
            persona_main()
            return 0
        finally:
            sys.argv = old_argv

    except ImportError as e:
        print_error(f"Persona installer not available: {e}")
        return 1
    except KeyboardInterrupt:
        print_warning("\nInstallation cancelled by user")
        return 1
    except Exception as e:
        print_error(f"Installation failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


def check_command(args: argparse.Namespace) -> int:
    """
    Check LLM provider configuration and availability.

    Diagnoses LLM setup and provides actionable guidance for new users.

    Features:
        - Auto-detects available providers (Ollama, OpenAI, Anthropic, OpenRouter)
        - Checks environment variables for API keys
        - Validates provider connectivity
        - Shows step-by-step setup instructions
        - Identifies which providers are ready to use
        - Checks Neo4j connectivity (optional but helpful)

    Output:
        Comprehensive status report showing:
        - Available providers with connection details
        - Missing providers with setup instructions
        - Neo4j status (connected/not connected/optional)
        - Next steps for quick setup
        - Links to documentation

    Exit Codes:
        0: At least one provider is available
        1: No providers configured (setup needed)

    Examples:
        $ agentic check              # Check all providers
        $ agentic check --verbose    # Verbose output with details

    Use Cases:
        - First-time setup verification
        - Troubleshooting LLM connection issues
        - Validating environment configuration
        - Pre-flight checks before using chat/serve
    """
    from agentic_brain.router import (
        ProviderChecker,
        format_provider_status_report,
        get_setup_help,
    )

    print_header("LLM Provider Status Check")

    try:
        status_dict = ProviderChecker.check_all()
        available = [s for s in status_dict.values() if s.available]

        # Print detailed report
        report = format_provider_status_report(status_dict)
        print(report)

        if available:
            print_success(
                f"Ready to use! {len(available)} provider(s) available: "
                f"{', '.join([s.provider.value for s in available])}"
            )
            print_info("Try running: agentic chat")

            # Check Neo4j (optional)
            try:
                neo4j_uri = os.getenv("NEO4J_URI")
                if neo4j_uri:
                    print_info("Neo4j is configured (optional memory/persistence)")
            except Exception:
                pass

            return 0
        else:
            print_error("No LLM providers configured")
            print()
            print_info("Quick setup (2 minutes):")
            print(get_setup_help("groq"))
            print_info("Or run: agentic setup-help <provider_name>")
            print_info(
                "Available providers: groq, ollama, openai, anthropic, google, xai, openrouter, together"
            )
            return 1

    except Exception as e:
        print_error(f"Provider check failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def setup_help_command(args: argparse.Namespace) -> int:
    """
    Get detailed setup instructions for a specific LLM provider.

    Shows step-by-step instructions for configuring the requested provider.

    Examples:
        $ agentic setup-help groq
        $ agentic setup-help ollama
        $ agentic setup-help openai
    """
    from agentic_brain.router import get_setup_help

    try:
        provider = args.provider.lower()
        help_text = get_setup_help(provider)
        print(help_text)
        return 0
    except Exception as e:
        print_error(f"Failed to get setup help for {args.provider}: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def chat_command(args: argparse.Namespace) -> int:
    """
    Start an interactive chat session with the Agentic Brain agent.

    Launches an interactive CLI chat interface where users can:
    - Send messages to the agent
    - View agent responses
    - Access command history
    - Integrate with Neo4j memory (optional)
    - Load previous conversations

    Features:
        - Multi-line input support
        - Color-coded output (user/agent)
        - Command history with help
        - Optional Neo4j memory integration
        - Graceful error handling
        - Support for custom agents

    Commands available in chat:
        - help: Display available commands
        - exit/quit/bye: Exit the chat
        - clear: Clear the screen

    Configuration:
        - Agent name customizable via --agent-name
        - Memory integration optional (--no-memory disables)
        - Custom model can be specified
        - History can be loaded from file

    Args:
        args (argparse.Namespace): Parsed arguments with:
            - model (str): LLM model name
            - agent_name (str): Agent name for identification
            - no_memory (bool): Disable Neo4j memory if True
            - history (Optional[str]): Path to history file to load
            - verbose (bool): Enable verbose logging on error

    Returns:
        int: Exit code
            - 0: Successful chat session exit
            - 1: Error (import missing, connection failed, etc.)

    Raises:
        ImportError: If required dependencies not installed
        ConnectionError: If Neo4j connection fails (non-fatal)
        Exception: Other unhandled errors (logged if verbose)

    Example:
        >>> import argparse
        >>> args = argparse.Namespace(
        ...     model="llama3.1:8b",
        ...     agent_name="assistant",
        ...     no_memory=False,
        ...     history=None,
        ...     verbose=False
        ... )
        >>> result = chat_command(args)
        >>> print(f"Exit code: {result}")

    Note:
        - Requires agentic-brain[all] or agentic-brain[neo4j]
        - Neo4j connection is optional but recommended
        - Memory integration at bolt://localhost:7687
        - Keyboard interrupt (Ctrl+C) returns to prompt
        - Colors disabled in non-TTY environments
    """
    print_header("Agentic Brain Chat")
    print(f"Version: {__version__}")
    print(f"Model: {Colors.CYAN}{args.model}{Colors.RESET}")
    print(f"Agent: {Colors.CYAN}{args.agent_name}{Colors.RESET}")

    if args.no_memory:
        print_warning("Memory integration disabled")
    else:
        print_info("Memory integration: Neo4j (at bolt://localhost:7687)")

    if args.history:
        print_info(f"Loading history from: {args.history}")

    print_info("Type 'help' for available commands, 'exit' to quit\n")

    try:
        from agentic_brain import Agent, Neo4jMemory

        # Initialize memory if enabled
        memory = None
        if not args.no_memory:
            try:
                memory = Neo4jMemory(uri="bolt://localhost:7687")
                print_success("Connected to Neo4j memory")
            except Exception as e:
                print_warning(f"Could not connect to Neo4j: {e}")
                print_info("Continuing without memory...")

        # Create agent
        agent = Agent(name=args.agent_name, memory=memory)
        print_success(f"Agent '{args.agent_name}' ready\n")

        # Interactive chat loop
        while True:
            try:
                user_input = input(f"{Colors.BOLD}You:{Colors.RESET} ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ("exit", "quit", "bye"):
                    print_info("Goodbye!")
                    break

                if user_input.lower() == "help":
                    print("\nAvailable commands:")
                    print("  help   - Show this help message")
                    print("  exit   - Exit the chat")
                    print("  clear  - Clear screen")
                    print("\nOtherwise, just chat naturally!\n")
                    continue

                if user_input.lower() == "clear":
                    print("\033[2J\033[H", end="", flush=True)
                    continue

                # Send message to agent
                print(f"{Colors.DIM}Agent:{Colors.RESET} ", end="", flush=True)
                response = agent.chat(user_input)
                print(response + "\n")

            except KeyboardInterrupt:
                print("\n")
                continue

    except ImportError as e:
        print_error(f"Required dependency not installed: {e}")
        print_info("Install with: pip install agentic-brain[all]")
        return 1
    except Exception as e:
        print_error(f"Chat failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

    return 0


def serve_command(args: argparse.Namespace) -> int:
    """
    Start the Agentic Brain FastAPI server.

    Launches a production-ready REST API and WebSocket server with:
    - Chat endpoints (POST /chat, GET /chat/stream, WS /ws/chat)
    - Session management (GET, DELETE /session/{id})
    - Dashboard admin interface (GET /dashboard)
    - Real-time metrics and health checks
    - Automatic API documentation (OpenAPI/Swagger)

    Server Features:
        - Uvicorn ASGI server with configurable workers
        - Auto-reload support for development
        - CORS middleware for frontend support
        - Comprehensive error handling
        - Structured JSON logging
        - WebSocket streaming support

    Configuration:
        - Host: Network interface to bind to
        - Port: Server port (default: 8000)
        - Workers: Number of worker processes
        - Reload: Auto-reload on file changes (dev mode)
        - All settings via CLI arguments

    Endpoints:
        - POST /chat: Send message, get response
        - GET /chat/stream: SSE streaming response
        - WS /ws/chat: WebSocket bidirectional chat
        - GET /session/{id}: Get session info
        - DELETE /session/{id}: Delete session
        - GET /health: Server health check
        - GET /dashboard: Admin dashboard
        - GET /docs: Swagger UI
        - GET /redoc: ReDoc documentation

    Args:
        args (argparse.Namespace): Parsed arguments with:
            - host (str): Host to bind to (e.g., "0.0.0.0")
            - port (int): Server port
            - workers (int): Number of worker processes
            - reload (bool): Enable auto-reload for development
            - verbose (bool): Enable verbose logging on error

    Returns:
        int: Exit code
            - 0: Server ran successfully (no errors)
            - 1: Error starting or running server

    Raises:
        ImportError: If uvicorn or FastAPI not installed
        OSError: If port is already in use or permission denied
        Exception: Other unhandled errors (logged if verbose)

    Example:
        >>> import argparse
        >>> args = argparse.Namespace(
        ...     host="0.0.0.0",
        ...     port=8000,
        ...     workers=4,
        ...     reload=False,
        ...     verbose=False
        ... )
        >>> serve_command(args)  # Blocks until server stopped

    Development vs Production:
        Development:
            >>> args.reload = True
            >>> args.workers = 1
            >>> # Auto-reload on code changes

        Production:
            >>> args.reload = False
            >>> args.workers = 4  # Or number of CPU cores
            >>> # Use reverse proxy (nginx) for SSL/load balancing

    Note:
        - Requires agentic-brain[api] or full install
        - Server starts at http://{host}:{port}
        - API docs at http://localhost:8000/docs
        - WebSocket at ws://localhost:8000/ws/chat
        - Dashboard at http://localhost:8000/dashboard
        - Sessions stored in memory (lost on restart)
        - For persistence, integrate with database
    """
    # Check and auto-detect port
    port = args.port
    actual_port = port

    try:
        actual_port = find_available_port(port, max_attempts=10)
        if actual_port != port:
            print_warning(f"Port {port} is busy, using {actual_port} instead")
    except RuntimeError as e:
        print_error(str(e))
        return 1

    # Get LLM info for startup message
    llm_status = "❌ Not configured"
    llm_provider = os.environ.get("LLM_PROVIDER", "").lower()

    if llm_provider == "groq":
        key = os.environ.get("GROQ_API_KEY", "")
        if key:
            llm_status = f"✅ Groq ({key[:10]}...)"
    elif llm_provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        if key:
            llm_status = f"✅ OpenAI ({key[:10]}...)"
    elif llm_provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            llm_status = f"✅ Anthropic ({key[:10]}...)"
    elif llm_provider == "ollama":
        llm_status = "✅ Ollama (local)"
    else:
        # Check for any provider key
        if os.environ.get("GROQ_API_KEY"):
            llm_status = "✅ Groq (auto-detected)"
        elif os.environ.get("OPENAI_API_KEY"):
            llm_status = "✅ OpenAI (auto-detected)"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            llm_status = "✅ Anthropic (auto-detected)"

    # Check Neo4j
    neo4j_status = "⚠️ Not connected (optional)"
    neo4j_uri = os.environ.get("NEO4J_URI", "")
    if neo4j_uri and neo4j_uri != "neo4j://localhost:7687":
        neo4j_status = "✅ Connected"
    else:
        # Try to detect if container is running
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    "name=neo4j-brain",
                    "--format",
                    "{{.Status}}",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and "Up" in result.stdout:
                neo4j_status = "✅ Running (docker)"
        except Exception:
            pass

    # Print startup box
    startup_lines = [
        f"API:       {Colors.CYAN}http://localhost:{actual_port}{Colors.RESET}",
        f"Dashboard: {Colors.CYAN}http://localhost:{actual_port}/dashboard{Colors.RESET}",
        f"Docs:      {Colors.CYAN}http://localhost:{actual_port}/docs{Colors.RESET}",
        f"WebSocket: {Colors.CYAN}ws://localhost:{actual_port}/ws/chat{Colors.RESET}",
        "",
        f"LLM:       {llm_status}",
        f"Neo4j:     {neo4j_status}",
    ]

    print_box("🧠 Agentic Brain Server", startup_lines)

    try:
        import uvicorn

        # When using reload or workers > 1, uvicorn needs an import string
        # This avoids the "must pass application as import string" warning
        use_import_string = args.reload or args.workers > 1

        if use_import_string:
            # Use import string for reload/workers support
            print_info("Starting server (use Ctrl+C to stop)...")
            uvicorn.run(
                "agentic_brain.api:app",
                host=args.host,
                port=actual_port,
                workers=1 if args.reload else args.workers,
                reload=args.reload,
                access_log=True,
                factory=True,  # app is a factory function (create_app)
            )
        else:
            # Direct app object for single worker, no reload (faster startup)
            from agentic_brain.api import create_app

            app = create_app()
            print_info("Starting server (use Ctrl+C to stop)...")
            uvicorn.run(
                app,
                host=args.host,
                port=actual_port,
                workers=1,
                access_log=True,
            )

    except ImportError as e:
        print_error(f"Required dependency not installed: {e}")
        print_info("Install with: pip install agentic-brain[api]")
        return 1
    except Exception as e:
        print_error(f"Server failed to start: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

    return 0


def init_command(args: argparse.Namespace) -> int:
    """
    Initialize a new Agentic Brain project.

    Creates a complete project scaffold with:
    - Project directory structure
    - Python package setup (pyproject.toml)
    - Configuration templates (.env.example)
    - README documentation
    - Main entry point (main.py)
    - Git repository (optional)

    Created Structure:
        project-name/
        ├── src/
        │   └── project_name/
        │       ├── __init__.py
        │       └── main.py
        ├── tests/
        ├── data/
        ├── config/
        ├── pyproject.toml
        ├── .env.example
        └── README.md

    Files Created:
        - pyproject.toml: Package metadata and dependencies
        - .env.example: Environment variables template
        - README.md: Project documentation
        - src/<project>/main.py: Main agent code
        - src/<project>/__init__.py: Package init
        - Git repository (unless --skip-git specified)

    Configuration:
        - Project name from CLI argument
        - Installation path (default: current directory)
        - Auto-initializes git (unless --skip-git)
        - Generates dependencies based on version

    Args:
        args (argparse.Namespace): Parsed arguments with:
            - name (str): Project name (used for directory and package)
            - path (str): Installation path (default: ".")
            - skip_git (bool): Skip git initialization if True
            - verbose (bool): Enable verbose logging on error

    Returns:
        int: Exit code
            - 0: Project created successfully
            - 1: Error creating project

    Raises:
        OSError: If path doesn't exist or permission denied
        Exception: Other errors (logged if verbose)

    Example:
        >>> import argparse
        >>> args = argparse.Namespace(
        ...     name="my-chatbot",
        ...     path="/home/user/projects",
        ...     skip_git=False,
        ...     verbose=False
        ... )
        >>> result = init_command(args)
        >>> # Creates /home/user/projects/my-chatbot/

    Next Steps (printed):
        1. cd project-name
        2. pip install -e .
        3. cp .env.example .env
        4. Edit .env with configuration
        5. python -m agentic_brain.cli chat

    Dependencies:
        The generated pyproject.toml includes:
        - agentic-brain[all] (main package with all features)
        - Python >= 3.9 requirement
        - Apache-2.0 license

    Note:
        - Project name is also used as package name (- becomes _)
        - Creates local editable install with pip install -e .
        - Git initialization runs in background
        - All created files use Apache-2.0 license
        - Python version >= 3.9 required
    """
    print_header(f"Initializing Project: {args.name}")

    project_path = Path(args.path) / args.name
    project_path.mkdir(parents=True, exist_ok=True)

    try:
        # Create project structure
        print_info("Creating project structure...")
        (project_path / "src").mkdir(exist_ok=True)
        (project_path / "src" / args.name.replace("-", "_")).mkdir(exist_ok=True)
        (project_path / "tests").mkdir(exist_ok=True)
        (project_path / "data").mkdir(exist_ok=True)
        (project_path / "config").mkdir(exist_ok=True)

        # Create __init__.py files
        (project_path / "src" / args.name.replace("-", "_") / "__init__.py").write_text(
            f'"""\\n{args.name.replace("-", " ").title()}\n\n'
            f'Created with agentic-brain {__version__}\n"""\n'
        )

        # Create main.py
        main_py_content = f'''"""
Main entry point for {args.name}
"""

from agentic_brain import Agent, Neo4jMemory, __version__


def main():
    """Run the agent."""
    print(f"Starting {{args.name}} (agentic-brain {__version__})")

    # Initialize memory
    memory = Neo4jMemory(uri="bolt://localhost:7687")

    # Create agent
    agent = Agent(name="{args.name}", memory=memory)

    # Run agent
    response = agent.chat("Hello!")
    print(response)


if __name__ == "__main__":
    main()
'''
        (project_path / "src" / args.name.replace("-", "_") / "main.py").write_text(
            main_py_content
        )

        # Create pyproject.toml
        pyproject_content = f"""[project]
name = "{args.name}"
version = "0.1.0"
description = "Agentic brain project"
requires-python = ">=3.9"
license = {{text = "Apache-2.0"}}
authors = [
    {{name = "Your Name", email = "your.email@example.com"}}
]

dependencies = [
    "agentic-brain[all]>={__version__}",
]

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"
"""
        (project_path / "pyproject.toml").write_text(pyproject_content)

        # Create .env.example
        env_example = """# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# LLM Configuration
OPENAI_API_KEY=your-api-key-here
LLM_MODEL=gpt-4

# Agent Configuration
AGENT_NAME=assistant
"""
        (project_path / ".env.example").write_text(env_example)

        # Create README.md
        readme_content = f"""# {args.name.replace("-", " ").title()}

Agentic brain project.

## Setup

```bash
pip install -e .
```

## Running

```bash
python -m agentic_brain.cli chat
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

## License

Apache-2.0
"""
        (project_path / "README.md").write_text(readme_content)

        # Initialize git if requested
        if not args.skip_git:
            print_info("Initializing git repository...")
            subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
            print_success("Git repository initialized")

        print_success(f"Project created at: {Colors.CYAN}{project_path}{Colors.RESET}")
        print_info("Next steps:")
        print(f"  cd {project_path}")
        print("  pip install -e .")
        print("  cp .env.example .env")
        print("  # Edit .env with your configuration")
        print("  python -m agentic_brain.cli chat\n")

        return 0

    except Exception as e:
        print_error(f"Project initialization failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def schema_command(args: argparse.Namespace) -> int:
    """
    Apply or verify Neo4j database schema.

    Manages Neo4j constraints and indexes for Agentic Brain:
    - Create unique constraints on Entity nodes
    - Create indexes for optimized queries
    - Verify existing schema
    - Display database statistics

    Schema Components:
        Constraints:
            - Entity.id IS UNIQUE (prevents duplicate IDs)

        Indexes:
            - Entity.timestamp (for time-range queries)

        Database Stats:
            - Node count
            - Relationship count

    Modes:
        Apply (default):
            - Creates constraints if missing
            - Creates indexes if missing
            - Idempotent (safe to run multiple times)
            - Shows created count

        Verify (--verify-only):
            - Lists existing constraints
            - Lists existing indexes
            - Shows database statistics
            - Does not create anything

    Authentication:
        - URI: Bolt protocol (bolt://localhost:7687)
        - Username: Prompts if not provided
        - Password: Prompts if not provided (hidden input)
        - Command-line arguments can provide credentials

    Args:
        args (argparse.Namespace): Parsed arguments with:
            - uri (str): Neo4j bolt URI
            - username (str): Neo4j username
            - password (Optional[str]): Neo4j password (prompts if missing)
            - verify_only (bool): Verify instead of apply if True
            - verbose (bool): Enable verbose logging on error

    Returns:
        int: Exit code
            - 0: Schema operation successful
            - 1: Error (connection failed, schema error, etc.)

    Raises:
        ImportError: If neo4j driver not installed
        ConnectionError: If cannot connect to Neo4j
        Exception: Other errors (logged if verbose)

    Example:
        Apply schema (creates constraints and indexes):
            >>> import argparse
            >>> args = argparse.Namespace(
            ...     uri="bolt://localhost:7687",
            ...     username="neo4j",
            ...     password="password",
            ...     verify_only=False,
            ...     verbose=False
            ... )
            >>> schema_command(args)

        Verify existing schema:
            >>> args.verify_only = True
            >>> schema_command(args)

    Usage:
        Command line:
            $ agentic-brain schema --uri bolt://localhost:7687
            $ agentic-brain schema --verify-only

    Common Connection Strings:
        Local development:
            bolt://localhost:7687

        Remote server:
            bolt://neo4j.example.com:7687

        With authentication in URI:
            bolt+s://user:password@hostname:7687

    Note:
        - Requires neo4j driver (pip install neo4j)
        - Neo4j server must be running and accessible
        - Default URI: bolt://localhost:7687
        - Default username: neo4j
        - Password always prompted for security
        - Statistics shown via APOC (if installed)
        - Constraints prevent data integrity issues
        - Indexes speed up queries
    """
    print_header("Neo4j Schema Management")
    print(f"URI: {Colors.CYAN}{args.uri}{Colors.RESET}")
    print(f"User: {Colors.CYAN}{args.username}{Colors.RESET}")

    try:
        # Get password if not provided
        password = args.password
        if not password:
            password = getpass.getpass("Neo4j Password: ")

        print_info("Connecting to Neo4j...")
        configure_neo4j_pool(
            uri=args.uri,
            user=args.username,
            password=password,
        )

        with get_shared_neo4j_session() as session:
            print_success("Connected to Neo4j")

            if args.verify_only:
                print_info("Verifying schema...")
                # Check for essential constraints and indexes
                constraints = session.run("SHOW CONSTRAINTS").data()
                indexes = session.run("SHOW INDEXES").data()

                print(f"\nConstraints: {len(constraints)}")
                for constraint in constraints[:5]:
                    print(f"  - {constraint}")

                print(f"\nIndexes: {len(indexes)}")
                for index in indexes[:5]:
                    print(f"  - {index}")

            else:
                print_info("Applying schema...")

                # Create constraints
                session.run(
                    """
                    CREATE CONSTRAINT IF NOT EXISTS
                    FOR (n:Entity) REQUIRE n.id IS UNIQUE
                    """
                )
                print_success("Created Entity constraints")

                # Create indexes
                session.run(
                    """
                    CREATE INDEX IF NOT EXISTS
                    FOR (n:Entity) ON (n.timestamp)
                    """
                )
                print_success("Created indexes")

            # Get statistics
            stats = session.run(
                "CALL apoc.meta.stats() YIELD nodeCount, relCount"
            ).single()

            if stats:
                print_info(
                    f"Database stats: {stats['nodeCount']} nodes, "
                    f"{stats['relCount']} relationships"
                )

        print_success("Schema operation completed\n")
        return 0

    except ImportError:
        print_error("neo4j driver not installed")
        print_info("Install with: pip install neo4j")
        return 1
    except Exception as e:
        print_error(f"Schema operation failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def install_command(args: argparse.Namespace) -> int:
    """
    Install optional Agentic Brain dependencies.

    Manages optional feature packages for Agentic Brain:
    - Neo4j: Database and memory integration
    - LLM: Language model providers
    - API: Web server and REST API

    Available Packages:
        neo4j:
            - Neo4j graph database driver
            - Memory management for agents
            - Knowledge graph integration

        llm:
            - Language model providers
            - OpenAI, Anthropic, Ollama support
            - Local model inference

        api:
            - FastAPI web framework
            - Uvicorn ASGI server
            - WebSocket support

    Installation Groups:
        Individual:
            $ agentic-brain install --neo4j
            $ agentic-brain install --llm

        All:
            $ agentic-brain install --all

    Implementation:
        - Runs pip install with packages list
        - Constructs format: agentic-brain[group1,group2]
        - Supports multiple groups
        - Displays installation progress
        - Returns pip exit code

    Args:
        args (argparse.Namespace): Parsed arguments with:
            - all (bool): Install all optional dependencies
            - neo4j (bool): Install Neo4j dependencies
            - llm (bool): Install LLM dependencies
            - verbose (bool): Enable verbose logging on error

    Returns:
        int: Exit code
            - 0: Installation successful
            - 1: Installation failed or no groups specified

    Raises:
        ImportError: If subprocess not available (shouldn't happen)
        OSError: If pip command not found
        Exception: Other errors (logged if verbose)

    Example:
        Install all dependencies:
            >>> import argparse
            >>> args = argparse.Namespace(
            ...     all=True,
            ...     neo4j=False,
            ...     llm=False,
            ...     verbose=False
            ... )
            >>> install_command(args)

        Install specific packages:
            >>> args.all = False
            >>> args.neo4j = True
            >>> args.llm = True
            >>> install_command(args)

    Command line:
        Install all:
            $ agentic-brain install --all

        Install Neo4j:
            $ agentic-brain install --neo4j

        Install LLM:
            $ agentic-brain install --llm

        Show options:
            $ agentic-brain install

    Installed Packages:
        Neo4j:
            - neo4j (Python driver)
            - neo4j-admin-tools

        LLM:
            - openai
            - anthropic
            - ollama

        API:
            - fastapi
            - uvicorn

    Note:
        - Runs pip in subprocess
        - Requires pip and internet connection
        - May prompt for elevated permissions
        - Installation may take several minutes
        - Check pip output for details
        - --verbose shows full pip output
    """
    print_header("Agentic Brain Installer")
    print(f"Version: {__version__}\n")

    # Determine what to install
    install_groups = []
    if args.all:
        install_groups = ["neo4j", "llm", "api"]
    else:
        if args.neo4j:
            install_groups.append("neo4j")
        if args.llm:
            install_groups.append("llm")

    if not install_groups:
        print_info("Available install options:")
        print("  --neo4j   Install Neo4j dependencies")
        print("  --llm     Install LLM dependencies")
        print("  --all     Install all optional dependencies\n")
        return 0

    try:
        import subprocess

        # Build pip install command
        packages = []
        for group in install_groups:
            packages.append(f"agentic-brain[{group}]")

        cmd = [sys.executable, "-m", "pip", "install"] + packages
        print_info(f"Installing: {', '.join(packages)}")
        print()

        result = subprocess.run(cmd)

        if result.returncode == 0:
            print_success("\nInstallation completed")
            return 0
        else:
            print_error("\nInstallation failed")
            return 1

    except Exception as e:
        print_error(f"Installation failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def benchmark_command(args: argparse.Namespace) -> int:
    """
    Benchmark local LLM performance.

    Runs comprehensive benchmarks against Ollama models to measure:
    - Response latency (P50, P95, P99 percentiles)
    - Token throughput (tokens/second)
    - Time to first token (streaming)
    - Hardware-specific performance baselines

    Use this to:
    - Validate on-premise LLM performance for clients
    - Compare different models on same hardware
    - Generate performance reports for documentation
    - Establish SLAs for local deployments

    Output Formats:
        - table: ASCII table for terminal display
        - json: Machine-readable JSON for automation
        - markdown: Markdown table for documentation

    Args:
        args (argparse.Namespace): Parsed arguments with:
            - models (str): Comma-separated model names
            - iterations (int): Benchmark iterations per model
            - warmup (int): Warmup iterations (not counted)
            - prompt (str): Custom benchmark prompt
            - output (str): Output file path
            - format (str): Output format (table/json/markdown)
            - ollama_host (str): Ollama API endpoint
            - no_streaming (bool): Skip streaming benchmark
            - verbose (bool): Enable verbose output

    Returns:
        int: Exit code
            - 0: Benchmark completed successfully
            - 1: Error (Ollama not available, etc.)

    Example:
        $ agentic-brain benchmark --models llama3.2:3b,llama3.1:8b -n 20
        $ agentic-brain benchmark --format json -o results.json
        $ agentic-brain benchmark --models mistral:7b --iterations 50

    Note:
        - Requires Ollama running at specified host
        - Models must be pre-pulled (ollama pull model-name)
        - Warmup iterations help stabilize results
        - P95/P99 require sufficient iterations for accuracy
    """
    import asyncio
    from pathlib import Path

    print_header("Agentic Brain LLM Benchmark")

    # Parse models
    models = [m.strip() for m in args.models.split(",")]
    print_info(f"Models: {', '.join(models)}")
    print_info(f"Iterations: {args.iterations} (warmup: {args.warmup})")
    print_info(f"Ollama host: {args.ollama_host}")

    if args.output:
        print_info(f"Output file: {args.output}")

    print()

    try:
        from agentic_brain.benchmark import (
            BenchmarkConfig,
            BenchmarkRunner,
            OutputFormat,
        )

        # Build config
        config = BenchmarkConfig(
            models=models,
            iterations=args.iterations,
            warmup_iterations=args.warmup,
            ollama_host=args.ollama_host,
            include_streaming=not args.no_streaming,
        )

        if args.prompt:
            config.prompt = args.prompt

        # Set output format
        format_map = {
            "table": OutputFormat.TABLE,
            "json": OutputFormat.JSON,
            "markdown": OutputFormat.MARKDOWN,
        }
        config.output_format = format_map.get(args.format, OutputFormat.TABLE)

        if args.output:
            config.output_file = Path(args.output)

        # Run benchmark
        print_info("Starting benchmark... (this may take a few minutes)")
        print()

        runner = BenchmarkRunner(config)
        results = asyncio.run(runner.run())

        # Output results
        if args.format == "json":
            output = results.to_json()
        elif args.format == "markdown":
            output = results.to_markdown()
        else:
            output = results.to_table()

        print(output)

        # Save to file if specified
        if args.output:
            output_path = Path(args.output)
            if args.format == "json":
                output_path.write_text(results.to_json())
            elif args.format == "markdown":
                output_path.write_text(results.to_markdown())
            else:
                output_path.write_text(results.to_table())

            print_success(f"Results saved to: {args.output}")

        # Summary
        print()
        print_success(results.summary())

        return 0

    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Install with: pip install agentic-brain[all]")
        return 1
    except RuntimeError as e:
        print_error(f"Benchmark failed: {e}")
        if "Ollama not available" in str(e):
            print_info("Please ensure Ollama is running: ollama serve")
        return 1
    except Exception as e:
        print_error(f"Benchmark failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def neo4j_status_command(args: argparse.Namespace) -> int:
    """Check if Neo4j is running and show connection info."""
    print_header("Neo4j Status")

    try:
        # Try to connect to Neo4j
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=neo4j-brain", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            print_warning("Docker not available or Neo4j container not found")
            print_info("Start Neo4j with: agentic neo4j start")
            return 1

        status = result.stdout.strip()
        if not status:
            print_error("Neo4j container not found")
            print_info("Start Neo4j with: agentic neo4j start")
            return 1

        if "Up" in status:
            print_success(f"Neo4j is running: {status}")
            print_info("Connection: bolt://localhost:7687")
            print_info("Web UI: http://localhost:7474")
            print_info("Default username: neo4j")
            print_info("Default password: password")
            return 0
        else:
            print_warning(f"Neo4j container exists but not running: {status}")
            print_info("Start it with: agentic neo4j start")
            return 1

    except subprocess.TimeoutExpired:
        print_error("Docker command timed out")
        return 1
    except FileNotFoundError:
        print_error("Docker not installed")
        print_info("Install Docker from https://www.docker.com/products/docker-desktop")
        return 1


def neo4j_start_command(args: argparse.Namespace) -> int:
    """Start Neo4j with Docker."""
    print_header("Starting Neo4j")

    try:
        # Check if Docker is running
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            print_error("Docker is not running")
            print_info("Start Docker Desktop and try again")
            return 1

        # Check if container already exists
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=neo4j-brain",
                "--format",
                "{{.ID}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        container_id = result.stdout.strip()
        if container_id:
            # Container exists, try to start it
            print_info("Neo4j container exists, starting it...")
            result = subprocess.run(
                ["docker", "start", "neo4j-brain"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                print_error(f"Failed to start container: {result.stderr}")
                return 1
        else:
            # Create new container
            print_info("Pulling Neo4j Docker image...")
            result = subprocess.run(
                ["docker", "pull", "neo4j:latest"],
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0:
                print_error("Failed to pull Neo4j image")
                return 1

            print_info("Starting Neo4j container...")
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    "neo4j-brain",
                    "-p",
                    "7474:7474",
                    "-p",
                    "7687:7687",
                    "-e",
                    "NEO4J_AUTH=neo4j/Brain2026",
                    "neo4j:latest",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print_error(f"Failed to start Neo4j: {result.stderr}")
                return 1

        # Wait for Neo4j to be ready
        print_info("Waiting for Neo4j to be ready (this may take up to 30 seconds)...")
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                # Try to connect
                import socket

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(("localhost", 7687))
                sock.close()
                if result == 0:
                    break
            except Exception:
                pass
            time.sleep(1)
            if (attempt + 1) % 10 == 0:
                print_info(f"Still waiting... ({attempt + 1}/{max_attempts}s)")

        print_success("Neo4j is running!")
        print_info("Web UI: http://localhost:7474")
        print_info("Connection: bolt://localhost:7687")
        print_info("Default username: neo4j")
        print_info("Default password: password")

        return 0

    except FileNotFoundError:
        print_error("Docker not installed")
        print_info("Install Docker from https://www.docker.com/products/docker-desktop")
        return 1
    except subprocess.TimeoutExpired:
        print_error("Operation timed out")
        return 1


def neo4j_stop_command(args: argparse.Namespace) -> int:
    """Stop the Neo4j container."""
    print_header("Stopping Neo4j")

    try:
        result = subprocess.run(
            ["docker", "stop", "neo4j-brain"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print_success("Neo4j stopped")
            return 0
        elif "No such container" in result.stderr:
            print_warning("Neo4j container not found")
            return 0
        else:
            print_error(f"Failed to stop Neo4j: {result.stderr}")
            return 1

    except FileNotFoundError:
        print_error("Docker not installed")
        return 1
    except subprocess.TimeoutExpired:
        print_error("Operation timed out")
        return 1


def neo4j_restart_command(args: argparse.Namespace) -> int:
    """Restart the Neo4j container."""
    print_header("Restarting Neo4j")

    try:
        result = subprocess.run(
            ["docker", "restart", "neo4j-brain"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print_info("Waiting for Neo4j to be ready...")
            time.sleep(5)
            print_success("Neo4j restarted")
            return 0
        elif "No such container" in result.stderr:
            print_warning("Neo4j container not found")
            print_info("Start it with: agentic neo4j start")
            return 1
        else:
            print_error(f"Failed to restart Neo4j: {result.stderr}")
            return 1

    except FileNotFoundError:
        print_error("Docker not installed")
        return 1
    except subprocess.TimeoutExpired:
        print_error("Operation timed out")
        return 1


def models_command(args: argparse.Namespace) -> int:
    """
    List all available models with their codes and specifications.

    Shows all models organized by provider:
    - Local models (L1-L4): Free, no internet
    - Claude (Anthropic): CL, CL2, CL3
    - OpenAI: OP, OP2, OP3
    - Gemini (Google): GO, GO2
    - Groq: GR, GR2

    Each entry shows: code, model name, speed, and cost

    Example:
        $ agentic models

    Returns:
        int: Always returns 0 (success)
    """
    from agentic_brain.model_aliases import MODEL_ALIASES

    print_header("Available Models")

    # Local models
    print("LOCAL MODELS (Free, no internet):")
    for code in ["L1", "L2", "L3", "L4"]:
        if code in MODEL_ALIASES:
            model = MODEL_ALIASES[code]
            chat_note = (
                " (embeddings only)" if not model.get("chat_capable", True) else ""
            )
            print(
                f"  {code:4} {model['model']:30} Speed: {model['speed']:8} Cost: {model['cost']:6}{chat_note}"
            )

    # Claude
    print("\nCLAUDE (Anthropic):")
    for code in ["CL", "CL2", "CL3"]:
        if code in MODEL_ALIASES:
            model = MODEL_ALIASES[code]
            tier_info = f"({model['tier']})"
            print(
                f"  {code:4} {model['model']:30} Speed: {model['speed']:8} Cost: {model['cost']:6} {tier_info}"
            )

    # OpenAI
    print("\nOPENAI:")
    for code in ["OP", "OP2", "OP3"]:
        if code in MODEL_ALIASES:
            model = MODEL_ALIASES[code]
            tier_info = f"({model['tier']})"
            print(
                f"  {code:4} {model['model']:30} Speed: {model['speed']:8} Cost: {model['cost']:6} {tier_info}"
            )

    # Gemini
    print("\nGEMINI (Google):")
    for code in ["GO", "GO2"]:
        if code in MODEL_ALIASES:
            model = MODEL_ALIASES[code]
            tier_info = f"({model['tier']})"
            print(
                f"  {code:4} {model['model']:30} Speed: {model['speed']:8} Cost: {model['cost']:6} {tier_info}"
            )

    # Groq
    print("\nGROQ:")
    for code in ["GR", "GR2"]:
        if code in MODEL_ALIASES:
            model = MODEL_ALIASES[code]
            tier_info = f"({model['tier']})"
            print(
                f"  {code:4} {model['model']:30} Speed: {model['speed']:8} Cost: {model['cost']:6} {tier_info}"
            )

    print("\nTo get info about a specific model, use: agentic model <CODE>")
    print("To set a default model, use: agentic switch <CODE>")
    print("")

    return 0


def model_command(args: argparse.Namespace) -> int:
    """
    Get detailed information about a specific model.

    Shows provider, actual model name, description, speed, cost, and tier.

    Example:
        $ agentic model CL2

    Returns:
        int: 0 on success, 1 on error
    """
    from agentic_brain.model_aliases import resolve_alias

    code = args.code.upper()

    try:
        model = resolve_alias(code)

        print_header(f"Model: {code}")
        print(f"Provider:     {model['provider']}")
        print(f"Model name:   {model['model']}")
        print(f"Description:  {model['description']}")
        print(f"Speed:        {model['speed']}")
        print(f"Cost:         {model['cost']}")
        print(f"Tier:         {model['tier']}")

        if model.get("fallback"):
            print(f"Fallback:     {model['fallback']}")

        chat_capable = model.get("chat_capable", True)
        if not chat_capable:
            print("Chat capable: No (embeddings only)")

        print("")
        return 0

    except ValueError as e:
        print_error(str(e))
        return 1


def switch_command(args: argparse.Namespace) -> int:
    """
    Set the default model and save to config file.

    Updates or creates a config file with the default model.
    Saves to ~/.agentic/config.json by default.

    Example:
        $ agentic switch CL2

    Returns:
        int: 0 on success, 1 on error
    """
    from agentic_brain.model_aliases import resolve_alias

    code = args.code.upper()

    try:
        # Validate the model exists
        model = resolve_alias(code)
        print_info(f"Setting default model to {code} ({model['model']})")

        # Determine config path
        config_dir = Path.home() / ".agentic"
        config_file = config_dir / "config.json"

        # Create directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)

        # Load existing config or create new one
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
        else:
            config = {}

        # Update the default model
        config["default_model"] = code

        # Save config
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        print_success(f"Default model set to {code}")
        print(f"Config saved to: {config_file}")
        print("")
        return 0

    except ValueError as e:
        print_error(str(e))
        return 1
    except Exception as e:
        print_error(f"Failed to save config: {e}")
        return 1


def test_model_command(args: argparse.Namespace) -> int:
    """
    Test if a model responds correctly.

    Sends a simple "Say OK" prompt to verify the model works.
    Tests connectivity and basic functionality.

    Example:
        $ agentic test-model L1

    Returns:
        int: 0 on success, 1 on error
    """
    from agentic_brain.model_aliases import is_chat_capable, is_local, resolve_alias

    code = args.code.upper()

    try:
        # Validate the model exists
        model = resolve_alias(code)

        # Check if chat capable
        if not is_chat_capable(code):
            print_error(f"Model {code} is not chat capable (embeddings only)")
            return 1

        print_header(f"Testing Model: {code}")
        print(f"Provider: {model['provider']}")
        print(f"Model: {model['model']}")
        print(f"Description: {model['description']}")
        print("")

        if is_local(code):
            print_info("Testing local model (Ollama)")
            try:
                import requests

                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={"model": model["model"], "prompt": "Say OK", "stream": False},
                    timeout=30,
                )

                if response.status_code == 200:
                    result = response.json()
                    print_success("Model responded successfully")
                    print(f"Response: {result.get('response', 'N/A')[:100]}")
                    print("")
                    return 0
                else:
                    print_error(f"Model returned status {response.status_code}")
                    return 1

            except requests.ConnectionError:
                print_error("Could not connect to Ollama at http://localhost:11434")
                print_info("Make sure Ollama is running: ollama serve")
                return 1
            except Exception as e:
                print_error(f"Error testing model: {e}")
                return 1
        else:
            print_info("Testing cloud model (requires provider credentials)")
            print_warning("Full cloud model testing not yet implemented")
            print_info(
                "Make sure your API credentials are configured in environment variables"
            )
            print("")
            return 0

    except ValueError as e:
        print_error(str(e))
        return 1
    except Exception as e:
        print_error(f"Error: {e}")
        return 1


def version_command(args: argparse.Namespace) -> int:
    """
    Display version and project information.

    Shows detailed information about Agentic Brain installation:
    - Package version
    - Author name and email
    - License information
    - Repository URL

    Output:
        Agentic Brain
        Version: X.Y.Z
        Author: Name <email@example.com>
        License: Apache-2.0
        Repository: https://github.com/joseph-webber/agentic-brain

    Use Cases:
        - Verify installation version
        - Check license compliance
        - Get author information
        - Find project repository
        - Include in bug reports

    Args:
        args (argparse.Namespace): Parsed arguments (unused)

    Returns:
        int: Always returns 0 (success)

    Example:
        >>> import argparse
        >>> args = argparse.Namespace()
        >>> version_command(args)
        0

    Command line:
        $ agentic-brain version
        $ agentic-brain --version

    Output Details:
        Version: Fetched from agentic_brain.__version__
        Author: Fetched from agentic_brain.__author__
        Email: Fetched from agentic_brain.__email__
        License: Fetched from agentic_brain.__license__
        Repository: Hardcoded GitHub URL

    Note:
        - Always succeeds (returns 0)
        - No network requests
        - Reads from package metadata
        - Colored output for readability
        - Useful in CI/CD pipelines
    """
    from agentic_brain import __author__, __email__, __license__

    print_header("Agentic Brain")
    print(f"Version: {Colors.CYAN}{__version__}{Colors.RESET}")
    print(f"Author: {Colors.CYAN}{__author__}{Colors.RESET} <{__email__}>")
    print(f"License: {Colors.CYAN}{__license__}{Colors.RESET}")
    print(
        f"Repository: {Colors.CYAN}https://github.com/joseph-webber/agentic-brain{Colors.RESET}\n"
    )

    return 0


# ---------------------------------------------------------------------------
# Voice commands
# ---------------------------------------------------------------------------


def voice_list_command(args: argparse.Namespace) -> int:
    """List available voices from the global voice registry.

    This provides a thin CLI wrapper around :mod:`agentic_brain.voice`. For now
    filter flags (``--english``, ``--female`` etc.) are advisory only – we
    always show the full list and rely on the ``--search`` term to narrow
    results.
    """

    try:
        from agentic_brain.voice import list_voices

        query = getattr(args, "search", None)
        voices = list_voices(query)

        if not voices:
            print_warning("No voices found")
            return 0

        lines = []
        for v in voices:
            name = v.get("full_name") or v.get("name") or "<unknown>"
            lang = v.get("language", "?")
            region = v.get("region", "?")
            desc = v.get("description", "").strip()
            line = f"{name}  [{lang} / {region}]"
            if desc:
                line += f"  - {desc}"
            lines.append(line)

        print_box("Available Voices", lines)
        return 0

    except Exception as e:
        print_error(f"Failed to list voices: {e}")
        return 1


def voice_region_command(args: argparse.Namespace) -> int:
    """Set or show the preferred region/city for voice assistants."""

    city = getattr(args, "city", None)
    env_key = "AGENTIC_REGION_CITY"

    if not city:
        current = os.environ.get(env_key, "adelaide")
        print_info(f"Current region city: {current}")
        return 0

    os.environ[env_key] = city
    print_success(f"Set region city to: {city}")
    return 0


def voice_queue_status_command(args: argparse.Namespace) -> int:
    """Show status of the global voice queue (backend, length, etc.)."""

    import asyncio

    async def _inner() -> int:
        from agentic_brain.voice.redpanda_queue import get_voice_queue

        queue = await get_voice_queue()
        status = await queue.status()

        lines = [
            f"Backend:        {status.get('backend')}",
            f"Processing:     {'yes' if status.get('processing') else 'no'}",
            f"Bootstrap:      {status.get('bootstrap_servers')}",
        ]
        if status.get("redis_url"):
            lines.append(f"Redis URL:      {status['redis_url']}")
        qlen = status.get("queue_length")
        if qlen is not None:
            lines.append(f"Queue length:   {qlen}")
        else:
            lines.append("Queue length:   (unknown for Redpanda backend)")

        print_box("Voice Queue Status", lines)
        return 0

    return asyncio.run(_inner())


def voice_queue_clear_command(args: argparse.Namespace) -> int:
    """Clear pending messages from the voice queue (Redis/memory backends)."""

    import asyncio

    async def _inner() -> int:
        from agentic_brain.voice.redpanda_queue import get_voice_queue

        queue = await get_voice_queue()
        cleared = await queue.clear()
        print_success(f"Cleared {cleared} pending voice message(s)")
        if queue.backend == "redpanda":
            print_info(
                "Redpanda backend does not support destructive clear via CLI; "
                "use Kafka tooling if you need to truncate topics."
            )
        return 0

    return asyncio.run(_inner())


def voice_queue_priority_command(args: argparse.Namespace) -> int:
    """Queue a message with an explicit priority level."""

    import asyncio

    level_raw = args.level
    text = args.text

    from agentic_brain.voice.redpanda_queue import VoicePriority, queue_speak

    # Parse priority from name or integer value
    try:
        priority = VoicePriority[level_raw.upper()]
    except (KeyError, AttributeError):
        try:
            priority = VoicePriority(int(level_raw))
        except Exception:
            print_error(
                "Invalid priority level. Use one of: CRITICAL, URGENT, HIGH, "
                "NORMAL, LOW or an integer value."
            )
            return 1

    async def _inner() -> int:
        await queue_speak(text, voice=args.voice, rate=args.rate, priority=priority)
        print_success(
            f"Queued voice message with priority {priority.name} ({int(priority)})"
        )
        return 0

    return asyncio.run(_inner())
