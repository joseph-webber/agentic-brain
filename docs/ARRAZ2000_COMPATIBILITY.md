# Arraz2000 Graph RAG Compatibility Guide

> **Status**: Framework Ready — awaiting Arraz2000's public Graph RAG repositories
> **Last Updated**: 2026-07-22
> **Author**: Joseph Webber (contributor to Arraz2000's work)

---

## Overview

This document defines how **agentic-brain**'s Graph RAG implementation
maintains compatibility with **Arraz2000**'s Graph RAG patterns and the
broader Neo4j Graph RAG ecosystem, ensuring we *extend* rather than replace
external frameworks.

### GitHub User

- **Username**: [Arraz2000](https://github.com/Arraz2000)
- **Status**: Public Graph RAG repos not yet published (as of 2026-07-22).
  Once published, this document will be updated with specific repo links,
  schema mappings, and migration guides.

---

## Our Neo4j Schema (Compatibility Surface)

agentic-brain uses the following graph schema that aligns with standard
Neo4j Graph RAG patterns (Microsoft GraphRAG, neo4j-graphrag Python
package, LangChain/LlamaIndex integrations):

### Node Labels

| Label      | Key Properties                                   | Purpose                    |
|------------|--------------------------------------------------|----------------------------|
| `Document` | `id` (unique), `content`, `timestamp`, `metadata`| Source documents           |
| `Chunk`    | `id` (unique), `text`, `embedding`, `position`   | Document chunks + vectors  |
| `Entity`   | `id` (unique), `name`, `type`, `description`     | Extracted knowledge entities|

### Relationship Types

| Relationship  | Pattern                    | Purpose                        |
|---------------|----------------------------|--------------------------------|
| `CONTAINS`    | `(Document)-[:CONTAINS]->(Chunk)` | Doc → chunk hierarchy    |
| `MENTIONS`    | `(Document)-[:MENTIONS]->(Entity)` | Doc/chunk → entity links|
| `MENTIONS`    | `(Chunk)-[:MENTIONS]->(Entity)`    | Chunk → entity links    |
| `RELATED_TO`  | `(Entity)-[:RELATED_TO]->(Entity)` | Entity relationships    |
| `PART_OF`     | `(Entity)-[:PART_OF]->(Entity)`    | Hierarchical membership |

### Indexes

| Index Name          | Type      | Target                                |
|---------------------|-----------|---------------------------------------|
| `chunk_embeddings`  | Vector    | `Chunk.embedding` (384d, cosine)      |
| `entity_fulltext`   | Fulltext  | `Entity.name`, `Entity.description`   |
| `chunk_fulltext`    | Fulltext  | `Chunk.content`                       |
| `document_fulltext` | Fulltext  | `Document.content`, `Document.title`  |
| `entity_type`       | Range     | `Entity.type`                         |

### Entity Types Supported

`PERSON`, `ORGANIZATION`, `LOCATION`, `CONCEPT`, `TECHNOLOGY`

---

## How We Extend (Not Replace)

### Design Principle

agentic-brain is built to be a **superset** of standard Graph RAG patterns:

1. **Standard Schema First** — Our `Document → Chunk → Entity` schema
   follows the same patterns used by neo4j-graphrag, Microsoft GraphRAG,
   and LangChain's Neo4jGraph. Any data written by external tools should
   be queryable by our retrieval pipeline.

2. **Additional Metadata** — We add fields like `first_seen`, `last_seen`,
   `mention_count`, `community_id` that enrich but don't break baseline
   compatibility.

3. **Multiple Retrieval Strategies** — Vector, Graph, Hybrid, Community,
   and Multi-hop. External data only needs the base schema to work with
   our vector and graph strategies.

4. **Community Detection is Optional** — Leiden/Louvain community metadata
   is layered on top. Graphs without community annotations still work
   perfectly with all other search strategies.

### Import Path for External Data

To import data from any standard Neo4j Graph RAG format:

```python
from agentic_brain.rag.graph import EnhancedGraphRAG

rag = EnhancedGraphRAG()
await rag.initialize()  # Creates constraints + indexes if missing

# Option 1: Index raw text (we handle extraction)
await rag.index_document(content="...", doc_id="external_001")

# Option 2: Import pre-extracted entities via GraphRAG class
from agentic_brain.rag.graph_rag import GraphRAG
grag = GraphRAG()
await grag.ingest([{
    "entities": [
        {"id": "e1", "type": "PERSON", "description": "Alice"},
        {"id": "e2", "type": "ORGANIZATION", "description": "Acme Corp"},
    ],
    "relationships": [
        {"source": "e1", "target": "e2", "type": "WORKS_AT", "weight": 1.0},
    ],
}])

# Option 3: Direct Cypher for maximum flexibility
from agentic_brain.core.neo4j_pool import get_session
with get_session() as session:
    session.run("""
        MERGE (e:Entity {id: $id})
        SET e.name = $name, e.type = $type
    """, id="custom_1", name="Bob", type="PERSON")
```

---

## Compatibility Matrix

| Feature                        | agentic-brain | neo4j-graphrag | Microsoft GraphRAG | LangChain Neo4j |
|-------------------------------|---------------|----------------|---------------------|-----------------|
| Document → Chunk → Entity     | ✅            | ✅             | ✅                  | ✅              |
| Vector embeddings on chunks   | ✅            | ✅             | ✅                  | ✅              |
| Entity extraction (NER)       | ✅ (built-in) | ✅ (LLM)      | ✅ (LLM)           | ✅ (LLM)        |
| Relationship extraction       | ✅            | ✅             | ✅                  | ✅              |
| Community detection (Leiden)  | ✅            | ❌             | ✅                  | ❌              |
| Hybrid search (RRF)           | ✅            | ✅             | ❌                  | ✅              |
| MLX/Apple Silicon acceleration| ✅            | ❌             | ❌                  | ❌              |
| Batched UNWIND writes         | ✅            | ✅             | ✅                  | ❌              |
| Async Neo4j driver            | ✅            | ✅             | ❌                  | ✅              |
| Entity resolution             | ✅            | ❌             | ✅                  | ❌              |
| Multi-hop reasoning           | ✅            | ❌             | ❌                  | ❌              |

---

## Migration Guide

### From Any Standard Neo4j Graph RAG → agentic-brain

If Arraz2000 (or any contributor) has an existing Neo4j database with
Graph RAG data:

#### Step 1: Verify Schema Compatibility

```cypher
// Check existing node labels
CALL db.labels() YIELD label RETURN label

// Check existing relationship types
CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType

// Check existing indexes
SHOW INDEXES
```

#### Step 2: Add Missing Constraints (Safe — IF NOT EXISTS)

```cypher
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;
```

#### Step 3: Add Vector Index (If Missing)

```cypher
CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}};
```

#### Step 4: Enrich with agentic-brain Metadata

```cypher
// Add timestamps to entities missing them
MATCH (e:Entity) WHERE e.first_seen IS NULL
SET e.first_seen = datetime(), e.last_seen = datetime();

// Add mention counts
MATCH (e:Entity)<-[r:MENTIONS]-()
WITH e, count(r) AS mentions
SET e.mention_count = mentions;
```

#### Step 5: Run Community Detection (Optional)

```python
from agentic_brain.rag.community_detection import detect_communities
# Requires Neo4j GDS plugin for Leiden; falls back to Louvain or connected components
communities = detect_communities(session)
```

---

## Arraz2000 Specific Notes

> **This section will be updated** when Arraz2000's Graph RAG repositories
> become publicly available.

### What We Know

- GitHub: [github.com/Arraz2000](https://github.com/Arraz2000)
- Joseph is a contributor to Arraz2000's work
- Graph RAG repos may be private or in development

### When Repos Are Published, Update This Section With:

- [ ] Specific repository URLs and descriptions
- [ ] Schema differences (if any) and mapping guide
- [ ] Entity type mappings (their types → our types)
- [ ] Relationship type mappings
- [ ] Embedding model compatibility (dimension matching)
- [ ] Import/export scripts
- [ ] Joint test suite

### Integration Principles

1. **Never break Arraz2000's schema** — add, don't modify
2. **Support both schemas** — if they use different labels, create adapters
3. **Share entity types** — align on PERSON, ORGANIZATION, LOCATION, etc.
4. **Compatible embeddings** — support configurable dimensions (384, 768, 1536)
5. **Bidirectional** — data should flow both ways between implementations

---

## Testing Compatibility

Run the compatibility test suite:

```bash
cd ~/brain/agentic-brain
python -m pytest tests/test_graphrag_compatibility.py -v
```

Tests verify:
- Schema creation is idempotent (safe to run on existing databases)
- Entity/relationship data round-trips correctly
- External Graph RAG data can be queried by our retrieval pipeline
- Community detection handles graphs with/without pre-existing metadata
- Embedding dimensions are validated and configurable

---

## Contact

- **Joseph Webber** — joseph.webber@gmail.com
- **Repository** — [github.com/ecomlounge/brain](https://github.com/ecomlounge/brain)
