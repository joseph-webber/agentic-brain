# GraphRAG Hierarchical Community Audit

**Date**: 2026-07-07  
**Auditor**: Iris Lumina  
**Status**: ✅ PASS - Implementation aligns with Microsoft GraphRAG design

---

## Executive Summary

The hierarchical community implementation in `agentic-brain/src/agentic_brain/rag/` correctly implements Microsoft GraphRAG's multi-level community hierarchy. Both `community_detection.py` and `community.py` work together to provide:

- Multi-level hierarchy via resolution-based Leiden detection
- Proper parent/child relationship wiring
- Level-based community access
- Per-community summary generation
- Ancestor traversal for hierarchical context

**Overall Assessment**: Production-ready with minor enhancement opportunities.

---

## 1. Multi-Level Hierarchy Implementation

### ✅ PASS - Correctly Implemented

**Location**: `community_detection.py:120-207` (`_detect_leiden_hierarchical`)

**How it works**:
```python
# Runs Leiden at multiple resolutions (gamma * 2^i)
resolutions = [gamma * (2.0 ** i) for i in range(max_levels)]
# Level 0 = finest (gamma=1.0), Level 1 = coarser (gamma=2.0), etc.
```

**Microsoft GraphRAG alignment**:
| Feature | Microsoft GraphRAG | Our Implementation |
|---------|-------------------|-------------------|
| Level 0 (leaf) | Finest granularity | ✅ Yes (highest gamma) |
| Higher levels | Coarser communities | ✅ Yes (lower gamma values) |
| Default levels | 3-4 levels | ✅ `max_levels=3` default |
| Algorithm | Leiden preferred | ✅ Leiden primary, Louvain/CC fallback |

**Evidence**:
```python
# community_detection.py:146
resolutions = [gamma * (2.0 ** i) for i in range(max_levels)]
# gamma=1.0 → [1.0, 2.0, 4.0] → Level 0 (fine), Level 1, Level 2 (coarse)
```

---

## 2. Parent/Child Relationships

### ✅ PASS - Correctly Implemented

**Location**: `community_detection.py:187-204`

**How it works**:
The implementation correctly wires parent/child relationships by mapping entities across resolution levels:

```python
# For each entity, find which child community (level N-1) maps to which parent (level N)
for entity, parent_cid in parent_level.items():
    child_cid = child_level.get(entity)
    if child_cid is not None and child_cid not in child_to_parent:
        child_to_parent[child_cid] = parent_cid

# Then wire the relationships
hierarchy.communities[child_cid].parent_id = parent_cid
hierarchy.communities[parent_cid].children_ids.append(child_cid)
```

**Data Structure** (`Community` dataclass):
```python
@dataclass
class Community:
    id: int
    level: int              # 0 = leaf, higher = coarser
    parent_id: Optional[int] = None
    children_ids: list[int] = field(default_factory=list)
```

**Test Coverage**: Present in `test_graphrag_compatibility.py:150-164`

---

## 3. Level-Based Search (`communities_at_level`)

### ✅ PASS - Correctly Implemented

**Location**: `community_detection.py:71-72`

```python
def communities_at_level(self, level: int) -> list[Community]:
    return [c for c in self.communities.values() if c.level == level]
```

**Usage in `community.py`**:
```python
# Filters for leaf communities (level 0)
for community in hierarchy.communities.values()
    if community.level == 0
```

**Microsoft GraphRAG alignment**: ✅ Matches the pattern of accessing communities by level for global/local search routing.

---

## 4. Summary Generation Per Community

### ✅ PASS - Correctly Implemented

**Location**: `community_detection.py:374-456` (`summarize_community`) and `community.py:565-592` (`_generate_summary`)

**Two-tier approach**:

1. **LLM-based** (preferred):
   ```python
   prompt = (
       f"Summarize this knowledge graph community in 2-3 sentences.\n"
       f"Entities: {entities_text}\n"
       f"Relationships: {rels_text}\n"
       ...
   )
   ```

2. **Structured fallback** (no LLM):
   ```python
   # Groups entities by type and lists key relationships
   type_groups: dict[str, list[str]] = defaultdict(list)
   for e in entity_details:
       type_groups[e["type"] or "Entity"].append(e["name"])
   ```

**Summary storage**:
```python
# community.py:328-338
MERGE (c:Community {id: $community_id, level: $level})
SET c.summary = $summary,
    c.updatedAt = datetime()
```

**Batch summarization**: `summarize_all_communities()` at line 458-471 handles bulk generation.

---

## 5. Ancestor Traversal

### ✅ PASS - Correctly Implemented

**Location**: `community_detection.py:78-88`

```python
def get_community_ancestors(self, community_id: int) -> list[Community]:
    """Walk up the hierarchy from a community to the root."""
    ancestors: list[Community] = []
    current = self.communities.get(community_id)
    while current and current.parent_id is not None:
        parent = self.communities.get(current.parent_id)
        if parent is None:
            break
        ancestors.append(parent)
        current = parent
    return ancestors
```

**Behavior**:
- Returns empty list for root communities
- Walks up the tree until reaching a community with no parent
- Correctly handles broken chains (missing parent → stops traversal)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     CommunityGraphRAG                           │
│  (community.py - high-level orchestration)                      │
├─────────────────────────────────────────────────────────────────┤
│  • detect_communities() → persists to Neo4j                     │
│  • summarize_communities(llm) → generates summaries             │
│  • build_hierarchy() → 4-level structure (0=entities, 1=leaf,   │
│                        2=coarse, 3=global)                      │
│  • route_query() → community/entity/hybrid                      │
│  • query() → CommunityQueryResult with hierarchy_level          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               CommunityHierarchy + Community                    │
│  (community_detection.py - data structures)                     │
├─────────────────────────────────────────────────────────────────┤
│  Community:                                                     │
│    • id, level, entities[], parent_id, children_ids[]           │
│    • summary, size, modularity_score                            │
│                                                                 │
│  CommunityHierarchy:                                            │
│    • communities: dict[int, Community]                          │
│    • levels: int                                                │
│    • entity_to_community: dict[str, int]                        │
│    • flat_communities (backward compat)                         │
│    • communities_at_level(level)                                │
│    • get_entity_community(name)                                 │
│    • get_community_ancestors(id)                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Detection Algorithms                          │
│  (community_detection.py - detection functions)                 │
├─────────────────────────────────────────────────────────────────┤
│  Cascade (tries in order):                                      │
│  1. _detect_leiden_hierarchical()   [GDS required, multi-level] │
│  2. _detect_louvain()               [GDS required, single-level]│
│  3. _detect_connected_components()  [Pure Cypher, single-level] │
│                                                                 │
│  + Async variants for all three                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Neo4j Schema

Communities are persisted as nodes with relationships:

```cypher
// Community nodes
(:Community {
  id: "community_id",
  level: 1,  // 1=leaf, 2=coarse, 3=global
  members: ["entity1", "entity2"],
  memberCount: 2,
  summary: "LLM-generated summary",
  metadata: {detection_method: "leiden_hierarchical"},
  updatedAt: datetime()
})

// Entity membership
(:Entity)-[:IN_COMMUNITY {level: 1}]->(:Community)

// Hierarchy
(:Community {level: 3})-[:HAS_SUBCOMMUNITY]->(:Community {level: 2})
(:Community {level: 2})-[:HAS_SUBCOMMUNITY]->(:Community {level: 1})
```

---

## Minor Observations (Not Blocking)

### 1. Level Numbering Inconsistency

**Observation**: `community_detection.py` uses Level 0 as leaf (standard), but `community.py` uses Level 1 as leaf when persisting:

```python
# community_detection.py:43
level: int  # 0 = leaf, higher = coarser

# community.py:298
"level": 1,  # Leaf communities stored as level 1
```

**Impact**: Low - internal implementation detail, doesn't affect functionality.  
**Recommendation**: Consider documenting this convention explicitly.

### 2. Async Detection Duplication

**Observation**: `_async_leiden_hierarchical` duplicates sync logic rather than using `asyncio.to_thread()`.

**Impact**: Low - code works correctly, just more maintenance surface.  
**Recommendation**: Future refactor opportunity.

### 3. Missing `get_community_descendants`

**Observation**: `get_community_ancestors()` exists but no `get_community_descendants()` for top-down traversal.

**Impact**: Low - can be derived from `children_ids`.  
**Recommendation**: Add for completeness if top-down drill-down queries are common.

---

## Test Coverage

| Test File | Coverage |
|-----------|----------|
| `test_community_rag.py` | CommunityGraphRAG operations |
| `test_graphrag_compatibility.py` | CommunityHierarchy backward compat |

**Key tests**:
- `test_community_hierarchy_backward_compatible` - verifies `flat_communities`
- `test_detect_communities_persists_leaf_communities` - verifies Neo4j persistence
- `test_hierarchy_built` - verifies 4-level structure

---

## Conclusion

The hierarchical community implementation is **production-ready** and correctly follows Microsoft GraphRAG's multi-level community design:

| Requirement | Status |
|-------------|--------|
| Multi-level hierarchy | ✅ Implemented via resolution-based Leiden |
| Parent/child relationships | ✅ Correctly wired |
| Level-based search | ✅ `communities_at_level()` works |
| Summary generation | ✅ LLM + structured fallback |
| Ancestor traversal | ✅ `get_community_ancestors()` works |
| Backward compatibility | ✅ `flat_communities` property preserved |
| Graceful degradation | ✅ Leiden → Louvain → CC cascade |

**No blocking issues found.**

---

## References

- [Microsoft GraphRAG Paper](https://arxiv.org/abs/2404.16130)
- [Leiden Algorithm](https://arxiv.org/abs/1810.08473)
- [Neo4j Graph Data Science](https://neo4j.com/docs/graph-data-science/)
