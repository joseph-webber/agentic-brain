# Agentic Brain 🧠

**Lightweight AI agent framework with Neo4j memory and LLM orchestration.**

[![License: GPL v2](https://img.shields.io/badge/License-GPL_v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## What is Agentic Brain?

A minimal, production-ready framework for building AI agents with:

- **Persistent Memory** - Neo4j knowledge graph for long-term recall
- **Data Separation** - Keep private, public, and customer data isolated
- **LLM Orchestration** - Route queries to the right model
- **Clean Architecture** - Type-hinted, documented, tested

This is the **lite version** of [brain-core](https://github.com/joseph-webber/brain-core), focused on the essentials.

---

## Quick Start

### Installation

```bash
pip install agentic-brain
```

Or from source:

```bash
git clone https://github.com/joseph-webber/agentic-brain.git
cd agentic-brain
pip install -e .
```

### Basic Usage

```python
from agentic_brain import Agent, Neo4jMemory

# Create memory backend
memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your-password"
)

# Create an agent
agent = Agent(
    name="assistant",
    memory=memory,
    system_prompt="You are a helpful assistant."
)

# Chat with memory
response = agent.chat("What did we discuss yesterday?")
print(response)
```

### Data Separation

```python
from agentic_brain import Neo4jMemory, DataScope

# Create isolated memory scopes
public_memory = Neo4jMemory(uri="...", scope=DataScope.PUBLIC)
private_memory = Neo4jMemory(uri="...", scope=DataScope.PRIVATE)
customer_memory = Neo4jMemory(uri="...", scope=DataScope.CUSTOMER, customer_id="acme-corp")

# Agents only see their scope
public_agent = Agent(name="public-bot", memory=public_memory)
private_agent = Agent(name="internal-bot", memory=private_memory)
customer_agent = Agent(name="acme-bot", memory=customer_memory)
```

---

## Features

### 🧠 Persistent Memory

Unlike ChatGPT, agentic-brain remembers across sessions:

```python
# Session 1
agent.chat("My favorite color is blue")

# Session 2 (days later)
agent.chat("What's my favorite color?")
# → "Your favorite color is blue"
```

### 🔒 Data Separation Architecture

Keep data secure while enabling chatbots:

| Scope | Use Case | Isolation |
|-------|----------|-----------|
| `PUBLIC` | General knowledge, FAQs | Shared across all users |
| `PRIVATE` | Internal company data | Admin access only |
| `CUSTOMER` | B2B client data | Per-customer isolation |

### 🔄 LLM Orchestration

Route to the right model:

```python
from agentic_brain import LLMRouter

router = LLMRouter(
    default="gpt-4",
    fallback="ollama/llama3",
    routing_rules={
        "code": "gpt-4",
        "simple": "gpt-3.5-turbo",
        "private": "ollama/llama3"  # Keep sensitive queries local
    }
)
```

### 🔥 Firebase Ready

Coming soon: Firebase integration for real-time chat.

```python
from agentic_brain.firebase import FirebaseChat

chat = FirebaseChat(
    project_id="your-project",
    agent=agent
)
chat.listen()  # Real-time message handling
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Your Application                      │
├─────────────────────────────────────────────────────────┤
│                      Agent Layer                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                  │
│  │ Agent 1 │  │ Agent 2 │  │ Agent N │                  │
│  └────┬────┘  └────┬────┘  └────┬────┘                  │
├───────┼────────────┼────────────┼───────────────────────┤
│       │            │            │                        │
│  ┌────▼────────────▼────────────▼────┐                  │
│  │           LLM Router              │ ◄── Model routing │
│  └────┬─────────────────────────┬────┘                  │
│       │                         │                        │
│  ┌────▼────┐               ┌────▼────┐                  │
│  │  OpenAI │               │  Ollama │ ◄── Local/Cloud  │
│  └─────────┘               └─────────┘                  │
├─────────────────────────────────────────────────────────┤
│                    Memory Layer                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │               Neo4j Knowledge Graph              │    │
│  │  ┌────────┐  ┌─────────┐  ┌──────────┐         │    │
│  │  │ PUBLIC │  │ PRIVATE │  │ CUSTOMER │         │    │
│  │  └────────┘  └─────────┘  └──────────┘         │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## Comparison: Agentic Brain vs Brain-Core

| Feature | Agentic Brain (Public) | Brain-Core (Private) |
|---------|------------------------|----------------------|
| Neo4j Memory | ✅ | ✅ |
| Data Separation | ✅ | ✅ |
| LLM Routing | ✅ Basic | ✅ Advanced |
| Agent Framework | ✅ Single | ✅ Multi-agent fleet |
| Firebase | 🔜 Coming | ✅ |
| Voice/TTS | ❌ | ✅ |
| MCP Servers | ❌ | ✅ (9 servers) |
| RAG Pipeline | ❌ | ✅ |
| Self-Healing | ❌ | ✅ |

---

## Examples

See the `examples/` directory:

- `basic_chat.py` - Simple chatbot with memory
- `data_separation.py` - Multi-tenant data isolation
- `llm_routing.py` - Model selection logic

---

## Requirements

- Python 3.9+
- Neo4j 5.x (for memory)
- OpenAI API key or Ollama (for LLM)

---

## License

GPL-2.0-or-later - See [LICENSE](LICENSE)

---

## Author

**Joseph Webber**  
📧 joseph@ecomlounge.com  
🌏 Adelaide, South Australia

---

## Roadmap

- [x] Neo4j memory backend
- [x] Data separation scopes
- [x] Basic agent framework
- [x] LLM routing
- [ ] Firebase real-time chat
- [ ] RAG (Retrieval-Augmented Generation)
- [ ] Vector embeddings
- [ ] Multi-agent orchestration

---

*Part of the [brain-core](https://github.com/joseph-webber/brain-core) ecosystem*
