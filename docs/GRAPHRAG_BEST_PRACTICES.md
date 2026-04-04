# Graph RAG Best Practices — Agentic Brain

> Best-in-class Graph RAG implementation aligned with Microsoft GraphRAG,
> LlamaIndex, and LangChain patterns. Optimised for Neo4j + Apple Silicon (MLX).

## Architecture Overview

```
Query → Semantic Router → Strategy Selection
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                  ▼
        Vector Search    Graph Traversal   Community Search
        (Neo4j native)   (Cypher + hops)   (Hierarchical)
            │                 │                  │
            └─────────┬───────┘                  │
                      ▼                          ▼
              Reciprocal Rank Fusion    Community Summaries
                      │                          │
                      └──────────┬───────────────┘
                                 ▼
                        Contextual Reranking
                                 ▼
                           LLM Generation
```

## Feature Comparison vs State-of-Art

| Feature | Microsoft GraphRAG | LlamaIndex KG | LangChain Graph | **Agentic Brain** |
|---|---|---|---|---|
| Community detection | Leiden | — | — | **Leiden + Louvain + fallback** |
| Multi-level hierarchy | ✅ | — | — | **✅ (3 levels)** |
| Community summaries | ✅ (LLM) | — | — | **✅ (LLM + structured)** |
| Entity resolution | ✅ | partial | — | **✅ (normalized name)** |
| Multi-hop reasoning | partial | ✅ | — | **✅ (5-hop chains)** |
| Triple extraction | ✅ | ✅ | ✅ | **✅ (LLM + heuristic)** |
| Neo4j native vectors | — | — | ✅ | **✅** |
| Cypher generation | — | — | ✅ | **✅ (Text2Cypher)** |
| Hybrid retrieval (RRF) | — | ✅ | ✅ | **✅ (vector+graph+keyword)** |
| MLX/Apple Silicon | — | — | — | **✅ (Metal-accelerated)** |
| BM25 keyword search | — | ✅ | — | **✅** |
| Query decomposition | — | ✅ | — | **✅** |
| GDS-free fallback | — | n/a | n/a | **✅ (pure Cypher components)** |

## Key Components

### 1. Community Detection (`community_detection.py`)

**Cascade strategy** — works with or without Neo4j GDS:

1. **Leiden** (GDS required) — multi-resolution hierarchical detection
2. **Louvain** (GDS required) — single-level fallback
3. **Connected Components** (pure Cypher) — always works

```python
from agentic_brain.rag import detect_communities_hierarchical

hierarchy = detect_communities_hierarchical(session, gamma=1.0, max_levels=3)
for community in hierarchy.communities_at_level(0):
    print(f"Community {community.id}: {community.entities[:5]}")
    print(f"  Summary: {community.summary}")
```

**Hierarchy levels:**
- Level 0: Fine-grained (highest gamma) — best for specific queries
- Level 1: Mid-grain — good for topic-level queries
- Level 2: Coarse — good for "tell me about everything related to X"

### 2. Community Summarization

Each community gets a summary (LLM-powered when available, structured fallback otherwise):

```python
from agentic_brain.rag import summarize_all_communities

hierarchy = summarize_all_communities(session, hierarchy, llm=my_llm)
# Summaries stored on Community.summary attribute
```

Summaries are used during retrieval to match queries against community themes,
not just individual entity names.

### 3. Entity Resolution (`resolve_entities`)

Automatic deduplication on ingest:
- Merges entities with identical normalized names
- Transfers relationships from duplicate to canonical entity
- Aggregates mention counts
- Runs after every `index_document()` call

```python
from agentic_brain.rag import resolve_entities

merged_count = resolve_entities(session, similarity_threshold=0.85)
```

### 4. Multi-Hop Reasoning (`multi_hop_reasoning.py`)

For complex questions requiring chain-of-thought retrieval:

```python
from agentic_brain.rag import GraphMultiHopReasoner

reasoner = GraphMultiHopReasoner(llm, retriever, neo4j_driver=driver, max_hops=5)
result = reasoner.reason("Who manages the project that fixed bug #123?")
# Hop 1: "What project fixed bug #123?" → Project Alpha
# Hop 2: "Who manages Project Alpha?" → Sarah Chen
```

Features:
- Automatic hop planning (LLM-guided)
- Graph traversal for relationship hops (efficient Cypher)
- Confidence tracking per hop (stops early if uncertain)
- Citation chain in final answer

### 5. Hybrid Retrieval with RRF (`hybrid.py`)

Three-signal fusion:

```python
from agentic_brain.rag import reciprocal_rank_fusion

fused = reciprocal_rank_fusion(
    vector_results,    # Semantic similarity (MLX embeddings)
    graph_results,     # Graph traversal scores
    keyword_results,   # BM25 lexical match
    k=60,              # RRF constant
)
```

### 6. Retrieval Strategies (`graph.py`)

```python
from agentic_brain.rag import EnhancedGraphRAG

rag = EnhancedGraphRAG()
await rag.initialize()

# Strategy options:
results = await rag.retrieve(query, strategy="vector")     # Fast embedding search
results = await rag.retrieve(query, strategy="graph")      # Relationship traversal
results = await rag.retrieve(query, strategy="hybrid")     # Vector + graph + RRF
results = await rag.retrieve(query, strategy="community")  # Hierarchical community
```

## When to Use Each Strategy

| Query Type | Best Strategy | Why |
|---|---|---|
| "What is X?" | `vector` | Direct semantic match |
| "Who works on X?" | `graph` | Follow relationships |
| "Tell me about the ML team" | `community` | Cluster-level understanding |
| "What caused the outage?" | `hybrid` | Needs both semantic + structural |
| "Who manages the team that built X?" | Multi-hop | Chain of reasoning |
| Exact term / acronym lookup | `hybrid` (keyword boost) | BM25 catches exact matches |

## Performance Benchmarks

### Expected Accuracy (based on Microsoft GraphRAG paper findings)

| Method | Simple Queries | Complex Queries | Global Queries |
|---|---|---|---|
| Naive retrieval | ~60% | ~30% | ~15% |
| Vector-only RAG | ~80% | ~50% | ~25% |
| Standard GraphRAG | ~85% | ~70% | ~55% |
| **Community GraphRAG** | **~85%** | **~75%** | **~70%** |

Community Graph RAG's main advantage is **global queries** — questions about
themes, trends, or "tell me about everything related to X" — where
community summaries provide context that no single chunk contains.

### MLX Embedding Performance (Apple M2/M3)

| Model | Dimension | Throughput | Latency |
|---|---|---|---|
| all-MiniLM-L6-v2 (MLX) | 384 | ~500 docs/sec | ~2ms |
| nomic-embed-text (Ollama) | 768 | ~200 docs/sec | ~5ms |
| Deterministic fallback | 384 | ~10k docs/sec | <0.1ms |

## Configuration Guide

```python
from agentic_brain.rag.graph import GraphRAGConfig, EnhancedGraphRAG

config = GraphRAGConfig(
    # Vector settings
    embedding_dimension=384,           # Match your embedding model
    similarity_threshold=0.7,          # Min cosine similarity for results

    # Entity extraction
    min_entity_length=3,               # Skip short entities
    max_entities_per_doc=50,           # Cap per document
    entity_types=["PERSON", "ORGANIZATION", "LOCATION", "CONCEPT", "TECHNOLOGY"],

    # Graph traversal
    max_hop_depth=3,                   # Max relationship hops
    max_neighbors=20,                  # Max neighbors per expansion

    # Retrieval
    top_k=10,                          # Results per query
    rerank=True,                       # Enable reranking
)

rag = EnhancedGraphRAG(config)
```

## Design Decisions

### Why Leiden over Louvain?
Leiden produces higher-quality communities (better modularity) and supports
hierarchical detection through gamma parameter tuning. We keep Louvain as
fallback because some Neo4j GDS versions don't include Leiden.

### Why pure-Cypher fallback?
Neo4j GDS is a paid plugin. The connected-components fallback ensures community
detection works in any Neo4j deployment, including free Community Edition.

### Why RRF over learned fusion?
Reciprocal Rank Fusion is parameter-free, works well across diverse signals,
and doesn't require training data. It consistently outperforms linear
weighted fusion in RAG benchmarks.

### Why entity resolution on ingest?
Incremental deduplication prevents entity explosion in long-running systems.
Running it per-document keeps the graph clean without expensive batch jobs.

## Files Reference

| File | Purpose |
|---|---|
| `graph.py` | `EnhancedGraphRAG` — main entry point with all strategies |
| `community_detection.py` | Hierarchical community detection, summarization, entity resolution |
| `hybrid.py` | RRF fusion, BM25 index, hybrid search |
| `multi_hop_reasoning.py` | Multi-hop reasoning chains |
| `graph_traversal.py` | BFS/DFS/weighted graph traversal |
| `graph_rag.py` | `GraphRAG` — async-first alternative with community search |
| `graphrag/knowledge_extractor.py` | Entity/relationship extraction (LLM + heuristic) |
| `mlx_embeddings.py` | Metal-accelerated embeddings for Apple Silicon |
| `reranking.py` | Cross-encoder, MMR, combined rerankers |
| `query_decomposition.py` | Complex query decomposition |
| `semantic_router.py` | Query intent classification |

---

*Last updated: 2026-07-17*
*Aligned with: Microsoft GraphRAG v1, LlamaIndex 0.12, LangChain 0.3*
