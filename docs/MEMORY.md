# Advanced Brain Memory

<div align="center">

[![Memory](https://img.shields.io/badge/Memory-Neo4j%20%2B%20Vectors-008CC1?style=for-the-badge&logo=neo4j&logoColor=white)](https://neo4j.com)
[![Semantic](https://img.shields.io/badge/Semantic-Embeddings-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white)]()
[![Distributed](https://img.shields.io/badge/Distributed-Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)

**The memory system that makes AI feel intelligent.**

*Cross-session recall • Semantic search • Relationship tracking • Never forget*

</div>

---

## 🧠 Memory Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENTIC BRAIN MEMORY                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │   SESSION   │  │  LONG-TERM  │  │  SEMANTIC   │  │  EPISODIC  │ │
│  │   MEMORY    │  │   MEMORY    │  │   MEMORY    │  │   MEMORY   │ │
│  │             │  │             │  │             │  │            │ │
│  │ Conversation│  │ Neo4j Graph │  │   Vector    │  │   Event    │ │
│  │   Context   │  │  Knowledge  │  │ Embeddings  │  │  Sourcing  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
│         │                │                │               │        │
│         └────────────────┼────────────────┼───────────────┘        │
│                          │                │                        │
│                    ┌─────┴────────────────┴─────┐                  │
│                    │     UNIFIED MEMORY API     │                  │
│                    │   brain.memory.recall()    │                  │
│                    └────────────────────────────┘                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Memory Types

### 1. Session Memory

**In-conversation context** — what happened in this chat session.

```python
from agentic_brain.memory import SessionMemory

session = SessionMemory(session_id="user-123-abc")

# Automatically tracks conversation
await session.add_message({"role": "user", "content": "My name is Alice"})
await session.add_message({"role": "assistant", "content": "Nice to meet you, Alice!"})

# Recall within session
context = session.get_context(last_n=10)  # Last 10 messages
```

**Features:**
- Sliding window context
- Token-aware truncation
- Message importance scoring
- Automatic summarization of old messages

---

### 2. Long-Term Memory (Neo4j Knowledge Graph)

**Persistent knowledge** — facts, relationships, entities across all sessions.

```python
from agentic_brain.memory import LongTermMemory

ltm = LongTermMemory(neo4j_uri="bolt://localhost:7687")

# Store knowledge
await ltm.store_fact(
    subject="Alice",
    predicate="lives_in",
    object="Adelaide",
    confidence=0.95
)

# Store relationships
await ltm.store_relationship(
    entity1="Alice",
    relation="works_at",
    entity2="Enterprise",
    properties={"role": "Developer", "since": "2020"}
)

# Query knowledge
facts = await ltm.query("MATCH (p:Person {name: 'Alice'})-[r]->(n) RETURN p, r, n")
```

**Features:**
- Graph-based knowledge representation
- Entity resolution and deduplication
- Relationship inference
- Temporal versioning (facts change over time)

---

### 3. Semantic Memory (Vector Embeddings)

**Meaning-based recall** — find related memories by semantic similarity.

```python
from agentic_brain.memory import SemanticMemory

semantic = SemanticMemory(
    embedding_model="text-embedding-3-small",
    vector_store="neo4j"  # Or "chroma", "pinecone", "qdrant"
)

# Store with embeddings
await semantic.store(
    text="The user prefers bullet points over paragraphs",
    metadata={"type": "preference", "confidence": 0.9}
)

# Semantic search
results = await semantic.search(
    query="How does the user like information formatted?",
    top_k=5
)
# Returns the preference even though wording is different!
```

**Features:**
- Multiple embedding models (OpenAI, Cohere, local)
- Hybrid search (vector + keyword)
- Clustering similar memories
- Automatic embedding refresh

---

### 4. Episodic Memory (Event Sourcing)

**Time-ordered events** — what happened and when.

```python
from agentic_brain.memory import EpisodicMemory

episodic = EpisodicMemory()

# Events are immutable, append-only
await episodic.record_event(
    event_type="user_action",
    data={"action": "requested_pr_review", "pr": "SD-1350"},
    timestamp=datetime.now()
)

# Replay events for a time period
events = await episodic.get_events(
    start=datetime(2024, 3, 14),
    end=datetime(2024, 3, 15),
    event_types=["user_action", "ai_response"]
)

# Time-travel: reconstruct state at any point
state_at_noon = await episodic.reconstruct_state(
    timestamp=datetime(2024, 3, 14, 12, 0, 0)
)
```

**Features:**
- Immutable event log
- State reconstruction at any point
- Event replay for debugging
- Audit trail for compliance

---

## 🔧 Unified Memory API

All memory types work together through a unified interface:

```python
from agentic_brain import Brain

brain = Brain()

# Store across all memory types automatically
await brain.memory.remember(
    "Alice lives in Adelaide and works as a developer",
    session_id="current"
)
# This will:
# 1. Add to session context
# 2. Extract entities → Neo4j (Alice, Adelaide)
# 3. Generate embeddings → vector store
# 4. Record event → episodic log

# Recall intelligently
memories = await brain.memory.recall(
    query="Where does Alice work?",
    session_id="current",
    include_long_term=True,
    include_semantic=True,
    top_k=5
)
# Combines results from all memory types!
```

---

## 🧹 Forgetting Strategies

Not all memories should last forever. Smart forgetting keeps memory manageable:

### Time-Based Decay

```python
memory_config = {
    "session": {"ttl": "24h"},           # Session memory expires in 24 hours
    "semantic": {"ttl": "30d"},          # Semantic memories decay after 30 days
    "long_term": {"ttl": None},          # Facts persist forever (unless overwritten)
    "episodic": {"ttl": "90d"}           # Events kept for 90 days
}
```

### Importance-Based Retention

```python
# High-importance memories survive longer
await brain.memory.remember(
    "the user's birthday is March 15",
    importance=0.9,  # Will be retained longer
    decay_rate=0.1   # Slow decay
)

await brain.memory.remember(
    "Alice mentioned liking coffee",
    importance=0.3,  # Lower priority
    decay_rate=0.5   # Faster decay
)
```

### Compression

```python
# Compress old memories to save space
await brain.memory.compress(
    older_than="7d",
    strategy="summarize"  # Or "cluster", "prune"
)
```

---

## 🔗 Storage Backends

### Neo4j (Graph Memory)

```python
from agentic_brain.memory.backends import Neo4jBackend

backend = Neo4jBackend(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

# Full Cypher query support
result = await backend.query("""
    MATCH (u:User {name: $name})-[:MENTIONED]->(topic:Topic)
    RETURN topic.name, count(*) as mentions
    ORDER BY mentions DESC
    LIMIT 5
""", {"name": "Alice"})
```

### SQLite (Local Memory)

```python
from agentic_brain.memory.backends import SQLiteBackend

backend = SQLiteBackend(
    path="~/.agentic-brain/memory.db"
)

# Works offline, zero dependencies
# Great for personal use
```

### Redis (Distributed Memory)

```python
from agentic_brain.memory.backends import RedisBackend

backend = RedisBackend(
    url="redis://localhost:6379",
    cluster=True  # For Redis Cluster
)

# Fast, distributed, perfect for multi-instance deployments
# Automatic expiration support
```

---

## 🔄 Cross-Session Recall

The magic of Agentic Brain — memories persist across sessions:

```python
# Session 1 (Monday)
brain.memory.remember("I'm working on the AusPost integration")

# Session 2 (Tuesday) - different session!
context = await brain.memory.recall("What was I working on?")
# Returns: "You were working on the AusPost integration"

# Session 3 (Friday)
context = await brain.memory.recall("AusPost")
# Returns full context about the AusPost work
```

### How It Works

1. **Session ends** → Important memories extracted and scored
2. **Entities identified** → Stored in Neo4j knowledge graph
3. **Embeddings generated** → Stored in vector database
4. **New session starts** → Query all memory types
5. **Context assembled** → Relevant memories injected into prompt

---

## 📊 Memory Dashboard

Monitor memory health and usage:

```bash
# View memory statistics
ab memory stats

# Output:
# ┌─────────────────────────────────────┐
# │         MEMORY STATISTICS           │
# ├─────────────────────────────────────┤
# │ Session Memories:     1,234         │
# │ Long-term Facts:      5,678         │
# │ Semantic Embeddings:  12,345        │
# │ Episodic Events:      45,678        │
# │ Total Storage:        256 MB        │
# │ Last Compression:     2 hours ago   │
# └─────────────────────────────────────┘
```

---

## 🧪 Testing Memory

Memory systems have comprehensive tests:

```bash
# Run memory tests
pytest tests/test_memory*.py -v

# Test specific backend
pytest tests/test_memory_neo4j.py -v
pytest tests/test_memory_redis.py -v

# Test semantic search accuracy
pytest tests/test_memory_semantic.py -v
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| Session Memory | 120+ | 95% |
| Long-term Memory | 150+ | 92% |
| Semantic Memory | 80+ | 90% |
| Episodic Memory | 60+ | 88% |
| Unified API | 100+ | 94% |

---

## 🏗️ Configuration

```yaml
# config/memory.yaml
memory:
  session:
    backend: "sqlite"
    max_messages: 100
    summarize_after: 50
  
  long_term:
    backend: "neo4j"
    uri: "${NEO4J_URI}"
    user: "${NEO4J_USER}"
    password: "${NEO4J_PASSWORD}"
  
  semantic:
    backend: "neo4j"  # Neo4j with vector index
    embedding_model: "text-embedding-3-small"
    dimensions: 1536
  
  episodic:
    backend: "sqlite"
    retention_days: 90
  
  forgetting:
    enabled: true
    compression_schedule: "daily"
    importance_threshold: 0.3
```

---

## 🎯 Why Memory Matters

> "Memory is what separates a chatbot from an AI assistant."

| Without Memory | With Agentic Brain Memory |
|----------------|---------------------------|
| Forgets your name | Remembers everything about you |
| Asks same questions | Builds on past conversations |
| No context | Understands relationships |
| Starts fresh every time | Learns and improves |
| Generic responses | Personalized assistance |

**Memory makes AI feel intelligent.** It's not just about storing data — it's about understanding context, relationships, and meaning across time.

---

## See Also

- [RAG.md](./RAG.md) - Retrieval-Augmented Generation
- [TESTING.md](./TESTING.md) - Testing memory systems
- [NEO4J-HEALTH-GUIDE.md](./NEO4J_ARCHITECTURE.md) - Neo4j best practices
- [SECURITY.md](./SECURITY.md) - Memory encryption and privacy
