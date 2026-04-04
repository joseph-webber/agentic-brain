# Dependencies Guide

**Last Updated:** 2026-03-26  
**Project:** agentic-brain v3.1.0

## Overview

This document lists all dependencies used in the agentic-brain project, organized by category with explanations of why each is needed.

---

## Core Dependencies (Always Installed)

These dependencies are installed with the base package.

| Package | Version | Purpose |
|---------|---------|---------|
| `aiohttp` | >=3.9.0,<4.0.0 | Async HTTP client for LLM API calls (Ollama, OpenRouter, OpenAI) |
| `questionary` | >=2.0.0,<3.0.0 | Interactive CLI prompts for `new-config` wizard |
| `pyttsx3` | >=2.90 | Cross-platform text-to-speech (Windows/Linux fallback) |
| `gTTS` | >=2.5.0 | Google Text-to-Speech (free cloud TTS fallback) |
| `typer` | >=0.9.0,<0.10.0 | CLI framework (pinned for Python 3.14 compatibility) |
| `click` | >=8.0.0 | CLI utilities (typer dependency) |
| `numpy` | >=1.24.0,<3.0.0 | Core numerical computations (embeddings, vector operations) |

**Why numpy is core:** Used throughout the codebase for:
- Vector embeddings and similarity calculations
- RAG (Retrieval-Augmented Generation) operations
- Numerical transformations
- Array operations in ADL (Agent Definition Language)

---

## Test Dependencies

All test dependencies are correctly specified in both `[dev]` and `[test]` optional groups.

### Core Test Framework

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=8.0.0,<9.0.0 | Test framework |
| `pytest-cov` | >=4.1.0,<5.0.0 | Code coverage reporting |
| `pytest-asyncio` | >=0.23.0,<1.0.0 | Async test support |
| `pytest-timeout` | >=2.1.0,<3.0.0 | Prevent hanging tests |
| `pytest-xdist` | >=3.5.0,<4.0.0 | Parallel test execution |

### Required by Test Files

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | >=0.104.0,<1.0.0 | API framework (for API tests) |
| `httpx` | >=0.25.0,<1.0.0 | Async HTTP (for TestClient) |
| `neo4j` | >=5.14.0,<6.0.0 | Neo4j driver (for pool tests) |
| `redis` | >=5.0.0,<6.0.0 | Redis client (imported directly in tests) |
| `sqlalchemy` | >=2.0.0,<3.0.0 | SQL toolkit (for database loader tests) |
| `PyJWT` | >=2.8.0,<3.0.0 | JWT library (imported by auth tests) |
| `requests` | >=2.28.0,<3.0.0 | HTTP client (imported in RAG/LLM tests) |
| `PyYAML` | >=6.0.0,<7.0.0 | YAML parser (imported in loader/governance tests) |
| `docker` | >=7.0.0,<8.0.0 | Docker SDK (for infrastructure tests) |
| `numpy` | >=1.24.0,<3.0.0 | RAG/ADL tests |

### Test Mocking Libraries

| Package | Version | Purpose |
|---------|---------|---------|
| `fakeredis` | >=2.19.0,<3.0.0 | Redis mock for tests |
| `mongomock` | >=4.1.0,<5.0.0 | MongoDB mock for tests |
| `responses` | >=0.25.0,<1.0.0 | HTTP request mocking |

---

## Optional Feature Dependencies

### Memory & Persistence

```bash
pip install agentic-brain[memory]
```

| Package | Version | Purpose |
|---------|---------|---------|
| `neo4j` | >=5.14.0,<6.0.0 | Graph database for knowledge graphs, GraphRAG |

---

### API & Web Server

```bash
pip install agentic-brain[api]
```

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | >=0.104.0,<1.0.0 | High-performance async web framework |
| `uvicorn[standard]` | >=0.24.0,<1.0.0 | ASGI server for FastAPI |
| `pydantic` | >=2.0.0,<3.0.0 | Data validation and settings management |
| `pydantic-settings` | >=2.0.0,<3.0.0 | Environment-based configuration profiles |
| `python-multipart` | >=0.0.6,<1.0.0 | Multipart form parsing for file uploads |
| `websockets` | >=12.0.0,<14.0.0 | WebSocket support for real-time connections |

---

### LLM Integrations

```bash
pip install agentic-brain[llm]
```

| Package | Version | Purpose |
|---------|---------|---------|
| `openai` | >=1.0.0,<2.0.0 | OpenAI API client (GPT-4, GPT-3.5) |
| `httpx` | >=0.25.0,<1.0.0 | Modern async HTTP client |
| `requests` | >=2.28.0,<3.0.0 | Sync HTTP client for fallback LLM APIs |

---

### Vector Databases

```bash
pip install agentic-brain[vectordb]
```

| Package | Version | Purpose |
|---------|---------|---------|
| `pinecone` | >=3.0.0,<4.0.0 | Pinecone vector database client |
| `weaviate-client` | >=4.0.0,<5.0.0 | Weaviate vector database client |
| `qdrant-client` | >=1.7.0,<2.0.0 | Qdrant vector database client |
| `numpy` | >=1.24.0,<3.0.0 | Vector operations |

---

### Embeddings (Local)

```bash
pip install agentic-brain[embeddings]
```

| Package | Version | Purpose |
|---------|---------|---------|
| `sentence-transformers` | >=2.2.0,<3.0.0 | Local embedding models (BERT, MPNet) |
| `torch` | >=2.0.0,<3.0.0 | PyTorch deep learning framework |
| `numpy` | >=1.24.0,<3.0.0 | Numerical operations |

---

### Apple Silicon Acceleration

```bash
pip install agentic-brain[mlx]
```

| Package | Version | Purpose |
|---------|---------|---------|
| `mlx` | >=0.5.0,<1.0.0 | Apple MLX framework for M1/M2/M3 GPU acceleration |
| `numpy` | >=1.24.0,<3.0.0 | Array operations |

---

## Installation Recommendations

### Minimal Install (CLI Only)
```bash
pip install agentic-brain
```
Installs core dependencies including numpy.

---

### Development
```bash
pip install agentic-brain[dev]
```
Includes all testing and linting tools.

---

### Testing Only
```bash
pip install agentic-brain[test]
```
Test dependencies only for CI/CD.

---

### Full Features
```bash
pip install agentic-brain[all]
```
All optional dependencies except dev/test.

---

## Verification

### Verify numpy is installed:
```bash
python -c "import numpy; print(numpy.__version__)"
```

### Run tests:
```bash
pytest tests/ -v
```

### Check dependencies:
```bash
pip list | grep -E "numpy|pytest|fastapi"
```

---

## Summary

✅ **numpy is included** in core dependencies (line 72 of pyproject.toml)  
✅ **All test dependencies are listed** in both `[dev]` and `[test]` groups  
✅ **Test mocking libraries** (fakeredis, mongomock, responses) are included  
✅ **docker** is included for infrastructure tests  

The dependency configuration is complete and correct!

---

**Maintainer:** Agentic Brain Contributors (agentic-brain@proton.me)
