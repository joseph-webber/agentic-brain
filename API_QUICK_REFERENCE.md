# Agentic Brain API - Quick Reference

## 📦 Installation

```bash
pip install agentic-brain
```

## 🚀 Dead-Simple Shortcuts

Import and go:

```python
from agentic_brain.api import quick_rag, quick_graph, quick_search, quick_eval
```

### RAG Query (1 line)

```python
result = quick_rag("How do I deploy?", docs=["deployment.md"])
print(result.answer)
```

### Knowledge Graph (1 line)

```python
graph = quick_graph(["User", "Project", "Task"], [("User", "owns", "Project")])
```

### Search (1 line)

```python
results = quick_search("neural networks", num_results=10)
```

### Evaluation (1 line)

```python
metrics = quick_eval([result1, result2], metrics=["retrieval", "generation"])
```

## 🔗 Fluent Builder (Chainable)

```python
from agentic_brain.api import AgenticBrain

# Build configuration
brain = (
    AgenticBrain()
    .with_llm_openai("gpt-4")        # or groq, ollama, anthropic
    .with_graph()                     # Neo4j graph
    .with_rag(cache_ttl_hours=24)    # RAG with caching
    .ingest_documents(["docs/"])      # Load documents
)

# Query
result = brain.query("What is our deployment process?")
print(result.answer)

# Track history
history = brain.get_query_history(limit=10)

# Evaluate
metrics = brain.evaluate_recent_queries()
print(f"Avg confidence: {metrics['avg_confidence']}")
```

## 📋 Common Patterns

### Pattern 1: Quick RAG Lookup

```python
# Fast, no configuration
result = quick_rag("question")
```

### Pattern 2: Production RAG

```python
# Full configuration with caching and graph
brain = (
    AgenticBrain()
    .with_llm_openai()
    .with_graph()
    .with_rag(cache_ttl_hours=24)
    .ingest_folder("knowledge_base/")
)

result = brain.query("question")
```

### Pattern 3: Search Pipeline

```python
# Multi-step search
results = quick_search("topic", num_results=20, search_type="hybrid")

# Evaluate quality
metrics = quick_eval(results)
```

### Pattern 4: Graph + RAG

```python
brain = (
    AgenticBrain()
    .with_graph()
    .with_rag()
    .add_entities(["User", "Project"])
    .add_relationships([("User", "manages", "Project")])
    .query("Who manages what?")
)
```

## 🎛️ LLM Provider Shortcuts

```python
# Local (free)
brain = AgenticBrain().with_llm_ollama("llama3.1:8b")

# Fast (free tier)
brain = AgenticBrain().with_llm_groq()

# Best quality
brain = AgenticBrain().with_llm_openai("gpt-4")

# Alternative
brain = AgenticBrain().with_llm_anthropic("claude-opus")
```

## 🔧 Configuration Methods

### LLM Configuration
- `with_llm(provider, model)` - Custom provider
- `with_llm_openai(model)` - OpenAI
- `with_llm_groq(model)` - Groq (free)
- `with_llm_ollama(model)` - Local Ollama
- `with_llm_anthropic(model)` - Anthropic

### Component Management
- `with_graph(neo4j_uri, user, password)` - Enable Neo4j
- `without_graph()` - Disable graph
- `with_rag(cache_ttl_hours, embedding_provider)` - Enable RAG
- `without_rag()` - Disable RAG

### Document Loading
- `ingest_documents(paths, extensions)` - Load files
- `ingest_folder(path, recursive)` - Load folder

### Graph Operations
- `add_entities(names)` - Create entities
- `add_relationships(tuples)` - Create relationships

### Query & Analyze
- `query(question)` - Execute RAG query
- `search(query, num_results, search_type)` - Search
- `get_query_history(limit)` - View history
- `evaluate_recent_queries()` - Get metrics
- `clear_history()` - Reset history

### Utilities
- `describe()` - Show configuration
- `repr(brain)` - Configuration string

## 📊 Evaluation Metrics

```python
# All metrics available
metrics = quick_eval(
    results,
    metrics=[
        "retrieval",    # Retrieval rate
        "generation",   # Answer quality
        "latency",      # Response time
        "sources",      # Source citation
        "confidence"    # Confidence calibration
    ]
)

# With golden answers
metrics = quick_eval(
    results,
    golden_answers=["expected answer 1", "expected answer 2"]
)
```

## ✨ Key Features

✅ **Chainable** - Every method returns self  
✅ **Graceful** - Errors return results, never crash  
✅ **Lazy** - Components initialize on first use  
✅ **Type-Safe** - Full type hints  
✅ **Well-Documented** - Docstrings everywhere  
✅ **Well-Tested** - 45 tests, 100% pass  
✅ **Backward Compatible** - Old API still works  

## 🎯 When to Use Each

| Scenario | Use |
|----------|-----|
| Quick lookup | `quick_rag()` |
| Complex workflow | `AgenticBrain()` |
| Search tasks | `quick_search()` |
| Quality check | `quick_eval()` |
| Graph work | `quick_graph()` or `.with_graph()` |

## 📚 More Information

- **Examples**: See `examples/api_quick_start.py`
- **Tests**: See `tests/test_api/test_shortcuts.py`
- **Full Docs**: See `README.md` or `API_ERGONOMICS_IMPROVEMENTS.md`
- **Code**: See `src/agentic_brain/api/`

## 🚨 Common Issues

**Q: Module not found?**  
A: Install with `pip install agentic-brain` or ensure you're in the right environment.

**Q: RAG not working?**  
A: Ensure Neo4j is running or use RAG without graph: `.without_graph()`

**Q: How do I handle errors?**  
A: All functions return error results - check `result.confidence == 0.0`

**Q: Can I use both shortcuts and builder?**  
A: Yes! They work together seamlessly.

**Q: Is this backward compatible?**  
A: 100% - old APIs still work, new APIs are additions.

## 💡 Pro Tips

1. **Start simple** - Use shortcuts first, add builder complexity as needed
2. **Chain methods** - Takes advantage of fluent API for readability  
3. **Reuse brain** - Create once, query many times to save resources
4. **Track history** - Use `get_query_history()` for debugging
5. **Evaluate quality** - Use `quick_eval()` to measure performance

---

**Ready to build AI apps?** Start with one of the quick-start examples above! 🚀
