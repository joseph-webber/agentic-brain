# Integrations (Enhanced)

This guide documents the **optional integrations** bundled under the enhanced extras, plus the built-in routing, GraphRAG, and chunking capabilities that ship with Agentic Brain.

- **Built-in LLM router** (`agentic_brain.router.LLMRouter`) — multi-provider routing, alias resolution, retries, backoff, and cost tracking
- **Built-in GraphRAG** (`agentic_brain.rag.graph_rag`, `agentic_brain.rag.graph`, `agentic_brain.rag.graphrag`) — graph extraction, hybrid retrieval, and Neo4j-native graph workflows
- **Chonkie** (`chonkie`) — fast chunking for RAG preprocessing

> These integrations are optional. Install only what you need.
>
> Agentic Brain already includes a built-in memory system (`agentic_brain.memory.UnifiedMemory`) with session, long-term, semantic, and episodic memory backed by SQLite with optional Neo4j.

## Install

From PyPI:

```bash
pip install "agentic-brain[enhanced]"
```

From a local checkout:

```bash
pip install -e ".[enhanced]"
```

Install individually:

```bash
pip install "agentic-brain[documents]"   # PDF, DOCX, PPTX, XLSX, etc.
pip install "agentic-brain[graphrag]"    # Optional neo4j-graphrag experiments
pip install "agentic-brain[chonkie]"     # Chonkie chunking
```

---

## 1) Built-in LLM routing

### What it does
Agentic Brain ships a built-in router (`agentic_brain.router.LLMRouter`) for local-first multi-provider fallback without forcing an extra abstraction layer.

### What it supports
- local-first routing for Ollama
- cloud fallback for Anthropic and OpenAI
- task-aware routing for fast, reasoning, and code requests
- friendly model aliases (`claude`, `gpt-fast`, `local`, etc.)
- one normalized `messages` format across Ollama, OpenAI, and Anthropic
- rate-limit aware retries with exponential backoff
- token and estimated-cost tracking
- semantic caching to reduce repeated spend

### Example

```python
import asyncio
from agentic_brain.router import LLMRouter

async def main():
    router = LLMRouter()
    response = await router.chat(
        message="Explain the latest GraphRAG release changes",
        model="claude",
    )
    print(response.provider, response.model)
    print(response.content)

asyncio.run(main())
```

---

## 2) Document parsing — built-in loaders

### What it does
Agentic Brain includes 155+ loader classes in `src/agentic_brain/rag/loaders/` covering major document formats and app integrations without forcing a heavyweight parser stack.

### Supported formats
PDF, DOCX, PPTX, XLSX, CSV, JSON, YAML, HTML, XML, RTF, ODF, EPUB, and many more.

### Example

```python
from agentic_brain.rag.loaders.pdf import PDFLoader
from agentic_brain.rag.loaders.docx import DocxLoader

pdf_loader = PDFLoader(ocr_enabled=True)
pdf_doc = pdf_loader.load_document("report.pdf")

docx_loader = DocxLoader()
docx_doc = docx_loader.load_document("report.docx")
```

---

## 3) Built-in GraphRAG

Agentic Brain now exposes GraphRAG as a **layered architecture** rather than a single integration point:

- **`KnowledgeExtractor`** (`agentic_brain.rag.graphrag`) for entity extraction, relationship persistence, and safe Text2Cypher queries
- **`GraphRAG`** (`agentic_brain.rag.graph_rag`) for ingestion, embedding-aware search strategies, and community-oriented workflows
- **`EnhancedGraphRAG`** (`agentic_brain.rag.graph`) for production Neo4j vector indexing, chunk storage, and reciprocal-rank-fusion hybrid retrieval

### GraphRAG architecture

```text
Documents / APIs / Events
        |
        v
 Chunking + Embeddings -------------------------+
        |                                       |
        v                                       v
Graph extraction (entities + relationships)   Vector index / chunk store
        |                                       |
        +--------------- Neo4j -----------------+
                        |
                        v
      Hybrid retrieval (vector + graph + rerank)
                        |
                        v
      Natural-language graph query / answer generation
```

### Vector + graph hybrid search

Hybrid retrieval combines two signals:

1. **Vector similarity** finds semantically similar chunks or entities from embeddings.
2. **Graph traversal** expands those hits through `MENTIONS`, `CONTAINS`, and `RELATES_TO` edges.

In production, `EnhancedGraphRAG` merges both ranked lists with **reciprocal rank fusion (RRF)** so consensus hits score highest. When the Neo4j vector index is unavailable, it falls back to text matching instead of failing the request.

### Community detection (Leiden)

The GraphRAG pipeline exposes `enable_communities` and `community_algorithm` in `GraphRAGConfig` so you can add a graph analytics stage after ingestion. The built-in ingestion pipeline tracks this stage and the extracted schema (`Entity` + `RELATES_TO`) is compatible with Neo4j GDS.

For production analytics we recommend **Leiden** for dense knowledge graphs because it produces stable, well-separated communities. Example GDS workflow after ingestion:

```cypher
CALL gds.graph.project(
  'graphrag-entities',
  'Entity',
  {RELATES_TO: {orientation: 'UNDIRECTED'}}
);

CALL gds.leiden.write('graphrag-entities', {
  writeProperty: 'communityId',
  includeIntermediateCommunities: true
})
YIELD communityCount, modularity;
```

### Embedding integration

GraphRAG integrates with the existing embedding stack in two places:

- `GraphRAG` lazily uses `MLXEmbeddings` when available and falls back deterministically when local accelerators are unavailable
- `EnhancedGraphRAG` stores chunk embeddings in Neo4j and queries them through Neo4j's native vector index
- `KnowledgeExtractor` accepts an `embedder=` hook so you can wire graph extraction into a broader hybrid pipeline

Recommended flow:

1. Chunk documents with `rag.chunking` or Chonkie
2. Generate embeddings with `agentic_brain.rag.embeddings`
3. Persist chunks and graph structure into Neo4j
4. Retrieve with vector, graph, hybrid, or community strategy

### Feature guide

| Feature | Module | What it does |
|---|---|---|
| Graph extraction | `agentic_brain.rag.graphrag.KnowledgeExtractor` | Extracts entities and relationships, persists `SourceDocument`, `Entity`, and `RELATES_TO` data |
| Natural-language graph query | `KnowledgeExtractor.query()` | Uses safe read-only Text2Cypher with keyword fallback |
| End-to-end GraphRAG | `agentic_brain.rag.graph_rag.GraphRAG` | Ingests graph documents, stores entity embeddings, exposes search strategies |
| Production hybrid retrieval | `agentic_brain.rag.graph.EnhancedGraphRAG` | Indexes chunks, uses Neo4j vector search, fuses vector and graph rankings |
| Community analysis | Neo4j GDS + GraphRAG schema | Runs Leiden/Louvain-style clustering over extracted entity graphs |

### Example: extract knowledge

```python
from agentic_brain.rag.graphrag import KnowledgeExtractor, KnowledgeExtractorConfig


class MyLLM:
    def generate(self, prompt: str, **kwargs) -> str:
        return '{"entities":[{"name":"Alice","type":"Person"},{"name":"Acme Corp","type":"Organization"}],"relationships":[{"source":"Alice","target":"Acme Corp","type":"WORKS_AT","evidence":"Alice works at Acme Corp."}]}'


extractor = KnowledgeExtractor(KnowledgeExtractorConfig(), llm=MyLLM())
result = extractor.extract_from_text_sync("Alice works at Acme Corp.")
print(result.entity_count, result.relationship_count, result.metadata["pipeline"])
```

### Example: graph query with safe fallback

```python
from agentic_brain.rag.graphrag import KnowledgeExtractor, KnowledgeExtractorConfig


class MyLLM:
    def generate(self, prompt: str, **kwargs) -> str:
        return '{"cypher":"MATCH (d:SourceDocument)-[:MENTIONS]->(e:Entity) WHERE toLower(e.name) CONTAINS $name RETURN d.content AS content, e.name AS entity","params":{"name":"alice"},"reasoning":"lookup by entity name"}'


extractor = KnowledgeExtractor(KnowledgeExtractorConfig(), llm=MyLLM())
response = extractor.query("Where does Alice work?")
print(response.mode)
print(response.metadata["cypher"])
```

### Example: production hybrid retrieval

```python
import asyncio
from agentic_brain.rag.graph import EnhancedGraphRAG

async def main():
    rag = EnhancedGraphRAG()
    await rag.initialize()
    await rag.index_document("Alice works at Acme Corp in Adelaide.", doc_id="doc-1")
    results = await rag.retrieve("Where does Alice work?", strategy="hybrid")
    print(results[0]["strategy"], results[0]["score"])

asyncio.run(main())
```

For the complete guide, see [GRAPHRAG.md](GRAPHRAG.md).

---

## 4) Chonkie — fast chunking

### What it does
Chonkie provides high-performance chunking for RAG preprocessing.

### Strategies
- `token` — fastest, fixed-size chunks
- `sentence` — preserves sentence boundaries
- `semantic` — embedding-aware chunking (requires `chonkie[semantic]`)

### Example

```python
from agentic_brain.rag.chunking import ChonkieChunker

chunker = ChonkieChunker(strategy="token", chunk_size=512, overlap=50)
chunks = chunker.chunk("Your long document text here...")

print("chunks=", len(chunks))
print(chunks[0].metadata)
```

---

## Troubleshooting

- If you see `ImportError: ... Install with: pip install 'agentic-brain[...]'`, install the referenced extra.
- For Neo4j-backed features, ensure Neo4j is running and `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` are set correctly.
- For Neo4j native vector search, use Neo4j 5.11+ and create the vector index before relying on `EnhancedGraphRAG._vector_retrieve()`.
- For Leiden community detection, install the Neo4j Graph Data Science plugin and run the GDS projection/write steps after ingestion.
- For prompt-based extraction or Text2Cypher, provide an LLM client that implements `generate()`, `chat_sync()`, or `chat()`.
