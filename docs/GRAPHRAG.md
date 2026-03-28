# GraphRAG

Comprehensive guide to Agentic Brain's GraphRAG stack.

Agentic Brain exposes GraphRAG through **three complementary layers**:

1. **`agentic_brain.rag.graphrag.KnowledgeExtractor`** — lightweight entity extraction, relationship persistence, and safe natural-language graph queries
2. **`agentic_brain.rag.graph_rag.GraphRAG`** — end-to-end ingest and search pipeline with vector, graph, hybrid, community, and multi-hop search strategies
3. **`agentic_brain.rag.graph.EnhancedGraphRAG`** — production-oriented Neo4j vector search, chunk indexing, and reciprocal-rank-fusion hybrid retrieval

Use the layer that matches your job:

- need graph extraction from raw text → `KnowledgeExtractor`
- need a simple GraphRAG pipeline with multiple search strategies → `GraphRAG`
- need Neo4j-native vector indexing and chunk retrieval → `EnhancedGraphRAG`

---

## Architecture

```text
                 ┌──────────────────────────────┐
                 │        Data sources          │
                 │ docs · APIs · chat · events  │
                 └──────────────┬───────────────┘
                                │
                     chunking + loader pipeline
                                │
                  ┌─────────────┴─────────────┐
                  │                           │
                  v                           v
        embedding generation          graph extraction
      (MLX / sentence-transformers)  (entities + relations)
                  │                           │
                  └─────────────┬─────────────┘
                                v
                             Neo4j
            chunks + vectors + documents + entities + edges
                                │
              ┌─────────────────┼──────────────────┐
              v                 v                  v
        vector search     graph traversal   community analysis
              \_________________|__________________/
                                v
                      hybrid rerank / answer step
```

### What each layer owns

| Layer | Responsibilities |
|---|---|
| `KnowledgeExtractor` | `SourceDocument` + `Entity` schema, `MENTIONS` / `RELATES_TO` edges, safe Text2Cypher, heuristic fallback |
| `GraphRAG` | Ingest workflow, entity embeddings, basic strategy selection (`VECTOR`, `GRAPH`, `HYBRID`, `COMMUNITY`, `MULTI_HOP`) |
| `EnhancedGraphRAG` | `Document` / `Chunk` / `Entity` schema, Neo4j vector index, graph traversal scoring, reciprocal-rank fusion |

---

## Core concepts

### Vector + graph hybrid search

GraphRAG combines two ranking signals:

- **Vector similarity** answers “what is semantically close to this query?”
- **Graph traversal** answers “what is structurally connected to the matched entities or chunks?”

`EnhancedGraphRAG` merges both via **reciprocal rank fusion (RRF)**. This rewards chunks that score well in both lists.

### Community detection (Leiden)

Community detection groups related entities into higher-level topics or themes. Agentic Brain's graph schema is compatible with Neo4j GDS, so you can run **Leiden** or **Louvain** after ingestion.

- `GraphRAGConfig.enable_communities` controls whether the pipeline should include the community-analysis stage
- `GraphRAGConfig.community_algorithm` lets you record the intended algorithm name
- `EnhancedGraphRAG` exposes a `community` retrieval strategy placeholder that can be upgraded with GDS-backed clustering

**Recommendation:** use **Leiden** in production because it generally yields cleaner, more stable communities on dense graphs.

### Embedding integration

Embedding generation plugs into GraphRAG in three ways:

1. `GraphRAG` uses MLX embeddings when available and falls back deterministically when they are not
2. `EnhancedGraphRAG` stores chunk embeddings for Neo4j vector search
3. `KnowledgeExtractor` accepts an `embedder=` hook so graph extraction can join a custom retrieval pipeline

---

## Installation

### Core GraphRAG

```bash
pip install agentic-brain neo4j
```

### Recommended extras

```bash
pip install "agentic-brain[enhanced]"
```

### Optional extras

```bash
pip install "agentic-brain[graphrag]"   # Optional neo4j-graphrag experiments
pip install "agentic-brain[chonkie]"    # Fast chunking
pip install "agentic-brain[embeddings]" # Sentence-transformers / torch
```

### Neo4j requirements

- Neo4j running locally or remotely
- Neo4j 5.11+ recommended for native vector index search
- Neo4j Graph Data Science plugin required for Leiden/Louvain analytics

---

## Quick start

### 1) Extract a graph from text

```python
from agentic_brain.rag.graphrag import KnowledgeExtractor, KnowledgeExtractorConfig

extractor = KnowledgeExtractor(
    KnowledgeExtractorConfig(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="your-password",
        database="neo4j",
    )
)

result = extractor.extract_from_text_sync(
    "Alice works at Acme Corp in Adelaide. Alice mentors Bob.",
    document_id="doc-1",
)

print(result.entity_count)
print(result.relationship_count)
print(result.metadata["pipeline"])
```

### 2) Query the extracted graph in natural language

```python
from agentic_brain.rag.graphrag import KnowledgeExtractor, KnowledgeExtractorConfig


class GraphLLM:
    def generate(self, prompt: str, **kwargs) -> str:
        return '{"cypher":"MATCH (d:SourceDocument)-[:MENTIONS]->(e:Entity) WHERE toLower(e.name) CONTAINS $name RETURN d.content AS content, e.name AS entity","params":{"name":"alice"},"reasoning":"lookup by entity name"}'


extractor = KnowledgeExtractor(KnowledgeExtractorConfig(), llm=GraphLLM())
response = extractor.query("Where does Alice work?")

print(response.mode)
print(response.results)
```

### 3) Use end-to-end GraphRAG search strategies

```python
import asyncio
from agentic_brain.rag.graph_rag import GraphRAG, GraphRAGConfig, SearchStrategy

async def main():
    rag = GraphRAG(GraphRAGConfig(enable_communities=True, community_algorithm="leiden"))

    await rag.ingest([
        {"content": "Alice works at Acme Corp in Adelaide."},
        {"content": "Bob works with Alice on the GraphRAG team."},
    ])

    vector_results = await rag.search("Where does Alice work?", strategy=SearchStrategy.VECTOR)
    hybrid_results = await rag.search("Where does Alice work?", strategy=SearchStrategy.HYBRID)

    print(vector_results[0])
    print(hybrid_results[0])

asyncio.run(main())
```

### 4) Production retrieval with Neo4j vector index

```python
import asyncio
from agentic_brain.rag.graph import EnhancedGraphRAG

async def main():
    rag = EnhancedGraphRAG()
    await rag.initialize()

    await rag.index_document(
        "GraphRAG combines vector search with graph traversal.",
        doc_id="doc-graph",
        metadata={"source": "docs"},
    )

    results = await rag.retrieve("How does GraphRAG work?", strategy="hybrid")
    print(results[0]["fusion_method"], results[0]["score"])

asyncio.run(main())
```

---

## How to use each feature

### Knowledge extraction

Use `KnowledgeExtractor` when you want a graph built from raw text with minimal setup.

#### Heuristic extraction
- works without an LLM
- finds candidate entities with capitalization and hint-based typing
- infers common relationship types such as `WORKS_AT`, `LOCATED_IN`, `PART_OF`, and `RELATED_TO`

```python
extractor = KnowledgeExtractor(KnowledgeExtractorConfig())
result = extractor.extract_from_text_sync(text, use_graphrag_pipeline=False)
```

#### LLM-assisted extraction
- pass an object implementing `generate()`, `chat_sync()`, or `chat()`
- the LLM returns strict JSON for entities and relationships
- if extraction fails and `on_error="IGNORE"`, the extractor falls back to heuristics

```python
extractor = KnowledgeExtractor(KnowledgeExtractorConfig(on_error="IGNORE"), llm=my_llm)
result = extractor.extract_from_text_sync(text, use_graphrag_pipeline=True)
```

#### Safe Text2Cypher
- `query()` asks the LLM for **read-only Cypher only**
- unsafe Cypher (`CREATE`, `DELETE`, `CALL`, `APOC`, etc.) is rejected
- the extractor then falls back to keyword graph search

This gives you a natural-language interface without trusting arbitrary generated Cypher.

### GraphRAG search strategies

`GraphRAG.search()` supports multiple strategies through `SearchStrategy`:

| Strategy | Use when | Notes |
|---|---|---|
| `VECTOR` | You need semantic similarity first | Embeds the query and returns vector-style hits |
| `GRAPH` | You want direct graph relationships | Traverses connections from matched entities |
| `HYBRID` | You want the best default | Combines vector matches with graph expansion |
| `COMMUNITY` | You need topic-level grouping | Community-aware stage; pair with GDS for production |
| `MULTI_HOP` | You need reasoning across chains | Reserved for deeper traversal workflows |

### Enhanced hybrid retrieval

`EnhancedGraphRAG.retrieve(strategy="hybrid")` runs:

1. vector search against Neo4j chunk embeddings
2. graph retrieval from matched entities/documents
3. reciprocal-rank fusion
4. reranked results with `vector_score`, `graph_score`, `rrf_score`, and `fusion_method`

This is the most complete retrieval path currently documented in the codebase.

### Community detection with Leiden

After indexing documents and entities, run Neo4j GDS on the `Entity` graph.

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

You can then retrieve by community:

```cypher
MATCH (e:Entity)
WHERE e.communityId = $community_id
MATCH (d:Document)-[:MENTIONS]->(e)
RETURN d.id, d.content
LIMIT 10;
```

### Embedding integration patterns

#### Reuse existing embeddings

`EnhancedGraphRAG.index_document()` accepts an optional `embedding=` parameter. If you already computed a document embedding upstream, you can reuse it for chunk insertion.

#### Use MLX on Apple Silicon

`GraphRAG` and `EnhancedGraphRAG` both lazy-load MLX embeddings when available, so local Apple Silicon deployments get faster embedding generation without extra wiring.

#### Provide a custom embedder

```python
class MyEmbedder:
    def embed(self, text: str) -> list[float]:
        return [0.0] * 384

extractor = KnowledgeExtractor(KnowledgeExtractorConfig(), embedder=MyEmbedder())
```

The extractor's embedder hook is the right integration point when you need graph extraction to participate in a wider hybrid retrieval flow.

---

## Configuration options

### `KnowledgeExtractorConfig`

| Field | Default | Description |
|---|---|---|
| `uri` | `bolt://localhost:7687` | Neo4j URI |
| `user` | `neo4j` | Neo4j username |
| `password` | `Brain2026` or `NEO4J_PASSWORD` | Neo4j password |
| `database` | `neo4j` | Neo4j database name |
| `use_connection_pool` | `True` | Use shared Neo4j pool helpers |
| `create_schema` | `True` | Create constraints and indexes on startup |
| `perform_entity_resolution` | `True` | Reserved for higher-level entity resolution flows |
| `on_error` | `IGNORE` | `IGNORE` falls back gracefully, other values raise |
| `max_entities` | `50` | Cap extracted entities per document |
| `schema` | built-in defaults | Allowed node types, relationship types, and patterns |

### `GraphRAGConfig` (`agentic_brain.rag.graph_rag`)

| Field | Default | Description |
|---|---|---|
| `neo4j_uri` | `bolt://localhost:7687` | Neo4j URI |
| `neo4j_user` | `neo4j` | Neo4j user |
| `neo4j_password` | env-backed | Neo4j password |
| `embedding_dim` | `384` | Embedding dimensionality |
| `embedding_model` | `all-MiniLM-L6-v2` | Preferred embedding model label |
| `similarity_threshold` | `0.7` | Similarity cutoff |
| `chunk_size` | `512` | Chunk size for ingestion |
| `chunk_overlap` | `50` | Chunk overlap |
| `max_hops` | `3` | Multi-hop traversal depth |
| `max_relationships` | `50` | Max relationships to ingest per document |
| `enable_communities` | `True` | Include community stage |
| `community_algorithm` | `louvain` | Algorithm label for community stage; set to `leiden` for GDS workflows |
| `cache_embeddings` | `True` | Enable embedding cache |
| `cache_ttl` | `3600` | Embedding cache TTL in seconds |

### `GraphRAGConfig` (`agentic_brain.rag.graph`)

| Field | Default | Description |
|---|---|---|
| `use_pool` | `True` | Use shared Neo4j session pool |
| `embedding_dimension` | `384` | Chunk embedding dimension |
| `vector_index_name` | `VECTOR_INDEX_NAME` | Neo4j vector index to query |
| `similarity_threshold` | `0.7` | Similarity threshold |
| `min_entity_length` | `3` | Minimum entity token length |
| `max_entities_per_doc` | `50` | Max entities stored per doc |
| `entity_types` | built-in list | Allowed entity types |
| `max_hop_depth` | `3` | Traversal depth |
| `max_neighbors` | `20` | Neighbor cap during traversal |
| `relationship_weights` | built-in weights | Relative weights for graph scoring |
| `top_k` | `10` | Default result count |
| `include_metadata` | `True` | Include metadata in results |
| `rerank` | `True` | Enable result reranking |

### Environment variables

- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`
- any embedding provider variables needed by your chosen embedding backend

---

## Examples

### Example: docs + graph + vector workflow

```python
import asyncio
from agentic_brain.rag.graph import EnhancedGraphRAG
from agentic_brain.rag.loaders.pdf import PDFLoader

async def main():
    loader = PDFLoader()
    document = loader.load_document("architecture.pdf")

    rag = EnhancedGraphRAG()
    await rag.initialize()
    await rag.index_document(document.content, doc_id="architecture-pdf")

    results = await rag.retrieve("How do services communicate?", strategy="hybrid")
    for item in results[:3]:
        print(item["doc_id"], item["score"], item["strategy"])

asyncio.run(main())
```

### Example: extraction + Text2Cypher + fallback

```python
extractor = KnowledgeExtractor(KnowledgeExtractorConfig(), llm=my_llm)
extractor.extract_from_text_sync("Paul Atreides rules Caladan.")

answer = extractor.query("Who rules Caladan?")
print(answer.mode)         # text2cypher or keyword_fallback
print(answer.metadata)
```

### Example: community-centric review

1. ingest documents with `GraphRAG` or `EnhancedGraphRAG`
2. project `Entity` nodes into Neo4j GDS
3. run Leiden write-back
4. summarize each community with your LLM
5. route broad exploratory questions to the community layer first, then to hybrid retrieval

---

## Troubleshooting

### Neo4j vector search fails
Use Neo4j 5.11+ and create the vector index before calling vector retrieval. `EnhancedGraphRAG` will fall back to plain text matching when the index is unavailable.

### LLM-generated Cypher is rejected
This is expected for unsafe queries. `KnowledgeExtractor.query()` rejects write-capable Cypher and drops back to keyword graph search.

### Community retrieval is empty
The built-in community retrieval path is intentionally conservative. Install Neo4j GDS and run Leiden or Louvain explicitly after ingestion.

### Extraction quality is low
Start with heuristic extraction, inspect entities, then add an LLM that returns strict JSON. Keep `on_error="IGNORE"` during rollout so the system degrades gracefully.

---

## Related docs

- [INTEGRATIONS.md](INTEGRATIONS.md)
- [VECTOR_EMBEDDINGS.md](VECTOR_EMBEDDINGS.md)
- [RAG_GUIDE.md](RAG_GUIDE.md)
- [integrations/NEO4J.md](integrations/NEO4J.md)
