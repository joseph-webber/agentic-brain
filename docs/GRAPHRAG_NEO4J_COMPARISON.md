# GraphRAG Implementation: neo4j-graphrag Compatibility Audit

**Date**: 2026-01-14  
**Auditor**: Agentic Brain Team  
**Reference**: [neo4j-graphrag on PyPI](https://pypi.org/project/neo4j-graphrag/)  
**Official Docs**: [neo4j.com/docs/neo4j-graphrag-python](https://neo4j.com/docs/neo4j-graphrag-python/current/)

---

## Executive Summary

The Agentic Brain GraphRAG implementation is **well-aligned** with the official neo4j-graphrag library patterns but uses **extended abstractions** for hardware acceleration (MLX/MPS/CUDA) and **additional features** not present in the official library. Users familiar with neo4j-graphrag will find the API intuitive with minor adaptations.

| Category | Compatibility | Notes |
|----------|--------------|-------|
| Driver/Session Management | ⚠️ Partial | Async-first vs sync-first difference |
| GDS Integration (Leiden) | ✅ Excellent | Same GDS calls, plus hierarchical support |
| Embedding Providers | ✅ Excellent | Superset with MLX/MPS acceleration |
| Retriever Patterns | ⚠️ Partial | Different naming, similar functionality |
| Pipeline Construction | ⚠️ Partial | Different class names, similar concepts |

---

## 1. Driver/Session Management Patterns

### neo4j-graphrag Pattern (Official)
```python
from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.generation import GraphRAG

# Sync driver, passed explicitly to components
driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("neo4j", "password"))
retriever = VectorRetriever(driver, "index-name", embedder)
rag = GraphRAG(retriever=retriever, llm=llm)
```

### Agentic Brain Pattern (Current)
```python
from neo4j import AsyncGraphDatabase
from agentic_brain.rag.graph_rag import GraphRAG, GraphRAGConfig

# Async driver, internal creation via config
config = GraphRAGConfig(neo4j_uri="bolt://localhost:7687")
rag = GraphRAG(config)
await rag.search(query, strategy=SearchStrategy.HYBRID)
await rag.close()
```

### Assessment

| Aspect | neo4j-graphrag | Agentic Brain | Verdict |
|--------|---------------|---------------|---------|
| Driver Type | Sync (primary) | Async (primary) | **Divergent** - intentional for performance |
| Driver Ownership | External (passed in) | Internal (created) | **Divergent** - config-driven |
| Connection Pooling | Manual | Via `neo4j_pool` module | **Extended** - shared pool |
| Session Management | `with driver.session()` | `async with driver.session()` | **Divergent** - async pattern |

### Recommendation
✅ **Keep**: Async-first is correct for modern Python applications.  
⚠️ **Add**: Optional sync wrappers for neo4j-graphrag compatibility:

```python
class GraphRAGSync:
    """Sync wrapper for users migrating from neo4j-graphrag."""
    
    def __init__(self, driver, retriever, llm):
        """Accept external driver like neo4j-graphrag."""
        self._driver = driver
        self._retriever = retriever
        self._llm = llm
    
    def search(self, query_text: str, retriever_config: dict = None):
        """Match neo4j-graphrag's GraphRAG.search() signature."""
        return asyncio.run(self._async_search(query_text, retriever_config))
```

---

## 2. GDS (Graph Data Science) Integration

### neo4j-graphrag Pattern (Official)
```python
# GDS used via direct Cypher calls
# Community detection typically via SimpleKGPipeline
CALL gds.graph.project('entity', 'Entity', '*')
CALL gds.leiden.stream('entity') YIELD nodeId, communityId
```

### Agentic Brain Pattern (Current)
```python
# community_detection.py - Lines 120-207
def _detect_leiden_hierarchical(session, *, gamma=1.0, max_levels=3):
    """Hierarchical Leiden with multiple resolutions."""
    session.run("""
        CALL gds.graph.project($name, 'Entity',
            {RELATES_TO: {orientation: 'UNDIRECTED'}})
    """, name=GRAPH_PROJECT_NAME)
    
    # Multi-resolution for hierarchy
    resolutions = [gamma * (2.0 ** i) for i in range(max_levels)]
    for level, resolution in enumerate(resolutions):
        session.run("""
            CALL gds.leiden.stream($name, {gamma: $gamma})
            YIELD nodeId, communityId
            RETURN gds.util.asNode(nodeId).name AS entity, communityId
        """, ...)
```

### Assessment

| Aspect | neo4j-graphrag | Agentic Brain | Verdict |
|--------|---------------|---------------|---------|
| Leiden Support | ✅ via GDS | ✅ via GDS | **Compatible** |
| Louvain Fallback | Not documented | ✅ `_detect_louvain()` | **Extended** |
| Pure-Cypher Fallback | ❌ | ✅ `_detect_connected_components()` | **Extended** |
| Hierarchical Communities | ❌ | ✅ Multi-level hierarchy | **Extended** |
| Graph Projection | Same pattern | Same pattern | **Compatible** |
| Entity Resolution | ✅ | ✅ `resolve_entities()` | **Compatible** |

### Recommendation
✅ **Keep all extensions** - Agentic Brain's community detection is a superset.  
✅ **Document** the GDS version requirements (2.x+ for Leiden).

---

## 3. Embedding Provider Abstraction

### neo4j-graphrag Pattern (Official)
```python
from neo4j_graphrag.embeddings import OpenAIEmbeddings, SentenceTransformerEmbeddings

# Base interface
class Embedder:
    def embed_query(text: str) -> list[float]: ...
    async def async_embed_query(text: str) -> list[float]: ...

# Usage
embedder = OpenAIEmbeddings(model="text-embedding-3-large")
vector = embedder.embed_query("What is GraphRAG?")
```

### Agentic Brain Pattern (Current)
```python
from agentic_brain.rag.embeddings import (
    EmbeddingProvider, OpenAIEmbeddings, 
    SentenceTransformerEmbeddings, OllamaEmbeddings
)

# Base interface
class EmbeddingProvider(ABC):
    def embed(text: str) -> list[float]: ...
    def embed_batch(texts: list[str]) -> list[list[float]]: ...
    @property
    def dimensions(self) -> int: ...

# Usage with hardware detection
embedder = SentenceTransformerEmbeddings(device="mps")  # Apple Silicon
vector = embedder.embed("What is GraphRAG?")
```

### Assessment

| Aspect | neo4j-graphrag | Agentic Brain | Verdict |
|--------|---------------|---------------|---------|
| Method Name | `embed_query()` | `embed()` | **Divergent** - minor |
| Batch Support | Not documented | ✅ `embed_batch()` | **Extended** |
| Async Support | ✅ `async_embed_query()` | ❌ Missing | **Gap** |
| Hardware Detection | ❌ | ✅ MLX/MPS/CUDA/ROCm | **Extended** |
| Ollama Support | ✅ (extras) | ✅ Native | **Compatible** |
| OpenAI Support | ✅ | ✅ | **Compatible** |
| Sentence Transformers | ✅ | ✅ + device control | **Extended** |
| Dimensions Property | ❌ | ✅ | **Extended** |

### Recommendation
⚠️ **Add method alias** for compatibility:

```python
class EmbeddingProvider(ABC):
    def embed(self, text: str) -> list[float]: ...
    
    def embed_query(self, text: str) -> list[float]:
        """neo4j-graphrag compatible alias."""
        return self.embed(text)
    
    async def async_embed_query(self, text: str) -> list[float]:
        """neo4j-graphrag async interface."""
        return self.embed(text)  # Add true async if needed
```

---

## 4. Retriever Patterns

### neo4j-graphrag Pattern (Official)
```python
from neo4j_graphrag.retrievers import (
    VectorRetriever,      # Vector similarity search
    HybridRetriever,      # Vector + fulltext
    Text2CypherRetriever, # Natural language → Cypher
)

# Constructor signature
retriever = VectorRetriever(
    driver,              # Neo4j driver
    "index-name",        # Vector index name
    embedder,            # Embedding provider
    return_properties=["content", "title"]  # Optional
)

# Search signature
results = retriever.search(query_text="...", top_k=5)
```

### Agentic Brain Pattern (Current)
```python
from agentic_brain.rag.retriever import Retriever, RetrievedChunk
from agentic_brain.rag.hybrid import HybridSearch, reciprocal_rank_fusion
from agentic_brain.rag.graph_rag import GraphRAG, SearchStrategy

# Constructor signature
retriever = Retriever(
    neo4j_uri="bolt://localhost:7687",  # URI not driver
    neo4j_user="neo4j",
    embedding_provider=embedder,
    sources=["Document", "Memory"]
)

# Search signatures
chunks = retriever.search(query, k=5)  # Different param name
chunks = retriever.search_neo4j(query, k=5, labels=["Document"])
```

### Assessment

| Aspect | neo4j-graphrag | Agentic Brain | Verdict |
|--------|---------------|---------------|---------|
| Class Names | `VectorRetriever`, `HybridRetriever` | `Retriever`, `HybridSearch` | **Divergent** |
| Constructor | Driver object | URI + credentials | **Divergent** |
| Search Param | `top_k` | `k` | **Divergent** - minor |
| Vector Index | Named index required | Fallback to manual | **Extended** |
| RRF Fusion | ✅ Hybrid alpha param | ✅ `reciprocal_rank_fusion()` | **Compatible concept** |
| Text2Cypher | ✅ | ❌ Not implemented | **Gap** |
| Result Type | RetrieverResult | RetrievedChunk | **Similar structure** |

### Recommendation
⚠️ **Add compatibility wrappers**:

```python
class VectorRetriever:
    """neo4j-graphrag compatible vector retriever."""
    
    def __init__(self, driver, index_name: str, embedder, return_properties=None):
        self._driver = driver
        self._index_name = index_name
        self._embedder = embedder
        self._return_properties = return_properties
    
    def search(self, query_text: str, top_k: int = 5):
        """neo4j-graphrag compatible search interface."""
        # Map to internal retriever
        ...

class HybridRetriever:
    """neo4j-graphrag compatible hybrid retriever."""
    
    def __init__(self, driver, vector_index_name, fulltext_index_name, embedder, alpha=0.5):
        ...
```

⚠️ **Consider implementing** `Text2CypherRetriever` for parity.

---

## 5. Pipeline Construction

### neo4j-graphrag Pattern (Official)
```python
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.llm import OpenAILLM

# Main orchestration class
llm = OpenAILLM(model_name="gpt-4", model_params={"temperature": 0})
rag = GraphRAG(retriever=retriever, llm=llm)

# Primary method
response = rag.search(
    query_text="How do I do similarity search?",
    retriever_config={"top_k": 5}
)
print(response.answer)
```

### Agentic Brain Pattern (Current)
```python
from agentic_brain.rag.graph_rag import GraphRAG, GraphRAGConfig, SearchStrategy
from agentic_brain.rag.pipeline import RAGPipeline, RAGResult

# Config-based construction
config = GraphRAGConfig(
    neo4j_uri="bolt://localhost:7687",
    embedding_model="all-MiniLM-L6-v2",
    enable_communities=True
)
rag = GraphRAG(config)

# Search with strategy enum
results = await rag.search(
    query="How do I do similarity search?",
    strategy=SearchStrategy.HYBRID,
    top_k=5
)

# Full pipeline
pipeline = RAGPipeline(retriever=retriever, llm_provider="claude")
result: RAGResult = await pipeline.query("...")
print(result.answer)
```

### Assessment

| Aspect | neo4j-graphrag | Agentic Brain | Verdict |
|--------|---------------|---------------|---------|
| Main Class | `GraphRAG` | `GraphRAG` + `RAGPipeline` | **Extended** |
| Configuration | Constructor args | `GraphRAGConfig` dataclass | **Extended** |
| LLM Interface | `OpenAILLM` class | Provider string | **Divergent** |
| Search Method | `search(query_text=)` | `search(query=)` | **Divergent** - minor |
| Result Type | `response.answer` | `RAGResult.answer` | **Similar** |
| Retriever Config | `retriever_config={}` | `strategy=`, `top_k=` | **Divergent** |
| Community Search | Not built-in | ✅ `SearchStrategy.COMMUNITY` | **Extended** |

### Recommendation
⚠️ **Add compatibility layer**:

```python
from neo4j_graphrag.generation import GraphRAG as Neo4jGraphRAG  # If installed

class GraphRAG:
    """Extended GraphRAG with neo4j-graphrag compatible interface."""
    
    def __init__(self, retriever=None, llm=None, config=None):
        if config:
            # Agentic Brain mode
            self._init_from_config(config)
        else:
            # neo4j-graphrag compatible mode
            self._retriever = retriever
            self._llm = llm
    
    def search(self, query_text: str = None, query: str = None, 
               retriever_config: dict = None, **kwargs):
        """Accept both API styles."""
        q = query_text or query
        top_k = retriever_config.get("top_k", 10) if retriever_config else kwargs.get("top_k", 10)
        ...
```

---

## 6. Patterns to Adopt from neo4j-graphrag

### 6.1 Explicit Driver Injection (High Priority)
The neo4j-graphrag pattern of accepting an external driver allows better:
- Testing with mock drivers
- Connection sharing across components
- User control over connection lifecycle

```python
# Current: Internal driver creation
rag = GraphRAG(config)

# Adopt: Accept external driver option
rag = GraphRAG(driver=my_driver, config=config)  # Both options
```

### 6.2 RagTemplate for Prompt Control (Medium Priority)
neo4j-graphrag allows custom prompt templates:

```python
from neo4j_graphrag.generation.prompts import RagTemplate

custom_template = RagTemplate(
    template="Answer based on: {context}\n\nQuestion: {query}"
)
rag = GraphRAG(retriever=retriever, llm=llm, prompt_template=custom_template)
```

**Recommendation**: Add `prompt_template` parameter to `RAGPipeline`.

### 6.3 Async Method Naming (Low Priority)
neo4j-graphrag uses `async_` prefix for async methods:

```python
# neo4j-graphrag
await embedder.async_embed_query(text)

# Agentic Brain uses native async
async def embed(self, text): ...
```

**Recommendation**: Keep current pattern but document difference.

---

## 7. Where We Intentionally Diverge

### 7.1 Hardware Acceleration (Keep)
neo4j-graphrag doesn't provide hardware detection or MLX support.  
**Reason**: Core differentiator for Apple Silicon performance.

### 7.2 Async-First Design (Keep)
neo4j-graphrag is sync-first with async options.  
**Reason**: Modern Python applications benefit from async I/O.

### 7.3 Config Dataclasses (Keep)
neo4j-graphrag uses constructor arguments.  
**Reason**: Better IDE support, validation, and serialization.

### 7.4 Multi-Strategy Search (Keep)
neo4j-graphrag has separate retriever classes.  
**Reason**: `SearchStrategy` enum is more discoverable.

### 7.5 Community Hierarchy (Keep)
neo4j-graphrag uses flat communities.  
**Reason**: Hierarchical communities enable better global search.

---

## 8. Migration Path Recommendations

### For Users Coming from neo4j-graphrag

#### Quick Migration
```python
# neo4j-graphrag
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.generation import GraphRAG

driver = GraphDatabase.driver(...)
embedder = OpenAIEmbeddings()
retriever = VectorRetriever(driver, "index", embedder)
rag = GraphRAG(retriever=retriever, llm=llm)
response = rag.search(query_text="...", retriever_config={"top_k": 5})

# Agentic Brain equivalent
from agentic_brain.rag import Retriever, RAGPipeline

retriever = Retriever(neo4j_uri="...", embedding_provider=embedder)
pipeline = RAGPipeline(retriever=retriever, llm_provider="openai")
response = await pipeline.query("...", k=5)
```

#### Using Both Libraries
```python
# Agentic Brain components with neo4j-graphrag pipeline
from neo4j_graphrag.generation import GraphRAG
from agentic_brain.rag.embeddings import SentenceTransformerEmbeddings

# Use Agentic Brain's hardware-accelerated embeddings
embedder = SentenceTransformerEmbeddings(device="mps")

# Use neo4j-graphrag's pipeline
retriever = VectorRetriever(driver, "index", embedder)  # Works!
rag = GraphRAG(retriever=retriever, llm=llm)
```

---

## 9. Compatibility Matrix

| Feature | neo4j-graphrag | Agentic Brain | Interoperable |
|---------|---------------|---------------|---------------|
| OpenAI Embeddings | ✅ | ✅ | ✅ Yes |
| Sentence Transformers | ✅ | ✅ | ✅ Yes |
| Ollama Embeddings | ✅ | ✅ | ✅ Yes |
| MLX Embeddings | ❌ | ✅ | N/A |
| Vector Search | ✅ | ✅ | ⚠️ Different APIs |
| Hybrid Search | ✅ | ✅ | ⚠️ Different APIs |
| Text2Cypher | ✅ | ❌ | ❌ Gap |
| Leiden Communities | ✅ | ✅ | ✅ Yes |
| Hierarchical Communities | ❌ | ✅ | N/A |
| GDS Integration | ✅ | ✅ | ✅ Yes |
| Sync Driver | ✅ Primary | ⚠️ Secondary | ⚠️ Adapter needed |
| Async Driver | ⚠️ Secondary | ✅ Primary | ✅ Yes |

---

## 10. Action Items

### High Priority
1. [ ] Add `VectorRetriever` compatibility wrapper
2. [ ] Add `embed_query()` alias to `EmbeddingProvider`
3. [ ] Support external driver injection in `GraphRAG`
4. [ ] Document migration guide in README

### Medium Priority
5. [ ] Implement `Text2CypherRetriever` equivalent
6. [ ] Add `HybridRetriever` compatibility wrapper
7. [ ] Add `RagTemplate` prompt customization
8. [ ] Create interoperability tests

### Low Priority
9. [ ] Add sync wrappers for async components
10. [ ] Harmonize parameter names (`k` vs `top_k`)
11. [ ] Create example notebooks showing both APIs

---

## Appendix: API Mapping Reference

| neo4j-graphrag | Agentic Brain | Notes |
|----------------|---------------|-------|
| `GraphRAG` | `GraphRAG` / `RAGPipeline` | Similar concepts |
| `VectorRetriever` | `Retriever.search_neo4j()` | Method vs class |
| `HybridRetriever` | `HybridSearch` | Different interface |
| `Text2CypherRetriever` | ❌ Not implemented | Gap |
| `OpenAIEmbeddings` | `OpenAIEmbeddings` | Same name, similar API |
| `SentenceTransformerEmbeddings` | `SentenceTransformerEmbeddings` | Extended with device |
| `embed_query()` | `embed()` | Different method name |
| `top_k` | `k` | Different param name |
| `retriever_config` | Strategy enum + kwargs | Different approach |
| `SimpleKGPipeline` | `KnowledgeExtractor` | Different scope |

---

*Report generated for agentic-brain GraphRAG audit. Last updated: 2026-01-14.*
