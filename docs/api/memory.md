# Memory Module API

Persistent knowledge storage backed by Neo4j graph database with multi-tenant data isolation. Store and retrieve facts, with automatic data scoping for secure multi-user applications.

## Table of Contents
- [Neo4jMemory](#neo4jmemory) - Main memory class
- [DataScope](#datascope) - Isolation scopes
- [Memory](#memory) - Memory entry objects
- [MemoryConfig](#memoryconfig) - Configuration
- [Examples](#examples)

---

## Neo4jMemory

Persistent memory backed by Neo4j with scoped data separation.

### Signature

```python
class Neo4jMemory:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "",
        database: str = "neo4j",
    ) -> None:
        """Initialize Neo4j memory connection."""
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `uri` | `str` | `bolt://localhost:7687` | Neo4j bolt URI |
| `user` | `str` | `neo4j` | Database username |
| `password` | `str` | `""` | Database password |
| `database` | `str` | `neo4j` | Database name |

### Methods

#### `connect()`

Establish connection to Neo4j.

```python
def connect(self) -> bool:
```

**Returns:**
- `bool`: True if connection successful

**Raises:**
- `ImportError`: If neo4j package not installed

**Example:**
```python
memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)
if memory.connect():
    print("Connected to Neo4j")
else:
    print("Connection failed")
```

---

#### `store()`

Store a memory entry.

```python
def store(
    self,
    content: str,
    scope: DataScope = DataScope.PUBLIC,
    customer_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Memory:
```

**Parameters:**
- `content` (str): Memory text to store
- `scope` (DataScope): Isolation scope (PUBLIC, PRIVATE, CUSTOMER)
- `customer_id` (str, optional): Customer ID (required for CUSTOMER scope)
- `metadata` (dict, optional): Additional metadata

**Returns:**
- `Memory`: Stored memory object with ID and timestamp

**Raises:**
- `ValueError`: If CUSTOMER scope without customer_id

**Example:**
```python
memory = Neo4jMemory()
memory.connect()

# Store public knowledge
memory.store("Python is a programming language", scope=DataScope.PUBLIC)

# Store admin notes
memory.store("System is under maintenance", scope=DataScope.PRIVATE)

# Store customer data
memory.store(
    "Customer prefers evening calls",
    scope=DataScope.CUSTOMER,
    customer_id="acme_corp",
    metadata={"preference": "communication"}
)
```

---

#### `search()`

Search memories within a scope.

```python
def search(
    self,
    query: str,
    scope: DataScope = DataScope.PUBLIC,
    customer_id: Optional[str] = None,
    limit: int = 10,
    min_score: float = 0.3
) -> List[Memory]:
```

**Parameters:**
- `query` (str): Search query/keywords
- `scope` (DataScope): Scope to search within
- `customer_id` (str, optional): Customer ID (required for CUSTOMER scope)
- `limit` (int): Max results to return
- `min_score` (float): Minimum relevance score (0-1)

**Returns:**
- `List[Memory]`: Matching memories, ranked by relevance

**Example:**
```python
# Search public knowledge
results = memory.search("Python", scope=DataScope.PUBLIC)

# Search private data (admin only)
results = memory.search("maintenance", scope=DataScope.PRIVATE)

# Search customer data
results = memory.search(
    "preferences",
    scope=DataScope.CUSTOMER,
    customer_id="acme_corp",
    limit=5
)

for mem in results:
    print(f"{mem.content} (score: {mem.metadata.get('score', 0):.2f})")
```

---

#### `get_by_id()`

Retrieve a specific memory by ID.

```python
def get_by_id(self, memory_id: str) -> Optional[Memory]:
```

**Returns:**
- `Memory`: Memory if found, None otherwise

**Example:**
```python
memory = Neo4jMemory()
memory.connect()

# Store and retrieve
stored = memory.store("Important fact")
retrieved = memory.get_by_id(stored.id)
print(retrieved.content)
```

---

#### `delete()`

Delete a memory entry.

```python
def delete(self, memory_id: str) -> bool:
```

**Returns:**
- `bool`: True if deleted, False if not found

**Example:**
```python
memory_id = "mem_12345"
if memory.delete(memory_id):
    print("Deleted")
else:
    print("Not found")
```

---

#### `update()`

Update a memory entry.

```python
def update(
    self,
    memory_id: str,
    content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Memory]:
```

**Example:**
```python
memory = Neo4jMemory()
memory.connect()

stored = memory.store("Old content")
updated = memory.update(stored.id, content="New content")
```

---

#### `clear_scope()`

Delete all memories in a scope.

```python
def clear_scope(
    self,
    scope: DataScope,
    customer_id: Optional[str] = None
) -> int:
```

**Returns:**
- `int`: Number of memories deleted

**Warning:** Use with care - this is permanent!

**Example:**
```python
# Clear all public memories
count = memory.clear_scope(DataScope.PUBLIC)
print(f"Deleted {count} public memories")

# Clear customer data
count = memory.clear_scope(
    DataScope.CUSTOMER,
    customer_id="acme_corp"
)
```

---

#### `get_stats()`

Get storage statistics.

```python
def get_stats(self) -> Dict[str, Any]:
```

**Returns:**
```python
{
    "total_memories": 1000,
    "public": 500,
    "private": 100,
    "customer": 400,
    "size_bytes": 5242880,
    "last_query": "2026-03-20T12:34:56Z"
}
```

---

## DataScope

Enumeration for data isolation scopes.

### Signature

```python
class DataScope(Enum):
    PUBLIC = "public"        # Shared knowledge
    PRIVATE = "private"      # Admin/system data
    CUSTOMER = "customer"    # Per-client isolated
```

### Usage

```python
from agentic_brain import DataScope

# Public knowledge (accessible to all)
memory.store("API documentation", scope=DataScope.PUBLIC)

# Private data (admin only)
memory.store("Database credentials", scope=DataScope.PRIVATE)

# Customer data (isolated per customer)
memory.store(
    "Customer data",
    scope=DataScope.CUSTOMER,
    customer_id="customer_id"
)
```

### Scope Characteristics

| Scope | Accessible | Isolation | Use Case |
|-------|-----------|-----------|----------|
| PUBLIC | Everyone | Shared | Documentation, shared knowledge |
| PRIVATE | Admin only | System-wide | Credentials, internal notes |
| CUSTOMER | That customer only | Per-customer | User preferences, history |

---

## Memory

Individual memory entry.

### Signature

```python
@dataclass
class Memory:
    id: str
    content: str
    scope: DataScope
    timestamp: datetime
    customer_id: Optional[str] = None
    metadata: dict = {}
    embedding: Optional[List[float]] = None
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Unique identifier |
| `content` | `str` | Memory text |
| `scope` | `DataScope` | Isolation scope |
| `timestamp` | `datetime` | Creation time |
| `customer_id` | `str` | Customer ID (if CUSTOMER scope) |
| `metadata` | `dict` | Additional data |
| `embedding` | `List[float]` | Vector embedding (for search) |

### Methods

#### `to_dict()`

Serialize to dictionary.

```python
def to_dict(self) -> Dict[str, Any]:
```

**Example:**
```python
memory = Neo4jMemory()
memory.connect()

stored = memory.store("Important fact")
data = stored.to_dict()

import json
json.dump(data, open("memory.json", "w"))
```

---

## MemoryConfig

Configuration for memory backend.

### Signature

```python
@dataclass
class MemoryConfig:
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    embedding_dim: int = 384
    max_results: int = 10
```

---

## Examples

### Example 1: Basic Storage and Retrieval

```python
from agentic_brain import Neo4jMemory, DataScope

# Connect
memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)
memory.connect()

# Store facts
memory.store(
    "The customer prefers email contact",
    scope=DataScope.CUSTOMER,
    customer_id="customer_123"
)

# Retrieve later
results = memory.search(
    "customer contact",
    scope=DataScope.CUSTOMER,
    customer_id="customer_123"
)

for mem in results:
    print(mem.content)
```

---

### Example 2: Multi-Tenant Application

```python
from agentic_brain import Neo4jMemory, DataScope

memory = Neo4jMemory()
memory.connect()

# Store data for different customers
customers = ["acme_corp", "techstart_inc", "global_solutions"]

for customer in customers:
    memory.store(
        f"{customer} prefers monthly billing",
        scope=DataScope.CUSTOMER,
        customer_id=customer
    )

# Each customer's data is isolated
for customer in customers:
    results = memory.search(
        "billing",
        scope=DataScope.CUSTOMER,
        customer_id=customer
    )
    print(f"{customer}: {results[0].content if results else 'No data'}")
```

---

### Example 3: Knowledge Base

```python
from agentic_brain import Neo4jMemory, DataScope

memory = Neo4jMemory()
memory.connect()

# Build shared knowledge base
docs = [
    "Python is dynamically typed",
    "Python was created in 1991",
    "Python uses indentation for blocks",
    "Python supports multiple programming paradigms",
]

for doc in docs:
    memory.store(doc, scope=DataScope.PUBLIC)

# Anyone can search
results = memory.search("Python", scope=DataScope.PUBLIC, limit=10)
print(f"Found {len(results)} facts about Python")

for mem in results:
    print(f"- {mem.content}")
```

---

### Example 4: Integration with Chatbot

```python
from agentic_brain import Chatbot, Neo4jMemory, DataScope

# Create memory and chatbot
memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    password="password"
)
memory.connect()

bot = Chatbot("support", memory=memory)

# Chat (memory is used automatically)
bot.chat("My name is Alice and I work at Acme Corp")

# Store explicit knowledge
memory.store(
    "Alice is a valued customer",
    scope=DataScope.CUSTOMER,
    customer_id="alice",
    metadata={"importance": "high"}
)

# Bot retrieves context automatically
response = bot.chat("What do you know about me?")
# -> Uses both conversation history and stored memory
```

---

### Example 5: Admin Notes

```python
from agentic_brain import Neo4jMemory, DataScope

memory = Neo4jMemory()
memory.connect()

# Store admin notes (private)
memory.store(
    "System will be down for maintenance 2026-03-25 2:00 AM UTC",
    scope=DataScope.PRIVATE,
    metadata={"category": "maintenance", "duration": "30 minutes"}
)

# Store public documentation
memory.store(
    "Scheduled maintenance notices appear in the dashboard",
    scope=DataScope.PUBLIC
)

# Admin search (private)
admin_results = memory.search("maintenance", scope=DataScope.PRIVATE)
print(f"Admin: {admin_results[0].content if admin_results else 'No notes'}")

# User search (public only)
user_results = memory.search("maintenance", scope=DataScope.PUBLIC)
print(f"User: {user_results[0].content if user_results else 'No info'}")
```

---

### Example 6: Statistics and Cleanup

```python
from agentic_brain import Neo4jMemory, DataScope

memory = Neo4jMemory()
memory.connect()

# Store some data
for i in range(100):
    memory.store(f"Fact {i}", scope=DataScope.PUBLIC)

# Check stats
stats = memory.get_stats()
print(f"Total memories: {stats['total_memories']}")
print(f"Public: {stats['public']}")
print(f"Storage used: {stats['size_bytes'] / 1024 / 1024:.1f} MB")

# Clean up customer data (e.g., after account closure)
deleted = memory.clear_scope(DataScope.CUSTOMER, customer_id="old_customer")
print(f"Deleted {deleted} customer memories")

# Updated stats
stats = memory.get_stats()
print(f"Remaining: {stats['total_memories']}")
```

---

## Connection Management

### Environment Variables

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"
```

### From Environment

```python
import os
from agentic_brain import Neo4jMemory

memory = Neo4jMemory(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "")
)
memory.connect()
```

---

## Performance Considerations

### Vector Search
- Uses Neo4j vector indexes for fast similarity search
- Dimension: 384 (default, configurable)
- Supports approximate nearest neighbor search for large datasets

### Scoped Queries
- Automatically filtered by scope
- CUSTOMER queries are fully isolated - no cross-contamination

### Caching
- Results are cached by default
- Cache is invalidated on updates

### Indexing
- Automatic indexes on scope and timestamp
- Vector indexes for similarity search
- Consider indexing on frequently-searched metadata fields

---

## Error Handling

```python
from agentic_brain import Neo4jMemory

try:
    memory = Neo4jMemory()
    memory.connect()
    memory.store("Important fact")
except ImportError:
    print("neo4j package required: pip install neo4j")
except ConnectionError:
    print("Could not connect to Neo4j")
except ValueError as e:
    print(f"Invalid parameter: {e}")
```

---

## See Also

- [Chat Module](./chat.md) - Uses memory for context
- [Agent Module](./agent.md) - Agent memory integration
- [RAG Module](./rag.md) - Vector search
- [Index](./index.md) - All modules

---

**Last Updated**: 2026-03-20  
**Status**: Production Ready ✅
