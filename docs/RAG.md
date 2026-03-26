# RAG (Retrieval-Augmented Generation) Guide

Agentic-Brain provides a **production-ready, comprehensive RAG pipeline** with hardware acceleration, multi-source document loading, advanced retrieval strategies, and rigorous evaluation. This guide covers all components and how to use them effectively.

---

## Overview

RAG (Retrieval-Augmented Generation) enhances LLM responses by:
1. **Retrieving** relevant documents or chunks
2. **Ranking** by relevance (optional but recommended)
3. **Augmenting** the LLM prompt with retrieved context
4. **Generating** informed answers with citations

Agentic-Brain's RAG pipeline includes:
- **Multi-source retrieval** (Neo4j, files, cloud services)
- **Hardware-accelerated embeddings** (Apple M1-M4, NVIDIA, AMD)
- **Advanced chunking** (semantic, recursive, markdown-aware)
- **Hybrid search** (vector + keyword BM25)
- **Reranking** (cross-encoder, MMR for diversity)
- **Evaluation & A/B testing** framework
- **Cloud loaders** (Google Drive, Gmail, iCloud, S3, Dropbox, Box, OneDrive, SharePoint, etc.)
- **Caching** for efficiency
- **Source citation** with confidence scores

### Quick Start

```python
from agentic_brain.rag import ask, RAGPipeline, get_embeddings

# Simplest usage - uses defaults
answer = ask("What is the status of project X?")

# Full pipeline with Neo4j backend
rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
result = rag.query("How do I deploy?")
print(f"Answer: {result.answer}")
print(f"Sources: {result.sources}")
```

---

## Hardware Acceleration

Agentic-Brain automatically detects and uses the fastest available hardware for embeddings. Depending on your hardware, this can provide significant speedups compared to CPU-only processing.

### Supported Platforms

| Platform | Best For | Speed | Installation |
|----------|----------|-------|--------------|
| **Apple Silicon (MLX)** | M1, M2, M3, M4 | 50ms/embed | `pip install mlx mlx-lm` |
| **Apple MPS** | M1-M4 via PyTorch | 180ms/embed | Automatic with PyTorch |
| **NVIDIA CUDA** | RTX 30/40 series | 35-70ms/embed | `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118` |
| **AMD ROCm** | Radeon/Instinct | 60-100ms/embed | `pip install torch-rocm` |
| **CPU** | Fallback | 700ms/embed | Default |

### Hardware Detection

```python
from agentic_brain.rag import detect_hardware, get_best_device, get_hardware_info

# Auto-detect available hardware
device, info = detect_hardware()
print(f"Best device: {device}")
print(f"Info: {info}")
# Output: Best device: mlx (or cuda, mps, rocm, cpu)
# Info: {'platform': 'Darwin', 'apple_silicon': True, 'chip': 'Apple M2', 
#        'mlx': True, 'cuda': False, 'mps': True, ...}

# Get detailed hardware info
hw_info = get_hardware_info()
print(f"GPU Memory: {hw_info.get('gpu_memory')}")
print(f"CPU Cores: {hw_info.get('cpu_cores')}")
```

### Getting Accelerated Embeddings

```python
from agentic_brain.rag import get_embeddings, get_accelerated_embeddings

# Auto-detect best device (recommended)
embeddings = get_embeddings(provider="auto")

# Or get accelerated explicitly
embeddings = get_accelerated_embeddings()

# Force specific hardware
embeddings = get_embeddings(provider="mlx")      # Apple Silicon
embeddings = get_embeddings(provider="cuda")     # NVIDIA
embeddings = get_embeddings(provider="rocm")     # AMD
embeddings = get_embeddings(provider="sentence_transformers")  # CPU/MPS fallback
```

### Benchmark Results

```
Test: Embedding 1,000 sentences (768-dim vectors)

Hardware           Model                    Time      Speed      Relative
─────────────────────────────────────────────────────────────────────────
CPU (8-core)       all-MiniLM-L6-v2        50s       20 docs/s  1.0x (baseline)
Apple M2 (MPS)     all-MiniLM-L6-v2        12s       83 docs/s  4.2x faster
Apple M4 (MLX)     nomic-embed-text        5s       200 docs/s  10x faster
RTX 3080 (CUDA)    all-MiniLM-L6-v2        7s       143 docs/s  7.1x faster
RTX 4090 (CUDA)    all-MiniLM-L6-v2        3.5s     286 docs/s  14.3x faster
```

### Platform-Specific Setup

**Apple Silicon (M1-M4):**
```bash
# Option 1: MLX (fastest, native)
pip install mlx mlx-lm

# Option 2: PyTorch with MPS (slower, but CPU fallback works)
pip install torch torchvision torchaudio
```

**NVIDIA GPU:**
```bash
# CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Or CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**AMD GPU:**
```bash
# ROCm 5.7
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

---

## Embedding Providers

Embeddings convert text into dense vectors for semantic search. Each provider has different tradeoffs between speed, quality, cost, and privacy.

### Provider Comparison

| Provider | Dimensions | Speed | Quality | Cost | Privacy | Local |
|----------|-----------|-------|---------|------|---------|-------|
| **OllamaEmbeddings** | 768 | Fast | Good | Free | Fully Local | ✅ |
| **SentenceTransformerEmbeddings** | 384 | Medium | Good | Free | Fully Local | ✅ |
| **MLXEmbeddings** | 768 | Fastest | Good | Free | Fully Local | ✅ |
| **CUDAEmbeddings** | 768 | Fastest | Good | Free | Fully Local | ✅ |
| **ROCmEmbeddings** | 768 | Fastest | Good | Free | Fully Local | ✅ |
| **OpenAIEmbeddings** | 512 | Medium | Best | $0.02/M | Cloud | ❌ |

### OllamaEmbeddings

For local embeddings without dependencies. Requires Ollama running.

```python
from agentic_brain.rag import OllamaEmbeddings

# Requires: ollama pull nomic-embed-text
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://localhost:11434"
)

# Generate embeddings
vectors = embeddings.embed(["Hello world", "How are you?"])
# Returns: List[List[float]] - 768-dim vectors

# Single embedding
vec = embeddings.embed_query("What is AI?")
```

**Installation:**
```bash
# Install Ollama from ollama.com
# Then pull the embedding model
ollama pull nomic-embed-text
```

### SentenceTransformerEmbeddings

Fast, local, hardware-accelerated embeddings. Best for general use.

```python
from agentic_brain.rag import SentenceTransformerEmbeddings

embeddings = SentenceTransformerEmbeddings(
    model="all-MiniLM-L6-v2",  # Small, fast
    device="mps"                # or "cuda", "cpu"
)

# Alternative models by use case:
# - "all-MiniLM-L6-v2"      # Default, balanced (384D)
# - "all-mpnet-base-v2"     # Higher quality (768D)
# - "all-roberta-large-v1"  # Best quality (768D)
# - "sentence-t5-large"     # Multilingual (768D)

vectors = embeddings.embed(["Document 1", "Document 2"])

# Cache embeddings to disk for reuse
from agentic_brain.rag import CachedEmbeddings
cached = CachedEmbeddings(embeddings, cache_dir="./embeddings_cache")
```

**Installation:**
```bash
pip install sentence-transformers torch
```

### MLXEmbeddings

**Fastest option for Apple Silicon.** Native MLX acceleration for M1-M4 Macs.

```python
from agentic_brain.rag import MLXEmbeddings

embeddings = MLXEmbeddings(
    model="nomic-embed-text",  # Recommended
    # or try: "jinaai/jina-embeddings-v2-small"
)

vectors = embeddings.embed(["Text 1", "Text 2"])
```

**Installation:**
```bash
pip install mlx mlx-lm mlx-data
```

### CUDAEmbeddings

**For NVIDIA GPUs.** Fastest non-Apple option.

```python
from agentic_brain.rag import CUDAEmbeddings

embeddings = CUDAEmbeddings(
    model="all-MiniLM-L6-v2",
    device_id=0  # GPU device number
)

vectors = embeddings.embed(["Query 1", "Query 2"])
```

**Installation:**
```bash
# See PyTorch CUDA setup above
pip install sentence-transformers torch
```

### ROCmEmbeddings

**For AMD Radeon/Instinct GPUs.**

```python
from agentic_brain.rag import ROCmEmbeddings

embeddings = ROCmEmbeddings(
    model="all-MiniLM-L6-v2"
)

vectors = embeddings.embed(["Document 1", "Document 2"])
```

### OpenAIEmbeddings

**Best quality, cloud-hosted.** Use when you need maximum semantic understanding and have internet access.

```python
from agentic_brain.rag import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    api_key="sk-...",  # or env var OPENAI_API_KEY
    model="text-embedding-3-small"  # or "text-embedding-3-large"
)

vectors = embeddings.embed(["Query", "Document"])

# Large model has better quality but costs 5x more and is slower
# small: $0.02/M tokens (512D), fast
# large: $0.13/M tokens (3072D), slower, better quality
```

**Cost:** ~$0.02 per million tokens for `text-embedding-3-small`

### CachedEmbeddings (Wrapper)

**Avoid recomputing embeddings** by caching to disk. Wraps any provider.

```python
from agentic_brain.rag import get_embeddings, CachedEmbeddings

# Wrap any embeddings provider
base_embeddings = get_embeddings(provider="sentence_transformers")
cached = CachedEmbeddings(
    embeddings=base_embeddings,
    cache_dir="./embedding_cache",
    ttl_days=365  # Cache for 1 year
)

# First call: computes and caches
vec1 = cached.embed_query("Machine learning")

# Second call: returns cached result (instant)
vec2 = cached.embed_query("Machine learning")

# View cache stats
stats = cached.get_cache_stats()
print(f"Cache hit rate: {stats['hit_rate']}")
print(f"Stored embeddings: {stats['num_cached']}")
```

### Factory Function

```python
from agentic_brain.rag import get_embeddings

# Auto-detect best available hardware
embeddings = get_embeddings(provider="auto")

# Explicit provider selection
embeddings = get_embeddings(provider="sentence_transformers")
embeddings = get_embeddings(provider="mlx")
embeddings = get_embeddings(provider="cuda")
embeddings = get_embeddings(provider="ollama")
embeddings = get_embeddings(provider="openai")

# With options
embeddings = get_embeddings(
    provider="sentence_transformers",
    model="all-mpnet-base-v2",
    device="cuda",
    cache=True,
    cache_dir="./cache"
)
```

---

## Document Loaders

Load documents from cloud services and on-premise systems. 26 loaders support various sources.

### All Loaders

| Loader | Source | Requires | Auth Method | Example |
|--------|--------|----------|-------------|---------|
| **GoogleDriveLoader** | Google Drive | google-auth | OAuth2 or service account | `load_folder("My Project")` |
| **GmailLoader** | Gmail | google-auth | OAuth2 or service account | `load_recent(days=7)` |
| **iCloudLoader** | iCloud Drive | pyicloud | Apple ID + app password | `load_folder("Documents")` |
| **FirestoreLoader** | Firestore | firebase-admin | Service account JSON | `load_collection("articles")` |
| **S3Loader** | AWS S3 / MinIO | boto3 | AWS credentials or host key | `load_folder("reports/")` |
| **MongoDBLoader** | MongoDB | pymongo | Connection URI | `load_collection(filter={...})` |
| **GitHubLoader** | GitHub | PyGithub | Personal access token | `load_repo("owner/repo")` |
| **Microsoft365Loader** | OneDrive, SharePoint | msal, msgraph-core | Azure app registration | `load_folder("/drive/root")` |
| **NotionLoader** | Notion | notion-client | Notion API token | `load_database("database_id")` |
| **ConfluenceLoader** | Confluence | atlassian-python-api | Username + token | `load_space("SPACE_KEY")` |
| **SlackLoader** | Slack | slack-sdk | Bot token | `load_channel("channel_id")` |
| **DropboxLoader** | Dropbox | dropbox | OAuth2 token | `load_folder("/work")` |
| **BoxLoader** | Box | boxsdk | OAuth2 or JWT | `load_folder("0")` |
| **OneDriveLoader** | OneDrive | msal | Azure app OAuth2 | `load_folder("/Documents")` |
| **SharePointLoader** | SharePoint | msal | Azure app OAuth2 | `load_site("site_id")` |
| **DiscordLoader** | Discord | discord.py | Bot token | `load_channel("channel_id")` |
| **TeamsLoader** | Microsoft Teams | msal | Azure app OAuth2 | `load_channel("channel_id")` |
| **JiraLoader** | Jira Cloud/Server | jira | API token or OAuth | `load_project("PROJ")` |
| **AsanaLoader** | Asana | asana | Personal access token | `load_project("project_gid")` |
| **TrelloLoader** | Trello | py-trello | API key + token | `load_board("board_id")` |
| **AirtableLoader** | Airtable | pyairtable | API key | `load_base("base_id")` |
| **HubSpotLoader** | HubSpot CRM | hubspot-api-client | Private app token | `load_contacts()` |
| **SalesforceLoader** | Salesforce | simple-salesforce | OAuth2 or username/password | `load_objects("Account")` |
| **ZendeskLoader** | Zendesk | zenpy | API token | `load_tickets()` |
| **IntercomLoader** | Intercom | python-intercom | Access token | `load_conversations()` |
| **FreshdeskLoader** | Freshdesk | freshdesk-api | API key | `load_tickets()` |

### GoogleDriveLoader

Load documents from Google Drive. Supports OAuth2 or service account auth.

```python
from agentic_brain.rag import GoogleDriveLoader

# Method 1: OAuth2 (interactive, first use)
loader = GoogleDriveLoader()  # Will prompt for auth
docs = loader.load_folder("My Project")

# Method 2: Service account (automated)
loader = GoogleDriveLoader(
    credentials_path="/path/to/service-account.json"
)

# Load operations
docs = loader.load_folder("Project Name", recursive=True)
docs = loader.load_document("file_id_here")
docs = loader.search("annual report 2024", max_results=10)

# Metadata included
for doc in docs:
    print(f"Filename: {doc.filename}")
    print(f"Source ID: {doc.source_id}")
    print(f"Modified: {doc.modified_at}")
```

**Setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project, enable Google Drive API
3. Create OAuth2 credentials or download service account JSON

### GmailLoader

Load emails from Gmail.

```python
from agentic_brain.rag import GmailLoader

loader = GmailLoader(credentials_path="credentials.json")

# Load recent emails
docs = loader.load_recent(
    days=7,
    query="from:boss@company.com"
)

# Search emails
docs = loader.search(
    query="project status",
    max_results=20
)

# Gmail query syntax:
# "from:sender@example.com"
# "subject:meeting notes"
# "has:attachment"
# "is:unread"
# "before:2024-03-01"
```

### iCloudLoader

Load documents from iCloud Drive.

```python
from agentic_brain.rag import iCloudLoader

loader = iCloudLoader(
    apple_id="user@icloud.com",
    password="app-password"  # Not account password - generate app-specific
)

docs = loader.load_folder("Documents/Work")
docs = loader.search("meeting notes", max_results=10)
```

**Setup:** Generate app-specific password in iCloud settings → Security

### FirestoreLoader

Load from Firebase Firestore.

```python
from agentic_brain.rag import FirestoreLoader

loader = FirestoreLoader(
    service_account_path="firebase-adminsdk.json"
)

# Load collection
docs = loader.load_collection("articles")

# With filters
docs = loader.load_collection(
    "articles",
    where=[
        ("status", "==", "published"),
        ("category", "in", ["tech", "ai"])
    ]
)

# Search across collection
docs = loader.search("machine learning", max_results=20)
```

### S3Loader

Load from AWS S3 or MinIO.

```python
from agentic_brain.rag import S3Loader

# AWS S3
loader = S3Loader(bucket="my-documents")

# MinIO (self-hosted)
loader = S3Loader(
    bucket="documents",
    endpoint_url="http://minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin"
)

# Load operations
docs = loader.load_folder("reports/2024/")
docs = loader.load_document("reports/2024/annual.pdf")
docs = loader.search("quarterly", max_results=50)
```

### MongoDBLoader

Load from MongoDB.

```python
from agentic_brain.rag import MongoDBLoader

loader = MongoDBLoader(
    uri="mongodb://localhost:27017",
    database="knowledge",
    collection="documents"
)

# Load with filter
docs = loader.load_collection(
    filter={"category": "technical", "status": "active"}
)

# Search
docs = loader.search("deployment", max_results=30)
```

### GitHubLoader

Load from GitHub repositories.

```python
from agentic_brain.rag import GitHubLoader

loader = GitHubLoader(
    token="github_pat_...",  # Personal access token
)

# Load repository files
docs = loader.load_repo(
    owner="owner",
    repo="repo-name",
    path="docs/",  # Optional: specific path
    recursive=True
)

# Load issues
docs = loader.load_issues(
    owner="owner",
    repo="repo-name",
    state="open"  # or "closed", "all"
)

# Load pull requests
docs = loader.load_pull_requests(
    owner="owner",
    repo="repo-name",
    state="merged"
)
```

### Multi-Source Loading

```python
from agentic_brain.rag import load_from_multiple_sources

configs = [
    {
        "type": "google_drive",
        "credentials_path": "creds.json",
        "folder": "My Project"
    },
    {
        "type": "s3",
        "bucket": "documents",
        "prefix": "reports/"
    },
    {
        "type": "mongodb",
        "uri": "mongodb://localhost:27017",
        "database": "knowledge",
        "collection": "docs"
    }
]

all_docs = load_from_multiple_sources(configs)
print(f"Loaded {len(all_docs)} documents from 3 sources")
```

---

## Chunking Strategies

Divide documents into chunks for embedding and retrieval. Different strategies suit different content types.

### Strategy Comparison

| Strategy | Use Case | Best For | Preserves Structure |
|----------|----------|----------|-------------------|
| **FixedChunker** | Uniform splitting | Simple content | No |
| **SemanticChunker** | Sentence-aware | Articles, essays | Partial |
| **RecursiveChunker** | Multi-level fallback | Mixed content | Yes |
| **MarkdownChunker** | Document structure | Docs, wikis | Yes ✅ |

### FixedChunker

Simple fixed-size chunks. Predictable but may split sentences.

```python
from agentic_brain.rag import FixedChunker

chunker = FixedChunker(
    chunk_size=512,      # Characters per chunk
    overlap=50           # Overlap between chunks
)

chunks = chunker.chunk(document_text)

for chunk in chunks:
    print(f"Chunk {chunk.chunk_index}: {len(chunk.content)} chars")
    print(f"Position: {chunk.start_char}-{chunk.end_char}")
    print(f"Tokens: ~{chunk.token_count}")
```

### SemanticChunker

Groups sentences together, respecting semantic boundaries.

```python
from agentic_brain.rag import SemanticChunker

chunker = SemanticChunker(
    chunk_size=512,      # Target size
    overlap=50,
    separator="\n\n"     # Primary separator
)

chunks = chunker.chunk(document_text)
# Produces chunks at sentence/paragraph boundaries
```

### RecursiveChunker

Hierarchical approach: tries separators in order, falls back if chunks too large.

```python
from agentic_brain.rag import RecursiveChunker

chunker = RecursiveChunker(
    chunk_size=512,
    overlap=50,
    separators=[
        "\n\n",      # Try paragraph breaks first
        "\n",        # Then line breaks
        ". ",        # Then sentences
        " ",         # Then words
        ""           # Finally characters
    ]
)

chunks = chunker.chunk(document_text)
# Splits on best separator to keep structure
```

### MarkdownChunker

**Recommended for documentation.** Respects headers, code blocks, lists.

```python
from agentic_brain.rag import MarkdownChunker

chunker = MarkdownChunker(
    chunk_size=512,
    overlap=50
)

md_text = """
# Introduction

This is the intro.

## Section 1

Content here.

```python
code_block()
```

## Section 2

More content.
"""

chunks = chunker.chunk(md_text)
# Chunks respect header hierarchy and code blocks
```

### Factory Function

```python
from agentic_brain.rag import create_chunker, ChunkingStrategy

# By enum
chunker = create_chunker(ChunkingStrategy.SEMANTIC)

# By string
chunker = create_chunker("markdown", chunk_size=512)

# With options
chunker = create_chunker(
    strategy="recursive",
    chunk_size=512,
    overlap=50,
    separator="\n\n"
)
```

### Complete Chunking Pipeline

```python
from agentic_brain.rag import MarkdownChunker

# Load document
with open("documentation.md") as f:
    text = f.read()

# Chunk it
chunker = MarkdownChunker(chunk_size=512, overlap=50)
chunks = chunker.chunk(text)

# Add metadata
for i, chunk in enumerate(chunks):
    chunk.add_metadata("source_file", "documentation.md")
    chunk.add_metadata("section", i)
    chunk.add_metadata("word_count", len(chunk.content.split()))

# Embed chunks
from agentic_brain.rag import get_embeddings
embeddings = get_embeddings()
vectors = embeddings.embed([c.content for c in chunks])

print(f"Created {len(chunks)} chunks")
print(f"Average chunk size: {sum(len(c.content) for c in chunks) / len(chunks):.0f} chars")
```

---

## Reranking

Reorder search results by relevance. Improves precision with minimal speed cost.

### Reranker Comparison

| Reranker | Method | Speed | Accuracy | Use Case |
|----------|--------|-------|----------|----------|
| **QueryDocumentSimilarityReranker** | Vector similarity | ⚡⚡⚡ | Good | Quick reranking |
| **CrossEncoderReranker** | Cross-encoder model | ⚡⚡ | Best | Maximum precision |
| **MMRReranker** | Maximal Marginal Relevance | ⚡⚡ | Good+Diversity | Diverse results |
| **CombinedReranker** | Ensemble methods | ⚡ | Better | Robust ranking |
| **Reranker** | Auto best choice | ⚡⚡ | Best | Default recommendation |

### SimpleReranker (Embedding Similarity)

Fast reranking using vector similarity.

```python
from agentic_brain.rag import QueryDocumentSimilarityReranker

reranker = QueryDocumentSimilarityReranker(
    top_k=5  # Keep top 5 after reranking
)

reranked = reranker.rerank(query="machine learning", chunks=retrieved_chunks)

for chunk in reranked[:3]:
    print(f"Score: {chunk.score:.3f}")
    print(f"Content: {chunk.content[:100]}...")
```

### CrossEncoderReranker (Most Accurate)

Uses cross-encoder model (ms-marco-MiniLM-L6-v2) for best accuracy.

```python
from agentic_brain.rag import CrossEncoderReranker

reranker = CrossEncoderReranker(
    model="ms-marco-MiniLM-L6-v2",
    top_k=5
)

reranked = reranker.rerank(query, chunks)
```

**Installation:**
```bash
pip install sentence-transformers
```

### MMRReranker (Diversity)

Maximal Marginal Relevance: Balance relevance and diversity using lambda parameter.

```python
from agentic_brain.rag import MMRReranker

# λ=1.0: Pure relevance (same as regular ranking)
# λ=0.5: Balanced (default, recommended)
# λ=0.0: Pure diversity (very different results)

mmr = MMRReranker(
    lambda_param=0.5,  # Relevance/diversity tradeoff
    top_k=5
)

diverse_results = mmr.rerank(query, chunks)

# Use cases:
# - News summaries: λ=0.3 (want different articles)
# - FAQ search: λ=0.7 (want similar answers)
# - Documentation: λ=0.6 (want related but diverse docs)
```

### CombinedReranker (Ensemble)

Use multiple rerankers and combine scores for robustness.

```python
from agentic_brain.rag import (
    CombinedReranker,
    CrossEncoderReranker,
    MMRReranker,
    QueryDocumentSimilarityReranker
)

combined = CombinedReranker(
    rerankers=[
        CrossEncoderReranker(top_k=None),  # None = keep all
        MMRReranker(lambda_param=0.5, top_k=None),
        QueryDocumentSimilarityReranker(top_k=None)
    ],
    weights=[0.5, 0.3, 0.2],  # How to weight each reranker
    top_k=5
)

final_ranking = combined.rerank(query, chunks)
```

### Reranker (Recommended Default)

Auto-selects best reranker based on available models.

```python
from agentic_brain.rag import Reranker

reranker = Reranker()  # Uses cross-encoder by default

reranked = reranker.rerank(query, chunks)
```

### Pipeline Integration

```python
from agentic_brain.rag import HybridSearch, Reranker

# Hybrid search retrieval
search = HybridSearch()
retrieved = search.search(query, k=20)

# Rerank for precision
reranker = Reranker(top_k=5)
final_results = reranker.rerank(query, retrieved)

# Use top result
best_chunk = final_results[0]
print(f"Best match: {best_chunk.content[:200]}")
```

---

## Hybrid Search

Combine vector semantic search with keyword BM25 search for comprehensive retrieval.

### How It Works

1. **Vector Search:** Semantic understanding (catches paraphrases)
2. **Keyword Search:** Exact term matching (catches acronyms, jargon)
3. **Fusion:** Combine scores (RRF or linear weighted)

### BM25Index

Build keyword index for fast search.

```python
from agentic_brain.rag import BM25Index

index = BM25Index()

# Add documents
index.add_document("doc1", "machine learning is AI")
index.add_document("doc2", "deep learning neural networks")
index.add_document("doc3", "natural language processing")

# Build index (computes IDF)
index.build_index()

# Search
results = index.search("machine learning", k=2)
# Returns: [("doc1", score), ("doc2", score)]

# Save/load
index.save("bm25_index.pkl")
loaded_index = BM25Index.load("bm25_index.pkl")
```

### HybridSearch

Combine vector and keyword search.

```python
from agentic_brain.rag import HybridSearch, BM25Index
from agentic_brain.rag import get_embeddings

# Create hybrid search
search = HybridSearch(
    bm25_index=BM25Index(),
    embeddings=get_embeddings(),
    vector_weight=0.6,  # 60% weight on vector
    keyword_weight=0.4, # 40% weight on keywords
    fusion_method="rrf"  # or "linear"
)

# Add documents
for doc in documents:
    search.add_document(doc.id, doc.content)

# Search
results = search.search(
    query="machine learning basics",
    k=5
)

# Results include both vector and keyword scores
print(f"Vector results: {results.vector_results}")
print(f"Keyword results: {results.keyword_results}")
print(f"Fused results: {results.fused_results}")
```

### Fusion Methods

**RRF (Reciprocal Rank Fusion)** - Recommended:
```
score = 1/(k+rank_vector) + 1/(k+rank_keyword)
```

**Linear** - Simple weighted average:
```
score = vector_weight * vector_score + keyword_weight * keyword_score
```

### Weight Selection Guide

| Scenario | Vector Weight | Keyword Weight | Reason |
|----------|---------------|----------------|--------|
| General knowledge | 0.5 | 0.5 | Balanced |
| Academic papers | 0.7 | 0.3 | Semantic understanding |
| Code search | 0.3 | 0.7 | Exact syntax/terms |
| Customer support | 0.6 | 0.4 | Semantic + common phrases |
| Medical docs | 0.7 | 0.3 | Precise terminology |

### Example: Technical Documentation Search

```python
from agentic_brain.rag import HybridSearch, BM25Index, get_embeddings

# Create hybrid search optimized for technical docs
search = HybridSearch(
    bm25_index=BM25Index(),
    embeddings=get_embeddings(provider="sentence_transformers"),
    vector_weight=0.4,  # Less semantic, more keywords
    keyword_weight=0.6, # More exact terms (API names, commands)
    fusion_method="linear"
)

# Index all documentation
docs = load_documentation()
for doc in docs:
    search.add_document(doc.id, doc.content)

# User searches for "how to authenticate with JWT"
results = search.search("JWT authentication", k=5)

# Results include:
# - Keyword results: Exact matches for "JWT", "authentication"
# - Vector results: Semantic matches for "token-based auth"
# - Fused: Combined ranking

for result in results.fused_results[:3]:
    print(f"Relevance: {result.score:.2f}")
    print(f"Document: {result.document_id}")
```

---

## Evaluation

Rigorously evaluate RAG performance using standard IR metrics.

### Metrics

| Metric | Formula | Interpretation |
|--------|---------|-----------------|
| **Precision@k** | relevant_items_in_top_k / k | Of top k results, how many are relevant? |
| **Recall@k** | relevant_items_in_top_k / total_relevant | Of all relevant items, how many in top k? |
| **MRR** | 1 / rank_of_first_relevant | Position of first correct result |
| **NDCG@k** | DCG@k / IDCG@k | Ranking quality (penalizes bad positions) |
| **MAP** | Avg precision across all queries | Overall ranking quality |

### EvalDataset

Build evaluation dataset with queries and relevant documents.

```python
from agentic_brain.rag import EvalDataset, EvalQuery

dataset = EvalDataset()

# Add queries with relevant documents
dataset.add_query(
    query="How do I deploy to production?",
    relevant_docs=[
        "doc_123",  # Document IDs that answer this
        "doc_456"
    ],
    difficulty="medium",
    metadata={"category": "deployment"}
)

dataset.add_query(
    query="What is the company mission?",
    relevant_docs=["doc_789"],
    difficulty="easy",
    metadata={"category": "company"}
)

# Load from file
dataset = EvalDataset()
dataset.load_from_file("eval_dataset.json")

# Save dataset
dataset.save("eval_results.json")
```

### RAGEvaluator

Evaluate retrieval quality against benchmark dataset.

```python
from agentic_brain.rag import RAGEvaluator, EvalDataset, RAGPipeline

# Load evaluation dataset
dataset = EvalDataset()
dataset.load_from_file("eval_dataset.json")

# Create evaluator
evaluator = RAGEvaluator()

# Evaluate RAG pipeline
rag = RAGPipeline()

metrics = evaluator.evaluate(
    retrieval_func=rag.retrieve,  # Your retrieval function
    dataset=dataset,
    k_values=[1, 3, 5, 10]
)

# Results
print(f"Precision@5: {metrics.precision_at_k[5]:.3f}")
print(f"Recall@5: {metrics.recall_at_k[5]:.3f}")
print(f"MRR: {metrics.mrr:.3f}")
print(f"NDCG@5: {metrics.ndcg_at_k[5]:.3f}")
print(f"MAP: {metrics.map:.3f}")
```

### A/B Testing

Compare two retrieval strategies.

```python
from agentic_brain.rag import RAGEvaluator, EvalDataset

dataset = EvalDataset()
dataset.load_from_file("eval_dataset.json")

evaluator = RAGEvaluator()

# Strategy A: Vector search only
retriever_a = rag_vector_only.retrieve

# Strategy B: Hybrid search with reranking
retriever_b = rag_hybrid_with_reranking.retrieve

# Compare
results = evaluator.ab_test(
    retriever_a=retriever_a,
    retriever_b=retriever_b,
    dataset=dataset
)

print("STRATEGY A: Vector Search")
print(f"  Precision@5: {results['a'].precision_at_k[5]:.3f}")
print(f"  Recall@5:    {results['a'].recall_at_k[5]:.3f}")
print(f"  MRR:         {results['a'].mrr:.3f}")

print("\nSTRATEGY B: Hybrid + Reranking")
print(f"  Precision@5: {results['b'].precision_at_k[5]:.3f}")
print(f"  Recall@5:    {results['b'].recall_at_k[5]:.3f}")
print(f"  MRR:         {results['b'].mrr:.3f}")

print(f"\nWinner: {'B' if results['b'].mrr > results['a'].mrr else 'A'}")
```

### Example: Full Evaluation Pipeline

```python
from agentic_brain.rag import (
    RAGPipeline, EvalDataset, RAGEvaluator,
    MarkdownChunker, Reranker, HybridSearch
)

# 1. Build evaluation dataset
dataset = EvalDataset()
with open("eval_queries.json") as f:
    for line in f:
        query_data = json.loads(line)
        dataset.add_query(
            query=query_data["query"],
            relevant_docs=query_data["relevant_doc_ids"]
        )

# 2. Build RAG pipeline
rag = RAGPipeline(
    chunker=MarkdownChunker(),
    reranker=Reranker(),
    hybrid_search=HybridSearch()
)

# 3. Evaluate
evaluator = RAGEvaluator()
metrics = evaluator.evaluate(rag.retrieve, dataset, k_values=[1,3,5,10])

# 4. Report results
print(f"Dataset size: {len(dataset.queries)}")
print(f"Precision@5: {metrics.precision_at_k[5]:.3%}")
print(f"Recall@10: {metrics.recall_at_k[10]:.3%}")
print(f"MRR: {metrics.mrr:.3f}")

# 5. Iterate on weak areas
if metrics.recall_at_k[10] < 0.8:
    print("⚠️  Low recall - consider adjusting chunking strategy")
if metrics.precision_at_k[1] < 0.7:
    print("⚠️  Low precision - consider reranking or better embeddings")
```

---

## RAG Pipeline

End-to-end pipeline combining all components: retrieval, reranking, augmentation, generation.

### Quick Query Interface

```python
from agentic_brain.rag import ask

# Simplest usage
answer = ask("What's the project status?")
print(answer)
```

### Full Pipeline

```python
from agentic_brain.rag import RAGPipeline

# Create pipeline
rag = RAGPipeline(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
    llm_provider="ollama",  # or "openai"
    llm_model="llama2"
)

# Query
result = rag.query("How do I deploy to production?")

# Result includes
print(f"Answer: {result.answer}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Sources: {result.sources}")  # Citations
print(f"Retrieved chunks: {len(result.retrieved_chunks)}")
```

### With Custom Components

```python
from agentic_brain.rag import (
    RAGPipeline, MarkdownChunker, Reranker,
    HybridSearch, get_embeddings
)

rag = RAGPipeline(
    chunker=MarkdownChunker(chunk_size=512),
    embeddings=get_embeddings(provider="mlx"),
    reranker=Reranker(),
    hybrid_search=HybridSearch(
        vector_weight=0.6,
        keyword_weight=0.4
    ),
    llm_provider="openai",
    llm_model="gpt-4"
)

result = rag.query("Technical question?")
```

### Streaming Responses

```python
from agentic_brain.rag import RAGPipeline

rag = RAGPipeline()

# Stream response token by token
for chunk in rag.query_stream("Your question"):
    print(chunk, end="", flush=True)
```

### Caching

```python
from agentic_brain.rag import RAGPipeline

rag = RAGPipeline(
    cache_results=True,
    cache_ttl_seconds=3600  # 1 hour
)

# First query: retrieves and caches
result1 = rag.query("How to deploy?")

# Second identical query: returns cached result instantly
result2 = rag.query("How to deploy?")

# Clear cache
rag.clear_cache()
```

---

## Complete Examples

### Example 1: Document Q&A System

```python
from agentic_brain.rag import (
    RAGPipeline, MarkdownChunker, GoogleDriveLoader,
    get_embeddings, Reranker
)
import time

# 1. Load documents from Google Drive
loader = GoogleDriveLoader(credentials_path="creds.json")
docs = loader.load_folder("Knowledge Base")
print(f"Loaded {len(docs)} documents")

# 2. Create RAG pipeline
rag = RAGPipeline(
    chunker=MarkdownChunker(chunk_size=512, overlap=50),
    embeddings=get_embeddings(provider="auto"),
    reranker=Reranker(),
    llm_provider="openai"
)

# 3. Ingest documents
for doc in docs:
    rag.add_document(doc.filename, doc.content)
print(f"Ingested documents")

# 4. Query
start = time.time()
result = rag.query("How do I request time off?")
elapsed = time.time() - start

print(f"\n📚 Question: How do I request time off?")
print(f"\n💬 Answer: {result.answer}")
print(f"\n🔍 Sources:")
for source in result.sources:
    print(f"  - {source['filename']} (confidence: {source['confidence']:.0%})")
print(f"\n⏱️  Retrieved in {elapsed:.1f}s")
```

### Example 2: Code Search

```python
from agentic_brain.rag import (
    RAGPipeline, RecursiveChunker, GitHubLoader,
    HybridSearch, get_embeddings
)

# 1. Load code from GitHub
loader = GitHubLoader(token="github_pat_...")
docs = loader.load_repo("owner", "awesome-project", path="src/")

# 2. Create code-optimized RAG
rag = RAGPipeline(
    chunker=RecursiveChunker(
        chunk_size=256,  # Smaller for code
        overlap=25
    ),
    embeddings=get_embeddings(provider="sentence_transformers"),
    hybrid_search=HybridSearch(
        vector_weight=0.3,  # Less semantic for code
        keyword_weight=0.7  # More keywords
    )
)

for doc in docs:
    rag.add_document(doc.filename, doc.content)

# 3. Search
result = rag.query("How is authentication implemented?")
print(result.answer)
```

### Example 3: Multi-Source Knowledge Base

```python
from agentic_brain.rag import load_from_multiple_sources, RAGPipeline

# Load from multiple sources
configs = [
    {"type": "google_drive", "folder": "Company Docs"},
    {"type": "github", "repo": "owner/wiki"},
    {"type": "notion", "database_id": "abc123"},
    {"type": "s3", "bucket": "knowledge", "prefix": "docs/"}
]

docs = load_from_multiple_sources(configs)
print(f"Loaded {len(docs)} documents from 4 sources")

# Create RAG
rag = RAGPipeline()
for doc in docs:
    rag.add_document(f"{doc.source}:{doc.filename}", doc.content)

# Query
result = rag.query("What's our policy on remote work?")
print(result.answer)

# View sources - shows which service the answer came from
for source in result.sources:
    print(f"From {source['source']}: {source['filename']}")
```

### Example 4: Evaluation and Optimization

```python
from agentic_brain.rag import (
    RAGPipeline, RAGEvaluator, EvalDataset,
    MarkdownChunker, HybridSearch, Reranker
)
import json

# 1. Create evaluation dataset
dataset = EvalDataset()
with open("test_queries.json") as f:
    for line in f:
        q = json.loads(line)
        dataset.add_query(q["query"], q["relevant_docs"])

# 2. Test multiple strategies
strategies = [
    {
        "name": "Vector Only",
        "config": {"hybrid": False, "rerank": False}
    },
    {
        "name": "Hybrid (balanced)",
        "config": {"hybrid": True, "vector_weight": 0.5, "rerank": False}
    },
    {
        "name": "Hybrid + Reranking",
        "config": {"hybrid": True, "vector_weight": 0.6, "rerank": True}
    }
]

# 3. Evaluate each
evaluator = RAGEvaluator()
results = {}

for strategy in strategies:
    config = strategy["config"]
    rag = RAGPipeline(
        hybrid_search=config["hybrid"],
        reranker=Reranker() if config.get("rerank") else None
    )
    
    metrics = evaluator.evaluate(rag.retrieve, dataset, k_values=[1,3,5])
    results[strategy["name"]] = metrics

# 4. Compare
print("\n🏆 Comparison\n")
print(f"{'Strategy':<25} {'P@5':<8} {'R@5':<8} {'MRR':<8}")
print("-" * 50)
for name, metrics in results.items():
    p5 = metrics.precision_at_k.get(5, 0)
    r5 = metrics.recall_at_k.get(5, 0)
    print(f"{name:<25} {p5:<8.3f} {r5:<8.3f} {metrics.mrr:<8.3f}")

# 5. Pick winner
best = max(results.items(), key=lambda x: x[1].mrr)
print(f"\n✅ Best strategy: {best[0]}")
```

---

## Performance Tips

### Optimize for Speed

```python
# 1. Use appropriate hardware
embeddings = get_embeddings(provider="auto")  # Auto-detects

# 2. Cache embeddings
from agentic_brain.rag import CachedEmbeddings
cached = CachedEmbeddings(embeddings, cache_dir="./cache")

# 3. Use smaller embedding models
embeddings = get_embeddings(
    provider="sentence_transformers",
    model="all-MiniLM-L6-v2"  # Small, fast
)

# 4. Batch operations
vectors = embeddings.embed(batch_of_texts)  # Not one at a time

# 5. Use BM25 for keyword search (skip if not needed)
# Only enable reranking if precision matters more than speed
```

### Optimize for Quality

```python
# 1. Better embeddings model
embeddings = get_embeddings(
    provider="sentence_transformers",
    model="all-mpnet-base-v2"  # Larger, higher quality
)

# 2. Markdown-aware chunking
from agentic_brain.rag import MarkdownChunker
chunker = MarkdownChunker()

# 3. Cross-encoder reranking
from agentic_brain.rag import CrossEncoderReranker
reranker = CrossEncoderReranker()

# 4. Hybrid search with proper weighting
from agentic_brain.rag import HybridSearch
search = HybridSearch(
    vector_weight=0.6,
    keyword_weight=0.4
)

# 5. Evaluate and iterate
from agentic_brain.rag import RAGEvaluator
evaluator = RAGEvaluator()
metrics = evaluator.evaluate(rag.retrieve, dataset)
```

### Cost Optimization (Cloud APIs)

```python
# 1. Cache embeddings to avoid recomputation
from agentic_brain.rag import CachedEmbeddings
cached = CachedEmbeddings(
    get_embeddings(provider="openai"),
    cache_dir="./cache"
)

# 2. Use smaller embedding models
embeddings = get_embeddings(
    provider="openai",
    model="text-embedding-3-small"  # Cheaper, faster
)

# 3. Batch API calls
vectors = embeddings.embed(large_batch)  # Not individual calls

# 4. Local embeddings when possible
embeddings = get_embeddings(provider="sentence_transformers")  # Free
```

---

## Troubleshooting

### No CUDA/MPS/MLX Support

**Problem:** Getting CPU fallback when GPU available

**Solution:**
```python
from agentic_brain.rag import detect_hardware, get_hardware_info

device, info = detect_hardware()
hw = get_hardware_info()

print(f"Detected device: {device}")
print(f"Apple Silicon: {info.get('apple_silicon')}")
print(f"CUDA available: {info.get('cuda')}")
print(f"MPS available: {info.get('mps')}")
print(f"MLX available: {info.get('mlx')}")

# If empty, install appropriate library:
# MLX: pip install mlx mlx-lm
# CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu118
# MPS: pip install torch (comes with PyTorch)
```

### Slow Embeddings

**Problem:** Embeddings taking >100ms each

**Solution:**
1. Check if using GPU: `detect_hardware()`
2. Use smaller model: `model="all-MiniLM-L6-v2"`
3. Enable caching: `CachedEmbeddings(...)`
4. Batch process: `embed(list_of_texts)`

### Out of Memory

**Problem:** OOM error during embedding

**Solution:**
```python
# Reduce batch size
embeddings = get_embeddings()
for batch in chunk_text(texts, batch_size=32):  # Smaller batches
    vectors = embeddings.embed(batch)

# Use smaller model
embeddings = get_embeddings(
    provider="sentence_transformers",
    model="all-MiniLM-L6-v2"
)

# Disable GPU
embeddings = get_embeddings(device="cpu")
```

### Poor Retrieval Results

**Problem:** Not finding relevant documents

**Solution:**
```python
from agentic_brain.rag import RAGEvaluator, EvalDataset

# 1. Create test queries
dataset = EvalDataset()
dataset.add_query("Test query", ["relevant_doc_ids"])

# 2. Evaluate current pipeline
evaluator = RAGEvaluator()
metrics = evaluator.evaluate(rag.retrieve, dataset)

# 3. If low metrics, try:
# - Better embeddings model
# - Hybrid search instead of vector-only
# - Reranking with cross-encoder
# - Different chunking strategy
```

---

## API Reference

### Key Classes

```python
# Core
RAGPipeline, RAGResult, ask, Retriever, RetrievedChunk

# Embeddings
EmbeddingProvider, get_embeddings
OllamaEmbeddings, OpenAIEmbeddings, SentenceTransformerEmbeddings
MLXEmbeddings, CUDAEmbeddings, ROCmEmbeddings, CachedEmbeddings
detect_hardware, get_best_device, get_hardware_info

# Document Storage
Document, DocumentStore, InMemoryDocumentStore, FileDocumentStore

# Chunking
BaseChunker, Chunk, ChunkingStrategy
FixedChunker, SemanticChunker, RecursiveChunker, MarkdownChunker
create_chunker

# Reranking
BaseReranker, RerankResult
QueryDocumentSimilarityReranker, CrossEncoderReranker
MMRReranker, CombinedReranker, Reranker

# Hybrid Search
BM25Index, HybridSearch, HybridSearchResult

# Evaluation
EvalQuery, EvalMetrics, EvalResults, EvalDataset, RAGEvaluator

# Loaders
LoadedDocument, BaseLoader
GoogleDriveLoader, GmailLoader, iCloudLoader
FirestoreLoader, S3Loader, MongoDBLoader
GitHubLoader, Microsoft365Loader, NotionLoader
ConfluenceLoader, SlackLoader
create_loader, load_from_multiple_sources
```

### Hardware Detection

```python
detect_hardware() -> (str, Dict[str, Any])
get_best_device() -> str
get_hardware_info() -> Dict[str, Any]
get_accelerated_embeddings() -> EmbeddingProvider
```

### Embeddings

```python
# Create embeddings
embeddings = get_embeddings(provider="auto", cache=True, model="...")

# Generate embeddings
vectors = embeddings.embed(list_of_texts)
vector = embeddings.embed_query(text)
```

### Chunking

```python
chunker = create_chunker(strategy, chunk_size=512, overlap=50)
chunks = chunker.chunk(text)

for chunk in chunks:
    print(chunk.content)
    print(chunk.token_count)
    print(chunk.metadata)
```

### Reranking

```python
reranker = Reranker(top_k=5)
reranked = reranker.rerank(query, chunks)
```

### Hybrid Search

```python
search = HybridSearch(vector_weight=0.6, keyword_weight=0.4)
results = search.search(query, k=5)
```

### Evaluation

```python
dataset = EvalDataset()
dataset.add_query(query, relevant_docs)

evaluator = RAGEvaluator()
metrics = evaluator.evaluate(retriever_func, dataset, k_values=[1,3,5])
```

---

## See Also

- [Architecture Guide](architecture.md) - System design
- [Setup Guide](SETUP.md) - Installation and configuration
- [API Reference](api-reference.md) - Full API docs
- [Streaming Guide](STREAMING.md) - Real-time responses
- [Enterprise Guide](ENTERPRISE.md) - Production deployment

---

**Last Updated:** 2024-03-21  
**Status:** Production Ready ✅
