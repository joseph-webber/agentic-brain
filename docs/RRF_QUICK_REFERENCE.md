# RRF (Reciprocal Rank Fusion) Quick Reference

## What is RRF?

RRF combines multiple ranked result lists into a single fused ranking. It's ideal for hybrid search where you have results from different sources (vector search, graph search, keyword search) and want to find items that are highly relevant across multiple signals.

**Formula:** `RRF_score = Σ 1/(k + rank)` for each list

**Key property:** Items that appear in multiple lists get boosted because their scores accumulate.

## Using RRF in Agentic-Brain

### Module-Level Function (Main API)

```python
from agentic_brain.rag.hybrid import reciprocal_rank_fusion

# Perform searches (returns list of dicts with 'id' field)
vector_results = [
    {"id": "chunk_a", "content": "...", "score": 0.95},
    {"id": "chunk_b", "content": "...", "score": 0.85},
]

graph_results = [
    {"id": "chunk_b", "content": "...", "entities": ["Entity"]},
    {"id": "chunk_c", "content": "...", "graph_score": 0.75},
]

keyword_results = [
    {"id": "chunk_a", "content": "...", "bm25_score": 150},
]

# Fuse with RRF
fused = reciprocal_rank_fusion(
    vector_results=vector_results,
    graph_results=graph_results,
    keyword_results=keyword_results,
    k=60  # Standard value, adjust if needed
)

# Results are sorted by RRF score, highest first
for item in fused:
    print(f"{item['id']}: RRF={item['rrf_score']:.4f}")
    # Output:
    # chunk_b: RRF=0.0325 (appears in vector and graph - consensus!)
    # chunk_a: RRF=0.0164 (vector and keyword)
    # chunk_c: RRF=0.0161 (graph only)
```

### Class Method (Internal Use)

For internal hybrid search pipelines using `RetrievedChunk` objects:

```python
from agentic_brain.rag.hybrid import HybridSearch
from agentic_brain.rag.retriever import RetrievedChunk

search = HybridSearch()

vector_chunks = [
    RetrievedChunk(content="...", source="doc1.pdf", score=0.95),
    RetrievedChunk(content="...", source="doc2.pdf", score=0.85),
]

keyword_chunks = [
    RetrievedChunk(content="...", source="doc1.pdf", score=0.75),
]

# Hybrid search automatically fuses with RRF
result = search.search(
    query="your query",
    chunks=all_chunks,
    k=5,
    fusion_method="rrf"  # or "linear"
)

# Access fused results
for chunk in result.fused_results:
    print(f"{chunk.source}: score={chunk.score:.4f}")
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

## Understanding Results

### Scoring

Each result item includes:
- `id`: Unique identifier
- `rrf_score`: Fusion score (sum of 1/(k+rank) from each list)
- All fields from all source lists (merged)

### Ranking

Results are sorted by `rrf_score` in descending order:
- Higher score = better consensus/ranking
- Items in multiple lists score higher
- Items only in one list score lower

### Example

```python
# Vector search result:
{"id": "a", "rank": 1}  # Score: 1/(60+0+1) = 0.0164

# Graph search result:
{"id": "a", "rank": 1}  # Score: 1/(60+0+1) = 0.0164

# Fused result:
{"id": "a", "rrf_score": 0.0328}  # Sum of both: 0.0328
```

## Common Patterns

### Fusion with Optional Third List

```python
# Always have vector and graph
fused = reciprocal_rank_fusion(
    vector_results=vec_results,
    graph_results=graph_results,
    keyword_results=kw_results if kw_results else None,
    k=60
)
```

### Getting Top-K Results

```python
fused = reciprocal_rank_fusion(vector, graph, keyword, k=60)
top_5 = fused[:5]  # First 5 results (already sorted)
```

### Filtering by Score Threshold

```python
fused = reciprocal_rank_fusion(vector, graph, keyword, k=60)
confident = [r for r in fused if r['rrf_score'] > 0.02]
```

## Performance Notes

| Size | Latency | Notes |
|------|---------|-------|
| 100 items total | 0.24 ms | Fast, negligible |
| 1,000 items total | 1.1 ms | Typical RAG case |
| 10,000 items total | 11 ms | Large case, still acceptable |

For most RAG applications, RRF fusion takes <2ms.

## Troubleshooting

### Error: "RRF result item must include 'id' or 'chunk_id'"

**Cause:** Your dict doesn't have an `id` or `chunk_id` field.

**Fix:**
```python
# Add id field to your results
results = [
    {"id": "chunk_1", "content": "...", "score": 0.9},
]
```

### Results don't look right / Unexpected ordering

**Common causes:**
1. Items from different lists aren't being matched (different id format)
2. k value too low/high
3. Rank positions are wrong (should be 0, 1, 2, ...)

**Debug:**
```python
# Print intermediate scores
for rank, item in enumerate(vector_results):
    contribution = 1.0 / (60 + rank + 1)
    print(f"Vector rank {rank}: {item['id']} contributes {contribution:.4f}")
```

### All results have similar scores

**Likely causes:**
1. k value too high (try k=60 instead of k=100)
2. Lists have very different number of items

**Solution:**
```python
# Try adjusting k
fused = reciprocal_rank_fusion(vector, graph, keyword, k=30)  # Lower k
```

## Algorithm Details

### What RRF Does Well

✅ **Combines diverse signals:** Vector search (semantic), graph (structural), keyword (lexical)

✅ **Rewards consensus:** Items that rank well in multiple sources get highest scores

✅ **Fair to all sources:** Each source contributes equally to the formula (doesn't privilege vector over keyword)

✅ **Simple and efficient:** O(n log n) complexity, sub-millisecond latency

### What RRF Doesn't Do

❌ **Weight different sources:** All sources treated equally (use linear fusion with weights if needed)

❌ **Rerank based on query:** Just combines existing rankings

❌ **Deduplicate:** Same item in multiple lists contributes multiple times

## Comparison: RRF vs Linear Fusion

### RRF (Current Implementation)
```python
score = Σ 1/(k + rank)  # Exponential emphasis on top results
```
- Emphasizes consensus strongly
- Items in multiple lists score much higher
- More appropriate for truly diverse signals

### Linear Fusion
```python
score = vector_weight * vec_score + keyword_weight * kw_score
```
- Allows tuning relative importance of each source
- More gradual ranking
- Requires manual weight tuning

## References

- **Elasticsearch:** https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html
- **Weaviate:** https://weaviate.io/blog/what-is-rrf
- **Papers:** "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods"

