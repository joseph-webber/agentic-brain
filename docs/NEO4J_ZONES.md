# Neo4j Zones

This document describes the **five-zone storage model** used to organize Neo4j data in Agentic Brain.

The design is inspired by community patterns such as Arraz2000's five-zone approach, then adapted for Agentic Brain's hybrid workload: GraphRAG retrieval, conversation memory, and durable orchestration.

The zone model is a **logical architecture**. It does not require five separate databases on day one. Teams can implement it through labels, properties, subgraphs, retention rules, archival workflows, or separate databases as scale increases.

---

## 1. Why use zones?

A graph used for both retrieval and operational memory naturally accumulates data with very different access patterns.

Examples:
- a fresh conversation message may be queried many times in one hour
- a chunk from a recently indexed document may stay hot for several days
- an old workflow checkpoint may only be needed for audit or replay
- topic overlays may be reused for routing and retrieval long after their source events cool down

A zone strategy helps balance:

- **performance** for hot paths
- **cost** for large historical datasets
- **governance** for retention and archival
- **operability** for backup, rebuild, and analytics workflows

---

## 2. Zone model overview

```text
                         ┌───────────────────────┐
                         │       HOT ZONE        │
                         │ recent, mutable, fast │
                         └──────────┬────────────┘
                                    │ ages out
                                    v
                         ┌───────────────────────┐
                         │       WARM ZONE       │
                         │ useful, stable, mixed │
                         └──────────┬────────────┘
                                    │ archives
                                    v
                         ┌───────────────────────┐
                         │       COLD ZONE       │
                         │ historical, compact   │
                         └───────────────────────┘

                   ┌────────────────────┐   ┌────────────────────┐
                   │     TOPIC ZONE     │   │      META ZONE     │
                   │ semantic overlays  │   │ schema + system    │
                   │ communities/taxons │   │ ops + lineage      │
                   └────────────────────┘   └────────────────────┘
```

The first three zones are primarily about **temperature and lifecycle**.
The last two are about **organization and control**.

---

## 3. Hot zone

### 3.1 Purpose

The hot zone contains **recent, high-churn, latency-sensitive data**.

This is the working set that powers day-to-day retrieval and orchestration.

### 3.2 Typical contents

- new `Document` and `Chunk` nodes awaiting immediate retrieval
- recently referenced `Entity` nodes
- active `Session` and `Message` chains
- in-flight `Workflow` and `Step` nodes
- fresh summaries and recent cross-session links

### 3.3 Characteristics

- highest read/write activity
- strictest latency expectations
- frequent updates to counters, timestamps, status, or importance
- should rely on the best indexes and smallest traversals

## 3.4 Practical implementation options

You can model hot data using one or more of:

- `zone = 'hot'` property
- recent timestamp windows such as `timestamp >= now() - duration('P7D')`
- separate labels for active lifecycle state
- separate database or cluster only when scale justifies it

## 3.5 Recommended rules

- keep hot traversals shallow
- keep hot indexes lean and well maintained
- avoid storing bulky derived analytics here if they can be rebuilt elsewhere
- favor fast candidate generation before graph expansion

---

## 4. Warm zone

### 4.1 Purpose

The warm zone stores **still-useful but less volatile data**.

This is typically the largest operational zone. It holds context that remains relevant for retrieval, recall, and analytics, but no longer changes constantly.

### 4.2 Typical contents

- settled documents and chunks still used in retrieval
- durable entities with slower change frequency
- recent historical sessions
- completed workflows still within retention windows
- durable summaries and link structures

### 4.3 Characteristics

- moderate read activity
- lower write volume than hot zone
- ideal place for broader graph expansion and historical comparisons
- suitable for many hybrid retrieval operations

## 4.4 Recommended rules

- keep fulltext and vector access available
- retain key structural edges (`CONTAINS`, `MENTIONS`, `RELATES_TO`)
- compact redundant raw operational detail where summaries are sufficient
- preserve identifiers so warm data can still support provenance and replay

---

## 5. Cold zone

### 5.1 Purpose

The cold zone stores **archived or infrequently accessed historical data**.

It exists to preserve important history without making the active graph heavier than necessary.

### 5.2 Typical contents

- old sessions kept for compliance or long-tail recall
- aged workflow versions and checkpoints
- superseded summaries and historical state snapshots
- source documents that must remain discoverable but are rarely queried

### 5.3 Characteristics

- low read frequency
- low or no mutation
- optimized for retention, export, and occasional investigation
- ideal candidate for compression or denormalized summary forms

### 5.4 Recommended rules

- archive by age and access frequency, not just age alone
- preserve enough metadata to restore provenance
- consider summary-first recall before loading cold raw detail
- prefer scheduled migration rather than ad hoc movement

### 5.5 Common archival strategies

- move old nodes by `zone` property and retention job
- export cold snapshots for offline retention
- keep only summary nodes and essential identifiers in Neo4j
- rebuild auxiliary indexes only where cold query volume justifies it

---

## 6. Topic zone

### 6.1 Purpose

The topic zone groups **semantic overlays** that help the graph behave like an organized knowledge system instead of a raw event store.

This zone is especially useful for GraphRAG and routing logic.

### 6.2 Typical contents

- community assignments such as `communityId` on `Entity`
- curated topic nodes or taxonomies
- semantic clusters derived from retrieval behavior
- domain concepts or ontology mappings
- thematic summary nodes used to enrich prompts

### 6.3 Characteristics

- lower churn than the hot zone
- high reuse across retrieval workflows
- can be partially derived and rebuilt from other zones
- often bridges hot/warm/cold content into a stable semantic structure

### 6.4 Recommended modeling patterns

Topic zoning can be implemented with:

- `Topic` nodes and explicit topic edges
- community properties on `Entity`
- topic summary nodes linked to documents, entities, or sessions
- overlay relationships that do not disturb core operational edges

### 6.5 Example uses

- expand a query from one entity to its wider community
- organize documents by domain theme
- route prompts based on topic affinity
- pre-compute semantic neighborhoods for faster hybrid retrieval

---

## 7. Meta zone

### 7.1 Purpose

The meta zone stores **system-level graph information** rather than business or conversational content.

This is where the graph explains itself.

### 7.2 Typical contents

- schema metadata
- migration markers
- ingestion lineage
- workflow version checkpoints
- quality, trust, or provenance scores
- retention and archival markers
- job execution metadata

### 7.3 Characteristics

- operationally critical
- comparatively small volume
- should be highly reliable and easy to inspect
- often read by maintenance, monitoring, and admin tooling

### 7.4 Recommended rules

- keep the meta zone clean and explicit
- use stable identifiers and timestamps everywhere
- make it easy to answer questions such as:
  - what created this node?
  - when was this graph segment last refreshed?
  - which version of the extractor produced this relationship?
  - which nodes are safe to archive?

---

## 8. How zones map to current labels

The current codebase does not require a one-label-per-zone design. Instead, the same labels can exist in different zones based on lifecycle.

| Label | Likely zone placement |
|---|---|
| `Document` | hot → warm → cold |
| `Chunk` | hot → warm; selectively cold if retained |
| `Entity` | hot for fresh mentions, warm for durable graph, topic zone for community overlays |
| `SourceDocument` | hot during extraction, warm/cold for provenance |
| `Session` | hot while active, warm after completion, cold after archival |
| `Message` | hot initially, warm for recent recall, cold or summarized later |
| `Summary` | warm and topic zone; sometimes cold |
| `Workflow` | hot while running, warm after completion |
| `Step` | hot while active, warm after completion |
| `WorkflowVersion` | meta zone and cold zone depending on retention |

---

## 9. Lifecycle guidance

### 9.1 Promotion and demotion

Typical lifecycle:

1. data lands in the **hot zone**
2. once mutation slows, it moves to the **warm zone**
3. after retention thresholds, it is archived to the **cold zone**
4. topic/meta overlays may persist independently if still valuable

### 9.2 Suggested movement signals

Move data out of hot when:
- update frequency drops
- the workflow or session is completed
- recent-access score falls below threshold
- summary artifacts exist

Move data into cold when:
- it is beyond the operational recall window
- it is low-frequency and expensive to keep fully indexed
- a summary or condensed form is sufficient for most use cases

### 9.3 Do not move blindly

Avoid moving data based solely on age. Consider:
- recent access count
- business importance
- provenance requirements
- compliance retention
- whether semantic overlays still depend on raw nodes

---

## 10. Zone-aware query patterns

### 10.1 Prefer hot-first retrieval

Start with recent, active data when latency matters.

```cypher
MATCH (c:Chunk)
WHERE c.zone = 'hot'
RETURN c.id, c.content
LIMIT 20
```

### 10.2 Expand to warm when needed

```cypher
MATCH (e:Entity {id: $entity_id})<-[r:MENTIONS]-(n)
WHERE coalesce(n.zone, 'warm') IN ['hot', 'warm']
RETURN n, r
LIMIT 100
```

### 10.3 Use cold as a fallback, not the default

```cypher
MATCH (s:Session)-[:SUMMARIZED_BY]->(sum:Summary)
WHERE s.zone = 'cold' AND toLower(sum.content) CONTAINS toLower($term)
RETURN s.id, sum.content
LIMIT 20
```

This keeps common queries fast while still preserving historical depth.

---

## 11. Performance guidance by zone

| Zone | Performance priority | Guidance |
|---|---|---|
| Hot | latency | keep indexes lean, traversals short, writes batched |
| Warm | balanced throughput | support hybrid retrieval and broader traversals |
| Cold | storage efficiency | compress, summarize, archive, query selectively |
| Topic | semantic reuse | optimize for clustering and prompt enrichment |
| Meta | operational clarity | keep small, explicit, and easy to inspect |

Additional recommendations:
- do not over-index cold data
- do not overload the hot zone with rebuildable analytics
- keep topic overlays derivable where possible
- treat meta data as operational infrastructure, not incidental detail

---

## 12. Suggested implementation roadmap

### Phase 1: Logical zones

Add lightweight lifecycle markers without changing deployment topology:
- `zone` property
- archival timestamps
- access counters
- retention jobs

### Phase 2: Operational policies

Add automated movement rules:
- hot → warm after inactivity
- warm → cold after retention threshold
- summary creation before archival

### Phase 3: Physical separation where justified

For larger deployments, map logical zones to separate databases, clusters, or export pipelines.

Examples:
- hot/warm in primary Neo4j
- cold in archive database or exported snapshots
- topic/meta in dedicated admin or analytics graph if needed

---

## 13. Recommended public position

For public documentation and releases, describe the zone model as:

> A five-zone logical architecture that separates active retrieval data, durable operational history, semantic overlays, and system metadata so Neo4j can scale across real-time GraphRAG and long-term memory workloads.

This framing is accurate, implementation-friendly, and does not over-promise a particular deployment shape.

---

## 14. Related documents

- [Neo4j Architecture](./NEO4J_ARCHITECTURE.md)
- [Neo4j Integration Guide](./neo4j.md)
- [GraphRAG Guide](./GRAPHRAG.md)
- [Memory Architecture](./MEMORY.md)
