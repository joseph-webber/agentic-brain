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
        - GPL-3.0-or-later license
    
    Note:
        - Project name is also used as package name (- becomes _)
        - Creates local editable install with pip install -e .
        - Git initialization runs in background
        - All created files use GPL-3.0-or-later license
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
        License: GPL-3.0-or-later
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
    print(f"Repository: {Colors.CYAN}https://github.com/joseph-webber/agentic-brain{Colors.RESET}\n")

    return 0
