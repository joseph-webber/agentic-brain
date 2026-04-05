# GraphRAG Global Search

Microsoft GraphRAG-style global search implementation for answering queries that require understanding across the entire knowledge graph.

## Overview

Global Search uses a **map-reduce pattern** to synthesize information from community summaries across the knowledge graph. Unlike local search (which finds specific entities), global search answers broad questions like:

- "What are the main themes in this dataset?"
- "Summarize the key topics across all documents"
- "What patterns emerge from the data?"

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        GLOBAL SEARCH                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐                                                 │
│  │   Query     │                                                 │
│  └──────┬──────┘                                                 │
│         │                                                         │
│         ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                    MAP PHASE                             │     │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │     │
│  │  │ Comm 1  │ │ Comm 2  │ │ Comm 3  │ │ Comm N  │        │     │
│  │  │ Summary │ │ Summary │ │ Summary │ │ Summary │        │     │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘        │     │
│  │       │           │           │           │              │     │
│  │       ▼           ▼           ▼           ▼              │     │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │     │
│  │  │ LLM     │ │ LLM     │ │ LLM     │ │ LLM     │        │     │
│  │  │ Query   │ │ Query   │ │ Query   │ │ Query   │        │     │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘        │     │
│  │       │           │           │           │              │     │
│  │       ▼           ▼           ▼           ▼              │     │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │     │
│  │  │Response │ │Response │ │Response │ │Response │        │     │
│  │  │+ Score  │ │+ Score  │ │+ Score  │ │+ Score  │        │     │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘        │     │
│  └───────┼───────────┼───────────┼───────────┼──────────────┘     │
│          │           │           │           │                    │
│          └───────────┴─────┬─────┴───────────┘                    │
│                            │                                       │
│                            ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                   REDUCE PHASE                           │     │
│  │  ┌────────────────────────────────────────────────┐     │     │
│  │  │  Filter by relevance score                      │     │     │
│  │  │  Extract cross-community themes                 │     │     │
│  │  │  Rank and aggregate responses                   │     │     │
│  │  │  Synthesize final answer (LLM)                  │     │     │
│  │  └────────────────────────────────────────────────┘     │     │
│  └─────────────────────────────────────────────────────────┘     │
│                            │                                       │
│                            ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                    FINAL RESPONSE                        │     │
│  │  • Synthesized answer                                    │     │
│  │  • Cross-community themes                                │     │
│  │  • Source communities                                    │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Search Modes

### Static Mode

Queries all communities at a fixed hierarchy level. Simple and predictable.

```python
from agentic_brain.rag import GlobalSearch, GlobalSearchConfig, GlobalSearchMode

config = GlobalSearchConfig(
    mode=GlobalSearchMode.STATIC,
    community_level=1,  # Query leaf-level communities
)
search = GlobalSearch(driver, llm, config)
result = await search.search("What are the main themes?")
```

### Dynamic Mode (Default)

Starts at root level, evaluates relevance, and only drills into relevant branches. More efficient for large graphs.

```python
config = GlobalSearchConfig(
    mode=GlobalSearchMode.DYNAMIC,
    drill_down_threshold=0.5,  # Only drill into communities scoring > 0.5
)
search = GlobalSearch(driver, llm, config)
result = await search.search("What are the main themes?")
```

### Hierarchical Mode

Traverses all hierarchy levels for the most comprehensive results.

```python
config = GlobalSearchConfig(
    mode=GlobalSearchMode.HIERARCHICAL,
    max_hierarchy_depth=3,  # Query levels 3, 2, and 1
)
search = GlobalSearch(driver, llm, config)
result = await search.search("What are the main themes?")
```

## Quick Start

### Basic Usage

```python
from agentic_brain.rag import GlobalSearch, global_search

# Quick function call
result = await global_search(
    "What are the main themes in this knowledge base?",
    driver=neo4j_driver,
    llm=your_llm,
)
print(result.response)
print(result.themes)

# Full class usage
search = GlobalSearch(driver, llm)
result = await search.search("Summarize the key topics")

# Access results
print(f"Response: {result.response}")
print(f"Themes: {result.themes}")
print(f"Communities queried: {result.total_communities_queried}")
print(f"Execution time: {result.execution_time_ms}ms")
```

### With GraphRAG Integration

```python
from agentic_brain.rag import GraphRAG, SearchStrategy

rag = GraphRAG(config)

# Use GLOBAL strategy for broad questions
results = await rag.search(
    "What are the main themes across all documents?",
    strategy=SearchStrategy.GLOBAL,
    top_k=10,
)

for r in results:
    print(f"Community: {r['community_id']}")
    print(f"Themes: {r['themes']}")
    print(f"Score: {r['score']}")
```

## Configuration Reference

```python
@dataclass
class GlobalSearchConfig:
    # Search behavior
    mode: GlobalSearchMode = GlobalSearchMode.DYNAMIC
    response_type: ResponseType = ResponseType.SUMMARY
    
    # Community selection
    community_level: int = 1          # Hierarchy level (1=leaf, 2=coarse, 3=global)
    max_communities: int = 100        # Max communities to query
    min_relevance_score: float = 0.1  # Minimum score to include
    
    # Rate limiting
    batch_size: int = 10              # Communities per LLM batch
    requests_per_minute: int = 60     # LLM rate limit
    concurrent_requests: int = 5      # Max parallel LLM calls
    
    # Response generation
    max_tokens_per_community: int = 500
    max_output_tokens: int = 2000
    temperature: float = 0.0
    
    # Caching
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600
    
    # Hierarchical settings
    drill_down_threshold: float = 0.5
    max_hierarchy_depth: int = 3
    
    # Theme extraction
    extract_themes: bool = True
    min_theme_mentions: int = 2       # Min communities mentioning a theme
```

## Response Types

```python
from agentic_brain.rag import ResponseType

# Concise summary (default)
config = GlobalSearchConfig(response_type=ResponseType.SUMMARY)

# Detailed analysis with sections
config = GlobalSearchConfig(response_type=ResponseType.DETAILED)

# Focus on themes only
config = GlobalSearchConfig(response_type=ResponseType.THEMES)

# Ranked list of findings
config = GlobalSearchConfig(response_type=ResponseType.RANKED)
```

## Community Hierarchy

Global search works with a 3-level community hierarchy:

```
Level 3: Global (1 community)
    └── Level 2: Coarse (√N communities)
        └── Level 1: Leaf (N communities)
            └── Level 0: Entities
```

The hierarchy is built using Leiden community detection:

```python
from agentic_brain.rag import CommunityGraphRAG

# Build hierarchy
community_rag = CommunityGraphRAG(driver)
await community_rag.detect_communities()
await community_rag.summarize_communities(llm=your_llm)
hierarchy = await community_rag.build_hierarchy()
```

## Caching

Global search includes built-in response caching:

```python
# Enable caching (default)
config = GlobalSearchConfig(
    enable_cache=True,
    cache_ttl_seconds=3600,  # 1 hour
)

search = GlobalSearch(driver, llm, config)

# First query - cache miss
result1 = await search.search("What are the themes?")
assert result1.from_cache is False

# Second query - cache hit
result2 = await search.search("What are the themes?")
assert result2.from_cache is True

# Manual cache management
search.clear_cache()
stats = search.get_cache_stats()
```

## Rate Limiting

Built-in rate limiting protects against API limits:

```python
config = GlobalSearchConfig(
    requests_per_minute=60,    # Max LLM calls per minute
    concurrent_requests=5,      # Max parallel calls
    batch_size=10,             # Communities per batch
)
```

## LLM Integration

Global search works with any LLM that implements a `generate()` method:

```python
# OpenAI
from openai import AsyncOpenAI

class OpenAILLM:
    def __init__(self):
        self.client = AsyncOpenAI()
    
    async def generate(self, prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

# Anthropic
import anthropic

class ClaudeLLM:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()
    
    async def generate(self, prompt: str) -> str:
        response = await self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

# Local Ollama
import httpx

class OllamaLLM:
    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3", "prompt": prompt},
            )
            return response.json()["response"]
```

## Without LLM (Keyword Fallback)

Global search works without an LLM using keyword matching:

```python
# No LLM - uses keyword relevance scoring
search = GlobalSearch(driver, llm=None)
result = await search.search("machine learning")

# Results based on keyword overlap with community summaries
```

## Theme Extraction

Themes are extracted by finding concepts mentioned across multiple communities:

```python
result = await search.search("What patterns emerge?")

# Themes that appear in 2+ communities
for theme in result.themes:
    print(f"Cross-community theme: {theme}")

# Per-community themes
for cr in result.community_responses:
    print(f"Community {cr.community_id} themes: {cr.themes}")
```

## Performance Optimization

### Batch Size Tuning

```python
# Smaller batches = more parallelism, more overhead
config = GlobalSearchConfig(batch_size=5)

# Larger batches = less parallelism, less overhead
config = GlobalSearchConfig(batch_size=20)
```

### Community Limits

```python
# Limit communities queried (faster, less comprehensive)
config = GlobalSearchConfig(max_communities=50)

# Query more communities (slower, more comprehensive)
config = GlobalSearchConfig(max_communities=200)
```

### Relevance Filtering

```python
# Strict filtering (fewer results, higher quality)
config = GlobalSearchConfig(min_relevance_score=0.5)

# Loose filtering (more results, variable quality)
config = GlobalSearchConfig(min_relevance_score=0.05)
```

## Error Handling

```python
try:
    result = await search.search("test query")
except Exception as e:
    # Global search handles most errors internally
    # and returns empty/partial results
    logger.error(f"Search failed: {e}")

# Check result quality
if not result.community_responses:
    print("No relevant communities found")
    
if result.total_communities_queried == 0:
    print("No communities in graph - run community detection first")
```

## Comparison: Global vs Local Search

| Aspect | Global Search | Local Search |
|--------|---------------|--------------|
| Query Type | "What are the themes?" | "Tell me about X" |
| Scope | Entire knowledge graph | Specific entities |
| Method | Map-reduce over communities | Vector similarity |
| Speed | Slower (LLM calls) | Faster (embedding lookup) |
| Best For | Synthesis, summarization | Specific lookups |

## References

- [Microsoft GraphRAG Paper](https://arxiv.org/abs/2404.16130)
- [Microsoft GraphRAG GitHub](https://github.com/microsoft/graphrag)
- [GraphRAG Documentation](https://microsoft.github.io/graphrag/)
