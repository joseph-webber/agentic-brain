"""
Agentic Brain MCP Servers
=========================

Open-source MCP servers for Claude, Copilot, and other AI agents.

## Included Servers

### Core Infrastructure
- **brain-core**: Core brain functionality
- **brain-data**: Data access and querying
- **brain-memory**: Memory management
- **core-data**: Auto-exposed core_data modules as MCP tools
- **event-bus**: Event publishing and subscription

### AI & LLM
- **openrouter**: Multi-provider LLM routing (Groq, Claude, Together, etc.)
- **local-llm**: Local Ollama integration
- **smart-router**: Intelligent LLM provider selection
- **claude-emulator**: Claude emulator for testing

### Apple Integration
- **brain-apple**: Apple system integration with accessibility features

### Database
- **neo4j-backup**: Neo4j backup and restore operations
- **neo4j-unified**: Unified Neo4j query interface

### Tools & Utilities
- **cli-tools**: Command-line tool automation
- **browser-automation**: Browser control and automation
- **archive**: Archive/compression utilities

### Session Management
- **session-continuity**: Session persistence and recovery
- **continuity**: Clock chain-based continuity
- **memory-hooks**: Memory system integration

### Creative
- **music-producer**: Music production and synthesis

## Usage

### Configuration

Add to your `mcp-config.json`:

```json
{
  "mcpServers": {
    "brain-core": {
      "command": "python",
      "args": ["mcp-servers/brain-core/server.py"]
    },
    "openrouter": {
      "command": "python",
      "args": ["mcp-servers/openrouter/server.py"]
    },
    // ... add more servers as needed
  }
}
```

### Environment Variables

Some servers require environment variables:

- **openrouter**: `GROQ_API_KEY`, `TOGETHER_API_KEY`, `OPENROUTER_API_KEY`, `CLAUDE_API_KEY`
- **neo4j-unified**: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- **cli-tools**: May need various tool paths

## Development

Each server is a self-contained Python package with:
- `server.py`: Main MCP server implementation
- `tools/`: Tool implementations (if applicable)
- `requirements.txt`: Python dependencies

### Running a Server Standalone

```bash
cd mcp-servers/brain-core
python server.py
```

### Testing

Each server can be tested by running its server module directly:

```bash
python mcp-servers/openrouter/server.py
```

## Architecture

All servers follow the MCP (Model Context Protocol) standard and use:
- `FastMCP` or standard MCP Server for implementation
- Relative imports where possible to support both brain and agentic-brain roots
- Lazy loading to minimize startup time
- Proper error handling and fallbacks

## Security Notes

- No hardcoded credentials in this repository
- API keys and sensitive data should be provided via environment variables
- Some servers require Neo4j database connectivity
- Some tools require system utilities (e.g., `archive` needs tar/zip)

## License

These servers are part of the Agentic Brain project. See the main repository for license details.
"""

__version__ = "1.0.0"
__all__ = [
    "brain-core",
    "brain-data",
    "brain-memory",
    "core-data",
    "event-bus",
    "openrouter",
    "local-llm",
    "smart-router",
    "claude-emulator",
    "brain-apple",
    "neo4j-backup",
    "neo4j-unified",
    "cli-tools",
    "browser-automation",
    "archive",
    "session-continuity",
    "continuity",
    "memory-hooks",
    "music-producer",
]
