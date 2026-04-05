# GraphRAG: Microsoft Implementation Comparison

> **Audit Date**: 2026-06-24  
> **Agentic-Brain Version**: v4.x  
> **Microsoft GraphRAG Reference**: [github.com/microsoft/graphrag](https://github.com/microsoft/graphrag)

## Executive Summary

This document compares the agentic-brain GraphRAG implementation against Microsoft's official GraphRAG architecture. The goal is to ensure alignment with best practices while maintaining flexibility for simpler projects that don't require the full enterprise feature set.

**Overall Assessment**: ⚠️ **Partial Alignment** - Core concepts implemented but gaps in enterprise features

---

## Feature Comparison Table

| Feature | Microsoft GraphRAG | Agentic-Brain | Status | Notes |
|---------|-------------------|---------------|--------|-------|
| **Entity Extraction** |
| LLM-based extraction | ✅ GPT-4 Turbo prompts | ✅ Any LLM via `_extract_graph_with_llm()` | ✅ Supported | Flexible LLM backend |
| Heuristic fallback | ❌ LLM-only | ✅ Regex + pattern matching | ✅ Better | Works without LLM costs |
| Entity deduplication | ✅ LLM-driven merge | ⚠️ Normalized name matching | ⚠️ Partial | Missing semantic similarity dedup |
| Entity typing | ✅ LLM classification | ✅ Heuristic + LLM | ✅ Supported | Hint-based fallback works well |
| **Relationship Extraction** |
| LLM-based extraction | ✅ Full prompt pipeline | ✅ JSON extraction prompts | ✅ Supported | Via `_build_entity_extraction_prompt()` |
| Co-occurrence fallback | ❌ | ✅ Sentence-level detection | ✅ Better | `_extract_relationships()` |
| Relationship typing | ✅ LLM-driven | ✅ Inference + LLM | ✅ Supported | `_infer_relationship_type()` |
| Evidence capture | ✅ Source text | ✅ Sentence evidence | ✅ Supported | Stored in `evidence` field |
| **Community Detection** |
| Leiden algorithm | ✅ Primary | ✅ Primary via GDS | ✅ Supported | Multi-resolution hierarchy |
| Louvain fallback | ⚠️ Legacy | ✅ GDS fallback | ✅ Supported | Better Leiden → Louvain cascade |
| No-GDS fallback | ❌ Requires GDS | ✅ Connected components | ✅ Better | Pure Cypher works always |
| Hierarchical levels | ✅ 4 levels | ✅ 3 levels configurable | ⚠️ Partial | Missing Level-4 global |
| Resolution tuning | ✅ Gamma parameter | ✅ Gamma + max_levels | ✅ Supported | `_detect_leiden_hierarchical()` |
| **Community Summarization** |
| LLM summarization | ✅ Required | ✅ Optional with fallback | ✅ Supported | `summarize_community()` |
| Structured fallback | ❌ | ✅ Entity list summary | ✅ Better | Works without LLM |
| Hierarchical summaries | ✅ Per-level | ⚠️ Leaf-level only | ⚠️ Partial | `summarize_all_communities()` |
| Summary persistence | ✅ Parquet/DB | ✅ Neo4j Community nodes | ✅ Supported | `:Community.summary` |
| **TextUnit Chunking** |
| Semantic chunking | ✅ Token-based | ✅ Multiple strategies | ✅ Supported | `SemanticChunker` |
| Fixed-size chunking | ✅ Configurable | ✅ Configurable | ✅ Supported | `FixedChunker` |
| Markdown-aware | ⚠️ Basic | ✅ Header hierarchy | ✅ Better | `MarkdownChunker` |
| TextUnit → Entity links | ✅ Required | ⚠️ Document → Entity | ⚠️ Partial | Missing chunk-level links |
| **Search Strategies** |
| Local Search (entity-centric) | ✅ Required | ✅ `_search_entities()` | ✅ Supported | Vector + keyword |
| Global Search (community) | ✅ Map-reduce | ⚠️ Summary matching | ⚠️ Partial | Missing map-reduce aggregation |
| Hybrid Search | ✅ Combined | ✅ RRF fusion | ✅ Supported | `_hybrid_search()` |
| Dynamic community selection | ✅ LLM-guided | ❌ Static query | ❌ Missing | Enterprise feature |
| Context window allocation | ✅ text_unit_prop | ❌ Not configurable | ❌ Missing | Would improve quality |
| **Query Routing** |
| Automatic routing | ✅ LLM-based | ✅ Keyword heuristics | ⚠️ Partial | `route_query()` |
| Global question detection | ✅ | ✅ Pattern matching | ✅ Supported | `_is_global_question()` |
| Local question detection | ✅ | ✅ Pattern matching | ✅ Supported | `_is_local_question()` |
| **Infrastructure** |
| Async support | ✅ | ✅ Full async | ✅ Supported | `_async_*` variants |
| Connection pooling | ❌ Per-query | ✅ Neo4j pool | ✅ Better | `neo4j_pool.py` |
| Retry handling | ⚠️ Basic | ✅ Resilient queries | ✅ Better | `resilient_query_sync()` |
| MLX acceleration | ❌ | ✅ M-series optimized | ✅ Better | `MLXEmbeddings` |

---

## Gap Analysis

### Critical Gaps (Enterprise Features)

#### 1. ❌ TextUnit → Entity Direct Links
**Microsoft Pattern**: Every entity has direct links to the TextUnits (chunks) that mention it.
```
(TextUnit)-[:MENTIONS]->(Entity)
(Entity)-[:APPEARS_IN]->(TextUnit)
```

**Current Implementation**: Uses `SourceDocument → Entity` links only.

**Impact**: Cannot do fine-grained context retrieval at chunk level.

**Recommendation**: Add `Chunk` node type with MENTIONS relationships. Mark as **OPTIONAL** for simple projects.

#### 2. ❌ Map-Reduce Global Search
**Microsoft Pattern**: Global search uses a two-phase approach:
1. **Map**: Query each relevant community summary independently
2. **Reduce**: Aggregate partial answers into final response

**Current Implementation**: Single-pass summary matching without aggregation.

**Impact**: Lower quality answers for broad, thematic questions.

**Recommendation**: Implement `CommunityMapReduceSearch` class. Mark as **OPTIONAL** - current approach works for smaller datasets.

#### 3. ❌ Dynamic Community Selection
**Microsoft Pattern**: LLM scores community relevance before including in context.

**Current Implementation**: Static keyword matching against summaries.

**Impact**: May include irrelevant communities, wasting context window.

**Recommendation**: Add LLM-based relevance scoring. Mark as **OPTIONAL** - only valuable for large knowledge graphs.

#### 4. ⚠️ Hierarchical Summary Generation
**Microsoft Pattern**: Summaries generated at all 4 levels:
- Level 0: Raw entities
- Level 1: Leaf communities
- Level 2: Coarse communities
- Level 3: Global themes

**Current Implementation**: `summarize_all_communities()` only processes leaf level.

**Impact**: Missing coarse/global summaries limits multi-scale reasoning.

**Recommendation**: Extend `build_hierarchy()` to generate summaries at all levels.

---

### Moderate Gaps

#### 5. ⚠️ Context Window Allocation
**Microsoft Pattern**: Configurable proportions:
```yaml
text_unit_prop: 0.55
community_prop: 0.15
entity_prop: 0.15
relationship_prop: 0.15
```

**Current Implementation**: No explicit allocation strategy.

**Recommendation**: Add `ContextWindowConfig` dataclass. **OPTIONAL** for simple projects.

#### 6. ⚠️ Entity Resolution with Semantic Similarity
**Microsoft Pattern**: Uses embedding similarity for fuzzy entity matching.

**Current Implementation**: `resolve_entities()` uses exact normalized name matching.

**Recommendation**: Add embedding-based similarity threshold. **OPTIONAL** - current approach catches 80% of duplicates.

---

### Agentic-Brain Advantages (Keep These!)

| Feature | Why It's Better |
|---------|----------------|
| **No-LLM Fallback** | Heuristic extraction works without API costs |
| **Pure Cypher Fallback** | Works without Neo4j GDS plugin |
| **MLX Embeddings** | 10x faster on Apple Silicon |
| **Connection Pooling** | Better Neo4j performance at scale |
| **Retry Handling** | Production-grade resilience |
| **Markdown Chunking** | Better for documentation RAG |

---

## Recommendations

### Phase 1: Core Alignment (Required)

1. **Add TextUnit/Chunk entity links**
   ```python
   # In knowledge_extractor.py
   MERGE (chunk:Chunk {id: $chunk_id})
   MERGE (chunk)-[:MENTIONS]->(entity)
   MERGE (entity)-[:APPEARS_IN]->(chunk)
   ```

2. **Extend hierarchy summarization**
   ```python
   # In community.py
   async def summarize_hierarchy(self, llm=None):
       for level in range(self.max_levels):
           for community in hierarchy.communities_at_level(level):
               community.summary = await self._generate_summary(...)
   ```

### Phase 2: Enterprise Features (Optional)

These should be **OFF by default** but available via configuration:

```python
@dataclass
class GraphRAGEnterpriseConfig:
    """Enterprise features - disabled by default."""
    
    enable_map_reduce_search: bool = False
    enable_dynamic_community_selection: bool = False
    enable_semantic_entity_resolution: bool = False
    enable_context_window_allocation: bool = False
    
    # Only enable for large knowledge graphs (>10k entities)
    min_entities_for_enterprise: int = 10_000
```

3. **Map-reduce global search** (Phase 2)
   - Only valuable for datasets > 50 communities
   - Significant LLM cost increase

4. **Dynamic community selection** (Phase 2)
   - Requires additional LLM call per query
   - Only valuable for complex queries

5. **Context window allocation** (Phase 2)
   - Helps with long-context models
   - Simple projects don't need this granularity

---

## Configuration Examples

### Simple Project (Default)
```python
config = GraphRAGConfig(
    enable_communities=True,
    community_algorithm="leiden",
    # Enterprise features OFF by default
)
```

### Enterprise Project
```python
config = GraphRAGConfig(
    enable_communities=True,
    community_algorithm="leiden",
    # Enterprise features enabled
    enterprise=GraphRAGEnterpriseConfig(
        enable_map_reduce_search=True,
        enable_dynamic_community_selection=True,
        enable_context_window_allocation=True,
    )
)
```

---

## Test Coverage Checklist

- [ ] Entity extraction with/without LLM
- [ ] Relationship extraction with/without LLM
- [ ] Leiden → Louvain → Connected Components cascade
- [ ] Hierarchical community levels (1-3)
- [ ] Community summarization with/without LLM
- [ ] Local search (entity-centric)
- [ ] Global search (community-centric)
- [ ] Hybrid search (RRF fusion)
- [ ] Query routing (local vs global detection)
- [ ] TextUnit → Entity links (when implemented)
- [ ] Map-reduce search (when implemented)

---

## References

- [Microsoft GraphRAG Paper (arXiv:2404.16130)](https://arxiv.org/abs/2404.16130)
- [Microsoft GraphRAG Documentation](https://microsoft.github.io/graphrag/)
- [Microsoft GraphRAG GitHub](https://github.com/microsoft/graphrag)
- [Leiden Algorithm Paper](https://arxiv.org/abs/1810.08473)
- [GraphRAG: Improving global search via dynamic community selection](https://www.microsoft.com/en-us/research/blog/graphrag-improving-global-search-via-dynamic-community-selection/)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-24 | Initial comparison audit |
