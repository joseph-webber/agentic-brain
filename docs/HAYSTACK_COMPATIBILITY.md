# Haystack 2.0 Compatibility (agentic-brain)

`agentic_brain.rag.haystack_compat` provides a Haystack-style API for GraphRAG workflows.

## Supported Haystack 2.0 API Surface

### 1) Pipeline (DAG-based composition)
- `Pipeline.add_component(name, instance)`
- `Pipeline.connect(sender, receiver)` with:
  - simple syntax: `"retriever" -> "prompt_builder"`
  - explicit ports: `"retriever.documents" -> "prompt_builder.documents"`
- `Pipeline.run(data, include_outputs_from=None)`
- cycle detection + topological execution
- serialization: `to_dict()`, `dumps()`, `from_dict()`, `loads()`

### 2) Component decorator
- `@component` for pipeline nodes
- `@component.output_types(...)` for typed outputs
- input/output metadata is used for connection validation

### 3) DocumentStore
- `InMemoryDocumentStore`
  - `write_documents()`, `filter_documents()`, `delete_documents()`, `count_documents()`
  - `embedding_retrieval()` and `bm25_retrieval()`

### 4) Retrievers
- `EmbeddingRetriever`
- `BM25Retriever`
- (also available: `HybridRetriever`)

### 5) PromptBuilder
- `PromptBuilder(template, required_variables=None)`
- Supports `{var}` and `{{ var }}` placeholders
- Handles `documents` lists by rendering readable context blocks

## Example

```python
from agentic_brain.rag.haystack_compat import (
    Pipeline,
    PromptBuilder,
    InMemoryDocumentStore,
    EmbeddingRetriever,
    Document,
)

store = InMemoryDocumentStore()
store.write_documents(
    [
        Document(content="GraphRAG improves retrieval with graph context.", embedding=[1.0, 0.0, 0.0]),
        Document(content="BM25 helps with keyword precision.", embedding=[0.7, 0.3, 0.0]),
    ]
)

pipe = Pipeline(metadata={"name": "haystack-rag"})
pipe.add_component("retriever", EmbeddingRetriever(document_store=store, top_k=2))
pipe.add_component(
    "prompt_builder",
    PromptBuilder("Question: {query}\n\nContext:\n{documents}\n\nAnswer:"),
)

pipe.connect("retriever.documents", "prompt_builder.documents")

result = pipe.run(
    {
        "retriever": {"query_embedding": [1.0, 0.0, 0.0]},
        "prompt_builder": {"query": "How does GraphRAG help?"},
    }
)

print(result["prompt_builder"]["prompt"])
```

## Test Coverage

Integration tests live in:
- `tests/test_rag/test_haystack_integration.py`

The suite includes 40+ tests across:
- component decorator behavior
- pipeline DAG composition/execution/serialization
- in-memory document store operations
- embedding + BM25 retrievers
- prompt template rendering
