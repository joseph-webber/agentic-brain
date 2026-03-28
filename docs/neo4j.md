# Neo4j Integration Guide

GraphRAG relies on Neo4j for both knowledge graph storage and vector similarity search. This guide explains how the latest 2.16.0 improvements make the integration faster and more resilient.

## Core integration features

1. **Async Neo4j driver support** — ingestion and retrieval use `neo4j.AsyncGraphDatabase` with graceful fallbacks to the pooled sync client.
2. **Transaction retries** — all queries run through `resilient_query_sync()` / `_retry_query()` helpers with exponential backoff so transient cluster errors never surface to users.
3. **Batched UNWIND writes** — every insert path (documents, chunks, entities, relationships, communities) uses `UNWIND` to avoid N+1 behavior.
4. **Hybrid search with RRF** — `EnhancedGraphRAG` combines vector, keyword, and graph traversal scores inside Neo4j before handing results back to the LLM.
5. **Leiden community detection** — community metadata is persisted via Neo4j Graph Data Science so downstream prompts know which subgraph generated an answer.
6. **MLX embeddings** — Apple Silicon deployments automatically compute real embeddings locally, then push them to Neo4j vector indexes.

---

## Connection strategies

```python
from agentic_brain.rag.graph_rag import GraphRAG

rag = GraphRAG()

async with rag._driver.session(database="neo4j") as session:
    await session.execute_write(store_chunks, chunks)
```

- The async driver is preferred so background ingestion does not block the event loop.
- `GraphRAGConfig.use_pool` (in `agentic_brain.rag.graph`) toggles between the global sync pool and direct driver creation when async is unavailable.
- When `neo4j` is missing, both classes raise a helpful `ImportError` instructing you to install `pip install neo4j`.

## Transaction retries

All helper functions wrap Neo4j transactions:

```python
from agentic_brain.core.neo4j_utils import resilient_query_sync

def store_chunks(session, chunks):
    return resilient_query_sync(
        session,
        """
        UNWIND $chunks AS ch
        MERGE (c:Chunk {id: ch.id})
        SET c += ch.props
        """,
        {"chunks": chunks},
    )
```

- Retries default to three attempts with exponential backoff and jitter.
- `TransientError`, `ServiceUnavailable`, and `ReadOnlyDatabase` automatically trigger a retry.
- After the final failure the original exception is raised with retry metadata.

## Batched UNWIND pipelines

- `EnhancedGraphRAG._store_entities()`, `_store_chunks()`, and `_link_entities()` all call `UNWIND` queries so every ingest round trip handles hundreds of rows.
- `KnowledgeExtractor` and `neo4j_memory.py` share the same pattern, guaranteeing O(n) write time.
- The batching helpers accept `batch_size` arguments if you need to tune for clusters with strict memory caps.

## MLX embeddings

```python
from agentic_brain.rag.graph import EnhancedGraphRAG

rag = EnhancedGraphRAG()
await rag.index_document(
    "GraphRAG combines vector search with graph traversal.",
    doc_id="doc-graph",
    metadata={"source": "docs"},
)
```

- `_get_mlx_embeddings()` lazily imports `MLXEmbeddings` and verifies hardware availability.
- When MLX is present, embeddings run on Metal (M1–M4) and produce the vectors persisted to Neo4j.
- Deterministic fallback embeddings only trigger when MLX/torch are truly unavailable, ensuring tests stay reproducible.

## Community detection (Leiden)

```cypher
CALL gds.graph.project(
  'graphrag-entities',
  'Entity',
  {RELATES_TO: {orientation: 'UNDIRECTED'}}
);

CALL gds.leiden.write('graphrag-entities', {
  writeProperty: 'communityId',
  includeIntermediateCommunities: true,
  gamma: 1.0
})
YIELD communityCount, modularity;
```

- `GraphRAGConfig.community_algorithm` now defaults to `"leiden"` to reflect this recommendation.
- Store `communityId` on `Entity` nodes, then let `EnhancedGraphRAG.retrieve(strategy="community")` filter or boost by community.

## Hybrid search with RRF

Neo4j holds all scoring inputs:

1. **Vector index** on `Chunk.embedding` via `CREATE VECTOR INDEX`.
2. **Fulltext index** on chunk/document text for BM25.
3. **Graph traversal** weights (`MENTIONS`, `RELATED_TO`, etc.).

`EnhancedGraphRAG.retrieve(strategy="hybrid")` fetches the top `k` from each source, then calculates reciprocal-rank fusion (`rrf_score`) before returning structured results (vector, keyword, graph scores plus provenance).

## Configuration checklist

| Requirement | Status |
|-------------|--------|
| Neo4j 5.11+ | ✅ Native vector indexes |
| GDS plugin 2.6+ | ✅ Leiden community detection |
| APOC (optional) | ✅ Convenience procedures (not required) |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | ✅ Read from env or config |
| Ports 7687 / 7474 | ✅ Required for Bolt/HTTP access |

Need more? See [docs/GRAPHRAG.md](GRAPHRAG.md) for API usage and [CHANGELOG.md](../CHANGELOG.md) for the latest improvements.


## Architecture references

For the public reference model behind this integration, see:

- [Neo4j Architecture](./NEO4J_ARCHITECTURE.md)
- [Neo4j Zones](./NEO4J_ZONES.md)
- [GraphRAG Guide](./GRAPHRAG.md)
