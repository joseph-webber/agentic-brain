# Vector Stores

The `agentic_brain.vectorstore` package provides a unified interface for vector database backends.

## Supported backends

- ChromaDB
- Qdrant
- Weaviate
- Pinecone

## Quick start

```python
from agentic_brain.vectorstore import create_vector_store

store = create_vector_store(
    "qdrant",
    collection_name="docs",
    dimension=1536,
)

store.connect()
store.create_collection("docs")
store.upsert([
    {"id": "1", "vector": [0.1, 0.2, 0.3], "metadata": {"title": "hello"}},
])

results = store.search([0.1, 0.2, 0.3])
```

## Factory

- `create_vector_store(name, **kwargs)`
- `available_backends()`

Aliases:

- `chroma` → `chromadb`
- `chromadb`
- `qdrant`
- `weaviate`
- `pinecone`

## Common API

- `connect()`
- `close()`
- `create_collection()`
- `delete_collection()`
- `list_collections()`
- `upsert()`
- `search()`
- `delete()`
- `count()`
- `stats()`
- `health()`

## Optional dependencies

Install the vector backend extras to use real clients:

```bash
pip install "agentic-brain[vectordb]"
```

## Notes

The package falls back to an in-memory mode when a backend client is unavailable, so tests and local development stay predictable.
