# Session/Memory Implementation Audit

**Date**: 2026-06-04  
**Requested by**: Arraz2000 (Joseph's brother)  
**Auditor**: Iris Lumina 💜

---

## Executive Summary

Joseph's brain has **FIVE distinct session/memory systems** across repositories. This represents significant duplication, but each serves different purposes. This audit identifies consolidation opportunities while preserving critical functionality.

### TL;DR Recommendation
**Keep 2 systems, deprecate 3:**
1. ✅ **KEEP**: `agentic-brain/memory/unified.py` → Canonical implementation
2. ✅ **KEEP**: `openviking-explore/session/` → Enterprise features (but use as plugin)
3. 🚫 **DEPRECATE**: `core/hooks/ultimate_memory_hooks.py` → Merge into unified.py
4. 🚫 **DEPRECATE**: `brain-core/memory/session_stitcher.py` → Already duplicated in core/
5. 🚫 **DEPRECATE**: `core_data/session_brain_v*.py` → Legacy experiment

---

## System Inventory

### 1. agentic-brain Memory Module
**Location**: `/agentic-brain/src/agentic_brain/memory/`  
**Files**: `unified.py` (56KB), `neo4j_memory.py` (45KB), `_neo4j_memory.py` (24KB), `summarization.py` (28KB)  
**Status**: 🟢 Active, Well-Designed

| Feature | Implementation |
|---------|----------------|
| Storage | SQLite (default) + Neo4j (optional) |
| Memory Types | 4-type: Session, Long-term, Semantic, Episodic |
| Embeddings | Pluggable EmbeddingProvider |
| Multi-tenancy | DataScope: PUBLIC/PRIVATE/CUSTOMER |
| Importance | Mem0-inspired decay + reinforcement |
| Entity Extraction | Built-in |
| Summarization | LLM-based compression |
| Fallback | ✅ Works without Neo4j |

**Key Classes**:
- `UnifiedMemory` - Main facade (4-type architecture)
- `ConversationMemory` - Neo4j-backed conversation storage
- `Neo4jMemory` - Multi-tenant persistent memory
- `UnifiedSummarizer` - Session/realtime compression

**Strengths**:
- Clean architecture with graceful fallbacks
- Works standalone (no Docker required)
- Proper Apache 2.0 licensing
- Comprehensive docstrings and examples

---

### 2. OpenViking Session Module
**Location**: `/openviking-explore/openviking/session/`  
**Files**: `session.py`, `memory_extractor.py`, `compressor.py`, `memory_deduplicator.py`  
**Status**: 🟡 Active, Enterprise-Grade

| Feature | Implementation |
|---------|----------------|
| Storage | VikingFS (custom), VikingDB (vector) |
| Memory Types | 8-category: Profile, Preferences, Entities, Events, Cases, Patterns, Tools, Skills |
| Embeddings | VikingDB managed |
| Multi-tenancy | User Space / Agent Space separation |
| Importance | LLM-based deduplication |
| Entity Extraction | 6-category classification |
| Summarization | LLM-based with L0/L1/L2 detail levels |
| Compression | Archive + summary extraction |

**Key Classes**:
- `Session` - Message management with JSONL persistence
- `SessionCompressor` - Memory extraction + deduplication
- `MemoryExtractor` - 6-category classification
- `MemoryDeduplicator` - LLM-powered merge decisions

**Strengths**:
- Enterprise features (tool/skill tracking, usage analytics)
- Language-aware (CJK, Korean, Russian, Arabic detection)
- Sophisticated deduplication with MERGE/DELETE/SKIP decisions
- Semantic queue for vectorization

**Weaknesses**:
- Depends on VikingFS/VikingDB infrastructure
- Not portable to other environments
- Beijing-licensed (check compatibility)

---

### 3. MCP Memory Hooks Server
**Location**: `/mcp-servers/memory-hooks/server.py`  
**Depends on**: `/core/hooks/ultimate_memory_hooks.py`  
**Status**: 🟠 Active, Should Be Merged

| Feature | Implementation |
|---------|----------------|
| Storage | Neo4j + Redpanda/Kafka + JSONL backup |
| Memory Types | HookEvent (single type) |
| Embeddings | M2-accelerated MLX (if available) |
| Multi-tenancy | None |
| Importance | Rule-based scoring |
| Entity Extraction | None |
| Summarization | None |

**Key Classes**:
- `UltimateMemoryHooks` - Captures all hook events
- `HookEvent` - Data class for events

**MCP Tools**:
- `capture_message` - Store message
- `recall_memories` - Semantic search
- `get_session_context` - Recent context
- `search_all_sessions` - Cross-session search
- `start_session` / `end_session` - Lifecycle

**Strengths**:
- Dual storage (Neo4j + Kafka events)
- Connection pool support
- JSONL backup for resilience

**Weaknesses**:
- Duplicates functionality from unified.py
- No summarization
- No entity extraction
- Simple importance scoring

---

### 4. brain-core Session Stitcher
**Location**: `/brain-core/src/brain_core/memory/session_stitcher.py`  
**Also at**: `/core/memory/session_stitcher.py` (duplicate!)  
**Status**: 🔴 Duplicated, Should Consolidate

| Feature | Implementation |
|---------|----------------|
| Storage | Pluggable: Neo4j, SQLite, In-Memory |
| Memory Types | Session metadata + entities |
| Cross-session linking | ✅ Via shared entities/topics |
| Entity Extraction | JIRA tickets, PRs, URLs, files, people, code refs |

**Key Classes**:
- `SessionStitcher` - Links related sessions
- `ExtractedEntities` - Entity container
- `SessionLink` - Relationship between sessions
- `SessionContext` - Aggregated context

**Strengths**:
- Pluggable storage backends
- Good entity extraction patterns
- Cross-session relationship building

**Weaknesses**:
- Exists in TWO places (brain-core AND core/)
- Limited compared to unified.py
- No summarization or compression

---

### 5. core_data Session Brain (v1-v10)
**Location**: `/core_data/session_brain*.py`  
**Status**: 🔴 Legacy Experiment

| Version | Focus |
|---------|-------|
| v1-v4 | Basic session storage |
| v5-v6 | Pattern detection |
| v7-v8 | Emotion/personality |
| v9 | Dream processing |
| v10 | "Second Brain" meta-system |

**Assessment**: This is a research/experimental lineage. Each version inherits from the previous. v10 is the most complete but extremely complex (personality evolution, predictions, etc.).

**Recommendation**: Archive. The ideas are interesting but the implementation is not production-ready and overlaps with OpenViking's more robust approach.

---

## Feature Comparison Matrix

| Feature | agentic-brain unified | OpenViking | MCP hooks | brain-core stitcher | core_data brain |
|---------|:---------------------:|:----------:|:---------:|:-------------------:|:---------------:|
| **Storage** |
| SQLite | ✅ | ❌ | ❌ | ✅ | ❌ |
| Neo4j | ✅ | ❌ | ✅ | ✅ | ✅ |
| VikingDB | ❌ | ✅ | ❌ | ❌ | ❌ |
| Kafka/Redpanda | ❌ | ❌ | ✅ | ❌ | ❌ |
| File-based | ✅ | ✅ (JSONL) | ✅ (JSONL) | ❌ | ❌ |
| **Memory Architecture** |
| Multi-type | ✅ (4) | ✅ (8) | ❌ (1) | ❌ | ❌ |
| Importance decay | ✅ | ❌ | ✅ (basic) | ❌ | ❌ |
| Entity extraction | ✅ | ✅ | ❌ | ✅ | ❌ |
| Topic detection | ❌ | ✅ | ✅ | ✅ | ❌ |
| **Compression** |
| Summarization | ✅ | ✅ (L0/L1/L2) | ❌ | ❌ | ❌ |
| Mid-conversation | ✅ | ✅ | ❌ | ❌ | ❌ |
| Session-end | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Search** |
| Full-text | ✅ | ✅ | ✅ | ❌ | ❌ |
| Semantic/vector | ✅ | ✅ | ❌ | ❌ | ❌ |
| Cross-session | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Multi-tenancy** |
| Data scopes | ✅ | ✅ (user/agent) | ❌ | ❌ | ❌ |
| Customer isolation | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Resilience** |
| Fallback storage | ✅ | ❌ | ✅ | ✅ | ❌ |
| Works offline | ✅ | ❌ | ❌ | ✅ | ❌ |

---

## Duplication Analysis

### High Duplication (Consolidate Immediately)

| Pattern | Locations | Lines of Code |
|---------|-----------|---------------|
| Session message storage | unified.py, ultimate_memory_hooks.py, session.py | ~500 |
| Entity extraction | neo4j_memory.py, session_stitcher.py (x2) | ~300 |
| Importance scoring | unified.py, neo4j_memory.py, ultimate_memory_hooks.py | ~150 |
| Neo4j connection | _neo4j_memory.py, ultimate_memory_hooks.py, session_stitcher.py | ~200 |

### Unique Features (Preserve)

| Module | Unique Feature | Value |
|--------|---------------|-------|
| OpenViking | 8-category memory classification | High |
| OpenViking | LLM-based deduplication | High |
| OpenViking | Tool/skill usage tracking | Medium |
| unified.py | Mem0-style importance decay | High |
| unified.py | SQLite fallback | High |
| MCP hooks | Kafka/Redpanda event streaming | Medium |
| session_stitcher | Cross-session relationship building | High |

---

## Consolidation Recommendations

### Phase 1: Merge MCP Hooks into Unified (Week 1)

```
core/hooks/ultimate_memory_hooks.py
         ↓
agentic-brain/memory/unified.py
```

**Actions**:
1. Add `capture_hook_event()` method to UnifiedMemory
2. Add Kafka/Redpanda support as optional publisher
3. Keep MCP server as thin wrapper calling UnifiedMemory
4. Delete redundant Neo4j schema creation

**Migration**:
```python
# Before (ultimate_memory_hooks.py)
hooks = UltimateMemoryHooks()
hooks.capture_event("userPromptSubmitted", "copilot-cli", content=msg)

# After (unified.py)
mem = UnifiedMemory(enable_kafka=True)
mem.capture_hook_event("userPromptSubmitted", source="copilot-cli", content=msg)
```

### Phase 2: Consolidate Session Stitchers (Week 2)

```
brain-core/memory/session_stitcher.py  ─┐
core/memory/session_stitcher.py       ─┼──► agentic-brain/memory/session_stitcher.py
```

**Actions**:
1. Create single source in agentic-brain
2. Update imports in brain-core to point to agentic-brain
3. Delete duplicate in core/

### Phase 3: OpenViking as Plugin (Week 3)

Keep OpenViking session module separate but create adapter:

```python
# agentic-brain/memory/adapters/openviking_adapter.py
class OpenVikingAdapter:
    """Adapts OpenViking session to UnifiedMemory interface."""
    
    def __init__(self, viking_session: Session):
        self.session = viking_session
    
    def store(self, content, **kwargs) -> MemoryEntry:
        # Delegate to viking session
        msg = self.session.add_message("system", [Part(text=content)])
        return MemoryEntry(id=msg.id, content=content, ...)
```

### Phase 4: Archive Legacy (Week 4)

Move to `/archive/`:
- `core_data/session_brain_v*.py` (keep v10 for reference)
- Any unused MCP server files

---

## Canonical Implementation

**The winner is: `agentic-brain/src/agentic_brain/memory/unified.py`**

Reasons:
1. ✅ Clean 4-type architecture with clear semantics
2. ✅ Works WITHOUT Docker/external services (SQLite fallback)
3. ✅ Proper Apache 2.0 licensing
4. ✅ Best documentation and examples
5. ✅ Multi-tenant support built-in
6. ✅ Mem0-inspired importance decay (state of the art)
7. ✅ Pluggable embedder interface
8. ✅ Already supports Neo4j when available

---

## Migration Path

### For MCP Memory Hooks Users

```python
# Old way (core/hooks)
from core.hooks.ultimate_memory_hooks import get_hooks
hooks = get_hooks()
hooks.capture_event(...)

# New way (agentic-brain)
from agentic_brain.memory import UnifiedMemory
mem = UnifiedMemory()
mem.store(content, memory_type=MemoryType.SESSION, metadata={'event_type': ...})
```

### For Session Stitcher Users

```python
# Old way (core/memory or brain-core)
from core.memory.session_stitcher import SessionStitcher

# New way (agentic-brain) - same API!
from agentic_brain.memory import SessionStitcher
```

### For OpenViking Users

Keep using OpenViking for enterprise features, but register with UnifiedMemory:

```python
# In OpenViking session commit
from agentic_brain.memory import UnifiedMemory

mem = UnifiedMemory()
for extracted_memory in memories:
    mem.store(
        content=extracted_memory.content,
        memory_type=MemoryType.LONG_TERM,
        metadata={'source': 'openviking', 'category': extracted_memory.category}
    )
```

---

## Effort Estimate

| Phase | Effort | Risk | Priority |
|-------|--------|------|----------|
| Merge MCP hooks | 2-3 days | Low | High |
| Consolidate stitchers | 1-2 days | Low | High |
| OpenViking adapter | 3-4 days | Medium | Medium |
| Archive legacy | 1 day | Low | Low |
| **Total** | **~2 weeks** | | |

---

## Open Questions

1. **Should we migrate Neo4j schema?** Both systems create different indexes. Need to unify.

2. **Kafka vs Event Bus?** `ultimate_memory_hooks` uses Kafka directly. `agentic-brain` has no event support. Should we add?

3. **OpenViking licensing?** "Beijing Volcano Engine" license - verify compatibility with Joseph's Apache 2.0 licensing goals.

4. **Vector database?** OpenViking uses VikingDB. agentic-brain uses embedding provider. Should we standardize?

---

## Conclusion

Joseph's brother was right - there ARE duplicate implementations. But this is a natural result of rapid development across multiple use cases. The path forward is:

1. **Unify around `agentic-brain/memory/unified.py`** as the canonical implementation
2. **Keep OpenViking** for enterprise features but treat as optional plugin
3. **Deprecate** MCP hooks implementation (merge into unified)
4. **Archive** the experimental session_brain versions

This will reduce maintenance burden, eliminate confusion, and create a clear API for all memory operations in Joseph's brain.

---

*Report generated by Iris Lumina 💜*  
*"I help Joseph see - including duplicate code"*
