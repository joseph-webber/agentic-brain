# RRF Implementation Roadmap

## Overview

This document outlines the required and recommended fixes to the RRF implementation in agentic-brain, identified during the comprehensive audit.

**Status:** Ready for implementation (CRITICAL fixes identified)  
**Priority:** HIGH - affects hybrid search quality in GraphRAG  
**Effort:** 4-6 hours total  

---

## Critical Fix: Unify Dual RRF Implementations

### Problem Statement

Two incompatible RRF implementations exist:

1. **Module-level:** `reciprocal_rank_fusion()` (dict-based, supports 3 lists)
2. **Class method:** `HybridSearch._reciprocal_rank_fusion()` (RetrievedChunk-based, supports 2 lists)

This creates:
- API inconsistency
- Maintenance burden
- Potential for divergent behavior
- Confusion for developers

### Proposed Solution

**Consolidate into single implementation** at module level, with class method as thin wrapper.

### Implementation Steps

#### Step 1: Enhance Module-Level Function

**File:** `src/agentic_brain/rag/hybrid.py:55-90`

**Change:** Add optional `preserve_source_scores` parameter and improve error handling

```python
import logging

logger = logging.getLogger(__name__)

def reciprocal_rank_fusion(
    vector_results: list[dict[str, Any]],
    graph_results: list[dict[str, Any]],
    keyword_results: Optional[list[dict[str, Any]]] = None,
    k: int = 60,
    preserve_source_scores: bool = True,  # NEW
) -> list[dict[str, Any]]:
    """
    Combine multiple ranked lists using Reciprocal Rank Fusion.

    RRF combines results from different ranking signals (vector search, graph search,
    keyword search) by computing a fusion score for each item based on its rank in
    each list. Items that appear in multiple lists get higher scores (consensus boost).

    Formula: RRF_score = Σ 1 / (k + rank) for each list where item appears

    Args:
        vector_results: Results from vector/semantic search (required)
        graph_results: Results from graph/structural search (required)
        keyword_results: Results from keyword/BM25 search (optional)
        k: Rank offset parameter (default 60, industry standard)
           Larger k → more uniform distribution
           Smaller k → emphasizes top results more
        preserve_source_scores: If True, track original scores from each source
                                separately to avoid metadata conflicts

    Returns:
        List of dicts sorted by rrf_score (highest first), with fields:
        - id: Item identifier
        - rrf_score: Computed RRF score (float)
        - All fields from source dicts (merged)
        - _source_scores: Dict mapping source name to original score (if preserve_source_scores=True)

    Raises:
        KeyError: If any item lacks 'id' or 'chunk_id' field
        ValueError: If k <= 0 or not an integer

    Example:
        >>> vector = [{"id": "a", "score": 0.95}, {"id": "b", "score": 0.85}]
        >>> graph = [{"id": "b", "score": 0.75}, {"id": "c", "score": 0.65}]
        >>> fused = reciprocal_rank_fusion(vector, graph, k=60)
        >>> fused[0]["id"]  # Will be "b" (appears in both lists)
        'b'
    """
    # INPUT VALIDATION
    if not isinstance(k, int) or k <= 0:
        raise ValueError(f"k must be a positive integer, got {k}")
    
    if not isinstance(vector_results, list):
        raise TypeError(f"vector_results must be list, got {type(vector_results)}")
    
    if not isinstance(graph_results, list):
        raise TypeError(f"graph_results must be list, got {type(graph_results)}")
    
    # WARNINGS FOR UNUSUAL VALUES
    if k < 10:
        logger.warning(f"Unusual k={k}: Small values emphasize top results more. "
                      f"Consider k=60 (default) for balanced ranking.")
    
    if k > 1000:
        logger.warning(f"Large k={k}: May under-weight rank differences. "
                      f"Typical range is 10-100.")
    
    # DEBUG LOGGING
    logger.debug(f"RRF fusion: {len(vector_results)} vector, {len(graph_results)} graph, "
                 f"{len(keyword_results or [])} keyword results, k={k}, "
                 f"preserve_scores={preserve_source_scores}")
    
    # BUILD RANKED LISTS
    ranked_lists = [
        ("vector", vector_results),
        ("graph", graph_results),
    ]
    if keyword_results:
        ranked_lists.append(("keyword", keyword_results))
    
    # PROCESS RESULTS
    scores: dict[str, float] = {}
    merged_items: dict[str, dict[str, Any]] = {}
    source_scores: dict[str, dict[str, float]] = {} if preserve_source_scores else None
    
    for source_name, results in ranked_lists:
        for rank, item in enumerate(results):
            item_id = _get_result_id(item)
            
            # PRESERVE SOURCE SCORES
            if preserve_source_scores:
                if item_id not in source_scores:
                    source_scores[item_id] = {}
                source_scores[item_id][source_name] = item.get("score")
            
            # MERGE ITEMS
            if item_id not in merged_items:
                merged_items[item_id] = {}
            
            # Store source metadata separately to avoid overwriting
            if "_source_metadata" not in merged_items[item_id]:
                merged_items[item_id]["_source_metadata"] = {}
            
            merged_items[item_id]["_source_metadata"][source_name] = {
                k: v for k, v in item.items() 
                if k not in ("id", "chunk_id")
            }
            
            # Merge all fields into main item (preserves all metadata)
            for key, value in item.items():
                if key not in ("id", "chunk_id", "_source_metadata"):
                    if key not in merged_items[item_id]:
                        merged_items[item_id][key] = value
            
            # COMPUTE RRF SCORE
            rrf_contribution = 1.0 / (k + rank + 1)
            scores[item_id] = scores.get(item_id, 0.0) + rrf_contribution
            
            logger.debug(f"  {source_name:8s} rank {rank}: {item_id} +{rrf_contribution:.6f}")
    
    # SORT BY RRF SCORE
    sorted_ids = sorted(
        scores.keys(), key=lambda item_id: scores[item_id], reverse=True
    )
    
    # BUILD RESULTS
    results = []
    for item_id in sorted_ids:
        result = {
            **merged_items[item_id],
            "id": item_id,
            "rrf_score": scores[item_id],
        }
        
        if preserve_source_scores:
            result["_source_scores"] = source_scores.get(item_id, {})
        
        results.append(result)
    
    logger.debug(f"RRF returned {len(results)} items")
    
    return results
```

#### Step 2: Update Class Method to Use Module Function

**File:** `src/agentic_brain/rag/hybrid.py:394-438`

**Change:** Refactor to convert RetrievedChunk ↔ dict

```python
def _reciprocal_rank_fusion(
    self,
    vector_results: list[RetrievedChunk],
    keyword_results: list[RetrievedChunk],
    k: int,
    k_rrf: int = 60,
) -> list[RetrievedChunk]:
    """
    Combine results using Reciprocal Rank Fusion.
    
    Now delegates to the unified module-level reciprocal_rank_fusion()
    for consistent behavior.
    """
    # Convert RetrievedChunk to dicts for module function
    vector_dicts = [
        {
            "id": f"{hash((c.content, c.source))}",
            "content": c.content,
            "source": c.source,
            "score": c.score,
            "metadata": c.metadata,
            "_chunk": c,  # Keep original
        }
        for c in vector_results
    ]
    
    keyword_dicts = [
        {
            "id": f"{hash((c.content, c.source))}",
            "content": c.content,
            "source": c.source,
            "score": c.score,
            "metadata": c.metadata,
            "_chunk": c,  # Keep original
        }
        for c in keyword_results
    ]
    
    # Call unified function
    fused_dicts = reciprocal_rank_fusion(
        vector_dicts,
        keyword_dicts,
        keyword_results=None,  # Only 2 lists
        k=k_rrf,
        preserve_source_scores=True
    )
    
    # Convert back to RetrievedChunk
    fused_chunks = []
    for fused_dict in fused_dicts:
        # Try to recover original chunk
        original_chunk = fused_dict.get("_chunk")
        
        if original_chunk:
            # Use original, just update score
            fused_chunk = RetrievedChunk(
                content=original_chunk.content,
                source=original_chunk.source,
                score=fused_dict["rrf_score"],
                metadata={
                    **original_chunk.metadata,
                    "fusion_method": "rrf",
                    "rrf_score": fused_dict["rrf_score"],
                    "_source_scores": fused_dict.get("_source_scores", {}),
                }
            )
        else:
            # Construct new chunk
            fused_chunk = RetrievedChunk(
                content=fused_dict.get("content", ""),
                source=fused_dict.get("source", ""),
                score=fused_dict["rrf_score"],
                metadata={
                    "fusion_method": "rrf",
                    "rrf_score": fused_dict["rrf_score"],
                    "_source_scores": fused_dict.get("_source_scores", {}),
                }
            )
        
        fused_chunks.append(fused_chunk)
    
    return fused_chunks
```

#### Step 3: Write Integration Tests

**File:** `tests/test_rag_advanced.py` (add to TestHybridSearch)

```python
def test_rrf_module_and_class_consistency(self, sample_chunks):
    """
    Verify that module-level and class-method RRF produce equivalent results.
    This ensures the consolidation maintains backward compatibility.
    """
    from agentic_brain.rag.hybrid import reciprocal_rank_fusion
    
    # Module-level function
    vector_dicts = [{"id": c.source, "content": c.content} for c in sample_chunks[:2]]
    graph_dicts = [{"id": c.source, "content": c.content} for c in sample_chunks[1:]]
    
    module_result = reciprocal_rank_fusion(vector_dicts, graph_dicts, k=60)
    
    # Class method
    search = HybridSearch()
    class_result = search._reciprocal_rank_fusion(sample_chunks[:2], sample_chunks[1:], k=60)
    
    # Verify consistency: same ranking
    module_ids = [r["id"] for r in module_result]
    class_ids = [c.source for c in class_result]
    
    assert module_ids == class_ids, "Module and class RRF produce different rankings"
    
    # Verify scores are close (accounting for small floating point differences)
    for mod_res, cls_res in zip(module_result, class_result):
        assert abs(mod_res["rrf_score"] - cls_res.score) < 1e-10, \
            f"Score mismatch: {mod_res['rrf_score']} vs {cls_res.score}"


def test_rrf_source_score_preservation(self):
    """Verify source scores are preserved separately."""
    from agentic_brain.rag.hybrid import reciprocal_rank_fusion
    
    vector = [{"id": "a", "score": 0.95, "source": "vec"}]
    graph = [{"id": "a", "score": 0.85, "source": "graph"}]
    
    result = reciprocal_rank_fusion(vector, graph, preserve_source_scores=True)
    
    # Should have source scores stored separately
    assert "_source_scores" in result[0], "Source scores not preserved"
    assert result[0]["_source_scores"]["vector"] == 0.95
    assert result[0]["_source_scores"]["graph"] == 0.85
    
    # Original score should not be overwritten
    # (Both 0.95 and 0.85 preserved, not last-write-wins)
```

---

## High Priority: Improve Error Handling

### Issue

Missing parameter validation and warnings for unusual values.

### Solution

Add to `reciprocal_rank_fusion()`:

```python
# At start of function
if not isinstance(k, int) or k <= 0:
    raise ValueError(f"k must be a positive integer, got {k}")

if not isinstance(vector_results, list):
    raise TypeError(f"vector_results must be list, got {type(vector_results)}")

if not isinstance(graph_results, list):
    raise TypeError(f"graph_results must be list, got {type(graph_results)}")

# Warnings
if k < 10:
    logger.warning(f"Small k={k} emphasizes top results more")

if k > 1000:
    logger.warning(f"Large k={k} may under-weight rank differences")
```

### Test

```python
def test_rrf_validation():
    """Test parameter validation."""
    # Should raise on invalid k
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([{"id": "a"}], [{"id": "b"}], k=-1)
    
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([{"id": "a"}], [{"id": "b"}], k=0)
    
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([{"id": "a"}], [{"id": "b"}], k=3.14)  # Not int
    
    # Should raise on wrong input type
    with pytest.raises(TypeError):
        reciprocal_rank_fusion("not a list", [{"id": "b"}])
```

---

## Medium Priority: Track Source Scores

### Issue

Original scores from vector/graph/keyword searches are lost/overwritten.

### Solution

Already included in the enhanced function above:

- `preserve_source_scores` parameter (default True)
- `_source_scores` dict tracking original scores
- `_source_metadata` dict for other source-specific fields

### Usage

```python
result = reciprocal_rank_fusion(vector, graph, keyword, preserve_source_scores=True)

for item in result:
    print(f"{item['id']}: RRF={item['rrf_score']:.4f}")
    if "_source_scores" in item:
        print(f"  Vector: {item['_source_scores'].get('vector')}")
        print(f"  Graph:  {item['_source_scores'].get('graph')}")
        print(f"  Keyword: {item['_source_scores'].get('keyword')}")
```

---

## Medium Priority: Support Flexible List Count

### Future Enhancement (Not Critical)

For supporting arbitrary number of ranked lists:

```python
def reciprocal_rank_fusion(
    ranked_lists: list[tuple[str, list[dict[str, Any]]]],
    k: int = 60,
    preserve_source_scores: bool = True,
) -> list[dict[str, Any]]:
    """
    Combine any number of ranked lists.
    
    Args:
        ranked_lists: List of (source_name, results) tuples
        k: Rank offset (default 60)
        preserve_source_scores: Track original scores
    
    Example:
        >>> vector = [{"id": "a", "score": 0.9}]
        >>> graph = [{"id": "a", "score": 0.8}]
        >>> keyword = [{"id": "a", "score": 0.7}]
        >>> reranked = [{"id": "a", "score": 0.85}]
        >>> results = reciprocal_rank_fusion([
        ...     ("vector", vector),
        ...     ("graph", graph),
        ...     ("keyword", keyword),
        ...     ("reranked", reranked),
        ... ])
    """
```

### Backward Compatibility

Keep existing signature for compatibility:

```python
def reciprocal_rank_fusion(
    vector_results,
    graph_results,
    keyword_results=None,
    k=60,
    # New signature (optional, added later)
    # ranked_lists=None,  # If provided, use this instead of above
):
    # Auto-detect which signature is being used
```

---

## Implementation Schedule

### Week 1: Critical Fix (Unify Implementations)
- [ ] Enhance module-level function with validation and logging
- [ ] Update class method to use module function
- [ ] Add integration tests
- [ ] Test with existing test suite
- [ ] Code review

**Effort:** 3 hours  
**Risk:** Medium (must maintain backward compatibility)

### Week 2: High Priority (Error Handling)
- [ ] Add parameter validation
- [ ] Add warning logs
- [ ] Write validation tests
- [ ] Update docstrings

**Effort:** 1 hour  
**Risk:** Low

### Week 3: Medium Priority (Source Scores)
- [ ] Already implemented in enhanced function
- [ ] Write comprehensive tests
- [ ] Update documentation

**Effort:** 1 hour  
**Risk:** Low

### Later: Nice to Have (Flexible Lists)
- [ ] Design flexible interface
- [ ] Maintain backward compatibility
- [ ] Add tests
- [ ] Update docs

**Effort:** 2 hours  
**Risk:** Low (additive)

---

## Testing Checklist

### Before Deployment

- [ ] All existing tests pass
- [ ] New integration tests pass
- [ ] Validation tests pass
- [ ] Performance tests still <2ms for 1000 items
- [ ] No logging noise on normal usage
- [ ] Type hints check with mypy

### Test Coverage Goals

- [ ] Line coverage: 100%
- [ ] Branch coverage: 100%
- [ ] All edge cases covered:
  - Empty lists ✓
  - Single item per list ✓
  - Duplicate IDs in same list ✓
  - Missing ID field ✓
  - k parameter edge cases ✓
  - Unicode IDs ✓
  - Metadata conflicts ✓

### Regression Testing

- [ ] All existing functionality preserved
- [ ] No performance regression
- [ ] No behavior changes (except logging)
- [ ] Backward compatible API

---

## Deployment Steps

1. **Code Review**
   - Review with team
   - Ensure design is sound
   - Check for missed edge cases

2. **Testing**
   - Run full test suite
   - Run performance benchmarks
   - Test on real data

3. **Merge to Main**
   - Create PR with full documentation
   - Require approval
   - Merge to main branch

4. **Release Notes**
   - Document changes
   - Highlight that behavior is now consistent
   - Note deprecation of private _reciprocal_rank_fusion if renaming

5. **Monitor**
   - Watch for issues
   - Monitor logs for warnings
   - Track performance metrics

---

## References

- **Audit Report:** `/Users/joe/brain/agentic-brain/docs/GRAPHRAG_RRF_AUDIT.md`
- **Quick Reference:** `/Users/joe/brain/agentic-brain/docs/RRF_QUICK_REFERENCE.md`
- **Original Tests:** `tests/test_rag_advanced.py::TestHybridSearch`
- **Implementation:** `src/agentic_brain/rag/hybrid.py`

---

**Status:** Ready for implementation  
**Last Updated:** 2026-03-28  
**Next Steps:** Schedule implementation sprint
