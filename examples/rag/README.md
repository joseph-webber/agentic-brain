# 📚 RAG Examples

> Retrieval-Augmented Generation - documents, code, research, and more.

## Examples

| # | Example | Description | Level |
|---|---------|-------------|-------|
| 37 | [rag_documents.py](37_rag_documents.py) | General document Q&A | 🟡 Intermediate |
| 38 | [rag_codebase.py](38_rag_codebase.py) | Code understanding | 🟡 Intermediate |
| 39 | [rag_research.py](39_rag_research.py) | Research paper analysis | 🔴 Advanced |
| 40 | [rag_catalog.py](40_rag_catalog.py) | Product catalog search | 🟡 Intermediate |
| 41 | [rag_contracts.py](41_rag_contracts.py) | Contract analysis | 🔴 Advanced |
| 42 | [rag_medical.py](42_rag_medical.py) | Medical knowledge base | 🔴 Advanced |

## Quick Start

```bash
# Document Q&A
python examples/rag/37_rag_documents.py

# Codebase understanding
python examples/rag/38_rag_codebase.py

# Research papers
python examples/rag/39_rag_research.py
```

## What is RAG?

**Retrieval-Augmented Generation** combines:
1. **Retrieval**: Find relevant documents/chunks
2. **Augmentation**: Add context to the prompt
3. **Generation**: LLM generates informed response

```
User Question → Search Documents → Add Context → LLM → Answer
```

## Use Cases

### Document Q&A
- Company policies
- Technical documentation
- User manuals
- FAQ databases

### Codebase Understanding
- Code search and explanation
- API documentation
- Architecture understanding
- Bug investigation

### Research Analysis
- Paper summarization
- Citation finding
- Trend analysis
- Literature review

### Product Catalog
- Product search
- Comparison queries
- Recommendation
- Specification lookup

### Contract Analysis
- Clause extraction
- Risk identification
- Obligation tracking
- Compliance checking

### Medical Knowledge
- Clinical guidelines
- Drug interactions
- Symptom analysis
- Treatment protocols

## Common Patterns

### Basic RAG Setup
```python
from agentic_brain import Agent

agent = Agent(
    name="doc_assistant",
    rag_source="./documents/",  # Load from directory
    embedding_model="nomic-embed-text",
    chunk_size=500
)

answer = agent.chat("What is the refund policy?")
```

### Code RAG
```python
agent = Agent(
    name="code_assistant",
    rag_source="./src/",
    file_types=[".py", ".js", ".ts"],
    system_prompt="Explain code and answer questions about the codebase."
)

explanation = agent.chat("How does the authentication work?")
```

### Multi-Source RAG
```python
from agentic_brain import RAGStore

store = RAGStore()
store.add_documents("./policies/")
store.add_documents("./procedures/")
store.add_documents("./faqs/")

agent = Agent(rag_store=store)
```

### Hybrid Search
```python
# Combine keyword + semantic search
agent = Agent(
    rag_source="./docs/",
    search_type="hybrid",  # keyword + semantic
    rerank=True  # Re-rank results for relevance
)
```

## RAG Architecture

```
┌─────────────────────────────────────────┐
│              RAG Pipeline               │
├─────────────────────────────────────────┤
│  1. Document Ingestion                  │
│     └─ Load → Chunk → Embed → Store     │
├─────────────────────────────────────────┤
│  2. Query Processing                    │
│     └─ Question → Embed → Search        │
├─────────────────────────────────────────┤
│  3. Context Retrieval                   │
│     └─ Top-K chunks → Rerank → Filter   │
├─────────────────────────────────────────┤
│  4. Response Generation                 │
│     └─ Context + Question → LLM → Answer│
└─────────────────────────────────────────┘
```

## Prerequisites

- Python 3.10+
- Ollama with embedding model: `ollama pull nomic-embed-text`
- Vector store (Neo4j, ChromaDB, or in-memory)
