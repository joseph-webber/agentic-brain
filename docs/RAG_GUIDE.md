# 🧠 GraphRAG Guide

> **GraphRAG is our CORE differentiator.** While others do basic vector search, we build **knowledge graphs** that understand relationships, context, and meaning.

---

<div align="center">

## 🌟 Why GraphRAG Changes Everything

| Traditional RAG | GraphRAG (Agentic Brain) |
|-----------------|--------------------------|
| Chunks are isolated blobs | Chunks are **connected nodes** |
| "Find similar text" | "Find related **concepts**" |
| Flat retrieval | **Multi-hop reasoning** |
| No context between docs | **Cross-document relationships** |
| Simple keyword + vector | **Graph traversal + semantic** |

</div>

---

## 💡 The Problem with Traditional RAG

Traditional RAG has a fundamental limitation: **it treats documents as isolated islands**.

```
Traditional RAG:
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   [Doc A] ─────?───── [Doc B] ─────?───── [Doc C]               │
│      ↓                    ↓                    ↓                 │
│   Embed                Embed                Embed                │
│      ↓                    ↓                    ↓                 │
│   [Vec A]              [Vec B]              [Vec C]              │
│                                                                  │
│   Query: "What did Sarah say about the project timeline?"        │
│          ↓                                                       │
│   Finds: Doc B (mentions "project timeline")                     │
│   Misses: Doc A (Sarah), Doc C (Sarah's concerns) ❌             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**The query found "project timeline" but missed that Sarah's concerns in Doc C relate to the same project discussed in Doc A!**

---

## 🎯 How GraphRAG Solves This

GraphRAG builds a **knowledge graph** where documents, entities, and concepts are connected:

```
GraphRAG Knowledge Graph:
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│           [Sarah] ───AUTHORED──→ [Doc A]                         │
│              │                      │                            │
│          MENTIONED_IN            DISCUSSES                       │
│              │                      │                            │
│              ↓                      ↓                            │
│           [Doc C] ←──RELATED_TO── [Project X]                    │
│              │                      │                            │
│          CONTAINS                HAS_TIMELINE                    │
│              │                      │                            │
│              ↓                      ↓                            │
│         [Concerns] ──ABOUT──→ [Timeline]                         │
│                                                                  │
│   Query: "What did Sarah say about the project timeline?"        │
│          ↓                                                       │
│   Traverses: Sarah → authored → Doc A → discusses → Project X   │
│              → has_timeline → Timeline ← about ← Concerns        │
│              ← contains ← Doc C ← mentioned_in ← Sarah           │
│                                                                  │
│   Finds: Doc A, Doc B, AND Doc C with full context! ✅           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**GraphRAG connects the dots that traditional RAG can't see.**

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GRAPHRAG PIPELINE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   54 Data    │───→│   Chunking   │───→│   Entity     │          │
│  │   Loaders    │    │   Engine     │    │   Extraction │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│                                                 │                   │
│                                                 ↓                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   Vector     │←───│   Embedding  │←───│ Relationship │          │
│  │   Index      │    │   (M2/CUDA)  │    │  Extraction  │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             ↓                                       │
│                    ┌──────────────────┐                            │
│                    │     NEO4J        │                            │
│                    │  Knowledge Graph │                            │
│                    │                  │                            │
│                    │  • Nodes (Chunks,│                            │
│                    │    Entities)     │                            │
│                    │  • Relationships │                            │
│                    │  • Vectors       │                            │
│                    │  • Metadata      │                            │
│                    └──────────────────┘                            │
│                             │                                       │
│         ┌───────────────────┼───────────────────┐                   │
│         ↓                   ↓                   ↓                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │    Graph     │    │   Hybrid     │    │    LLM       │          │
│  │   Traversal  │    │   Search     │    │   Reranking  │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             ↓                                       │
│                    ┌──────────────────┐                            │
│                    │    RESPONSE      │                            │
│                    │  + Citations     │                            │
│                    │  + Confidence    │                            │
│                    └──────────────────┘                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Basic GraphRAG Query

```python
from agentic_brain.rag import RAGPipeline

# Initialize with Neo4j
rag = RAGPipeline(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"
)

# Ingest documents (builds knowledge graph automatically)
await rag.ingest("./documents/")

# Query with GraphRAG
result = await rag.query("What are Sarah's concerns about the timeline?")

print(f"Answer: {result.answer}")
print(f"Confidence: {result.confidence}")
print(f"Sources: {result.sources}")
print(f"Graph Path: {result.reasoning_path}")  # Shows the traversal!
```

### Entity-Aware Queries

```python
# Find all documents mentioning specific entities
docs = await rag.find_by_entity("Sarah Thompson", entity_type="PERSON")

# Find connections between entities
connections = await rag.find_connections("Project X", "Budget Concerns")
print(f"Connected via: {connections}")  # Shows relationship path

# Multi-hop reasoning
result = await rag.graph_query(
    "Who has concerns about projects managed by Sarah?",
    max_hops=3  # Traverse up to 3 relationships
)
```

### Relationship Queries

```python
# What entities are related to a concept?
related = await rag.get_related_entities(
    "Q3 Budget",
    relationship_types=["MENTIONS", "CONCERNS", "APPROVES"]
)

# Build a subgraph around a topic
subgraph = await rag.extract_subgraph(
    center="Project Artemis",
    depth=2  # 2 hops from center
)
```

---

## 🔄 Standard RAG vs GraphRAG Comparison

### Scenario: "What are our compliance requirements for HIPAA?"

**Standard RAG Approach:**
```python
# 1. Embed the query
query_embedding = embed("HIPAA compliance requirements")

# 2. Vector similarity search
similar_chunks = vector_store.search(query_embedding, top_k=5)

# 3. Pass to LLM
context = "\n".join([c.text for c in similar_chunks])
answer = llm(f"Context: {context}\n\nQuestion: {query}")
```

**Result:** Finds chunks that mention "HIPAA" but:
- ❌ Misses related regulations (HITECH, state laws)
- ❌ Doesn't connect to specific implementation guidelines
- ❌ No link to previous audit findings
- ❌ No connection to responsible personnel

**GraphRAG Approach:**
```python
# 1. Parse query for entities
entities = extract_entities("HIPAA compliance requirements")
# → ["HIPAA", "compliance", "requirements"]

# 2. Find entity nodes and relationships
cypher = """
MATCH (req:Requirement)-[:REGULATED_BY]->(reg:Regulation {name: 'HIPAA'})
MATCH (req)-[:IMPLEMENTED_IN]->(proc:Procedure)
MATCH (proc)-[:OWNED_BY]->(person:Person)
MATCH (req)-[:AUDITED_IN]->(audit:Audit)
OPTIONAL MATCH (reg)-[:RELATED_TO]->(other:Regulation)
RETURN req, proc, person, audit, other
"""
graph_context = neo4j.query(cypher)

# 3. Combine with vector search for comprehensive context
vector_chunks = vector_store.search(query_embedding, top_k=5)
combined = merge_contexts(graph_context, vector_chunks)

# 4. LLM with rich context
answer = llm(f"Graph Context: {graph_context}\n"
             f"Document Context: {vector_chunks}\n"
             f"Question: {query}")
```

**Result:**
- ✅ HIPAA requirements with specific sections
- ✅ Related regulations (HITECH Act, state privacy laws)
- ✅ Implementation procedures and guidelines
- ✅ Responsible personnel for each requirement
- ✅ Previous audit findings and remediation status
- ✅ Cross-references between related requirements

---

## 🗄️ Neo4j Knowledge Graph Schema

### Node Types

```cypher
// Document chunks with embeddings
(:Chunk {
  id: "chunk_123",
  content: "The HIPAA Privacy Rule...",
  embedding: [0.1, 0.2, ...],  // 768-dim vector
  source: "compliance_manual.pdf",
  page: 42,
  created_at: datetime()
})

// Extracted entities
(:Entity {
  id: "entity_456",
  name: "HIPAA",
  type: "REGULATION",
  description: "Health Insurance Portability and Accountability Act"
})

(:Entity {
  id: "entity_789",
  name: "Sarah Thompson",
  type: "PERSON",
  role: "Compliance Officer"
})

// Documents
(:Document {
  id: "doc_abc",
  title: "Compliance Manual 2024",
  source: "compliance_manual.pdf",
  type: "PDF",
  created_at: datetime()
})
```

### Relationship Types

```cypher
// Chunk relationships
(chunk1)-[:FOLLOWS]->(chunk2)           // Sequential in document
(chunk)-[:PART_OF]->(document)          // Chunk belongs to document
(chunk)-[:MENTIONS]->(entity)           // Chunk mentions entity
(chunk)-[:DISCUSSES]->(concept)         // Chunk discusses concept

// Entity relationships
(person)-[:WORKS_ON]->(project)
(person)-[:RESPONSIBLE_FOR]->(process)
(regulation)-[:REQUIRES]->(requirement)
(requirement)-[:IMPLEMENTED_IN]->(procedure)
(entity)-[:RELATED_TO]->(entity)

// Semantic relationships
(chunk)-[:SIMILAR_TO {score: 0.85}]->(chunk)  // Semantic similarity
(entity)-[:CO_OCCURS_WITH]->(entity)          // Appear together
```

### Creating the Schema

```cypher
// Create indexes for performance
CREATE INDEX chunk_id IF NOT EXISTS FOR (c:Chunk) ON (c.id);
CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX document_id IF NOT EXISTS FOR (d:Document) ON (d.id);

// Create vector index for semantic search
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}};

// Constraints
CREATE CONSTRAINT chunk_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT entity_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
```

---

## 🔍 Query Strategies

### 1. Hybrid Search (Vector + Graph)

Combines semantic similarity with graph relationships:

```python
result = await rag.hybrid_query(
    query="What did the CEO say about Q3 performance?",
    vector_weight=0.4,    # 40% semantic similarity
    graph_weight=0.6,     # 60% graph relationships
    rerank=True           # LLM reranking
)
```

### 2. Multi-Hop Reasoning

Traverse relationships to find indirect connections:

```python
result = await rag.graph_query(
    query="What projects are affected by Sarah's budget concerns?",
    max_hops=3,
    reasoning_strategy="chain_of_thought"
)

# Shows reasoning path:
# Sarah → RAISED → Budget Concerns → AFFECTS → Project X → DEPENDS_ON → Project Y
```

### 3. Entity-Centric Search

Start from known entities and expand:

```python
result = await rag.entity_query(
    entities=["HIPAA", "PHI"],
    relationship_filter=["REQUIRES", "PROTECTS", "VIOLATES"],
    include_neighbors=True
)
```

### 4. Temporal Queries

Query across time:

```python
result = await rag.temporal_query(
    query="How has our security posture changed since January?",
    time_range=("2024-01-01", "2024-06-30"),
    compare_periods=True
)
```

### 5. Community Detection

Find clusters of related content:

```python
communities = await rag.detect_communities(
    algorithm="louvain",
    min_size=5
)

# Query within a community
result = await rag.query(
    "What are the main topics?",
    community_id=communities[0].id
)
```

---

## 📊 Chunking Strategies

GraphRAG supports multiple chunking strategies:

### Semantic Chunking (Recommended)

Splits on semantic boundaries, not arbitrary character counts:

```python
from agentic_brain.rag import RAGPipeline

rag = RAGPipeline(
    chunk_strategy="semantic",
    chunk_config={
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "threshold": 0.7,  # Semantic similarity threshold
        "min_chunk_size": 100,
        "max_chunk_size": 1000
    }
)
```

### Recursive Chunking

Hierarchical splitting that respects document structure:

```python
rag = RAGPipeline(
    chunk_strategy="recursive",
    chunk_config={
        "separators": ["\n\n", "\n", ". ", " "],
        "chunk_size": 512,
        "chunk_overlap": 50
    }
)
```

### Document-Aware Chunking

Respects document-specific structure:

```python
rag = RAGPipeline(
    chunk_strategy="document_aware",
    chunk_config={
        "pdf": {"by": "page", "overlap_pages": 0},
        "markdown": {"by": "heading", "min_heading": 2},
        "code": {"by": "function", "include_docstrings": True}
    }
)
```

### Sliding Window

Fixed-size chunks with overlap:

```python
rag = RAGPipeline(
    chunk_strategy="sliding_window",
    chunk_config={
        "chunk_size": 256,
        "overlap": 64
    }
)
```

---

## 🎛️ Vector Search Options

### Built-in Neo4j Vector Index (Recommended)

```python
rag = RAGPipeline(
    vector_store="neo4j",  # Uses Neo4j's native vector index
    embedding_model="sentence-transformers/all-mpnet-base-v2",
    embedding_dimensions=768
)
```

### External Vector Stores

```python
# Qdrant
rag = RAGPipeline(
    vector_store="qdrant",
    qdrant_url="http://localhost:6333"
)

# Pinecone
rag = RAGPipeline(
    vector_store="pinecone",
    pinecone_api_key="xxx",
    pinecone_index="knowledge"
)

# Weaviate
rag = RAGPipeline(
    vector_store="weaviate",
    weaviate_url="http://localhost:8080"
)

# ChromaDB (local)
rag = RAGPipeline(
    vector_store="chroma",
    chroma_path="./chroma_db"
)
```

---

## 🏎️ Performance Optimization

### Hardware Acceleration

```python
from agentic_brain.rag import detect_hardware, get_accelerated_embeddings

# Auto-detect best hardware
device, info = detect_hardware()
print(f"Using: {device} ({info})")  # "mlx (Apple M2 Pro)"

# Embeddings are automatically accelerated
embeddings = get_accelerated_embeddings()
```

### Batch Processing

```python
# Ingest in batches for large datasets
await rag.ingest_directory(
    "./large_dataset/",
    batch_size=100,
    parallel_workers=4,
    show_progress=True
)
```

### Caching

```python
rag = RAGPipeline(
    cache_embeddings=True,
    cache_dir="./rag_cache/",
    cache_ttl=86400  # 24 hours
)
```

### Query Optimization

```python
# Pre-warm frequently accessed entities
await rag.warm_cache(entities=["HIPAA", "GDPR", "SOX"])

# Use query hints for faster traversal
result = await rag.query(
    "What are the HIPAA requirements?",
    hints={
        "start_nodes": ["HIPAA"],
        "relationship_types": ["REQUIRES", "SPECIFIES"]
    }
)
```

---

## 📈 Example Queries

### Simple Q&A
```python
result = await rag.query("What is our vacation policy?")
```

### Multi-Document Synthesis
```python
result = await rag.query(
    "Summarize all discussions about the Q3 budget across Teams, Slack, and email",
    sources=["teams", "slack", "email"],
    synthesize=True
)
```

### Comparative Analysis
```python
result = await rag.query(
    "How do our security policies compare to NIST guidelines?",
    compare_mode=True
)
```

### Timeline Construction
```python
result = await rag.query(
    "Create a timeline of the Project X milestones",
    output_format="timeline"
)
```

### Knowledge Graph Exploration
```python
# Get entity relationships
graph = await rag.explore_entity(
    "Project Artemis",
    depth=2,
    include_metrics=True
)

# Visualize (returns D3.js compatible JSON)
viz_data = rag.visualize_subgraph(graph)
```

---

## 🔧 Configuration Reference

```python
from agentic_brain.rag import RAGPipeline

rag = RAGPipeline(
    # Neo4j Connection
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password",
    
    # Embeddings
    embedding_model="sentence-transformers/all-mpnet-base-v2",
    embedding_dimensions=768,
    embedding_device="auto",  # "mlx", "cuda", "mps", "cpu"
    
    # Chunking
    chunk_strategy="semantic",  # "recursive", "sliding_window", "document_aware"
    chunk_size=512,
    chunk_overlap=50,
    
    # Entity Extraction
    extract_entities=True,
    entity_model="en_core_web_lg",  # spaCy model
    entity_types=["PERSON", "ORG", "PRODUCT", "EVENT"],
    
    # Relationship Extraction
    extract_relationships=True,
    relationship_model="rebel-large",  # HuggingFace model
    
    # Search
    search_strategy="hybrid",  # "vector", "graph", "hybrid"
    vector_weight=0.4,
    graph_weight=0.6,
    top_k=10,
    
    # Reranking
    rerank=True,
    rerank_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
    
    # LLM
    llm_provider="ollama",  # "openai", "anthropic", "ollama"
    llm_model="llama3.1",
    
    # Caching
    cache_embeddings=True,
    cache_dir="./rag_cache/"
)
```

---

## 📚 See Also

- [Data Loaders](./DATA_LOADERS.md) — 54 data loaders for ingestion
- [RAG Reference](./RAG.md) — Complete technical reference
- [Neo4j Integration](./integrations/NEO4J.md) — Neo4j setup and optimization
- [Architecture](./architecture.md) — System architecture overview

---

<div align="center">

## 🧠 GraphRAG: Think in Graphs, Not Chunks

**Traditional RAG:** "Find similar text"  
**GraphRAG:** "Understand relationships, traverse connections, reason across documents"

*This is what makes Agentic Brain different.*

</div>
