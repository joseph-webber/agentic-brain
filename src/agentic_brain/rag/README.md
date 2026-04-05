# RAG (Retrieval-Augmented Generation)

Advanced document retrieval and question answering system with production-ready features.

## Components

- **pipeline.py** - Complete RAG pipeline with caching and source attribution
- **retriever.py** - Vector search against Neo4j with confidence scores
- **embeddings.py** - Embedding providers (Ollama, OpenAI) with caching
- **chunking.py** - Text chunking strategies (Fixed, Semantic, Recursive, Markdown)
- **reranking.py** - Result reranking (Cross-encoder, MMR, Diversity)
- **hybrid.py** - Hybrid vector + BM25 keyword search
- **evaluation.py** - RAG quality metrics (Precision, Recall, MRR, NDCG)
- **langchain_compat.py** - LangChain compatibility layer for LCEL chains
- **llamaindex_compat.py** - LlamaIndex compatibility layer for migration

## Key Features

- Multi-source retrieval (Neo4j, files, APIs)
- Semantic search with embeddings and caching
- Advanced chunking for optimal context
- Reranking for precision and diversity
- Hybrid search combining vector + keyword matching
- A/B testing and evaluation framework
- Source citation with confidence scores
- **LangChain integration** - Use as retriever in LCEL chains
- **LlamaIndex compatibility** - Migrate from LlamaIndex with minimal changes

## Quick Start

```python
from agentic_brain.rag import RAGPipeline, ask

# Simple interface
answer = ask("What is the status of project X?")
print(answer)

# Full pipeline with Neo4j
rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
result = rag.query("How do I deploy?")
print(result.answer)
print(result.sources)  # With confidence scores

# Advanced chunking
from agentic_brain.rag import create_chunker, ChunkingStrategy
chunker = create_chunker(ChunkingStrategy.MARKDOWN)
chunks = chunker.chunk(text)

# Reranking results
from agentic_brain.rag import MMRReranker
reranker = MMRReranker()
reranked = reranker.rerank("query text", chunks)
```

---

## LlamaIndex Migration Guide

Agentic Brain provides a LlamaIndex-compatible API layer for seamless migration. Users familiar with LlamaIndex can use their existing patterns with minimal code changes.

### Installation

No additional dependencies required - the compatibility layer is built-in.

### Basic Migration

**Before (LlamaIndex):**
```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

# Load documents
documents = SimpleDirectoryReader("./data").load_data()

# Create index
index = VectorStoreIndex.from_documents(documents)

# Query
query_engine = index.as_query_engine()
response = query_engine.query("What is the main topic?")
print(response)
```

**After (Agentic Brain):**
```python
from agentic_brain.rag.llamaindex_compat import (
    AgenticIndex,
    SimpleDirectoryReader,
)

# Load documents (same API)
documents = SimpleDirectoryReader("./data").load_data()

# Create index (same API)
index = AgenticIndex.from_documents(documents)

# Query (same API)
query_engine = index.as_query_engine()
response = query_engine.query("What is the main topic?")
print(response)
```

### API Mapping

| LlamaIndex | Agentic Brain |
|------------|---------------|
| `VectorStoreIndex` | `AgenticIndex` |
| `KnowledgeGraphIndex` | `GraphRAGIndex` |
| `QueryEngine` | `AgenticQueryEngine` |
| `BaseRetriever` | `AgenticRetriever` |
| `SimpleDirectoryReader` | `SimpleDirectoryReader` |
| `TextNode` | `TextNode` |
| `NodeWithScore` | `NodeWithScore` |
| `Response` | `Response` |
| `Settings` | `Settings` |

### GraphRAG Features

Agentic Brain's compatibility layer includes GraphRAG features not available in standard LlamaIndex:

```python
from agentic_brain.rag.llamaindex_compat import (
    GraphRAGIndex,
    GraphRAGQueryEngine,
    LlamaIndexGraphRAGRetriever,
    SearchStrategy,
    GraphRAGConfig,
)

# Create a knowledge graph index with community detection
config = GraphRAGConfig(
    neo4j_uri="bolt://localhost:7687",
    enable_communities=True,
)

# Index documents with entity/relationship extraction
index = GraphRAGIndex.from_documents(
    documents,
    neo4j_uri="bolt://localhost:7687",
    enable_communities=True,
)

# Query with different strategies
query_engine = index.as_query_engine(strategy=SearchStrategy.COMMUNITY)
response = query_engine.query("What are the main themes?")

# Or use the GraphRAG retriever directly
retriever = LlamaIndexGraphRAGRetriever(
    config=config,
    strategy=SearchStrategy.HYBRID,
    similarity_top_k=10,
)
nodes = retriever.retrieve("Explain the architecture")
```

### Search Strategies

- `SearchStrategy.VECTOR` - Pure embedding similarity search
- `SearchStrategy.GRAPH` - Graph traversal using relationships
- `SearchStrategy.HYBRID` - Combined vector + graph search (default)
- `SearchStrategy.COMMUNITY` - Community-based global search
- `SearchStrategy.MULTI_HOP` - Multi-hop reasoning chains

### Response Modes

```python
from agentic_brain.rag.llamaindex_compat import (
    AgenticSynthesizer,
    ResponseMode,
)

# Different response synthesis modes
synthesizer = AgenticSynthesizer(
    response_mode=ResponseMode.COMPACT,  # Default - concise answers
    # ResponseMode.REFINE - Iteratively refine answer
    # ResponseMode.SIMPLE_SUMMARIZE - Simple summary
    # ResponseMode.TREE_SUMMARIZE - Hierarchical summary
    # ResponseMode.ACCUMULATE - Accumulate all responses
)
```

### Custom Components

```python
from agentic_brain.rag.llamaindex_compat import (
    AgenticQueryEngine,
    AgenticRetriever,
    AgenticSynthesizer,
)

# Create custom retriever
retriever = AgenticRetriever(
    neo4j_uri="bolt://localhost:7687",
    similarity_top_k=10,
    sources=["Document", "Knowledge"],
)

# Create custom synthesizer
synthesizer = AgenticSynthesizer(
    response_mode=ResponseMode.REFINE,
    llm_model="gpt-4",
)

# Combine into query engine
engine = AgenticQueryEngine(
    retriever=retriever,
    synthesizer=synthesizer,
)

response = engine.query("Your question here")
```

### Settings Configuration

```python
from agentic_brain.rag.llamaindex_compat import Settings

# Configure global settings
Settings.set_llm("gpt-4")
Settings.set_embed_model("text-embedding-3-small")
Settings.set_chunk_size(1024)
Settings.set_chunk_overlap(100)
```

### Async Support

```python
import asyncio
from agentic_brain.rag.llamaindex_compat import AgenticQueryEngine

async def main():
    engine = AgenticQueryEngine()
    response = await engine.aquery("What is GraphRAG?")
    return response

response = asyncio.run(main())
```

### Key Differences from LlamaIndex

1. **Built-in GraphRAG** - Knowledge graph support out of the box
2. **Hardware Acceleration** - MLX (Apple Silicon), CUDA, ROCm embeddings
3. **Community Detection** - Hierarchical community-aware retrieval
4. **Neo4j Integration** - Native Neo4j graph database support
5. **No External Dependencies** - Works without installing llama-index

---

## LangChain Integration

Agentic Brain GraphRAG integrates seamlessly with LangChain pipelines.

### Installation

```bash
pip install langchain-core  # Required for LangChain features
```

### Basic Usage

```python
from agentic_brain.rag import AgenticBrainRetriever

# Create a LangChain-compatible retriever
retriever = AgenticBrainRetriever(k=5, min_score=0.3)

# Use like any LangChain retriever
docs = retriever.invoke("What is GraphRAG?")
for doc in docs:
    print(f"[{doc.metadata['score']:.2f}] {doc.page_content[:100]}...")
```

### LCEL Chain Integration

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from agentic_brain.rag import AgenticBrainRetriever

# Create retriever
retriever = AgenticBrainRetriever(k=5)

# Create prompt
prompt = ChatPromptTemplate.from_template("""
Answer based on the following context:

{context}

Question: {question}
""")

# Format documents for context
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Build LCEL chain
llm = ChatOpenAI(model="gpt-4")
chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# Use the chain
answer = chain.invoke("How do I configure GraphRAG?")
print(answer)
```

### Available Retrievers

```python
from agentic_brain.rag import (
    AgenticBrainRetriever,   # Basic retriever
    GraphRAGRetriever,       # GraphRAG with community detection
    DocumentStoreRetriever,  # Local document store
    create_langchain_retriever,  # Factory function
)

# Basic retriever (Neo4j vector search)
basic = AgenticBrainRetriever(k=5, min_score=0.3)

# GraphRAG with community-aware retrieval
graphrag = GraphRAGRetriever(
    search_strategy="hybrid",  # vector, graph, hybrid, community
    k=10,
    include_communities=True
)

# Document store retriever (local files)
from agentic_brain.rag import InMemoryDocumentStore
store = InMemoryDocumentStore()
store.add("Your document content here...")
store_retriever = DocumentStoreRetriever(store=store)

# Factory function
retriever = create_langchain_retriever("graphrag", search_strategy="community")
```

### Callback Support

```python
from langchain_core.callbacks import StdOutCallbackHandler
from agentic_brain.rag import AgenticBrainRetriever

# Use with LangChain callbacks
retriever = AgenticBrainRetriever(k=5)
docs = retriever.invoke(
    "query",
    config={"callbacks": [StdOutCallbackHandler()]}
)
```

### Document Conversion

```python
from agentic_brain.rag import (
    retrieved_chunk_to_langchain_document,
    agentic_document_to_langchain_document,
    langchain_document_to_agentic_document,
)

# Convert Agentic Brain documents to LangChain format
from agentic_brain.rag import Document
agentic_doc = Document(id="1", content="Hello world")
lc_doc = agentic_document_to_langchain_document(agentic_doc)

# Convert LangChain documents to Agentic Brain format
from langchain_core.documents import Document as LCDocument
lc_doc = LCDocument(page_content="Hello", metadata={"id": "doc1"})
agentic_doc = langchain_document_to_agentic_document(lc_doc)
```

### Async Support

```python
import asyncio
from agentic_brain.rag import AgenticBrainRetriever

async def main():
    retriever = AgenticBrainRetriever(k=5)
    docs = await retriever.ainvoke("async query")
    return docs

docs = asyncio.run(main())
```

## Configuration

```python
rag = RAGPipeline(
    neo4j_uri="bolt://localhost:7687",
    embedding_model="all-MiniLM-L6-v2",
    cache_enabled=True,
    top_k=10
)
```

## See Also

- [Chat Integration](../chat/README.md) - Use RAG with chatbot
- [Hooks System](../hooks/README.md) - Hook into RAG lifecycle events
- [API Reference](../../../docs/api/rag.md)
- [Tutorial: RAG Chatbot](../../../docs/tutorials/03-rag-chatbot.md)
