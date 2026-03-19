"""
Agentic Brain CLI Commands
==========================

Implementation of CLI commands for agentic-brain.

Copyright (C) 2026 Joseph Webber
License: GPL-3.0-or-later
"""

import sys
import os
import argparse
import getpass
from pathlib import Path
from typing import Optional

from agentic_brain import __version__


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


def chat_command(args: argparse.Namespace) -> int:
    """
    Start an interactive chat session.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
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
                    os.system("clear" if os.name == "posix" else "cls")
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
    Start the API server.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    print_header("Starting Agentic Brain API Server")
    print(f"Version: {__version__}")
    print(f"Host: {Colors.CYAN}{args.host}{Colors.RESET}")
    print(f"Port: {Colors.CYAN}{args.port}{Colors.RESET}")
    print(f"Workers: {Colors.CYAN}{args.workers}{Colors.RESET}")

    if args.reload:
        print_warning("Auto-reload enabled (development mode)")

    try:
        import uvicorn
        from agentic_brain.api import create_app

        # Create FastAPI app
        app = create_app()
        print_success("API app created")

        # Run server
        print_info(f"Server starting at http://{args.host}:{args.port}\n")
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            workers=1 if args.reload else args.workers,
            reload=args.reload,
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
    Initialize a new agentic-brain project.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
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
        pyproject_content = f'''[project]
name = "{args.name}"
version = "0.1.0"
description = "Agentic brain project"
requires-python = ">=3.9"
license = {{text = "GPL-3.0-or-later"}}
authors = [
    {{name = "Your Name", email = "your.email@example.com"}}
]

dependencies = [
    "agentic-brain[all]>={__version__}",
]

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"
'''
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

GPL-3.0-or-later
"""
        (project_path / "README.md").write_text(readme_content)

        # Initialize git if requested
        if not args.skip_git:
            print_info("Initializing git repository...")
            os.system(f"cd {project_path} && git init > /dev/null 2>&1")
            print_success("Git repository initialized")

        print_success(f"Project created at: {Colors.CYAN}{project_path}{Colors.RESET}")
        print_info(f"Next steps:")
        print(f"  cd {project_path}")
        print(f"  pip install -e .")
        print(f"  cp .env.example .env")
        print(f"  # Edit .env with your configuration")
        print(f"  python -m agentic_brain.cli chat\n")

        return 0

    except Exception as e:
        print_error(f"Project initialization failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def schema_command(args: argparse.Namespace) -> int:
    """
    Apply or verify Neo4j schema.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    print_header("Neo4j Schema Management")
    print(f"URI: {Colors.CYAN}{args.uri}{Colors.RESET}")
    print(f"User: {Colors.CYAN}{args.username}{Colors.RESET}")

    try:
        from neo4j import GraphDatabase

        # Get password if not provided
        password = args.password
        if not password:
            password = getpass.getpass("Neo4j Password: ")

        # Connect to Neo4j
        print_info("Connecting to Neo4j...")
        driver = GraphDatabase.driver(args.uri, auth=(args.username, password))

        with driver.session() as session:
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

        driver.close()
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
    Run the installer.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
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


def version_command(args: argparse.Namespace) -> int:
    """
    Show version information.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    from agentic_brain import __author__, __email__, __license__

    print_header("Agentic Brain")
    print(f"Version: {Colors.CYAN}{__version__}{Colors.RESET}")
    print(f"Author: {Colors.CYAN}{__author__}{Colors.RESET} <{__email__}>")
    print(f"License: {Colors.CYAN}{__license__}{Colors.RESET}")
    print(f"Repository: {Colors.CYAN}https://github.com/joseph-webber/agentic-brain{Colors.RESET}\n")

    return 0
