# Agentic Brain CLI

Complete command-line interface for the agentic-brain project with six essential commands for managing AI agents, chat sessions, and deployment.

## Installation

The CLI is included with agentic-brain. Install the package:

```bash
pip install agentic-brain[all]
```

## Usage

### Running Commands

Commands can be invoked via Python module:

```bash
python -m agentic_brain.cli <command> [options]
```

Or if installed as a script:

```bash
agentic <command> [options]
```

## Commands

### 1. Chat - Interactive Chat Session

Start an interactive chat session with the AI agent:

```bash
python -m agentic_brain.cli chat [options]
```

**Options:**
- `--model MODEL` - LLM model to use (default: gpt-4)
- `--agent-name NAME` - Name of the agent (default: assistant)
- `--history FILE` - Load chat history from file
- `--no-memory` - Disable Neo4j memory integration
- `-v, --verbose` - Enable verbose output

**Example:**
```bash
python -m agentic_brain.cli chat --model gpt-4 --agent-name my-agent
```

**Features:**
- Interactive REPL-style interface
- Persistent memory with Neo4j (when enabled)
- Command history
- Help system (`help` command)
- Clear screen (`clear` command)

### 2. Serve - Start API Server

Start the REST API server:

```bash
python -m agentic_brain.cli serve [options]
```

**Options:**
- `--host HOST` - Server host (default: 127.0.0.1)
- `--port PORT` - Server port (default: 8000)
- `--workers WORKERS` - Number of worker processes (default: 4)
- `--reload` - Enable auto-reload on file changes (development mode)
- `-v, --verbose` - Enable verbose output

**Examples:**
```bash
# Production server
python -m agentic_brain.cli serve --host 0.0.0.0 --port 8000 --workers 4

# Development with auto-reload
python -m agentic_brain.cli serve --port 8000 --reload
```

**Server Endpoints:**
- `POST /chat` - Send message to agent
- `GET /status` - Server health check
- `GET /docs` - API documentation (Swagger)

### 3. Init - Initialize New Project

Create a new agentic-brain project with scaffolding:

```bash
python -m agentic_brain.cli init --name <project-name> [options]
```

**Options:**
- `--name NAME` - Project name (required)
- `--path PATH` - Path to create project (default: current directory)
- `--skip-git` - Skip git initialization

**Example:**
```bash
python -m agentic_brain.cli init --name my-agent-project
```

**Generated Files:**
- `src/<project>/` - Python package
- `tests/` - Test directory
- `data/` - Data directory
- `config/` - Configuration directory
- `pyproject.toml` - Project configuration
- `.env.example` - Environment variables template
- `README.md` - Project documentation

### 4. Schema - Apply/Verify Neo4j Schema

Apply or verify the Neo4j database schema:

```bash
python -m agentic_brain.cli schema [options]
```

**Options:**
- `--uri URI` - Neo4j connection URI (default: bolt://localhost:7687)
- `--username USERNAME` - Neo4j username (default: neo4j)
- `--password PASSWORD` - Neo4j password (prompted if not provided)
- `--verify-only` - Verify schema without making changes
- `-v, --verbose` - Enable verbose output

**Examples:**
```bash
# Apply schema
python -m agentic_brain.cli schema --uri bolt://localhost:7687

# Verify schema without changes
python -m agentic_brain.cli schema --verify-only

# Use custom connection
python -m agentic_brain.cli schema --uri bolt://neo4j.example.com:7687 --username admin
```

**Schema Components:**
- Entity constraints
- Relationship types
- Indexes for performance
- Database statistics

### 5. Install - Run Installer

Install optional dependencies:

```bash
python -m agentic_brain.cli install [options]
```

**Options:**
- `--neo4j` - Install Neo4j dependencies
- `--llm` - Install LLM dependencies (OpenAI, etc.)
- `--all` - Install all optional dependencies
- `-v, --verbose` - Enable verbose output

**Examples:**
```bash
# Install all dependencies
python -m agentic_brain.cli install --all

# Install only LLM support
python -m agentic_brain.cli install --llm

# Install only Neo4j support
python -m agentic_brain.cli install --neo4j
```

**Installed Packages:**
- **LLM**: openai, httpx
- **Neo4j**: neo4j

### 6. Version - Show Version Information

Display version and project information:

```bash
python -m agentic_brain.cli version
```

**Output:**
- Version number
- Author information
- License type
- Repository URL

## Global Options

Available for all commands:

- `-h, --help` - Show help message for command
- `-v, --verbose` - Enable verbose output (shows full tracebacks on errors)
- `--version` - Show version and exit (main CLI only)

## Output Formatting

The CLI provides colored output when the terminal supports it:

- **Colors automatically disabled** if:
  - `TERM=dumb` environment variable is set
  - `NO_COLOR` environment variable is set
  - Terminal is not a TTY (e.g., piped output)

- **Force colors** with `FORCE_COLOR=1`:
  ```bash
  FORCE_COLOR=1 python -m agentic_brain.cli chat
  ```

## Environment Configuration

### Chat Command
```bash
# Load from .env file
export OPENAI_API_KEY=sk-...
export NEO4J_URI=bolt://localhost:7687
python -m agentic_brain.cli chat
```

### Serve Command
```bash
# Server environment
export HOST=0.0.0.0
export PORT=8000
python -m agentic_brain.cli serve
```

### Schema Command
```bash
# Neo4j environment
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password
python -m agentic_brain.cli schema
```

## Error Handling

### Verbose Mode
For detailed error information, use the `-v` or `--verbose` flag:

```bash
python -m agentic_brain.cli chat --verbose
```

This shows full Python tracebacks instead of just error messages.

### Common Errors

**Neo4j Connection Failed**
```
Error: Could not connect to Neo4j at bolt://localhost:7687
Solution: Ensure Neo4j is running and connection details are correct
```

**Missing Dependencies**
```
Error: Required dependency not installed: openai
Solution: Run: pip install agentic-brain[all]
```

**Port Already in Use**
```
Error: Address already in use
Solution: Use a different port: --port 8001
```

## Examples

### Quick Start

```bash
# 1. Initialize a new project
python -m agentic_brain.cli init --name my-agent

# 2. Change to project directory
cd my-agent

# 3. Install dependencies
pip install -e .

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Start chatting
python -m agentic_brain.cli chat
```

### Development Workflow

```bash
# Start development server with auto-reload
python -m agentic_brain.cli serve --reload --port 8000

# In another terminal, test chat
python -m agentic_brain.cli chat --model gpt-4
```

### Production Deployment

```bash
# Apply schema to production database
python -m agentic_brain.cli schema \
  --uri bolt://prod-db.example.com:7687 \
  --username prod_user \
  --password prod_password

# Start production server
python -m agentic_brain.cli serve \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 8
```

## Architecture

The CLI consists of three modules:

### `__init__.py`
- Main CLI entry point using argparse
- Color-aware formatter for help text
- Argument parsing and command routing
- Global error handling

### `commands.py`
- Individual command implementations
- Color output utilities
- Helper functions for each command
- Error handling and messaging

### `__main__.py`
- Module entry point for `python -m agentic_brain.cli`
- Enables direct execution

## License

GPL-3.0-or-later, Copyright 2026 Joseph Webber

## Support

For issues or questions:
- GitHub Issues: https://github.com/joseph-webber/agentic-brain/issues
- Documentation: https://github.com/joseph-webber/agentic-brain#readme
