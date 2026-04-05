# Community RAG Specification

## Overview

The Community RAG implementation in `agentic_brain.rag` now supports full hierarchical community workflows while remaining optional for simple retrieval use cases.

## Goals

- expose important Leiden controls for tuning graph partitions
- support 4+ hierarchy levels for multi-scale retrieval and summarization
- summarize communities at every hierarchy level
- dynamically choose the best hierarchy level for each query
- calculate quality metrics for every detected community and hierarchy level
- allow callers to disable community features entirely

## Community Detection (`community_detection.py`)

### Leiden controls

The hierarchical detector supports these parameters:

- `resolution`: base Leiden resolution (defaults to `gamma` when omitted)
- `n_iterations`: maximum Leiden iterations
- `randomness`: random seed used to control deterministic partitioning
- `resolution_multiplier`: scales the resolution schedule between hierarchy levels
- `max_levels`: maximum hierarchy depth to explore

### Hierarchy semantics

- level `0` is the leaf / most granular partition
- larger level numbers are progressively coarser partitions
- the default configuration supports at least 4 levels
- duplicate adjacent partitions are skipped automatically

### Metrics

Each `Community` stores:

- `modularity_score`
- `coverage_score`
- `cohesion_score`
- `resolution`
- `n_iterations`
- `randomness`

Each `CommunityHierarchy` stores:

- `parameters`
- `level_metrics`
- `summaries_by_level`

### Summaries

`summary_all_communities()` can summarize one level or the full hierarchy.

Summary generation order is bottom-up:

1. leaf communities
2. intermediate communities
3. global / top communities

Parent summaries can reuse child summaries when available.

### Optional mode

`detect_communities_hierarchical(..., enabled=False)` returns an empty disabled hierarchy without touching Neo4j GDS.

## Community Graph RAG (`community.py`)

### Optional communities

`CommunityGraphRAG` accepts `enable_communities=False`.

When disabled:

- `detect_communities()` returns `{}`
- `summarize_communities()` returns `{}`
- `build_hierarchy()` returns `{0: []}`
- routing never selects the `community` strategy
- hybrid retrieval falls back to entity retrieval

### Dynamic level selection

`select_optimal_level(query)` chooses an appropriate hierarchy level using:

- query length
- reasoning markers (`compare`, `across`, `relationships`, `themes`, etc.)
- global-vs-local query heuristics

Selection rules:

- global questions prefer the highest level
- local questions prefer the lowest community level
- mixed questions map complexity onto the available community levels

### Built hierarchy

`build_hierarchy()` returns:

- level `0`: entity placeholders
- level `1`: leaf communities
- levels `2..N-1`: synthetic roll-up communities
- level `N`: global theme

This allows 4+ community levels even when the raw detector yields fewer persisted levels.

## Persistence Model

Persisted `:Community` nodes include:

- `id`
- `level`
- `members`
- `memberCount`
- `summary`
- `metadata`
- `updatedAt`

Relationships:

- `(:Entity)-[:IN_COMMUNITY]->(:Community)`
- `(:Community)-[:HAS_SUBCOMMUNITY]->(:Community)`

## Query Routing

### Strategies

- `entity`: simple, local questions
- `community`: global / thematic questions
- `hybrid`: mixed reasoning queries

### Query result metadata

`CommunityQueryResult` now includes:

- `strategy`
- `results`
- `hierarchy_level`
- `query_complexity`

## Testing

Advanced coverage is provided in `tests/test_rag/test_community_advanced.py` and includes:

- hierarchy depth
- summary generation
- dynamic selection
- optional mode
- metrics
- fallback behavior
- persistence payloads
