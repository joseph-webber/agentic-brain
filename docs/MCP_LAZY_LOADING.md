# MCP Lazy Loading

`agentic_brain.mcp` must stay cheap to import so MCP discovery and CLI startup do not block on unrelated subsystems.

## Why

In the main `brain` repo, MCP startup delays were caused by module-level imports and connections. The same rule applies here:

- do not create Neo4j, Redis, or HTTP clients at import time
- do not import heavyweight subpackages in `__init__.py` just to re-export names
- only connect when a tool is actually called or the server is explicitly initialized

## Required patterns

### 1. Lazy singleton for connections

```python
_neo4j = None


def get_neo4j():
    global _neo4j
    if _neo4j is None:
        from agentic_brain.core import Neo4jPool

        _neo4j = Neo4jPool()
    return _neo4j
```

Use the same pattern for Redis, event buses, clients, and other network resources.

### 2. Function-level imports for optional or heavy dependencies

```python
def build_rag_pipeline(config):
    from agentic_brain.rag import RAGPipeline

    return RAGPipeline(...)
```

This keeps import-time work minimal and avoids dragging in transitive dependencies for commands that do not need them.

### 3. Lazy package re-exports

`agentic_brain/__init__.py` and `agentic_brain/mcp/__init__.py` now use module `__getattr__()` maps instead of eager `from ... import ...` blocks.

Use this pattern when you want a convenient public API without paying the import cost up front:

```python
_LAZY_EXPORTS = {
    "AgenticMCPServer": ("agentic_brain.mcp.server", "AgenticMCPServer"),
}


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        import importlib

        module_name, attribute_name = _LAZY_EXPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attribute_name)
        globals()[name] = value
        return value
    raise AttributeError(...)
```

## What to avoid

### Bad

```python
from neo4j import GraphDatabase
from agentic_brain.rag import RAGPipeline

driver = GraphDatabase.driver(uri, auth=(user, password))
pipeline = RAGPipeline(...)
```

### Good

```python
_driver = None


def get_driver():
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase

        _driver = GraphDatabase.driver(uri, auth=(user, password))
    return _driver
```

## Current MCP status

- `agentic_brain.mcp.server` keeps Neo4j and memory setup inside initialization methods
- `agentic_brain.mcp.__init__` lazily exposes client, server, tool, and type exports
- `agentic_brain.__init__` no longer imports heavy commerce/audio/router modules during MCP package import
- `agentic_brain.mcp.__main__` defers server import until `main()` runs

## Quick verification

Run these from the repository root:

```bash
time python3 -c "from agentic_brain.mcp import tools"
python3 -X importtime -c "from agentic_brain.mcp import tools" 2>&1 | tail -n 40
pytest tests/test_mcp.py tests/test_imports.py
```

## Rule of thumb

If importing `agentic_brain.mcp` or `from agentic_brain.mcp import tools` causes network access, subprocess startup, or heavyweight package trees to load, treat it as a startup regression and fix it before merging.
