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

## Cloud Document Loaders

Load documents from cloud services for ingestion into RAG pipelines.

### Supported Services

- **Google Drive**: Documents, Sheets, Slides, PDFs, text files
- **Gmail**: Email messages with attachments
- **iCloud Drive**: Documents and folders

### LoadedDocument

Data class representing a loaded document.

```python
@dataclass
class LoadedDocument:
    content: str                          # Extracted text content
    metadata: Dict[str, Any] = {}         # Additional metadata
    source: str = ""                      # Source name (google_drive, gmail, icloud)
    source_id: str = ""                   # Original ID in source system
    filename: str = ""                    # Original filename
    mime_type: str = "text/plain"         # MIME type
    created_at: Optional[datetime] = None # Creation timestamp
    modified_at: Optional[datetime] = None# Last modified timestamp
    size_bytes: int = 0                   # File size
```

**Methods:**
- `to_dict() -> Dict[str, Any]`: Serialize to dictionary
- `from_dict(data) -> LoadedDocument`: Create from dictionary

---

### GoogleDriveLoader

Load documents from Google Drive.

```python
from agentic_brain.rag import GoogleDriveLoader

# Using OAuth2 (opens browser for auth)
loader = GoogleDriveLoader(
    credentials_path="client_secrets.json",
    token_path="token.json",
    max_file_size_mb=50
)

# Using service account (for servers)
loader = GoogleDriveLoader(
    credentials_path="service-account.json",
    use_service_account=True
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `credentials_path` | `str` | `None` | Path to credentials JSON |
| `token_path` | `str` | `gdrive_token.json` | Where to store OAuth token |
| `use_service_account` | `bool` | `False` | Use service account auth |
| `max_file_size_mb` | `int` | `50` | Max file size to download |

**Methods:**

```python
# Authenticate (required before other methods)
loader.authenticate() -> bool

# Load a single document by ID
doc = loader.load_document(doc_id="abc123") -> LoadedDocument

# Load all documents in a folder
docs = loader.load_folder("My Project/Docs", recursive=True) -> List[LoadedDocument]

# Search for documents
results = loader.search("quarterly report", max_results=50) -> List[LoadedDocument]

# List subfolders
folders = loader.list_folders("My Project") -> List[Dict[str, str]]
```

**Supported file types:**
- Google Docs, Sheets, Slides (exported as text/CSV)
- PDFs (text extraction)
- Plain text, Markdown, JSON, CSV
- Word documents (.docx)

---

### GmailLoader

Load emails from Gmail.

```python
from agentic_brain.rag import GmailLoader

loader = GmailLoader(
    credentials_path="client_secrets.json",
    token_path="gmail_token.json",
    include_attachments=True,
    max_attachment_size_mb=25
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `credentials_path` | `str` | `None` | Path to OAuth2 credentials |
| `token_path` | `str` | `gmail_token.json` | Where to store token |
| `include_attachments` | `bool` | `True` | Extract text from attachments |
| `max_attachment_size_mb` | `int` | `25` | Max attachment size |

**Methods:**

```python
# Authenticate
loader.authenticate() -> bool

# Load a single email by message ID
email = loader.load_document(doc_id="msg123") -> LoadedDocument

# Load emails by label (INBOX, IMPORTANT, etc.)
emails = loader.load_by_label("IMPORTANT", max_results=100) -> List[LoadedDocument]

# Load recent emails
emails = loader.load_recent(days=7, max_results=100) -> List[LoadedDocument]

# Search with Gmail query syntax
results = loader.search("from:boss@company.com has:attachment") -> List[LoadedDocument]

# List all labels
labels = loader.list_labels() -> List[Dict[str, str]]
```

**Gmail query syntax examples:**
- `from:sender@example.com` - From specific sender
- `to:me` - Sent to you
- `has:attachment` - Has attachments
- `newer_than:7d` - Last 7 days
- `is:unread` - Unread messages
- `subject:important` - Subject contains word

---

### iCloudLoader

Load documents from iCloud Drive.

```python
from agentic_brain.rag import iCloudLoader

loader = iCloudLoader(
    apple_id="your@icloud.com",
    password="app-specific-password",  # Recommended!
    cookie_directory=".icloud",
    max_file_size_mb=50
)

# Or use environment variables
# ICLOUD_APPLE_ID=your@icloud.com
# ICLOUD_PASSWORD=your-password
loader = iCloudLoader()
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `apple_id` | `str` | `None` | Apple ID email (or env var) |
| `password` | `str` | `None` | Password (or env var) |
| `cookie_directory` | `str` | `.icloud` | Session cookie storage |
| `max_file_size_mb` | `int` | `50` | Max file size |

**Note:** On first use, 2FA verification is required. Use an app-specific password for automated use.

**Methods:**

```python
# Authenticate (may prompt for 2FA code)
loader.authenticate() -> bool

# Load a document by path
doc = loader.load_document("Documents/report.pdf") -> LoadedDocument

# Load all documents in a folder
docs = loader.load_folder("Documents/Work", recursive=True) -> List[LoadedDocument]

# Search by filename
results = loader.search("quarterly", max_results=50) -> List[LoadedDocument]

# List subfolders
folders = loader.list_folders("Documents") -> List[Dict[str, str]]
```

**Supported file types:**
- Text files (.txt, .md, .json, .csv)
- PDFs (text extraction)
- Word documents (.docx)
- HTML files

---

### Factory Functions

#### create_loader()

Create a loader by source name.

```python
from agentic_brain.rag import create_loader

# Google Drive
loader = create_loader('google_drive', credentials_path='creds.json')
loader = create_loader('drive', credentials_path='creds.json')  # Alias

# Gmail
loader = create_loader('gmail', credentials_path='creds.json')
loader = create_loader('email', credentials_path='creds.json')  # Alias

# iCloud
loader = create_loader('icloud', apple_id='me@icloud.com', password='xxx')
loader = create_loader('icloud_drive', apple_id='me@icloud.com', password='xxx')  # Alias
```

#### load_from_multiple_sources()

Load from multiple cloud sources in one call.

```python
from agentic_brain.rag import load_from_multiple_sources

sources = [
    {
        'type': 'google_drive',
        'credentials_path': 'creds.json',
        'folder': 'Work/Projects'
    },
    {
        'type': 'gmail',
        'credentials_path': 'creds.json',
        'query': 'from:boss@company.com'
    },
    {
        'type': 'icloud',
        'apple_id': 'me@icloud.com',
        'password': 'app-password',
        'folder': 'Documents'
    },
]

# Load all documents with deduplication
all_docs = load_from_multiple_sources(sources, deduplicate=True)

print(f"Loaded {len(all_docs)} unique documents")
```

---

### Availability Flags

Check if cloud libraries are installed:

```python
from agentic_brain.rag import GOOGLE_API_AVAILABLE, PYICLOUD_AVAILABLE

if GOOGLE_API_AVAILABLE:
    # Google Drive and Gmail loaders available
    pass

if PYICLOUD_AVAILABLE:
    # iCloud loader available
    pass
```

**Installation:**

```bash
# Google APIs (for Google Drive and Gmail)
pip install google-auth google-auth-oauthlib google-api-python-client

# iCloud
pip install pyicloud

# PDF extraction (optional but recommended)
pip install PyPDF2
# or
pip install pdfplumber

# Word documents (optional)
pip install python-docx
```

---

### Example: RAG Pipeline Integration

```python
from agentic_brain.rag import (
    RAGPipeline,
    GoogleDriveLoader,
    GmailLoader,
    create_chunker,
    ChunkingStrategy,
)

# Load documents from Google Drive
drive = GoogleDriveLoader(credentials_path='creds.json')
drive.authenticate()
drive_docs = drive.load_folder('Knowledge Base')

# Load recent important emails
gmail = GmailLoader(credentials_path='creds.json')
gmail.authenticate()
email_docs = gmail.search('label:important newer_than:30d')

# Combine all documents
all_docs = drive_docs + email_docs

# Create chunker for processing
chunker = create_chunker(ChunkingStrategy.RECURSIVE)

# Process into chunks with metadata
all_chunks = []
for doc in all_docs:
    chunks = chunker.chunk(doc.content)
    for chunk in chunks:
        chunk.metadata.update({
            'source': doc.source,
            'filename': doc.filename,
            'source_id': doc.source_id,
        })
    all_chunks.extend(chunks)

print(f"Created {len(all_chunks)} chunks from {len(all_docs)} documents")

# Now use with RAG pipeline
rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
result = rag.query("What are the project deadlines?")
print(result.answer)
```

---

**Last Updated**: 2026-03-20  
**Status**: Production Ready ✅
