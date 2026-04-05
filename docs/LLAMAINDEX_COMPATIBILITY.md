# LlamaIndex Compatibility (Agentic Brain)

This project includes a **LlamaIndex compatibility layer** at:

- `agentic_brain/rag/llamaindex_compat.py`

It provides LlamaIndex-style APIs on top of Agentic Brain’s native RAG and GraphRAG stack.

## What’s supported

### Service configuration

- `Settings`: global defaults (llm, embed_model, chunk_size, chunk_overlap)
- `ServiceContext.from_defaults(...)`: captures service configuration
- Global helpers:
  - `set_global_service_context(ctx)`
  - `get_global_service_context()`

`ServiceContext.to_settings()` applies the context back onto `Settings`.

### Node parsing (text splitting)

Node parsers split documents into smaller nodes for indexing.

- `SentenceSplitter(chunk_size, chunk_overlap, ...)`
  - overlap support
  - optional `prev/next` relationships
- `TokenTextSplitter(chunk_size, chunk_overlap, ...)`
  - approximate token-based splitting with overlap

### Response synthesis modes

Response synthesis is available via `AgenticSynthesizer` (and the mode-specific synthesizers), plus the factory:

- `get_response_synthesizer(response_mode=...)`

Supported modes:

- `compact`
- `refine`
- `tree_summarize`
- `simple_summarize`

### Streaming

For token streaming, use:

- `StreamingSynthesizer.synthesize_stream(...)` → `StreamingResponse`

`StreamingResponse` provides:

- `response_gen`: sync generator of tokens
- `async_response_gen()`: async generator of tokens
- `get_response()` / `aget_response()`: helpers to consume the generators

`AgenticQueryEngine.query(..., streaming=True)` returns `StreamingResponse`.

### Metadata extraction

Metadata extractors follow the LlamaIndex “transformation” pattern and can be used in an ingestion pipeline:

- `TitleExtractor(nodes=N)`
  - generates a single representative `document_title` and applies it to all nodes
- `SummaryExtractor(summaries=["self", "prev", "next"])`
  - adds `section_summary`, `prev_section_summary`, `next_section_summary`

### Ingestion pipeline

`IngestionPipeline` can chain node parsing and metadata extraction:

```python
from agentic_brain.rag.llamaindex_compat import (
  IngestionPipeline, SentenceSplitter, TitleExtractor
)

pipeline = IngestionPipeline(
  transformations=[
    SentenceSplitter(chunk_size=512, chunk_overlap=50),
    TitleExtractor(nodes=5),
  ]
)

nodes = pipeline.run(documents=documents)
```

`AgenticIndex.from_documents(...)` will preserve previous behavior unless you explicitly provide:

- `transformations=[...]`, or
- `node_parser=...`, or
- `chunk_size` / `chunk_overlap`, or
- a global / passed `ServiceContext` that includes a `node_parser`

## Quick migration examples

### Indexing with chunking + titles

```python
from agentic_brain.rag.llamaindex_compat import (
  AgenticIndex, SentenceSplitter, TitleExtractor
)

docs = [
  {"text": "# My Doc\n\nA. B. C. D.", "source": "demo"},
]

index = AgenticIndex.from_documents(
  docs,
  transformations=[
    SentenceSplitter(chunk_size=256, chunk_overlap=20),
    TitleExtractor(nodes=1),
  ],
)
```

### Streaming query

```python
from agentic_brain.rag.llamaindex_compat import AgenticQueryEngine

engine = AgenticQueryEngine()
resp = engine.query("What is GraphRAG?", streaming=True)

for token in resp.response_gen:
    print(token, end="", flush=True)
```
