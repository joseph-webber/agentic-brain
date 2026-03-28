# Neo4j Architecture

This document describes the public Neo4j architecture used by Agentic Brain for GraphRAG, long-term memory, and durable workflow state.

It is intentionally implementation-aligned rather than aspirational. The labels, relationship types, indexes, and query patterns below reflect the current architecture in `src/agentic_brain/` and provide a stable reference for contributors, operators, and integrators.

---

## 1. Overview

Agentic Brain uses Neo4j as a **multi-purpose graph platform** rather than a single-feature datastore.

Neo4j currently supports three complementary workloads:

1. **GraphRAG retrieval** — documents, chunks, entities, and graph edges used for hybrid vector + graph search.
2. **Conversation memory** — sessions, messages, summaries, and entity links for cross-session recall.
3. **Workflow durability** — workflow runs, steps, versions, and dependencies for resumable orchestration.

At a high level, the graph is optimized for these goals:

- preserve **relationships as first-class data**
- support **semantic retrieval** with native vector indexes
- keep **time-aware history** for memory and workflow replay
- allow **progressive enrichment** from raw documents to extracted entities to higher-level communities and topics

```text
                    ┌──────────────────────────────┐
                    │        Data Sources          │
                    │ docs · chat · APIs · events  │
                    └──────────────┬───────────────┘
                                   │
                         ingest / memory write
                                   │
             ┌─────────────────────┼─────────────────────┐
             │                     │                     │
             v                     v                     v
      Document graph        Conversation graph     Workflow graph
   Document → Chunk → Entity  Session → Message      Workflow → Step
             │                     │                     │
             └──────────────┬──────┴──────────────┬──────┘
                            v                     v
                     Vector + fulltext      Time + state queries
                            │
                            v
                       Hybrid retrieval
```

---

## 2. Graph model overview

### 2.1 Architectural principle

Agentic Brain models each domain as a **small, purpose-built subgraph** with a few shared conventions:

- every major node type has a stable `id`
- timestamps are stored for ordering, decay, or auditing
- relationships carry meaningful domain semantics
- extracted entities act as a bridge between documents, memory, and retrieval

### 2.2 Core graph domains

| Domain | Primary labels | Main purpose |
|---|---|---|
| GraphRAG | `Document`, `Chunk`, `Entity`, `SourceDocument` | Retrieval, extraction, semantic search |
| Memory | `Session`, `Message`, `Summary`, `Entity` | Conversation history, recall, summarization |
| Workflows | `Workflow`, `Step`, `WorkflowVersion` | Durable execution, recovery, lineage |
| Analytics / topic overlays | `Entity` with community metadata | Community detection and topic grouping |

### 2.3 Shared modeling rules

- Use `MERGE` on stable identifiers for idempotent ingestion.
- Store frequently filtered properties directly on the node.
- Keep relationship types explicit (`CONTAINS`, `MENTIONS`, `DEPENDS_ON`) instead of generic link types.
- Prefer additive enrichment over destructive rewrite; for example, entities can accumulate `mention_count`, `last_seen`, or community metadata over time.

---

## 3. Node labels and their purposes

### 3.1 Retrieval and knowledge graph labels

#### `Document`
Represents a canonical indexed document inside the production GraphRAG pipeline.

**Typical properties**
- `id`
- `content`
- `title` (when present)
- `timestamp`
- `metadata`
- `char_count`

**Purpose**
- anchor record for a source item
- parent of chunked content
- entry point for document-level filtering

#### `Chunk`
Represents a searchable document fragment.

**Typical properties**
- `id`
- `content`
- `text`
- `position`
- `document_id`
- `embedding`

**Purpose**
- vector retrieval target
- fulltext retrieval target
- bridge between semantic similarity and graph traversal

#### `Entity`
Represents an extracted or normalized concept such as a person, organization, location, concept, or domain object.

**Typical properties**
- `id`
- `name`
- `type`
- `description` or `normalized_name`
- `embedding` (where available)
- `mention_count`
- `first_seen`
- `last_seen`
- `communityId` (when graph analytics is applied)

**Purpose**
- semantic bridge across documents and sessions
- graph traversal anchor for GraphRAG
- entity-centric search and topic grouping

#### `SourceDocument`
Represents a source text processed by the lightweight knowledge extraction pipeline.

**Typical properties**
- `id`
- `content`
- `metadata`
- `created_at`
- `updated_at`

**Purpose**
- provenance record for extracted entities and edges
- simpler extraction-oriented schema for `KnowledgeExtractor`

### 3.2 Memory labels

#### `Session`
Represents a conversational or interaction session.

**Typical properties**
- `id`
- `started_at`
- `last_updated`
- `message_count`

**Purpose**
- conversation boundary
- history grouping
- cross-session linking target

#### `Message`
Represents a single message in a session.

**Typical properties**
- `id`
- `role`
- `content`
- `timestamp`
- `session_id`
- `metadata`
- `importance`
- `access_count`
- `last_accessed`

**Purpose**
- ordered conversation history
- temporal recall
- entity linking and memory scoring

#### `Summary`
Represents a generated summary or condensation of prior messages.

**Typical properties**
- `id`
- `content`
- `message_count`
- `timestamp`
- `summary_type`

**Purpose**
- memory compaction
- long-range recall without replaying every message

### 3.3 Workflow labels

#### `Workflow`
Represents a durable workflow instance.

**Typical properties**
- `id`
- `name`
- `status`
- `input_data`
- `metadata`
- timestamps for start/update/completion

**Purpose**
- top-level execution record
- recovery anchor after interruption
- orchestration lineage

#### `Step`
Represents an individual unit of workflow work.

**Typical properties**
- `id`
- `name`
- `status`
- `input_data`
- `output_data`
- `error`
- `retry_count`
- `started_at`
- `completed_at`

**Purpose**
- step-level execution state
- dependency tracking
- progress reporting and replay

#### `WorkflowVersion`
Represents a historical version or checkpoint of workflow state.

**Purpose**
- rollback support
- audit and lineage inspection
- versioned recovery

---

## 4. Relationship types

### 4.1 Retrieval relationships

| Relationship | From → To | Meaning |
|---|---|---|
| `CONTAINS` | `Document` → `Chunk` | Document owns chunk |
| `MENTIONS` | `Document`/`Chunk`/`Message`/`SourceDocument` → `Entity` | Content references entity |
| `RELATES_TO` | `Entity` → `Entity` | Extracted semantic relationship between entities |

`RELATES_TO` carries additional semantics in properties such as:
- `type`
- `weight`
- `evidence`
- `created_at`
- `updated_at`

This pattern keeps the relationship type stable while preserving domain-specific semantics in properties.

### 4.2 Memory relationships

| Relationship | From → To | Meaning |
|---|---|---|
| `CONTAINS` | `Session` → `Message` | Session owns message |
| `NEXT` | `Message` → `Message` | Maintains message order |
| `MENTIONS` | `Message` → `Entity` | Message references entity |
| `DISCUSSED_IN` | `Entity` → `Session` | Entity appeared in session |
| `SUMMARIZED_BY` | `Session` → `Summary` | Session has summary nodes |
| `LINKS_TO` | `Session` → `Session` | Sessions are contextually related |

### 4.3 Workflow relationships

| Relationship | From → To | Meaning |
|---|---|---|
| `CONTAINS` | `Workflow` → `Step` | Workflow contains steps |
| `NEXT` | `Step` → `Step` | Ordered execution sequence |
| `DEPENDS_ON` | `Step` → `Step` | Explicit dependency edge |
| `VERSION` | `Workflow` → `WorkflowVersion` | Historical checkpoint |
| `EXECUTED_BY` | `Workflow` → `Agent`/`User` | Execution identity when modeled |

---

## 5. Indexing strategy

Agentic Brain uses a layered indexing strategy that matches its hybrid retrieval model.

### 5.1 Constraints

Use uniqueness constraints on stable identifiers first.

**Current patterns in the codebase include:**
- `Document.id`
- `Chunk.id`
- `Entity.id`
- `Session.id`
- `Message.id`
- `Workflow.id`
- `Step.id`

These constraints do two jobs:
- guarantee idempotent `MERGE` behavior
- protect against accidental duplication during retries or replay

### 5.2 Range indexes

Range indexes support selective filters and sort-friendly lookups.

**Current examples**
- `Entity.type`
- `Chunk.document_id`
- `Document.timestamp`
- `Message.timestamp`
- `Message.importance`
- `Session.started_at`
- `Workflow.name`
- `Workflow.status`
- `Step.status`

Use range indexes for:
- date filters
- status filters
- document scoping
- importance-based recall

### 5.3 Fulltext indexes

Fulltext indexes power literal search and BM25-style retrieval signals.

**Current examples**
- `entity_fulltext` on `Entity(name, description)`
- `chunk_fulltext` on `Chunk(content)`
- `document_fulltext` on `Document(content, title)`

Fulltext search is important even in a vector system because it handles:
- identifiers and acronyms
- exact terminology
- short queries with weak semantic signal

### 5.4 Vector indexes

Vector indexes are the backbone of semantic retrieval.

**Current standard index**
- `chunk_embeddings` on `Chunk.embedding`

**Current default configuration**
- dimensions: `384`
- similarity: `cosine`

Use vector indexes for:
- semantic chunk retrieval
- candidate generation before graph expansion
- hybrid retrieval with reciprocal-rank fusion

### 5.5 Practical indexing guidance

When extending the schema:

1. Add a uniqueness constraint before adding ingestion code.
2. Add a range index for every property that appears repeatedly in `WHERE`, `ORDER BY`, or partition-style filters.
3. Add fulltext indexes only to text fields that will actually be searched.
4. Add vector indexes only to labels with enough query volume to justify ANN overhead.

---

## 6. Query patterns

### 6.1 Document-to-chunk retrieval

Common when expanding a document hit into answerable context.

```cypher
MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(c:Chunk)
RETURN c.id, c.content, c.position
ORDER BY c.position ASC
```

### 6.2 Entity-centric graph expansion

Used after matching a chunk or entity from vector/fulltext search.

```cypher
MATCH (e:Entity {id: $entity_id})<-[m:MENTIONS]-(c:Chunk)
OPTIONAL MATCH (e)-[r:RELATES_TO]->(related:Entity)
RETURN e, collect(DISTINCT c.id) AS chunk_ids,
       collect(DISTINCT {type: r.type, target: related.name}) AS related_entities
```

### 6.3 Hybrid retrieval pattern

A typical hybrid pipeline is:

1. vector search on `Chunk.embedding`
2. fulltext search on `Chunk` and `Document`
3. graph expansion from matched entities
4. fusion/rerank in application code

```cypher
CALL db.index.vector.queryNodes('chunk_embeddings', $k, $embedding)
YIELD node, score
RETURN node.id, node.content, score
ORDER BY score DESC
```

### 6.4 Conversation history traversal

```cypher
MATCH (s:Session {id: $session_id})-[:CONTAINS]->(m:Message)
OPTIONAL MATCH (m)-[:MENTIONS]->(e:Entity)
RETURN m.id, m.role, m.content, m.timestamp, collect(e.name) AS entities
ORDER BY m.timestamp ASC
LIMIT $limit
```

### 6.5 Topic and entity recall

```cypher
MATCH (m:Message)-[:MENTIONS]->(e:Entity)
WHERE toLower(e.name) CONTAINS toLower($topic)
RETURN m.id, m.content, m.timestamp
ORDER BY m.timestamp DESC
LIMIT $limit
```

### 6.6 Cross-session recall

```cypher
MATCH (s1:Session {id: $session_id})-[:CONTAINS]->(:Message)-[:MENTIONS]->(e:Entity)
      <-[:MENTIONS]-(:Message)<-[:CONTAINS]-(s2:Session)
WHERE s2.id <> $session_id
WITH s2, collect(DISTINCT e.name) AS shared_entities
RETURN s2.id, shared_entities
ORDER BY size(shared_entities) DESC
LIMIT $limit
```

### 6.7 Workflow recovery

```cypher
MATCH (w:Workflow {id: $workflow_id})-[:CONTAINS]->(s:Step)
RETURN s.id, s.name, s.status, s.retry_count, s.error
ORDER BY s.started_at ASC
```

### 6.8 Community and topic overlays

When graph analytics is enabled, entities can be grouped and filtered by community metadata.

```cypher
MATCH (e:Entity)
WHERE e.communityId = $community_id
RETURN e.name, e.type, e.mention_count
ORDER BY e.mention_count DESC
LIMIT 50
```

---

## 7. Performance tips

### 7.1 Batch writes with `UNWIND`

Prefer one batched write over many single-row writes.

```cypher
UNWIND $chunks AS ch
MERGE (c:Chunk {id: ch.chunk_id})
SET c.content = ch.text,
    c.embedding = ch.embedding
```

This reduces round trips and keeps ingest throughput predictable.

### 7.2 Use `MERGE` only on identity keys

`MERGE` is powerful but expensive when used on wide property sets. Restrict it to the stable identifier, then use `SET` for mutable fields.

**Good**
```cypher
MERGE (e:Entity {id: $id})
SET e.name = $name, e.type = $type
```

**Avoid**
```cypher
MERGE (e:Entity {id: $id, name: $name, type: $type, updated_at: $timestamp})
```

### 7.3 Bound traversal depth

GraphRAG queries can become expensive when traversal depth is unconstrained. Use explicit hop limits and targeted relationship lists.

Recommended practice:
- 1 hop for precision-first answers
- 2 hops for broader context
- 3+ hops only with strong filtering and profiling

### 7.4 Keep hot properties small and direct

Properties used in filtering or ranking should stay flat and directly indexed.

Prefer:
- `status`
- `timestamp`
- `importance`
- `document_id`

Avoid forcing frequent filters through large `metadata` maps.

### 7.5 Separate candidate generation from enrichment

For hybrid retrieval, do not start with a large graph traversal. First generate a small candidate set via vector or fulltext search, then expand graph context only around those candidates.

### 7.6 Use timestamps for lifecycle management

Time-based properties enable:
- message decay
- archival decisions
- rolling summaries
- hot/warm/cold movement strategies

See [NEO4J_ZONES.md](./NEO4J_ZONES.md) for the zone model layered on top of this architecture.

### 7.7 Profile expensive Cypher regularly

For production queries:
- use `EXPLAIN` during development
- use `PROFILE` before high-volume rollout
- verify index usage after schema changes
- re-check plans after large data growth or version upgrades

---

## 8. Recommended extension patterns

### 8.1 Add a new retrievable content type

1. create a stable node label and `id`
2. decide whether it needs chunking
3. connect it to `Entity` nodes with `MENTIONS`
4. index only the fields required for retrieval

### 8.2 Add a new memory artifact

1. connect it to `Session` or `Message`
2. keep timestamps explicit
3. ensure query paths stay simple for recall APIs

### 8.3 Add analytics overlays without breaking retrieval

Community, topic, quality, or trust signals should usually be added as:
- node properties on `Entity`/`Chunk`
- dedicated summary nodes
- optional overlay relationships

This keeps core retrieval paths stable while allowing richer ranking.

---

## 9. Related documents

- [Neo4j Zones](./NEO4J_ZONES.md)
- [Neo4j Integration Guide](./neo4j.md)
- [Integration Overview](./integrations/NEO4J.md)
- [GraphRAG Guide](./GRAPHRAG.md)
- [Memory Architecture](./MEMORY.md)
