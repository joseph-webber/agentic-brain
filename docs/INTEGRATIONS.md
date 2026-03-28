# Integrations (Enhanced)

This guide documents the **new optional integrations** bundled under the `enhanced` extras, plus the built-in LLM router and Neo4j graph tooling that ship with agentic-brain:

- **Built-in LLM router** (`agentic_brain.router.LLMRouter`) — multi-provider routing + fallbacks with no extra dependency
- **Built-in Neo4j graph extraction** (`agentic_brain.rag.graphrag`) — lightweight entity extraction + prompt-based Text2Cypher without heavy extras
- **Chonkie** (`chonkie`) — fast chunking for RAG preprocessing

> These are **optional dependencies**. Install only what you need.
>
> **Note on memory:** agentic-brain ships a full built-in memory system
> (`agentic_brain.memory.UnifiedMemory`) with 4-type architecture
> (session, long-term, semantic, episodic), hybrid FTS + semantic search,
> and importance scoring — all backed by SQLite with optional Neo4j.
> No external memory library is needed.

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
pip install "agentic-brain[documents]"    # PDF, DOCX, PPTX, XLSX, etc.
# Graph extraction is built in; no extra required
pip install "agentic-brain[chonkie]"      # Chonkie
```

---

## 1) Built-in LLM routing

### What it does
Agentic Brain already ships a built-in router (`agentic_brain.router.LLMRouter`) for multi-provider fallback (local-first). It covers the providers used in this repo without pulling in an extra abstraction layer.

### What it supports
- **local-first routing** for Ollama
- **cloud fallback** for Anthropic, OpenAI, OpenRouter, Groq, Together, Google, and xAI
- **task-aware routing** (fast/simple vs reasoning vs code)
- **context-aware fallback chains** such as Claude → GPT → Ollama for coding requests
- **token usage tracking** per provider
- **semantic caching** to reduce repeated spend

### Example code (Agentic Brain router)

```python
import asyncio
from agentic_brain.router import LLMRouter

async def main():
    router = LLMRouter()
    r = await router.chat("Hello from the Agentic Brain router")
    print(r.provider, r.model)
    print(r.content)

asyncio.run(main())
```

---

## 2) Document Parsing — Built-in loaders

### What it does
Agentic Brain includes **102 built-in loader classes** in `src/agentic_brain/rag/loaders/` covering all major document formats without heavy external dependencies.

### Supported formats
PDF (PyPDF2 + pdfplumber + OCR fallback), DOCX, PPTX, XLSX, CSV, JSON, YAML, HTML, XML, RTF, ODF, EPUB, and many more.

### Usage patterns

```python
from agentic_brain.rag.loaders.pdf import PDFLoader
from agentic_brain.rag.loaders.docx import DocxLoader

pdf_loader = PDFLoader(ocr_enabled=True)
doc = pdf_loader.load_document("report.pdf")

docx_loader = DocxLoader()
doc = docx_loader.load_document("report.docx")
```

Install all document format support:

```bash
pip install "agentic-brain[documents]"
```

---

## 3) Built-in Neo4j graph extraction

### What it does
Agentic Brain keeps graph extraction in-house because `neo4j-graphrag` brings in a heavier base dependency set (`numpy`, `scipy`, `pypdf`, and related transitive packages) than we need for core graph extraction.

The built-in extractor can:
- extract entities and relationships with lightweight heuristics
- upgrade to LLM-driven extraction when you pass an LLM client with `generate()`
- persist them with raw Cypher through the shared `neo4j_pool`
- answer graph questions with prompt-based read-only Text2Cypher and safe keyword fallback

Typical phases:
1. **Extract entities + relations** into Neo4j
2. **Query the graph** using safe prompt-generated Cypher
3. **Layer additional retrieval/generation** on top if your application needs it

### Entity extraction

```python
from agentic_brain.rag.graphrag import KnowledgeExtractor, KnowledgeExtractorConfig


class MyLLM:
    def generate(self, prompt: str, **kwargs) -> str:
        return '{"entities":[{"name":"Alice","type":"Person"},{"name":"Acme Corp","type":"Organization"}],"relationships":[{"source":"Alice","target":"Acme Corp","type":"WORKS_AT","evidence":"Alice works at Acme Corp."}]}'


extractor = KnowledgeExtractor(KnowledgeExtractorConfig(), llm=MyLLM())
result = extractor.extract_from_text_sync("Alice works at Acme Corp.")
print(result.entity_count, result.relationship_count, result.metadata["pipeline"])
```

### Natural language queries

```python
from agentic_brain.rag.graphrag import KnowledgeExtractor, KnowledgeExtractorConfig


class MyLLM:
    def generate(self, prompt: str, **kwargs) -> str:
        return '{"cypher":"MATCH (d:SourceDocument)-[:MENTIONS]->(e:Entity) WHERE toLower(e.name) CONTAINS $name RETURN d.content AS content, e.name AS entity","params":{"name":"alice"},"reasoning":"lookup by entity name"}'


extractor = KnowledgeExtractor(KnowledgeExtractorConfig(), llm=MyLLM())
resp = extractor.query("Where does Alice work?")
print(resp.mode, resp.metadata["cypher"])
```

### Neo4j integration
You are responsible for:
- A running Neo4j instance
- Providing an LLM client if you want prompt-based extraction/Text2Cypher
- Any higher-level vector indexing or answer-generation layers built on top of this graph

---

## 4) Chonkie — Fast chunking

### What it does
Chonkie provides high-performance chunking for RAG preprocessing.

Agentic Brain includes a wrapper chunker:
- `agentic_brain.rag.chunking.ChonkieChunker`

### Chunking strategies
- `token` — fastest, fixed-size chunks (good default)
- `sentence` — preserves sentence boundaries
- `semantic` — embedding-aware, best quality (requires `chonkie[semantic]`)

### Configuration

```python
from agentic_brain.rag.chunking import ChonkieChunker

chunker = ChonkieChunker(strategy="token", chunk_size=512, overlap=50)
chunks = chunker.chunk("Your long document text here...")

print("chunks=", len(chunks))
print(chunks[0].metadata)
```

### Performance / benchmarking

```python
from agentic_brain.rag.chunking import benchmark_chunkers

sample = "Hello world. " * 5000
results = benchmark_chunkers(sample, iterations=5)

for r in results:
    print(r.chunker_name, r.avg_time_ms, "speedup=", r.speedup_over)
```

---

## Troubleshooting

- If you see `ImportError: ... Install with: pip install 'agentic-brain[...]'`, install the referenced extra.
- For Neo4j-backed features, ensure Neo4j is running and `NEO4J_URI/USER/PASSWORD` are set correctly.
- For prompt-based extraction/Text2Cypher, configure whatever LLM client you pass into `KnowledgeExtractor`.
