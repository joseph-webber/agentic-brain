# Agentic Brain - Claude/Copilot Instructions

This file provides context for AI assistants working on this codebase.

---

## Project Overview

**Agentic Brain** is an open-source AI brain infrastructure with:
- FastAPI backend with Neo4j graph database
- MCP (Model Context Protocol) server for tool integration
- Real-time event bus (Redpanda/Kafka)
- Voice synthesis and accessibility features

---

## 🔑 API Keys Setup

Store keys in `.env` file (NEVER commit actual values!):

```bash
# Required
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Optional LLM APIs
OPENAI_API_KEY=sk-...
CLAUDE_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...          # Fast inference (500 tok/s)
GEMINI_API_KEY=...
XAI_API_KEY=...

# Optional Services
JIRA_API_TOKEN=...
GITHUB_TOKEN=ghp_...
CARTESIA_API_KEY=...          # Fast TTS
```

**Local LLMs (FREE, no key needed):**
```bash
# Install Ollama: https://ollama.ai
ollama pull llama3.2:3b    # Fast responses
ollama pull llama3.1:8b    # Quality reasoning
ollama pull nomic-embed-text  # Embeddings
```

---

## Quick Start

```bash
# Start services
docker compose up -d

# Install Python deps
pip install -e ".[dev]"

# Run API server
uvicorn agentic_brain.api:app --reload

# Run MCP server
python -m agentic_brain.mcp.server
```

---

## Code Conventions

- **Python 3.11+** with type hints
- **Lazy loading** for all database connections (see mcp/server.py pattern)
- **Pydantic v2** for models with `json_schema_extra` examples
- **pytest** for testing with `pytest-asyncio`

---

## Key Directories

| Path | Purpose |
|------|---------|
| `src/agentic_brain/api/` | FastAPI routes and models |
| `src/agentic_brain/mcp/` | MCP server for Claude/Copilot |
| `src/agentic_brain/core/` | Neo4j, Redis, core services |
| `tests/` | Pytest test suite |
| `docs/` | API reference, guides |

---

## Performance Tips

1. **MCP servers** - Use lazy imports (not module-level) to avoid blocking
2. **Neo4j** - Use connection pooling via `neo4j_pool.py`
3. **Redis** - Optional caching layer for hot data

---

**License**: MIT  
**Docs**: See `docs/` folder and `INSTALL.md`
