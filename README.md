<div align="center">

<img src="./docs/assets/brain-logo.svg" alt="Agentic Brain Logo" width="120" onerror="this.style.display='none'"/>

# Agentic Brain

### Enterprise AI Orchestration Platform

**Multi-LLM orchestration** with **GraphRAG**, **Knowledge Graphs**, and **Vector Search**.  
Production-ready for **Healthcare**, **Finance**, **Legal**, and **Defense**.

```bash
pip install agentic-brain
```

[![CI](https://github.com/agentic-brain-project/agentic-brain/actions/workflows/ci.yml/badge.svg)](https://github.com/agentic-brain-project/agentic-brain/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentic-brain?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/agentic-brain/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://pypi.org/project/agentic-brain/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-5300%2B-brightgreen?logo=pytest)](./tests)

[![SOC 2](https://img.shields.io/badge/SOC_2-Ready-FF6B35)](./docs/COMPLIANCE.md)
[![HIPAA](https://img.shields.io/badge/HIPAA-Ready-4CAF50)](./docs/COMPLIANCE.md)
[![GDPR](https://img.shields.io/badge/GDPR-Compliant-0052CC)](./docs/COMPLIANCE.md)
[![WCAG 2.1](https://img.shields.io/badge/WCAG_2.1-AA-00703C)](./docs/ACCESSIBILITY.md)

[Quick Start](#-quick-start) · [Features](#-features) · [Documentation](#-documentation) · [API Reference](./docs/API_REFERENCE.md)

</div>

---

## 🎯 Overview

Agentic Brain is an enterprise AI orchestration platform that combines:

- **Multi-LLM Routing** — Intelligent model selection across 7+ providers
- **GraphRAG** — Hybrid vector + knowledge graph retrieval
- **100+ Data Loaders** — Connect to any enterprise data source
- **Durable Workflows** — Temporal-compatible execution patterns
- **Enterprise Security** — SOC 2, HIPAA, GDPR compliance ready

## ⚡ Quick Start

### One-Line Install

```bash
# macOS/Linux
curl -fsSL https://raw.githubusercontent.com/ecomlounge/brain/main/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/ecomlounge/brain/main/install.ps1 | iex
```

### PyPI Installation

The simplest way to install agentic-brain is from PyPI:

```bash
# Basic installation (core features only)
pip install agentic-brain

# With LLM support (OpenAI, Anthropic, etc.)
pip install "agentic-brain[llm]"

# With API server and async support
pip install "agentic-brain[api]"

# With GraphRAG and Neo4j
pip install "agentic-brain[graphrag]"

# With voice capabilities
pip install "agentic-brain[voice-kokoro]"

# Full installation (everything)
pip install "agentic-brain[all]"

# Development installation (with testing tools)
pip install "agentic-brain[dev]"
```

**Verify installation:**

```bash
# Check version
python -c "import agentic_brain; print(f'Agentic Brain {agentic_brain.__version__}')"

# Try the CLI
agentic-brain --help
agentic --help
ab --help
```

### Manual Install

```bash
pip install agentic-brain
ab config init
ab chat "Hello, Brain!"
```

### Docker

```bash
git clone https://github.com/ecomlounge/brain.git
cd brain
cp .env.docker.example .env.docker
docker compose up -d
```

**Services:**
| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8000 | — |
| Neo4j | http://localhost:7474 | neo4j / Brain2026 |
| Redis | localhost:6379 | — |

## ✨ Features

### LLM Orchestration

| Feature | Description |
|---------|-------------|
| **Smart Router** | Auto-select optimal models based on task complexity |
| **Consensus Voting** | Multi-model agreement reduces hallucinations |
| **Fallback Chains** | Automatic failover across providers |
| **Cost Control** | Route simple tasks to free/cheap models |

**Supported Providers:** OpenAI, Anthropic, Google Gemini, Groq, Azure, AWS Bedrock, Ollama (local)

### GraphRAG Architecture

| Component | Technology |
|-----------|------------|
| **Vector Search** | Neo4j, Pinecone, Weaviate |
| **Knowledge Graph** | Neo4j native graph |
| **Embeddings** | MLX (Apple Silicon), CUDA, ROCm |
| **Retrieval** | Hybrid vector + graph + BM25 |

### Data Integrations

<details>
<summary><strong>100+ Loaders Available</strong></summary>

**Documents:** PDF, Word, Excel, Markdown, HTML, JSON  
**Code:** GitHub, GitLab, Bitbucket  
**Enterprise:** Confluence, Notion, Slack, Teams, Jira, Salesforce  
**Databases:** PostgreSQL, MySQL, MongoDB, Redis  
**Cloud:** AWS S3, Google Cloud Storage, Azure Blob  
**Commerce:** WooCommerce, Shopify, Magento

</details>

### Security & Compliance

| Framework | Status |
|-----------|--------|
| SOC 2 Type II | ✅ Ready |
| ISO 27001 | ✅ Ready |
| HIPAA | ✅ Ready (BAA available) |
| GDPR | ✅ Compliant |
| WCAG 2.1 AA | ✅ Compliant |

### Industry Modes

Switch compliance posture with one command:

```bash
ab mode switch medical    # HIPAA, PHI handling
ab mode switch banking    # PCI-DSS, SOX compliance
ab mode switch government # FedRAMP, FIPS 140-2
```

## 💻 Usage

### Quick-Start API (One-Liners!)

Dead simple convenience functions for common tasks:

```python
# RAG - one-liner Q&A
from agentic_brain.api import quick_rag
result = quick_rag("How do I deploy?", docs=["deployment.md"])
print(result.answer)

# Search - unified across all sources
from agentic_brain.api import quick_search
results = quick_search("neural networks", num_results=10)

# Graph - instant knowledge graph
from agentic_brain.api import quick_graph
graph = quick_graph(
    entities=["User", "Project", "Task"],
    relationships=[
        ("User", "owns", "Project"),
        ("Project", "contains", "Task"),
    ]
)

# Evaluate - fast metrics on results
from agentic_brain.api import quick_eval
metrics = quick_eval(rag_results, metrics=["retrieval", "generation"])
```

### Fluent Builder (Chainable API)

Build complex workflows with readable method chaining:

```python
from agentic_brain.api import AgenticBrain

# Setup once, query many times
brain = (
    AgenticBrain()
    .with_llm_openai("gpt-4")           # Fast provider switching
    .with_graph()                        # Enable knowledge graph
    .with_rag(cache_ttl_hours=24)       # Enable RAG with caching
    .ingest_documents(["docs/", "wiki/"]) # Load documents
    .add_entities(["User", "Project"])
    .add_relationships([("User", "manages", "Project")])
)

# Query with automatic history tracking
result = brain.query("What projects do we have?")
print(result.answer)

# Evaluate multiple queries
metrics = brain.evaluate_recent_queries()
print(f"Accuracy: {metrics['generation']['avg_confidence']}")

# Check configuration
print(brain.describe())
```

### Python SDK

```python
from agentic_brain import Agent

agent = Agent("assistant")
response = await agent.chat_async("Hello!")
```

### GraphRAG Pipeline

```python
from agentic_brain.rag import RAGPipeline

rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
await rag.ingest("./documents/")
answer = await rag.query("What are our Q3 targets?")
```

### Durable Workflows

```python
from agentic_brain.temporal import workflow, activity

@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, order_id: str):
        await workflow.execute_activity(validate_order, order_id)
        await workflow.execute_activity(process_payment, order_id)
```

### Voice Output

```python
from agentic_brain.voice import speak

speak("Order confirmed!", voice="Karen", rate=160)
```

## 🔧 Configuration

```bash
# Set LLM provider
ab config set llm.provider ollama      # Local (free)
ab config set llm.provider anthropic   # Claude
ab config set llm.provider openai      # GPT-4

# Set API keys
ab config set llm.api_key $ANTHROPIC_API_KEY
```

**Free Providers:**
| Provider | Setup | Notes |
|----------|-------|-------|
| Ollama | https://ollama.ai | Local, no signup |
| Groq | https://console.groq.com | 30 req/min free |
| Gemini | https://aistudio.google.com | 1M tokens/day |

## 📊 Performance

| Component | Typical | Target |
|-----------|---------|--------|
| Text Response | 100ms | <150ms ✅ |
| Voice Output | 92ms | <200ms ✅ |
| Embeddings (MLX) | 1.4ms | <10ms ✅ |

## 🏢 Enterprise

<table>
<tr>
<td width="50%">

**Security**
- JWT RS256/ES256, OAuth 2.0, SAML 2.0
- Multi-tenant isolation
- Air-gapped deployment ready
- Zero telemetry by default

</td>
<td width="50%">

**Operations**
- OpenTelemetry tracing
- Prometheus metrics
- Health probes for Kubernetes
- 27 durability modules

</td>
</tr>
</table>

## 📚 Documentation

| Guide | Description |
|-------|-------------|
| [Quick Start](./docs/QUICKSTART.md) | Get running in 5 minutes |
| [API Reference](./docs/API_REFERENCE.md) | Complete API documentation |
| [GraphRAG Guide](./docs/GRAPHRAG.md) | Vector + graph retrieval |
| [Security](./docs/SECURITY.md) | Security architecture |
| [Deployment](./docs/DEPLOYMENT.md) | Production deployment |

**Full documentation:** [docs/INDEX.md](./docs/INDEX.md)

## 🚀 One-Click Deploy

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/agentic-brain-project/agentic-brain)
[![Deploy to Railway](https://railway.app/button.svg)](https://railway.app/template/agentic-brain)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/agentic-brain-project/agentic-brain)

## ⚔️ Comparison

| Feature | Agentic Brain | LangChain | LlamaIndex |
|---------|:-------------:|:---------:|:----------:|
| GraphRAG Native | ✅ Built-in | ❌ Plugin | ❌ Plugin |
| Multi-LLM Orchestration | ✅ Built-in | ⚠️ DIY | ⚠️ DIY |
| GPU Acceleration | ✅ MLX/CUDA/ROCm | ⚠️ Limited | ⚠️ Limited |
| Workflow Durability | ✅ 27 modules | ❌ None | ❌ None |
| Voice Output | ✅ 180+ voices | ❌ None | ❌ None |
| Enterprise Auth | ✅ Built-in | ⚠️ DIY | ⚠️ DIY |

## 🛠️ Development

```bash
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain
pip install -e ".[dev]"
pytest tests/ -v
```

## 📄 License

**Apache 2.0** — [See LICENSE](LICENSE)

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

---

<div align="center">

**[Report Bug](https://github.com/agentic-brain-project/agentic-brain/issues)** · **[Request Feature](https://github.com/agentic-brain-project/agentic-brain/issues)** · **[Discussions](https://github.com/agentic-brain-project/agentic-brain/discussions)**

[![Discord](https://img.shields.io/badge/Discord-Chat-5865F2?logo=discord&logoColor=white)](https://discord.gg/agentic-brain)
[![Twitter](https://img.shields.io/badge/Twitter-Follow-000000?logo=x&logoColor=white)](https://twitter.com/agentic_brain)

</div>
