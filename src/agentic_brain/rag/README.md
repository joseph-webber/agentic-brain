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

## Key Features

- Multi-source retrieval (Neo4j, files, APIs)
- Semantic search with embeddings and caching
- Advanced chunking for optimal context
- Reranking for precision and diversity
- Hybrid search combining vector + keyword matching
- A/B testing and evaluation framework
- Source citation with confidence scores

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
