# Integrations (Enhanced)

This guide documents the **new optional integrations** bundled under the `enhanced` extras:

- **Mem0** (`mem0ai`) — persistent memory service
- **LiteLLM** (`litellm`) — unified LLM routing + fallbacks + cost tracking
- **Docling** (`docling`) — document parsing / conversion
- **neo4j-graphrag** (`neo4j-graphrag`) — knowledge extraction + GraphRAG workflows
- **Chonkie** (`chonkie`) — fast chunking for RAG preprocessing

> These are **optional dependencies**. Install only what you need.

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
pip install "agentic-brain[memory]"       # Mem0
pip install "agentic-brain[llm-routing]"  # LiteLLM
pip install "agentic-brain[docling]"      # Docling
pip install "agentic-brain[graphrag]"     # neo4j-graphrag
pip install "agentic-brain[chonkie]"      # Chonkie
```

---

## 1) Mem0 — Persistent memory service

### What it does
Mem0 is a **persistent memory layer** for agent systems. It can store “memories” and later retrieve them via semantic search.

A common production setup is:
- **Neo4j** as a *graph store* (entities + relationships)
- a *vector store* (semantic recall)
- an *embedder* (to create vectors)
- optionally an *LLM* (to extract structured facts/relations)

### How to use

```python
import os
from mem0 import Memory

config = {
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "url": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "username": os.getenv("NEO4J_USER", "neo4j"),
            "password": os.getenv("NEO4J_PASSWORD", "your-password"),
        },
    },
    # Optionally add an embedder + vector store + llm here
}

memory = Memory.from_config(config)

memory.add("Joseph prefers bullet lists.", user_id="joseph")
results = memory.search("formatting preferences", user_id="joseph", limit=5)
print(results)
```

### Configuration options
Mem0’s configuration is provided as a Python dict to `Memory.from_config()`.

At minimum for Neo4j graph storage you’ll need:

- `NEO4J_URI` (e.g. `bolt://localhost:7687`)
- `NEO4J_USER` (e.g. `neo4j`)
- `NEO4J_PASSWORD`

If you enable an LLM and/or embedder (for extraction + semantic recall), you’ll also need provider keys (for example `OPENAI_API_KEY`).

### Example code (graph + embedder + LLM)

```python
import os
from mem0 import Memory

config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "temperature": 0.2,
            "api_key": os.environ["OPENAI_API_KEY"],
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
            "api_key": os.environ["OPENAI_API_KEY"],
        },
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "url": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "username": os.getenv("NEO4J_USER", "neo4j"),
            "password": os.environ["NEO4J_PASSWORD"],
        },
    },
}

memory = Memory.from_config(config)

conversation = [
    {"role": "user", "content": "Alice works at Acme Corp."},
    {"role": "user", "content": "Bob manages Alice."},
]

memory.add(conversation, user_id="demo")
print(memory.search("Who manages Alice?", user_id="demo", limit=3))
```

---

## 2) LiteLLM — LLM routing

### What it does
LiteLLM provides a **single Python API** for many LLM providers and adds:
- **fallback models**
- **retries**
- **token + cost estimation**

Agentic Brain also ships a built-in router (`agentic_brain.router.LLMRouter`) for multi-provider fallback (local-first). LiteLLM is useful when you want:
- access to additional providers through a single interface
- the LiteLLM proxy for centralised logging/budgeting

### Supported models
LiteLLM supports provider-native model identifiers, for example:
- OpenAI: `gpt-4o`, `gpt-4o-mini`
- Anthropic: `claude-3-5-sonnet-20241022`, `claude-3-haiku-20240307`
- Azure OpenAI: `azure/<deployment-name>`

### Fallback configuration

```python
from litellm import completion

messages = [{"role": "user", "content": "Summarise this paragraph."}]

resp = completion(
    model="gpt-4o-mini",
    messages=messages,
    # Ordered fallback list if the primary fails
    fallbacks=["gpt-4o", "claude-3-haiku-20240307"],
)

print(resp.choices[0].message["content"])
```

### Cost tracking

```python
from litellm import completion, completion_cost

resp = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a haiku about Neo4j."}],
)

print(resp.choices[0].message["content"])
print("estimated_cost_usd=", float(completion_cost(completion_response=resp)))
```

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

## 3) Docling — Document parsing

### What it does
Docling converts documents into structured representations and exports (commonly **Markdown**), with optional OCR and table structure extraction.

### Supported formats
Docling supports many formats (PDF, Office files, HTML, images, etc.). The exact list depends on your Docling version and installed backends.

### Usage patterns

#### Convert one file → Markdown

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("report.pdf")

markdown = result.document.export_to_markdown()
print(markdown)
```

#### Batch conversion

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
results = converter.convert_all(["a.pdf", "b.docx", "c.png"])

for r in results:
    print(r.document.export_to_markdown()[:200])
```

### Export options
Common exports:
- `result.document.export_to_markdown()`
- (Depending on Docling version) JSON exports / structured objects for tables, pages, etc.

### Example code (OCR + better tables)
Docling exposes pipeline options; the API surface can vary by version.

```python
from docling.document_converter import DocumentConverter

# Many Docling builds allow enabling OCR/table structure via pipeline options.
# See Docling docs for the exact option classes for your version.
converter = DocumentConverter()
result = converter.convert("scanned.pdf")
print(result.document.export_to_markdown())
```

---

## 4) neo4j-graphrag — Knowledge extraction

### What it does
`neo4j-graphrag` helps you build a **knowledge graph in Neo4j** from raw text, then answer questions using **GraphRAG** (graph + vector retrieval grounded generation).

Typical phases:
1. **Extract entities + relations** into Neo4j
2. **Retrieve context** (vector/hybrid + graph traversal)
3. **Generate** an answer grounded in retrieved context

### Entity extraction

```python
from neo4j import GraphDatabase

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "your-password")
driver = GraphDatabase.driver(URI, auth=AUTH)

from neo4j_graphrag.experimental.builders import SimpleKGPipeline
from neo4j_graphrag.llm import OpenAILLM

llm = OpenAILLM(model_name="gpt-4o-mini", model_params={"temperature": 0})
kg = SimpleKGPipeline(driver=driver, llm=llm)
kg.run(chunks=[
    "Alice works at Acme Corp.",
    "Bob manages Alice.",
])
```

### Natural language queries

```python
from neo4j import GraphDatabase
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import VectorRetriever

driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "your-password"))

embedder = OpenAIEmbeddings(model="text-embedding-3-large")
retriever = VectorRetriever(driver, index_name="your-index", embedder=embedder)
llm = OpenAILLM(model_name="gpt-4o-mini")

rag = GraphRAG(retriever=retriever, llm=llm)
resp = rag.search(query_text="Who manages Alice?", retriever_config={"top_k": 5})
print(resp.answer)
```

### Neo4j integration
You are responsible for:
- A running Neo4j instance
- Any required vector indexes (index naming, dimensions, similarity function, etc.)
- Provider credentials (e.g. `OPENAI_API_KEY`) for the LLM/embedder you choose

---

## 5) Chonkie — Fast chunking

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
- For Neo4j-backed features (Mem0, neo4j-graphrag), ensure Neo4j is running and `NEO4J_URI/USER/PASSWORD` are set correctly.
- For cloud LLMs (LiteLLM / neo4j-graphrag examples), set provider API keys such as `OPENAI_API_KEY`.
