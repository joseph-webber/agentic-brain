# Agentic Brain Examples

Learn by example! Each script demonstrates key features.

## Quick Start

```bash
cd examples
pip install -e "..[dev,api]"
python simple_chat.py
```

## Examples

| Example | Description | Difficulty |
|---------|-------------|------------|
| simple_chat.py | Basic chatbot with Ollama | Beginner |
| chat_with_memory.py | Persistent memory with Neo4j | Beginner |
| rag_chat.py | Document Q&A with RAG | Intermediate |
| streaming_chat.py | Token streaming | Intermediate |
| custom_plugin_example.py | Create custom plugins | Intermediate |
| analytics_example.py | Track usage metrics | Intermediate |
| orchestration_examples.py | Multi-agent workflows | Advanced |

## Prerequisites

- Python 3.10+
- Ollama running locally (for most examples)
- Neo4j (for memory/RAG examples)

## Which Example Should I Run?

- **New to agentic-brain?** → Start with `simple_chat.py`
- **Want persistent conversations?** → Try `chat_with_memory.py`
- **Building document Q&A?** → See `rag_chat.py`
- **Need real-time responses?** → Check `streaming_chat.py`
- **Extending functionality?** → Look at `custom_plugin_example.py`
- **Multi-agent systems?** → Study `orchestration_examples.py`

## See Also

- [Getting Started Guide](../docs/getting-started.md)
- [API Reference](../docs/api/)
- [Tutorials](../docs/tutorials/)
