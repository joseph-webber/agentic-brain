# GraphRAG Simple Mode (No Community Detection)

> **For Arraz2000 and smaller projects** - Run GraphRAG without the overhead of community detection.

## Quick Start

```python
from agentic_brain.rag.graph_rag import GraphRAG, GraphRAGConfig, SearchStrategy

# Simple mode - no community detection
config = GraphRAGConfig(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="your-password",
    enable_communities=False,  # ← KEY SETTING
)

rag = GraphRAG(config)

# Ingest documents (no community detection runs)
stats = await rag.ingest([
    {"content": "Your document text here..."}
])
# Returns: {"entities": 5, "relationships": 3, "communities": 0}

# Search with VECTOR or HYBRID (not COMMUNITY)
results = await rag.search("your query", strategy=SearchStrategy.HYBRID)
```

## What's Available in Simple Mode

| Feature | Simple Mode | Full Mode |
|---------|-------------|-----------|
| Entity extraction | ✅ | ✅ |
| Relationship extraction | ✅ | ✅ |
| Vector search | ✅ | ✅ |
| Hybrid search (vector + graph) | ✅ | ✅ |
| Graph traversal | ✅ | ✅ |
| Multi-hop reasoning | ✅ | ✅ |
| Community detection | ❌ | ✅ |
| Community search strategy | ❌ | ✅ |
| Hierarchical summarization | ❌ | ✅ |
| Neo4j GDS required | **No** | Yes (for Leiden/Louvain) |

## Search Strategies

### Available in Simple Mode

```python
# Vector search - fast embedding similarity
results = await rag.search(query, strategy=SearchStrategy.VECTOR)

# Hybrid search - combines vector + graph traversal (recommended)
results = await rag.search(query, strategy=SearchStrategy.HYBRID)

# Graph search - pure relationship traversal
results = await rag.search(query, strategy=SearchStrategy.GRAPH)

# Multi-hop - follows reasoning chains
results = await rag.search(query, strategy=SearchStrategy.MULTI_HOP)
```

### NOT Available in Simple Mode

```python
# This will log a warning and fall back to HYBRID search:
results = await rag.search(query, strategy=SearchStrategy.COMMUNITY)
# WARNING: COMMUNITY search requested but enable_communities=False.
#          Falling back to HYBRID search.
```

## When to Use Simple Mode

✅ **Use Simple Mode When:**
- Your graph has < 10,000 entities
- You don't need global/thematic queries
- Neo4j GDS plugin is not available
- You want faster ingest times
- You're building a prototype or POC

❌ **Use Full Mode When:**
- You need "big picture" queries across many topics
- Your graph has complex community structures
- You want hierarchical summarization
- You're doing competitive analysis or research synthesis

## Neo4j GDS Not Required

Simple mode works with vanilla Neo4j - no Graph Data Science plugin needed.

```bash
# Minimal Neo4j setup (no GDS)
docker run -d \
  --name neo4j \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:5-community
```

## Migration Path

When your project grows and you want community features:

```python
# Step 1: Enable communities in config
config = GraphRAGConfig(
    enable_communities=True,  # ← Enable
    community_algorithm="leiden",  # or "louvain"
)

# Step 2: Install Neo4j GDS (optional but recommended)
# docker run neo4j:5-enterprise with GDS plugin

# Step 3: Re-ingest to detect communities
stats = await rag.ingest(documents)
# Now stats["communities"] will be > 0

# Step 4: Use COMMUNITY search for global queries
results = await rag.search(
    "What are the main themes across all documents?",
    strategy=SearchStrategy.COMMUNITY
)
```

## Fixes Applied (2026-01-XX)

This document was created after an audit to ensure simple mode truly works:

1. **Lazy-loaded community module** - `community_detection.py` is only imported when `enable_communities=True` and community features are actually used.

2. **Search strategy validation** - Using `SearchStrategy.COMMUNITY` with `enable_communities=False` now gracefully falls back to HYBRID with a warning (instead of failing).

3. **No implicit dependencies** - Ingest and search work without any community code paths when disabled.

4. **GDS-free fallback** - Even if you enable communities without GDS, the system falls back to connected-component detection using pure Cypher.

## API Reference

### GraphRAGConfig

```python
@dataclass
class GraphRAGConfig:
    # Neo4j connection
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me"  # Or use NEO4J_PASSWORD env var
    
    # Vector settings
    embedding_dim: int = 384
    embedding_model: str = "all-MiniLM-L6-v2"
    similarity_threshold: float = 0.7
    
    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 50
    
    # Graph traversal
    max_hops: int = 3
    max_relationships: int = 50
    
    # Community detection (set False for simple mode)
    enable_communities: bool = True  # ← Set to False
    community_algorithm: str = "leiden"
    
    # Caching
    cache_embeddings: bool = True
    cache_ttl: int = 3600
```

### SearchStrategy Enum

```python
class SearchStrategy(Enum):
    VECTOR = "vector"       # Pure embedding similarity
    GRAPH = "graph"         # Pure graph traversal
    HYBRID = "hybrid"       # Vector + Graph combined (DEFAULT)
    COMMUNITY = "community" # Requires enable_communities=True
    MULTI_HOP = "multi_hop" # Multi-hop reasoning
```

## Troubleshooting

### "Community detection failed" warnings during ingest

If you see this with `enable_communities=True`, check:
1. Is Neo4j GDS installed? (Run `RETURN gds.version()` in Neo4j Browser)
2. Are there entities with relationships? (Minimum graph required)

With `enable_communities=False`, you won't see these warnings.

### Slow ingest times

Community detection adds overhead. With large graphs:
- Simple mode: ~100 docs/sec
- Full mode: ~20 docs/sec (due to Leiden algorithm)

### Empty search results

1. Check entities exist: `MATCH (e:Entity) RETURN count(e)`
2. Check embeddings exist: `MATCH (e:Entity) WHERE e.embedding IS NOT NULL RETURN count(e)`
3. Try VECTOR strategy first, then HYBRID

---

**Questions?** Open an issue or ping Joseph/Arraz2000.
