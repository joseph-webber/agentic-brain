# Neo4j Schema Migration Guide: Aligning to HappySkies Standard

## Overview

This document outlines the steps needed to align Joe's Neo4j schema with the HappySkies (HS)
standard for relationships between `HookEvent`, `Checkpoint`, `Session`, and `Topic` nodes.

The goal is a consistent, queryable graph where topic discovery flows through Sessions,
session history is traversable via `CONTINUES` chains, and all hook events are uniformly linked
to their parent session.

---

## Schema Comparison

### Current state (live counts from Joe's graph)

| Relationship | Type | Count | Status |
|---|---|---|---|
| HookEvent → Session | OCCURRED_IN | 1,553 | ❌ remove |
| HookEvent → Session | RELATED_TO | 418 | ❌ remove |
| HookEvent → Session | PART_OF | 336 | ✅ keep |
| HookEvent → Session | IN_SESSION | 229 | ❌ remove |
| Session → Topic | RELATED_TO | 1,071 | ❌ remove |
| Session → Topic | COVERS | 524 | ❌ remove |
| Session → Topic | DISCUSSES | 15 | ✅ keep |
| Session → Checkpoint | HAS_CHECKPOINT | 1,123 | ✅ keep |
| Checkpoint → Topic | DISCUSSES | 4,161 | ❌ remove (rule violation) |
| Session → Session | CONTINUES | 0 | ⚠️ missing — add |

### Target schema (HappySkies standard)

```
(HookEvent)  -[:PART_OF]-------> (Session)
(Session)    -[:DISCUSSES]------> (Topic)
(Session)    -[:HAS_CHECKPOINT]-> (Checkpoint)
(Session)    -[:CONTINUES]------> (Session)
(Session)    -[:MENTIONS]-------> (Entity)
(Checkpoint) -[:PART_OF]-------> (Session)
```

**Key rules:**
- `DISCUSSES` belongs on `Session → Topic` only — never `Checkpoint → Topic`
- `HookEvent → Session` uses `PART_OF` only — no `OCCURRED_IN`, `IN_SESSION`, `RELATED_TO`
- `Session → Topic` uses `DISCUSSES` only — no `RELATED_TO`, `COVERS`
- `CONTINUES` chains sessions chronologically — essential for continuity queries

---

## Visualise the current state

Paste into Neo4j browser (`http://localhost:7474/browser/`):

```cypher
MATCH (a)-[r]->(b)
WHERE any(l IN labels(a) WHERE l IN ['HookEvent','Checkpoint','Session','Topic'])
  AND any(l IN labels(b) WHERE l IN ['HookEvent','Checkpoint','Session','Topic'])
WITH a, r, b LIMIT 500
RETURN a, r, b
```

> Tip: Set **Settings → Graph → Initial node display number** to 500+ for full visibility.

---

## Migration Cypher

Run in order, one at a time. Each is idempotent (uses MERGE).

```cypher
// Step 1: Standardise HookEvent→Session to PART_OF only
MATCH (h:HookEvent)-[r:OCCURRED_IN|RELATED_TO|IN_SESSION]->(s:Session)
MERGE (h)-[:PART_OF]->(s)
DELETE r;

// Step 2: Standardise Session→Topic to DISCUSSES only
MATCH (s:Session)-[r:RELATED_TO|COVERS]->(t:Topic)
MERGE (s)-[:DISCUSSES]->(t)
DELETE r;

// Step 3: Remove Checkpoint→Topic DISCUSSES (rule violation)
MATCH (c:Checkpoint)-[r:DISCUSSES]->(t:Topic)
DELETE r;

// Step 4: Add CONTINUES chain between consecutive Sessions
MATCH (s:Session)
WHERE s.timestamp IS NOT NULL
WITH s ORDER BY s.timestamp
WITH collect(s) AS sessions
UNWIND range(0, size(sessions)-2) AS i
WITH sessions[i] AS s1, sessions[i+1] AS s2
MERGE (s1)-[:CONTINUES]->(s2);
```

> Before Step 4, verify timestamp property name:
> ```cypher
> MATCH (s:Session) RETURN keys(s) LIMIT 1
> ```

---

## Verification Queries

```cypher
// All should return 0
MATCH (h:HookEvent)-[r:OCCURRED_IN|RELATED_TO|IN_SESSION]->(s:Session)
RETURN count(r) AS leftover_hookevent_rels;

MATCH (s:Session)-[r:RELATED_TO|COVERS]->(t:Topic)
RETURN count(r) AS leftover_session_topic_rels;

MATCH (c:Checkpoint)-[r:DISCUSSES]->(t:Topic)
RETURN count(r) AS leftover_checkpoint_topic_rels;

// Should return > 0
MATCH (s1:Session)-[r:CONTINUES]->(s2:Session)
RETURN count(r) AS continues_count;

// Full picture after migration
MATCH (a)-[r]->(b)
WHERE any(l IN labels(a) WHERE l IN ['HookEvent','Checkpoint','Session','Topic'])
  AND any(l IN labels(b) WHERE l IN ['HookEvent','Checkpoint','Session','Topic'])
RETURN labels(a)[0] AS from, type(r) AS rel, labels(b)[0] AS to, count(r) AS count
ORDER BY from, to;
```

---

## Ingestion Scripts Reference

All files that write to Neo4j across brain-core and agentic-brain.
Schema-critical scripts must be updated or they will re-write old relationship types on next run.

### Schema-critical (must update)

| File | Writes | Action needed |
|---|---|---|
| src/brain_core/memory_hooks.py | HookEvent, Session, ConversationTurn — PART_OF, IN_SESSION, FOLLOWS | Remove IN_SESSION, use PART_OF only |
| src/brain_core/hooks/memory_hooks.py | HookEvent, Session — PART_OF, FOLLOWS | Verify no IN_SESSION fallback |
| src/brain_core/memory/session_stitcher.py | Session, Entity, Topic — CONTINUES, DISCUSSES, MENTIONS | Already correct — strongest foundation |
| src/brain_core/skills/builtin/session-continuity/continuity.py | Session, Todo, Learning — HAS_TODO, INVOLVES, LEARNED | Audit for direct Topic writes |

### Non-schema (no changes needed)

| File | Writes | Notes |
|---|---|---|
| src/brain_core/perfect_memory.py | Memory nodes only | Uses CREATE not MERGE — potential duplicates |
| src/brain_core/memory/perfect_memory.py | Memory nodes only | Duplicate of above |
| src/agentic_brain/memory/neo4j_memory.py | Memory nodes only | No schema impact |
| src/agentic_brain/workflows/neo4j_state.py | Workflow, Step nodes only | Unrelated |
| src/agentic_brain/graph/topic_hub.py | Orphan audit, topic hub maintenance | Maintenance tool, not ingestion |

---

## Topic Detection

Joe's `SimpleTopicDetector` (in `session_stitcher.py`) has only 4 generic topics:
`work`, `code`, `personal`, `learning` — nearly everything gets tagged as `work` or `code`,
making topic traversal almost meaningless.

The HS approach uses ~45 curated domain-specific topics tied to actual projects and
components (e.g. `neo4j`, `spam_filter`, `brain`, `scripts`, `trading`).

**Recommendation:** Replace the `TOPICS` dict in `SimpleTopicDetector` with a curated
keyword map matching your actual projects. The `session_stitcher.py` already writes
`DISCUSSES` correctly — detection quality is the only gap.
