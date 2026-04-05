# Agentic Brain Core Module

The core module provides foundational infrastructure for the Agentic Brain system, including connection pooling, caching, memory management, and behavior adaptation.

## Module Overview

The `core` module comprises several specialized components:

- **Polymorphic Brain**: Adapts behavior based on user type, context, environment, and compliance requirements
- **Neo4j Connection Pool**: Lazy-loaded graph database connection management
- **Redis Coordination**: Agent registry, task queues, and pub/sub messaging
- **Cache Manager**: Generic API response caching with TTL support
- **Startup Context**: Memory-backed startup greetings and session continuity
- **Neo4j Utilities**: Retry logic and schema management

All components are thread-safe and follow lazy initialization patterns to minimize resource overhead.

## Key Classes and Components

### PolymorphicBrain

Adapts the brain's behavior to match the operating context and compliance posture.

```python
from agentic_brain.core import PolymorphicBrain, UserType, ContextType

brain = PolymorphicBrain()

# Auto-detect user type from message content
user_type = brain.detect_user_type("I need to deploy this to production")

# Adapt behavior based on context
profile = brain.adapt(
    user_type=UserType.ENTERPRISE,
    context=ContextType.WORK,
    compliance=ComplianceMode.SOC2
)

# Get system prompt modifiers for LLM routing
modifiers = brain.get_system_prompt_modifier()

# Check if query needs consensus validation
if brain.should_use_consensus("delete all data"):
    # Route to multi-source verification
    pass
```

**Behavior Profiles** (preset configurations for different user types):

| User Type | Verbosity | Technical Level | Consensus | Audit Logging | Examples |
|-----------|-----------|-----------------|-----------|---------------|----------|
| BEGINNER | detailed | simple | no | no | First-time users |
| DEVELOPER | normal | technical | no | no | API/CLI developers |
| ENTERPRISE | normal | auto | yes | yes | Large organizations |
| DEFENSE | brief | expert | yes | yes | Government/military |
| MEDICAL | detailed | auto | yes | yes | Healthcare systems |

**Context Types** modify behavior further:

- `CASUAL`: Default behavior
- `WORK`: Professional tone
- `CODING`: Technical language
- `MEDICAL`/`LEGAL`: Citation required, consensus enabled
- `CLASSIFIED`: Local-only, no data retention

**Environment Types** enforce deployment constraints:

- `CLOUD`: Standard trust boundary
- `HYBRID`: Prefer local models, allow cloud fallback
- `AIRLOCKED`: Local-only, no external API calls

**Compliance Modes** tighten security requirements:

- `NONE`: Default
- `SOC2`/`ISO27001`: Audit logging + hallucination threshold 0.05
- `HIPAA`: HIPAA-grade encryption, threshold 0.02
- `FEDRAMP`/`DEFENSE`: Military encryption, local-only, threshold 0.01

### Neo4jPoolConfig

Configuration for the shared Neo4j driver connection pool.

```python
from agentic_brain.core import Neo4jPoolConfig, configure_neo4j_pool

# Configure via environment variables
# NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE, NEO4J_POOL_SIZE

# Or programmatically
configure_neo4j_pool(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="secret",
    database="neo4j",
    max_connection_pool_size=50
)
```

### Neo4j Pool Functions

All functions use lazy driver initialization—the driver is created on first use.

**Synchronous API** (for blocking contexts):

```python
from agentic_brain.core import (
    get_neo4j_driver,
    get_neo4j_session,
    neo4j_query,
    neo4j_query_single,
    neo4j_query_value,
    neo4j_write,
    neo4j_pool_health,
    close_neo4j_pool,
)

# Execute read queries
rows = neo4j_query("MATCH (n:Entity) RETURN n LIMIT 10")

# Get single result
record = neo4j_query_single("MATCH (n {id: $id}) RETURN n", id="entity-1")

# Get scalar value
count = neo4j_query_value("MATCH (n) RETURN count(n)")

# Execute write operations
affected = neo4j_write("CREATE (n:Node {name: $name})", name="New Node")

# Health check
health = neo4j_pool_health()
# Returns: {"status": "healthy", "uri": "...", "total_nodes": 1000, ...}

# Manual session management
with get_neo4j_session() as session:
    result = session.run("MATCH (n) RETURN n LIMIT 1")
    record = result.single()
```

**Asynchronous API** (for async/await contexts):

```python
from agentic_brain.core.neo4j_pool import (
    async_get_driver,
    async_get_session,
    async_query,
    async_query_single,
    async_query_value,
    async_write,
    async_health_check,
    async_close_pool,
)

# Async equivalents
async with async_get_session() as session:
    rows = await async_query("MATCH (n) RETURN n LIMIT 10")
    record = await async_query_single("MATCH (n) WHERE n.id = $id RETURN n", id="1")
    affected = await async_write("CREATE (n) SET n.processed = true")
```

### CacheManager

Generic cache for external API responses with TTL support.

```python
from agentic_brain.core import CacheManager

# Create a cache for a specific integration
jira_cache = CacheManager(label="JiraApiCache", database="neo4j")

# Cache a response
jira_cache.set_cached(
    cache_key="JIRA-1234",
    value={"key": "JIRA-1234", "status": "In Progress"},
    ttl_hours=1
)

# Retrieve cached data
ticket = jira_cache.get_cached("JIRA-1234")

# Invalidate when data changes
jira_cache.invalidate("JIRA-1234")
```

**Usage with `@neo4j_first` decorator**:

```python
from agentic_brain.core import neo4j_first

@neo4j_first(cache_key="jira:{ticket_id}", ttl_hours=1)
def get_jira_ticket(ticket_id: str) -> dict:
    """Fetches from API, but checks Neo4j first."""
    return jira_api.get(ticket_id)

# First call hits API and caches result
ticket = get_jira_ticket("JIRA-1234")

# Second call (within TTL) retrieves from Neo4j cache
ticket = get_jira_ticket("JIRA-1234")  # Fast path
```

Supports both sync and async functions:

```python
@neo4j_first(cache_key="github:{repo}:{pr_id}", ttl_hours=24)
async def get_pr_info(repo: str, pr_id: int) -> dict:
    return await github_api.get_pull_request(repo, pr_id)
```

### RedisPoolManager & RedisCoordination

Redis-based coordination for distributed agent systems.

```python
from agentic_brain.core import get_redis_pool, RedisCoordination

# Get default pool (configured via environment)
pool = get_redis_pool()

# High-level coordination primitives
coord = RedisCoordination(pool)

# Agent lifecycle management
coord.register_agent(
    agent_id="transformer-1",
    metadata={"role": "text_processing", "capacity": 10}
)

# Heartbeat (keep agent alive in registry)
coord.heartbeat_agent("transformer-1", ttl_seconds=60)

# List active agents
agents = coord.list_active_agents()

# Task queue
coord.enqueue_task({
    "task_id": "task-123",
    "type": "process",
    "data": {...}
})

task = coord.dequeue_task(queue="brain.tasks.queue", block_seconds=1)

# Result cache
coord.cache_result("result-key", {"output": "value"}, ttl_seconds=3600)
cached = coord.get_cached_result("result-key")

# Event pub/sub (brain.* topics bridge to Redpanda)
coord.publish_event(
    topic="brain.agents.state_changed",
    payload={"agent_id": "agent-1", "state": "ready"}
)

subscribers = coord.subscribe(["brain.agents.*", "brain.tasks.*"])
for message in subscribers.listen():
    print(message)
```

**Redis Configuration** (via environment):

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=secret
REDIS_DB=0
# Or use connection string:
REDIS_URL=redis://user:password@host:port/db
```

### Startup Context

Load recent memory from Neo4j to provide contextual startup greetings.

```python
from agentic_brain.core import get_startup_snapshot, startup_greeting

# Get full snapshot with structured data
snapshot = get_startup_snapshot(limit=5, scopes=("private", "public"))
print(snapshot.greeting)
print(snapshot.pending_count)  # Action items from last week
print(snapshot.recent_summary)  # Quick context refresh

# Or just get the greeting string
greeting = startup_greeting()
```

The greeting queries Neo4j for:
- Recent memories (ordered by timestamp)
- Pending items (containing "todo", "pending", "follow up", etc.)
- Last session topic extracted from memory metadata

Example output:

```
Welcome back! Here's what I remember:
- Last session: Deploying frontend to production at today at 3:42 PM
- Pending: 3 items
- Recent: API redesign completed; Database backup verified; Testing framework installed
Ready to continue?
```

### Neo4j Utilities

**Resilient Query Execution** with exponential backoff retry:

```python
from agentic_brain.core.neo4j_utils import resilient_query_sync, resilient_query

# Sync version (for blocking code)
rows = resilient_query_sync(
    session=my_session,
    query="MATCH (n) RETURN n",
    params={"limit": 10},
    max_retries=3
)

# Async version
rows = await resilient_query(
    session=my_async_session,
    query="MATCH (n) RETURN n",
    params={"limit": 10},
    max_retries=3
)
```

Retries on transient errors with backoff: 1s, 2s, 4s (before giving up)

**Schema Management** (vector indexes, fulltext search):

```python
from agentic_brain.core.neo4j_schema import ensure_indexes, ensure_indexes_sync

# Sync initialization
with get_neo4j_session() as session:
    ensure_indexes_sync(session)

# Async initialization
async with async_get_session() as session:
    await ensure_indexes(session)
```

Auto-created indexes:
- Fulltext: `entity`, `chunk`, `document` (content + metadata)
- Range: entity type, chunk document_id, document timestamp
- Vector: `chunk_embeddings` (384-dim cosine, for RAG embeddings)

## Configuration

All components use environment variables for default configuration:

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=
NEO4J_DATABASE=neo4j
NEO4J_POOL_SIZE=50
NEO4J_POOL_TIMEOUT=30

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
# Or:
REDIS_URL=redis://localhost:6379/0
```

Programmatic overrides are also supported:

```python
from agentic_brain.core import configure_neo4j_pool, get_redis_pool, RedisPoolManager, RedisConfig

# Override Neo4j config
configure_neo4j_pool(uri="bolt://neo4j.prod:7687", password="prod-secret")

# Create custom Redis pool
config = RedisConfig(host="redis.prod", port=6379)
pool = RedisPoolManager(config=config)
```

## Usage Examples

### Full Integration Example

```python
from agentic_brain.core import (
    PolymorphicBrain,
    get_startup_snapshot,
    get_redis_pool,
    neo4j_query,
    CacheManager,
)

# 1. Load startup context
snapshot = get_startup_snapshot()
print(snapshot.greeting)

# 2. Adapt behavior to user
brain = PolymorphicBrain()
user_type = brain.detect_user_type("Deploy to production")
profile = brain.adapt(user_type=user_type)
system_prompt = brain.get_system_prompt_modifier()

# 3. Check for high-stakes operations
if brain.should_use_consensus("DELETE FROM users"):
    print("Routing to consensus verification")

# 4. Use caching for external APIs
github_cache = CacheManager(label="GitHubApiCache")
@neo4j_first(cache_key="github:{repo}:{issue_id}", ttl_hours=2, cache_manager=github_cache)
def get_issue(repo: str, issue_id: int) -> dict:
    return github_api.get_issue(repo, issue_id)

issue = get_issue("owner/repo", 123)

# 5. Publish agent events
coord = RedisCoordination(get_redis_pool())
coord.register_agent("processor-1", metadata={"type": "nlp"})
coord.publish_event("brain.events.processor_started", {"agent_id": "processor-1"})

# 6. Query graph database
results = neo4j_query(
    "MATCH (e:Entity {type: $type}) RETURN e",
    type="PERSON"
)
```

## Thread Safety & Performance

- **Lazy initialization**: Drivers/pools created only on first use
- **Connection pooling**: Shared driver instances prevent connection exhaustion
- **Thread-safe**: All operations are reentrant and thread-safe
- **Resource cleanup**: Automatic cleanup via `atexit` hooks
- **Async support**: Full async/await support for non-blocking I/O

## Error Handling

All pool functions include defensive error handling:

```python
# Neo4j pool handles connection errors gracefully
health = neo4j_pool_health()
# Returns error details if Neo4j is unavailable

# Redis pool never raises on connection issues
health = pool.health_check()
# Returns {"ok": False, "error": "Connection refused", ...}

# Cache manager fails open (doesn't break API calls)
@neo4j_first(cache_key="...")
def api_call():
    # If Neo4j cache is down, still calls API
    pass
```

## Best Practices

1. **Configure early**: Set environment variables or call `configure_*` functions before first use
2. **Reuse pools**: Don't create new `PolymorphicBrain()` or `RedisCoordination()` instances per request
3. **Use context managers**: Always use `with get_neo4j_session()` or `async with async_get_session()`
4. **Cache appropriately**: Use `@neo4j_first` for external APIs with stable data
5. **Monitor health**: Periodically call `neo4j_pool_health()` and `pool.health_check()` for observability
6. **Handle transient errors**: Use resilient query functions for production systems

## Testing

All components include test-friendly interfaces:

```python
from agentic_brain.core import (
    CacheManager,
    RedisPoolManager,
    RedisConfig,
)

# Test with in-memory Redis (via mock)
mock_client = MagicMock()
pool = RedisPoolManager(client=mock_client)
coord = RedisCoordination(pool)

# Test with custom cache manager
cache = CacheManager(label="TestCache")
@neo4j_first(cache_key="test:{id}", cache_manager=cache)
def fetch(id: str):
    return {"id": id}
```
