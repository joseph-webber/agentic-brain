# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
RAG (Retrieval-Augmented Generation) Pipeline

Production-ready RAG with:
- Multi-source retrieval (Neo4j, files, APIs)
- Semantic search with embeddings
- Advanced chunking strategies (fixed, semantic, recursive, markdown)
- Reranking for precision (cross-encoder, MMR, diversity)
- Hybrid search (vector + keyword BM25)
- Evaluation and A/B testing
- Source citation with confidence scores
- Caching for efficiency
- Cloud document loaders (Google Drive, Gmail, iCloud)

For advanced RAG features (multi-tenant isolation, streaming),
see: https://github.com/joseph-webber/brain-core

Import weight guide
-------------------
``rag.pipeline``    — medium  (imports neo4j driver, core retrieval)
``rag.embeddings``  — heavy   (sentence-transformers, optional MLX/CUDA;
                                hardware-accelerated variants guarded by
                                try/except and only loaded when available)
``rag.loaders``     — heavy   (54 optional cloud/DB connectors; each guarded
                                by its own availability flag — unused loaders
                                add zero runtime cost)
``rag.graphql_api`` — heavy   (strawberry-graphql; guarded by STRAWBERRY_AVAILABLE)

If startup time matters, import pipeline components directly::

    from agentic_brain.rag.pipeline import RAGPipeline
    from agentic_brain.rag.chunking import create_chunker

Usage:
    from agentic_brain.rag import RAGPipeline, ask

    # Quick interface
    answer = ask("What is the status of project X?")

    # Full pipeline with advanced features
    rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
    result = rag.query("How do I deploy?")

    # Advanced chunking
    from agentic_brain.rag import create_chunker, ChunkingStrategy
    chunker = create_chunker(ChunkingStrategy.MARKDOWN)
    chunks = chunker.chunk(text)

    # Reranking
    from agentic_brain.rag import Reranker, MMRReranker
    reranker = Reranker()
    reranked = reranker.rerank(query, chunks)

    # Hybrid search
    from agentic_brain.rag import HybridSearch
    search = HybridSearch()
    results = search.search(query, chunks)

    # Evaluation
    from agentic_brain.rag import RAGEvaluator, EvalDataset
    evaluator = RAGEvaluator()
    dataset = EvalDataset()
    metrics = evaluator.evaluate(rag.query, dataset)

    # Cloud loaders
    from agentic_brain.rag import GoogleDriveLoader, GmailLoader, iCloudLoader
    drive = GoogleDriveLoader(credentials_path="creds.json")
    docs = drive.load_folder("My Project")
"""

# Core pipeline
import contextlib

from .embeddings import EmbeddingProvider, get_embeddings
from .pipeline import (
    GraphQueryResult,
    GraphSearchResult,
    IngestResult,
    RAGPipeline,
    RAGResult,
    ask,
)
from .retriever import RetrievedChunk, Retriever

# Hardware-accelerated embeddings
try:
    from .embeddings import SentenceTransformerEmbeddings

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    from .embeddings import MLXEmbeddings

    MLX_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    MLX_AVAILABLE = False

try:
    from .embeddings import CUDAEmbeddings

    CUDA_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    CUDA_AVAILABLE = False

with contextlib.suppress(ImportError, ModuleNotFoundError):
    from .embeddings import ROCmEmbeddings

# Hardware detection utilities
with contextlib.suppress(ImportError, ModuleNotFoundError):
    from .embeddings import (
        detect_hardware,
        get_best_device,
        get_hardware_info,
    )

# Hardware availability flags
try:
    import torch

    CUDA_DEVICE_AVAILABLE = torch.cuda.is_available()
    MPS_AVAILABLE = torch.backends.mps.is_available()
except (ImportError, ModuleNotFoundError):
    CUDA_DEVICE_AVAILABLE = False
    MPS_AVAILABLE = False

# Accelerated embeddings helper (optional - added after hardware module completion)
with contextlib.suppress(ImportError, ModuleNotFoundError):
    from .embeddings import get_accelerated_embeddings

# Document store
# Advanced chunking
from .chunking import (
    CHONKIE_AVAILABLE,
    BaseChunker,
    Chunk,
    ChunkingStrategy,
    FixedChunker,
    MarkdownChunker,
    RecursiveChunker,
    SemanticChunker,
    create_chunker,
)

# Chonkie fast chunking (optional)
if CHONKIE_AVAILABLE:
    from .chunking import ChonkieChunker, ChonkieStrategy, benchmark_chunkers

# Contextual compression (reduce chunk noise)
from .contextual_compression import (
    ChainedCompressor,
    CompressedChunk,
    CompressionResult,
    CompressionStrategy,
    ContextualCompressor,
)

# Evaluation
from .evaluation import (
    EvalDataset,
    EvalMetrics,
    EvalQuery,
    EvalResults,
    RAGEvaluator,
)
from .graph_rag import (
    GraphRAG,
    GraphRAGConfig,
    SearchStrategy,
)

# Graph traversal (Neo4j relationship-aware retrieval)
from .graph_traversal import (
    EntityCentricRetriever,
    GraphContext,
    GraphNode,
    GraphTraversalRetriever,
    TraversalStrategy,
)

# GraphQL API (Strawberry)
from .graphql_api import (
    STRAWBERRY_AVAILABLE,
    create_graphql_app,
    get_context,
    get_schema,
)

# Hybrid search
from .hybrid import (
    BM25Index,
    HybridSearch,
    HybridSearchResult,
)

# Document loaders - modular package (migrated from monolith 2026-03-23)
from .loaders import (
    # Availability flags
    BOTO3_AVAILABLE,
    CONFLUENCE_AVAILABLE,
    FIREBASE_AVAILABLE,
    GOOGLE_API_AVAILABLE,
    GOOGLE_DRIVE_AVAILABLE,
    MSAL_AVAILABLE,
    NOTION_AVAILABLE,
    PYGITHUB_AVAILABLE,
    PYICLOUD_AVAILABLE,
    PYMONGO_AVAILABLE,
    # Social/Collaboration
    SLACK_AVAILABLE,
    AfterpayLoader,
    # Other
    APILoader,
    AzureBlobLoader,
    # Base
    BaseLoader,
    CMISLoader,
    ConfluenceLoader,
    CSVLoader,
    DeputyLoader,
    DocxLoader,
    Dynamics365Loader,
    ElasticsearchLoader,
    EmploymentHeroLoader,
    ExcelLoader,
    FirestoreLoader,
    GCSLoader,
    GitHubLoader,
    # Email
    GmailLoader,
    GoogleDriveLoader,
    HTMLLoader,
    JSONLLoader,
    JSONLoader,
    LoadedDocument,
    MarkdownLoader,
    Microsoft365Loader,
    MinIOLoader,
    # NoSQL
    MongoDBLoader,
    # Australian business
    MYOBLoader,
    MySQLLoader,
    NotionLoader,
    OracleLoader,
    PayPalLoader,
    # Documents
    PDFLoader,
    # Database (SQL injection protected)
    PostgreSQLLoader,
    QuickBooksLoader,
    RateLimitError,
    RedisLoader,
    RESTLoader,
    # Cloud storage
    S3Loader,
    # CRM (SQL injection protected)
    SalesforceLoader,
    # Enterprise
    SAPLoader,
    ServiceNowLoader,
    # Payments/E-commerce
    ShopifyLoader,
    SlackLoader,
    StripeLoader,
    # Text
    TextLoader,
    WebLoader,
    WooCommerceLoader,
    WordLoader,
    WorkdayLoader,
    XeroLoader,
    create_loader,
    get_available_loaders,
    iCloudLoader,
    load_from_multiple_sources,
    with_rate_limit,
)

# Additional availability flags exposed by loader modules
try:
    from .loaders.cloud import AZURE_BLOB_AVAILABLE, GCS_AVAILABLE
except (ImportError, ModuleNotFoundError):
    AZURE_BLOB_AVAILABLE = False
    GCS_AVAILABLE = False

try:
    from .loaders.database import MYSQL_AVAILABLE, POSTGRES_AVAILABLE
except (ImportError, ModuleNotFoundError):
    MYSQL_AVAILABLE = False
    POSTGRES_AVAILABLE = False

try:
    from .loaders.nosql import ELASTICSEARCH_AVAILABLE, REDIS_AVAILABLE
except (ImportError, ModuleNotFoundError):
    ELASTICSEARCH_AVAILABLE = False
    REDIS_AVAILABLE = False

# Multi-hop reasoning (chain of reasoning)
from .multi_hop_reasoning import (
    GraphMultiHopReasoner,
    HopType,
    MultiHopReasoner,
    ReasoningChain,
    ReasoningHop,
)

# Parallel retrieval (concurrent multi-source search)
from .parallel_retrieval import (
    FederatedRetriever,
    ParallelResult,
    ParallelRetrievalResult,
    ParallelRetriever,
    RetrievalSource,
    SourceType,
)

# Query decomposition (complex query handling)
from .query_decomposition import (
    DecompositionResult,
    ParallelQueryDecomposer,
    QueryDecomposer,
    SubQuery,
)

# Advanced reranking
from .reranking import (
    BaseReranker,
    CombinedReranker,
    CrossEncoderReranker,
    MMRReranker,
    QueryDocumentSimilarityReranker,
    Reranker,
    RerankResult,
)

# Semantic routing (query intent classification)
from .semantic_router import (
    Route,
    RouteMatch,
    SemanticRouter,
)
from .store import (
    Document,
    DocumentStore,
    FileDocumentStore,
    InMemoryDocumentStore,
)

__all__ = [
    # Core
    "RAGPipeline",
    "RAGResult",
    "IngestResult",
    "GraphSearchResult",
    "GraphQueryResult",
    "ask",
    "Retriever",
    "RetrievedChunk",
    "EmbeddingProvider",
    "get_embeddings",
    # Hardware-accelerated Embeddings
    "SentenceTransformerEmbeddings",
    "MLXEmbeddings",
    "CUDAEmbeddings",
    "ROCmEmbeddings",
    "detect_hardware",
    "get_best_device",
    "get_hardware_info",
    "get_accelerated_embeddings",
    # Availability Flags
    "SENTENCE_TRANSFORMERS_AVAILABLE",
    "MLX_AVAILABLE",
    "CUDA_AVAILABLE",
    "CUDA_DEVICE_AVAILABLE",
    "MPS_AVAILABLE",
    # Document Store
    "Document",
    "DocumentStore",
    "InMemoryDocumentStore",
    "FileDocumentStore",
    # Chunking
    "BaseChunker",
    "Chunk",
    "ChunkingStrategy",
    "FixedChunker",
    "SemanticChunker",
    "RecursiveChunker",
    "MarkdownChunker",
    "create_chunker",
    # Chonkie fast chunking
    "CHONKIE_AVAILABLE",
    "ChonkieChunker",
    "ChonkieStrategy",
    "benchmark_chunkers",
    # Reranking
    "BaseReranker",
    "RerankResult",
    "QueryDocumentSimilarityReranker",
    "CrossEncoderReranker",
    "MMRReranker",
    "CombinedReranker",
    "Reranker",
    # Hybrid Search
    "BM25Index",
    "HybridSearch",
    "HybridSearchResult",
    # Evaluation
    "EvalQuery",
    "EvalMetrics",
    "EvalResults",
    "EvalDataset",
    "RAGEvaluator",
    # Cloud Loaders
    "LoadedDocument",
    "BaseLoader",
    "GoogleDriveLoader",
    "GmailLoader",
    "iCloudLoader",
    "FirestoreLoader",
    "S3Loader",
    "MongoDBLoader",
    "GitHubLoader",
    "Microsoft365Loader",
    "NotionLoader",
    "ConfluenceLoader",
    "SlackLoader",
    "create_loader",
    "load_from_multiple_sources",
    "GOOGLE_API_AVAILABLE",
    "PYICLOUD_AVAILABLE",
    "FIREBASE_AVAILABLE",
    "BOTO3_AVAILABLE",
    "PYMONGO_AVAILABLE",
    "PYGITHUB_AVAILABLE",
    "MSAL_AVAILABLE",
    "NOTION_AVAILABLE",
    "CONFLUENCE_AVAILABLE",
    "SLACK_AVAILABLE",
    # New Cloud Storage Loaders
    "AzureBlobLoader",
    "GCSLoader",
    "MinIOLoader",
    "AZURE_BLOB_AVAILABLE",
    "GCS_AVAILABLE",
    # Database Loaders
    "PostgreSQLLoader",
    "MySQLLoader",
    "ElasticsearchLoader",
    "RedisLoader",
    "OracleLoader",
    "POSTGRES_AVAILABLE",
    "MYSQL_AVAILABLE",
    "ELASTICSEARCH_AVAILABLE",
    "REDIS_AVAILABLE",
    # Enterprise Loaders
    "SAPLoader",
    "ServiceNowLoader",
    "WorkdayLoader",
    # CRM Loaders
    "Dynamics365Loader",
    # Australian Business Loaders
    "MYOBLoader",
    "XeroLoader",
    "EmploymentHeroLoader",
    "DeputyLoader",
    # Payment Gateway Loaders
    "StripeLoader",
    "PayPalLoader",
    "AfterpayLoader",
    # E-Commerce Platform Loaders
    "ShopifyLoader",
    "WooCommerceLoader",
    # Accounting Loaders
    "QuickBooksLoader",
    # Semantic Routing
    "SemanticRouter",
    "Route",
    "RouteMatch",
    # Query Decomposition
    "QueryDecomposer",
    "ParallelQueryDecomposer",
    "SubQuery",
    "DecompositionResult",
    # Parallel Retrieval
    "ParallelRetriever",
    "FederatedRetriever",
    "ParallelResult",
    "ParallelRetrievalResult",
    "RetrievalSource",
    "SourceType",
    # Multi-Hop Reasoning
    "MultiHopReasoner",
    "GraphMultiHopReasoner",
    "ReasoningHop",
    "ReasoningChain",
    "HopType",
    # Rate Limiting
    "with_rate_limit",
    "RateLimitError",
    # Contextual Compression
    "ContextualCompressor",
    "ChainedCompressor",
    "CompressedChunk",
    "CompressionResult",
    "CompressionStrategy",
    # Graph Traversal
    "GraphTraversalRetriever",
    "EntityCentricRetriever",
    "GraphNode",
    "GraphContext",
    "TraversalStrategy",
    # Advanced GraphRAG
    "GraphRAG",
    "GraphRAGConfig",
    "SearchStrategy",
    # Enhanced Graph RAG
    "EnhancedGraphRAG",
    "EnhancedGraphRAGConfig",
    "RetrievalStrategy",
    # GraphQL API
    "STRAWBERRY_AVAILABLE",
    "create_graphql_app",
    "get_schema",
    "get_context",
]
