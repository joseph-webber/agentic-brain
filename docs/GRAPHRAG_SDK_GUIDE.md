# GraphRAG SDK Guide — From Simple to Enterprise

> **Progressive adoption guide for Agentic Brain's GraphRAG stack**  
> Start simple, grow when you need to, never rewrite.

---

## Overview

Agentic Brain's GraphRAG is designed for **progressive adoption**. You can start with basic vector search today and grow to full enterprise GraphRAG without changing your code architecture.

```
Level 1: Basic Vector Search      → 5 minutes to production
Level 2: Graph Traversal          → Add relationship awareness
Level 3: Community Detection      → Enable global understanding
Level 4: Enterprise Features      → Multi-hop, custom extractors, GDS
```

**Philosophy**: Every level builds on the previous. No "rip and replace" upgrades.

---

## Level 1: Quick Start (Simple Mode)

**Best for**: Getting started, small datasets (&lt;10K documents), specific queries, users who don't need community detection.

### Minimal Setup

```bash
# Install core package only
pip install agentic-brain neo4j

# Start Neo4j (Docker recommended)
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:5.26-community
```

### Basic Vector Search

```python
import asyncio
from agentic_brain.rag.graph import EnhancedGraphRAG, GraphRAGConfig

async def main():
    # Simple config - no communities, no GDS required
    config = GraphRAGConfig(
        embedding_dimension=384,
        similarity_threshold=0.7,
        top_k=10,
    )
    
    rag = EnhancedGraphRAG(config)
    await rag.initialize()
    
    # Index your documents
    await rag.index_document(
        content="GraphRAG combines vector search with knowledge graphs.",
        doc_id="doc-001",
        metadata={"source": "readme", "version": "1.0"}
    )
    
    # Search with vector similarity only
    results = await rag.retrieve(
        query="How does GraphRAG work?",
        strategy="vector"  # Simple vector search
    )
    
    for r in results:
        print(f"Score: {r['score']:.3f} - {r['content'][:100]}")

asyncio.run(main())
```

### What You Get

| Feature | Included | Notes |
|---------|----------|-------|
| Vector similarity search | ✅ | MLX-accelerated on Apple Silicon |
| Document chunking | ✅ | Automatic |
| Entity extraction | ✅ | Heuristic (no LLM needed) |
| Metadata filtering | ✅ | Filter by source, date, etc. |
| Community detection | ❌ | Not needed for specific queries |
| Multi-hop reasoning | ❌ | Level 4 feature |

### When to Use Simple Mode

✅ **Use Simple Mode when:**
- You're just getting started
- Your queries are specific ("What is X?", "Where is Y?")
- Dataset is &lt;10K documents
- You want fast setup
- You don't have Neo4j GDS

❌ **Consider upgrading when:**
- Queries ask about themes/trends
- You need "Who works with whom?" answers
- Dataset is growing rapidly
- Users ask broad, exploratory questions

---

## Level 2: Adding Graph Traversal

**Best for**: Relationship-aware search, "Who works with X?" queries, medium datasets.

### Enable Hybrid Search

Graph traversal adds structural awareness without requiring community detection.

```python
import asyncio
from agentic_brain.rag.graph import EnhancedGraphRAG, GraphRAGConfig

async def main():
    config = GraphRAGConfig(
        embedding_dimension=384,
        similarity_threshold=0.7,
        
        # Graph traversal settings
        max_hop_depth=2,           # How many relationship hops
        max_neighbors=20,          # Max connected nodes per hop
        
        # Relationship weights for scoring
        relationship_weights={
            "WORKS_AT": 1.0,
            "MANAGES": 0.9,
            "RELATES_TO": 0.7,
            "MENTIONS": 0.5,
        },
        
        top_k=10,
        rerank=True,  # Enable reranking for better results
    )
    
    rag = EnhancedGraphRAG(config)
    await rag.initialize()
    
    # Index documents - entities and relationships extracted automatically
    await rag.index_document(
        "Alice works at Acme Corp. Alice manages Bob and Carol.",
        doc_id="org-001"
    )
    await rag.index_document(
        "Bob works on the GraphRAG project at Acme Corp.",
        doc_id="project-001"
    )
    
    # Hybrid search: vector + graph traversal + keyword
    results = await rag.retrieve(
        "Who does Alice manage?",
        strategy="hybrid"  # Combines all signals
    )
    
    for r in results:
        print(f"[{r['fusion_method']}] Score: {r['rrf_score']:.3f}")
        print(f"  Vector rank: {r.get('vector_rank', 'N/A')}")
        print(f"  Graph rank: {r.get('graph_rank', 'N/A')}")

asyncio.run(main())
```

### How Hybrid Search Works

```
Query: "Who does Alice manage?"
           │
           ├─► Vector Search ──► "Alice manages Bob and Carol" (rank 1)
           │
           ├─► Graph Traversal ─► Alice─[MANAGES]→Bob (rank 1)
           │                      Alice─[MANAGES]→Carol (rank 2)
           │
           └─► Keyword Match ──► Document containing "manages" (rank 1)
           
                      │
                      ▼
              Reciprocal Rank Fusion (RRF)
                      │
                      ▼
              Final ranked results
```

### Reciprocal Rank Fusion (RRF)

RRF combines multiple ranking signals without requiring training:

```
rrf_score = Σ 1 / (k + rank_i)
```

Where `k=60` (default) and `rank_i` is position in each result list.

**Why RRF?**
- Parameter-free (no training needed)
- Works across diverse signals
- Consistently outperforms linear weighted fusion
- Documents scoring well in multiple lists rank highest

### Using Graph-Only Strategy

For purely structural queries:

```python
# Find related entities through relationships only
results = await rag.retrieve(
    "What projects is Acme Corp involved in?",
    strategy="graph"  # Pure graph traversal
)
```

### What You Get at Level 2

| Feature | Level 1 | Level 2 |
|---------|---------|---------|
| Vector search | ✅ | ✅ |
| Graph traversal | ❌ | ✅ |
| Hybrid fusion (RRF) | ❌ | ✅ |
| Relationship scoring | ❌ | ✅ |
| Keyword/BM25 | partial | ✅ |
| Community detection | ❌ | ❌ |

---

## Level 3: Community Detection (Advanced)

**Best for**: Large datasets, global/thematic queries, "Summarize everything about X" questions.

### When You Need Communities

Communities become valuable when:

1. **Dataset is large** (&gt;10K documents)
2. **Queries are exploratory** ("What are the main themes?", "Summarize the ML team's work")
3. **No single document answers** the question
4. **You need topic clustering** for navigation

### Enable Community Detection

```python
import asyncio
from agentic_brain.rag.graph_rag import GraphRAG, GraphRAGConfig, SearchStrategy

async def main():
    config = GraphRAGConfig(
        # Enable community features
        enable_communities=True,
        community_algorithm="leiden",  # or "louvain" for simpler clustering
        
        # Standard settings
        embedding_dim=384,
        similarity_threshold=0.7,
        max_hops=3,
    )
    
    rag = GraphRAG(config)
    
    # Ingest documents
    await rag.ingest([
        {"content": "Alice leads the ML team at Acme.", "id": "doc-1"},
        {"content": "Bob works on computer vision under Alice.", "id": "doc-2"},
        {"content": "Carol handles NLP projects in the ML team.", "id": "doc-3"},
        {"content": "Dave manages backend infrastructure.", "id": "doc-4"},
        {"content": "Eve works on API development with Dave.", "id": "doc-5"},
    ])
    
    # Community-aware search
    results = await rag.search(
        "Tell me about the ML team's work",
        strategy=SearchStrategy.COMMUNITY
    )
    
    # Results include community context
    for r in results:
        print(f"Community: {r.get('community_id')}")
        print(f"Content: {r['content']}")

asyncio.run(main())
```

### Running Community Detection with Neo4j GDS

For production community detection, use Neo4j Graph Data Science:

```python
import asyncio
from agentic_brain.rag.graph import EnhancedGraphRAG
from agentic_brain.rag.community import CommunityGraphRAG

async def main():
    rag = EnhancedGraphRAG()
    await rag.initialize()
    
    # Index documents first...
    
    # Initialize community layer
    community_rag = CommunityGraphRAG(rag)
    
    # Detect communities (requires GDS)
    await community_rag.detect_communities(
        algorithm="leiden",
        gamma=1.0,  # Resolution: higher = more communities
    )
    
    # Generate LLM summaries for each community
    await community_rag.summarize_communities()
    
    # Build hierarchy
    hierarchy = await community_rag.build_hierarchy()
    
    print(f"Levels: {len(hierarchy)}")
    print(f"Level 0 communities: {len(hierarchy[0])}")
    print(f"Level 1 communities: {len(hierarchy[1])}")

asyncio.run(main())
```

### Hierarchy Levels Explained

```
Level 3 (Global)     ┌─────────────────────────────┐
                     │   "Technology Company"       │
                     └─────────────────────────────┘
                                    │
Level 2 (Coarse)    ┌───────────────┴───────────────┐
                    │                               │
              ┌─────┴─────┐                   ┌─────┴─────┐
              │ ML/AI Org │                   │ Infra Org │
              └───────────┘                   └───────────┘
                    │                               │
Level 1 (Fine)     ┌┴──────┬──────┐          ┌─────┴─────┐
                   │       │      │          │           │
                ┌──┴──┐ ┌──┴──┐ ┌─┴─┐     ┌──┴──┐    ┌──┴──┐
                │ CV  │ │ NLP │ │ML │     │ API │    │ DB  │
                │Team │ │Team │ │Ops│     │Team │    │Team │
                └─────┘ └─────┘ └───┘     └─────┘    └─────┘
                                    
Level 0 (Entities)  Alice Bob Carol Dave Eve ... (individual nodes)
```

**Query Routing by Level:**

| Query Type | Best Level | Example |
|------------|------------|---------|
| Specific fact | 0 (Entities) | "What does Bob work on?" |
| Team scope | 1 (Fine) | "What is the CV team building?" |
| Department | 2 (Coarse) | "Summarize ML organization work" |
| Company-wide | 3 (Global) | "What are main business areas?" |

### Smart Query Routing

```python
async def main():
    community_rag = CommunityGraphRAG(rag)
    
    # Auto-route query to appropriate level
    route = await community_rag.route_query(
        "What are the main themes in our documentation?"
    )
    
    print(f"Recommended level: {route['level']}")
    print(f"Strategy: {route['strategy']}")
    # Output: level=3, strategy=community (global query → top level)
    
    route = await community_rag.route_query(
        "What is Alice working on?"
    )
    print(f"Recommended level: {route['level']}")
    # Output: level=0, strategy=hybrid (specific query → entity level)
```

### GDS-Free Fallback

No Neo4j GDS? The system falls back to connected components:

```python
# Will use connected components when GDS unavailable
await community_rag.detect_communities(
    algorithm="leiden",  # Attempts Leiden
    fallback_to_components=True  # Falls back if GDS missing
)
```

### What You Get at Level 3

| Feature | Level 1 | Level 2 | Level 3 |
|---------|---------|---------|---------|
| Vector search | ✅ | ✅ | ✅ |
| Graph traversal | ❌ | ✅ | ✅ |
| Hybrid fusion | ❌ | ✅ | ✅ |
| Community detection | ❌ | ❌ | ✅ |
| Hierarchy levels | ❌ | ❌ | ✅ |
| Community summaries | ❌ | ❌ | ✅ |
| Query routing | ❌ | ❌ | ✅ |

---

## Level 4: Enterprise Features

**Best for**: Production systems, complex reasoning, custom domains, high performance.

### Multi-Hop Reasoning

For questions requiring chain-of-thought traversal:

```python
from agentic_brain.rag import GraphMultiHopReasoner

async def main():
    reasoner = GraphMultiHopReasoner(
        llm=my_llm,
        retriever=rag,
        neo4j_driver=driver,
        max_hops=5,
        confidence_threshold=0.7,  # Stop if confidence drops
    )
    
    # Complex query requiring multiple hops
    result = await reasoner.reason(
        "Who manages the project that fixed the authentication bug?"
    )
    
    print("Reasoning chain:")
    for hop in result.chain:
        print(f"  Hop {hop.number}: {hop.question}")
        print(f"    Answer: {hop.answer}")
        print(f"    Confidence: {hop.confidence:.2f}")
    
    print(f"\nFinal answer: {result.answer}")
    print(f"Citations: {result.citations}")

# Output:
# Reasoning chain:
#   Hop 1: What project fixed the authentication bug?
#     Answer: Project Phoenix
#     Confidence: 0.92
#   Hop 2: Who manages Project Phoenix?
#     Answer: Sarah Chen
#     Confidence: 0.88
# 
# Final answer: Sarah Chen manages the project that fixed the authentication bug.
# Citations: [doc-142, doc-89]
```

### Custom Entity Extractors

For domain-specific entities:

```python
from agentic_brain.rag.graphrag import KnowledgeExtractor, KnowledgeExtractorConfig

# Domain-specific schema
config = KnowledgeExtractorConfig(
    schema={
        "entity_types": [
            "MEDICATION", "CONDITION", "PROCEDURE",
            "DOSAGE", "PATIENT", "PROVIDER"
        ],
        "relationship_types": [
            "TREATS", "CAUSES", "CONTRAINDICATES",
            "PRESCRIBED_BY", "DIAGNOSED_WITH"
        ],
        "patterns": [
            {"from": "MEDICATION", "rel": "TREATS", "to": "CONDITION"},
            {"from": "PROCEDURE", "rel": "TREATS", "to": "CONDITION"},
            {"from": "MEDICATION", "rel": "CONTRAINDICATES", "to": "MEDICATION"},
        ]
    },
    max_entities=100,  # Higher limit for medical docs
    on_error="IGNORE",  # Graceful fallback
)

extractor = KnowledgeExtractor(config, llm=medical_llm)

# Extract with custom schema
result = extractor.extract_from_text_sync(
    "Metformin 500mg treats Type 2 Diabetes. Contraindicated with contrast dye.",
    document_id="clinical-001"
)

print(f"Entities: {result.entity_count}")
print(f"Relationships: {result.relationship_count}")
```

### Text2Cypher with Safety

Natural language to Cypher translation (read-only):

```python
extractor = KnowledgeExtractor(config, llm=my_llm)

# Safe querying - only READ operations allowed
response = extractor.query("Which medications treat diabetes?")

print(f"Mode: {response.mode}")  # text2cypher or keyword_fallback
print(f"Results: {response.results}")

# Unsafe queries automatically rejected and fall back to keyword search:
response = extractor.query("Delete all patient records")
print(f"Mode: {response.mode}")  # keyword_fallback (DELETE rejected)
```

### Performance Tuning

#### Batch Processing

```python
from agentic_brain.rag.graph import EnhancedGraphRAG

async def batch_ingest(documents: list[dict]):
    rag = EnhancedGraphRAG()
    await rag.initialize()
    
    # Batch documents for efficient UNWIND operations
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        
        # Single transaction for entire batch
        await rag.index_documents_batch(batch)
        
        print(f"Indexed {min(i + batch_size, len(documents))}/{len(documents)}")
```

#### Connection Pooling

```python
from agentic_brain.core.neo4j_utils import get_pool_driver

# Shared connection pool across the application
driver = get_pool_driver(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    max_connection_pool_size=50,
    connection_acquisition_timeout=30,
)

config = GraphRAGConfig(use_pool=True)
rag = EnhancedGraphRAG(config)
```

#### Embedding Cache

```python
config = GraphRAGConfig(
    cache_embeddings=True,
    cache_ttl=3600,  # 1 hour cache
)

# Embeddings cached in Redis if available, memory otherwise
```

### GDS Integration (Full)

```python
# Create GDS graph projection
async def setup_gds_projection(session):
    await session.run("""
        CALL gds.graph.project(
            'knowledge-graph',
            ['Entity', 'Document', 'Chunk'],
            {
                RELATES_TO: {orientation: 'UNDIRECTED'},
                MENTIONS: {orientation: 'NATURAL'},
                PART_OF: {orientation: 'NATURAL'}
            }
        )
    """)

# Run Leiden with intermediate communities
async def run_leiden(session):
    result = await session.run("""
        CALL gds.leiden.write('knowledge-graph', {
            writeProperty: 'communityId',
            includeIntermediateCommunities: true,
            gamma: 1.0,
            maxLevels: 10
        })
        YIELD communityCount, modularity, ranLevels
        RETURN communityCount, modularity, ranLevels
    """)
    
    record = await result.single()
    print(f"Communities: {record['communityCount']}")
    print(f"Modularity: {record['modularity']:.3f}")
    print(f"Levels: {record['ranLevels']}")
```

### Enterprise Feature Matrix

| Feature | Level 1-3 | Level 4 |
|---------|-----------|---------|
| Multi-hop reasoning | ❌ | ✅ |
| Custom extractors | basic | ✅ full |
| Text2Cypher | ❌ | ✅ |
| Batch processing | basic | ✅ optimized |
| Connection pooling | auto | ✅ configurable |
| GDS integration | fallback | ✅ full |
| Embedding cache | ❌ | ✅ |
| Query decomposition | ❌ | ✅ |

---

## Migration Path

### From Level 1 → Level 2

**Changes required**: None! Just change your search strategy.

```python
# Before (Level 1)
results = await rag.retrieve(query, strategy="vector")

# After (Level 2)
results = await rag.retrieve(query, strategy="hybrid")
```

**What happens:**
- Same indexed data works
- Graph relationships already extracted during indexing
- RRF automatically combines signals

### From Level 2 → Level 3

**Changes required**: Enable communities in config, run detection.

```python
# Before (Level 2)
config = GraphRAGConfig()
rag = EnhancedGraphRAG(config)

# After (Level 3) - add community layer
from agentic_brain.rag.community import CommunityGraphRAG

config = GraphRAGConfig()  # Same config
rag = EnhancedGraphRAG(config)
await rag.initialize()

# Add community detection (one-time)
community_rag = CommunityGraphRAG(rag)
await community_rag.detect_communities()
await community_rag.summarize_communities()

# Use community search for global queries
results = await rag.retrieve(query, strategy="community")
```

**What happens:**
- Existing data preserved
- Communities computed on existing graph
- No re-indexing required

### From Level 3 → Level 4

**Changes required**: Add enterprise components as needed.

```python
# Add multi-hop reasoning
from agentic_brain.rag import GraphMultiHopReasoner
reasoner = GraphMultiHopReasoner(llm, rag)

# Add custom extractor
from agentic_brain.rag.graphrag import KnowledgeExtractor
extractor = KnowledgeExtractor(custom_config, llm=domain_llm)

# Add GDS projection
await setup_gds_projection(session)
```

### Backwards Compatibility Guarantees

| Guarantee | Scope |
|-----------|-------|
| **API Stability** | Public APIs don't break within major versions |
| **Data Compatibility** | Graph schema additions are always additive |
| **Config Defaults** | New config options default to existing behavior |
| **Fallback Behavior** | Features degrade gracefully when dependencies missing |

### Version Migration

```python
# v1.x → v2.x migration helper
from agentic_brain.rag import migrate_graphrag_schema

await migrate_graphrag_schema(
    driver=driver,
    from_version="1.x",
    to_version="2.x",
    dry_run=True  # Preview changes first
)
```

---

## Quick Reference

### Which Level Do I Need?

| Scenario | Recommended Level |
|----------|-------------------|
| Just getting started | Level 1 |
| &lt;10K documents | Level 1 |
| Specific queries only | Level 1 |
| "Who works with X?" queries | Level 2 |
| Need relationship awareness | Level 2 |
| 10K-100K documents | Level 2-3 |
| Global/thematic queries | Level 3 |
| "Summarize all X" queries | Level 3 |
| &gt;100K documents | Level 3-4 |
| Complex reasoning chains | Level 4 |
| Domain-specific extraction | Level 4 |
| Production optimization | Level 4 |

### Strategy Selection

```python
# Specific fact lookup
await rag.retrieve("What is X?", strategy="vector")

# Relationship query
await rag.retrieve("Who works with X?", strategy="graph")

# Best general purpose
await rag.retrieve("Tell me about X", strategy="hybrid")

# Theme/summary queries (Level 3+)
await rag.retrieve("What are main themes?", strategy="community")
```

### Config Cheat Sheet

```python
# Level 1: Minimal
config = GraphRAGConfig()

# Level 2: Hybrid-ready
config = GraphRAGConfig(
    max_hop_depth=2,
    max_neighbors=20,
    rerank=True,
)

# Level 3: Community-enabled
config = GraphRAGConfig(
    enable_communities=True,
    community_algorithm="leiden",
    max_hop_depth=3,
)

# Level 4: Production
config = GraphRAGConfig(
    enable_communities=True,
    community_algorithm="leiden",
    max_hop_depth=5,
    cache_embeddings=True,
    cache_ttl=3600,
    use_pool=True,
)
```

---

## Appendix: Architecture Diagram

```
                    ┌─────────────────────────────────────┐
                    │            Your Application          │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │         GraphRAG SDK                 │
                    │  ┌─────────────────────────────────┐│
                    │  │ Level 1: Vector Search          ││
                    │  │  • EnhancedGraphRAG.retrieve()  ││
                    │  │  • strategy="vector"            ││
                    │  └──────────────┬──────────────────┘│
                    │  ┌──────────────▼──────────────────┐│
                    │  │ Level 2: Hybrid Search          ││
                    │  │  • Graph traversal              ││
                    │  │  • RRF fusion                   ││
                    │  │  • strategy="hybrid"            ││
                    │  └──────────────┬──────────────────┘│
                    │  ┌──────────────▼──────────────────┐│
                    │  │ Level 3: Communities            ││
                    │  │  • CommunityGraphRAG            ││
                    │  │  • Hierarchy levels             ││
                    │  │  • Query routing                ││
                    │  └──────────────┬──────────────────┘│
                    │  ┌──────────────▼──────────────────┐│
                    │  │ Level 4: Enterprise             ││
                    │  │  • Multi-hop reasoning          ││
                    │  │  • Custom extractors            ││
                    │  │  • GDS integration              ││
                    │  └─────────────────────────────────┘│
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │              Neo4j                   │
                    │  • Documents, Chunks, Entities       │
                    │  • Vector indexes (5.11+)            │
                    │  • GDS plugin (optional)             │
                    └─────────────────────────────────────┘
```

---

## Related Documentation

- [GRAPHRAG.md](GRAPHRAG.md) — Core GraphRAG documentation
- [GRAPHRAG_BEST_PRACTICES.md](GRAPHRAG_BEST_PRACTICES.md) — Performance tuning
- [NEO4J_ARCHITECTURE.md](NEO4J_ARCHITECTURE.md) — Graph schema reference
- [VECTOR_EMBEDDINGS.md](VECTOR_EMBEDDINGS.md) — Embedding configuration
- [RAG_GUIDE.md](RAG_GUIDE.md) — General RAG patterns

---

*Last updated: 2026-01-15*  
*Supports: Agentic Brain v2.x, Neo4j 5.11+, Python 3.10+*
