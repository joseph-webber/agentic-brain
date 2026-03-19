# RAG Module API

Retrieval-augmented generation for question-answering over documents. Combines document retrieval, context building, and LLM generation into a complete Q&A pipeline.

## Table of Contents
- [RAGPipeline](#ragpipeline) - Main RAG class
- [Retriever](#retriever) - Document retrieval
- [RetrievedChunk](#retrievedchunk) - Retrieved content
- [RAGResult](#ragresult) - Query results
- [EmbeddingProvider](#embeddingprovider) - Vector embeddings
- [Examples](#examples)

---

## RAGPipeline

Complete retrieval-augmented generation pipeline.

### Signature

```python
class RAGPipeline:
    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        llm_provider: str = "ollama",
        llm_model: str = "llama3.1:8b",
        llm_base_url: str = "http://localhost:11434",
        cache_ttl_hours: int = 4,
    ) -> None:
        """Initialize RAG pipeline."""
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `neo4j_uri` | `str` | `None` | Neo4j connection URI. If None, uses file-based search |
| `neo4j_user` | `str` | `neo4j` | Neo4j username |
| `neo4j_password` | `str` | `None` | Neo4j password |
| `embedding_provider` | `EmbeddingProvider` | `None` | Custom embedding model. If None, uses default |
| `llm_provider` | `str` | `ollama` | LLM provider ("ollama", "openai", etc.) |
| `llm_model` | `str` | `llama3.1:8b` | Model name/ID |
| `llm_base_url` | `str` | `http://localhost:11434` | LLM API base URL |
| `cache_ttl_hours` | `int` | `4` | Query result cache lifetime |

### Methods

#### `query()`

Submit a query and get an answer with sources.

```python
def query(
    self,
    query: str,
    sources: Optional[List[str]] = None,
    top_k: int = 5,
    temperature: float = 0.7,
    use_cache: bool = True
) -> RAGResult:
```

**Parameters:**
- `query` (str): Question or search query
- `sources` (list, optional): Limit search to specific sources (e.g., ["JiraTicket", "Document"])
- `top_k` (int): Number of documents to retrieve
- `temperature` (float): LLM temperature (0=deterministic, 1=creative)
- `use_cache` (bool): Use cached results if available

**Returns:**
- `RAGResult`: Answer with citations and metadata

**Example:**
```python
rag = RAGPipeline()

# Simple query
result = rag.query("What's the deployment process?")
print(result.answer)
print(result.format_with_citations())

# With Neo4j filtering
result = rag.query(
    "Recent project status",
    sources=["JiraTicket"],
    top_k=10
)

# Deterministic answer
result = rag.query("What is Python?", temperature=0)
```

---

#### `query_stream()`

Stream query answer token-by-token.

```python
def query_stream(
    self,
    query: str,
    sources: Optional[List[str]] = None,
    top_k: int = 5
) -> Iterator[str]:
```

**Returns:**
- Generator yielding response tokens

**Example:**
```python
rag = RAGPipeline()

for token in rag.query_stream("Explain quantum computing"):
    print(token, end="", flush=True)
print()  # newline
```

---

#### `batch_query()`

Process multiple queries efficiently.

```python
def batch_query(
    self,
    queries: List[str],
    sources: Optional[List[str]] = None,
    top_k: int = 5
) -> List[RAGResult]:
```

**Returns:**
- List of RAGResult objects

**Example:**
```python
rag = RAGPipeline()

queries = [
    "How do I deploy?",
    "What's the API endpoint?",
    "How do I configure?"
]

results = rag.batch_query(queries)

for result in results:
    print(f"Q: {result.query}")
    print(f"A: {result.answer}")
    print()
```

---

#### `clear_cache()`

Clear the query result cache.

```python
def clear_cache(self) -> None:
```

---

## Retriever

Multi-source document retriever for fetching relevant content.

### Signature

```python
class Retriever:
    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        sources: Optional[List[str]] = None
    ) -> None:
        """Initialize retriever."""
```

### Methods

#### `search()`

Search across all sources.

```python
def search(
    self,
    query: str,
    k: int = 5,
    min_score: float = 0.3
) -> List[RetrievedChunk]:
```

**Parameters:**
- `query` (str): Search query
- `k` (int): Number of results to return
- `min_score` (float): Minimum relevance score (0-1)

**Returns:**
- List of RetrievedChunk objects, ranked by relevance

**Example:**
```python
retriever = Retriever(neo4j_uri="bolt://localhost:7687")

chunks = retriever.search("deployment guide", k=5)

for chunk in chunks:
    print(f"{chunk.source}: {chunk.score:.2f}")
    print(chunk.content[:200])
    print()
```

---

#### `search_neo4j()`

Search Neo4j graph database with vector similarity.

```python
def search_neo4j(
    self,
    query: str,
    k: int = 5,
    labels: Optional[List[str]] = None,
    min_score: float = 0.3
) -> List[RetrievedChunk]:
```

**Parameters:**
- `query` (str): Search query
- `k` (int): Results to return
- `labels` (list, optional): Neo4j node labels to search
- `min_score` (float): Minimum similarity score

**Example:**
```python
retriever = Retriever(neo4j_uri="bolt://localhost:7687")

# Search all document types
results = retriever.search_neo4j("API endpoints")

# Search specific types
results = retriever.search_neo4j(
    "API endpoints",
    labels=["Document", "Code"]
)
```

---

#### `search_files()`

Search local files with BM25 ranking.

```python
def search_files(
    self,
    query: str,
    directory: str = ".",
    extensions: Optional[List[str]] = None,
    k: int = 5
) -> List[RetrievedChunk]:
```

**Parameters:**
- `query` (str): Search query
- `directory` (str): Directory to search
- `extensions` (list, optional): File types to search (.md, .py, etc.)
- `k` (int): Results to return

**Example:**
```python
retriever = Retriever()

# Search markdown documentation
results = retriever.search_files(
    "deployment",
    directory="./docs",
    extensions=[".md"],
    k=3
)
```

---

## RetrievedChunk

Individual retrieved document chunk.

### Signature

```python
@dataclass
class RetrievedChunk:
    content: str
    source: str
    score: float
    metadata: Dict[str, Any] = {}
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `content` | `str` | Chunk text |
| `source` | `str` | Source name (file, URL, database ID) |
| `score` | `float` | Relevance score (0-1) |
| `metadata` | `dict` | Additional metadata |
| `confidence` | `str` | Human-readable confidence ("high", "medium", "low", "uncertain") |

### Methods

#### `to_context()`

Format for LLM context.

```python
def to_context(self) -> str:
```

**Returns:**
```
[Source: filename.md]
Content here...
```

**Example:**
```python
chunk = RetrievedChunk(
    content="Python is a programming language",
    source="wiki.md",
    score=0.95
)

print(chunk.to_context())
# [Source: wiki.md]
# Python is a programming language
```

---

## RAGResult

Result from a RAG query.

### Signature

```python
@dataclass
class RAGResult:
    query: str
    answer: str
    sources: List[RetrievedChunk]
    confidence: float
    model: str
    cached: bool = False
    generation_time_ms: float = 0
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `query` | `str` | Original query |
| `answer` | `str` | Generated answer |
| `sources` | `List[RetrievedChunk]` | Retrieved documents |
| `confidence` | `float` | Answer confidence (0-1) |
| `model` | `str` | LLM model used |
| `cached` | `bool` | Whether result was cached |
| `generation_time_ms` | `float` | Generation time in milliseconds |
| `has_sources` | `bool` | True if sources available |
| `confidence_level` | `str` | "high", "medium", "low", or "uncertain" |

### Methods

#### `to_dict()`

Serialize to dictionary.

```python
def to_dict(self) -> Dict[str, Any]:
```

**Example:**
```python
result = rag.query("What is Python?")

import json
print(json.dumps(result.to_dict(), indent=2))
```

---

#### `format_with_citations()`

Format answer with numbered citations.

```python
def format_with_citations(self) -> str:
```

**Returns:**
```
Generated answer text

---
Sources:
[1] document.md (confidence: 0.95)
[2] file.py (confidence: 0.87)
```

**Example:**
```python
result = rag.query("Explain machine learning")
print(result.format_with_citations())
```

---

## EmbeddingProvider

Interface for embedding models (optional - use default).

### Signature

```python
class EmbeddingProvider:
    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
```

### Built-in Providers

- **Sentence-Transformers** (default): Fast, lightweight embeddings
- **OpenAI**: High-quality embeddings (requires API key)
- **Cohere**: Commercial embeddings (requires API key)

### Custom Provider

```python
class MyEmbedder(EmbeddingProvider):
    def embed(self, text: str) -> List[float]:
        # Your implementation
        return [...]

rag = RAGPipeline(embedding_provider=MyEmbedder())
```

---

## Examples

### Example 1: Simple Q&A

```python
from agentic_brain import RAGPipeline

rag = RAGPipeline()

# Query
result = rag.query("What is the return policy?")

print(f"Question: {result.query}")
print(f"Answer: {result.answer}")
print(f"Confidence: {result.confidence_level}")
print(f"Sources: {len(result.sources)}")
```

---

### Example 2: With Citations

```python
from agentic_brain import RAGPipeline

rag = RAGPipeline()

result = rag.query("How do I deploy?")
print(result.format_with_citations())

# Output:
# To deploy, follow these steps:
# 1. Build the project...
# 
# ---
# Sources:
# [1] docs/deployment.md (confidence: 0.98)
# [2] README.md (confidence: 0.85)
```

---

### Example 3: Neo4j Backend

```python
from agentic_brain import RAGPipeline

rag = RAGPipeline(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"
)

# Search Jira tickets and documents
result = rag.query(
    "Recent project status",
    sources=["JiraTicket", "Document"]
)

print(result.answer)
```

---

### Example 4: Batch Queries

```python
from agentic_brain import RAGPipeline

rag = RAGPipeline()

questions = [
    "What's the API?",
    "How do I install?",
    "What's the license?"
]

results = rag.batch_query(questions)

for result in results:
    print(f"Q: {result.query}")
    print(f"A: {result.answer}\n")
```

---

### Example 5: Streaming Response

```python
from agentic_brain import RAGPipeline

rag = RAGPipeline()

print("Generating answer... ")
for token in rag.query_stream("Explain cloud computing"):
    print(token, end="", flush=True)
print()
```

---

### Example 6: Custom Configuration

```python
from agentic_brain import RAGPipeline

rag = RAGPipeline(
    neo4j_uri="bolt://localhost:7687",
    llm_provider="ollama",
    llm_model="mistral-nemo",
    llm_base_url="http://localhost:11434",
    cache_ttl_hours=24  # Longer cache
)

# Deterministic generation
result = rag.query("Explain Python", temperature=0.0)
```

---

### Example 7: File-Based Search

```python
from agentic_brain import Retriever

retriever = Retriever()

# Search local documentation
chunks = retriever.search_files(
    "configuration",
    directory="./docs",
    extensions=[".md", ".txt"],
    k=5
)

for chunk in chunks:
    print(f"{chunk.source}: {chunk.score:.2f}")
    print(chunk.content[:100])
    print()
```

---

## Environment Variables

```bash
# Neo4j
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"

# LLM
export OLLAMA_BASE_URL="http://localhost:11434"
export LLM_MODEL="llama3.1:8b"
```

---

## Performance Tips

### 1. Use Vector Indexes
For large Neo4j databases, create vector indexes:
```cypher
CREATE INDEX document_embedding_index 
FOR (d:Document) 
ON (d.embedding)
```

### 2. Cache Results
RAG results are cached by default. Control caching:
```python
# Use cache
result = rag.query("What's the API?", use_cache=True)

# Skip cache (always fresh)
result = rag.query("What's the API?", use_cache=False)

# Clear cache
rag.clear_cache()
```

### 3. Batch Processing
For multiple queries, use batch:
```python
# Much faster than individual queries
results = rag.batch_query(queries)
```

### 4. Limit Results
Reduce k for faster retrieval:
```python
result = rag.query("What's the API?", top_k=3)  # Instead of 5
```

---

## Error Handling

```python
from agentic_brain import RAGPipeline

try:
    rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
    result = rag.query("What is this?")
except ConnectionError:
    print("Could not connect to Neo4j")
except ValueError as e:
    print(f"Invalid query: {e}")
```

---

## See Also

- [Chat Module](./chat.md) - Chatbot with memory
- [Memory Module](./memory.md) - Knowledge storage
- [Agent Module](./agent.md) - Full-featured agent
- [Index](./index.md) - All modules

---

**Last Updated**: 2026-03-20  
**Status**: Production Ready ✅
