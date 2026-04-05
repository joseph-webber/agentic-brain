# RRF (Reciprocal Rank Fusion) Quick Reference

> **Version**: 2.0.0 (Unified) | **Module**: `agentic_brain.rag.rrf`

## What is RRF?

RRF combines multiple ranked result lists into a single fused ranking. It's ideal for hybrid search where you have results from different sources (vector search, graph search, keyword search) and want to find items that are highly relevant across multiple signals.

**Formula:** `RRF_score = Σ (weight / (k + rank))` for each source

**Key property:** Items that appear in multiple lists get boosted because their scores accumulate.

## 🆕 Unified Implementation (v2.0)

As of v2.0, there is **ONE canonical RRF implementation** in `agentic_brain.rag.rrf`. All other modules (hybrid.py, parallel_retrieval.py, community.py, graph.py) use this unified version.

### Import Options

```python
# NEW: Canonical import (recommended)
from agentic_brain.rag.rrf import reciprocal_rank_fusion, RRFResult

# Or from main module
from agentic_brain.rag import reciprocal_rank_fusion, RRFResult

# LEGACY: Still works for backward compatibility
from agentic_brain.rag.hybrid import reciprocal_rank_fusion  # Legacy API
```

## Quick Start

### New API (Recommended)

```python
from agentic_brain.rag import reciprocal_rank_fusion

# Prepare ranked lists with source names
result = reciprocal_rank_fusion([
    {"source": "vector", "results": [
        {"id": "doc_1", "score": 0.95, "content": "..."},
        {"id": "doc_2", "score": 0.87, "content": "..."},
    ]},
    {"source": "keyword", "results": [
        {"id": "doc_2", "score": 0.92, "content": "..."},
        {"id": "doc_3", "score": 0.80, "content": "..."},
    ]},
])

# Results are sorted by RRF score, highest first
for item in result.items:
    print(f"{item['id']}: RRF={item['rrf_score']:.4f}")
    # Output:
    # doc_2: RRF=0.0328 (appears in both - consensus!)
    # doc_1: RRF=0.0164 (vector only)
    # doc_3: RRF=0.0161 (keyword only)
```

### Legacy API (Backward Compatible)

```python
from agentic_brain.rag.hybrid import reciprocal_rank_fusion

# Old signature: vector_results, graph_results, keyword_results=None, k=60
fused = reciprocal_rank_fusion(vector_results, graph_results, keyword_results)

for item in fused:
    print(f"{item['id']}: RRF={item['rrf_score']:.4f}")
```

## New Features in v2.0

### 1. Weighted RRF

Give different sources different importance:

```python
result = reciprocal_rank_fusion(
    ranked_lists,
    weights={"vector": 1.5, "keyword": 1.0, "graph": 1.2},
)
```

### 2. Explain Mode

Debug why items ranked the way they did:

```python
result = reciprocal_rank_fusion(ranked_lists, explain=True)

# See per-source contributions
for item in result.items[:3]:
    exp = result.explanations[item["id"]]
    print(f"{item['id']}: appeared in {exp.appeared_in_count} sources")
    for contrib in exp.sources:
        print(f"  {contrib.source}: rank {contrib.rank}, score {contrib.weighted_score:.4f}")
```

### 3. Top-K Limit

```python
result = reciprocal_rank_fusion(ranked_lists, top_k=10)
assert len(result.items) <= 10
```

### 4. Full Type Hints

```python
def reciprocal_rank_fusion(
    ranked_lists: list[dict[str, Any]],
    *,
    k: int = 60,
    weights: dict[str, float] | None = None,
    explain: bool = False,
    top_k: int | None = None,
    merge_strategy: str = "update",
) -> RRFResult: ...
```

## Key Parameters

### `k` Parameter

- **What it does:** Controls how much emphasis is placed on ranking position
- **Default:** 60 (industry standard)
- **Range:** Typically 10-100
- **Effects:**
  - `k=10`: Emphasizes top results more, amplifies differences
  - `k=60`: Balanced (standard)
  - `k=100`: Downplays differences, more uniform distribution

```python
# Different k values, same input:
k=10: First item gets 1/11 = 0.0909
k=60: First item gets 1/61 = 0.0164  (default)
k=100: First item gets 1/101 = 0.0099
```

### `weights` Parameter

| Source Type | Suggested Weight | When to Use |
|-------------|------------------|-------------|
| Vector (semantic) | 1.0-1.5 | General queries, conceptual |
| Keyword (BM25) | 1.0 | Technical docs, exact terms |
| Graph (relationships) | 0.8-1.2 | Entity-centric queries |
| Community summaries | 0.6-0.8 | High-level overview queries |

### `merge_strategy` Parameter

How to handle when same item appears in multiple sources:

| Strategy | Behavior |
|----------|----------|
| `"update"` (default) | Later sources update earlier data |
| `"first"` | Keep only first occurrence's data |
| `"all"` | Keep all source data in a list |

## Understanding Results

### RRFResult Structure

```python
@dataclass
class RRFResult:
    items: list[dict[str, Any]]           # Fused results with rrf_score
    explanations: dict[str, RRFExplanation] | None  # If explain=True
    k: int                                # k value used
    weights: dict[str, float] | None      # Weights used
    total_sources: int                    # Number of sources
    total_unique_items: int               # Number of unique items
```

### Scoring

Each result item includes:
- `id`: Unique identifier
- `rrf_score`: Fusion score (sum of weight/(k+rank) from each list)
- All fields from all source lists (merged per merge_strategy)

## Common Patterns

### Pattern 1: Hybrid Search Pipeline

```python
from agentic_brain.rag import reciprocal_rank_fusion

async def hybrid_retrieve(query: str, top_k: int = 10):
    # Parallel retrieval
    vector_results = await vector_search(query, top_k * 2)
    keyword_results = await keyword_search(query, top_k * 2)
    graph_results = await graph_search(query, top_k * 2)

    # Fuse with weighted RRF
    result = reciprocal_rank_fusion(
        [
            {"source": "vector", "results": vector_results},
            {"source": "keyword", "results": keyword_results},
            {"source": "graph", "results": graph_results},
        ],
        weights={"vector": 1.2, "keyword": 1.0, "graph": 1.0},
        top_k=top_k,
    )

    return result.items
```

### Pattern 2: Debug Low-Quality Results

```python
result = reciprocal_rank_fusion(ranked_lists, explain=True)

# Find items that only appeared in one source (potential false positives)
for item_id, exp in result.explanations.items():
    if exp.appeared_in_count == 1:
        print(f"⚠️ {item_id} only in {exp.sources[0].source}")
```

### Pattern 3: A/B Test Weight Configurations

```python
configs = {
    "balanced": {"vector": 1.0, "keyword": 1.0},
    "vector_heavy": {"vector": 1.5, "keyword": 0.8},
    "keyword_heavy": {"vector": 0.8, "keyword": 1.5},
}

for name, weights in configs.items():
    result = reciprocal_rank_fusion(ranked_lists, weights=weights)
    # Evaluate result quality...
```

## Module Architecture

```
agentic_brain/rag/
├── rrf.py                 # ← CANONICAL implementation (v2.0)
│   ├── reciprocal_rank_fusion()
│   ├── reciprocal_rank_fusion_legacy()
│   ├── get_result_id()
│   ├── RRFResult
│   └── RRFExplanation
├── hybrid.py              # Uses rrf.py, re-exports legacy API
├── parallel_retrieval.py  # Uses rrf.py
├── community.py           # Uses rrf.py
└── graph.py               # Uses rrf.py (via hybrid.py)
```

## Troubleshooting

### Error: "RRF result item must include one of: ('id', 'chunk_id', ...)"

**Cause:** Your dict doesn't have a recognized ID field.

**Fix:**
```python
# Add id field to your results
results = [
    {"id": "chunk_1", "content": "...", "score": 0.9},  # ✅
]
# Or use chunk_id, doc_id, content_hash
```

### Results don't look right / Unexpected ordering

**Debug with explain mode:**
```python
result = reciprocal_rank_fusion(ranked_lists, explain=True)

for item in result.items[:5]:
    exp = result.explanations[item["id"]]
    print(f"{item['id']}: score={item['rrf_score']:.4f}")
    for c in exp.sources:
        print(f"  {c.source}: rank={c.rank}, contribution={c.weighted_score:.4f}")
```

### All results have similar scores

**Likely causes:**
1. k value too high (try k=60 instead of k=100)
2. Lists have very different number of items
3. Weights are too uniform

**Solution:**
```python
# Try lower k or add weights
result = reciprocal_rank_fusion(
    ranked_lists,
    k=30,  # Lower k
    weights={"vector": 1.5, "keyword": 1.0},  # Differentiate sources
)
```

## Performance

| Size | Latency | Notes |
|------|---------|-------|
| 100 items total | <1 ms | Fast, negligible |
| 1,000 items total | ~2 ms | Typical RAG case |
| 10,000 items total | ~15 ms | Large case, still acceptable |

**Complexity:** O(n log n) where n = total items across all sources

## References

- **Paper:** Cormack, Clarke & Buettcher (2009). "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods"
- **Elasticsearch RRF:** https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html
- **Weaviate Hybrid:** https://weaviate.io/blog/what-is-rrf
- **Microsoft GraphRAG:** Uses RRF for community + entity + chunk fusion

---

**Last Updated**: 2026-04-02
**Maintainer**: Agentic Brain Team

