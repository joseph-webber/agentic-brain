# Neo4j patterns to adopt from Arraz2000's `happy-skies-automation`

Source reviewed:
- `/Users/joe/brain/private/arraz2000/happy-skies-automation/P09-hs-brain/NEO4J_ARCHITECTURE.md`
- `/Users/joe/brain/private/arraz2000/happy-skies-automation/P09-hs-brain/happyskies_brain.py`
- `/Users/joe/brain/private/arraz2000/happy-skies-automation/P09-hs-brain/happyskies_mcp.py`
- `/Users/joe/brain/private/arraz2000/happy-skies-automation/P09-hs-brain/brain_benchmark.py`
- `/Users/joe/brain/private/arraz2000/happy-skies-automation/P09-hs-brain/brain_backup.json`

## Executive summary

The cleanest ideas in HappySkies are **not** exotic graph tricks. They are disciplined constraints:

1. A **topic-centric bipartite overlay** on top of a normal domain graph.
2. A **small, governed topic vocabulary** (33 topics in practice).
3. **Layered labels** that separate raw logs, curated knowledge, domain entities, operational config, and benchmarking.
4. **Directional, verb-based relationships** with clear semantics.
5. A small set of **repeatable query shapes**: topic traversal, latest-state lookup, structured search, and benchmark/health queries.

Conservative take: these patterns are worth copying. The parts to avoid copying are schema drift (`Supplier` vs `Distributor`, `TAGGED` vs `TAGGED_BY`) and benchmark-driven overreach.

---

## 1. The bi-partite graph design — how it works

### What is actually proven

HappySkies is **not a pure bipartite graph**. It also has direct entity-to-entity links such as:

- `Project-[:HAS_COMPONENT]->Component`
- `Brand-[:SOLD_BY]->Store`
- `Brand-[:SUPPLIED_BY]->Supplier`
- `Supplier-[:SUPPLIES_TO]->Store`
- `Person-[:CONTACT_FOR]->Supplier`

What *is* proven is a **bipartite overlay around `Topic`**:

- many node types point **into** `Topic`
- `Topic` is used as a semantic hub
- `Topic` does **not** fan back out operationally
- raw events do **not** connect directly to `Topic`

From the export, inbound links to `Topic` come from at least:

- `Checkpoint` (261)
- `Brand` (183)
- `Session` (140)
- `Supplier` (61)
- `Component` (57)
- `Memory` (53)
- `Person` (48)
- `Automation` (47)
- `Project` (38)
- `SessionSummary` (37)
- `BrainBenchmark` (37)
- `Learning` (29)
- `Store` (28)

And the dominant relationship types into `Topic` are:

- `RELATES_TO` (469)
- `DISCUSSES` (401)
- `ABOUT` (53)
- `TAGGED` (50)
- `COVERS` (37)

### Why it works

This gives HappySkies two graph modes at once:

1. **Structural graph** for hard business facts
   - supply chain
   - project/component hierarchy
   - ownership/contact links

2. **Semantic graph** for cross-cutting retrieval
   - "what relates to shipping?"
   - "which sessions touched suppliers?"
   - "which automations belong to email_ops?"

That is the reusable design pattern.

### Why it is better than fully connecting everything

HappySkies explicitly avoids:

- `HookEvent -> Topic`
- `HookEvent -> Project`
- `HookEvent -> Component`

This is the clean part to copy. Raw logs stay cheap and append-only. Only distilled artifacts link into the semantic layer.

### Recommendation for agentic-brain

Adopt a **two-graph-in-one** design:

- keep direct factual edges for durable business/agent structure
- add a controlled `Topic` hub for semantic navigation
- never let raw event spam connect directly to domain nodes

### Adaptable Cypher examples

#### A. Topic overlay for a durable domain node
```cypher
MATCH (a:Agent {id: $agent_id})
MERGE (t:Topic {name: $topic})
MERGE (a)-[:RELATES_TO]->(t)
```

#### B. Distill session output into topic links, not raw events
```cypher
MATCH (s:Session {id: $session_id})
UNWIND $topics AS topic_name
MERGE (t:Topic {name: topic_name})
MERGE (s)-[:DISCUSSES]->(t)
```

#### C. Keep raw capture separate
```cypher
MERGE (e:HookEvent {id: $event_id})
SET e.content = $content,
    e.timestamp = datetime($timestamp),
    e.source = $source,
    e.primary_topic = $primary_topic
WITH e
MATCH (s:Session {id: $session_id})
MERGE (e)-[:PART_OF]->(s)
```

#### D. Semantic traversal across many node types
```cypher
MATCH (n)-[r:RELATES_TO|DISCUSSES|TAGGED|COVERS|ABOUT]->(t:Topic {name: $topic})
RETURN labels(n)[0] AS label, coalesce(n.name, n.title, n.id) AS item, type(r) AS rel
ORDER BY label, item
```

### Verdict

**Adopt.**

But describe it accurately as a **topic-centric bipartite overlay**, not a pure bipartite graph.

---

## 2. The 33 Topics cap — why and how

### What is proven

HappySkies documents an explicit rule:

- `Topic` count is stable
- the target is roughly **33 topics**
- topics are concepts, not every noun seen in text

The export currently contains exactly these 33 topics:

`accounting, backorders, brain, brevo, customers, dashboard, dns, docker, email_ops, financials, google_apis, happyrasta, hosting, invoice_processor, mcp, payments, people, po_generator, products, scheduling, scripts, security, session_continuity, shipping, spam_filter, stock, stores, supplementsam, suppliers, testing, toughaudio, website, woocommerce`

### Why it works

The cap prevents the classic graph-RAG failure mode:

- too many ad hoc topic nodes
- near-duplicate topics
- brittle retrieval because the semantic surface explodes

With only ~33 topics:

- links stay dense
- topic pages stay meaningful
- traversal quality improves
- naming becomes a governed ontology, not tag soup

### How it seems to be implemented

Important nuance: in the code reviewed, the cap is mostly a **governance rule**, not a hard DB constraint.

There is lightweight extraction logic:

```python
patterns = [
    r'invoice[\s_]processor', r'spam[\s_]filter', r'link[\s_]audio',
    ...
]
...
return list(topics)[:10]
```

So the real mechanism is:

1. keep a small, manually chosen vocabulary
2. extract only from known patterns / known concepts
3. limit per-document topic fan-out
4. resist adding new topics casually

### Recommendation for agentic-brain

Adopt the principle, but tighten the mechanism:

- maintain a **governed topic registry**
- require review before adding a new topic
- cap per artifact/session to a small number (for example 3-10)
- periodically merge or delete low-value topics

Do **not** copy the exact number 33 blindly. Copy the idea of a **small stable ontology**. For agentic-brain, a target band like **24-40** may be healthier unless a stronger ontology already exists.

### Adaptable Cypher examples

#### A. Enforce only approved topics at write time
```cypher
UNWIND $topics AS topic_name
MATCH (t:TopicRegistry {name: topic_name, active: true})
WITH collect(t.name) AS approved
MATCH (s:Session {id: $session_id})
UNWIND approved AS topic_name
MERGE (t:Topic {name: topic_name})
MERGE (s)-[:DISCUSSES]->(t)
```

#### B. Find candidate topic sprawl
```cypher
MATCH (t:Topic)
OPTIONAL MATCH (n)-[r]->(t)
WITH t, count(r) AS incoming
RETURN t.name, incoming
ORDER BY incoming ASC, t.name
```

#### C. Detect near-duplicate topic names for cleanup
```cypher
MATCH (t1:Topic), (t2:Topic)
WHERE id(t1) < id(t2)
  AND toLower(t1.name) CONTAINS toLower(t2.name)
RETURN t1.name, t2.name
ORDER BY t1.name, t2.name
```

#### D. Hard cap guardrail (application-side policy query)
```cypher
MATCH (t:Topic)
RETURN count(t) AS topic_count
```
Application rule: reject new topic creation when `topic_count >= $cap` unless explicitly approved.

### Verdict

**Adopt the principle.**

Do not copy the literal `33` unless agentic-brain wants that exact size. Copy the **controlled ontology discipline**.

---

## 3. Node labeling conventions

### What is clean and proven

HappySkies mostly follows these label conventions:

### A. Singular PascalCase labels
Examples:

- `Project`
- `Component`
- `ComponentDoc`
- `Automation`
- `Topic`
- `Session`
- `Checkpoint`
- `HookEvent`
- `EmailAccount`
- `BrainBenchmark`

This is clean and worth copying.

### B. Labels encode graph layer / role
The strongest pattern is not syntax, but **separation by layer**:

- **Raw capture**: `HookEvent`
- **Curated session knowledge**: `Session`, `Checkpoint`, `SessionSummary`, `Learning`, `Memory`
- **Domain entities**: `Project`, `Component`, `Automation`, `Store`, `Supplier`, `Person`, `Brand`
- **Operational config**: `EmailAccount`, `SpamDomain`, `WhitelistEntry`
- **Meta / scoring**: `BrainBenchmark`, `BaselineScore`

This is one of the best patterns in the system.

### C. Labels represent node kind, not status
Status usually lives in properties:

- `Task.status`
- `Distributor.status`
- `Memory.updated_at`

That is clean.

### D. Unique constraints use natural identity keys
Examples from code:

- `Project.name` unique
- `Distributor.name` unique
- `EmailAccount.name` unique
- `Task.id` unique
- `Session.id` unique
- `Checkpoint.id` unique
- `Memory.key` unique

This is a solid default pattern.

### What is not clean enough to copy directly

There is some schema drift:

- docs talk about `Supplier`, code also uses `Distributor`
- benchmark config mentions `CoreItem`
- export contains both `TAGGED` and `TAGGED_BY`

So the **labeling style** is good, but the **vocabulary governance** is imperfect.

### Recommendation for agentic-brain

Adopt these conventions:

1. Singular PascalCase labels.
2. One label family per layer.
3. Status in properties, not new labels.
4. Natural unique keys or stable IDs per node class.
5. Maintain a schema registry so synonyms do not proliferate.

### Adaptable Cypher examples

#### A. Constraint creation pattern
```cypher
CREATE CONSTRAINT agent_id IF NOT EXISTS
FOR (a:Agent)
REQUIRE a.id IS UNIQUE
```

```cypher
CREATE CONSTRAINT topic_name IF NOT EXISTS
FOR (t:Topic)
REQUIRE t.name IS UNIQUE
```

#### B. Label-by-layer example
```cypher
MERGE (e:HookEvent {id: $id})
SET e.content = $content,
    e.timestamp = datetime($timestamp)

MERGE (s:Session {id: $session_id})
SET s.updated_at = datetime()

MERGE (a:Agent {id: $agent_id})
SET a.name = $agent_name,
    a.kind = $agent_kind
```

### Verdict

**Adopt with cleanup.**

Copy the label discipline. Do not copy the naming drift.

---

## 4. Relationship patterns

### What is clean and proven

HappySkies uses a small set of relationship families that are easy to reason about.

### A. Structural hierarchy
Examples:

- `Project-[:HAS_COMPONENT]->Component`
- `Component-[:HAS_DOC]->ComponentDoc`
- `Component-[:HAS]->Automation`
- `Project-[:HAS_SESSION]->Session`

Pattern: use `HAS_*` only for durable containment/ownership.

### B. Domain facts
Examples:

- `Brand-[:SOLD_BY]->Store`
- `Brand-[:SUPPLIED_BY]->Supplier`
- `Supplier-[:SUPPLIES_TO]->Store`
- `Person-[:CONTACT_FOR]->Supplier`

Pattern: domain verbs are directional and human-readable.

### C. Semantic attachment to topics
Examples:

- `Entity-[:RELATES_TO]->Topic`
- `Session-[:DISCUSSES]->Topic`
- `Checkpoint-[:DISCUSSES]->Topic`
- `SessionSummary-[:COVERS]->Topic`
- `Memory-[:TAGGED]->Topic`
- `Learning-[:TAGGED]->Topic`
- `BrainBenchmark-[:ABOUT]->Topic`

Pattern: different relationship verbs signal different evidence strengths.

### D. Provenance / distillation
Examples:

- `HookEvent-[:PART_OF]->Session`
- `Learning-[:PRODUCED_BY]->Session`

Pattern: keep raw source and curated artifact connected, but indirectly.

### E. Operational attachment
Examples:

- `Project-[:MANAGES_ACCOUNT]->EmailAccount`
- `Project-[:BLOCKS_DOMAIN]->SpamDomain`
- `Project-[:WHITELISTS]->WhitelistEntry`

Pattern: operational config attaches to the owning project, not to semantic topics.

### What to avoid copying

- duplicate semantics (`TAGGED` and `TAGGED_BY` both pointing to `Topic`)
- relationship proliferation without governance
- placeholder dependency edges just to satisfy benchmark scores

### Recommendation for agentic-brain

Adopt four explicit relationship buckets:

1. **STRUCTURE**: `HAS_COMPONENT`, `HAS_TOOL`, `HAS_MEMORY_STORE`
2. **DOMAIN FACT**: `OWNS`, `RUNS`, `USES`, `DEPENDS_ON` only when real
3. **SEMANTIC**: `RELATES_TO`, `DISCUSSES`, `COVERS`, `TAGGED`
4. **PROVENANCE / OPERATIONAL**: `PART_OF`, `PRODUCED_BY`, `MANAGES_ACCOUNT`

Prefer one canonical edge per meaning.

### Adaptable Cypher examples

#### A. Hierarchy + documentation
```cypher
MATCH (p:Project {id: $project_id})
MERGE (c:Component {id: $component_id})
SET c.name = $component_name
MERGE (p)-[:HAS_COMPONENT]->(c)

MERGE (d:ComponentDoc {id: $doc_id})
SET d.content = $content
MERGE (c)-[:HAS_DOC]->(d)
```

#### B. Provenance for distilled learnings
```cypher
MATCH (s:Session {id: $session_id})
MERGE (l:Learning {id: $learning_id})
SET l.content = $content,
    l.created_at = datetime()
MERGE (l)-[:PRODUCED_BY]->(s)
```

#### C. Real dependency only when justified
```cypher
MATCH (a:Automation {id: $from_id})
MATCH (b:Automation {id: $to_id})
MERGE (a)-[:DEPENDS_ON]->(b)
```
Only create this when execution or correctness truly depends on it.

#### D. Supply-chain style pattern reusable for agent ecosystems
```cypher
MATCH (cap:Capability {name: $capability})
MATCH (agent:Agent {id: $agent_id})
MATCH (surface:Surface {name: $surface})
MERGE (agent)-[:PROVIDES]->(cap)
MERGE (cap)-[:SERVES]->(surface)
```

### Verdict

**Adopt.**

Especially the rule: **different verbs for different evidence strengths**.

---

## 5. Query patterns that are reusable

These are the most reusable Cypher patterns I found.

### Pattern A: topic-centered retrieval

Use a controlled union of semantic edge types to answer cross-cutting questions.

```cypher
MATCH (n)-[r:RELATES_TO|DISCUSSES|TAGGED|COVERS|ABOUT]->(t:Topic {name: $topic})
RETURN labels(n)[0] AS label,
       coalesce(n.name, n.title, n.key, n.id) AS item,
       type(r) AS via
ORDER BY label, item
```

Why it is reusable:
- one query can surface sessions, entities, learnings, and meta nodes
- good for RAG context assembly
- works well only if topic vocabulary is controlled

### Pattern B: latest-state lookup

HappySkies repeatedly uses `ORDER BY ... DESC LIMIT 1` for current context.

```cypher
MATCH (c:Checkpoint)
RETURN c.title AS title, c.file AS file
ORDER BY c.modified DESC
LIMIT 1
```

Adapted for agentic-brain:

```cypher
MATCH (s:Session)
RETURN s.id, s.title, s.updated_at
ORDER BY s.updated_at DESC
LIMIT 1
```

### Pattern C: structured search first, raw events second

HappySkies searches `SessionSummary` before `HookEvent`. That is exactly right.

```cypher
MATCH (ss:SessionSummary)
WHERE toLower(ss.overview) CONTAINS toLower($query)
   OR toLower(ss.work_done) CONTAINS toLower($query)
   OR toLower(ss.title) CONTAINS toLower($query)
RETURN ss.title, ss.overview, ss.work_done
LIMIT 5
```

Then fallback:

```cypher
MATCH (e:HookEvent)
WHERE toLower(e.content) CONTAINS toLower($query)
RETURN e.timestamp, e.primary_topic, e.content
ORDER BY e.timestamp DESC
LIMIT $limit
```

Why it is reusable:
- prioritizes curated summaries over noisy logs
- still preserves auditability when summaries miss details

### Pattern D: optional expansion without losing the parent node

```cypher
MATCH (p:Project)
OPTIONAL MATCH (p)-[:HAS_COMPONENT]->(c:Component)
RETURN p.name AS project, collect(c.name) AS components
ORDER BY p.name
```

Why it is reusable:
- ideal for dashboards
- prevents empty child sets from dropping the parent row

### Pattern E: profile completeness / coverage query

```cypher
MATCH (d:Supplier)
RETURN d.name, size(keys(d)) AS props
ORDER BY props DESC
LIMIT 1
```

Why it is reusable:
- quick schema-health signal
- useful when deciding which entity types are mature enough for automation

### Pattern F: topic connectivity health

```cypher
MATCH (t:Topic)<-[r]-()
RETURN t.name, count(r) AS inbound_links
ORDER BY inbound_links DESC
LIMIT 10
```

And:

```cypher
MATCH (n)-[]->(t:Topic)
RETURN count(DISTINCT labels(n)[0]) AS inbound_label_types
```

Why it is reusable:
- measures whether topics are actually acting as shared semantic hubs

### Pattern G: short path sanity check

HappySkies benchmark checks whether a known anchor can reach a topic within a few hops.

```cypher
MATCH p = shortestPath((s:Store {name: $anchor})-[*..4]-(t:Topic {name: $topic}))
RETURN length(p) AS hops
LIMIT 1
```

Why it is reusable:
- good as a graph-health benchmark
- do not overuse in production query paths

### Pattern H: distinct-count aggregation for dashboards

```cypher
MATCH (p:Project)
OPTIONAL MATCH (p)-[:HAS_TASK]->(t:Task)
  WHERE t.status IN ['pending', 'in_progress']
OPTIONAL MATCH (p)-[:HAS_DISTRIBUTOR]->(d:Distributor)
  WHERE d.status <> 'working'
RETURN p.name,
       count(DISTINCT t) AS open_tasks,
       count(DISTINCT d) AS flagged_distributors
```

Why it is reusable:
- safe against row multiplication
- great for operational dashboards

---

## What I would recommend adopting for agentic-brain

### Strong adopt

1. **Topic-centric semantic overlay** on top of direct factual edges.
2. **Small controlled topic vocabulary**.
3. **Layer separation**: raw events vs curated knowledge vs domain graph vs operational config vs metrics.
4. **Directional verb relationships** with distinct meanings.
5. **Search curated summaries first, raw logs second**.
6. **Benchmark the graph using traversal questions**, not only counts.

### Adopt with modifications

1. Topic cap concept → yes, but set agentic-brain's own range.
2. Constraints → expand and standardize them more than HappySkies does.
3. Semantic relationships → collapse to one canonical form where possible (`TAGGED`, not both `TAGGED` and `TAGGED_BY`).

### Do not copy blindly

1. Schema drift between `Supplier` and `Distributor`.
2. Benchmark targets that pressure the graph into artificial edges.
3. Legacy labels mentioned in benchmark config but not consistently used in the live graph.

---

## Best concise pattern statement

If I had to reduce the HappySkies lesson to one sentence for agentic-brain:

> Build a **layered graph** where raw events stay raw, curated artifacts link to a **small governed topic ontology**, and durable domain entities keep their own direct factual edges.

That is the part that is proven, clean, and worth adopting.
