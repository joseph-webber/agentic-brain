# Embeddings Module Documentation

## Overview

The embeddings module provides comprehensive support for multiple embedding model providers in the agentic-brain framework. It includes support for OpenAI, Cohere, Sentence Transformers (local), Voyage AI, and Jina embeddings with a unified interface.

**Key Features:**
- 🔄 Unified interface across all embedding providers
- ⚡ Async/sync support for all operations
- 📦 Efficient batch processing with rate limiting
- 🔁 Automatic retry logic and error handling
- 📊 Normalization and similarity calculations
- 🎯 Provider-specific optimizations

## Installation

### Base Installation

```bash
pip install agentic-brain
```

### With Embedding Provider Support

Install the embeddings extra to get all dependencies:

```bash
pip install agentic-brain[embeddings]
```

Or install specific providers:

```bash
# OpenAI
pip install openai

# Cohere
pip install cohere

# Sentence Transformers (local models)
pip install sentence-transformers

# Voyage AI
pip install voyageai

# Jina
pip install jinaai
```

## Quick Start

### OpenAI Embeddings

```python
from agentic_brain.embeddings import OpenAIEmbedder

# Initialize embedder
embedder = OpenAIEmbedder(api_key="your-api-key")
# or use OPENAI_API_KEY environment variable

# Single text embedding
result = embedder.embed_sync("Hello, world!")
print(result.embedding)  # numpy array of shape (1536,)
print(result.dimension)  # 1536

# Batch embedding
texts = ["First document", "Second document", "Third document"]
batch_result = embedder.embed_batch_sync(texts, batch_size=32, show_progress=True)
print(f"Successfully embedded {batch_result.successful} texts")
print(f"Tokens used: {batch_result.total_tokens_used}")
```

### Local Embeddings with Sentence Transformers

```python
from agentic_brain.embeddings import SentenceTransformersEmbedder

# Initialize with local model (no API key needed!)
embedder = SentenceTransformersEmbedder(
    model="all-MiniLM-L6-v2",  # Fast, ~2x faster than mpnet
    device="mps",  # Apple Silicon acceleration
    normalize_embeddings=True
)

# Single embedding
result = embedder.embed_sync("This will run locally!")
print(f"Embedding dimension: {result.dimension}")  # 384

# Batch with GPU acceleration
batch_result = embedder.embed_batch_sync(
    texts=["text1", "text2"],
    batch_size=32,
    show_progress=True
)
```

### Async Operations

```python
import asyncio
from agentic_brain.embeddings import OpenAIEmbedder

async def embed_async():
    embedder = OpenAIEmbedder()
    
    # Single async embedding
    result = await embedder.embed_async("Async text")
    
    # Batch async with concurrency control
    batch_result = await embedder.embed_batch_async(
        texts=["text1", "text2", "text3"],
        concurrent_requests=5
    )
    
    print(f"Embedded {batch_result.successful} texts concurrently")
    
    await embedder.close()

asyncio.run(embed_async())
```

## Supported Models

### OpenAI

| Model | Dimension | Speed | Cost | Best For |
|-------|-----------|-------|------|----------|
| text-embedding-3-small | 1536 | Fast | Low | General use |
| text-embedding-3-large | 3072 | Medium | Higher | High-quality retrieval |
| text-embedding-ada-002 | 1536 | Fast | Low | Legacy compatibility |

### Cohere

| Model | Dimension | Speed | Language | Best For |
|-------|-----------|-------|----------|----------|
| embed-english-v3.0 | 1024 | Medium | English | Optimal quality |
| embed-english-light-v3.0 | 384 | Fast | English | Speed/efficiency |
| embed-multilingual-v3.0 | 1024 | Medium | 92 languages | Multilingual |

### Sentence Transformers

| Model | Dimension | Device | Speed | Best For |
|-------|-----------|--------|-------|----------|
| all-MiniLM-L6-v2 | 384 | CPU/GPU | Very Fast | Quick local embedding |
| all-mpnet-base-v2 | 768 | CPU/GPU | Medium | High quality local |
| multilingual-e5-base | 768 | CPU/GPU | Medium | 200+ languages |
| text2vec-base-chinese | 768 | CPU/GPU | Medium | Chinese text |

### Voyage AI

| Model | Dimension | Speed | Best For |
|-------|-----------|-------|----------|
| voyage-2 | 1024 | Medium | General retrieval |
| voyage-large-2 | 1536 | Medium | High-quality results |
| voyage-law-2 | 1024 | Medium | Legal documents |
| voyage-finance-2 | 1024 | Medium | Financial documents |

### Jina

| Model | Dimension | Language | Best For |
|-------|-----------|----------|----------|
| jina-embeddings-v2-base-en | 512 | English | Fast English |
| jina-embeddings-v2-small-en | 384 | English | Ultra-fast English |
| jina-embeddings-v2-base-multilingual | 512 | 92 languages | Multilingual |

## API Reference

### Base Classes

#### `Embedder` (Abstract Base Class)

All embedding implementations inherit from this abstract base class.

**Properties:**
- `provider: EmbeddingProvider` - The embedding provider type
- `model: str` - The model name/identifier
- `dimension: int` - Embedding vector dimension

**Methods:**
- `embed_sync(text: str) -> EmbeddingResult` - Embed single text
- `embed_async(text: str) -> EmbeddingResult` - Async single embedding
- `embed_batch_sync(texts, batch_size=32, show_progress=False) -> BatchEmbeddingResult`
- `embed_batch_async(texts, batch_size=32, show_progress=False, concurrent_requests=5) -> BatchEmbeddingResult`
- `validate_text(text: str)` - Validate single text
- `validate_texts(texts: List[str])` - Validate batch of texts
- `normalize_embedding(embedding: np.ndarray) -> np.ndarray` - L2 normalization
- `cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float` - Cosine similarity
- `close()` - Clean up resources

#### `EmbeddingResult`

Result of a single embedding operation.

```python
@dataclass
class EmbeddingResult:
    text: str                                    # Input text
    embedding: np.ndarray                        # Embedding vector
    dimension: int                               # Vector dimension
    provider: str                                # Provider name
    model: str                                   # Model name
    tokens_used: Optional[int] = None            # API tokens (if applicable)
    latency_ms: Optional[float] = None           # Request latency in ms
```

#### `BatchEmbeddingResult`

Result of a batch embedding operation.

```python
@dataclass
class BatchEmbeddingResult:
    results: List[EmbeddingResult]              # Individual embeddings
    total_texts: int                            # Total texts processed
    successful: int                             # Successfully embedded
    failed: int                                 # Failed embeddings
    total_tokens_used: int                      # Total API tokens
    total_latency_ms: float                     # Total time in ms
    errors: List[Dict[str, Any]]                # Error details
```

### Provider Implementations

#### `OpenAIEmbedder`

```python
embedder = OpenAIEmbedder(
    api_key: str = None,                 # API key or OPENAI_API_KEY env var
    model: str = "text-embedding-3-small",  # Model to use
    rate_limit: int = 3500,              # Requests per minute
    max_retries: int = 3,                # Retry attempts
    timeout: int = 30                    # Request timeout (seconds)
)
```

**Features:**
- Automatic retry with exponential backoff
- Rate limiting to stay under API quotas
- Token counting support
- Supports all OpenAI embedding models

#### `CohereEmbedder`

```python
embedder = CohereEmbedder(
    api_key: str = None,                 # API key or COHERE_API_KEY env var
    model: str = "embed-english-v3.0",   # Model to use
    input_type: str = "search_document", # "search_document", "search_query", etc
    rate_limit: int = 10000,             # Requests per minute
    max_retries: int = 3,
    timeout: int = 30
)
```

**Features:**
- Input type optimization (document vs query)
- Efficient batch processing (up to 96 texts)
- Support for multilingual models

#### `SentenceTransformersEmbedder`

```python
embedder = SentenceTransformersEmbedder(
    model: str = "all-MiniLM-L6-v2",    # Hugging Face model
    device: str = None,                  # "cpu", "cuda", "mps" (auto-detect)
    batch_size: int = 32,                # Batch size for inference
    show_progress: bool = True,          # Show progress bar
    normalize_embeddings: bool = True,   # L2 normalization
    cache_folder: str = None             # Model cache location
)
```

**Features:**
- 100% local execution - no API calls
- Automatic device detection (CPU/GPU/MPS)
- Efficient batch processing
- Support for 100+ Hugging Face models
- No API key required

#### `E5Embedder`

Specialized embedder for multilingual E5 models with query/passage prefixes.

```python
embedder = E5Embedder(
    model: str = "intfloat/e5-small",   # E5 model variant
    device: str = None,
    batch_size: int = 32
)

# Embed with task type
result = embedder.embed_sync("query text", task_type="query")
result = embedder.embed_sync("passage text", task_type="passage")
```

#### `VoyageEmbedder`

```python
embedder = VoyageEmbedder(
    api_key: str = None,                 # API key or VOYAGE_API_KEY env var
    model: str = "voyage-2",
    input_type: str = "document",        # "document" or "query"
    rate_limit: int = 5000,
    max_retries: int = 3,
    timeout: int = 30
)
```

#### `JinaEmbedder`

```python
embedder = JinaEmbedder(
    api_key: str = None,                 # API key or JINA_API_KEY env var
    model: str = "jina-embeddings-v2-base-en",
    task: str = "retrieval.passage",     # Task type for optimization
    rate_limit: int = 5000,
    max_retries: int = 3,
    timeout: int = 30
)
```

## Advanced Usage

### Similarity Search

```python
from agentic_brain.embeddings import SentenceTransformersEmbedder
import numpy as np

embedder = SentenceTransformersEmbedder()

# Embed query and documents
query = "Machine learning fundamentals"
documents = [
    "Introduction to machine learning",
    "Deep learning neural networks",
    "Natural language processing",
    "Computer vision models"
]

query_emb = embedder.embed_sync(query).embedding
doc_results = embedder.embed_batch_sync(documents)

# Find most similar documents
similarities = [
    embedder.cosine_similarity(query_emb, doc.embedding)
    for doc in doc_results.results
]

# Rank by similarity
ranked = sorted(zip(documents, similarities), key=lambda x: x[1], reverse=True)
for doc, score in ranked:
    print(f"{score:.3f} - {doc}")
```

### Provider Switching

```python
from agentic_brain.embeddings import (
    OpenAIEmbedder,
    SentenceTransformersEmbedder
)

def get_embedder(use_cloud=True):
    if use_cloud:
        return OpenAIEmbedder()
    else:
        return SentenceTransformersEmbedder(device="mps")

# Switch providers as needed
embedder = get_embedder(use_cloud=False)  # Local
result = embedder.embed_sync("Some text")
```

### Batch Processing with Progress

```python
from agentic_brain.embeddings import OpenAIEmbedder

embedder = OpenAIEmbedder()

documents = ["doc1", "doc2", ..., "doc1000"]

# With progress bar
result = embedder.embed_batch_sync(
    documents,
    batch_size=100,
    show_progress=True
)

print(f"Embedded {result.successful}/{result.total_texts} documents")
print(f"Tokens used: {result.total_tokens_used}")
print(f"Total time: {result.total_latency_ms:.1f}ms")

# Handle errors
if result.errors:
    for error in result.errors:
        print(f"Error: {error}")
```

### Concurrent Async Requests

```python
import asyncio
from agentic_brain.embeddings import OpenAIEmbedder

async def process_large_batch():
    embedder = OpenAIEmbedder()
    
    texts = [f"Document {i}" for i in range(1000)]
    
    # Process with high concurrency
    result = await embedder.embed_batch_async(
        texts,
        batch_size=50,
        concurrent_requests=10,
        show_progress=True
    )
    
    await embedder.close()
    
    return result

result = asyncio.run(process_large_batch())
```

### Apple Silicon Acceleration

```python
from agentic_brain.embeddings import SentenceTransformersEmbedder

# Automatic M1/M2/M3 acceleration via MPS
embedder = SentenceTransformersEmbedder(
    model="all-mpnet-base-v2",
    device="mps"  # or leave as None for auto-detection
)

result = embedder.embed_sync("This will use GPU!")
print(f"Latency: {result.latency_ms:.1f}ms")
```

## Best Practices

### 1. Choose the Right Model

- **Speed Priority**: Use `all-MiniLM-L6-v2` (local) or `text-embedding-3-small` (OpenAI)
- **Quality Priority**: Use `all-mpnet-base-v2` (local) or `text-embedding-3-large` (OpenAI)
- **No API Access**: Use `SentenceTransformersEmbedder`
- **Multilingual**: Use `multilingual-e5-base` or `E5Embedder`

### 2. Batch Processing

```python
# Good: Batch processing
result = embedder.embed_batch_sync(texts, batch_size=32)

# Avoid: Individual requests in loop
for text in texts:
    embedder.embed_sync(text)  # Slow and inefficient
```

### 3. Caching

```python
# Store embeddings to avoid re-computation
embedding_cache = {}

for text in texts:
    if text not in embedding_cache:
        result = embedder.embed_sync(text)
        embedding_cache[text] = result.embedding
```

### 4. Error Handling

```python
try:
    result = embedder.embed_sync(text)
except ValueError as e:
    print(f"Validation error: {e}")
except RuntimeError as e:
    print(f"Embedding error: {e}")
```

### 5. Resource Cleanup

```python
import asyncio

async def safe_embedding():
    embedder = OpenAIEmbedder()
    try:
        result = await embedder.embed_async("text")
        return result
    finally:
        await embedder.close()  # Always clean up

result = asyncio.run(safe_embedding())
```

## Environment Variables

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Cohere
export COHERE_API_KEY="..."

# Voyage AI
export VOYAGE_API_KEY="..."

# Jina
export JINA_API_KEY="..."
```

## Performance Benchmarks

Typical latencies (single text):

| Provider | Model | Latency | Notes |
|----------|-------|---------|-------|
| Local | all-MiniLM-L6-v2 | 5-10ms | CPU, can use GPU |
| Local | all-mpnet-base-v2 | 20-30ms | Higher quality |
| OpenAI | text-embedding-3-small | 100-200ms | API latency included |
| OpenAI | text-embedding-3-large | 150-250ms | Higher quality |
| Cohere | embed-english-v3.0 | 100-200ms | API latency |
| Voyage | voyage-2 | 100-200ms | API latency |

Batch processing is 10-100x faster per text due to amortized overhead.

## Troubleshooting

### API Key Not Found

```python
# Ensure API key is set in environment
import os
os.environ['OPENAI_API_KEY'] = 'your-key'

# Or pass directly
embedder = OpenAIEmbedder(api_key='your-key')
```

### Out of Memory

```python
# Reduce batch size for local models
embedder = SentenceTransformersEmbedder()
result = embedder.embed_batch_sync(texts, batch_size=8)  # Smaller batches
```

### Slow Performance

```python
# Use GPU acceleration
embedder = SentenceTransformersEmbedder(device="cuda")  # or "mps" for Apple

# Or use faster model
embedder = SentenceTransformersEmbedder(model="all-MiniLM-L6-v2")
```

### Rate Limiting

```python
# Configure rate limits
embedder = OpenAIEmbedder(
    rate_limit=3500,  # Requests per minute
    max_retries=5     # More retries for rate limits
)
```

## Testing

Run comprehensive tests:

```bash
pytest tests/test_embeddings_comprehensive.py -v
pytest tests/test_embeddings_comprehensive.py::TestOpenAIEmbedder -v  # Specific provider
pytest tests/test_embeddings_comprehensive.py -k "normalization" -v   # Specific test
```

Test coverage includes:
- Base class interface validation
- All provider implementations
- Batch processing
- Rate limiting
- Error handling
- Async operations
- Normalization and similarity

## Contributing

To add a new embedding provider:

1. Create a new file: `src/agentic_brain/embeddings/myprovider.py`
2. Implement the `Embedder` ABC
3. Add tests to `tests/test_embeddings_comprehensive.py`
4. Update documentation
5. Add to `__init__.py` exports

## License

Apache License 2.0 - See LICENSE file for details

## Support

- 📖 Documentation: https://agentic-brain.readthedocs.io/
- 🐛 Issues: https://github.com/ecomlounge/brain/issues
- 💬 Discussions: https://github.com/ecomlounge/brain/discussions
