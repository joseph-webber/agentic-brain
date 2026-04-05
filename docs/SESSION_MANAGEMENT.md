# Session Management

> **Canonical module**: `agentic_brain.memory.session_manager`

This document describes the unified session management system for agentic-brain, consolidating best patterns from multiple implementations.

---

## Overview

The session management module provides:

- **Neo4j-preferred persistence** with SQLite fallback
- **Context window management** with token awareness
- **Memory summarization/compression** (Mem0-inspired)
- **Cross-session continuity**
- **Optional Redis caching layer**
- **Entity extraction and linking**
- **Importance-based retention** with time decay

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      SESSION MANAGER                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Session   │    │   Memory    │    │    Cache    │        │
│  │   Context   │───▶│   Backend   │◀───│   (Redis)   │        │
│  │  (in-mem)   │    │ (Neo4j/SQL) │    │  (optional) │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│         │                  │                  │                │
│         ▼                  ▼                  ▼                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                   UNIFIED API                           │  │
│  │  create_session() | get_context() | recall() | end()    │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Basic Usage

```python
from agentic_brain.memory import SessionManager

# Create manager (auto-detects Neo4j, falls back to SQLite)
manager = SessionManager()

# Create a session
session = await manager.create_session()

# Add messages
await session.add_message("user", "What's the status of SD-1350?")
await session.add_message("assistant", "SD-1350 is currently in review.")

# Get context for LLM (token-aware)
context = await session.get_context(max_tokens=4000)

# End session (generates summary, persists)
summary = await session.end()
```

### Cross-Session Recall

```python
# In a new session, recall what was discussed before
manager = SessionManager()
recent = await manager.get_recent_context(hours=24)

# Search across all sessions
results = await manager.search("SD-1350")
```

### With Redis Caching

```python
from agentic_brain.memory import SessionManager, SessionConfig

config = SessionConfig(
    use_redis_cache=True,
    redis_url="redis://localhost:6379"
)
manager = SessionManager(config=config)
```

## Configuration

```python
from agentic_brain.memory import SessionConfig

config = SessionConfig(
    # Context window
    max_context_tokens=8000,
    
    # Auto-summarization
    summarize_threshold=50,  # Messages before compression
    
    # Importance scoring keywords
    importance_keywords=[
        "important", "critical", "remember", 
        "decision", "agreed", "deadline"
    ],
    
    # Entity extraction patterns
    entity_patterns=[
        r"(?:SD|CITB|PR)-\d+",  # JIRA tickets
        r"@\w+",                 # Mentions
        r"[A-Z][a-z]+ [A-Z][a-z]+",  # Names
    ],
    
    # Memory decay (Mem0-inspired)
    decay_rate=0.01,  # Importance lost per day
    
    # Redis caching
    use_redis_cache=False,
    redis_url="redis://localhost:6379"
)
```

## Components

### SessionMessage

Represents a single message in a session:

```python
@dataclass
class SessionMessage:
    id: str
    role: MessageRole  # user, assistant, system, tool
    content: str
    timestamp: datetime
    session_id: str
    metadata: dict[str, Any]
    entities: list[dict[str, str]]
    importance: float  # 0.0-1.0
    access_count: int  # Reinforcement
    token_count: int
    
    @property
    def effective_importance(self) -> float:
        """Importance with time decay applied."""
        ...
```

### Session

Active conversation session:

```python
class Session:
    async def add_message(role, content, metadata=None) -> SessionMessage
    async def get_context(max_tokens=None) -> list[dict]
    async def recall(query, limit=5) -> list[SessionMessage]
    async def end() -> SessionSummary
```

### SessionManager

Factory and manager for sessions:

```python
class SessionManager:
    async def create_session(session_id=None) -> Session
    async def get_session(session_id) -> Session | None
    async def get_recent_context(hours=24) -> list[SessionMessage]
    async def search(query, limit=10) -> list[SessionMessage]
```

## Storage Backends

### Neo4j (Preferred)

Graph structure:
```cypher
(:SessionMessage {
    id, role, content, timestamp,
    session_id, importance, access_count,
    metadata, entities_json
})

(:SessionSummary {
    id, session_id, content, message_count,
    start_time, end_time, topics_json,
    entities_json, key_facts_json
})
```

Indexes created automatically:
- `session_msg_id` - unique constraint
- `session_msg_time` - timestamp index
- `session_msg_session` - session_id index

### SQLite (Fallback)

Used when Neo4j is unavailable:
- Location: `~/.agentic_brain/sessions.db`
- Full-text search via FTS5
- Zero external dependencies

## Memory Patterns

### Importance Scoring

Messages are scored based on:
- Keywords (important, critical, decision, etc.)
- Questions (likely need follow-up)
- Code blocks (technical context)

```python
# Example importance calculation
base = 0.5
if "important" in content.lower():
    importance += 0.1
if "?" in content:
    importance += 0.05
if "```" in content:
    importance += 0.1
```

### Time Decay (Mem0-inspired)

Importance decays over time unless reinforced by access:

```python
effective_importance = base_importance * exp(-decay_rate * days) + reinforcement
```

Where:
- `decay_rate = 0.01` (1% per day)
- `reinforcement = min(access_count * 0.02, 0.2)`

### Context Compression

When message count exceeds `summarize_threshold`:
1. Keep last 20 messages in full
2. Summarize older messages
3. Extract topics and entities
4. Store summary for future recall

## Migration Guide

### From `neo4j_memory.ConversationMemory`

```python
# Old
from agentic_brain.memory.neo4j_memory import ConversationMemory
memory = ConversationMemory(session_id="xyz")
await memory.add_message("user", "Hello")

# New
from agentic_brain.memory import SessionManager
manager = SessionManager()
session = await manager.create_session("xyz")
await session.add_message("user", "Hello")
```

### From `unified.UnifiedMemory`

```python
# Old
from agentic_brain.memory import UnifiedMemory
mem = UnifiedMemory()
mem.store("Hello")

# New
from agentic_brain.memory import SessionManager
manager = SessionManager()
session = await manager.create_session()
await session.add_message("user", "Hello")
```

### From `core/hooks/ultimate_memory_hooks`

The MCP server (`mcp-servers/memory-hooks/server.py`) continues to work unchanged. Internally it can be updated to use SessionManager:

```python
# In memory-hooks/server.py
from agentic_brain.memory import get_session_manager

def get_memory_hooks():
    return get_session_manager()
```

## Backwards Compatibility

The existing exports in `agentic_brain.memory.__init__.py` remain unchanged:

- `ConversationMemory` - Still available
- `UnifiedMemory` - Still available  
- `Neo4jMemory` - Still available
- `UnifiedSummarizer` - Still available

New exports added:
- `SessionManager`
- `Session`
- `SessionMessage`
- `SessionSummary`
- `SessionConfig`
- `get_session_manager`

## Best Practices

### 1. Use the Manager

Always use `SessionManager` rather than backends directly:

```python
# Good
manager = SessionManager()
session = await manager.create_session()

# Avoid
backend = Neo4jSessionBackend()
```

### 2. End Sessions Properly

Always end sessions to generate summaries:

```python
try:
    session = await manager.create_session()
    # ... conversation ...
finally:
    await session.end()
```

### 3. Recall Before Starting

For continuity, recall recent context on session start:

```python
manager = SessionManager()
recent = await manager.get_recent_context(hours=24)
# Inject relevant context into system prompt
```

### 4. Use Importance Keywords

Add important messages with keywords:

```python
# This will have higher importance
await session.add_message("user", "IMPORTANT: The deadline is Friday")
```

## Testing

```bash
# Run session tests
pytest tests/test_memory_session.py -v

# Test with Neo4j
NEO4J_URI=bolt://localhost:7687 pytest tests/test_memory_session.py -v

# Test SQLite fallback
pytest tests/test_memory_session.py -v --no-neo4j
```

## See Also

- [MEMORY.md](./MEMORY.md) - Full memory architecture
- [NEO4J_ARCHITECTURE.md](./NEO4J_ARCHITECTURE.md) - Neo4j patterns
- [RAG_GUIDE.md](./RAG_GUIDE.md) - Retrieval patterns
