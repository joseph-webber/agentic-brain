# Agentic Brain

<div align="center">

```
╔═══════════════════════════════════════╗
║   🧠 AGENTIC BRAIN                   ║
║   Production-Ready AI Chatbot        ║
║   with Persistent Memory             ║
╚═══════════════════════════════════════╝
```

![License](https://img.shields.io/badge/license-GPL--3.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen)

</div>

---

## Overview

**Production-ready AI chatbot framework with persistent memory, retrieval-augmented generation, and multi-user isolation—built for enterprise deployments.**

Agentic Brain combines Neo4j knowledge graphs, session persistence, and local-first inference to deliver stateful, contextual AI experiences that scale. No vendor lock-in. Works locally with Ollama or integrates with cloud LLMs.

---

## ✨ Key Features

- **🧠 Neo4j Knowledge Graph** — Persistent memory across sessions with semantic search
- **💾 Session Persistence** — User state and conversation history preserved automatically
- **🔍 RAG Built-In** — Retrieval-augmented generation for knowledge-grounded responses
- **👥 Multi-User Isolation** — Tenant separation and role-based access control
- **🐳 Docker-Ready** — Production deployments with compose files included
- **🏠 Local-First** — Run entirely on-premises with Ollama; zero external dependencies
- **⚡ Fast** — Async I/O, connection pooling, optimized queries
- **🔐 Enterprise-Grade** — Encryption, audit logging, compliance-ready

---

## 🚀 Quick Start

```bash
# 1. Install
pip install agentic-brain

# 2. Start Neo4j locally
docker run -d -p 7687:7687 neo4j:latest

# 3. Create a chatbot in 30 seconds
from agentic_brain import Brain

brain = Brain(neo4j_uri="bolt://localhost:7687")
response = brain.chat("Hello, remember this: I prefer Python.", user_id="user_1")
print(response)

# 4. Chatbot remembers context
response = brain.chat("What do I prefer?", user_id="user_1")
print(response)  # Output: "You prefer Python"

# 5. Deploy
docker-compose up
```

---

## 📦 Installation

### Via pip (Recommended)

```bash
pip install agentic-brain
```

Requires: Python 3.10+, Neo4j 5.0+

### Via Docker

```bash
git clone https://github.com/yourusername/agentic-brain.git
cd agentic-brain
docker-compose up
```

Includes Neo4j, Redis, and pre-configured brain services.

### From Source

```bash
git clone https://github.com/yourusername/agentic-brain.git
cd agentic-brain
pip install -e .

# Install optional dependencies
pip install agentic-brain[dev,docker]
```

---

## 💡 Code Example

```python
from agentic_brain import Brain, ConversationTemplate

# Initialize with local Neo4j
brain = Brain(
    neo4j_uri="bolt://localhost:7687",
    neo4j_password="neo4j",
    llm_provider="ollama",  # or "openai", "anthropic"
)

# Chat with memory
user_id = "customer_12345"
response = brain.chat(
    message="I work in healthcare and need a compliant system.",
    user_id=user_id,
)

# Retrieve conversation history
history = brain.get_session(user_id).get_messages(limit=10)

# RAG: Ground responses in knowledge
documents = brain.search_knowledge("healthcare compliance", limit=5)
response = brain.chat(
    message="What compliance rules apply?",
    user_id=user_id,
    context=documents,
)

# Export memory graph
graph_json = brain.export_graph(user_id)
```

---

## 📋 Built-In Templates

Pre-configured templates for common use cases:

| Template | Best For | Includes |
|----------|----------|----------|
| **Minimal** | Learning / Prototypes | Core brain, single user |
| **Retail** | E-commerce | Product memory, cart state, recommendations |
| **Support** | Customer service | Ticket history, resolution patterns, escalation logic |
| **Enterprise** | Large orgs | RBAC, audit trails, multi-tenant isolation |

```bash
agentic-brain init --template retail
```

---

## 📚 Documentation

- **[Installation Guide](./docs/installation.md)** — Detailed setup for all platforms
- **[API Reference](./docs/api.md)** — Complete function documentation
- **[Architecture](./docs/architecture.md)** — Design decisions and data flow
- **[Deployment](./docs/deployment.md)** — Production checklist, scaling, monitoring
- **[Examples](./examples/)** — Retail, support, and enterprise chatbots
- **[FAQ](./docs/faq.md)** — Common questions answered

### Core Modules

- **[Streaming](./docs/STREAMING.md)** — Real-time token-by-token responses (Ollama, OpenAI, Anthropic)
- **[Plugins](./docs/plugins.md)** — Extensible plugin system for custom functionality
- **[Dashboard](./DASHBOARD.md)** — Admin dashboard for monitoring and management
- **[Analytics](./docs/chat.md)** — Usage tracking and performance metrics
- **[Orchestration](./docs/getting-started.md)** — Crew + Workflow integration for multi-agent systems

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────┐
│   API Layer (FastAPI)            │
├──────────────────────────────────┤
│   Brain Logic                    │
│   ├─ Conversation Manager        │
│   ├─ Memory Controller           │
│   └─ RAG Engine                  │
├──────────────────────────────────┤
│   Data Layer                     │
│   ├─ Neo4j (Knowledge Graph)    │
│   ├─ Redis (Sessions)            │
│   └─ Vector DB (Embeddings)      │
├──────────────────────────────────┤
│   LLM Layer                      │
│   ├─ Ollama (Local)              │
│   ├─ OpenAI / Anthropic (Cloud) │
│   └─ Custom Providers            │
└──────────────────────────────────┘
```

---

## Development

### Setup
```bash
pip install -e ".[dev]"
pre-commit install
```

### Running Tests
```bash
pytest tests/ -v
```

### Code Quality
Pre-commit hooks run automatically on commit. To run manually:
```bash
pre-commit run --all-files
```

---

## 🔧 Configuration

Set environment variables or use `brain.config`:

```python
import os

os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_PASSWORD"] = "secure_password"
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["OLLAMA_MODEL"] = "mistral"
os.environ["REDIS_URL"] = "redis://localhost:6379"
```

---

## 📊 Monitoring & Observability

Built-in telemetry with OpenTelemetry:

```python
from agentic_brain import Brain

brain = Brain(
    enable_telemetry=True,
    tracing_endpoint="http://localhost:4317",
)

# Logs automatically include:
# - Request/response times
# - Memory lookups
# - LLM calls
# - Session lifecycle
```

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Run integration tests (requires Neo4j, Ollama)
pytest tests/integration/ -v

# Code coverage
pytest --cov=agentic_brain tests/
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/yourusername/agentic-brain.git
cd agentic-brain
pip install -e ".[dev]"
pre-commit install
```

### Pull Request Process

1. Fork and branch: `git checkout -b feature/your-feature`
2. Commit with clear messages
3. Add tests for new functionality
4. Run linting: `make lint`
5. Submit PR with description

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0** — see [LICENSE](./LICENSE) for details.

### What This Means

- ✅ **Commercial use allowed** with source code disclosure
- ✅ **Modifications permitted** with same license
- ✅ **Distribution allowed** with source availability
- ✅ **Private use allowed** without disclosure
- ⚠️ **Derivative works must be open-source** under GPL-3.0

---

## 🐛 Support

- **Issues** — [GitHub Issues](https://github.com/yourusername/agentic-brain/issues)
- **Discussions** — [GitHub Discussions](https://github.com/yourusername/agentic-brain/discussions)
- **Email** — support@example.com

---

## 🎯 Roadmap

- [ ] PostgreSQL support for structured data
- [ ] GraphQL API layer
- [ ] Vision capabilities (image understanding)
- [ ] Real-time collaborative sessions
- [ ] Advanced RAG with BM25 + semantic reranking
- [ ] Multi-language support
- [ ] Kubernetes operator

---

## 🙏 Acknowledgments

Built with production expertise in AI systems, persistent storage, and distributed applications.

---

<div align="center">

**[Documentation](./docs) • [Examples](./examples) • [Issues](https://github.com/yourusername/agentic-brain/issues)**

Made with ❤️ for developers building intelligent systems.

</div>
